"""
APScheduler 任务调度器

支持任务监控：每个任务的执行状态、耗时和错误信息记录到 Redis。
通过 /api/v1/system/scheduler-status 可查看调度器状态。
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sanic.response import json

from ..middleware.auth import auth_required, require_permission
from .monitor import get_task_results, monitored_task

logger = logging.getLogger(__name__)

# 创建全局调度器实例
scheduler = AsyncIOScheduler()


def init_scheduler(app):
    """初始化任务调度器"""

    # 存储 session 工厂供任务使用
    session_factory = None

    @app.before_server_start
    async def start_scheduler(app, loop):
        """启动调度器"""
        nonlocal session_factory
        # 获取 session 工厂
        session_factory = app.ctx.async_session_maker

        # 导入任务函数
        from ..cache.base import cache_service
        from ..services.sync_task_service import SyncTaskService
        from .balance_check import check_balance_warning
        from .cost_calc import calc_daily_cost
        from .email_tasks import send_overdue_emails
        from .file_cleanup import cleanup_temp_files
        from .invoice_generator import generate_monthly_invoices
        from .order_sync import sync_daily_orders
        from .webhook_cleanup import cleanup_webhook_signatures

        # 为每个任务添加监控装饰器
        @monitored_task("generate_monthly_invoices", "月度结算单自动生成")
        async def _generate_monthly_invoices(session):
            return await generate_monthly_invoices(session)

        @monitored_task("check_balance_warning", "余额预警检查")
        async def _check_balance_warning(session):
            return await check_balance_warning(session)

        @monitored_task("send_overdue_emails", "逾期提醒邮件")
        async def _send_overdue_emails(session):
            return await send_overdue_emails(session)

        @monitored_task("cleanup_temp_files", "临时文件清理")
        async def _cleanup_temp_files():
            return await cleanup_temp_files()

        @monitored_task("cleanup_webhook_signatures", "Webhook 签名清理")
        async def _cleanup_webhook_signatures(session):
            return await cleanup_webhook_signatures(session)

        @monitored_task("sync_daily_orders", "每日订单同步")
        async def _sync_daily_orders(session, engine):
            return await sync_daily_orders(session, engine)

        @monitored_task("calc_daily_cost", "每日费用计算")
        async def _calc_daily_cost(session):
            return await calc_daily_cost(session)

        @monitored_task("check_stuck_sync_tasks", "卡住同步任务检测")
        async def _check_stuck_sync_tasks():
            redis_client = await cache_service._get_redis()
            async with session_factory() as session:  # pyright: ignore[reportOptionalCall]
                service = SyncTaskService(db=session, redis_client=redis_client)
                recovered = await service.check_stuck_tasks(max_running_minutes=60)
                if recovered > 0:
                    logger.warning(f"检测到 {recovered} 个卡住的同步任务，已标记为失败")
                return {"recovered": recovered}

        # 添加定时任务 - 使用 lambda 传递 session

        # P6-3: 每月 1 日 02:00 自动生成结算单
        scheduler.add_job(
            lambda: _generate_monthly_invoices(session_factory()),  # pyright: ignore[reportOptionalCall]
            trigger=CronTrigger(day=1, hour=2, minute=0),
            id="generate_monthly_invoices",
            name="月度结算单自动生成",
            replace_existing=True,
        )

        # P6-4: 每小时检查余额预警
        scheduler.add_job(
            lambda: _check_balance_warning(session_factory()),  # pyright: ignore[reportOptionalCall]
            trigger=IntervalTrigger(hours=1),
            id="check_balance_warning",
            name="余额预警检查",
            replace_existing=True,
        )

        # P6-7: 每日 09:00 发送逾期提醒邮件
        scheduler.add_job(
            lambda: _send_overdue_emails(session_factory()),  # pyright: ignore[reportOptionalCall]
            trigger=CronTrigger(hour=9, minute=0),
            id="send_overdue_emails",
            name="逾期提醒邮件",
            replace_existing=True,
        )

        # P6-10: 每日 03:00 清理临时文件 (不需要 session)
        scheduler.add_job(
            _cleanup_temp_files,
            trigger=CronTrigger(hour=3, minute=0),
            id="cleanup_temp_files",
            name="临时文件清理",
            replace_existing=True,
        )

        # P6-8: 每日 04:00 清理 Webhook 签名（5 天前）
        scheduler.add_job(
            lambda: _cleanup_webhook_signatures(session_factory()),  # pyright: ignore[reportOptionalCall]
            trigger=CronTrigger(hour=4, minute=0),
            id="cleanup_webhook_signatures",
            name="Webhook 签名清理",
            replace_existing=True,
        )

        # 消耗分析增强：每日 01:00 同步订单
        scheduler.add_job(
            lambda: _sync_daily_orders(session_factory(), app.ctx.external_mysql_engine),  # pyright: ignore[reportOptionalCall]
            trigger=CronTrigger(hour=1, minute=0),
            id="sync_daily_orders",
            name="每日订单同步",
            replace_existing=True,
        )

        # 消耗分析增强：每日 01:30 计算费用
        scheduler.add_job(
            lambda: _calc_daily_cost(session_factory()),  # pyright: ignore[reportOptionalCall]
            trigger=CronTrigger(hour=1, minute=30),
            id="calc_daily_cost",
            name="每日费用计算",
            replace_existing=True,
        )

        # 卡住任务检测：每小时检查一次运行超过 60 分钟的同步任务
        scheduler.add_job(
            _check_stuck_sync_tasks,
            trigger=IntervalTrigger(hours=1),
            id="check_stuck_sync_tasks",
            name="卡住同步任务检测",
            replace_existing=True,
        )

        # 启动调度器
        scheduler.start()
        logger.info("📅 任务调度器已启动")

        # 记录已注册的任务
        for job in scheduler.get_jobs():
            logger.info(f"  └─ 已注册任务：{job.name} - {job.trigger}")

    @app.after_server_stop
    async def stop_scheduler(app, loop):
        """停止调度器"""
        if scheduler.running:
            scheduler.shutdown()
            logger.info("📅 任务调度器已停止")

    # 注册调度器状态查看路由
    @app.get("/api/v1/system/scheduler-status")
    @auth_required
    @require_permission("system:view")
    async def scheduler_status(request):
        """获取调度器状态和任务执行记录"""
        from ..cache.base import cache_service

        jobs_info = []
        job_ids = []
        for job in scheduler.get_jobs():
            job_ids.append(job.id)
            next_run = job.next_run_time
            jobs_info.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "trigger": str(job.trigger),
                    "next_run_time": next_run.isoformat() if next_run else None,
                    "is_running": scheduler.get_job(job.id) is not None,
                }
            )

        # 获取最近执行结果
        redis_client = await cache_service._get_redis()
        task_results = await get_task_results(redis_client, job_ids)

        # 合并任务信息和执行结果
        results_map = {r["job_id"]: r for r in task_results}
        for job_info in jobs_info:
            result = results_map.get(job_info["id"], {})
            job_info["last_execution"] = {
                "status": result.get("status", "never_executed"),
                "duration_ms": result.get("duration_ms"),
                "executed_at": result.get("executed_at"),
                "error": result.get("error"),
            }

        # 统计
        total = len(jobs_info)
        healthy = sum(1 for j in jobs_info if j["last_execution"]["status"] == "success")
        failed = sum(1 for j in jobs_info if j["last_execution"]["status"] == "failed")
        never_run = sum(1 for j in jobs_info if j["last_execution"]["status"] == "never_executed")

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "scheduler_running": scheduler.running,
                    "total_jobs": total,
                    "healthy_jobs": healthy,
                    "failed_jobs": failed,
                    "never_executed_jobs": never_run,
                    "jobs": jobs_info,
                },
            }
        )

    return scheduler


def get_scheduler() -> AsyncIOScheduler:
    """获取调度器实例"""
    return scheduler
