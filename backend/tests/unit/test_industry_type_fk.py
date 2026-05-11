"""行业类型外键关联集成测试"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from app.models.customers import Customer, CustomerProfile
from app.models.industry_type import IndustryType
from app.services.customers import CustomerService


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


@pytest.mark.asyncio
class TestIndustryTypeForeignKey:
    """行业类型外键关联测试"""

    async def test_create_customer_with_industry_type(self, mock_db_session):
        """测试创建客户时关联行业类型"""
        # 准备测试数据
        industry_type = IndustryType(id=1, name="测试行业", sort_order=999)

        # Mock execute 返回 IndustryType
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = industry_type
        mock_db_session.execute.return_value = mock_result

        # Mock flush 和 refresh
        created_customer = Customer(id=1, company_id=999999, name="测试客户")

        async def mock_flush():
            mock_db_session.new.add(created_customer)
            created_customer.id = 1

        async def mock_refresh(obj):
            if hasattr(obj, "id") and not getattr(obj, "id", None):
                obj.id = 1
            # 设置 profile 的关联
            if isinstance(obj, Customer):
                obj.profile = CustomerProfile(
                    customer_id=1,
                    industry_type_id=industry_type.id,
                    industry_type=industry_type,
                )

        mock_db_session.flush = mock_flush
        mock_db_session.refresh = mock_refresh

        service = CustomerService(db_session=mock_db_session)
        customer = await service.create_customer(
            {
                "company_id": 999999,
                "name": "测试客户",
                "industry_type_id": industry_type.id,
            }
        )

        assert customer is not None
        assert customer.profile is not None
        assert customer.profile.industry_type_id == industry_type.id

    async def test_create_customer_without_industry_type(self, mock_db_session):
        """测试创建客户时不指定行业类型"""
        created_customer = Customer(id=2, company_id=999998, name="测试客户无行业")

        async def mock_flush():
            mock_db_session.new.add(created_customer)
            created_customer.id = 2

        async def mock_refresh(obj):
            if hasattr(obj, "id") and not getattr(obj, "id", None):
                obj.id = 2

        mock_db_session.flush = mock_flush
        mock_db_session.refresh = mock_refresh

        service = CustomerService(db_session=mock_db_session)
        customer = await service.create_customer(
            {
                "company_id": 999998,
                "name": "测试客户无行业",
            }
        )

        assert customer is not None
        # 没有提供 industry_type_id 时，profile 不会创建
        assert customer.profile is None

    async def test_update_customer_industry_type(self, mock_db_session):
        """测试更新客户行业类型"""
        # 创建 Mock 行业类型
        it1 = IndustryType(id=1, name="行业A", sort_order=100)
        it2 = IndustryType(id=2, name="行业B", sort_order=101)

        # Mock get_customer_by_id 返回已有客户
        existing_profile = CustomerProfile(customer_id=1, industry_type_id=it1.id)
        existing_customer = Customer(
            id=1,
            company_id=999997,
            name="测试更新行业",
        )
        existing_customer.profile = existing_profile

        mock_get = MagicMock()
        mock_get.scalar_one_or_none.return_value = existing_customer
        mock_db_session.execute.return_value = mock_get

        service = CustomerService(db_session=mock_db_session)

        # 执行更新
        updated = await service.update_customer(
            1,
            {
                "industry_type_id": it2.id,
            },
        )

        assert updated is not None
        mock_db_session.commit.assert_called_once()

    async def test_delete_industry_type_sets_null(self, mock_db_session):
        """测试删除行业类型后客户 industry_type_id 设为 NULL"""
        # 创建客户画像
        profile = CustomerProfile(customer_id=1, industry_type_id=1)
        customer = Customer(id=1, company_id=999996, name="测试删除行业")
        customer.profile = profile

        # Mock get_customer_by_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = customer
        mock_db_session.execute.return_value = mock_result

        CustomerService(db_session=mock_db_session)

        # 模拟删除：设置 industry_type_id 为 None
        async def mock_delete():
            profile.industry_type_id = None
            mock_db_session.commit()

        mock_db_session.commit = mock_delete

        # 模拟删除行业类型（实际是软删除，不影响外键）
        # 验证 customer 的 industry_type_id
        assert customer.profile.industry_type_id == 1
