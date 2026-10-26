"""数据备份 API

管理「每日数据库备份」任务的配置（开启/关闭、执行时间）、手动备份、
备份下载、选择指定备份恢复，以及备份/清理/恢复全过程任务记录查询。
GET 需 system:view；写操作（PUT/POST/下载）需 system:database_backup。
"""

import logging
import re

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import auth_required, require_permission
from ..models.backup import BackupRecord
from ..services.backup_service import BackupService

logger = logging.getLogger(__name__)

backup_bp = Blueprint("backup", url_prefix="/api/v1/system/backup")

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


async def _get_or_create_config(db_session: AsyncSession):
    """获取定时备份配置（不存在则创建默认行）"""
    service = BackupService(db=db_session)
    return await service.get_or_create_schedule_config()


def _config_dict(config) -> dict:
    """配置响应（含下次执行时间）"""
    from ..tasks.backup import BACKUP_JOB_ID
    from ..tasks.scheduler import get_scheduler

    scheduler = get_scheduler()
    job = scheduler.get_job(BACKUP_JOB_ID)
    return {
        "task_name": config.task_name,
        "enabled": bool(config.enabled),
        "backup_time": config.backup_time,
        "next_run_time": job.next_run_time.isoformat() if job and job.next_run_time else None,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


def _reschedule_job(request: Request, enabled: bool, backup_time: str) -> None:
    """按配置动态注册/注销 APScheduler 每日备份 job"""
    from ..tasks.backup import register_backup_daily
    from ..tasks.scheduler import get_scheduler

    session_factory = request.app.ctx.async_session_maker
    register_backup_daily(get_scheduler(), session_factory, enabled, backup_time)


@backup_bp.get("/schedule")
@auth_required
@require_permission("system:view")
async def get_backup_schedule(request: Request):
    """获取定时备份配置"""
    try:
        db_session: AsyncSession = request.ctx.db_session
        config = await _get_or_create_config(db_session)
        return json({"code": 0, "message": "success", "data": _config_dict(config)})
    except Exception as e:
        logger.error("获取定时备份配置失败: %s", e)
        return json({"code": 500, "message": f"获取失败: {str(e)}"}, status=500)


@backup_bp.put("/schedule")
@auth_required
@require_permission("system:database_backup")
async def update_backup_schedule(request: Request):
    """更新定时备份配置（PUT 后立即动态调整调度）"""
    try:
        db_session: AsyncSession = request.ctx.db_session
        data = request.json
        if not isinstance(data, dict):
            return json({"code": 400, "message": "请求体必须是 JSON 对象"}, status=400)

        config = await _get_or_create_config(db_session)

        backup_time = data.get("backup_time", config.backup_time)
        enabled = data.get("enabled", config.enabled)

        if not TIME_PATTERN.match(str(backup_time)):
            return json(
                {"code": 400, "message": "备份时间格式应为 HH:MM（24小时制），如 02:00"},
                status=400,
            )
        if not isinstance(enabled, bool):
            return json({"code": 400, "message": "enabled 必须为布尔值"}, status=400)

        config.enabled = enabled
        config.backup_time = backup_time
        config.updated_by = request.ctx.user["user_id"]
        await db_session.commit()
        await db_session.refresh(config)

        # 动态调整 APScheduler job
        try:
            _reschedule_job(request, enabled, backup_time)
        except Exception as e:
            logger.error("动态调整备份任务失败: %s", e)
            # 配置已保存，调度调整失败不影响响应（下次启动会按配置注册）
            return json(
                {
                    "code": 0,
                    "message": f"配置已保存（调度调整失败: {e}）",
                    "data": _config_dict(config),
                }
            )

        return json({"code": 0, "message": "配置已更新", "data": _config_dict(config)})
    except Exception as e:
        logger.error("更新定时备份配置失败: %s", e)
        return json({"code": 500, "message": f"更新失败: {str(e)}"}, status=500)


@backup_bp.get("/records")
@auth_required
@require_permission("system:view")
async def list_backup_records(request: Request):
    """获取备份任务记录列表（分页）"""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        task_type = request.args.get("task_type")

        service = BackupService(db=request.ctx.db_session)
        result = await service.list_records(page=page, page_size=page_size, task_type=task_type)
        return json({"code": 0, "message": "success", "data": result})
    except Exception as e:
        logger.error("获取备份记录列表失败: %s", e)
        return json({"code": 500, "message": f"获取失败: {str(e)}"}, status=500)


@backup_bp.get("/records/<record_id:int>")
@auth_required
@require_permission("system:view")
async def get_backup_record(request: Request, record_id: int):
    """获取单条备份任务记录"""
    try:
        service = BackupService(db=request.ctx.db_session)
        record = await service.get_record(record_id)
        return json(
            {"code": 0, "message": "success", "data": BackupService._record_to_dict(record)}
        )
    except ValueError as e:
        return json({"code": 404, "message": str(e)}, status=404)
    except Exception as e:
        logger.error("获取备份记录失败: %s", e)
        return json({"code": 500, "message": f"获取失败: {str(e)}"}, status=500)


@backup_bp.post("/perform")
@auth_required
@require_permission("system:database_backup")
async def perform_backup(request: Request):
    """手动立即备份（异步执行，立即返回 pending 记录）"""
    try:
        db_session: AsyncSession = request.ctx.db_session
        operator_id = request.ctx.user["user_id"]

        service = BackupService(db=db_session)
        record = await service.create_record("manual_backup", operator_id=operator_id)

        # 备份可能耗时数分钟：用独立 session 后台执行，避免 HTTP 超时
        async_session_maker = request.app.ctx.async_session_maker

        async def run_backup():
            async with async_session_maker() as new_session:
                bg_service = BackupService(db=new_session)
                await bg_service.execute_backup(record.id)  # pyright: ignore[reportArgumentType]

        request.app.add_task(run_backup())

        return json(
            {
                "code": 0,
                "message": "备份任务已创建",
                "data": BackupService._record_to_dict(record),
            },
            status=201,
        )
    except Exception as e:
        logger.error("创建手动备份任务失败: %s", e)
        return json({"code": 500, "message": f"创建失败: {str(e)}"}, status=500)


@backup_bp.post("/records/<record_id:int>/restore")
@auth_required
@require_permission("system:database_backup")
async def restore_backup(request: Request, record_id: int):
    """恢复指定备份（破坏性操作，需确认日期匹配，异步执行）"""
    try:
        db_session: AsyncSession = request.ctx.db_session
        operator_id = request.ctx.user["user_id"]

        data = request.json if isinstance(request.json, dict) else {}
        confirm_date = data.get("confirm_date")
        if not confirm_date or not DATE_PATTERN.match(str(confirm_date)):
            return json(
                {"code": 400, "message": "请提供确认日期（YYYY-MM-DD）"},
                status=400,
            )

        service = BackupService(db=db_session)
        source = await db_session.get(BackupRecord, record_id)
        if source is None:
            return json({"code": 404, "message": "备份记录不存在"}, status=404)

        # 二次校验：确认日期必须与源备份日期完全一致（防误触，不匹配则不创建记录）
        source_date = source.backup_date
        if source_date is None or confirm_date != source_date.isoformat():
            return json(
                {"code": 400, "message": "确认日期与备份日期不匹配"},
                status=400,
            )

        # 校验源备份可恢复（success 备份、文件存在、路径在 backup_dir 内）
        try:
            source_abs_path = await service.resolve_restorable_source(record_id)
        except ValueError as e:
            message = str(e)
            status = 404 if "不存在" in message else 400
            return json({"code": status, "message": message}, status=status)

        record = await service.create_record(
            "restore",
            operator_id=operator_id,
            file_path=source.file_path,
            backup_date=source.backup_date,
        )

        # 恢复可能耗时数分钟：用独立 session 后台执行，避免 HTTP 超时
        async_session_maker = request.app.ctx.async_session_maker
        restore_record_id = record.id

        async def run_restore():
            async with async_session_maker() as new_session:
                bg_service = BackupService(
                    db=new_session,
                    session_factory=async_session_maker,  # 恢复后留痕表被 DROP，需新连接写终态
                )
                await bg_service.execute_restore(restore_record_id, source_abs_path)

        request.app.add_task(run_restore())

        return json(
            {
                "code": 0,
                "message": "恢复任务已创建",
                "data": BackupService._record_to_dict(record),
            },
            status=201,
        )
    except Exception as e:
        logger.error("创建备份恢复任务失败: %s", e)
        return json({"code": 500, "message": f"创建失败: {str(e)}"}, status=500)


@backup_bp.get("/records/<record_id:int>/download")
@auth_required
@require_permission("system:database_backup")
async def download_backup(request: Request, record_id: int):
    """下载备份文件（流式）"""
    from pathlib import Path

    from sanic.response import file as response_file

    try:
        service = BackupService(db=request.ctx.db_session)
        record = await service.get_record(record_id)

        if not record.file_path:
            return json({"code": 400, "message": "该记录无备份文件"}, status=400)

        # 路径安全：文件必须位于 backup_dir 内（防路径穿越）
        try:
            abs_path: Path = service._abs_path(record.file_path)
        except ValueError:
            return json({"code": 400, "message": "备份文件路径非法"}, status=400)

        if not abs_path.is_file():
            return json({"code": 404, "message": "备份文件不存在"}, status=404)

        return await response_file(
            str(abs_path), filename=abs_path.name, mime_type="application/octet-stream"
        )
    except ValueError as e:
        return json({"code": 404, "message": str(e)}, status=404)
    except Exception as e:
        logger.error("下载备份文件失败: %s", e)
        return json({"code": 500, "message": f"下载失败: {str(e)}"}, status=500)
