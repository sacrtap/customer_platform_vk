"""Email Tasks 单元测试 - 逾期提醒邮件任务"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, date
from decimal import Decimal

from app.tasks.email_tasks import send_overdue_emails, _log_email_task
from app.models.billing import SyncTaskLog


# ==================== Fixtures ====================


@pytest.fixture
def mock_models():
    """Mock 模型和查询函数"""
    with patch("app.tasks.email_tasks.Invoice") as MockInvoice:
        with patch("app.tasks.email_tasks.InvoiceStatus") as MockInvoiceStatus:
            with patch("app.tasks.email_tasks.select") as mock_select:
                with patch("app.tasks.email_tasks.selectinload") as mock_selectinload:
                    # Mock InvoiceStatus.OVERDUE
                    MockInvoiceStatus.OVERDUE = "overdue"

                    # Mock selectinload 返回 MagicMock
                    mock_selectinload.return_value = MagicMock()

                    # Mock select 返回可链式调用的对象
                    mock_query = MagicMock()
                    mock_query.options.return_value = mock_query
                    mock_query.where.return_value = mock_query
                    mock_select.return_value = mock_query

                    yield {
                        "Invoice": MockInvoice,
                        "InvoiceStatus": MockInvoiceStatus,
                        "select": mock_select,
                        "selectinload": mock_selectinload,
                    }


@pytest.fixture
def mock_email_service():
    """Mock 邮件服务"""
    with patch("app.services.email.get_email_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.render_template = MagicMock(return_value="<html>test</html>")
        mock_service.send_email = AsyncMock(return_value=True)
        mock_get_service.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_invoice():
    """创建 Mock Invoice 对象"""
    invoice = MagicMock()
    invoice.id = 1
    invoice.invoice_no = "INV-2026-001"
    invoice.total_amount = Decimal("1000.00")
    invoice.status = "overdue"
    invoice.period_start = date(2026, 3, 1)
    invoice.period_end = date(2026, 3, 31)
    invoice.deleted_at = None

    # Mock customer
    invoice.customer = MagicMock()
    invoice.customer.name = "测试客户"

    # Mock created_by_user
    invoice.created_by_user = MagicMock()
    invoice.created_by_user.name = "张三"
    invoice.created_by_user.email = "sales@example.com"

    return invoice


@pytest.fixture
def mock_session():
    """Mock 数据库 Session"""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    return session


# ==================== Test Send Overdue Emails ====================


class TestSendOverdueEmails:
    """发送逾期提醒邮件测试"""

    @pytest.mark.asyncio
    async def test_no_overdue_invoices(
        self, mock_session, mock_email_service, mock_models
    ):
        """测试无逾期账单情况"""
        # Mock 查询结果为空
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        # 执行函数
        await send_overdue_emails(mock_session)

        # 验证查询被执行
        mock_session.execute.assert_called_once()
        # 验证没有发送邮件
        mock_email_service.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_overdue_email_success(
        self, mock_session, mock_invoice, mock_email_service, mock_models
    ):
        """测试成功发送逾期提醒邮件"""
        # Mock 查询返回逾期账单
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_invoice]
        mock_session.execute.return_value = mock_result

        # 执行函数
        await send_overdue_emails(mock_session)

        # 验证邮件服务被调用
        mock_email_service.render_template.assert_called_once()
        mock_email_service.send_email.assert_called_once()

        # 验证邮件内容
        call_args = mock_email_service.send_email.call_args
        assert call_args[1]["to_emails"] == ["sales@example.com"]
        assert "逾期提醒" in call_args[1]["subject"]

        # 验证日志记录
        mock_session.add.assert_called()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_multiple_invoices_same_sales(
        self, mock_session, mock_email_service, mock_models
    ):
        """测试同一商务的多个逾期账单"""
        # 创建两个属于同一商务的逾期账单
        invoice1 = MagicMock()
        invoice1.id = 1
        invoice1.created_by_user = MagicMock()
        invoice1.created_by_user.email = "sales@example.com"
        invoice1.created_by_user.name = "张三"

        invoice2 = MagicMock()
        invoice2.id = 2
        invoice2.created_by_user = MagicMock()
        invoice2.created_by_user.email = "sales@example.com"
        invoice2.created_by_user.name = "张三"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [invoice1, invoice2]
        mock_session.execute.return_value = mock_result

        await send_overdue_emails(mock_session)

        # 验证只发送了一封邮件（按商务分组）
        assert mock_email_service.send_email.call_count == 1

        # 验证主题中包含账单数量
        call_args = mock_email_service.send_email.call_args
        assert "2 笔" in call_args[1]["subject"]

    @pytest.mark.asyncio
    async def test_invoice_without_creator(
        self, mock_session, mock_email_service, mock_models
    ):
        """测试没有创建人的逾期账单"""
        invoice = MagicMock()
        invoice.id = 1
        invoice.created_by_user = None  # 没有创建人

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [invoice]
        mock_session.execute.return_value = mock_result

        await send_overdue_emails(mock_session)

        # 验证没有发送邮件（因为无法确定收件人）
        mock_email_service.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_invoice_creator_without_email(
        self, mock_session, mock_email_service, mock_models
    ):
        """测试创建人没有邮箱的情况"""
        invoice = MagicMock()
        invoice.id = 1
        invoice.created_by_user = MagicMock()
        invoice.created_by_user.email = None  # 没有邮箱

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [invoice]
        mock_session.execute.return_value = mock_result

        await send_overdue_emails(mock_session)

        # 验证没有发送邮件
        mock_email_service.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_email_failure(
        self, mock_session, mock_invoice, mock_email_service, mock_models
    ):
        """测试邮件发送失败"""
        # Mock 查询返回逾期账单
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_invoice]
        mock_session.execute.return_value = mock_result

        # Mock 邮件发送失败
        mock_email_service.send_email.return_value = False

        await send_overdue_emails(mock_session)

        # 验证邮件被尝试发送
        mock_email_service.send_email.assert_called_once()

        # 验证记录了失败
        mock_session.add.assert_called()
        log_entry = mock_session.add.call_args[0][0]
        assert log_entry.status == "partial"
        assert log_entry.failed_count == 1

    @pytest.mark.asyncio
    async def test_send_email_exception(
        self, mock_session, mock_invoice, mock_email_service, mock_models
    ):
        """测试邮件发送异常"""
        # Mock 查询返回逾期账单
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_invoice]
        mock_session.execute.return_value = mock_result

        # Mock 邮件发送抛出异常
        mock_email_service.send_email.side_effect = Exception("SMTP 连接失败")

        await send_overdue_emails(mock_session)

        # 验证记录了失败
        mock_session.add.assert_called()
        log_entry = mock_session.add.call_args[0][0]
        assert log_entry.status == "partial"

    @pytest.mark.asyncio
    async def test_main_task_exception(
        self, mock_session, mock_email_service, mock_models
    ):
        """测试主任务执行异常"""
        # Mock 查询抛出异常
        mock_session.execute.side_effect = Exception("数据库连接失败")

        # 执行应该抛出异常
        with pytest.raises(Exception):
            await send_overdue_emails(mock_session)

        # 验证执行了回滚
        mock_session.rollback.assert_called_once()

        # 验证记录了错误日志
        mock_session.add.assert_called()
        log_entry = mock_session.add.call_args[0][0]
        assert log_entry.status == "failed"
        assert log_entry.error_message is not None

    @pytest.mark.asyncio
    async def test_multiple_sales_emails(
        self, mock_session, mock_email_service, mock_models
    ):
        """测试向多个商务发送邮件"""
        # 创建属于不同商务的逾期账单
        invoice1 = MagicMock()
        invoice1.id = 1
        invoice1.created_by_user = MagicMock()
        invoice1.created_by_user.email = "sales1@example.com"
        invoice1.created_by_user.name = "张三"

        invoice2 = MagicMock()
        invoice2.id = 2
        invoice2.created_by_user = MagicMock()
        invoice2.created_by_user.email = "sales2@example.com"
        invoice2.created_by_user.name = "李四"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [invoice1, invoice2]
        mock_session.execute.return_value = mock_result

        await send_overdue_emails(mock_session)

        # 验证发送了两封邮件
        assert mock_email_service.send_email.call_count == 2

    @pytest.mark.asyncio
    async def test_deleted_invoices_excluded(
        self, mock_session, mock_email_service, mock_models
    ):
        """测试已删除的账单被排除"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await send_overdue_emails(mock_session)

        # 验证查询被调用
        mock_session.execute.assert_called_once()


# ==================== Test Log Email Task ====================


class TestLogEmailTask:
    """记录邮件任务日志测试"""

    @pytest.mark.asyncio
    async def test_log_success_status(self, mock_session):
        """测试记录成功状态的日志"""
        executed_at = datetime(2026, 4, 7, 9, 0, 0)

        await _log_email_task(
            session=mock_session,
            task_name="send_overdue_emails",
            status="success",
            total_count=10,
            sent_count=10,
            failed_count=0,
            executed_at=executed_at,
        )

        # 验证创建了日志条目
        mock_session.add.assert_called_once()
        log_entry = mock_session.add.call_args[0][0]

        assert isinstance(log_entry, SyncTaskLog)
        assert log_entry.task_name == "send_overdue_emails"
        assert log_entry.status == "success"
        assert log_entry.total_count == 10
        assert log_entry.success_count == 10
        assert log_entry.failed_count == 0
        assert log_entry.executed_at == "2026-04-07 09:00:00"

        # 验证提交
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_partial_status(self, mock_session):
        """测试记录部分成功状态的日志"""
        executed_at = datetime(2026, 4, 7, 9, 0, 0)

        await _log_email_task(
            session=mock_session,
            task_name="send_welcome_emails",
            status="partial",
            total_count=10,
            sent_count=8,
            failed_count=2,
            executed_at=executed_at,
        )

        log_entry = mock_session.add.call_args[0][0]
        assert log_entry.status == "partial"
        assert log_entry.total_count == 10
        assert log_entry.success_count == 8
        assert log_entry.failed_count == 2

    @pytest.mark.asyncio
    async def test_log_failed_status(self, mock_session):
        """测试记录失败状态的日志"""
        executed_at = datetime(2026, 4, 7, 9, 0, 0)
        error_msg = "SMTP 连接超时"

        await _log_email_task(
            session=mock_session,
            task_name="send_invoice_emails",
            status="failed",
            total_count=0,
            sent_count=0,
            failed_count=0,
            executed_at=executed_at,
            error_message=error_msg,
        )

        log_entry = mock_session.add.call_args[0][0]
        assert log_entry.status == "failed"
        assert log_entry.error_message == error_msg

    @pytest.mark.asyncio
    async def test_log_with_none_error_message(self, mock_session):
        """测试错误消息为 None 的情况"""
        executed_at = datetime(2026, 4, 7, 9, 0, 0)

        await _log_email_task(
            session=mock_session,
            task_name="send_overdue_emails",
            status="success",
            total_count=5,
            sent_count=5,
            failed_count=0,
            executed_at=executed_at,
            error_message=None,
        )

        log_entry = mock_session.add.call_args[0][0]
        assert log_entry.error_message is None

    @pytest.mark.asyncio
    async def test_log_session_commit_exception(self, mock_session):
        """测试日志提交异常的情况"""
        mock_session.commit.side_effect = Exception("数据库写入失败")

        executed_at = datetime(2026, 4, 7, 9, 0, 0)

        # 应该抛出异常
        with pytest.raises(Exception):
            await _log_email_task(
                session=mock_session,
                task_name="send_overdue_emails",
                status="success",
                total_count=5,
                sent_count=5,
                failed_count=0,
                executed_at=executed_at,
            )


# ==================== Integration Tests ====================


class TestEmailTasksIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow_success(
        self, mock_session, mock_invoice, mock_email_service, mock_models
    ):
        """测试完整工作流程 - 成功场景"""
        # 设置查询结果
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_invoice]
        mock_session.execute.return_value = mock_result

        # 执行任务
        await send_overdue_emails(mock_session)

        # 验证整个流程
        # 1. 查询逾期账单
        mock_session.execute.assert_called()

        # 2. 渲染模板
        mock_email_service.render_template.assert_called_once_with(
            "overdue_invoice_reminder.html",
            user_name="张三",
            invoices=[mock_invoice],
            today=date.today(),
        )

        # 3. 发送邮件
        mock_email_service.send_email.assert_called_once()

        # 4. 记录日志
        assert mock_session.add.call_count >= 1
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_full_workflow_with_failures(
        self, mock_session, mock_email_service, mock_models
    ):
        """测试完整工作流程 - 包含失败"""
        # 创建两个账单
        invoice1 = MagicMock()
        invoice1.id = 1
        invoice1.created_by_user = MagicMock()
        invoice1.created_by_user.email = "sales1@example.com"
        invoice1.created_by_user.name = "张三"

        invoice2 = MagicMock()
        invoice2.id = 2
        invoice2.created_by_user = MagicMock()
        invoice2.created_by_user.email = "sales2@example.com"
        invoice2.created_by_user.name = "李四"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [invoice1, invoice2]
        mock_session.execute.return_value = mock_result

        # 第一个成功，第二个失败
        mock_email_service.send_email.side_effect = [True, False]

        await send_overdue_emails(mock_session)

        # 验证发送了两封邮件
        assert mock_email_service.send_email.call_count == 2

        # 验证日志记录为部分成功
        log_entry = mock_session.add.call_args[0][0]
        assert log_entry.status == "partial"
        assert log_entry.success_count == 1
        assert log_entry.failed_count == 1
