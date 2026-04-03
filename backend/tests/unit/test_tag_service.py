"""Tag Service 单元测试"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from app.services.tags import TagService
from app.models.tags import Tag, CustomerTag, ProfileTag
from app.models.customers import Customer, CustomerProfile


# ==================== Fixtures ====================


@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def tag_service(mock_db_session):
    """创建 TagService 实例"""
    return TagService(db_session=mock_db_session)


# ==================== Test Create Tag ====================


class TestTagService_CreateTag:
    """创建标签测试"""

    @pytest.mark.asyncio
    async def test_create_tag_success(self, tag_service, mock_db_session):
        """测试创建标签成功"""
        # 准备测试数据
        tag_data = {
            "name": "VIP 客户",
            "type": "customer",
            "category": "等级",
        }
        created_by = 1

        # Mock 数据库添加和刷新
        mock_tag = Tag(
            id=1,
            name="VIP 客户",
            type="customer",
            category="等级",
            created_by=created_by,
            created_at=datetime.utcnow(),
        )
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock(side_effect=lambda x: setattr(x, "id", 1))

        # 执行测试
        result = await tag_service.create_tag(tag_data, created_by)

        # 验证结果
        assert result is not None
        assert isinstance(result, Tag)
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_tag_duplicate_name(self, tag_service, mock_db_session):
        """测试创建重复名称的标签"""
        # 准备测试数据
        tag_data = {
            "name": "VIP 客户",
            "type": "customer",
            "category": "等级",
        }
        created_by = 1

        # Mock 数据库添加
        mock_tag = Tag(
            id=1,
            name="VIP 客户",
            type="customer",
            category="等级",
            created_by=created_by,
        )
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock(side_effect=lambda x: setattr(x, "id", 1))

        # 执行测试（当前实现不检查重复，直接创建）
        result = await tag_service.create_tag(tag_data, created_by)

        # 验证结果（当前实现会成功创建）
        assert result is not None
        assert isinstance(result, Tag)
        mock_db_session.add.assert_called_once()


# ==================== Test Customer Tag Operations ====================


class TestTagService_CustomerTagOperations:
    """客户标签操作测试"""

    @pytest.mark.asyncio
    async def test_add_customer_tag_success(self, tag_service, mock_db_session):
        """测试给客户添加标签成功"""
        customer_id = 1
        tag_id = 1

        # Mock 客户存在
        mock_customer_result = MagicMock()
        mock_customer_result.scalar_one_or_none.return_value = Customer(
            id=customer_id, name="Test Customer"
        )
        mock_db_session.execute = AsyncMock(return_value=mock_customer_result)

        # Mock 标签存在
        mock_tag_result = MagicMock()
        mock_tag_result.scalar_one_or_none.return_value = Tag(
            id=tag_id, name="VIP", type="customer"
        )

        # Mock 检查现有关系（不存在）
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None

        # Mock 添加和提交
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        # 设置 execute 的 side_effect 来返回不同的 mock 结果
        call_count = {"count": 0}

        async def mock_execute_side_effect(query):
            call_count["count"] += 1
            if call_count["count"] == 1:
                # 第一次调用：检查客户
                return mock_customer_result
            elif call_count["count"] == 2:
                # 第二次调用：检查标签
                return mock_tag_result
            elif call_count["count"] == 3:
                # 第三次调用：检查现有关系
                return mock_existing_result
            return mock_existing_result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

        # 执行测试
        result = await tag_service.add_customer_tag(customer_id, tag_id)

        # 验证结果
        assert result is True
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_customer_tag_success(self, tag_service, mock_db_session):
        """测试移除客户标签成功"""
        customer_id = 1
        tag_id = 1

        # Mock 现有的 CustomerTag 关系
        mock_customer_tag = CustomerTag(
            customer_id=customer_id,
            tag_id=tag_id,
            created_at=datetime.utcnow(),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_customer_tag
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()

        # 执行测试
        result = await tag_service.remove_customer_tag(customer_id, tag_id)

        # 验证结果
        assert result is True
        assert mock_customer_tag.deleted_at is not None
        mock_db_session.commit.assert_called_once()


# ==================== Test Profile Tag Operations ====================


class TestTagService_ProfileTagOperations:
    """画像标签操作测试"""

    @pytest.mark.asyncio
    async def test_add_profile_tag_success(self, tag_service, mock_db_session):
        """测试给画像添加标签成功"""
        profile_id = 1
        tag_id = 1

        # Mock 画像存在
        mock_profile_result = MagicMock()
        mock_profile_result.scalar_one_or_none.return_value = CustomerProfile(
            id=profile_id, customer_id=profile_id
        )

        # Mock 标签存在
        mock_tag_result = MagicMock()
        mock_tag_result.scalar_one_or_none.return_value = Tag(
            id=tag_id, name="VIP", type="profile"
        )

        # Mock 检查现有关系（不存在）
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None

        # Mock 添加和提交
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        # 设置 execute 的 side_effect
        call_count = {"count": 0}

        async def mock_execute_side_effect(query):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return mock_profile_result
            elif call_count["count"] == 2:
                return mock_tag_result
            elif call_count["count"] == 3:
                return mock_existing_result
            return mock_existing_result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

        # 执行测试
        result = await tag_service.add_profile_tag(profile_id, tag_id)

        # 验证结果
        assert result is True
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_profile_tag_success(self, tag_service, mock_db_session):
        """测试移除画像标签成功"""
        profile_id = 1
        tag_id = 1

        # Mock 现有的 ProfileTag 关系
        mock_profile_tag = ProfileTag(
            profile_id=profile_id,
            tag_id=tag_id,
            created_at=datetime.utcnow(),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_profile_tag
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()

        # 执行测试
        result = await tag_service.remove_profile_tag(profile_id, tag_id)

        # 验证结果
        assert result is True
        assert mock_profile_tag.deleted_at is not None
        mock_db_session.commit.assert_called_once()


# ==================== Test Batch Operations ====================


class TestTagService_BatchOperations:
    """批量操作测试"""

    @pytest.mark.asyncio
    async def test_batch_add_customer_tags_success(self, tag_service, mock_db_session):
        """测试批量给客户添加标签成功"""
        customer_ids = [1, 2]
        tag_ids = [1, 2]

        # Mock 有效客户
        mock_customers_result = MagicMock()
        mock_customers_result.scalars.return_value.all.return_value = [1, 2]

        # Mock 有效标签
        mock_tags_result = MagicMock()
        mock_tags_result.scalars.return_value.all.return_value = [1, 2]

        # Mock 现有关系（无）
        mock_existing_result = MagicMock()
        mock_existing_result.all.return_value = []

        # Mock 添加和提交
        mock_db_session.add_all = MagicMock()
        mock_db_session.commit = AsyncMock()

        # 设置 execute 的 side_effect
        call_count = {"count": 0}

        async def mock_execute_side_effect(query):
            call_count["count"] += 1
            if call_count["count"] == 1:
                return mock_customers_result
            elif call_count["count"] == 2:
                return mock_tags_result
            elif call_count["count"] == 3:
                return mock_existing_result
            return mock_existing_result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute_side_effect)

        # 执行测试
        success_count, error_count = await tag_service.batch_add_customer_tags(
            customer_ids, tag_ids
        )

        # 验证结果（4 个新标签关系：2 个客户 x 2 个标签）
        assert success_count == 4
        assert error_count == 0
        mock_db_session.add_all.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_remove_customer_tags_success(
        self, tag_service, mock_db_session
    ):
        """测试批量移除客户标签成功"""
        customer_ids = [1, 2]
        tag_ids = [1, 2]

        # Mock 现有的 CustomerTag 关系
        mock_tags = [
            CustomerTag(customer_id=1, tag_id=1, created_at=datetime.utcnow()),
            CustomerTag(customer_id=2, tag_id=2, created_at=datetime.utcnow()),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_tags
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.commit = AsyncMock()

        # 执行测试
        removed_count = await tag_service.batch_remove_customer_tags(
            customer_ids, tag_ids
        )

        # 验证结果
        assert removed_count == 2
        for tag in mock_tags:
            assert tag.deleted_at is not None
        mock_db_session.commit.assert_called_once()
