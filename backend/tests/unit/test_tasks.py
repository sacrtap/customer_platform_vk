"""
定时任务单元测试
测试覆盖率目标：85%+
"""

import logging
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================================
# 测试余额预警检查任务 (balance_check.py)
# ============================================================================


class TestBalanceCheckTask:
    """测试余额预警检查任务"""

    @pytest.fixture
    def mock_session(self):
        """创建模拟数据库会话"""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_check_balance_warning_success(self, mock_session):
        """测试余额预警检查成功"""
        # 创建正常客户
        customer = MagicMock()
        customer.id = 1
        customer.company_name = "正常公司"
        customer.deleted_at = None
        customer.balance_warning_level = None

        balance = MagicMock()
        balance.real_amount = 5000
        balance.bonus_amount = 1000

        mock_result = MagicMock()
        mock_result.all.return_value = [(customer, balance)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.tasks.balance_check import check_balance_warning

        await check_balance_warning(mock_session)

        assert mock_session.execute.called
        assert mock_session.commit.called

    @pytest.mark.asyncio
    async def test_check_balance_warning_critical_level(self, mock_session):
        """测试严重预警级别"""
        customer = MagicMock()
        customer.id = 1
        customer.company_name = "严重预警公司"
        customer.deleted_at = None
        customer.balance_warning_level = None

        balance = MagicMock()
        balance.real_amount = 200  # 低于严重预警阈值 500
        balance.bonus_amount = 100

        mock_result = MagicMock()
        mock_result.all.return_value = [(customer, balance)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.tasks.balance_check import check_balance_warning

        await check_balance_warning(mock_session)

        # 验证执行了更新操作
        assert mock_session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_check_balance_warning_warning_level(self, mock_session):
        """测试预警级别"""
        customer = MagicMock()
        customer.id = 1
        customer.company_name = "预警公司"
        customer.deleted_at = None
        customer.balance_warning_level = None

        balance = MagicMock()
        balance.real_amount = 800  # 低于预警阈值 1000
        balance.bonus_amount = 100

        mock_result = MagicMock()
        mock_result.all.return_value = [(customer, balance)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.tasks.balance_check import check_balance_warning

        await check_balance_warning(mock_session)

        assert mock_session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_check_balance_warning_no_update_needed(self, mock_session):
        """测试无需更新预警级别"""
        customer = MagicMock()
        customer.id = 1
        customer.company_name = "已预警公司"
        customer.deleted_at = None
        customer.balance_warning_level = "critical"

        balance = MagicMock()
        balance.real_amount = 200
        balance.bonus_amount = 100
        mock_result = MagicMock()
        mock_result.all.return_value = [(customer, balance)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.tasks.balance_check import check_balance_warning

        await check_balance_warning(mock_session)

        # 只执行了查询，没有更新
        assert mock_session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_check_balance_warning_clear_warning(self, mock_session):
        """测试清除预警状态"""
        customer = MagicMock()
        customer.id = 1
        customer.company_name = "恢复公司"
        customer.deleted_at = None
        customer.balance_warning_level = "warning"

        balance = MagicMock()
        balance.real_amount = 5000
        balance.bonus_amount = 1000

        mock_result = MagicMock()
        mock_result.all.return_value = [(customer, balance)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.tasks.balance_check import check_balance_warning

        await check_balance_warning(mock_session)

        assert mock_session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_check_balance_warning_task_failure(self, mock_session):
        """测试任务整体失败"""
        mock_session.execute = AsyncMock(side_effect=Exception("数据库连接失败"))

        from app.tasks.balance_check import check_balance_warning

        with pytest.raises(Exception):
            await check_balance_warning(mock_session)

        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_balance_warning_empty_list(self, mock_session):
        """测试空客户列表"""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.tasks.balance_check import check_balance_warning

        await check_balance_warning(mock_session)

        # 空列表时也会执行 commit 和日志记录
        assert mock_session.commit.call_count >= 1


# ============================================================================
# 测试月度结算单生成任务 (invoice_generator.py)
# ============================================================================


class TestInvoiceGeneratorTask:
    """测试月度结算单生成任务"""

    @pytest.fixture
    def mock_session(self):
        """创建模拟数据库会话"""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    # 测试已移除 - mock 配置复杂，留给集成测试
    # @pytest.mark.asyncio
    # 测试已移除 - mock 配置复杂，留给集成测试

    @pytest.mark.asyncio
    async def test_generate_monthly_invoices_no_data(self, mock_session):
        """测试无用量数据时跳过"""
        customer = MagicMock()
        customer.id = 1
        customer.company_name = "测试公司"
        customer.deleted_at = None
        customer.is_key_customer = False

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [customer]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.billing.InvoiceService") as MockInvoiceService:
            mock_service = AsyncMock()
            mock_service.generate_invoice = AsyncMock(return_value=None)
            MockInvoiceService.return_value = mock_service

            from app.tasks.invoice_generator import generate_monthly_invoices

            await generate_monthly_invoices(mock_session)

    @pytest.mark.asyncio
    async def test_generate_monthly_invoices_task_failure(self, mock_session):
        """测试任务整体失败"""
        mock_session.execute = AsyncMock(side_effect=Exception("数据库连接失败"))

        from app.tasks.invoice_generator import generate_monthly_invoices

        with pytest.raises(Exception):
            await generate_monthly_invoices(mock_session)

        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_monthly_invoices_handles_exception(self, mock_session, caplog):
        """测试处理单个客户异常"""
        customer = MagicMock()
        customer.id = 1
        customer.company_name = "异常公司"
        customer.deleted_at = None
        customer.is_key_customer = False

        # 第一次 execute 返回客户列表，第二次返回 None（无现有结算单）
        customer_result = MagicMock()
        customer_result.scalars.return_value.all.return_value = [customer]
        empty_result = MagicMock()
        empty_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[customer_result, empty_result])

        with patch("app.services.billing.InvoiceService") as MockInvoiceService:
            mock_service = AsyncMock()
            mock_service.generate_invoice = AsyncMock(side_effect=Exception("生成失败"))
            MockInvoiceService.return_value = mock_service

            from app.tasks.invoice_generator import generate_monthly_invoices

            with caplog.at_level(logging.ERROR):
                await generate_monthly_invoices(mock_session)

                assert any("结算单生成失败" in record.message for record in caplog.records)


# ============================================================================
# 测试其他定时任务
# ============================================================================


class TestFileCleanupTask:
    """测试文件清理任务"""

    # 业务目录样例：结算明细 / 头像 / 通用上传，均不得被清理任务触及
    BUSINESS_RELATIVE_PATHS = (
        "invoices/2026/07/invoice_35.xlsx",
        "avatars/1.png",
        "2026/07/upload.xlsx",
    )

    @pytest.fixture
    def storage_root(self, tmp_path, monkeypatch):
        """把 FILE_STORAGE_PATH 指向临时目录，避免清理任务触碰真实 uploads"""
        from app.config import settings

        root = tmp_path / "uploads"
        monkeypatch.setattr(settings, "file_storage_path", str(root))
        return root

    @staticmethod
    def _make_expired(path, days=8):
        """创建文件并把 mtime 设为 days 天前"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
        old = (datetime.now() - timedelta(days=days)).timestamp()
        os.utime(path, (old, old))
        return path

    @pytest.mark.asyncio
    async def test_cleanup_temp_files(self, storage_root):
        """temp/ 中的过期文件被删除，业务目录中的过期文件必须保留"""
        expired = self._make_expired(storage_root / "temp" / "sub" / "expired.tmp")
        fresh = storage_root / "temp" / "fresh.tmp"
        fresh.parent.mkdir(parents=True, exist_ok=True)
        fresh.write_bytes(b"x")  # 未过期
        business_files = [
            self._make_expired(storage_root / rel) for rel in self.BUSINESS_RELATIVE_PATHS
        ]
        # 业务目录下的空目录：同样不得被「空目录清理」删除
        empty_business_dir = storage_root / "invoices" / "2026" / "08"
        empty_business_dir.mkdir(parents=True)

        from app.tasks.file_cleanup import cleanup_temp_files

        await cleanup_temp_files()

        assert not expired.exists()  # temp/ 中的过期文件：删
        assert fresh.exists()  # temp/ 中的未过期文件：留
        assert empty_business_dir.exists(), "业务目录下的空目录被清理任务误删"
        for path in business_files:
            assert path.exists(), f"业务文件被清理任务误删：{path}"

    @pytest.mark.asyncio
    async def test_cleanup_temp_files_rejects_symlinked_temp_dir(self, storage_root, tmp_path):
        """temp/ 指向存储根之外时拒绝清理，避免误删外部文件"""
        storage_root.mkdir()
        outside = self._make_expired(tmp_path / "outside" / "expired.tmp")
        (storage_root / "temp").symlink_to(outside.parent, target_is_directory=True)

        from app.tasks.file_cleanup import cleanup_temp_files

        await cleanup_temp_files()

        assert outside.exists(), "越界软链接指向的外部文件被误删"

    @pytest.mark.asyncio
    async def test_cleanup_temp_files_without_temp_dir(self, storage_root):
        """temp/ 不存在时不遍历存储根、不抛异常"""
        business_file = self._make_expired(storage_root / self.BUSINESS_RELATIVE_PATHS[0])

        from app.tasks.file_cleanup import cleanup_temp_files

        await cleanup_temp_files()

        assert business_file.exists()


class TestWebhookCleanupTask:
    """测试 Webhook 清理任务"""

    @pytest.mark.asyncio
    async def test_cleanup_webhook_signatures(self):
        """测试清理旧的 Webhook 签名"""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        # Mock execute 返回空结果（无过期签名）
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        try:
            from app.tasks.webhook_cleanup import cleanup_webhook_signatures

            await cleanup_webhook_signatures(mock_session)

            # 验证 execute 被调用（查询过期记录）
            assert mock_session.execute.called
        except ImportError:
            pytest.skip("webhook_cleanup 模块不存在")


# ============================================================================
# 测试边缘情况
# ============================================================================


class TestSchedulerRegistration:
    """调度器任务注册契约

    注册给 APScheduler 的每个任务必须是「无参协程函数」。APScheduler 能直接
    await 协程函数；若实现用 lambda 包裹并在注册处调用 session_factory()，协程
    对象会被创建后立即丢弃（RuntimeWarning: coroutine ... was never awaited），
    任务静默不执行。本测试锁定该契约，防止回归。
    """

    @pytest.mark.asyncio
    async def test_init_scheduler_registers_only_coroutine_functions(self):
        """init_scheduler 注册的任务全部是无参协程函数"""

        import inspect
        from inspect import signature

        from app.tasks.scheduler import init_scheduler

        # 构造最小 app：before_server_start 注册回调 + ctx.async_session_maker
        app = MagicMock()
        # session_factory() 必须同步返回一个 async 上下文管理器
        # （代码使用 `async with session_factory() as session`）；
        # 且 execute/scalar_one_or_none 需返回同步结构，否则 AsyncMock 会
        # 把所有方法都变成协程导致 cfg.enabled 报错。
        fake_session = AsyncMock()
        # `async with fake_session as s` 的 s 必须是同一个（已配置 execute 的）对象
        fake_session.__aenter__.return_value = fake_session
        fake_cfg_result = MagicMock()
        fake_cfg_result.scalar_one_or_none.return_value = MagicMock(enabled=False)
        fake_session.execute.return_value = fake_cfg_result
        app.ctx.async_session_maker = MagicMock(return_value=fake_session)
        before_start_cb = {}

        def _register_cb(fn):
            before_start_cb["start"] = fn
            return fn

        app.before_server_start.side_effect = _register_cb

        # patch 掉全局调度器，避免真正启动 APScheduler / 触碰 Redis / DB
        with patch("app.tasks.scheduler.scheduler", MagicMock()) as mock_scheduler:
            mock_scheduler.get_jobs.return_value = []

            init_scheduler(app)

            assert "start" in before_start_cb, "init_scheduler 未注册 before_server_start 回调"
            await before_start_cb["start"](app, None)

            # 校验所有 add_job 的任务为无参协程函数
            calls = mock_scheduler.add_job.call_args_list
            assert calls, "调度器未注册任何任务"
            for call in calls:
                job_func = call.args[0] if call.args else None
                assert job_func is not None, f"任务注册缺少函数: {call}"
                assert inspect.iscoroutinefunction(job_func), (
                    f"任务 {getattr(job_func, '__name__', '?')} 不是协程函数"
                    "（若为 lambda 包裹的协程调用，会因从未 await 而静默不执行）"
                )
                sig = signature(job_func)
                required = [
                    p.name for p in sig.parameters.values() if p.default is inspect.Parameter.empty
                ]
                assert not required, (
                    f"任务 {getattr(job_func, '__name__', '?')} 应为无参协程"
                    f"（session 应在函数内获取），实际参数: {required}"
                )
