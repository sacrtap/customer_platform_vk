"""定时同步配置接口单元测试（含权限校验）"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routes.sync_schedule import get_sync_schedule, update_sync_schedule


def parse_response_body(response):
    """解析 Sanic JSON 响应体为 dict"""
    body = response.body
    if isinstance(body, bytes):
        return json.loads(body)
    return body


@pytest.fixture
def mock_request():
    """模拟请求上下文（默认无权限，权限测试单独设置）"""
    request = MagicMock()
    request.ctx = MagicMock()
    request.ctx.db_session = AsyncMock()
    request.ctx.user = {"user_id": 1}
    request.json = {}
    request.app = MagicMock()
    request.app.ctx = MagicMock()
    request.app.ctx.async_session_maker = MagicMock()
    return request


@pytest.fixture
def mock_config():
    """模拟配置行"""
    config = MagicMock()
    config.task_name = "daily_sync"
    config.enabled = False
    config.sync_time = "01:00"
    config.sync_mode = "skip_existing"
    config.updated_at = None
    return config


def patch_permissions(permissions):
    """Mock 权限缓存返回指定权限集合"""

    def _decorator(func):
        return func

    # 直接 patch cache.permissions 模块的 get_permissions
    perm_mock = MagicMock()
    perm_mock.get_permissions = AsyncMock(return_value=set(permissions))
    return patch("app.cache.permissions.permission_cache", perm_mock)


def patch_scheduler(job=None):
    """Mock APScheduler（next_run_time）

    注意：`_config_dict` 内部是延迟 `from ..tasks.scheduler import get_scheduler`，
    因此必须 patch `app.tasks.scheduler.get_scheduler`。
    """
    scheduler = MagicMock()
    scheduler.get_job.return_value = job
    return patch("app.tasks.scheduler.get_scheduler", return_value=scheduler)


class TestGetSyncSchedule:
    """定时配置 GET 接口"""

    async def test_get_schedule(self, mock_request, mock_config):
        """测试获取配置（system:view 权限）"""
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_config
        mock_request.ctx.db_session.execute = AsyncMock(return_value=result)

        with patch_permissions({"system:view"}), patch_scheduler(job=None):
            response = await get_sync_schedule(mock_request)

        assert response.status == 200
        body = parse_response_body(response)
        assert body["code"] == 0
        data = body["data"]
        assert data["task_name"] == "daily_sync"
        assert data["enabled"] is False
        assert data["sync_time"] == "01:00"
        assert data["sync_mode"] == "skip_existing"
        assert data["next_run_time"] is None

    async def test_get_schedule_with_next_run(self, mock_request, mock_config):
        """测试返回 next_run_time"""
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_config
        mock_request.ctx.db_session.execute = AsyncMock(return_value=result)

        job = MagicMock()
        job.next_run_time = MagicMock()
        job.next_run_time.isoformat.return_value = "2026-09-18T01:00:00"

        with patch_permissions({"system:view"}), patch_scheduler(job=job):
            response = await get_sync_schedule(mock_request)

        body = parse_response_body(response)
        assert body["data"]["next_run_time"] == "2026-09-18T01:00:00"


class TestUpdateSyncSchedule:
    """定时配置 PUT 接口"""

    async def test_put_schedule_success(self, mock_request, mock_config):
        """测试更新配置（system:sync_schedule 权限）"""
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_config
        mock_request.ctx.db_session.execute = AsyncMock(return_value=result)
        mock_request.ctx.db_session.commit = AsyncMock()
        mock_request.ctx.db_session.refresh = AsyncMock()
        mock_request.json = {
            "enabled": True,
            "sync_time": "02:30",
            "sync_mode": "force_overwrite",
        }

        with (
            patch_permissions({"system:sync_schedule"}),
            patch_scheduler(job=None),
            patch("app.routes.sync_schedule._reschedule_job") as mock_reschedule,
        ):
            response = await update_sync_schedule(mock_request)

        assert response.status == 200
        body = parse_response_body(response)
        assert body["code"] == 0
        assert body["data"]["sync_time"] == "02:30"
        # 配置更新后动态调整调度
        mock_reschedule.assert_called_once_with(mock_request, True, "02:30")

    async def test_put_schedule_permission_denied(self, mock_request):
        """测试无 system:sync_schedule 权限 → 403"""
        with patch_permissions({"system:view"}):
            response = await update_sync_schedule(mock_request)

        assert response.status == 403
        body = parse_response_body(response)
        assert body["code"] == 40301  # ErrorCodes.FORBIDDEN

    async def test_put_schedule_invalid_time(self, mock_request, mock_config):
        """测试非法时间格式 → 400"""
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_config
        mock_request.ctx.db_session.execute = AsyncMock(return_value=result)
        mock_request.json = {"enabled": True, "sync_time": "25:99"}

        with patch_permissions({"system:sync_schedule"}):
            response = await update_sync_schedule(mock_request)

        assert response.status == 400
        body = parse_response_body(response)
        assert "HH:MM" in body["message"]

    async def test_put_schedule_invalid_mode(self, mock_request, mock_config):
        """测试非法同步模式 → 400"""
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_config
        mock_request.ctx.db_session.execute = AsyncMock(return_value=result)
        mock_request.json = {"enabled": True, "sync_mode": "bad_mode"}

        with patch_permissions({"system:sync_schedule"}):
            response = await update_sync_schedule(mock_request)

        assert response.status == 400
        body = parse_response_body(response)
        assert "同步模式" in body["message"]

    async def test_put_schedule_disabled_removes_job(self, mock_request, mock_config):
        """测试关闭定时同步（enabled=False）时仍调整调度"""
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_config
        mock_request.ctx.db_session.execute = AsyncMock(return_value=result)
        mock_request.ctx.db_session.commit = AsyncMock()
        mock_request.ctx.db_session.refresh = AsyncMock()
        mock_request.json = {"enabled": False}

        with (
            patch_permissions({"system:sync_schedule"}),
            patch_scheduler(job=None),
            patch("app.routes.sync_schedule._reschedule_job") as mock_reschedule,
        ):
            response = await update_sync_schedule(mock_request)

        assert response.status == 200
        # enabled=False 时同样触发调度调整（移除 job）
        mock_reschedule.assert_called_once_with(mock_request, False, "01:00")
