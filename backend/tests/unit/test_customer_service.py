"""Customer Service 单元测试"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal

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
    session.new = set()  # 用于跟踪新添加的对象
    return session


@pytest.fixture
def mock_db_session_with_flush():
    """Mock 数据库会话（带自定义 flush）"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.new = set()
    return session


@pytest.fixture
def customer_service(mock_db_session):
    """创建 CustomerService 实例"""
    return CustomerService(db_session=mock_db_session)


# ==================== Test Create Customer ====================


class TestCustomerService_CreateCustomer:
    """创建客户测试"""

    @pytest.mark.asyncio
    async def test_create_customer_success(self, mock_db_session_with_flush):
        """测试创建客户成功"""
        # 准备测试数据
        customer_data = {
            "company_id": "COMP001",
            "name": "测试公司",
            "account_type": "enterprise",
            "business_type": "technology",
            "customer_level": "gold",
            "price_policy": "standard",
            "manager_id": 1,
            "settlement_cycle": "monthly",
            "settlement_type": "prepaid",
            "is_key_customer": True,
            "email": "test@example.com",
        }

        # Mock 数据库操作
        created_customer = Customer(
            id=1,
            company_id=customer_data["company_id"],
            name=customer_data["name"],
            account_type=customer_data["account_type"],
            business_type=customer_data["business_type"],
            customer_level=customer_data["customer_level"],
            price_policy=customer_data["price_policy"],
            manager_id=customer_data["manager_id"],
            settlement_cycle=customer_data["settlement_cycle"],
            settlement_type=customer_data["settlement_type"],
            is_key_customer=customer_data["is_key_customer"],
            email=customer_data["email"],
            deleted_at=None,
        )

        # Mock flush 和 refresh
        async def mock_flush():
            mock_db_session_with_flush.new.add(created_customer)
            created_customer.id = 1

        async def mock_refresh(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = 1

        mock_db_session_with_flush.flush = mock_flush
        mock_db_session_with_flush.refresh = mock_refresh

        # 创建服务实例
        customer_service = CustomerService(db_session=mock_db_session_with_flush)

        # 执行测试
        result = await customer_service.create_customer(customer_data)

        # 验证结果
        assert result is not None
        assert isinstance(result, Customer)
        assert result.company_id == "COMP001"
        assert result.name == "测试公司"
        assert result.account_type == "enterprise"
        assert result.is_key_customer is True

        # 验证数据库操作被调用
        mock_db_session_with_flush.add.assert_called()
        # flush 是函数，不能用 assert_called
        mock_db_session_with_flush.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_customer_minimal_data(
        self, customer_service, mock_db_session
    ):
        """测试使用最少数据创建客户"""
        # 准备最少测试数据
        customer_data = {
            "company_id": "COMP002",
            "name": "最小化测试公司",
        }

        # Mock 数据库操作
        created_customer = Customer(
            id=2,
            company_id="COMP002",
            name="最小化测试公司",
            deleted_at=None,
        )

        async def mock_flush():
            mock_db_session.new.add(created_customer)
            created_customer.id = 2

        async def mock_refresh(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = 2

        mock_db_session.flush = mock_flush
        mock_db_session.refresh = mock_refresh

        # 执行测试
        result = await customer_service.create_customer(customer_data)

        # 验证结果
        assert result is not None
        assert result.company_id == "COMP002"
        assert result.name == "最小化测试公司"
        # 验证默认值
        assert result.is_key_customer is False

    @pytest.mark.asyncio
    async def test_create_customer_creates_balance(
        self, customer_service, mock_db_session
    ):
        """测试创建客户时自动创建余额记录"""
        customer_data = {
            "company_id": "COMP003",
            "name": "测试公司",
        }

        created_customer = Customer(
            id=3,
            company_id="COMP003",
            name="测试公司",
            deleted_at=None,
        )

        async def mock_flush():
            mock_db_session.new.add(created_customer)
            created_customer.id = 3

        async def mock_refresh(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = 3

        mock_db_session.flush = mock_flush
        mock_db_session.refresh = mock_refresh

        # 执行测试
        await customer_service.create_customer(customer_data)

        # 验证创建了余额记录
        # 检查 add 被调用了至少 2 次（客户 + 余额）
        assert mock_db_session.add.call_count >= 2


# ==================== Test Update Customer ====================


class TestCustomerService_UpdateCustomer:
    """更新客户测试"""

    @pytest.mark.asyncio
    async def test_update_customer_success(self, customer_service, mock_db_session):
        """测试更新客户成功"""
        customer_id = 1

        # Mock 现有客户
        existing_customer = Customer(
            id=customer_id,
            company_id="COMP001",
            name="原名称",
            account_type="enterprise",
            business_type="technology",
            customer_level="silver",
            email="old@example.com",
            deleted_at=None,
        )

        # Mock 查询返回现有客户
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_customer
        mock_db_session.execute.return_value = mock_result

        # 准备更新数据
        update_data = {
            "name": "新名称",
            "customer_level": "gold",
            "email": "new@example.com",
            "is_key_customer": True,
        }

        # 执行测试
        result = await customer_service.update_customer(customer_id, update_data)

        # 验证结果
        assert result is not None
        assert result.id == customer_id
        assert result.name == "新名称"
        assert result.customer_level == "gold"
        assert result.email == "new@example.com"
        assert result.is_key_customer is True
        # 验证未更新的字段保持不变
        assert result.company_id == "COMP001"
        assert result.account_type == "enterprise"

        # 验证数据库操作
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_customer_not_found(self, customer_service, mock_db_session):
        """测试更新不存在的客户"""
        customer_id = 999

        # Mock 查询返回 None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # 准备更新数据
        update_data = {
            "name": "新名称",
        }

        # 执行测试
        result = await customer_service.update_customer(customer_id, update_data)

        # 验证结果
        assert result is None
        # 验证没有调用 commit
        mock_db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_customer_partial_update(
        self, customer_service, mock_db_session
    ):
        """测试部分字段更新"""
        customer_id = 1

        existing_customer = Customer(
            id=customer_id,
            company_id="COMP001",
            name="原名称",
            account_type="enterprise",
            business_type="technology",
            customer_level="silver",
            email="test@example.com",
            deleted_at=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_customer
        mock_db_session.execute.return_value = mock_result

        # 只更新一个字段
        update_data = {
            "is_key_customer": True,
        }

        result = await customer_service.update_customer(customer_id, update_data)

        # 验证结果
        assert result is not None
        assert result.is_key_customer is True
        # 验证其他字段不变
        assert result.name == "原名称"
        assert result.customer_level == "silver"


# ==================== Test Delete Customer ====================


class TestCustomerService_DeleteCustomer:
    """删除客户测试"""

    @pytest.mark.asyncio
    async def test_delete_customer_success(self, customer_service, mock_db_session):
        """测试删除客户成功（软删除）"""
        customer_id = 1

        # Mock 现有客户
        existing_customer = Customer(
            id=customer_id,
            company_id="COMP001",
            name="测试公司",
            deleted_at=None,
        )

        # Mock 查询返回现有客户
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_customer
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await customer_service.delete_customer(customer_id)

        # 验证结果
        assert result is True
        # 验证设置了 deleted_at
        assert existing_customer.deleted_at is not None
        # 验证数据库操作
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_delete_customer_not_found(self, customer_service, mock_db_session):
        """测试删除不存在的客户"""
        customer_id = 999

        # Mock 查询返回 None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await customer_service.delete_customer(customer_id)

        # 验证结果
        assert result is False
        mock_db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_customer_already_deleted(
        self, customer_service, mock_db_session
    ):
        """测试删除已删除的客户"""
        customer_id = 1

        # Mock 查询 - 已删除的客户应该返回 None（因为查询条件包含 deleted_at.is_(None)）
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await customer_service.delete_customer(customer_id)

        # 验证结果
        assert result is False


# ==================== Test Batch Create Customers ====================


class TestCustomerService_BatchCreateCustomers:
    """批量创建客户测试"""

    @pytest.mark.asyncio
    async def test_batch_create_customers_success(self, mock_db_session_with_flush):
        """测试批量创建客户成功"""
        # 准备测试数据
        customers_data = [
            {"company_id": "COMP001", "name": "公司 1"},
            {"company_id": "COMP002", "name": "公司 2"},
            {"company_id": "COMP003", "name": "公司 3"},
        ]

        # Mock 现有 company_id 查询
        mock_result = MagicMock()
        mock_result.all.return_value = []  # 没有已存在的公司
        mock_db_session_with_flush.execute.return_value = mock_result

        # Mock 创建的客户
        created_customers = [
            Customer(id=1, company_id="COMP001", name="公司 1", deleted_at=None),
            Customer(id=2, company_id="COMP002", name="公司 2", deleted_at=None),
            Customer(id=3, company_id="COMP003", name="公司 3", deleted_at=None),
        ]

        # Mock flush 添加新对象
        async def mock_flush():
            for c in created_customers:
                mock_db_session_with_flush.new.add(c)

        mock_db_session_with_flush.flush = mock_flush

        # 创建服务实例
        customer_service = CustomerService(db_session=mock_db_session_with_flush)

        # 执行测试
        success_count, errors = await customer_service.batch_create_customers(
            customers_data
        )

        # 验证结果
        assert success_count == 3
        assert len(errors) == 0
        # 验证数据库操作
        mock_db_session_with_flush.commit.assert_called()

    @pytest.mark.asyncio
    async def test_batch_create_customers_with_duplicates(
        self, customer_service, mock_db_session
    ):
        """测试批量创建客户 - 包含重复的公司 ID"""
        customers_data = [
            {"company_id": "COMP001", "name": "公司 1"},
            {"company_id": "COMP001", "name": "重复公司 1"},  # 重复
            {"company_id": "COMP002", "name": "公司 2"},
        ]

        # Mock 现有 company_id 查询
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        async def mock_flush():
            mock_db_session.new.add(
                Customer(id=1, company_id="COMP001", name="公司 1", deleted_at=None)
            )
            mock_db_session.new.add(
                Customer(id=2, company_id="COMP002", name="公司 2", deleted_at=None)
            )

        mock_db_session.flush = mock_flush

        # 执行测试
        success_count, errors = await customer_service.batch_create_customers(
            customers_data
        )

        # 验证结果 - 同批次重复会被检测到
        assert success_count == 2
        assert len(errors) == 1
        assert "COMP001 已存在" in errors[0]

    @pytest.mark.asyncio
    async def test_batch_create_customers_with_existing(
        self, customer_service, mock_db_session
    ):
        """测试批量创建客户 - 包含已存在的公司 ID"""
        customers_data = [
            {"company_id": "EXIST001", "name": "已存在公司"},
            {"company_id": "NEW001", "name": "新公司"},
        ]

        # Mock 现有 company_id 查询
        mock_result = MagicMock()
        mock_result.all.return_value = [("EXIST001",)]  # 已存在的公司
        mock_db_session.execute.return_value = mock_result

        async def mock_flush():
            mock_db_session.new.add(
                Customer(id=1, company_id="NEW001", name="新公司", deleted_at=None)
            )

        mock_db_session.flush = mock_flush

        # 执行测试
        success_count, errors = await customer_service.batch_create_customers(
            customers_data
        )

        # 验证结果
        assert success_count == 1
        assert len(errors) == 1
        assert "EXIST001 已存在" in errors[0]

    @pytest.mark.asyncio
    async def test_batch_create_customers_missing_company_id(
        self, customer_service, mock_db_session
    ):
        """测试批量创建客户 - 缺少 company_id"""
        customers_data = [
            {"name": "公司 1"},  # 缺少 company_id
            {"company_id": "COMP001", "name": "公司 2"},
        ]

        # Mock 现有 company_id 查询
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        async def mock_flush():
            mock_db_session.new.add(
                Customer(id=1, company_id="COMP001", name="公司 2", deleted_at=None)
            )

        mock_db_session.flush = mock_flush

        # 执行测试
        success_count, errors = await customer_service.batch_create_customers(
            customers_data
        )

        # 验证结果
        assert success_count == 1
        assert len(errors) == 1
        assert "缺少 company_id" in errors[0]


# ==================== Test Get Customer By ID ====================


class TestCustomerService_GetCustomerById:
    """根据 ID 获取客户测试"""

    @pytest.mark.asyncio
    async def test_get_customer_by_id_success(self, customer_service, mock_db_session):
        """测试获取存在的客户"""
        customer_id = 1

        # Mock 现有客户
        existing_customer = Customer(
            id=customer_id,
            company_id="COMP001",
            name="测试公司",
            account_type="enterprise",
            deleted_at=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_customer
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await customer_service.get_customer_by_id(customer_id)

        # 验证结果
        assert result is not None
        assert isinstance(result, Customer)
        assert result.id == customer_id
        assert result.name == "测试公司"

    @pytest.mark.asyncio
    async def test_get_customer_by_id_not_found(
        self, customer_service, mock_db_session
    ):
        """测试获取不存在的客户"""
        customer_id = 999

        # Mock 查询返回 None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await customer_service.get_customer_by_id(customer_id)

        # 验证结果
        assert result is None

    @pytest.mark.asyncio
    async def test_get_customer_by_id_deleted(self, customer_service, mock_db_session):
        """测试获取已删除的客户"""
        customer_id = 1

        # Mock 查询 - 已删除的客户应该返回 None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await customer_service.get_customer_by_id(customer_id)

        # 验证结果
        assert result is None


# ==================== Integration Tests ====================


class TestCustomerService_Integration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_customer_crud_lifecycle(self, customer_service, mock_db_session):
        """测试客户完整的 CRUD 生命周期"""
        # 1. 创建客户
        create_data = {
            "company_id": "COMP100",
            "name": "生命周期测试公司",
            "customer_level": "silver",
        }

        created_customer = Customer(
            id=100,
            company_id="COMP100",
            name="生命周期测试公司",
            customer_level="silver",
            deleted_at=None,
        )

        async def mock_flush():
            mock_db_session.new.add(created_customer)
            created_customer.id = 100

        async def mock_refresh(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = 100

        mock_db_session.flush = mock_flush
        mock_db_session.refresh = mock_refresh

        # 创建
        result = await customer_service.create_customer(create_data)
        assert result is not None
        assert result.name == "生命周期测试公司"

        # 2. 更新客户
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = created_customer
        mock_db_session.execute.return_value = mock_result

        update_data = {"customer_level": "gold", "is_key_customer": True}
        result = await customer_service.update_customer(100, update_data)
        assert result is not None
        assert result.customer_level == "gold"
        assert result.is_key_customer is True

        # 3. 删除客户
        result = await customer_service.delete_customer(100)
        assert result is True
        assert created_customer.deleted_at is not None

    @pytest.mark.asyncio
    async def test_customer_with_profile_and_balance(
        self, customer_service, mock_db_session
    ):
        """测试客户关联画像和余额"""
        customer_id = 1

        # Mock 客户及其关联数据
        customer = Customer(
            id=customer_id,
            company_id="COMP001",
            name="测试公司",
            deleted_at=None,
        )

        # Mock 关联的 profile 和 balance
        profile = CustomerProfile(
            customer_id=customer_id,
            scale_level="medium",
            consume_level="high",
            industry="technology",
        )
        balance = CustomerBalance(
            customer_id=customer_id,
            total_amount=Decimal("10000.00"),
            real_amount=Decimal("8000.00"),
            bonus_amount=Decimal("2000.00"),
        )

        customer.profile = profile
        customer.balance = balance

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = customer
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await customer_service.get_customer_by_id(customer_id)

        # 验证结果
        assert result is not None
        assert result.profile is not None
        assert result.balance is not None
        assert result.profile.scale_level == "medium"
        assert result.balance.total_amount == Decimal("10000.00")


# ==================== Test is_key_customer Filter ====================


class TestCustomerService_IsKeyCustomerFilter:
    """重点客户筛选测试"""

    @pytest.mark.asyncio
    async def test_get_all_customers_filter_is_key_customer_true(self, mock_db_session):
        """测试筛选重点客户（is_key_customer=True）"""
        from sqlalchemy.ext.asyncio import AsyncSession

        # 准备测试数据
        key_customer = Customer(
            id=1,
            company_id="COMP001",
            name="重点客户",
            is_key_customer=True,
            deleted_at=None,
        )

        # Mock 查询返回 - 需要设置 return_value
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [key_customer]
        mock_result.scalar.return_value = 1  # count 结果

        # AsyncMock 需要设置 return_value 而不是 side_effect
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        # 强制让 isinstance 检查通过
        mock_db_session.__class__ = AsyncSession

        customer_service = CustomerService(db_session=mock_db_session)

        # 测试筛选 is_key_customer=True
        customers, total = await customer_service.get_all_customers(
            page=1, page_size=20, filters={"is_key_customer": True}
        )

        # 验证只返回了重点客户
        assert len(customers) == 1
        assert customers[0].is_key_customer is True
        assert customers[0].name == "重点客户"

    @pytest.mark.asyncio
    async def test_get_all_customers_filter_is_key_customer_false(
        self, mock_db_session
    ):
        """测试筛选非重点客户（is_key_customer=False）"""
        from sqlalchemy.ext.asyncio import AsyncSession

        # 准备测试数据
        normal_customer = Customer(
            id=2,
            company_id="COMP002",
            name="普通客户",
            is_key_customer=False,
            deleted_at=None,
        )

        # Mock 查询返回
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [normal_customer]
        mock_result.scalar.return_value = 1  # count 结果

        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.__class__ = AsyncSession

        customer_service = CustomerService(db_session=mock_db_session)

        # 测试筛选 is_key_customer=False
        customers, total = await customer_service.get_all_customers(
            page=1, page_size=20, filters={"is_key_customer": False}
        )

        # 验证只返回了非重点客户
        assert len(customers) == 1
        assert customers[0].is_key_customer is False
        assert customers[0].name == "普通客户"
