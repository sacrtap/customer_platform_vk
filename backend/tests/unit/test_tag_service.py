"""Tag Service 单元测试"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from app.services.tags import TagService
from app.models.tags import Tag, CustomerTag, ProfileTag


# ==================== Fixtures ====================


@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def tag_service(mock_db_session):
    """创建 TagService 实例"""
    return TagService(db_session=mock_db_session)


# ==================== Test TagService - Create Tag ====================


class TestTagService_CreateTag:
    """创建标签测试"""

    @pytest.mark.asyncio
    async def test_create_tag_success(self, tag_service, mock_db_session):
        """测试创建标签成功"""
        # Mock 无重复标签
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        tag_data = {
            "name": "高价值客户",
            "type": "customer",
            "category": "价值等级",
        }

        result = await tag_service.create_tag(tag_data, created_by=1)

        assert result is not None
        assert isinstance(result, Tag)
        assert result.name == "高价值客户"
        assert result.type == "customer"
        assert result.category == "价值等级"
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_tag_duplicate_error(self, tag_service, mock_db_session):
        """测试创建标签 - 名称重复"""
        existing_tag = Tag(id=1, name="高价值客户", type="customer")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_tag
        mock_db_session.execute.return_value = mock_result

        tag_data = {
            "name": "高价值客户",
            "type": "customer",
        }

        with pytest.raises(ValueError, match="已存在"):
            await tag_service.create_tag(tag_data, created_by=1)

        mock_db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_tag_same_name_different_type(self, tag_service, mock_db_session):
        """测试创建标签 - 同名不同类型允许创建"""
        # Mock 查询返回不同类型标签
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        tag_data = {
            "name": "高价值",
            "type": "profile",  # 不同类型
        }

        result = await tag_service.create_tag(tag_data, created_by=1)

        assert result is not None
        assert result.name == "高价值"
        assert result.type == "profile"


# ==================== Test TagService - Update Tag ====================


class TestTagService_UpdateTag:
    """更新标签测试"""

    @pytest.mark.asyncio
    async def test_update_tag_success(self, tag_service, mock_db_session):
        """测试更新标签成功"""
        existing_tag = Tag(
            id=1,
            name="原名称",
            type="customer",
            category="原分类",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_tag
        mock_db_session.execute.return_value = mock_result

        update_data = {
            "name": "新名称",
            "category": "新分类",
        }

        result = await tag_service.update_tag(1, update_data)

        assert result is not None
        assert result.name == "新名称"
        assert result.category == "新分类"
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_tag_partial(self, tag_service, mock_db_session):
        """测试部分更新标签"""
        existing_tag = Tag(id=1, name="原名称", type="customer", category="原分类")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_tag
        mock_db_session.execute.return_value = mock_result

        update_data = {"name": "新名称"}

        result = await tag_service.update_tag(1, update_data)

        assert result.name == "新名称"
        assert result.category == "原分类"  # 未改变

    @pytest.mark.asyncio
    async def test_update_tag_not_found(self, tag_service, mock_db_session):
        """测试更新不存在的标签"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await tag_service.update_tag(999, {"name": "新名称"})

        assert result is None
        mock_db_session.commit.assert_not_called()


# ==================== Test TagService - Delete Tag ====================


class TestTagService_DeleteTag:
    """删除标签测试"""

    @pytest.mark.asyncio
    async def test_delete_tag_success(self, tag_service, mock_db_session):
        """测试删除标签成功（软删除）"""
        existing_tag = Tag(id=1, name="测试标签", type="customer", deleted_at=None)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_tag
        mock_db_session.execute.return_value = mock_result

        result = await tag_service.delete_tag(1)

        assert result is True
        assert existing_tag.deleted_at is not None
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_delete_tag_not_found(self, tag_service, mock_db_session):
        """测试删除不存在的标签"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await tag_service.delete_tag(999)

        assert result is False


# ==================== Test TagService - Get Tags ====================


class TestTagService_GetTags:
    """获取标签列表测试"""

    @pytest.mark.asyncio
    async def test_get_all_tags_no_filter(self, tag_service, mock_db_session):
        """测试获取所有标签"""
        tags = [
            Tag(id=1, name="标签1", type="customer"),
            Tag(id=2, name="标签2", type="profile"),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = tags
        mock_result.scalar.return_value = 2
        mock_db_session.execute.return_value = mock_result

        result_tags, total = await tag_service.get_all_tags(page=1, page_size=20)

        assert len(result_tags) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_all_tags_filter_by_type(self, tag_service, mock_db_session):
        """测试按类型筛选标签"""
        tags = [Tag(id=1, name="客户标签", type="customer")]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = tags
        mock_result.scalar.return_value = 1
        mock_db_session.execute.return_value = mock_result

        result_tags, total = await tag_service.get_all_tags(tag_type="customer")

        assert len(result_tags) == 1
        assert result_tags[0].type == "customer"

    @pytest.mark.asyncio
    async def test_get_all_tags_filter_by_category(self, tag_service, mock_db_session):
        """测试按分类筛选标签"""
        tags = [Tag(id=1, name="高价值", type="customer", category="价值等级")]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = tags
        mock_result.scalar.return_value = 1
        mock_db_session.execute.return_value = mock_result

        result_tags, total = await tag_service.get_all_tags(category="价值等级")

        assert len(result_tags) == 1
        assert result_tags[0].category == "价值等级"

    @pytest.mark.asyncio
    async def test_get_all_tags_empty(self, tag_service, mock_db_session):
        """测试获取空标签列表"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.scalar.return_value = 0
        mock_db_session.execute.return_value = mock_result

        result_tags, total = await tag_service.get_all_tags()

        assert len(result_tags) == 0
        assert total == 0


# ==================== Test TagService - Get Tag By ID ====================


class TestTagService_GetTagById:
    """根据 ID 获取标签测试"""

    @pytest.mark.asyncio
    async def test_get_tag_by_id_success(self, tag_service, mock_db_session):
        """测试获取存在的标签"""
        tag = Tag(id=1, name="测试标签", type="customer")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tag
        mock_db_session.execute.return_value = mock_result

        result = await tag_service.get_tag_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.name == "测试标签"

    @pytest.mark.asyncio
    async def test_get_tag_by_id_not_found(self, tag_service, mock_db_session):
        """测试获取不存在的标签"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await tag_service.get_tag_by_id(999)

        assert result is None


# ==================== Test TagService - Tag Usage Count ====================


class TestTagService_TagUsageCount:
    """标签使用次数测试"""

    @pytest.mark.asyncio
    async def test_get_tag_usage_count(self, tag_service, mock_db_session):
        """测试获取标签使用次数"""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_db_session.execute.return_value = mock_result

        result = await tag_service.get_tag_usage_count(1)

        assert result["customer_count"] == 5
        assert result["profile_count"] == 5  # mock 返回相同值

    @pytest.mark.asyncio
    async def test_get_tag_usage_count_zero(self, tag_service, mock_db_session):
        """测试标签未被使用"""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_db_session.execute.return_value = mock_result

        result = await tag_service.get_tag_usage_count(1)

        assert result["customer_count"] == 0
        assert result["profile_count"] == 0


# ==================== Test TagService - Get Tag By Name And Type ====================


class TestTagService_GetTagByNameAndType:
    """根据名称和类型获取标签测试"""

    @pytest.mark.asyncio
    async def test_get_tag_by_name_and_type_found(self, tag_service, mock_db_session):
        """测试找到标签"""
        tag = Tag(id=1, name="高价值客户", type="customer")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = tag
        mock_db_session.execute.return_value = mock_result

        result = await tag_service.get_tag_by_name_and_type("高价值客户", "customer")

        assert result is not None
        assert result.name == "高价值客户"
        assert result.type == "customer"

    @pytest.mark.asyncio
    async def test_get_tag_by_name_and_type_not_found(self, tag_service, mock_db_session):
        """测试未找到标签"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await tag_service.get_tag_by_name_and_type("不存在", "customer")

        assert result is None
