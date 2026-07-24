"""同步任务 API 路由"""

import logging
from datetime import date
from uuid import UUID

from sanic import Blueprint, Request
from sanic.response import json

from app.cache.base import cache_service
from app.middleware.auth import auth_required
from app.services.sync_task_service import SyncTaskService

logger = logging.getLogger(__name__)

sync_tasks_bp = Blueprint("sync_tasks", url_prefix="/api/v1/sync-tasks")


@sync_tasks_bp.get("")
@auth_required
async def list_sync_tasks(request: Request):
    """获取同步任务列表"""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        status = request.args.get("status")

        service = SyncTaskService(db=request.ctx.db_session)
        result = await service.list_tasks(page=page, page_size=page_size, status=status)

        return json({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        return json({"code": 500, "message": f"获取任务列表失败: {str(e)}"}, status=500)


@sync_tasks_bp.get("/stats")
@auth_required
async def get_sync_task_stats(request: Request):
    """获取同步任务统计数据"""
    try:
        service = SyncTaskService(db=request.ctx.db_session)
        stats = await service.get_stats()

        return json({"code": 0, "data": stats})
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        return json({"code": 500, "message": f"获取统计数据失败: {str(e)}"}, status=500)


@sync_tasks_bp.get("/status")
@auth_required
async def get_sync_status(request: Request):
    """获取同步状态摘要（用于首页同步状态条）"""
    try:
        service = SyncTaskService(db=request.ctx.db_session)
        stats = await service.get_stats()

        # 从 stats 中提取同步状态信息
        error_count = stats.get("failed_count", 0)
        today_total = stats.get("today_total", 0)
        today_success = stats.get("today_success", 0)
        rate = round(today_success / today_total * 100, 1) if today_total > 0 else 0

        # 最近同步时间
        last_sync = stats.get("last_sync_time")
        if last_sync:
            last_sync_str = (
                last_sync.strftime("%H:%M") if hasattr(last_sync, "strftime") else str(last_sync)
            )
        else:
            last_sync_str = None

        return json(
            {
                "code": 0,
                "data": {
                    "status": "ok" if error_count == 0 else "warning",
                    "last_sync": last_sync_str,
                    "next_sync": None,
                    "sync_rate": rate,
                    "error_count": error_count,
                },
            }
        )
    except Exception as e:
        logger.error(f"获取同步状态失败: {e}")
        return json({"code": 500, "message": f"获取同步状态失败: {str(e)}"}, status=500)


@sync_tasks_bp.post("")
@auth_required
async def create_sync_task(request: Request):
    """创建同步任务"""
    try:
        data = request.json
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        sync_mode = data.get("sync_mode", "skip_existing")

        # 参数校验
        if not start_date or not end_date:
            return json(
                {"code": 400, "message": "开始日期和结束日期不能为空"},
                status=400,
            )

        if sync_mode not in ["skip_existing", "force_overwrite"]:
            return json(
                {"code": 400, "message": "无效的同步模式"},
                status=400,
            )

        # 解析日期
        try:
            start_date = date.fromisoformat(start_date)
            end_date = date.fromisoformat(end_date)
        except ValueError:
            return json(
                {"code": 400, "message": "日期格式错误，应为 YYYY-MM-DD"},
                status=400,
            )

        # 获取操作人
        operator_id = request.ctx.user["user_id"]

        # 检查 Redis 是否可用（同步任务依赖 Redis 做分布式锁和进度跟踪）
        redis_available = await cache_service.check_redis_available()
        if not redis_available:
            return json(
                {
                    "code": 503,
                    "message": "Redis 缓存服务未启动，无法创建同步任务。请先启动 Redis 服务（如 brew services start redis）",
                },
                status=503,
            )

        # 创建服务
        redis_client = await cache_service._get_redis()
        service = SyncTaskService(db=request.ctx.db_session, redis_client=redis_client)

        # 创建任务
        task = await service.create_task(
            start_date=start_date,
            end_date=end_date,
            sync_mode=sync_mode,
            operator_id=operator_id,
        )

        # 启动后台任务（使用独立的数据库 session）
        async_session_maker = request.app.ctx.async_session_maker

        async def run_task():
            async with async_session_maker() as new_session:
                bg_service = SyncTaskService(db=new_session, redis_client=redis_client)
                await bg_service.execute_task(task.id)

        request.app.add_task(run_task())

        return json(
            {
                "code": 0,
                "message": "任务创建成功",
                "data": {
                    "task_id": str(task.id),
                    "status": task.status,
                    "sync_mode": task.sync_mode,
                    "total_days": task.total_days,
                },
            },
            status=201,
        )

    except ValueError as e:
        return json({"code": 400, "message": str(e)}, status=400)
    except Exception as e:
        if "已有相同周期的同步任务正在执行" in str(e):
            return json({"code": 409, "message": str(e)}, status=409)
        # Redis 连接异常给出友好提示
        err_str = str(e)
        if "connecting to" in err_str and "6379" in err_str:
            logger.error(f"创建同步任务失败（Redis 不可用）: {e}")
            return json(
                {
                    "code": 503,
                    "message": "Redis 缓存服务未启动，无法创建同步任务。请先启动 Redis 服务（如 brew services start redis）",
                },
                status=503,
            )
        logger.error(f"创建同步任务失败: {e}")
        return json({"code": 500, "message": f"创建任务失败: {err_str}"}, status=500)


@sync_tasks_bp.get("/<task_id:uuid>")
@auth_required
async def get_sync_task(request: Request, task_id: UUID):
    """获取任务详情"""
    try:
        service = SyncTaskService(db=request.ctx.db_session)
        task = await service.get_task(task_id)

        return json(
            {
                "code": 0,
                "data": {
                    "task_id": str(task.id),
                    "start_date": task.start_date.isoformat(),
                    "end_date": task.end_date.isoformat(),
                    "sync_mode": task.sync_mode,
                    "status": task.status,
                    "total_days": task.total_days,
                    "completed_days": task.completed_days,
                    "skipped_days": task.skipped_days,
                    "success_count": task.success_count,
                    "failed_count": task.failed_count,
                    "operator_id": task.operator_id,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "error_message": task.error_message,
                },
            }
        )

    except ValueError as e:
        return json({"code": 404, "message": str(e)}, status=404)
    except Exception as e:
        logger.error(f"获取任务详情失败: {e}")
        return json({"code": 500, "message": f"获取任务失败: {str(e)}"}, status=500)


@sync_tasks_bp.get("/<task_id:uuid>/progress")
@auth_required
async def get_sync_task_progress(request: Request, task_id: UUID):
    """获取任务进度"""
    try:
        redis_client = await cache_service._get_redis()
        service = SyncTaskService(db=request.ctx.db_session, redis_client=redis_client)
        progress = await service.get_progress(task_id)

        return json({"code": 0, "data": progress})

    except ValueError as e:
        return json({"code": 404, "message": str(e)}, status=404)
    except Exception as e:
        err_str = str(e)
        if "connecting to" in err_str and "6379" in err_str:
            logger.error(f"获取任务进度失败（Redis 不可用）: {e}")
            return json(
                {"code": 503, "message": "Redis 缓存服务未启动，无法获取任务进度"},
                status=503,
            )
        logger.error(f"获取任务进度失败: {e}")
        return json({"code": 500, "message": f"获取进度失败: {err_str}"}, status=500)


@sync_tasks_bp.post("/<task_id:uuid>/cancel")
@auth_required
async def cancel_sync_task(request: Request, task_id: UUID):
    """取消同步任务"""
    try:
        redis_client = await cache_service._get_redis()
        service = SyncTaskService(db=request.ctx.db_session, redis_client=redis_client)

        await service.cancel_task(task_id)

        return json(
            {
                "code": 0,
                "message": "任务已取消",
            }
        )
    except ValueError as e:
        return json({"code": 400, "message": str(e)}, status=400)
    except Exception as e:
        err_str = str(e)
        if "connecting to" in err_str and "6379" in err_str:
            logger.error(f"取消任务失败（Redis 不可用）: {e}")
            return json(
                {"code": 503, "message": "Redis 缓存服务未启动，无法取消任务"},
                status=503,
            )
        logger.error(f"取消任务失败: {e}")
        return json({"code": 500, "message": f"取消失败: {err_str}"}, status=500)
