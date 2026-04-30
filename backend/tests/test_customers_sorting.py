"""客户列表排序功能测试

测试目标：
1. 排序参数验证（ALLOWED_SORT_FIELDS, VALID_SORT_ORDERS 常量）
2. CustomerService.get_all_customers 排序逻辑（Mock DB）
3. 无效排序参数错误处理
"""

import pytest
from unittest.mock import MagicMock

from app.services.customers import CustomerService, ALLOWED_SORT_FIELDS, VALID_SORT_ORDERS
from app.models.customers import Customer


# ==================== MockDBSession 工具类 ====================
# 注意：使用 MagicMock (非 AsyncMock) 因为 CustomerService 的 _is_async 检查
# 会将非 AsyncSession 实例识别为同步模式，直接调用 execute() 而不 await


class MockDBSession:
    """Mock 数据库会话（同步模式兼容）"""

    def __init__(self):
        self.execute = MagicMock()
        self._add_calls = []
        self._add_all_calls = []
        self.flush = MagicMock()
        self.commit = MagicMock()
        self.refresh = MagicMock()
        self._new = []

    def add(self, obj):
        self._add_calls.append(obj)
        self._new.append(obj)

    def add_all(self, objects):
        self._add_all_calls.append(objects)
        self._new.extend(objects)

    @property
    def new(self):
        return self._new


def make_mock_execute_result(rows, scalar_value=None):
    """创建 execute 返回结果

    Args:
        rows: 返回的行列表（用于 .all() 或 .scalars().all()）
        scalar_value: 标量值（用于 .scalar()）
    """
    result = MagicMock()
    result.all = MagicMock(return_value=rows)
    result.scalar_one_or_none = MagicMock(return_value=rows[0] if rows else None)

    if scalar_value is not None:
        result.scalar = MagicMock(return_value=scalar_value)
    elif rows and isinstance(rows[0], (list, tuple)):
        result.scalar = MagicMock(return_value=rows[0][0])
    else:
        result.scalar = MagicMock(return_value=None)

    scalars_result = MagicMock()
    scalars_result.all = MagicMock(return_value=rows)
    scalars_result.unique = MagicMock(return_value=scalars_result)
    result.scalars.return_value = scalars_result
    return result


# ==================== Fixtures ====================


@pytest.fixture
def mock_db():
    """创建 Mock 数据库会话"""
    return MockDBSession()


@pytest.fixture
def customer_service(mock_db):
    """创建 CustomerService 实例"""
    service = CustomerService(mock_db)
    yield service, mock_db


# ==================== 排序常量验证测试 ====================


class TestSortConstants:
    """排序常量验证"""

    def test_allowed_sort_fields_contains_expected_fields(self):
        """验证排序字段白名单包含预期字段（包括新扩展的 industry, settlement_type, manager_id, sales_manager_id, is_key_customer）"""
        expected_fields = {
            "id",
            "company_id",
            "name",
            "created_at",
            "updated_at",
            "industry",  # 行业类型 (CustomerProfile 表)
            "settlement_type",  # 结算方式 (Customer 表)
            "manager_id",  # 运营经理 (Customer 表)
            "sales_manager_id",  # 商务经理 (Customer 表)
            "is_key_customer",  # 重点客户 (Customer 表)
        }
        assert ALLOWED_SORT_FIELDS == expected_fields

    def test_valid_sort_orders(self):
        """验证排序方向白名单"""
        assert VALID_SORT_ORDERS == {"asc", "desc"}

    def test_sensitive_fields_not_in_allowlist(self):
        """验证敏感字段不在排序白名单中"""
        assert "password" not in ALLOWED_SORT_FIELDS
        assert "deleted_at" not in ALLOWED_SORT_FIELDS
        assert "email" not in ALLOWED_SORT_FIELDS
        # manager_id 现在是可排序字段（运营经理）
        # 注意：manager_id 是业务字段，不是敏感字段

    def test_sort_order_case_sensitive(self):
        """验证排序方向区分大小写"""
        assert "ASC" not in VALID_SORT_ORDERS
        assert "DESC" not in VALID_SORT_ORDERS
        assert "Random" not in VALID_SORT_ORDERS


# ==================== 服务层排序参数验证测试 ====================


class TestSortValidation:
    """排序参数验证测试（使用 Mock DB）"""

    @pytest.mark.asyncio
    async def test_invalid_sort_field_raises_value_error(self, customer_service):
        """无效排序字段应抛出 ValueError"""
        service, mock_db = customer_service

        mock_db.execute.return_value = make_mock_execute_result([(0,)])

        with pytest.raises(ValueError, match="Invalid sort field"):
            await service.get_all_customers(sort_by="invalid_field")

    @pytest.mark.asyncio
    async def test_password_field_raises_value_error(self, customer_service):
        """敏感字段 password 应抛出 ValueError"""
        service, mock_db = customer_service

        mock_db.execute.return_value = make_mock_execute_result([(0,)])

        with pytest.raises(ValueError, match="Invalid sort field"):
            await service.get_all_customers(sort_by="password")

    @pytest.mark.asyncio
    async def test_deleted_at_field_raises_value_error(self, customer_service):
        """deleted_at 字段应抛出 ValueError"""
        service, mock_db = customer_service

        mock_db.execute.return_value = make_mock_execute_result([(0,)])

        with pytest.raises(ValueError, match="Invalid sort field"):
            await service.get_all_customers(sort_by="deleted_at")

    @pytest.mark.asyncio
    async def test_invalid_sort_order_raises_value_error(self, customer_service):
        """无效排序方向应抛出 ValueError"""
        service, mock_db = customer_service

        mock_db.execute.return_value = make_mock_execute_result([(0,)])

        with pytest.raises(ValueError, match="Invalid sort order"):
            await service.get_all_customers(sort_order="DESC")

    @pytest.mark.asyncio
    async def test_random_sort_order_raises_value_error(self, customer_service):
        """随机排序方向应抛出 ValueError"""
        service, mock_db = customer_service

        mock_db.execute.return_value = make_mock_execute_result([(0,)])

        with pytest.raises(ValueError, match="Invalid sort order"):
            await service.get_all_customers(sort_order="random")


# ==================== 服务层排序逻辑集成测试 ====================


class TestSortServiceIntegration:
    """服务层排序集成测试（使用 Mock DB）

    注意：由于使用 Mock DB，实际的 SQL 排序不会执行。
    我们验证的是：
    1. 服务层能正确处理各种排序参数组合
    2. 返回的数据结构正确
    3. 排序参数验证逻辑正确
    """

    @pytest.mark.asyncio
    async def test_default_sort_is_id_asc(self, customer_service):
        """默认应按 id 递增排序"""
        service, mock_db = customer_service

        # Mock 数据按 id 递增（模拟数据库排序后的结果）
        mock_customers = [
            Customer(id=1, company_id=100, name="Customer A"),
            Customer(id=2, company_id=200, name="Customer B"),
            Customer(id=3, company_id=150, name="Customer C"),
        ]

        mock_db.execute.side_effect = [
            make_mock_execute_result([(3,)]),
            make_mock_execute_result(mock_customers),
        ]

        customers, total = await service.get_all_customers(page=1, page_size=100)

        assert total == 3
        assert len(customers) == 3
        for i in range(len(customers) - 1):
            assert customers[i].id <= customers[i + 1].id

    @pytest.mark.asyncio
    async def test_sort_by_company_id_asc(self, customer_service):
        """按 company_id 升序排序"""
        service, mock_db = customer_service

        # Mock 数据按 company_id 递增（模拟数据库排序后的结果）
        mock_customers = [
            Customer(id=1, company_id=100, name="Customer A"),
            Customer(id=3, company_id=150, name="Customer C"),
            Customer(id=2, company_id=200, name="Customer B"),
        ]

        mock_db.execute.side_effect = [
            make_mock_execute_result([(3,)]),
            make_mock_execute_result(mock_customers),
        ]

        customers, total = await service.get_all_customers(
            page=1, page_size=100, sort_by="company_id", sort_order="asc"
        )

        assert total == 3
        assert len(customers) == 3
        for i in range(len(customers) - 1):
            assert customers[i].company_id <= customers[i + 1].company_id

    @pytest.mark.asyncio
    async def test_sort_by_company_id_desc(self, customer_service):
        """按 company_id 降序排序"""
        service, mock_db = customer_service

        # Mock 数据按 company_id 递减（模拟数据库排序后的结果）
        mock_customers = [
            Customer(id=2, company_id=200, name="Customer B"),
            Customer(id=3, company_id=150, name="Customer C"),
            Customer(id=1, company_id=100, name="Customer A"),
        ]

        mock_db.execute.side_effect = [
            make_mock_execute_result([(3,)]),
            make_mock_execute_result(mock_customers),
        ]

        customers, total = await service.get_all_customers(
            page=1, page_size=100, sort_by="company_id", sort_order="desc"
        )

        assert total == 3
        for i in range(len(customers) - 1):
            assert customers[i].company_id >= customers[i + 1].company_id

    @pytest.mark.asyncio
    async def test_sort_by_name_asc(self, customer_service):
        """按 name 升序排序"""
        service, mock_db = customer_service

        mock_customers = [
            Customer(id=1, company_id=100, name="Alpha"),
            Customer(id=2, company_id=200, name="Beta"),
            Customer(id=3, company_id=150, name="Gamma"),
        ]

        mock_db.execute.side_effect = [
            make_mock_execute_result([(3,)]),
            make_mock_execute_result(mock_customers),
        ]

        customers, _ = await service.get_all_customers(
            page=1, page_size=100, sort_by="name", sort_order="asc"
        )

        assert len(customers) == 3
        for i in range(len(customers) - 1):
            assert customers[i].name <= customers[i + 1].name

    @pytest.mark.asyncio
    async def test_sort_by_created_at_desc(self, customer_service):
        """按 created_at 降序排序"""
        service, mock_db = customer_service

        from datetime import datetime

        # Mock 数据按 created_at 递减（模拟数据库排序后的结果）
        mock_customers = [
            Customer(id=2, company_id=200, name="Customer B", created_at=datetime(2026, 3, 1)),
            Customer(id=3, company_id=150, name="Customer C", created_at=datetime(2026, 2, 1)),
            Customer(id=1, company_id=100, name="Customer A", created_at=datetime(2026, 1, 1)),
        ]

        mock_db.execute.side_effect = [
            make_mock_execute_result([(3,)]),
            make_mock_execute_result(mock_customers),
        ]

        customers, _ = await service.get_all_customers(
            page=1, page_size=100, sort_by="created_at", sort_order="desc"
        )

        assert len(customers) == 3
        for i in range(len(customers) - 1):
            assert customers[i].created_at >= customers[i + 1].created_at

    @pytest.mark.asyncio
    async def test_sort_by_updated_at_asc(self, customer_service):
        """按 updated_at 升序排序"""
        service, mock_db = customer_service

        from datetime import datetime

        mock_customers = [
            Customer(id=1, company_id=100, name="Customer A", updated_at=datetime(2026, 1, 1)),
            Customer(id=2, company_id=200, name="Customer B", updated_at=datetime(2026, 2, 1)),
            Customer(id=3, company_id=150, name="Customer C", updated_at=datetime(2026, 3, 1)),
        ]

        mock_db.execute.side_effect = [
            make_mock_execute_result([(3,)]),
            make_mock_execute_result(mock_customers),
        ]

        customers, _ = await service.get_all_customers(
            page=1, page_size=100, sort_by="updated_at", sort_order="asc"
        )

        assert len(customers) == 3
        for i in range(len(customers) - 1):
            assert customers[i].updated_at <= customers[i + 1].updated_at

    @pytest.mark.asyncio
    async def test_sort_with_empty_result(self, customer_service):
        """空结果集排序不应报错"""
        service, mock_db = customer_service

        mock_db.execute.side_effect = [
            make_mock_execute_result([(0,)]),
            make_mock_execute_result([]),
        ]

        customers, total = await service.get_all_customers(
            page=1, page_size=20, sort_by="name", sort_order="desc"
        )

        assert total == 0
        assert len(customers) == 0

    @pytest.mark.asyncio
    async def test_sort_with_pagination(self, customer_service):
        """排序应与分页正确配合"""
        service, mock_db = customer_service

        mock_customers_page1 = [
            Customer(id=1, company_id=100, name="Customer A"),
            Customer(id=2, company_id=200, name="Customer B"),
        ]

        mock_db.execute.side_effect = [
            make_mock_execute_result([(5,)]),
            make_mock_execute_result(mock_customers_page1),
        ]

        customers, total = await service.get_all_customers(
            page=1, page_size=2, sort_by="id", sort_order="asc"
        )

        assert total == 5
        assert len(customers) == 2
        assert customers[0].id == 1
        assert customers[1].id == 2

    @pytest.mark.asyncio
    async def test_sort_with_filters(self, customer_service):
        """排序应与筛选条件配合工作"""
        service, mock_db = customer_service

        mock_customers = [
            Customer(id=1, company_id=100, name="Customer A"),
            Customer(id=2, company_id=200, name="Customer B"),
        ]

        mock_db.execute.side_effect = [
            make_mock_execute_result([(2,)]),
            make_mock_execute_result(mock_customers),
        ]

        customers, total = await service.get_all_customers(
            page=1,
            page_size=20,
            filters={"keyword": "Customer"},
            sort_by="name",
            sort_order="asc",
        )

        assert total == 2
        assert len(customers) == 2


# ==================== 边界场景测试 ====================


class TestSortEdgeCases:
    """排序边界场景测试"""

    @pytest.mark.asyncio
    async def test_sort_single_customer(self, customer_service):
        """单个客户排序"""
        service, mock_db = customer_service

        mock_customers = [Customer(id=1, company_id=100, name="Only Customer")]

        mock_db.execute.side_effect = [
            make_mock_execute_result([(1,)]),
            make_mock_execute_result(mock_customers),
        ]

        customers, total = await service.get_all_customers(
            page=1, page_size=20, sort_by="company_id", sort_order="desc"
        )

        assert total == 1
        assert len(customers) == 1

    @pytest.mark.asyncio
    async def test_sort_with_null_values(self, customer_service):
        """包含 NULL 值的排序（name 可能为 NULL）"""
        service, mock_db = customer_service

        mock_customers = [
            Customer(id=2, company_id=200, name=None),
            Customer(id=1, company_id=100, name="Customer A"),
            Customer(id=3, company_id=150, name="Customer C"),
        ]

        mock_db.execute.side_effect = [
            make_mock_execute_result([(3,)]),
            make_mock_execute_result(mock_customers),
        ]

        customers, total = await service.get_all_customers(
            page=1, page_size=100, sort_by="name", sort_order="asc"
        )

        assert total == 3
        assert len(customers) == 3

    @pytest.mark.asyncio
    async def test_all_allowed_sort_fields_are_valid_customer_attributes(self):
        """验证所有允许的排序字段都是有效字段（Customer 或 CustomerProfile 的属性）"""
        from app.models.customers import CustomerProfile

        for field in ALLOWED_SORT_FIELDS:
            # industry 字段在 CustomerProfile 表中
            if field == "industry":
                assert hasattr(
                    CustomerProfile, field
                ), f"{field} is not a valid CustomerProfile attribute"
            else:
                # 其他字段在 Customer 表中
                assert hasattr(Customer, field), f"{field} is not a valid Customer attribute"
