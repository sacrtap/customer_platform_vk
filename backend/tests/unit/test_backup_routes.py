"""数据备份接口单元测试（含权限校验与恢复日期二次校验）"""

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routes.backup import (
    download_backup,
    get_backup_record,
    get_backup_schedule,
    list_backup_records,
    perform_backup,
    restore_backup,
    update_backup_schedule,
)


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
    """模拟备份配置行"""
    config = MagicMock()
    config.task_name = "daily_backup"
    config.enabled = False
    config.backup_time = "02:00"
    config.updated_at = None
    return config


def patch_permissions(permissions):
    """Mock 权限缓存返回指定权限集合"""
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


def patch_get_or_create(config):
    """Mock BackupService.get_or_create_schedule_config"""
    return patch(
        "app.routes.backup.BackupService.get_or_create_schedule_config",
        new=AsyncMock(return_value=config),
    )


class TestGetBackupSchedule:
    """定时配置 GET 接口"""

    async def test_get_schedule(self, mock_request, mock_config):
        """测试获取配置（system:view 权限）"""
        with (
            patch_permissions({"system:view"}),
            patch_scheduler(job=None),
            patch_get_or_create(mock_config),
        ):
            response = await get_backup_schedule(mock_request)

        assert response.status == 200
        body = parse_response_body(response)
        assert body["code"] == 0
        data = body["data"]
        assert data["task_name"] == "daily_backup"
        assert data["enabled"] is False
        assert data["backup_time"] == "02:00"
        assert data["next_run_time"] is None

    async def test_get_schedule_with_next_run(self, mock_request, mock_config):
        """测试返回 next_run_time"""
        job = MagicMock()
        job.next_run_time = MagicMock()
        job.next_run_time.isoformat.return_value = "2026-10-27T02:00:00"

        with (
            patch_permissions({"system:view"}),
            patch_scheduler(job=job),
            patch_get_or_create(mock_config),
        ):
            response = await get_backup_schedule(mock_request)

        body = parse_response_body(response)
        assert body["data"]["next_run_time"] == "2026-10-27T02:00:00"

    async def test_get_schedule_permission_denied(self, mock_request):
        """测试无 system:view 权限 → 403"""
        with patch_permissions(set()):
            response = await get_backup_schedule(mock_request)

        assert response.status == 403
        body = parse_response_body(response)
        assert body["code"] == 40301  # ErrorCodes.FORBIDDEN


class TestUpdateBackupSchedule:
    """定时配置 PUT 接口"""

    async def test_put_schedule_success(self, mock_request, mock_config):
        """测试更新配置并动态调整调度"""
        with (
            patch_permissions({"system:database_backup"}),
            patch_scheduler(job=None),
            patch_get_or_create(mock_config),
            patch("app.routes.backup._reschedule_job") as mock_reschedule,
        ):
            mock_request.json = {"enabled": True, "backup_time": "03:30"}
            response = await update_backup_schedule(mock_request)

        assert response.status == 200
        body = parse_response_body(response)
        assert body["code"] == 0
        assert body["data"]["backup_time"] == "03:30"
        mock_reschedule.assert_called_once_with(mock_request, True, "03:30")

    async def test_put_schedule_permission_denied(self, mock_request):
        """测试无 system:database_backup 权限 → 403"""
        with patch_permissions({"system:view"}):
            response = await update_backup_schedule(mock_request)

        assert response.status == 403
        body = parse_response_body(response)
        assert body["code"] == 40301

    async def test_put_schedule_invalid_time(self, mock_request, mock_config):
        """测试非法时间格式 → 400"""
        with (
            patch_permissions({"system:database_backup"}),
            patch_get_or_create(mock_config),
        ):
            mock_request.json = {"enabled": True, "backup_time": "25:99"}
            response = await update_backup_schedule(mock_request)

        assert response.status == 400
        body = parse_response_body(response)
        assert "HH:MM" in body["message"]

    async def test_put_schedule_invalid_enabled_type(self, mock_request, mock_config):
        """测试 enabled 非布尔 → 400"""
        with (
            patch_permissions({"system:database_backup"}),
            patch_get_or_create(mock_config),
        ):
            mock_request.json = {"enabled": "yes"}
            response = await update_backup_schedule(mock_request)

        assert response.status == 400
        body = parse_response_body(response)
        assert "布尔值" in body["message"]

    async def test_put_schedule_non_dict_body(self, mock_request, mock_config):
        """测试请求体非 JSON 对象 → 400"""
        with (
            patch_permissions({"system:database_backup"}),
            patch_get_or_create(mock_config),
        ):
            mock_request.json = ["not", "a", "dict"]
            response = await update_backup_schedule(mock_request)

        assert response.status == 400


class TestListBackupRecords:
    """记录列表接口"""

    async def test_list_records(self, mock_request):
        """测试分页列表结构"""
        service_result = {
            "list": [{"id": 1, "task_type": "daily_backup", "status": "success"}],
            "pagination": {"total": 1, "page": 1, "page_size": 20},
        }
        with (
            patch_permissions({"system:view"}),
            patch(
                "app.routes.backup.BackupService.list_records",
                new=AsyncMock(return_value=service_result),
            ),
        ):
            mock_request.args = {}
            response = await list_backup_records(mock_request)

        assert response.status == 200
        body = parse_response_body(response)
        assert body["code"] == 0
        assert body["data"]["pagination"]["total"] == 1

    async def test_list_records_permission_denied(self, mock_request):
        """测试无 system:view 权限 → 403"""
        with patch_permissions(set()):
            response = await list_backup_records(mock_request)

        assert response.status == 403


class TestGetBackupRecord:
    """单条记录接口"""

    async def test_get_record(self, mock_request):
        """测试单条记录返回"""
        from app.models.backup import BackupRecord

        record = BackupRecord(
            id=7,
            task_type="manual_backup",
            status="success",
            file_path="backup_20261020_020000.dump",
            backup_date=date(2026, 10, 20),
        )
        with (
            patch_permissions({"system:view"}),
            patch(
                "app.routes.backup.BackupService.get_record",
                new=AsyncMock(return_value=record),
            ),
        ):
            response = await get_backup_record(mock_request, 7)

        assert response.status == 200
        body = parse_response_body(response)
        assert body["data"]["id"] == 7
        assert body["data"]["file_path"] == "backup_20261020_020000.dump"

    async def test_get_record_not_found(self, mock_request):
        """测试记录不存在 → 404"""
        with (
            patch_permissions({"system:view"}),
            patch(
                "app.routes.backup.BackupService.get_record",
                new=AsyncMock(side_effect=ValueError("记录不存在: 999")),
            ),
        ):
            response = await get_backup_record(mock_request, 999)

        assert response.status == 404


class TestPerformBackup:
    """手动备份接口"""

    async def test_perform_returns_pending_record(self, mock_request):
        """测试立即返回 pending 记录并后台异步执行"""
        from app.models.backup import BackupRecord
        from app.models.users import User

        record = BackupRecord(
            id=11,
            task_type="manual_backup",
            status="pending",
            operator_id=1,
            backup_date=date(2026, 10, 26),
        )
        record.operator = User(id=1, username="zhangsan", real_name="张三")
        with (
            patch_permissions({"system:database_backup"}),
            patch(
                "app.routes.backup.BackupService.create_record",
                new=AsyncMock(return_value=record),
            ),
            patch(
                "app.routes.backup.BackupService.execute_backup",
                new=AsyncMock(return_value=record),
            ),
        ):
            response = await perform_backup(mock_request)

        assert response.status == 201
        body = parse_response_body(response)
        assert body["code"] == 0
        assert body["data"]["task_type"] == "manual_backup"
        assert body["data"]["status"] == "pending"
        # 操作人需返回姓名而非裸 ID（前端「操作人」列渲染 operator_name）
        assert body["data"]["operator_name"] == "张三"

    async def test_perform_permission_denied(self, mock_request):
        """测试无 system:database_backup 权限 → 403"""
        with patch_permissions({"system:view"}):
            response = await perform_backup(mock_request)

        assert response.status == 403


class TestRestoreBackup:
    """恢复接口（破坏性操作，confirm_date 二次校验）"""

    @staticmethod
    def make_source(**overrides):
        from app.models.backup import BackupRecord

        defaults = {
            "id": 5,
            "task_type": "daily_backup",
            "status": "success",
            "file_path": "backup_20261020_020000.dump",
            "backup_date": date(2026, 10, 20),
        }
        defaults.update(overrides)
        return BackupRecord(**defaults)

    async def test_restore_date_mismatch_returns_400_and_creates_no_record(self, mock_request):
        """confirm_date 与源 backup_date 不匹配 → 400 且不创建 restore 记录"""
        source = self.make_source()

        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = source
        mock_request.ctx.db_session.get = AsyncMock(return_value=source)
        mock_request.ctx.db_session.execute = AsyncMock(return_value=get_result)
        mock_request.json = {"confirm_date": "2026-10-21"}

        with (
            patch_permissions({"system:database_backup"}),
            patch(
                "app.routes.backup.BackupService.create_record",
                new=AsyncMock(),
            ) as create_mock,
        ):
            response = await restore_backup(mock_request, 5)

        assert response.status == 400
        body = parse_response_body(response)
        assert "不匹配" in body["message"]
        create_mock.assert_not_called()

    async def test_restore_missing_confirm_date_returns_400(self, mock_request):
        """缺少 confirm_date → 400"""
        mock_request.json = {}
        with patch_permissions({"system:database_backup"}):
            response = await restore_backup(mock_request, 5)

        assert response.status == 400
        body = parse_response_body(response)
        assert "确认日期" in body["message"]

    async def test_restore_malformed_confirm_date_returns_400(self, mock_request):
        """confirm_date 格式非法 → 400"""
        mock_request.json = {"confirm_date": "20/10/2026"}
        with patch_permissions({"system:database_backup"}):
            response = await restore_backup(mock_request, 5)

        assert response.status == 400

    async def test_restore_success_returns_pending_record(self, mock_request):
        """confirm_date 匹配 → 创建 restore pending 记录并异步执行"""
        from app.models.backup import BackupRecord

        source = self.make_source()
        restore_record = BackupRecord(
            id=20,
            task_type="restore",
            status="pending",
            operator_id=1,
            file_path=source.file_path,
            backup_date=source.backup_date,
        )

        mock_request.ctx.db_session.get = AsyncMock(return_value=source)
        mock_request.json = {"confirm_date": "2026-10-20"}

        with (
            patch_permissions({"system:database_backup"}),
            patch(
                "app.routes.backup.BackupService.resolve_restorable_source",
                new=AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "app.routes.backup.BackupService.create_record",
                new=AsyncMock(return_value=restore_record),
            ),
        ):
            response = await restore_backup(mock_request, 5)

        assert response.status == 201
        body = parse_response_body(response)
        assert body["data"]["task_type"] == "restore"
        assert body["data"]["file_path"] == source.file_path

    async def test_restore_non_success_source_returns_400(self, mock_request):
        """对非 success 备份请求恢复 → 400"""
        mock_request.ctx.db_session.get = AsyncMock(return_value=self.make_source())
        mock_request.json = {"confirm_date": "2026-10-20"}

        with (
            patch_permissions({"system:database_backup"}),
            patch(
                "app.routes.backup.BackupService.resolve_restorable_source",
                new=AsyncMock(side_effect=ValueError("源备份不可恢复")),
            ),
            patch("app.routes.backup.BackupService.create_record", new=AsyncMock()) as create_mock,
        ):
            response = await restore_backup(mock_request, 5)

        assert response.status == 400
        body = parse_response_body(response)
        assert "不可恢复" in body["message"]
        create_mock.assert_not_called()

    async def test_restore_cleanup_source_returns_400(self, mock_request):
        """对 cleanup 记录请求恢复 → 400"""
        mock_request.ctx.db_session.get = AsyncMock(return_value=self.make_source())
        mock_request.json = {"confirm_date": "2026-10-20"}

        with (
            patch_permissions({"system:database_backup"}),
            patch(
                "app.routes.backup.BackupService.resolve_restorable_source",
                new=AsyncMock(side_effect=ValueError("源备份不可恢复")),
            ),
            patch("app.routes.backup.BackupService.create_record", new=AsyncMock()) as create_mock,
        ):
            response = await restore_backup(mock_request, 5)

        assert response.status == 400
        create_mock.assert_not_called()

    async def test_restore_source_not_found_returns_404(self, mock_request):
        """源记录不存在 → 404"""
        mock_request.ctx.db_session.get = AsyncMock(return_value=None)
        mock_request.json = {"confirm_date": "2026-10-20"}

        with patch_permissions({"system:database_backup"}):
            response = await restore_backup(mock_request, 999)

        assert response.status == 404

    async def test_restore_permission_denied(self, mock_request):
        """测试无 system:database_backup 权限 → 403"""
        mock_request.json = {"confirm_date": "2026-10-20"}
        with patch_permissions({"system:view"}):
            response = await restore_backup(mock_request, 5)

        assert response.status == 403


class TestDownloadBackup:
    """下载接口"""

    async def test_download_permission_denied(self, mock_request):
        """测试无 system:database_backup 权限 → 403"""
        with patch_permissions({"system:view"}):
            response = await download_backup(mock_request, 1)

        assert response.status == 403

    async def test_download_record_without_file_returns_400(self, mock_request):
        """记录无备份文件 → 400"""
        from app.models.backup import BackupRecord

        record = BackupRecord(id=1, task_type="cleanup", status="success", file_path=None)

        with (
            patch_permissions({"system:database_backup"}),
            patch("app.routes.backup.BackupService.get_record", new=AsyncMock(return_value=record)),
        ):
            response = await download_backup(mock_request, 1)

        assert response.status == 400
        body = parse_response_body(response)
        assert "无备份文件" in body["message"]

    async def test_download_path_traversal_rejected(self, mock_request):
        """篡改 file_path 越界 → 400"""
        from app.models.backup import BackupRecord

        record = BackupRecord(
            id=1,
            task_type="daily_backup",
            status="success",
            file_path="../../etc/passwd",
        )

        with (
            patch_permissions({"system:database_backup"}),
            patch("app.routes.backup.BackupService.get_record", new=AsyncMock(return_value=record)),
        ):
            response = await download_backup(mock_request, 1)

        assert response.status == 400
        body = parse_response_body(response)
        assert "路径非法" in body["message"]
