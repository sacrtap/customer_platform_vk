"""数据备份服务

提供数据库备份（pg_dump -Fc）、备份有效性校验（pg_restore --list）、
过期备份清理（清理前校验保留窗口内备份有效）、在线恢复（pg_restore --clean --if-exists）
与全流程任务留痕。

路径安全：备份文件名固定为 backup_YYYYMMDD_HHMMSS.dump，落 settings.backup_dir；
所有磁盘操作前解析绝对路径并校验位于 backup_dir 内（防路径穿越）。
"""

import logging
import os
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.backup import BackupRecord, BackupScheduleConfig
from app.utils.timezone import cst_now, cst_today

logger = logging.getLogger(__name__)

BACKUP_TASK_NAME = "daily_backup"
BACKUP_FILE_PREFIX = "backup_"
BACKUP_FILE_SUFFIX = ".dump"
_ERROR_MESSAGE_MAX = 2000
# cleanup 记录 created_at 为 naive 墙钟（TimestampMixin: DateTime 无 tz），
# cst_now() 为 aware → 剥离 tzinfo 后比较（asyncpg 同样不接受 aware 参数）
_NAIVE_NOW = lambda: cst_now().replace(tzinfo=None)  # noqa: E731


class BackupService:
    """数据备份服务"""

    def __init__(self, db: AsyncSession, session_factory=None):
        self.db = db
        # 恢复操作会 DROP 全库对象（含留痕表），终态写入需用新连接；
        # 与 InvoiceExcelService 同构，未提供时回退当前 session。
        self.session_factory = session_factory

    # ---------- 路径安全 ----------

    def _backup_root(self) -> Path:
        """备份根目录（绝对路径）"""
        return Path(settings.backup_dir).resolve()

    def _abs_path(self, file_path: str) -> Path:
        """相对路径 → 绝对路径，并校验位于 backup_dir 内（防路径穿越）"""
        root = self._backup_root()
        target = (root / file_path).resolve()
        if not target.is_relative_to(root):
            raise ValueError("备份文件路径非法")
        return target

    # ---------- 配置 ----------

    async def get_or_create_schedule_config(self) -> BackupScheduleConfig:
        """获取定时备份配置（不存在则创建默认行）"""
        result = await self.db.execute(
            select(BackupScheduleConfig).where(BackupScheduleConfig.task_name == BACKUP_TASK_NAME)
        )
        config = result.scalar_one_or_none()
        if config is None:
            config = BackupScheduleConfig(task_name=BACKUP_TASK_NAME)
            self.db.add(config)
            await self.db.commit()
            await self.db.refresh(config)
        return config

    # ---------- 留痕 ----------

    async def create_record(
        self,
        task_type: str,
        operator_id: int | None,
        file_path: str | None = None,
        backup_date: date | None = None,
    ) -> BackupRecord:
        """创建 pending 任务记录

        Args:
            task_type: daily_backup/manual_backup/cleanup/restore
            operator_id: 操作人ID；定时任务为 None
            file_path: 备份相对路径（restore 传源备份路径）
            backup_date: 备份业务日期；backup 类缺省取 cst_today()，restore 由调用方传源日期
        """
        if backup_date is None and "backup" in task_type:
            backup_date = cst_today()

        record = BackupRecord(
            task_type=task_type,
            status="pending",
            file_path=file_path,
            backup_date=backup_date,
            operator_id=operator_id,
            started_at=cst_now(),
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        # 序列化前显式加载 operator：async 会话中 relationship 懒加载会抛 MissingGreenlet
        await self.db.refresh(record, attribute_names=["operator"])
        return record

    async def _mark_running(self, record: BackupRecord) -> None:
        record.status = "running"
        await self.db.commit()

    async def _finalize(
        self,
        record: BackupRecord,
        *,
        success: bool,
        error_message: str | None = None,
        file_path: str | None = None,
        file_size_bytes: int | None = None,
        deleted_count: int | None = None,
        retention_check_passed: bool | None = None,
    ) -> BackupRecord:
        """写入终态并提交（成功/失败共用）"""
        record.status = "success" if success else "failed"
        completed_at = cst_now()
        record.completed_at = completed_at
        if record.started_at is not None:
            record.duration_seconds = int((completed_at - record.started_at).total_seconds())
        if file_path is not None:
            record.file_path = file_path
        if file_size_bytes is not None:
            record.file_size_bytes = file_size_bytes
        if deleted_count is not None:
            record.deleted_count = deleted_count
        if retention_check_passed is not None:
            record.retention_check_passed = retention_check_passed
        if error_message is not None:
            record.error_message = error_message[:_ERROR_MESSAGE_MAX]
        await self.db.commit()
        await self.db.refresh(record)
        return record

    def _snapshot(self, record: BackupRecord) -> dict:
        """留痕记录的字段快照（供短会话重插终态用）"""
        return {
            "id": record.id,
            "task_type": record.task_type,
            "file_path": record.file_path,
            "file_size_bytes": record.file_size_bytes,
            "backup_date": record.backup_date,
            "retention_check_passed": record.retention_check_passed,
            "deleted_count": record.deleted_count,
            "operator_id": record.operator_id,
            "started_at": record.started_at,
        }

    async def _write_final_state(
        self, snapshot: dict, *, success: bool, error_message: str | None
    ) -> None:
        """在**短会话**内写入任务终态（容忍留痕表被 pg_restore --clean 重建）

        pg_restore --clean 会 DROP 并重建全库对象，pending 留痕行随之消失，
        且原 session 的连接/事务状态已被破坏（greenlet 上下文失效）。
        因此必须用 session_factory 新开短会话（新连接）；
        先按 id UPDATE，匹配 0 行则按快照 INSERT，保证留痕连续。
        未提供工厂时（如测试）回退当前 session。
        """
        from sqlalchemy import insert, update

        completed_at = cst_now()
        started_at = snapshot.get("started_at")
        duration = None
        if started_at is not None:
            duration = int((completed_at - started_at).total_seconds())
        err_text = error_message[:_ERROR_MESSAGE_MAX] if error_message else None

        values = {
            "status": "success" if success else "failed",
            "completed_at": completed_at,
            "duration_seconds": duration,
            "error_message": err_text,
        }
        # created_at/updated_at 是 TIMESTAMP WITHOUT TIME ZONE（naive），
        # 而 completed_at 是 aware；显式剥离时区避免 asyncpg 编码失败。
        naive_now = completed_at.replace(tzinfo=None)

        async def _apply(db: AsyncSession) -> None:
            result = await db.execute(
                update(BackupRecord).where(BackupRecord.id == snapshot["id"]).values(**values)
            )
            if (result.rowcount or 0) == 0:  # pyright: ignore[reportAttributeAccessIssue]
                # 留痕行已被恢复操作删除 → 按快照重插，保持 id 与留痕连续性
                await db.execute(
                    insert(BackupRecord).values(
                        **snapshot,
                        **values,
                        created_at=naive_now,
                        updated_at=naive_now,
                    )
                )
            await db.commit()

        if self.session_factory is not None:
            async with self.session_factory() as fresh_db:
                await _apply(fresh_db)
        else:
            await _apply(self.db)

        logger.info(
            "恢复任务留痕已写入终态 id=%s status=%s",
            snapshot["id"],
            values["status"],
        )

    # ---------- 备份 ----------

    async def execute_backup(self, record_id: int) -> BackupRecord:
        """执行备份：pending → running → success/failed"""
        record = await self.db.get(BackupRecord, record_id)
        if record is None:
            raise ValueError(f"备份记录不存在: {record_id}")

        await self._mark_running(record)

        filename = f"{BACKUP_FILE_PREFIX}{cst_now().strftime('%Y%m%d_%H%M%S')}{BACKUP_FILE_SUFFIX}"
        dest_path = self._backup_root() / filename
        try:
            ok, error = await self._run_pg_dump(dest_path)
            if ok:
                return await self._finalize(
                    record,
                    success=True,
                    file_path=filename,
                    file_size_bytes=dest_path.stat().st_size,
                )
            return await self._finalize(record, success=False, error_message=error)
        except Exception as e:
            logger.error("执行备份失败: %s", e)
            return await self._finalize(record, success=False, error_message=str(e))

    async def _run_pg_dump(self, dest_path: Path) -> tuple[bool, str]:
        """pg_dump -Fc 整库备份；返回 (是否成功, 错误信息)"""
        import asyncio

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        proc = await asyncio.create_subprocess_exec(
            "pg_dump",
            "-Fc",
            "-f",
            str(dest_path),
            settings.database_url,
            env={**os.environ},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode == 0:
            return True, ""
        return False, (stderr or b"").decode("utf-8", errors="replace")

    # ---------- 清理 ----------

    async def validate_recent_backups(self, days: int) -> dict:
        """校验保留窗口内全部 success 备份文件存在且 pg_restore --list 通过

        Returns:
            {"passed": bool, "total": n, "valid": n, "invalid_records": [...], "missing": [...]}
        """
        import asyncio

        cutoff = _NAIVE_NOW() - timedelta(days=days)
        result = await self.db.execute(
            select(BackupRecord).where(
                BackupRecord.task_type.in_(["daily_backup", "manual_backup"]),
                BackupRecord.status == "success",
                BackupRecord.file_path.is_not(None),
                BackupRecord.created_at >= cutoff,
            )
        )
        records = result.scalars().all()

        invalid_records: list[dict] = []
        missing: list[dict] = []
        valid_count = 0

        for rec in records:
            assert rec.file_path is not None  # noqa: S101 -- 查询已过滤非空
            try:
                abs_path = self._abs_path(rec.file_path)
            except ValueError:
                invalid_records.append(
                    {"id": rec.id, "file_path": rec.file_path, "reason": "路径非法"}
                )
                continue

            if not abs_path.is_file():
                missing.append({"id": rec.id, "file_path": rec.file_path})
                continue

            proc = await asyncio.create_subprocess_exec(
                "pg_restore",
                "--list",
                str(abs_path),
                env={**os.environ},
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode == 0:
                valid_count += 1
            else:
                invalid_records.append(
                    {
                        "id": rec.id,
                        "file_path": rec.file_path,
                        "reason": "pg_restore --list 校验失败",
                    }
                )

        return {
            "passed": not invalid_records and not missing,
            "total": len(records),
            "valid": valid_count,
            "invalid_records": invalid_records,
            "missing": missing,
        }

    async def execute_cleanup(self) -> BackupRecord:
        """清理过期备份：先校验保留窗口内备份有效，通过才删除超期文件"""
        record = await self.create_record("cleanup", operator_id=None)
        await self._mark_running(record)

        try:
            check = await self.validate_recent_backups(settings.backup_retention_days)
            if not check["passed"]:
                detail = f"保留窗口内备份校验未通过: {check['invalid_records'] + check['missing']}"
                return await self._finalize(
                    record,
                    success=False,
                    error_message=detail,
                    deleted_count=0,
                    retention_check_passed=False,
                )

            cutoff = _NAIVE_NOW() - timedelta(days=settings.backup_retention_days)
            result = await self.db.execute(
                select(BackupRecord).where(
                    BackupRecord.task_type.in_(["daily_backup", "manual_backup"]),
                    BackupRecord.status == "success",
                    BackupRecord.file_path.is_not(None),
                    BackupRecord.created_at < cutoff,
                )
            )
            stale_records = result.scalars().all()

            deleted_count = 0
            for rec in stale_records:
                assert rec.file_path is not None  # noqa: S101 -- 查询已过滤非空
                try:
                    abs_path = self._abs_path(rec.file_path)
                except ValueError:
                    logger.warning("清理跳过路径非法记录 id=%s path=%s", rec.id, rec.file_path)
                    continue
                abs_path.unlink(missing_ok=True)
                deleted_count += 1

            return await self._finalize(
                record,
                success=True,
                deleted_count=deleted_count,
                retention_check_passed=True,
            )
        except Exception as e:
            logger.error("执行备份清理失败: %s", e)
            return await self._finalize(record, success=False, error_message=str(e))

    # ---------- 恢复 ----------

    async def resolve_restorable_source(self, source_record_id: int) -> Path:
        """校验源备份可恢复并返回其绝对路径

        可恢复条件：daily_backup/manual_backup + status=success + file_path 非空
        + 文件存在 + 路径位于 backup_dir 内。
        """
        source = await self.db.get(BackupRecord, source_record_id)
        if source is None:
            raise ValueError("源备份记录不存在")
        if source.task_type not in ("daily_backup", "manual_backup"):
            raise ValueError("源备份不可恢复")
        if source.status != "success":
            raise ValueError("源备份不可恢复")
        if not source.file_path:
            raise ValueError("源备份不可恢复")
        try:
            abs_path = self._abs_path(source.file_path)
        except ValueError as e:
            raise ValueError("源备份不可恢复") from e
        if not abs_path.is_file():
            raise ValueError("源备份不可恢复")
        return abs_path

    async def execute_restore(self, restore_record_id: int, abs_path: Path) -> BackupRecord:
        """对已创建的 restore 留痕记录执行 pg_restore --clean --if-exists

        pg_restore --clean 会 DROP 并重建全库对象（含 backup_records），留痕行随之消失，
        且当前 session 的连接/事务状态会被破坏。因此 `_run_pg_restore` 之后的
        终态写入**只用 session_factory 新开短会话**，不再触碰 self.db。
        """
        record = await self.db.get(BackupRecord, restore_record_id)
        if record is None:
            raise ValueError(f"恢复记录不存在: {restore_record_id}")

        # 取快照（必须在任何 DB 写操作前完成）
        snapshot = self._snapshot(record)

        try:
            await self._mark_running(record)
        except SQLAlchemyError as e:
            logger.warning("恢复留痕标记 running 失败（将继续执行恢复）: %s", e)

        try:
            ok, error = await self._run_pg_restore(abs_path)
        except Exception as e:
            logger.error("执行 pg_restore 失败: %s", e)
            ok, error = False, str(e)

        await self._write_final_state(snapshot, success=ok, error_message=error if not ok else None)
        return record

    async def _run_pg_restore(self, file_path: Path) -> tuple[bool, str]:
        """pg_restore --clean --if-exists 在线恢复；返回 (是否成功, 错误信息)

        --clean 的 DROP 阶段 stderr 会输出 notice，仅以 returncode 判定成败。
        """
        import asyncio

        proc = await asyncio.create_subprocess_exec(
            "pg_restore",
            "--clean",
            "--if-exists",
            "-d",
            settings.database_url,
            str(file_path),
            env={**os.environ},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode == 0:
            return True, ""
        return False, (stderr or b"").decode("utf-8", errors="replace")

    # ---------- 查询 ----------

    async def list_records(
        self, page: int = 1, page_size: int = 20, task_type: str | None = None
    ) -> dict:
        """获取备份任务记录列表（分页）"""
        from sqlalchemy import desc as sa_desc

        query = select(BackupRecord).options(selectinload(BackupRecord.operator))
        count_query = select(func.count(BackupRecord.id))

        if task_type:
            query = query.where(BackupRecord.task_type == task_type)
            count_query = count_query.where(BackupRecord.task_type == task_type)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(sa_desc(BackupRecord.created_at)).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        records = result.scalars().all()

        return {
            "list": [self._record_to_dict(rec) for rec in records],
            "pagination": {"total": total, "page": page, "page_size": page_size},
        }

    async def get_record(self, record_id: int) -> BackupRecord:
        """获取单条任务记录"""
        result = await self.db.execute(
            select(BackupRecord)
            .options(selectinload(BackupRecord.operator))
            .where(BackupRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise ValueError(f"记录不存在: {record_id}")
        return record

    @staticmethod
    def _record_to_dict(record: BackupRecord) -> dict:
        """序列化（UTC aware datetime → CST 展示串）"""
        from app.utils.timezone import utc_to_cst_datetime_str

        return {
            "id": record.id,
            "task_type": record.task_type,
            "status": record.status,
            "file_path": record.file_path,
            "file_size_bytes": record.file_size_bytes,
            "backup_date": record.backup_date.isoformat() if record.backup_date else None,
            "retention_check_passed": record.retention_check_passed,
            "deleted_count": record.deleted_count,
            "duration_seconds": record.duration_seconds,
            "error_message": record.error_message,
            "operator_id": record.operator_id,
            "operator_name": (
                (record.operator.real_name or record.operator.username) if record.operator else None
            ),
            "started_at": utc_to_cst_datetime_str(record.started_at),
            "completed_at": utc_to_cst_datetime_str(record.completed_at),
            "created_at": utc_to_cst_datetime_str(record.created_at),
        }
