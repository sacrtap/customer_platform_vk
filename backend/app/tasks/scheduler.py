"""
APScheduler 任务调度器

支持任务监控：每个任务的执行状态、耗时和错误信息记录到 Redis。
通过 /api/v1/system/scheduler-status 可查看调度器状态。
"""

import logging
from datetime import date, timedelta

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
        from .email_tasks import send_overdue_emails
        from .file_cleanup import cleanup_temp_files
        from .invoice_generator import generate_monthly_invoices
        from .webhook_cleanup import cleanup_webhook_signatures

        # 为每个任务添加监控装饰器
        # 任务一律声明为「无参协程 + 函数内取 session」：APScheduler 能直接调度协程
        # 函数；若改成 lambda 包裹并在注册处调用 session_factory()，协程对象会被创建
        # 后立即丢弃（RuntimeWarning: coroutine ... was never awaited），任务静默不执行。
        @monitored_task("generate_monthly_invoices", "月度结算单自动生成")
        async def _generate_monthly_invoices():
            async with session_factory() as session:  # pyright: ignore[reportOptionalCall]
                return await generate_monthly_invoices(session)

        @monitored_task("check_balance_warning", "余额预警检查")
        async def _check_balance_warning():
            async with session_factory() as session:  # pyright: ignore[reportOptionalCall]
                return await check_balance_warning(session)

        @monitored_task("send_overdue_emails", "逾期提醒邮件")
        async def _send_overdue_emails():
            async with session_factory() as session:  # pyright: ignore[reportOptionalCall]
                return await send_overdue_emails(session)

        @monitored_task("cleanup_temp_files", "临时文件清理")
        async def _cleanup_temp_files():
            return await cleanup_temp_files()

        @monitored_task("cleanup_webhook_signatures", "Webhook 签名清理")
        async def _cleanup_webhook_signatures():
            async with session_factory() as session:  # pyright: ignore[reportOptionalCall]
                return await cleanup_webhook_signatures(session)

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
            _generate_monthly_invoices,
            trigger=CronTrigger(day=1, hour=2, minute=0),
            id="generate_monthly_invoices",
            name="月度结算单自动生成",
            replace_existing=True,
        )

        # P6-4: 每小时检查余额预警
        scheduler.add_job(
            _check_balance_warning,
            trigger=IntervalTrigger(hours=1),
            id="check_balance_warning",
            name="余额预警检查",
            replace_existing=True,
        )

        # P6-7: 每日 09:00 发送逾期提醒邮件
        scheduler.add_job(
            _send_overdue_emails,
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
            _cleanup_webhook_signatures,
            trigger=CronTrigger(hour=4, minute=0),
            id="cleanup_webhook_signatures",
            name="Webhook 签名清理",
            replace_existing=True,
        )

        # 每日自动同步（原 01:00 订单同步 + 01:30 费用计算合并为单个任务）：
        # 按 sync_schedule_configs 配置注册/不注册，支持页面动态调整
        from sqlalchemy import select as sa_select

        from ..models.sync_schedule import SyncScheduleConfig

        cfg = None
        try:
            async with session_factory() as cfg_session:  # pyright: ignore[reportOptionalCall]
                cfg_result = await cfg_session.execute(
                    sa_select(SyncScheduleConfig).where(
                        SyncScheduleConfig.task_name == "daily_sync"
                    )
                )
                cfg = cfg_result.scalar_one_or_none()
        except Exception as e:
            # 配置表未初始化（未迁移）时降级为不注册，不影响其他调度任务
            logger.warning(f"读取定时同步配置失败，本次不注册每日自动同步: {e}")

        if cfg and cfg.enabled:
            logger.info(f"📅 注册每日自动同步任务: {cfg.sync_time} (模式 {cfg.sync_mode})")
            register_sync_daily_auto(
                session_factory, app.ctx.external_mysql_engine, True, cfg.sync_time
            )
        else:
            logger.info("📅 每日自动同步任务未启用（可在同步日志页开启）")

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


def register_sync_daily_auto(
    session_factory, external_engine, enabled: bool, sync_time: str
) -> None:
    """按配置注册/注销「每日自动同步」job

    与原 01:00 订单同步 + 01:30 费用计算不同，合并后的单个任务复用
    SyncTaskService.create_task + execute_task 完整链路（订单→费用→数据校验→明细落库），
    目标日期 = 昨天，操作人 = 系统自动（operator_id=NULL）。

    - enabled=True: 以 CronTrigger(hour, minute) 注册 job（幂等 replace_existing）
    - enabled=False: 移除已注册的 job（不存在则忽略）
    """
    job_id = "sync_daily_auto"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    if not enabled:
        return

    hour, minute = map(int, sync_time.split(":"))

    @monitored_task("sync_daily_auto", "每日自动同步")
    async def _run():
        from sqlalchemy import select as sa_select

        from ..models.sync_schedule import SyncScheduleConfig

        async with session_factory() as session:  # pyright: ignore[reportOptionalCall]
            # 二次校验配置（页面可能刚关闭）
            cfg_result = await session.execute(
                sa_select(SyncScheduleConfig).where(SyncScheduleConfig.task_name == "daily_sync")
            )
            cfg = cfg_result.scalar_one_or_none()
            if cfg is None or not cfg.enabled:
                logger.info("每日自动同步已停用，跳过本次执行")
                return

            # 目标日期 = 昨天（外部系统订单按日上传，当日数据不完整）
            yesterday = date.today() - timedelta(days=1)

            from ..cache.base import cache_service
            from ..services.sync_task_service import DuplicateSyncTaskError, SyncTaskService

            redis_client = await cache_service._get_redis()
            service = SyncTaskService(
                db=session,
                redis_client=redis_client,
                external_engine=external_engine,
            )
            try:
                task = await service.create_task(
                    start_date=yesterday,
                    end_date=yesterday,
                    sync_mode=cfg.sync_mode,
                    operator_id=None,  # 系统自动触发
                )
                await service.execute_task(task.id)
            except DuplicateSyncTaskError as e:
                # 与手动任务同日冲突：跳过本次，不视为调度失败
                logger.warning("每日自动同步跳过（同日已有任务执行中）: %s", e)
                return
            except Exception:
                raise

    scheduler.add_job(
        _run,
        trigger=CronTrigger(hour=hour, minute=minute),
        id=job_id,
        name="每日自动同步",
        replace_existing=True,
    )
    logger.info(f"📅 每日自动同步已注册: 每日 {sync_time}")


def get_scheduler() -> AsyncIOScheduler:
    """获取调度器实例"""
    return scheduler
