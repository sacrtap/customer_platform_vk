"""数据备份定时任务

提供纯执行函数（供 scheduler 闭包调用）与动态注册函数（仿 register_sync_daily_auto）。
恢复为手动触发，不在 scheduler 注册。
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.backup import BackupScheduleConfig
from ..services.backup_service import BACKUP_TASK_NAME, BackupService
from ..utils.timezone import CST

logger = logging.getLogger(__name__)

BACKUP_JOB_ID = "backup_daily_auto"
CLEANUP_JOB_ID = "cleanup_old_backups"


async def perform_backup_task(session: AsyncSession) -> None:
    """执行一次每日自动备份（系统触发，operator_id=None）"""
    service = BackupService(db=session)
    if await service.has_active_task():
        logger.info("已有备份任务正在执行，跳过本次每日备份")
        return
    record = await service.create_record("daily_backup", operator_id=None)
    await service.execute_backup(record.id)


async def perform_cleanup_task(session: AsyncSession) -> None:
    """执行一次过期备份清理（含保留窗口校验）"""
    service = BackupService(db=session)
    if await service.has_active_task():
        logger.info("已有备份任务正在执行，跳过本次过期清理")
        return
    await service.execute_cleanup()


def register_backup_daily(
    scheduler: AsyncIOScheduler, session_factory, enabled: bool, backup_time: str
) -> None:
    """按配置注册/注销「每日数据库备份」job

    - enabled=True: 以 CronTrigger(hour, minute) 注册 job（幂等 replace_existing）
    - enabled=False: 移除已注册的 job（不存在则忽略）
    """
    if scheduler.get_job(BACKUP_JOB_ID):
        scheduler.remove_job(BACKUP_JOB_ID)

    if not enabled:
        return

    hour, minute = map(int, backup_time.split(":"))

    from .monitor import monitored_task

    @monitored_task(BACKUP_JOB_ID, "每日数据库备份")
    async def _run():
        async with session_factory() as session:  # pyright: ignore[reportOptionalCall]
            # 二次校验配置（页面可能刚关闭）
            cfg_result = await session.execute(
                select(BackupScheduleConfig).where(
                    BackupScheduleConfig.task_name == BACKUP_TASK_NAME
                )
            )
            cfg = cfg_result.scalar_one_or_none()
            if cfg is None or not cfg.enabled:
                logger.info("每日数据库备份已停用，跳过本次执行")
                return

            await perform_backup_task(session)

    scheduler.add_job(
        _run,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=CST),
        id=BACKUP_JOB_ID,
        name="每日数据库备份",
        replace_existing=True,
    )
    logger.info(f"📅 每日数据库备份已注册: 每日 {backup_time}")
