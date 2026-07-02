"""CustomerRepository 单元测试"""

import pytest

from app.models.customers import Customer
from app.repository import CustomerRepository


@pytest.mark.asyncio
class TestCustomerRepository:
    """CustomerRepository 测试类"""

    async def test_find_by_id(self, db_session, sample_customer):
        """测试根据 ID 查询"""
        repo = CustomerRepository(db_session)

        result = await repo.find_by_id(sample_customer.id)

        assert result is not None
        assert result.id == sample_customer.id
        assert result.name == sample_customer.name

    async def test_find_by_id_not_found(self, db_session):
        """测试查询不存在的记录"""
        repo = CustomerRepository(db_session)

        result = await repo.find_by_id(99999)

        assert result is None

    async def test_find_by_id_include_deleted(self, db_session, sample_customer):
        """测试包含软删除记录的查询"""
        repo = CustomerRepository(db_session)

        # 先软删除
        await repo.soft_delete(sample_customer.id)

        # 默认查询应该找不到
        result = await repo.find_by_id(sample_customer.id)
        assert result is None

        # 包含删除记录应该能找到
        result = await repo.find_by_id(sample_customer.id, include_deleted=True)
        assert result is not None
        assert result.id == sample_customer.id

    async def test_find_all(self, db_session, sample_customer):
        """测试查询所有记录"""
        repo = CustomerRepository(db_session)

        results = await repo.find_all()

        assert len(results) > 0
        assert all(isinstance(r, Customer) for r in results)

    async def test_find_all_with_filters(self, db_session, sample_customer):
        """测试带过滤条件的查询"""
        repo = CustomerRepository(db_session)

        results = await repo.find_all(name=sample_customer.name)

        assert len(results) > 0
        assert all(r.name == sample_customer.name for r in results)

    async def test_count(self, db_session, sample_customer):
        """测试计数"""
        repo = CustomerRepository(db_session)

        count = await repo.count()

        assert count > 0

    async def test_soft_delete(self, db_session, sample_customer):
        """测试软删除"""
        repo = CustomerRepository(db_session)

        # 软删除
        result = await repo.soft_delete(sample_customer.id)
        assert result is True

        # 验证已软删除
        customer = await repo.find_by_id(sample_customer.id)
        assert customer is None

        # 验证 deleted_at 已设置
        customer = await repo.find_by_id(sample_customer.id, include_deleted=True)
        assert customer is not None
        assert customer.deleted_at is not None

    async def test_create(self, db_session):
        """测试创建记录"""
        repo = CustomerRepository(db_session)

        customer = Customer(
            name="Test Customer",
            contact_person="Test Contact",
            phone="1234567890",
            email="test@example.com",
        )

        result = await repo.create(customer)

        assert result.id is not None
        assert result.name == "Test Customer"
        assert result.created_at is not None

    async def test_update(self, db_session, sample_customer):
        """测试更新记录"""
        repo = CustomerRepository(db_session)

        sample_customer.name = "Updated Name"
        result = await repo.update(sample_customer)

        assert result.name == "Updated Name"
        assert result.updated_at is not None

    async def test_find_by_company_id(self, db_session, sample_customer):
        """测试根据公司 ID 查询"""
        repo = CustomerRepository(db_session)

        result = await repo.find_by_company_id(sample_customer.company_id)

        assert result is not None
        assert result.company_id == sample_customer.company_id

    async def test_find_by_manager_id(self, db_session, sample_customer):
        """测试根据客户经理 ID 查询"""
        repo = CustomerRepository(db_session)

        results = await repo.find_by_manager_id(sample_customer.manager_id)

        assert len(results) > 0
        assert all(r.manager_id == sample_customer.manager_id for r in results)

    async def test_search(self, db_session, sample_customer):
        """测试搜索"""
        repo = CustomerRepository(db_session)

        # 搜索名称
        results = await repo.search(sample_customer.name[:3])
        assert len(results) > 0

        # 搜索公司 ID
        results = await repo.search(str(sample_customer.company_id))
        assert len(results) > 0
