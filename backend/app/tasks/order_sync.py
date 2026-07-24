"""订单同步定时任务"""

import logging
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ..models.billing import SyncTaskLog
from ..services.order_sync import OrderSyncService

logger = logging.getLogger(__name__)


async def sync_daily_orders(session: AsyncSession, external_engine: AsyncEngine | None = None):
    """
    同步每日订单数据

    执行时间：每日 01:00
    职责：从外部 MySQL 数据库同步订单数据到 daily_orders 表
    """
    logger.info("开始执行每日订单同步任务")

    try:
        # 创建服务实例
        service = OrderSyncService(session, external_engine=external_engine)

        # 执行同步
        result = await service.sync_orders(sync_date=date.today() - timedelta(days=1))

        # 记录同步日志
        await _log_sync_task(
            session=session,
            task_name="order_sync",
            status="success" if result.success > 0 else "failed",
            total_count=result.success + result.failed + result.skipped,
            success_count=result.success,
            failed_count=result.failed,
            skipped_count=result.skipped,
            executed_at=datetime.now(),
            error_message=result.message if result.failed > 0 else None,  # pyright: ignore[reportArgumentType]
        )

        logger.info(
            f"每日订单同步任务完成：成功={result.success}, "
            f"失败={result.failed}, 跳过={result.skipped}"
        )

    except Exception as e:
        logger.error(f"每日订单同步任务执行失败：{str(e)}")

        # 记录失败日志
        await _log_sync_task(
            session=session,
            task_name="order_sync",
            status="failed",
            total_count=0,
            success_count=0,
            failed_count=1,
            skipped_count=0,
            executed_at=datetime.now(),
            error_message=str(e),
        )

        raise


async def _log_sync_task(
    session: AsyncSession,
    task_name: str,
    status: str,
    total_count: int,
    success_count: int,
    failed_count: int,
    skipped_count: int,
    executed_at: datetime,
    error_message: str = None,  # pyright: ignore[reportArgumentType]
):
    """记录同步任务日志"""
    log_entry = SyncTaskLog(
        task_name=task_name,
        status=status,
        total_count=total_count,
        success_count=success_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        executed_at=executed_at,
        error_message=error_message,
    )
    session.add(log_entry)
    await session.commit()
