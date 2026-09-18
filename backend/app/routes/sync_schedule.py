"""定时同步配置 API

管理「每日自动同步」任务的调度配置（开启/关闭、执行时间、同步模式）。
GET 需 system:view；PUT 需 system:sync_schedule（默认仅超级管理员）。
"""

import logging
import re

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy import select

from ..middleware.auth import auth_required, require_permission
from ..models.sync_schedule import SyncScheduleConfig

logger = logging.getLogger(__name__)

sync_schedule_bp = Blueprint("sync_schedule", url_prefix="/api/v1/sync-schedule")

SCHEDULE_TASK_NAME = "daily_sync"
SCHEDULE_JOB_ID = "sync_daily_auto"
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
VALID_SYNC_MODES = ("skip_existing", "force_overwrite")


async def _get_or_create_config(db_session) -> SyncScheduleConfig:
    """获取定时同步配置（不存在则创建默认行）"""
    result = await db_session.execute(
        select(SyncScheduleConfig).where(SyncScheduleConfig.task_name == SCHEDULE_TASK_NAME)
    )
    config = result.scalar_one_or_none()
    if config is None:
        config = SyncScheduleConfig(task_name=SCHEDULE_TASK_NAME)
        db_session.add(config)
        await db_session.commit()
        await db_session.refresh(config)
    return config


def _config_dict(config: SyncScheduleConfig) -> dict:
    """配置响应（含下次执行时间）"""
    from ..tasks.scheduler import get_scheduler

    scheduler = get_scheduler()
    job = scheduler.get_job(SCHEDULE_JOB_ID)
    return {
        "task_name": config.task_name,
        "enabled": bool(config.enabled),
        "sync_time": config.sync_time,
        "sync_mode": config.sync_mode,
        "next_run_time": job.next_run_time.isoformat() if job and job.next_run_time else None,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


def _reschedule_job(request: Request, enabled: bool, sync_time: str) -> None:
    """按配置动态注册/注销 APScheduler 每日自动同步 job"""
    from ..tasks.scheduler import register_sync_daily_auto

    session_factory = request.app.ctx.async_session_maker
    external_engine = getattr(request.app.ctx, "external_mysql_engine", None)
    register_sync_daily_auto(session_factory, external_engine, enabled, sync_time)


@sync_schedule_bp.get("")
@auth_required
@require_permission("system:view")
async def get_sync_schedule(request: Request):
    """获取定时同步配置"""
    try:
        db_session = request.ctx.db_session
        config = await _get_or_create_config(db_session)
        return json({"code": 0, "message": "success", "data": _config_dict(config)})
    except Exception as e:
        logger.error("获取定时同步配置失败: %s", e)
        return json({"code": 500, "message": f"获取失败: {str(e)}"}, status=500)


@sync_schedule_bp.put("")
@auth_required
@require_permission("system:sync_schedule")
async def update_sync_schedule(request: Request):
    """更新定时同步配置（部分更新，PUT 后立即动态调整调度）"""
    try:
        db_session = request.ctx.db_session
        data = request.json
        if not isinstance(data, dict):
            return json({"code": 400, "message": "请求体必须是 JSON 对象"}, status=400)

        config = await _get_or_create_config(db_session)

        # 参数校验
        sync_time = data.get("sync_time", config.sync_time)
        sync_mode = data.get("sync_mode", config.sync_mode)
        enabled = data.get("enabled", config.enabled)

        if not TIME_PATTERN.match(str(sync_time)):
            return json(
                {"code": 400, "message": "同步时间格式应为 HH:MM（24小时制），如 01:00"},
                status=400,
            )
        if sync_mode not in VALID_SYNC_MODES:
            return json({"code": 400, "message": "无效的同步模式"}, status=400)
        if not isinstance(enabled, bool):
            return json({"code": 400, "message": "enabled 必须为布尔值"}, status=400)

        # 更新配置
        config.enabled = enabled
        config.sync_time = sync_time
        config.sync_mode = sync_mode
        config.updated_by = request.ctx.user["user_id"]
        await db_session.commit()
        await db_session.refresh(config)

        # 动态调整 APScheduler job
        try:
            _reschedule_job(request, enabled, sync_time)
        except Exception as e:
            logger.error("动态调整定时任务失败: %s", e)
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
        logger.error("更新定时同步配置失败: %s", e)
        return json({"code": 500, "message": f"更新失败: {str(e)}"}, status=500)
