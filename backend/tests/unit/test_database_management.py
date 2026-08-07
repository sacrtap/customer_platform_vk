"""数据库管理路由单元测试"""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routes.database_management import clear_customer_data, clear_invoice_data


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


@pytest.fixture
def mock_invoice_scalar_results():
    """模拟清空结算单的全量 execute 调用结果

    顺序：3 次 count 查询（invoices / invoice_items / consumption_records）
    + 3 次 DELETE 语句（consumption_records / invoice_items / invoices）
    """

    def make_result(val):
        r = MagicMock()
        r.scalar = MagicMock(return_value=val)
        return r

    # 3 count results + 3 dummy DELETE results
    return [
        make_result(10),
        make_result(25),
        make_result(8),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]


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
        assert changes["before"]["customer_count"] == 5
        assert changes["after"]["customer_count"] == 0
        assert len(changes["tables_affected"]) == 12
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


# ==================== Test Clear Invoice Data ====================


class TestClearInvoiceData:
    """清空结算单数据路由测试"""

    @pytest.mark.asyncio
    async def test_clear_invoice_data_success(self, mock_request, mock_invoice_scalar_results):
        """测试成功清空结算单数据"""
        mock_request.ctx.db_session.execute = AsyncMock(side_effect=mock_invoice_scalar_results)

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ) as mock_audit:
            with patch("app.routes.database_management.logger"):
                with patch("app.cache.permissions.permission_cache") as mock_cache:
                    mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                    response = await clear_invoice_data(mock_request)

        assert response.status == 200
        body = parse_response_body(response)
        assert body["code"] == 0
        assert "成功清空结算单数据" in body["message"]
        assert body["data"]["deleted_count"] == 43  # 10 + 25 + 8
        assert body["data"]["invoices_deleted"] == 10
        assert body["data"]["invoice_items_deleted"] == 25
        assert body["data"]["consumption_records_linked_deleted"] == 8

        # 验证审计日志被调用
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args[1]
        assert call_kwargs["user_id"] == 1
        assert call_kwargs["action"] == "database_clear_invoices"
        assert call_kwargs["module"] == "system"
        assert call_kwargs["auto_commit"] is False
        assert call_kwargs["operation_type"] == "sensitive"

    @pytest.mark.asyncio
    async def test_clear_invoice_data_zero_data(self, mock_request):
        """测试没有结算单数据时清空"""

        def make_zero_result():
            r = MagicMock()
            r.scalar = MagicMock(return_value=0)
            return r

        mock_request.ctx.db_session.execute = AsyncMock(
            side_effect=[make_zero_result(), make_zero_result(), make_zero_result()]
        )

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ) as mock_audit:
            with patch("app.cache.permissions.permission_cache") as mock_cache:
                mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                response = await clear_invoice_data(mock_request)

        assert response.status == 200
        body = parse_response_body(response)
        assert body["code"] == 0
        assert body["message"] == "无结算单数据可清空"
        assert body["data"]["deleted_count"] == 0

        # 无数据时不应调用审计日志
        mock_audit.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_invoice_data_rollback_on_error(self, mock_request):
        """测试异常时事务回滚

        3 次 count 查询成功（返回非零），第 4 次 execute (DELETE) 抛异常触发回滚。
        """

        def make_result(val):
            r = MagicMock()
            r.scalar = MagicMock(return_value=val)
            return r

        # 3 count results + Exception on first DELETE
        mock_request.ctx.db_session.execute = AsyncMock(
            side_effect=[
                make_result(10),
                make_result(25),
                make_result(8),
                Exception("DB error"),
            ]
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
                    response = await clear_invoice_data(mock_request)

        assert response.status == 500
        body = parse_response_body(response)
        assert "结算单数据清空失败" in body["message"]
        assert body["code"] == 500

        # 验证调用了 rollback
        mock_request.ctx.db_session.rollback.assert_called_once()
        # 验证异常被记录
        mock_logger.exception.assert_called_once_with("结算单数据清空失败")

    @pytest.mark.asyncio
    async def test_clear_invoice_data_commit_called_on_success(
        self, mock_request, mock_invoice_scalar_results
    ):
        """测试成功时调用 commit"""
        mock_request.ctx.db_session.execute = AsyncMock(side_effect=mock_invoice_scalar_results)

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ):
            with patch("app.routes.database_management.logger"):
                with patch("app.cache.permissions.permission_cache") as mock_cache:
                    mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                    await clear_invoice_data(mock_request)

        mock_request.ctx.db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_invoice_data_audit_changes_payload(
        self, mock_request, mock_invoice_scalar_results
    ):
        """测试审计日志的 changes 参数包含正确的删除信息"""
        mock_request.ctx.db_session.execute = AsyncMock(side_effect=mock_invoice_scalar_results)

        with patch(
            "app.routes.database_management.create_audit_entry",
            new_callable=AsyncMock,
        ) as mock_audit:
            with patch("app.routes.database_management.logger"):
                with patch("app.cache.permissions.permission_cache") as mock_cache:
                    mock_cache.get_permissions = AsyncMock(return_value={"system:database_clear"})
                    await clear_invoice_data(mock_request)

        call_kwargs = mock_audit.call_args[1]
        changes = call_kwargs["changes"]
        assert changes["before"]["invoices_count"] == 10
        assert changes["before"]["invoice_items_count"] == 25
        assert changes["before"]["consumption_records_linked_count"] == 8
        assert changes["after"]["invoices_count"] == 0
        assert changes["after"]["invoice_items_count"] == 0
        assert changes["after"]["consumption_records_linked_count"] == 0
        assert len(changes["tables_affected"]) == 3
        assert "invoices" in changes["tables_affected"]
        assert "invoice_items" in changes["tables_affected"]

    @pytest.mark.asyncio
    async def test_clear_invoice_data_unauthenticated(self):
        """测试未认证时返回 401"""
        request = MagicMock()
        request.ctx = MagicMock()
        request.ctx.user = None

        response = await clear_invoice_data(request)
        assert response.status == 401
        body = parse_response_body(response)
        assert body["code"] == 40101
        assert "未认证" in body["message"]

    @pytest.mark.asyncio
    async def test_clear_invoice_data_unauthorized(self):
        """测试无权限时返回 403"""
        request = MagicMock()
        request.ctx = MagicMock()
        request.ctx.user = {"user_id": 1}
        request.ctx.db_session = AsyncMock()

        with patch("app.cache.permissions.permission_cache") as mock_cache:
            mock_cache.get_permissions = AsyncMock(return_value=set())
            response = await clear_invoice_data(request)

        assert response.status == 403
        body = parse_response_body(response)
        assert body["code"] == 40301
        assert "权限不足" in body["message"]
