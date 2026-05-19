"""数据库管理路由单元测试"""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routes.database_management import clear_customer_data


def parse_response_body(response):
    """解析 Sanic JSON 响应体为 dict"""
    body = response.body
    if isinstance(body, bytes):
        return json.loads(body)
    return body


# ==================== Fixtures ====================


@pytest.fixture
def mock_request():
    """模拟请求上下文"""
    request = MagicMock()
    request.ctx = MagicMock()
    request.ctx.db_session = AsyncMock()
    request.ctx.db_session.execute = AsyncMock()
    request.ctx.db_session.commit = AsyncMock()
    request.ctx.db_session.rollback = AsyncMock()
    request.ctx.user = {"user_id": 1}
    request.headers = {}
    request.ip = "127.0.0.1"
    return request


@pytest.fixture
def mock_scalar_result():
    """模拟 count 查询结果"""
    result = MagicMock()
    result.scalar = MagicMock(return_value=5)
    return result


# ==================== Test Clear Customer Data ====================


class TestClearCustomerData:
    """清空客户数据路由测试"""

    @pytest.mark.asyncio
    async def test_clear_customer_data_success(self, mock_request, mock_scalar_result):
        """测试成功清空客户数据"""
        mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_scalar_result)

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ) as mock_audit:
            with patch("app.routes.database_management.logger"):
                with patch("app.cache.permissions.permission_cache") as mock_cache:
                    mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                    response = await clear_customer_data(mock_request)

        assert response.status == 200
        body = parse_response_body(response)
        assert body["code"] == 0
        assert "成功清空 5 条客户数据" in body["message"]
        assert body["data"]["deleted_count"] == 5

        # 验证审计日志被调用
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args[1]
        assert call_kwargs["user_id"] == 1
        assert call_kwargs["action"] == "database_clear"
        assert call_kwargs["module"] == "system"
        assert call_kwargs["auto_commit"] is False
        assert call_kwargs["operation_type"] == "sensitive"

    @pytest.mark.asyncio
    async def test_clear_customer_data_rollback_on_error(self, mock_request, mock_scalar_result):
        """测试异常时事务回滚

        count 查询成功（返回非零），DELETE 阶段抛出异常触发回滚。
        """
        # 第一次 execute (count) 成功，后续 execute (DELETE) 抛异常
        mock_request.ctx.db_session.execute = AsyncMock(
            side_effect=[mock_scalar_result, Exception("DB error")]
        )

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ):
            with patch(
                "app.routes.database_management.logger",
                spec=logging.Logger,
            ) as mock_logger:
                with patch("app.cache.permissions.permission_cache") as mock_cache:
                    mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                    response = await clear_customer_data(mock_request)

        assert response.status == 500
        body = parse_response_body(response)
        assert "数据清空失败" in body["message"]
        assert body["code"] == 500

        # 验证调用了 rollback
        mock_request.ctx.db_session.rollback.assert_called_once()
        # 验证异常被记录
        mock_logger.exception.assert_called_once_with("数据库清空失败")

    @pytest.mark.asyncio
    async def test_clear_customer_data_zero_customers(self, mock_request, mock_scalar_result):
        """测试没有客户数据时清空"""
        mock_scalar_result.scalar = MagicMock(return_value=0)
        mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_scalar_result)

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ) as mock_audit:
            with patch("app.cache.permissions.permission_cache") as mock_cache:
                mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                response = await clear_customer_data(mock_request)

        assert response.status == 200
        body = parse_response_body(response)
        assert body["code"] == 0
        assert body["message"] == "无数据可清空"
        assert body["data"]["deleted_count"] == 0

        # 无数据时不应调用审计日志
        mock_audit.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_customer_data_uses_x_real_ip(self, mock_request, mock_scalar_result):
        """测试使用 x-real-ip 头记录 IP"""
        mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_scalar_result)
        mock_request.headers = {"x-real-ip": "10.0.0.1"}

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ) as mock_audit:
            with patch("app.routes.database_management.logger"):
                with patch("app.cache.permissions.permission_cache") as mock_cache:
                    mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                    await clear_customer_data(mock_request)

        call_kwargs = mock_audit.call_args[1]
        assert call_kwargs["ip_address"] == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_clear_customer_data_fallback_to_x_forwarded_for(
        self, mock_request, mock_scalar_result
    ):
        """测试 x-real-ip 不存在时回退到 x-forwarded-for"""
        mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_scalar_result)
        mock_request.headers = {"x-forwarded-for": "192.168.1.1"}

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ) as mock_audit:
            with patch("app.routes.database_management.logger"):
                with patch("app.cache.permissions.permission_cache") as mock_cache:
                    mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                    await clear_customer_data(mock_request)

        call_kwargs = mock_audit.call_args[1]
        assert call_kwargs["ip_address"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_clear_customer_data_fallback_to_request_ip(
        self, mock_request, mock_scalar_result
    ):
        """测试两个 IP 头都不存在时使用 request.ip"""
        mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_scalar_result)
        mock_request.headers = {}
        mock_request.ip = "127.0.0.1"

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ) as mock_audit:
            with patch("app.routes.database_management.logger"):
                with patch("app.cache.permissions.permission_cache") as mock_cache:
                    mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                    await clear_customer_data(mock_request)

        call_kwargs = mock_audit.call_args[1]
        assert call_kwargs["ip_address"] == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_clear_customer_data_commit_called_on_success(
        self, mock_request, mock_scalar_result
    ):
        """测试成功时调用 commit"""
        mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_scalar_result)

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ):
            with patch("app.routes.database_management.logger"):
                with patch("app.cache.permissions.permission_cache") as mock_cache:
                    mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                    await clear_customer_data(mock_request)

        mock_request.ctx.db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_customer_data_rollback_not_called_on_success(
        self, mock_request, mock_scalar_result
    ):
        """测试成功时不调用 rollback"""
        mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_scalar_result)

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ):
            with patch("app.routes.database_management.logger"):
                with patch("app.cache.permissions.permission_cache") as mock_cache:
                    mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                    await clear_customer_data(mock_request)

        mock_request.ctx.db_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_customer_data_commit_not_called_on_error(
        self, mock_request, mock_scalar_result
    ):
        """测试失败时不调用 commit

        count 查询成功，DELETE 阶段抛异常，commit 不应被调用。
        """
        mock_request.ctx.db_session.execute = AsyncMock(
            side_effect=[mock_scalar_result, Exception("DB error")]
        )

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ):
            with patch(
                "app.routes.database_management.logger",
                spec=logging.Logger,
            ):
                with patch("app.cache.permissions.permission_cache") as mock_cache:
                    mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                    await clear_customer_data(mock_request)

        mock_request.ctx.db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_customer_data_audit_changes_payload(
        self, mock_request, mock_scalar_result
    ):
        """测试审计日志的 changes 参数包含正确的删除信息"""
        mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_scalar_result)

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ) as mock_audit:
            with patch("app.routes.database_management.logger"):
                with patch("app.cache.permissions.permission_cache") as mock_cache:
                    mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                    await clear_customer_data(mock_request)

        call_kwargs = mock_audit.call_args[1]
        changes = call_kwargs["changes"]
        assert changes["deleted_count"] == 5
        assert len(changes["tables_affected"]) == 11
        assert "customers" in changes["tables_affected"]
        assert "customer_profiles" in changes["tables_affected"]
        assert "invoices" in changes["tables_affected"]

    @pytest.mark.asyncio
    async def test_clear_customer_data_unauthenticated(self):
        """测试未认证时返回 401"""
        request = MagicMock()
        request.ctx = MagicMock()
        request.ctx.user = None  # No user

        response = await clear_customer_data(request)
        assert response.status == 401
        body = parse_response_body(response)
        assert body["code"] == 40101
        assert "未认证" in body["message"]

    @pytest.mark.asyncio
    async def test_clear_customer_data_unauthorized(self):
        """测试无权限时返回 403"""
        request = MagicMock()
        request.ctx = MagicMock()
        request.ctx.user = {"user_id": 1}
        request.ctx.db_session = AsyncMock()

        with patch("app.cache.permissions.permission_cache") as mock_cache:
            mock_cache.get_permissions = AsyncMock(return_value=set())
            response = await clear_customer_data(request)

        assert response.status == 403
        body = parse_response_body(response)
        assert body["code"] == 40301
        assert "权限不足" in body["message"]
