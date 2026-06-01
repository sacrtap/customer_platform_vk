"""CustomerService.batch_update_customers 单元测试

测试覆盖 8 个场景：
1. 全部成功（正常批量更新 3 个客户）
2. 无效字段（fields 含非白名单字段 → ValueError）
3. 空 IDs → ValueError
4. 空 fields → ValueError
5. 客户不存在 → 记录到 failed_list
6. 字段值错误（email 格式错误）→ 部分失败
7. 审计日志验证（成功调用 create_audit_entry）
8. 缓存清理验证（成功调用 invalidate_customer_cache(None)）
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.customers import Customer
from app.services.customers import CustomerService

# ==================== Fixtures ====================


@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.new = set()
    return session


@pytest.fixture
def customer_service(mock_db_session):
    """创建 CustomerService 实例"""
    return CustomerService(db_session=mock_db_session)


def make_mock_execute_result(customer=None, scalar_value=None):
    """创建 execute 返回结果"""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=customer)
    if scalar_value is not None:
        result.scalar_one_or_none.return_value = scalar_value
    return result


# ==================== Test Batch Update ====================


class TestCustomerService_BatchUpdateCustomers:
    """批量更新客户测试"""

    @pytest.mark.asyncio
    async def test_batch_update_all_success(self, customer_service, mock_db_session):
        """测试批量更新全部成功（正常更新 3 个客户）"""
        # 准备 3 个客户
        customers = [
            Customer(
                id=1,
                company_id=1001,
                name="客户 A",
                account_type="enterprise",
                email="a@example.com",
            ),
            Customer(
                id=2,
                company_id=1002,
                name="客户 B",
                account_type="enterprise",
                email="b@example.com",
            ),
            Customer(
                id=3,
                company_id=1003,
                name="客户 C",
                account_type="enterprise",
                email="c@example.com",
            ),
        ]

        # 第一次调用 get_customer_by_id 返回 customer[0]，第二次返回 customer[1]，...
        call_count = {"count": 0}

        def execute_side_effect(*args, **kwargs):
            idx = call_count["count"]
            call_count["count"] += 1
            if idx < 3:
                return make_mock_execute_result(customers[idx])
            # industry_type_id 查询、company_id 唯一性查询返回空
            return make_mock_execute_result(None)

        mock_db_session.execute.side_effect = execute_side_effect

        fields = {"name": "更新后的名称", "email": "new@example.com"}
        current_user = {"user_id": 1}

        with patch.object(
            customer_service, "get_customer_profile", new_callable=AsyncMock
        ) as mock_profile:
            mock_profile.return_value = None

            result = await customer_service.batch_update_customers(
                customer_ids=[1, 2, 3],
                fields=fields,
                current_user=current_user,
            )

        # 验证返回值
        assert result["total"] == 3
        assert result["success_count"] == 3
        assert result["failed_count"] == 0
        assert result["failed_list"] == []

        # 验证 commit 被调用 3 次
        assert mock_db_session.commit.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_update_invalid_fields(self, customer_service, mock_db_session):
        """测试包含非白名单字段时抛出 ValueError"""
        fields = {"name": "新名称", "non_existent_field": "value"}
        current_user = {"user_id": 1}

        with pytest.raises(ValueError, match="包含不在白名单内的字段"):
            await customer_service.batch_update_customers(
                customer_ids=[1],
                fields=fields,
                current_user=current_user,
            )

    @pytest.mark.asyncio
    async def test_batch_update_empty_ids(self, customer_service, mock_db_session):
        """测试空 IDs 抛出 ValueError"""
        fields = {"name": "新名称"}
        current_user = {"user_id": 1}

        with pytest.raises(ValueError, match="customer_ids 不能为空"):
            await customer_service.batch_update_customers(
                customer_ids=[],
                fields=fields,
                current_user=current_user,
            )

    @pytest.mark.asyncio
    async def test_batch_update_empty_fields(self, customer_service, mock_db_session):
        """测试空 fields 抛出 ValueError"""
        current_user = {"user_id": 1}

        with pytest.raises(ValueError, match="fields 不能为空"):
            await customer_service.batch_update_customers(
                customer_ids=[1],
                fields={},
                current_user=current_user,
            )

    @pytest.mark.asyncio
    async def test_batch_update_customer_not_found(self, customer_service, mock_db_session):
        """测试客户不存在时记录到 failed_list"""
        # get_customer_by_id 返回 None
        mock_db_session.execute.return_value = make_mock_execute_result(None)

        fields = {"name": "新名称"}
        current_user = {"user_id": 1}

        with patch.object(
            customer_service, "get_customer_profile", new_callable=AsyncMock
        ) as mock_profile:
            mock_profile.return_value = None

            result = await customer_service.batch_update_customers(
                customer_ids=[99, 100],
                fields=fields,
                current_user=current_user,
            )

        # 验证返回值
        assert result["total"] == 2
        assert result["success_count"] == 0
        assert result["failed_count"] == 2
        assert len(result["failed_list"]) == 2
        assert result["failed_list"][0]["customer_id"] == 99
        assert result["failed_list"][0]["reason"] == "客户不存在"
        assert result["failed_list"][1]["customer_id"] == 100
        assert result["failed_list"][1]["reason"] == "客户不存在"

    @pytest.mark.asyncio
    async def test_batch_update_invalid_email_format(self, customer_service, mock_db_session):
        """测试 email 格式错误时部分失败"""
        customer = Customer(
            id=1,
            company_id=1001,
            name="客户 A",
            email="old@example.com",
        )

        call_count = {"count": 0}

        def execute_side_effect(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return make_mock_execute_result(customer)
            return make_mock_execute_result(None)

        mock_db_session.execute.side_effect = execute_side_effect

        fields = {"email": "invalid-email-no-at-sign"}
        current_user = {"user_id": 1}

        with patch.object(
            customer_service, "get_customer_profile", new_callable=AsyncMock
        ) as mock_profile:
            mock_profile.return_value = None

            result = await customer_service.batch_update_customers(
                customer_ids=[1],
                fields=fields,
                current_user=current_user,
            )

        # 验证返回值
        assert result["total"] == 1
        assert result["success_count"] == 0
        assert result["failed_count"] == 1
        assert result["failed_list"][0]["customer_id"] == 1
        assert result["failed_list"][0]["reason"] == "邮箱格式错误"

        # 验证 commit 未被调用（更新失败不应提交）
        mock_db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_update_audit_log_created(self, customer_service, mock_db_session):
        """测试批量更新成功后调用 create_audit_entry 记录审计日志"""
        customer = Customer(
            id=1,
            company_id=1001,
            name="客户 A",
            email="a@example.com",
        )

        call_count = {"count": 0}

        def execute_side_effect(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return make_mock_execute_result(customer)
            return make_mock_execute_result(None)

        mock_db_session.execute.side_effect = execute_side_effect

        fields = {"name": "更新后的名称"}
        current_user = {"user_id": 42}

        with patch.object(
            customer_service, "get_customer_profile", new_callable=AsyncMock
        ) as mock_profile:
            mock_profile.return_value = None

            with patch(
                "app.services.customers.create_audit_entry", new_callable=AsyncMock
            ) as mock_audit:
                with patch(
                    "app.services.customers.cache_service.invalidate_customer_cache",
                    new_callable=AsyncMock,
                ) as mock_cache:
                    await customer_service.batch_update_customers(
                        customer_ids=[1],
                        fields=fields,
                        current_user=current_user,
                    )

                    # 验证审计日志被调用
                    mock_audit.assert_called_once()
                    call_kwargs = mock_audit.call_args.kwargs
                    assert call_kwargs["user_id"] == 42
                    assert call_kwargs["action"] == "batch_update"
                    assert call_kwargs["module"] == "customers"
                    assert call_kwargs["operation_type"] == "batch"

                    # 验证缓存清理被调用
                    mock_cache.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_batch_update_cache_invalidated(self, customer_service, mock_db_session):
        """测试批量更新成功后调用 invalidate_customer_cache(None) 清理所有列表缓存"""
        customer = Customer(
            id=1,
            company_id=1001,
            name="客户 A",
            email="a@example.com",
        )

        call_count = {"count": 0}

        def execute_side_effect(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return make_mock_execute_result(customer)
            return make_mock_execute_result(None)

        mock_db_session.execute.side_effect = execute_side_effect

        fields = {"name": "更新后的名称"}
        current_user = {"user_id": 1}

        with patch.object(
            customer_service, "get_customer_profile", new_callable=AsyncMock
        ) as mock_profile:
            mock_profile.return_value = None

            with patch(
                "app.services.customers.cache_service.invalidate_customer_cache",
                new_callable=AsyncMock,
            ) as mock_cache:
                await customer_service.batch_update_customers(
                    customer_ids=[1],
                    fields=fields,
                    current_user=current_user,
                )

                # 验证缓存清理被调用且参数为 None
                mock_cache.assert_called_once_with(None)
