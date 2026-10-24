"""系统公告路由单元测试（缓存 + 降级）"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routes.system import get_system_updates


def parse_response_body(response):
    """解析 Sanic JSON 响应体为 dict"""
    body = response.body
    if isinstance(body, bytes):
        return json.loads(body)
    return body


@pytest.fixture
def mock_request():
    """模拟请求上下文（已认证用户）"""
    request = MagicMock()
    request.ctx = MagicMock()
    request.ctx.user = {"user_id": 1}
    return request


def make_cache_mock(cached=None, set_result=True):
    """构造 cache_service mock：get 返回 cached，set 记录调用"""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=cached)
    cache.set = AsyncMock(return_value=set_result)
    return cache


class TestGetSystemUpdates:
    """GET /api/v1/system/updates 测试"""

    @pytest.mark.asyncio
    async def test_returns_updates_from_client_and_caches(self, mock_request):
        """缓存未命中 → 拉取 GitHub 并写缓存"""
        cache = make_cache_mock(cached=None)
        updates = [
            {
                "deployed_at": "2026-10-20T03:00:00Z",
                "head_sha": "aaaaaaa",
                "status": "success",
                "commits": [
                    {
                        "sha": "2222222",
                        "message": "feat: x",
                        "author": "张三",
                        "date": "2026-10-19T01:00:00Z",
                    }
                ],
            }
        ]

        with (
            patch("app.routes.system.cache_service", cache),
            patch("app.routes.system.get_github_updates_client") as mock_get_client,
        ):
            client = MagicMock()
            client.get_recent_updates = AsyncMock(return_value=updates)
            mock_get_client.return_value = client

            response = await get_system_updates(mock_request)

        assert response.status == 200
        body = parse_response_body(response)
        assert body["code"] == 0
        assert body["data"]["updates"] == updates
        # 非空结果写入缓存（TTL 由 ttl_for 决定，未显式传）
        cache.set.assert_awaited_once_with("system_updates", updates)

    @pytest.mark.asyncio
    async def test_cache_hit_skips_github(self, mock_request):
        """缓存命中 → 直接返回，不请求 GitHub"""
        cached = [
            {
                "deployed_at": "2026-10-20T03:00:00Z",
                "head_sha": "aaaaaaa",
                "status": "success",
                "commits": [],
            }
        ]
        cache = make_cache_mock(cached=cached)

        with (
            patch("app.routes.system.cache_service", cache),
            patch("app.routes.system.get_github_updates_client") as mock_get_client,
        ):
            response = await get_system_updates(mock_request)

        assert response.status == 200
        body = parse_response_body(response)
        assert body["data"]["updates"] == cached
        mock_get_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_updates_not_cached(self, mock_request):
        """GitHub 不可达/限流（空结果）→ 返回空且不写缓存（下次可重试）"""
        cache = make_cache_mock(cached=None)

        with (
            patch("app.routes.system.cache_service", cache),
            patch("app.routes.system.get_github_updates_client") as mock_get_client,
        ):
            client = MagicMock()
            client.get_recent_updates = AsyncMock(return_value=[])
            mock_get_client.return_value = client

            response = await get_system_updates(mock_request)

        body = parse_response_body(response)
        assert body["code"] == 0
        assert body["data"]["updates"] == []
        cache.set.assert_not_awaited()
