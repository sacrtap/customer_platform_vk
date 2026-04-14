"""客户群组模型单元测试"""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models.base import Base
from app.models.groups import CustomerGroup, CustomerGroupMember
from app.models.users import User
from app.models.customers import Customer

# 测试数据库配置
TEST_DATABASE_URL = "postgresql+asyncpg://localhost:5432/customer_platform_test"


@pytest.fixture(scope="function")
async def async_engine():
    """创建异步测试数据库引擎"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def async_session(async_engine):
    """创建异步数据库会话"""
    async_session_maker = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ==================== Test CustomerGroup Model ====================


class TestCustomerGroupModel:
    """客户群组模型测试"""

    async def test_customer_group_creation(self, async_session):
        """测试创建客户群组"""
        # 先创建用户
        user = User(
            username="test_user",
            password_hash="hashed_password",
            email="test@example.com",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        # 准备测试数据
        group_data = {
            "name": "VIP 客户群",
            "description": "高价值客户群体",
            "group_type": "dynamic",
            "filter_conditions": {"customer_level": "VIP", "min_balance": 10000},
            "created_by": user.id,
        }

        # 创建群组
        group = CustomerGroup(**group_data)
        async_session.add(group)
        await async_session.commit()
        await async_session.refresh(group)

        # 验证结果
        assert group.id is not None
        assert group.name == "VIP 客户群"
        assert group.description == "高价值客户群体"
        assert group.group_type == "dynamic"
        assert group.filter_conditions == {
            "customer_level": "VIP",
            "min_balance": 10000,
        }
        assert group.created_by == user.id
        assert group.created_at is not None

    async def test_customer_group_relationships(self, async_session):
        """测试客户群组关联关系"""
        # 创建用户
        user = User(
            username="test_user",
            password_hash="hashed_password",
            email="test@example.com",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        # 创建群组
        group = CustomerGroup(
            name="测试群组",
            group_type="static",
            created_by=user.id,
        )
        async_session.add(group)
        await async_session.commit()
        await async_session.refresh(group)

        # 验证 creator 关联
        assert group.creator is not None
        assert group.creator.id == user.id
        assert group.creator.username == "test_user"

        # 验证用户的 created_groups 关联 - 使用 select 显式查询
        from sqlalchemy import select

        result = await async_session.execute(
            select(CustomerGroup).where(CustomerGroup.created_by == user.id)
        )
        user_groups = result.scalars().all()
        assert len(user_groups) == 1
        assert user_groups[0].id == group.id


# ==================== Test CustomerGroupMember Model ====================


class TestCustomerGroupMemberModel:
    """群组成员模型测试"""

    async def test_customer_group_member_creation(self, async_session):
        """测试创建群组成员"""
        # 创建用户
        user = User(
            username="group_owner",
            password_hash="hashed_password",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        # 创建群组
        group = CustomerGroup(
            name="静态群组",
            group_type="static",
            created_by=user.id,
        )
        async_session.add(group)
        await async_session.commit()
        await async_session.refresh(group)

        # 创建客户
        customer = Customer(
            company_id="TEST001",
            name="测试客户公司",
            account_type="enterprise",
            business_type="retail",
            customer_level="VIP",
            manager_id=user.id,
        )
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # 创建群组成员关系
        member = CustomerGroupMember(group_id=group.id, customer_id=customer.id)
        async_session.add(member)
        await async_session.commit()
        await async_session.refresh(member)

        # 验证结果
        assert member.group_id == group.id
        assert member.customer_id == customer.id
        assert member.created_at is not None

    async def test_customer_group_member_relationships(self, async_session):
        """测试群组成员关联关系"""
        # 创建用户
        user = User(
            username="owner",
            password_hash="hashed_password",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        # 创建群组
        group = CustomerGroup(
            name="关联测试群组",
            group_type="static",
            created_by=user.id,
        )
        async_session.add(group)
        await async_session.commit()
        await async_session.refresh(group)

        # 创建客户
        customer = Customer(
            company_id="TEST002",
            name="关联测试客户",
            account_type="enterprise",
            manager_id=user.id,
        )
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # 创建成员关系
        member = CustomerGroupMember(group_id=group.id, customer_id=customer.id)
        async_session.add(member)
        await async_session.commit()
        await async_session.refresh(member)

        # 验证 group 关联
        assert member.group is not None
        assert member.group.id == group.id
        assert member.group.name == "关联测试群组"

        # 验证 customer 关联
        assert member.customer is not None
        assert member.customer.id == customer.id
        assert member.customer.name == "关联测试客户"

        # 验证群组的 members 关联 - 使用 select 显式查询
        from sqlalchemy import select

        result = await async_session.execute(
            select(CustomerGroupMember).where(CustomerGroupMember.group_id == group.id)
        )
        group_members = result.scalars().all()
        assert len(group_members) == 1
        assert group_members[0].customer_id == customer.id

        # 验证客户的 group_memberships 关联
        result = await async_session.execute(
            select(CustomerGroupMember).where(CustomerGroupMember.customer_id == customer.id)
        )
        customer_memberships = result.scalars().all()
        assert len(customer_memberships) == 1
        assert customer_memberships[0].group_id == group.id

    async def test_customer_group_cascade_delete(self, async_session):
        """测试删除群组时级联删除成员"""
        # 创建用户
        user = User(
            username="delete_test_user",
            password_hash="hashed_password",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        # 创建群组
        group = CustomerGroup(
            name="级联删除测试群组",
            group_type="static",
            created_by=user.id,
        )
        async_session.add(group)
        await async_session.commit()
        await async_session.refresh(group)

        # 创建客户
        customer = Customer(
            company_id="TEST003",
            name="级联测试客户",
            account_type="enterprise",
            manager_id=user.id,
        )
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        # 创建成员关系
        member = CustomerGroupMember(group_id=group.id, customer_id=customer.id)
        async_session.add(member)
        await async_session.commit()

        # 删除群组
        await async_session.delete(group)
        await async_session.commit()

        # 验证成员关系已被级联删除
        from sqlalchemy import select

        result = await async_session.execute(
            select(CustomerGroupMember).where(CustomerGroupMember.group_id == group.id)
        )
        remaining_members = result.scalars().all()
        assert len(remaining_members) == 0
