"""明细生成任务（invoice_detail_generator）单元测试

覆盖三段式任务体的核心契约：
1. 主会话在计费项查询后 commit+close（释放 PG 连接，不覆盖 Excel 构建段）
2. 终态更新走 session_factory 短会话（传了工厂时不再用主会话）
3. 传了工厂时，InvoiceExcelService 收到同一工厂（余额查询用短会话）
4. 未传工厂时回退主会话（向后兼容）
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tasks.invoice_detail_generator import generate_invoice_detail


def _make_invoice(**overrides):
    inv = MagicMock()
    inv.id = 7001
    inv.customer_id = 42
    inv.status = "pending_customer"
    inv.detail_file_status = "pending"
    inv.period_start = MagicMock()
    inv.period_end = MagicMock()
    inv.total_amount = Decimal("100.00")
    inv.discount_amount = Decimal("0.00")
    for k, v in overrides.items():
        setattr(inv, k, v)
    return inv


def _make_session(invoice, customer=None):
    """构造假 AsyncSession：get/session.get 按类型返回 invoice/customer"""
    session = MagicMock()
    session.get = AsyncMock(
        side_effect=lambda model, _id: invoice
        if model.__name__ == "Invoice"
        else (customer or MagicMock())
    )
    session.commit = AsyncMock()
    session.close = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    return session


def _make_factory(invoice, customer=None):
    """构造假 async_sessionmaker：__call__ 返回支持 async with 的会话"""
    factory_session = _make_session(invoice, customer)

    class _Factory:
        def __call__(self):
            return factory_session

    # async_sessionmaker() 返回的是 AsyncSession 实例（本身即异步上下文管理器）
    factory_session.__aenter__ = AsyncMock(return_value=factory_session)
    factory_session.__aexit__ = AsyncMock(return_value=False)
    return _Factory(), factory_session


class TestDetailGeneratorThreePhase:
    """三段式任务体契约"""

    @pytest.mark.asyncio
    async def test_main_session_closed_before_build(self, monkeypatch):
        """主会话必须在构建前 commit+close（连接不覆盖构建段）"""
        invoice = _make_invoice()
        customer = MagicMock()
        customer.company_id = 99
        customer.name = "测试客户"
        session = _make_session(invoice, customer)

        factory, factory_session = _make_factory(invoice, customer)

        order = []
        orig_close = session.close
        orig_commit = session.commit

        async def tracked_commit():
            await orig_commit()
            order.append("main_commit")

        async def tracked_close():
            await orig_close()
            order.append("main_close")

        session.commit = tracked_commit
        session.close = tracked_close

        from app.services import invoice_excel

        built = {"called": False}

        async def fake_generate(self, **kwargs):
            # 构建发生时主会话必须已关闭
            assert "main_close" in order, "构建前主会话未关闭（连接覆盖构建段）"
            assert self.session_factory is factory, "service 未收到 session_factory"
            built["called"] = True
            return "invoices/2026/09/invoice_7001.xlsx"

        monkeypatch.setattr(
            invoice_excel.InvoiceExcelService, "generate_detail_file", fake_generate
        )

        await generate_invoice_detail(session, None, 7001, session_factory=factory)

        assert built["called"], "generate_detail_file 未被调用"
        # 终态更新走工厂短会话
        assert factory_session.commit.await_count >= 1
        assert factory_session.get.await_count >= 1

    @pytest.mark.asyncio
    async def test_final_status_via_factory_short_session(self, monkeypatch):
        """传工厂时终态 completed 写入工厂会话，而非已关闭的主会话"""
        invoice = _make_invoice()
        customer = MagicMock()
        customer.company_id = 99
        customer.name = "测试客户"
        session = _make_session(invoice, customer)
        factory, factory_session = _make_factory(invoice, customer)

        from app.services import invoice_excel

        async def fake_generate(self, **kwargs):
            return "invoices/2026/09/invoice_7001.xlsx"

        monkeypatch.setattr(
            invoice_excel.InvoiceExcelService, "generate_detail_file", fake_generate
        )

        await generate_invoice_detail(session, None, 7001, session_factory=factory)

        # 终态更新走工厂会话：get 一次 + commit 一次
        assert factory_session.get.await_count == 1
        assert factory_session.commit.await_count == 1
        assert session.commit.await_count == 2  # generating + 释放连接前

    @pytest.mark.asyncio
    async def test_fallback_without_factory(self, monkeypatch):
        """未传工厂（兼容旧调用/测试）：终态回退主会话"""
        invoice = _make_invoice()
        customer = MagicMock()
        customer.company_id = 99
        customer.name = "测试客户"
        session = _make_session(invoice, customer)

        from app.services import invoice_excel

        async def fake_generate(self, **kwargs):
            # 无工厂时构建前主会话仍应关闭（连接缩短与工厂无关）
            assert session.close.await_count >= 1
            assert self.session_factory is None
            return "invoices/2026/09/invoice_7001.xlsx"

        monkeypatch.setattr(
            invoice_excel.InvoiceExcelService, "generate_detail_file", fake_generate
        )

        await generate_invoice_detail(session, None, 7001)

        # 回退路径：重新打开主会话 get + commit 更新终态
        assert session.get.await_count >= 2  # 首次查询 + 终态回退查询

    @pytest.mark.asyncio
    async def test_exception_marks_failed_via_factory(self, monkeypatch):
        """构建抛异常时经工厂短会话兜底置 failed"""
        invoice = _make_invoice()
        customer = MagicMock()
        customer.company_id = 99
        customer.name = "测试客户"
        session = _make_session(invoice, customer)
        factory, factory_session = _make_factory(invoice, customer)

        from app.services import invoice_excel

        async def boom(self, **kwargs):
            raise RuntimeError("外部库炸了")

        monkeypatch.setattr(invoice_excel.InvoiceExcelService, "generate_detail_file", boom)

        # 不抛异常出去（内部已兜底）
        await generate_invoice_detail(session, None, 7001, session_factory=factory)

        # 兜底也走工厂会话
        assert factory_session.get.await_count >= 1
        assert factory_session.commit.await_count >= 1
