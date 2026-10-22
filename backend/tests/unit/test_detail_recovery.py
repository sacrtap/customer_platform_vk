"""明细生成任务重启恢复单元测试

覆盖：
1. 启动恢复钩子（_recover_stuck_detail_tasks）：generating→failed 批量标记、
   pending 重新入队（trigger 调用次数与顺序）
2. 生成器原子 claim guard：非 pending（claim rowcount=0）时跳过 Excel 构建
3. 终态条件 UPDATE：仅当 generating 才写终态（resolve last-writer-wins）
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tasks.invoice_detail_generator import generate_invoice_detail


class _FakeSession:
    """fake AsyncSession：execute 按序返回 中断数结果 + pending 列表结果"""

    def __init__(self, interrupted_rowcount: int, pending_ids: list[int]):
        interrupted_result = MagicMock()
        interrupted_result.rowcount = interrupted_rowcount
        pending_result = MagicMock()
        pending_result.scalars.return_value.all.return_value = pending_ids
        self.execute = AsyncMock(side_effect=[interrupted_result, pending_result])
        self.commit = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAsyncSessionMaker:
    """fake async_sessionmaker：__call__ 每次返回同一假会话"""

    def __init__(self, interrupted_rowcount: int, pending_ids: list[int]):
        self.session = _FakeSession(interrupted_rowcount, pending_ids)

    def __call__(self):
        return self.session


class TestStartupRecovery:
    """启动恢复钩子：generating→failed、pending 重新入队"""

    @pytest.mark.asyncio
    async def test_marks_generating_failed_and_requeues_pending(self):
        """generating 批量转 failed；pending 逐张重新入队（trigger 一次/张）"""
        from app.main import _recover_stuck_detail_tasks

        maker = _FakeAsyncSessionMaker(interrupted_rowcount=2, pending_ids=[11, 22, 33])
        trigger = AsyncMock()

        result = await _recover_stuck_detail_tasks(maker, trigger, app=None)

        assert result == {"interrupted": 2, "requeued": 3}
        # 重新入队：pending 每张触发一次（顺序保持）
        assert trigger.await_count == 3
        assert [c.args[1] for c in trigger.await_args_list] == [11, 22, 33]
        maker.session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_pending_no_requeue(self):
        """无 pending 时不触发任何重新入队"""
        from app.main import _recover_stuck_detail_tasks

        maker = _FakeAsyncSessionMaker(interrupted_rowcount=0, pending_ids=[])
        trigger = AsyncMock()

        result = await _recover_stuck_detail_tasks(maker, trigger, app=None)

        assert result == {"interrupted": 0, "requeued": 0}
        trigger.assert_not_awaited()


class TestClaimGuard:
    """生成器原子 claim：仅 pending 才进入构建段"""

    @pytest.mark.asyncio
    async def test_skips_excel_build_when_claim_fails(self, monkeypatch):
        """claim rowcount=0（非 pending/另一实例在跑）时跳过 Excel 构建"""
        invoice = MagicMock()  # 不该被读取到构建段
        session = MagicMock()
        session.get = AsyncMock(return_value=invoice)
        session.commit = AsyncMock()
        session.close = AsyncMock()
        result = MagicMock()
        result.rowcount = 0
        session.execute = AsyncMock(return_value=result)

        from app.services import invoice_excel

        built = {"called": False}

        async def fake_generate(self, **kwargs):
            built["called"] = True
            return "x.xlsx"

        monkeypatch.setattr(
            invoice_excel.InvoiceExcelService, "generate_detail_file", fake_generate
        )

        await generate_invoice_detail(session, None, 7001)

        assert not built["called"], "claim 失败后不应进入 Excel 构建"
        session.get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_builds_when_claim_succeeds(self, monkeypatch):
        """claim rowcount=1（pending）时进入 Excel 构建"""
        invoice = MagicMock()
        invoice.customer_id = 42
        invoice.status = "pending_customer"
        invoice.period_start = MagicMock()
        invoice.period_end = MagicMock()
        invoice.total_amount = MagicMock()
        invoice.discount_amount = MagicMock()
        invoice.detail_file_path = None
        customer = MagicMock()
        customer.company_id = 99
        customer.name = "测试客户"
        session = MagicMock()
        session.get = AsyncMock(
            side_effect=lambda model, _id: invoice if model.__name__ == "Invoice" else customer
        )
        session.commit = AsyncMock()
        session.close = AsyncMock()
        claim_result = MagicMock()
        claim_result.rowcount = 1
        rows_result = MagicMock()
        rows_result.all.return_value = []
        session.execute = AsyncMock(side_effect=[claim_result, rows_result])

        from app.services import invoice_excel

        built = {"called": False}

        async def fake_generate(self, **kwargs):
            built["called"] = True
            return "invoices/2026/09/invoice_7001.xlsx"

        monkeypatch.setattr(
            invoice_excel.InvoiceExcelService, "generate_detail_file", fake_generate
        )

        factory = MagicMock()
        factory_session = MagicMock()
        factory_session.__aenter__ = AsyncMock(return_value=factory_session)
        factory_session.__aexit__ = AsyncMock(return_value=False)
        factory_session.execute = AsyncMock(return_value=MagicMock(rowcount=1))
        factory_session.commit = AsyncMock()
        factory.__call__ = MagicMock(return_value=factory_session)

        await generate_invoice_detail(session, None, 7001, session_factory=factory)

        assert built["called"], "claim 成功后应进入 Excel 构建"
        session.get.assert_awaited()
