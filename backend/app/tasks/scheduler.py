"""
APScheduler 任务调度器
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

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
        from .usage_sync import sync_daily_usage
        from .invoice_generator import generate_monthly_invoices
        from .balance_check import check_balance_warning
        from .email_tasks import send_overdue_emails
        from .file_cleanup import cleanup_temp_files
        from .webhook_cleanup import cleanup_webhook_signatures

        # 添加定时任务 - 使用 lambda 传递 session
        # P6-2: 每日 00:00 同步用量
        scheduler.add_job(
            lambda: sync_daily_usage(session_factory()),
            trigger=CronTrigger(hour=0, minute=0),
            id="sync_daily_usage",
            name="每日用量同步",
            replace_existing=True,
        )

        # P6-3: 每月 1 日 02:00 自动生成结算单
        scheduler.add_job(
            lambda: generate_monthly_invoices(session_factory()),
            trigger=CronTrigger(day=1, hour=2, minute=0),
            id="generate_monthly_invoices",
            name="月度结算单自动生成",
            replace_existing=True,
        )

        # P6-4: 每小时检查余额预警
        scheduler.add_job(
            lambda: check_balance_warning(session_factory()),
            trigger=IntervalTrigger(hours=1),
            id="check_balance_warning",
            name="余额预警检查",
            replace_existing=True,
        )

        # P6-7: 每日 09:00 发送逾期提醒邮件
        scheduler.add_job(
            lambda: send_overdue_emails(session_factory()),
            trigger=CronTrigger(hour=9, minute=0),
            id="send_overdue_emails",
            name="逾期提醒邮件",
            replace_existing=True,
        )

        # P6-10: 每日 03:00 清理临时文件 (不需要 session)
        scheduler.add_job(
            cleanup_temp_files,
            trigger=CronTrigger(hour=3, minute=0),
            id="cleanup_temp_files",
            name="临时文件清理",
            replace_existing=True,
        )

        # P6-8: 每日 04:00 清理 Webhook 签名（5 天前）
        scheduler.add_job(
            lambda: cleanup_webhook_signatures(session_factory()),
            trigger=CronTrigger(hour=4, minute=0),
            id="cleanup_webhook_signatures",
            name="Webhook 签名清理",
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

    return scheduler


def get_scheduler() -> AsyncIOScheduler:
    """获取调度器实例"""
    return scheduler
