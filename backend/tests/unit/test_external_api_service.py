"""External API Service 单元测试"""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from app.services.external_api import ExternalAPIClient


# ==================== Fixtures ====================


@pytest.fixture
def mock_api_settings():
    """Mock API 配置"""
    with patch("app.services.external_api.settings") as mock_settings:
        mock_settings.external_api_base_url = "https://api.example.com/v1"
        mock_settings.external_api_token = "test-token-123"
        yield mock_settings


@pytest.fixture
def api_client(mock_api_settings):
    """创建 ExternalAPIClient 实例"""
    return ExternalAPIClient()


# ==================== Test ExternalAPIClient - Init ====================


class TestExternalAPIClient_Init:
    """初始化测试"""

    def test_init_with_settings(self, mock_api_settings):
        """测试初始化配置正确"""
        client = ExternalAPIClient()

        assert client.base_url == "https://api.example.com/v1"
        assert client.token == "test-token-123"
        assert client.timeout == 30.0


# ==================== Test ExternalAPIClient - Headers ====================


class TestExternalAPIClient_Headers:
    """请求头测试"""

    @pytest.mark.asyncio
    async def test_get_headers(self, api_client, mock_api_settings):
        """测试获取请求头"""
        headers = await api_client._get_headers()

        assert headers["Authorization"] == "Bearer test-token-123"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"


# ==================== Test ExternalAPIClient - Get Daily Usage ====================


class TestExternalAPIClient_GetDailyUsage:
    """获取每日用量测试"""

    @pytest.mark.asyncio
    async def test_get_daily_usage_success(self, api_client, mock_api_settings):
        """测试获取用量数据成功"""
        mock_response_data = {
            "data": {
                "total_usage": 1000,
                "device_breakdown": {"camera": 600, "sensor": 400},
            }
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await api_client.get_daily_usage(
                customer_id=100,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
            )

        assert result is not None
        assert result["total_usage"] == 1000
        assert result["device_breakdown"]["camera"] == 600

    @pytest.mark.asyncio
    async def test_get_daily_usage_http_error(self, api_client, mock_api_settings):
        """测试获取用量数据 - HTTP 错误"""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await api_client.get_daily_usage(
                customer_id=100,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
            )

        # 应该返回 None（错误处理）
        assert result is None

    @pytest.mark.asyncio
    async def test_get_daily_usage_generic_error(self, api_client, mock_api_settings):
        """测试获取用量数据 - 其他异常"""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Unknown error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await api_client.get_daily_usage(
                customer_id=100,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
            )

        assert result is None


# ==================== Test ExternalAPIClient - Get Customer Info ====================


class TestExternalAPIClient_GetCustomerInfo:
    """获取客户信息测试"""

    @pytest.mark.asyncio
    async def test_get_customer_info_success(self, api_client, mock_api_settings):
        """测试获取客户信息成功"""
        mock_response_data = {
            "data": {
                "company_id": 100,
                "name": "测试公司",
                "industry": "房产经纪",
            }
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await api_client.get_customer_info(customer_id=100)

        assert result is not None
        assert result["company_id"] == 100
        assert result["name"] == "测试公司"

    @pytest.mark.asyncio
    async def test_get_customer_info_not_found(self, api_client, mock_api_settings):
        """测试获取客户信息 - 404"""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await api_client.get_customer_info(customer_id=999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_customer_info_http_error(self, api_client, mock_api_settings):
        """测试获取客户信息 - HTTP 错误"""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Server error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await api_client.get_customer_info(customer_id=100)

        assert result is None


# ==================== Test ExternalAPIClient - Sync Customer Data ====================


class TestExternalAPIClient_SyncCustomerData:
    """同步客户数据测试"""

    @pytest.mark.asyncio
    async def test_sync_customer_data_success(self, api_client, mock_api_settings):
        """测试同步客户数据成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await api_client.sync_customer_data(customer_id=100)

        assert result is True

    @pytest.mark.asyncio
    async def test_sync_customer_data_failure(self, api_client, mock_api_settings):
        """测试同步客户数据失败"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("Sync failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await api_client.sync_customer_data(customer_id=100)

        assert result is False


# ==================== Test ExternalAPIClient - Get Usage Statistics ====================


class TestExternalAPIClient_GetUsageStatistics:
    """获取用量统计测试"""

    @pytest.mark.asyncio
    async def test_get_usage_statistics_success(self, api_client, mock_api_settings):
        """测试获取用量统计成功"""
        mock_response_data = {
            "data": {
                "total_usage": 5000,
                "avg_daily_usage": 161,
            }
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await api_client.get_usage_statistics(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
            )

        assert result is not None
        assert result["total_usage"] == 5000

    @pytest.mark.asyncio
    async def test_get_usage_statistics_http_error(self, api_client, mock_api_settings):
        """测试获取用量统计 - HTTP 错误"""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Stats error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await api_client.get_usage_statistics(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
            )

        assert result is None
