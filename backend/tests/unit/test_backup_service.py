"""BackupService 单元测试（mock pg_dump/pg_restore 子进程）"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.backup import BackupRecord
from app.services.backup_service import BackupService


@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock(return_value=None)
    return session


@pytest.fixture
def backup_service(mock_db_session):
    return BackupService(db=mock_db_session)


def make_proc(returncode: int, stderr: bytes = b"") -> MagicMock:
    """构造 mock 子进程（communicate 返回 (stdout, stderr)）"""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"", stderr))
    return proc


def make_record(**overrides) -> BackupRecord:
    """构造未持久化的 BackupRecord 实例（仅用于属性断言）"""
    defaults = {
        "task_type": "daily_backup",
        "status": "pending",
        "file_path": None,
        "file_size_bytes": None,
        "backup_date": date(2026, 10, 20),
        "retention_check_passed": None,
        "deleted_count": 0,
        "duration_seconds": None,
        "error_message": None,
        "operator_id": None,
        "started_at": datetime(2026, 10, 20, 2, 0, tzinfo=timezone(timedelta(hours=8))),
        "completed_at": None,
    }
    defaults.update(overrides)
    return BackupRecord(**defaults)


def make_short_session(rowcount: int = 1) -> MagicMock:
    """构造恢复后写终态用的短会话 mock"""
    session = MagicMock()
    session.commit = AsyncMock()
    result = MagicMock()
    result.rowcount = rowcount
    session.execute = AsyncMock(return_value=result)
    return session


def make_factory(short_session: MagicMock) -> MagicMock:
    """构造返回指定短会话的 session_factory mock（支持 async with）"""
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=short_session)
    factory.return_value.__aexit__ = AsyncMock(return_value=None)
    return factory


def stmt_calls(session: MagicMock, kind: str) -> list:
    """筛出指定类型的语句调用（kind: insert/update）"""
    return [
        call
        for call in session.execute.call_args_list
        if getattr(call[0][0], "__visit_name__", "") == kind
    ]


class TestExecuteBackup:
    """execute_backup：pending → running → 终态"""

    async def test_backup_success_writes_file_path_and_size(
        self, backup_service, mock_db_session, tmp_path
    ):
        """pg_dump 成功 → 写 file_path/file_size_bytes/status=success"""
        record = make_record()
        mock_db_session.get = AsyncMock(return_value=record)

        dest_file = tmp_path / "backup_20261020_020000.dump"
        dest_file.write_bytes(b"x" * 2048)

        frozen = datetime(2026, 10, 20, 2, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        with (
            patch.object(BackupService, "_backup_root", return_value=tmp_path),
            patch("app.services.backup_service.cst_now", return_value=frozen),
            patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=make_proc(0))),
        ):
            result = await backup_service.execute_backup(record_id=1)

        assert result.status == "success"
        assert result.file_path == "backup_20261020_020000.dump"
        assert result.file_size_bytes == 2048
        assert result.error_message is None
        assert result.completed_at is not None
        # running 与终态各一次 commit
        assert mock_db_session.commit.await_count == 2

    async def test_backup_failure_writes_error_message(
        self, backup_service, mock_db_session, tmp_path
    ):
        """pg_dump 非0 → status=failed + error_message=stderr"""
        record = make_record()
        mock_db_session.get = AsyncMock(return_value=record)

        with (
            patch.object(BackupService, "_backup_root", return_value=tmp_path),
            patch(
                "asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=make_proc(1, stderr=b"pg_dump: connection refused")),
            ),
        ):
            result = await backup_service.execute_backup(record_id=1)

        assert result.status == "failed"
        assert "connection refused" in result.error_message
        assert result.file_path is None

    async def test_backup_missing_record_raises(self, backup_service, mock_db_session):
        """记录不存在 → ValueError"""
        mock_db_session.get = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="不存在"):
            await backup_service.execute_backup(record_id=999)


class TestValidateRecentBackups:
    """validate_recent_backups：近保留窗口备份文件存在且 pg_restore --list 通过"""

    @staticmethod
    def _mock_execute_returning(records):
        result = MagicMock()
        result.scalars.return_value.all.return_value = records
        return result

    async def test_all_valid_passes(self, backup_service, mock_db_session, tmp_path):
        """全部有效 → passed=True"""
        valid_file = tmp_path / "a.dump"
        valid_file.write_bytes(b"data")
        records = [make_record(id=1, file_path="a.dump")]

        mock_db_session.execute = AsyncMock(return_value=self._mock_execute_returning(records))

        with (
            patch.object(BackupService, "_backup_root", return_value=tmp_path),
            patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=make_proc(0))),
        ):
            result = await backup_service.validate_recent_backups(days=5)

        assert result["passed"] is True
        assert result["total"] == 1
        assert result["valid"] == 1
        assert result["invalid_records"] == []
        assert result["missing"] == []

    async def test_invalid_file_fails(self, backup_service, mock_db_session, tmp_path):
        """pg_restore --list 非0 → passed=False + invalid_records"""
        bad_file = tmp_path / "bad.dump"
        bad_file.write_bytes(b"corrupted")
        records = [
            make_record(id=1, file_path="bad.dump"),
            make_record(id=2, file_path="good.dump"),
        ]

        mock_db_session.execute = AsyncMock(return_value=self._mock_execute_returning(records))

        good_file = tmp_path / "good.dump"
        good_file.write_bytes(b"data")

        procs = [make_proc(1, stderr=b"pg_restore: error"), make_proc(0)]
        exec_mock = AsyncMock(side_effect=procs)

        with (
            patch.object(BackupService, "_backup_root", return_value=tmp_path),
            patch("asyncio.create_subprocess_exec", new=exec_mock),
        ):
            result = await backup_service.validate_recent_backups(days=5)

        assert result["passed"] is False
        assert result["valid"] == 1
        assert len(result["invalid_records"]) == 1
        assert result["invalid_records"][0]["id"] == 1

    async def test_missing_file_fails(self, backup_service, mock_db_session, tmp_path):
        """文件缺失 → passed=False + missing"""
        records = [make_record(id=1, file_path="gone.dump")]
        mock_db_session.execute = AsyncMock(return_value=self._mock_execute_returning(records))

        with patch.object(BackupService, "_backup_root", return_value=tmp_path):
            result = await backup_service.validate_recent_backups(days=5)

        assert result["passed"] is False
        assert len(result["missing"]) == 1
        assert result["missing"][0]["id"] == 1

    async def test_path_traversal_rejected(self, backup_service, mock_db_session, tmp_path):
        """路径穿越 → 计入 invalid_records，不读文件"""
        records = [make_record(id=1, file_path="../../etc/passwd")]
        mock_db_session.execute = AsyncMock(return_value=self._mock_execute_returning(records))

        with (
            patch.object(BackupService, "_backup_root", return_value=tmp_path),
            patch("asyncio.create_subprocess_exec", new=AsyncMock()) as exec_mock,
        ):
            result = await backup_service.validate_recent_backups(days=5)

        assert result["passed"] is False
        assert result["invalid_records"][0]["reason"] == "路径非法"
        exec_mock.assert_not_called()


class TestExecuteCleanup:
    """execute_cleanup：校验通过才删除超期文件"""

    @staticmethod
    def _mock_execute_returning(records):
        result = MagicMock()
        result.scalars.return_value.all.return_value = records
        return result

    async def test_cleanup_deletes_stale_files_when_validation_passes(
        self, backup_service, mock_db_session, tmp_path
    ):
        """校验通过 → 删除 >5天 文件 + deleted_count>0 + retention_check_passed=True"""
        stale_file = tmp_path / "stale.dump"
        stale_file.write_bytes(b"old")
        stale_record = make_record(id=1, file_path="stale.dump")

        # validate_recent_backups 已 patch（不查库），execute 只服务于超期记录查询
        stale_result = self._mock_execute_returning([stale_record])
        mock_db_session.execute = AsyncMock(return_value=stale_result)

        with (
            patch.object(BackupService, "_backup_root", return_value=tmp_path),
            patch.object(
                BackupService,
                "validate_recent_backups",
                new=AsyncMock(
                    return_value={
                        "passed": True,
                        "total": 0,
                        "valid": 0,
                        "invalid_records": [],
                        "missing": [],
                    }
                ),
            ),
        ):
            result = await backup_service.execute_cleanup()

        assert result.task_type == "cleanup"
        assert result.status == "success"
        assert result.deleted_count == 1
        assert result.retention_check_passed is True
        assert not stale_file.exists()

    async def test_cleanup_skips_deletion_when_validation_fails(
        self, backup_service, mock_db_session, tmp_path
    ):
        """校验失败 → 不删任何文件 + retention_check_passed=False + status=failed"""
        stale_file = tmp_path / "stale.dump"
        stale_file.write_bytes(b"old")
        stale_record = make_record(id=1, file_path="stale.dump")

        mock_db_session.execute = AsyncMock(
            return_value=self._mock_execute_returning([stale_record])
        )

        with (
            patch.object(BackupService, "_backup_root", return_value=tmp_path),
            patch.object(
                BackupService,
                "validate_recent_backups",
                new=AsyncMock(
                    return_value={
                        "passed": False,
                        "total": 1,
                        "valid": 0,
                        "invalid_records": [
                            {
                                "id": 9,
                                "file_path": "bad.dump",
                                "reason": "pg_restore --list 校验失败",
                            }
                        ],
                        "missing": [],
                    }
                ),
            ),
        ):
            result = await backup_service.execute_cleanup()

        assert result.status == "failed"
        assert result.retention_check_passed is False
        assert result.deleted_count == 0
        assert stale_file.exists()
        assert "校验未通过" in result.error_message


class TestExecuteRestore:
    """execute_restore：源备份校验 + pg_restore 终态"""

    async def test_resolve_source_success(self, backup_service, mock_db_session, tmp_path):
        """可恢复源 → 返回绝对路径"""
        source_file = tmp_path / "src.dump"
        source_file.write_bytes(b"data")
        source = make_record(id=5, task_type="daily_backup", status="success", file_path="src.dump")
        mock_db_session.get = AsyncMock(return_value=source)

        with patch.object(BackupService, "_backup_root", return_value=tmp_path):
            resolved = await backup_service.resolve_restorable_source(5)

        assert resolved == (tmp_path / "src.dump").resolve()

    async def test_restore_success(self, mock_db_session, tmp_path):
        """pg_restore returncode 0 → 终态写入 success，源文件不被破坏"""
        source_file = tmp_path / "src.dump"
        source_file.write_bytes(b"data")
        restore_record = make_record(
            id=20, task_type="restore", operator_id=1, file_path="src.dump"
        )
        mock_db_session.get = AsyncMock(return_value=restore_record)

        short_session = make_short_session(rowcount=1)
        service = BackupService(db=mock_db_session, session_factory=make_factory(short_session))

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=make_proc(0))):
            await service.execute_restore(20, source_file)

        # 终态由短会话按 id 更新（留痕表可能已被恢复操作重建）
        update_calls = stmt_calls(short_session, "update")
        assert len(update_calls) == 1
        assert update_calls[0][0][0].table.name == "backup_records"
        short_session.commit.assert_awaited()
        # 源备份文件不被恢复操作修改/删除
        assert source_file.exists()

    async def test_restore_failure_writes_error_message(self, mock_db_session, tmp_path):
        """pg_restore 非0 → 终态写入 failed + error_message"""
        source_file = tmp_path / "src.dump"
        source_file.write_bytes(b"data")
        restore_record = make_record(
            id=20, task_type="restore", operator_id=1, file_path="src.dump"
        )
        mock_db_session.get = AsyncMock(return_value=restore_record)

        short_session = make_short_session(rowcount=1)
        service = BackupService(db=mock_db_session, session_factory=make_factory(short_session))

        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=make_proc(1, stderr=b"pg_restore: fatal")),
        ):
            await service.execute_restore(20, source_file)

        update_stmt = stmt_calls(short_session, "update")[0][0][0]
        # 终态 UPDATE 携带 failed 状态与错误信息
        params = update_stmt.compile().params
        assert params["status"] == "failed"
        assert "fatal" in params["error_message"]

    async def test_restore_reinserts_record_when_table_dropped(self, mock_db_session, tmp_path):
        """留痕表被 pg_restore --clean 重建导致 UPDATE 0 行时，重新 INSERT 终态行

        回归：恢复清空全库（含 backup_records），pending 留痕行随之消失，
        UPDATE 匹配 0 行；此时必须按快照 INSERT 重插，保证留痕不丢。
        """
        source_file = tmp_path / "src.dump"
        source_file.write_bytes(b"data")
        restore_record = make_record(
            id=20, task_type="restore", operator_id=1, file_path="src.dump"
        )
        mock_db_session.get = AsyncMock(return_value=restore_record)

        # 短会话：模拟留痕行已被删（rowcount=0）→ 必须走 INSERT 重插
        short_session = make_short_session(rowcount=0)
        service = BackupService(db=mock_db_session, session_factory=make_factory(short_session))

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=make_proc(0))):
            await service.execute_restore(20, source_file)

        # UPDATE 未命中 → 按快照 INSERT 同 id 终态行
        insert_calls = stmt_calls(short_session, "insert")
        assert len(insert_calls) == 1
        insert_stmt = insert_calls[0][0][0]
        assert insert_stmt.table.name == "backup_records"
        assert insert_stmt.compile().params["id"] == 20
        assert insert_stmt.compile().params["status"] == "success"
        short_session.commit.assert_awaited()

    @pytest.mark.parametrize(
        "overrides",
        [
            {"task_type": "cleanup"},
            {"status": "failed"},
            {"status": "pending"},
            {"file_path": None},
        ],
    )
    async def test_resolve_unrestorable_source_raises(
        self, backup_service, mock_db_session, tmp_path, overrides
    ):
        """源记录非 success 备份 / 无文件路径 → ValueError"""
        source = make_record(id=5, **overrides)
        mock_db_session.get = AsyncMock(return_value=source)

        with patch.object(BackupService, "_backup_root", return_value=tmp_path):
            with pytest.raises(ValueError, match="源备份不可恢复"):
                await backup_service.resolve_restorable_source(5)

    async def test_resolve_missing_file_raises(self, backup_service, mock_db_session, tmp_path):
        """源备份文件不存在 → ValueError"""
        source = make_record(
            id=5, task_type="daily_backup", status="success", file_path="gone.dump"
        )
        mock_db_session.get = AsyncMock(return_value=source)

        with patch.object(BackupService, "_backup_root", return_value=tmp_path):
            with pytest.raises(ValueError, match="源备份不可恢复"):
                await backup_service.resolve_restorable_source(5)

    async def test_resolve_path_traversal_raises(self, backup_service, mock_db_session, tmp_path):
        """源备份路径越界 → ValueError"""
        source = make_record(
            id=5, task_type="daily_backup", status="success", file_path="../../../etc/passwd"
        )
        mock_db_session.get = AsyncMock(return_value=source)

        with patch.object(BackupService, "_backup_root", return_value=tmp_path):
            with pytest.raises(ValueError, match="源备份不可恢复"):
                await backup_service.resolve_restorable_source(5)


class TestPathSafety:
    """_abs_path 路径穿越防护"""

    def test_relative_path_inside_root(self, backup_service, tmp_path):
        with patch.object(BackupService, "_backup_root", return_value=tmp_path):
            resolved = backup_service._abs_path("backup_20261020.dump")
        assert resolved == (tmp_path / "backup_20261020.dump").resolve()

    @pytest.mark.parametrize(
        "bad_path",
        ["../outside.dump", "../../etc/passwd", "subdir/../../outside.dump"],
    )
    def test_traversal_rejected(self, backup_service, tmp_path, bad_path):
        with patch.object(BackupService, "_backup_root", return_value=tmp_path):
            with pytest.raises(ValueError, match="路径非法"):
                backup_service._abs_path(bad_path)


class TestListRecords:
    """list_records 分页与筛选"""

    async def test_list_returns_pagination(self, backup_service, mock_db_session):
        records = [make_record(id=1), make_record(id=2, task_type="cleanup")]

        count_result = MagicMock()
        count_result.scalar.return_value = 2
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = records
        mock_db_session.execute = AsyncMock(side_effect=[count_result, data_result])

        result = await backup_service.list_records(page=1, page_size=20)

        assert result["pagination"] == {"total": 2, "page": 1, "page_size": 20}
        assert len(result["list"]) == 2
        assert result["list"][0]["id"] == 1
        assert result["list"][0]["backup_date"] == "2026-10-20"

    async def test_list_with_task_type_filter_passes_condition(
        self, backup_service, mock_db_session
    ):
        """task_type 筛选条件进入 SQL（捕获编译语句断言）"""
        from sqlalchemy.dialects import postgresql

        count_result = MagicMock()
        count_result.scalar.return_value = 0
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(side_effect=[count_result, data_result])

        await backup_service.list_records(page=1, page_size=20, task_type="cleanup")

        count_stmt = mock_db_session.execute.call_args_list[0][0][0]
        sql = str(count_stmt.compile(dialect=postgresql.dialect()))
        assert "backup_records.task_type = " in sql

    async def test_list_serializes_operator_name(self, backup_service, mock_db_session):
        """列表序列化带出 operator_name（real_name 优先，username 兜底）"""
        from app.models.users import User

        record = make_record(id=3, task_type="manual_backup", operator_id=1)
        record.operator = User(id=1, username="zhangsan", real_name="张三")

        count_result = MagicMock()
        count_result.scalar.return_value = 1
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = [record]
        mock_db_session.execute = AsyncMock(side_effect=[count_result, data_result])

        result = await backup_service.list_records(page=1, page_size=20)

        assert result["list"][0]["operator_name"] == "张三"


class TestRecordToDict:
    """_record_to_dict：操作人姓名序列化"""

    def test_operator_name_uses_real_name(self):
        from app.models.users import User

        record = make_record(id=5, operator_id=1)
        record.operator = User(id=1, username="zhangsan", real_name="张三")

        data = BackupService._record_to_dict(record)

        assert data["operator_id"] == 1
        assert data["operator_name"] == "张三"

    def test_operator_name_falls_back_to_username(self):
        """real_name 为空时回退 username"""
        from app.models.users import User

        record = make_record(id=6, operator_id=2)
        record.operator = User(id=2, username="lisi", real_name=None)

        data = BackupService._record_to_dict(record)

        assert data["operator_name"] == "lisi"

    def test_operator_name_none_for_system_task(self):
        """定时任务 operator_id 为 None → operator_name 为 None（前端显示「系统自动」）"""
        record = make_record(id=7, operator_id=None)

        data = BackupService._record_to_dict(record)

        assert data["operator_name"] is None
