"""行业类型服务单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.industry_type_service import IndustryTypeService
from app.models.industry_type import IndustryType


@pytest.fixture
def mock_db_session():
    """模拟数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def service(mock_db_session):
    """创建 IndustryTypeService 实例"""
    return IndustryTypeService(mock_db_session)


class TestIndustryTypeService_GetAll:
    """测试 get_all 方法"""

    @pytest.mark.asyncio
    async def test_returns_sorted_list(self, service, mock_db_session):
        """返回按 sort_order 升序排列的行业类型"""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [
            IndustryType(id=1, name="项目", sort_order=1),
            IndustryType(id=2, name="房产经纪", sort_order=2),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        result = await service.get_all()

        assert len(result) == 2
        assert result[0].name == "项目"
        assert result[1].name == "房产经纪"

    @pytest.mark.asyncio
    async def test_filters_deleted_records(self, service, mock_db_session):
        """过滤已删除的记录"""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        await service.get_all()

        # 验证 SQL 包含 deleted_at.is_(None) 过滤
        call_args = mock_db_session.execute.call_args
        stmt = call_args[0][0]
        assert "deleted_at" in str(stmt)


class TestIndustryTypeService_GetById:
    """测试 get_by_id 方法"""

    @pytest.mark.asyncio
    async def test_returns_industry_type(self, service, mock_db_session):
        """返回指定 ID 的行业类型"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = IndustryType(id=1, name="项目", sort_order=1)
        mock_db_session.execute.return_value = mock_result

        result = await service.get_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.name == "项目"

    @pytest.mark.asyncio
    async def test_returns_none_for_not_found(self, service, mock_db_session):
        """不存在的 ID 返回 None"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await service.get_by_id(999)

        assert result is None


class TestIndustryTypeService_Create:
    """测试 create 方法"""

    @pytest.mark.asyncio
    async def test_creates_industry_type(self, service, mock_db_session):
        """成功创建行业类型"""
        # Mock the name uniqueness check to return None (no existing record)
        mock_existing = MagicMock()
        mock_existing.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_existing
        mock_db_session.refresh = AsyncMock()

        result = await service.create("测试行业", 10)

        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()
        assert result.name == "测试行业"
        assert result.sort_order == 10


class TestIndustryTypeService_Update:
    """测试 update 方法"""

    @pytest.mark.asyncio
    async def test_updates_industry_type(self, service, mock_db_session):
        """成功更新行业类型"""
        # Mock get_by_id result (existing industry type)
        mock_get_result = MagicMock()
        mock_get_result.scalar_one_or_none.return_value = IndustryType(
            id=1, name="旧名称", sort_order=1
        )
        # Mock name uniqueness check (no existing record with new name)
        mock_check_result = MagicMock()
        mock_check_result.scalar_one_or_none.return_value = None

        # Set up execute to return different results based on call order
        mock_db_session.execute.side_effect = [mock_get_result, mock_check_result]
        mock_db_session.refresh = AsyncMock()

        result = await service.update(1, "新名称", 5)

        assert result is not None
        assert result.name == "新名称"
        assert result.sort_order == 5
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_none_for_not_found(self, service, mock_db_session):
        """不存在的 ID 返回 None"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await service.update(999, "新名称", 5)

        assert result is None


class TestIndustryTypeService_SoftDelete:
    """测试 soft_delete 方法"""

    @pytest.mark.asyncio
    async def test_soft_deletes_industry_type(self, service, mock_db_session):
        """成功软删除行业类型"""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        result = await service.soft_delete(1)

        assert result is True
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_false_for_not_found(self, service, mock_db_session):
        """不存在的 ID 返回 False"""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db_session.execute.return_value = mock_result

        result = await service.soft_delete(999)

        assert result is False
