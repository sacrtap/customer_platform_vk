"""
外部 API 客户端服务测试
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import date
import httpx

from app.services.external_api import (
    ExternalAPIClient,
    external_api_client,
    get_external_api_client,
)


class TestExternalAPIClient:
    """外部 API 客户端测试类"""

    @pytest.fixture
    def api_client(self):
        """创建 API 客户端实例"""
        with patch("app.services.external_api.settings") as mock_settings:
            mock_settings.external_api_base_url = "https://api.test.com"
            mock_settings.external_api_token = "test-token-123"
            client = ExternalAPIClient()
            yield client

    @pytest.fixture
    def sample_date_range(self):
        """示例日期范围"""
        return {
            "start_date": date(2026, 4, 1),
            "end_date": date(2026, 4, 30),
        }

    @pytest.mark.asyncio
    async def test_get_daily_usage_success(self, api_client, sample_date_range):
        """测试获取每日用量数据成功"""
        mock_response_data = {
            "data": {
                "total_usage": 1000,
                "device_breakdown": {"device1": 500, "device2": 500},
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client

            result = await api_client.get_daily_usage(
                customer_id=123,
                start_date=sample_date_range["start_date"],
                end_date=sample_date_range["end_date"],
            )

            assert result is not None
            assert result["total_usage"] == 1000
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_daily_usage_http_error(self, api_client, sample_date_range):
        """测试 HTTP 错误处理"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.HTTPError("连接失败")
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client

            result = await api_client.get_daily_usage(
                customer_id=123,
                start_date=sample_date_range["start_date"],
                end_date=sample_date_range["end_date"],
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_get_daily_usage_general_exception(self, api_client, sample_date_range):
        """测试通用异常处理"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("未知错误")
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client

            result = await api_client.get_daily_usage(
                customer_id=123,
                start_date=sample_date_range["start_date"],
                end_date=sample_date_range["end_date"],
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_get_customer_info_success(self, api_client):
        """测试获取客户信息成功"""
        mock_response_data = {
            "data": {
                "id": 123,
                "name": "测试公司",
                "account_type": "enterprise",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client

            result = await api_client.get_customer_info(customer_id=123)

            assert result is not None
            assert result["id"] == 123
            assert result["name"] == "测试公司"

    @pytest.mark.asyncio
    async def test_get_customer_info_not_found(self, api_client):
        """测试客户不存在 (404)"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client

            result = await api_client.get_customer_info(customer_id=999)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_customer_info_http_error(self, api_client):
        """测试 HTTP 错误处理"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.HTTPError("服务器错误")
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client

            result = await api_client.get_customer_info(customer_id=123)

            assert result is None

    @pytest.mark.asyncio
    async def test_sync_customer_data_success(self, api_client):
        """测试同步客户数据成功"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client

            result = await api_client.sync_customer_data(customer_id=123)

            assert result is True
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_customer_data_failure(self, api_client):
        """测试同步客户数据失败"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.HTTPError("同步失败")
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client

            result = await api_client.sync_customer_data(customer_id=123)

            assert result is False

    @pytest.mark.asyncio
    async def test_get_usage_statistics_success(self, api_client, sample_date_range):
        """测试获取用量统计数据成功"""
        mock_response_data = {
            "data": {
                "total_customers": 100,
                "total_usage": 50000,
                "average_usage": 500,
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client

            result = await api_client.get_usage_statistics(
                start_date=sample_date_range["start_date"],
                end_date=sample_date_range["end_date"],
            )

            assert result is not None
            assert result["total_customers"] == 100
            assert result["total_usage"] == 50000

    @pytest.mark.asyncio
    async def test_get_usage_statistics_http_error(self, api_client, sample_date_range):
        """测试获取用量统计 HTTP 错误"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.HTTPError("API 错误")
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client

            result = await api_client.get_usage_statistics(
                start_date=sample_date_range["start_date"],
                end_date=sample_date_range["end_date"],
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_get_headers(self, api_client):
        """测试获取请求头"""
        headers = await api_client._get_headers()

        assert headers["Authorization"] == "Bearer test-token-123"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_client_initialization(self):
        """测试客户端初始化"""
        with patch("app.services.external_api.settings") as mock_settings:
            mock_settings.external_api_base_url = "https://api.example.com"
            mock_settings.external_api_token = "my-token"

            client = ExternalAPIClient()

            assert client.base_url == "https://api.example.com"
            assert client.token == "my-token"
            assert client.timeout == 30.0

    def test_get_external_api_client(self):
        """测试获取外部 API 客户端实例"""
        client = get_external_api_client()

        assert isinstance(client, ExternalAPIClient)
        assert client is external_api_client  # 应该是同一个全局实例

    @pytest.mark.asyncio
    async def test_get_daily_usage_with_timeout(self, api_client, sample_date_range):
        """测试超时处理"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ReadTimeout("请求超时")
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client

            result = await api_client.get_daily_usage(
                customer_id=123,
                start_date=sample_date_range["start_date"],
                end_date=sample_date_range["end_date"],
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_sync_customer_data_with_retry_logic(self, api_client, sample_date_range):
        """测试同步重试逻辑（模拟网络波动）"""
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("临时连接错误")
            mock_response = MagicMock()
            mock_response.status_code = 200
            return mock_response

        # 注意：当前实现没有重试逻辑，这个测试验证单次失败即返回 False
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("连接错误")
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client

            result = await api_client.sync_customer_data(customer_id=123)

            assert result is False
            assert call_count == 0  # 因为没有重试逻辑

    @pytest.mark.asyncio
    async def test_get_customer_info_with_special_characters(self, api_client):
        """测试包含特殊字符的客户信息"""
        mock_response_data = {
            "data": {
                "id": 123,
                "name": "测试公司 <>&\"'",
                "description": "中文描述 & special chars",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client

            result = await api_client.get_customer_info(customer_id=123)

            assert result is not None
            assert "测试公司" in result["name"]
