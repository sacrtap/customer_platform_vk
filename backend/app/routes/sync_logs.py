"""
同步任务日志 API
"""

from sanic import Blueprint
from sanic.response import json
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import auth_required
from ..models.billing import SyncTaskLog

sync_logs_bp = Blueprint("sync_logs", url_prefix="/api/v1/sync-logs")


@sync_logs_bp.get("/")
@auth_required
async def get_sync_logs(request):
    """
    获取同步任务日志列表

    Query Params:
        page: 页码 (default: 1)
        page_size: 每页数量 (default: 20)
        task_name: 任务名称筛选
        status: 状态筛选 (success/partial/failed)

    Response:
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [...],
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total": 100
                }
            }
        }
    """
    try:
        session: AsyncSession = request.ctx.db_session

        # 获取查询参数
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        task_name = request.args.get("task_name")
        status = request.args.get("status")

        # 构建查询
        query = select(SyncTaskLog)

        if task_name:
            query = query.where(SyncTaskLog.task_name == task_name)
        if status:
            query = query.where(SyncTaskLog.status == status)

        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar()

        # 分页排序
        query = query.order_by(desc(SyncTaskLog.executed_at))
        query = query.limit(page_size).offset((page - 1) * page_size)

        # 执行查询
        result = await session.execute(query)
        logs = result.scalars().all()

        # 格式化响应
        log_list = [
            {
                "id": log.id,
                "task_name": log.task_name,
                "status": log.status,
                "total_count": log.total_count,
                "success_count": log.success_count,
                "failed_count": log.failed_count,
                "skipped_count": log.skipped_count,
                "executed_at": log.executed_at,
                "duration_seconds": log.duration_seconds,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "list": log_list,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total": total,
                    },
                },
            }
        )

    except Exception as e:
        return json(
            {"code": 500, "message": f"查询失败：{str(e)}", "data": None},
            status=500,
        )


@sync_logs_bp.get("/stats")
@auth_required
async def get_sync_stats(request):
    """
    获取同步任务统计

    Response:
        {
            "code": 0,
            "message": "success",
            "data": {
                "total_tasks": 100,
                "success_rate": 95.5,
                "last_24h": {
                    "total": 24,
                    "success": 23,
                    "failed": 1
                },
                "by_task": [
                    {"task_name": "sync_daily_usage", "success": 30, "failed": 0},
                    ...
                ]
            }
        }
    """
    try:
        session: AsyncSession = request.ctx.db_session
        from datetime import datetime, timedelta

        # 计算 24 小时前
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)

        # 总体统计
        total_result = await session.execute(
            select(
                func.count(SyncTaskLog.id),
                func.sum(func.case((SyncTaskLog.status == "success", 1), else_=0)),
                func.sum(func.case((SyncTaskLog.status == "failed", 1), else_=0)),
            )
        )
        total_row = total_result.one()
        total_tasks = total_row[0] or 0
        success_tasks = total_row[1] or 0
        failed_tasks = total_row[2] or 0

        # 24 小时统计
        last_24h_result = await session.execute(
            select(
                func.count(SyncTaskLog.id),
                func.sum(func.case((SyncTaskLog.status == "success", 1), else_=0)),
                func.sum(func.case((SyncTaskLog.status == "failed", 1), else_=0)),
            ).where(SyncTaskLog.executed_at >= yesterday.strftime("%Y-%m-%d %H:%M:%S"))
        )
        last_24h_row = last_24h_result.one()

        # 按任务分组统计
        by_task_result = await session.execute(
            select(
                SyncTaskLog.task_name,
                func.sum(func.case((SyncTaskLog.status == "success", 1), else_=0)),
                func.sum(func.case((SyncTaskLog.status == "failed", 1), else_=0)),
            )
            .group_by(SyncTaskLog.task_name)
            .order_by(desc(func.count(SyncTaskLog.id)))
            .limit(10)
        )
        by_task = [
            {
                "task_name": row[0],
                "success": row[1] or 0,
                "failed": row[2] or 0,
            }
            for row in by_task_result.all()
        ]

        success_rate = (success_tasks / total_tasks * 100) if total_tasks > 0 else 0

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "total_tasks": total_tasks,
                    "success_rate": round(success_rate, 2),
                    "last_24h": {
                        "total": last_24h_row[0] or 0,
                        "success": last_24h_row[1] or 0,
                        "failed": last_24h_row[2] or 0,
                    },
                    "by_task": by_task,
                },
            }
        )

    except Exception as e:
        return json(
            {"code": 500, "message": f"查询失败：{str(e)}", "data": None},
            status=500,
        )
