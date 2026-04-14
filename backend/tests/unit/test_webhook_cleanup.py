"""
Webhook Cleanup Tasks 单元测试
测试覆盖率目标：80%+
"""

import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch


class TestCleanupWebhookSignatures:
    """测试 Webhook 签名清理任务"""

    @pytest.fixture
    def mock_session(self):
        """创建模拟数据库会话"""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def mock_datetime(self):
        """固定当前时间用于测试"""
        fixed_now = datetime(2024, 1, 15, 12, 0, 0)
        with patch("app.tasks.webhook_cleanup.datetime") as mock_dt:
            mock_dt.utcnow.return_value = fixed_now
            yield fixed_now

    @pytest.mark.asyncio
    async def test_cleanup_no_expired_signatures(self, mock_session, mock_datetime):
        """测试无过期签名记录"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await cleanup_webhook_signatures(mock_session)

        assert mock_session.execute.call_count == 1
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_with_expired_signatures(self, mock_session, mock_datetime):
        """测试有过期签名记录需要清理"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures

        expired_sig1 = MagicMock()
        expired_sig1.signature = "sig_expired_1"
        expired_sig1.timestamp = datetime(2024, 1, 5, 10, 0, 0)

        expired_sig2 = MagicMock()
        expired_sig2.signature = "sig_expired_2"
        expired_sig2.timestamp = datetime(2024, 1, 8, 10, 0, 0)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [expired_sig1, expired_sig2]
        mock_session.execute = AsyncMock(return_value=mock_result)

        await cleanup_webhook_signatures(mock_session)

        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_with_valid_signatures_only(self, mock_session, mock_datetime):
        """测试只有有效签名记录（无需清理）"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures

        valid_sig = MagicMock()
        valid_sig.signature = "sig_valid_1"
        valid_sig.timestamp = datetime(2024, 1, 14, 10, 0, 0)
        valid_sig.deleted_at = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await cleanup_webhook_signatures(mock_session)

        assert mock_session.execute.call_count == 1
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_with_mixed_signatures(self, mock_session, mock_datetime):
        """测试混合过期和有效签名记录"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures

        expired_sig = MagicMock()
        expired_sig.signature = "sig_expired"
        expired_sig.timestamp = datetime(2024, 1, 5, 10, 0, 0)

        valid_sig = MagicMock()
        valid_sig.signature = "sig_valid"
        valid_sig.timestamp = datetime(2024, 1, 14, 10, 0, 0)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [expired_sig]
        mock_session.execute = AsyncMock(return_value=mock_result)

        await cleanup_webhook_signatures(mock_session)

        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_task_failure(self, mock_session, mock_datetime):
        """测试任务整体失败"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures

        mock_session.execute = AsyncMock(side_effect=Exception("数据库连接失败"))

        with pytest.raises(Exception, match="数据库连接失败"):
            await cleanup_webhook_signatures(mock_session)

        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_with_deleted_at_not_none(self, mock_session, mock_datetime):
        """测试已软删除的签名记录不会被清理"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures

        deleted_sig = MagicMock()
        deleted_sig.signature = "sig_deleted"
        deleted_sig.timestamp = datetime(2024, 1, 5, 10, 0, 0)
        deleted_sig.deleted_at = datetime(2024, 1, 6, 10, 0, 0)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await cleanup_webhook_signatures(mock_session)

        assert mock_session.execute.call_count == 1
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_with_boundary_timestamp(self, mock_session):
        """测试边界时间戳（正好 5 天）"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures

        fixed_now = datetime(2024, 1, 15, 12, 0, 0)
        cutoff_time = fixed_now - timedelta(days=5)

        with patch("app.tasks.webhook_cleanup.datetime") as mock_dt:
            mock_dt.utcnow.return_value = fixed_now

            expired_sig = MagicMock()
            expired_sig.timestamp = cutoff_time - timedelta(seconds=1)
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [expired_sig]
            mock_session.execute = AsyncMock(return_value=mock_result)

            await cleanup_webhook_signatures(mock_session)

            assert mock_session.execute.call_count == 2
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_retention_period_constant(self, mock_session):
        """测试签名保留天数常量"""
        from app.tasks.webhook_cleanup import SIGNATURE_RETENTION_DAYS

        assert SIGNATURE_RETENTION_DAYS == 5

    @pytest.mark.asyncio
    async def test_cleanup_delete_query_parameters(self, mock_session, mock_datetime, caplog):
        """测试删除查询参数正确性"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures
        from sqlalchemy.sql.dml import Delete

        expired_sig = MagicMock()
        expired_sig.signature = "sig_expired"
        expired_sig.timestamp = datetime(2024, 1, 5, 10, 0, 0)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [expired_sig]
        mock_session.execute = AsyncMock(return_value=mock_result)

        await cleanup_webhook_signatures(mock_session)

        assert mock_session.execute.call_count == 2

        delete_call = mock_session.execute.call_args_list[1]
        delete_stmt = delete_call[0][0]

        assert isinstance(delete_stmt, Delete)

    @pytest.mark.asyncio
    async def test_cleanup_logs_info_message(self, mock_session, mock_datetime, caplog):
        """测试日志记录信息"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures
        import logging

        expired_sig = MagicMock()
        expired_sig.signature = "sig_expired"
        expired_sig.timestamp = datetime(2024, 1, 5, 10, 0, 0)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [expired_sig]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with caplog.at_level(logging.INFO):
            await cleanup_webhook_signatures(mock_session)

        assert any("Webhook 签名清理完成" in record.message for record in caplog.records)
        assert any("删除记录数：1" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_cleanup_logs_debug_when_no_records(self, mock_session, mock_datetime, caplog):
        """测试无记录时的调试日志"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures
        import logging

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with caplog.at_level(logging.DEBUG):
            await cleanup_webhook_signatures(mock_session)

        assert any("Webhook 签名清理：无过期记录" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_cleanup_error_logging(self, mock_session, mock_datetime, caplog):
        """测试错误日志记录"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures

        mock_session.execute = AsyncMock(side_effect=Exception("数据库错误"))

        with pytest.raises(Exception):
            await cleanup_webhook_signatures(mock_session)

        assert any("Webhook 签名清理失败" in record.message for record in caplog.records)
        assert any("数据库错误" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_cleanup_with_multiple_expired_signatures(self, mock_session, mock_datetime):
        """测试清理多个过期签名"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures

        expired_signatures = []
        for i in range(5):
            sig = MagicMock()
            sig.signature = f"sig_expired_{i}"
            sig.timestamp = datetime(2024, 1, 5, 10, 0, 0) - timedelta(days=i)
            expired_signatures.append(sig)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = expired_signatures
        mock_session.execute = AsyncMock(return_value=mock_result)

        await cleanup_webhook_signatures(mock_session)

        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_session_state_after_success(self, mock_session, mock_datetime):
        """测试成功清理后会话状态"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures

        expired_sig = MagicMock()
        expired_sig.signature = "sig_expired"
        expired_sig.timestamp = datetime(2024, 1, 5, 10, 0, 0)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [expired_sig]
        mock_session.execute = AsyncMock(return_value=mock_result)

        await cleanup_webhook_signatures(mock_session)

        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_with_commit_failure(self, mock_session, mock_datetime):
        """测试提交失败场景"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures

        expired_sig = MagicMock()
        expired_sig.signature = "sig_expired"
        expired_sig.timestamp = datetime(2024, 1, 5, 10, 0, 0)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [expired_sig]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock(side_effect=Exception("提交失败"))

        with pytest.raises(Exception, match="提交失败"):
            await cleanup_webhook_signatures(mock_session)

        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_query_uses_correct_model(self, mock_session, mock_datetime, caplog):
        """测试查询使用正确的模型"""
        from app.tasks.webhook_cleanup import cleanup_webhook_signatures
        from app.models.webhooks import WebhookSignature

        expired_sig = MagicMock()
        expired_sig.signature = "sig_expired"
        expired_sig.timestamp = datetime(2024, 1, 5, 10, 0, 0)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [expired_sig]
        mock_session.execute = AsyncMock(return_value=mock_result)

        await cleanup_webhook_signatures(mock_session)

        select_call = mock_session.execute.call_args_list[0]
        select_stmt = select_call[0][0]

        assert "webhook_signatures" in str(select_stmt).lower()
