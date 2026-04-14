"""DictService 单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.dict_service import DictService
from app.models.industry_type import IndustryType


# ==================== Fixtures ====================


@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def dict_service(mock_db_session):
    """创建 DictService 实例"""
    return DictService(mock_db_session)


# ==================== Test Get Industry Types ====================


class TestDictService_GetIndustryTypes:
    """获取行业类型测试"""

    @pytest.mark.asyncio
    async def test_get_industry_types_returns_sorted_list(self, dict_service, mock_db_session):
        """测试获取行业类型按 sort_order 升序返回"""
        types = [
            IndustryType(id=2, name="房产经纪", sort_order=2),
            IndustryType(id=1, name="项目", sort_order=1),
        ]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = types
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await dict_service.get_industry_types()

        assert len(result) == 2
        assert result[0].name == "房产经纪"
        assert result[0].sort_order == 2
        assert result[1].name == "项目"
        assert result[1].sort_order == 1
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_industry_types_empty_result(self, dict_service, mock_db_session):
        """测试空结果返回空列表"""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await dict_service.get_industry_types()

        assert result == []
        assert len(result) == 0
