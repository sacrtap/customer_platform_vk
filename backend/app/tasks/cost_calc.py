"""费用计算定时任务"""

import logging
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.billing import SyncTaskLog
from ..services.cost_calc import CostCalcService

logger = logging.getLogger(__name__)


async def calc_daily_cost(session: AsyncSession):
    """
    计算每日费用

    执行时间：每日 01:30
    职责：根据 daily_orders 和 pricing_rules 计算每日费用到 daily_consumption 表
    """
    logger.info("💰 开始执行每日费用计算任务")

    try:
        # 创建服务实例
        service = CostCalcService(session)

        # 执行计算
        result = await service.calculate_daily_cost(consumption_date=date.today())

        # 记录任务日志
        await _log_calc_task(
            session=session,
            task_name="cost_calc",
            status="success",
            total_count=result["total_customers"],
            calculated_count=result["calculated"],
            no_rule_count=result["no_rule"],
            executed_at=datetime.now(),
            error_message=None,
        )

        logger.info(
            f"✅ 每日费用计算任务完成：总客户={result['total_customers']}, "
            f"有规则={result['calculated']}, 无规则={result['no_rule']}"
        )

    except Exception as e:
        logger.error(f"❌ 每日费用计算任务执行失败：{str(e)}")

        # 记录失败日志
        await _log_calc_task(
            session=session,
            task_name="cost_calc",
            status="failed",
            total_count=0,
            calculated_count=0,
            no_rule_count=0,
            executed_at=datetime.now(),
            error_message=str(e),
        )

        raise


async def _log_calc_task(
    session: AsyncSession,
    task_name: str,
    status: str,
    total_count: int,
    calculated_count: int,
    no_rule_count: int,
    executed_at: datetime,
    error_message: str = None,
):
    """记录费用计算任务日志"""
    log_entry = SyncTaskLog(
        task_name=task_name,
        status=status,
        total_count=total_count,
        success_count=calculated_count,
        failed_count=no_rule_count,
        skipped_count=0,
        executed_at=executed_at,
        error_message=error_message,
    )
    session.add(log_entry)
    await session.commit()
