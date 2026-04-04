"""
P6-2: 每日用量同步任务
从外部业务系统同步客户用量数据
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.customers import Customer
from ..models.billing import DailyUsage, SyncTaskLog

logger = logging.getLogger(__name__)


async def sync_daily_usage(session: AsyncSession):
    """
    同步昨日的用量数据

    执行时间：每日 00:00
    职责：从外部 API 获取所有客户昨日的用量数据并入库
    """
    logger.info("🔄 开始执行每日用量同步任务")

    try:
        # 计算昨日日期范围
        yesterday = date.today() - timedelta(days=1)
        start_of_day = datetime.combine(yesterday, datetime.min.time())
        end_of_day = datetime.combine(yesterday, datetime.max.time())

        logger.info(f"📊 同步日期范围：{yesterday}")

        # 获取所有活跃客户
        result = await session.execute(
            select(Customer).where(Customer.deleted_at.is_(None))
        )
        customers = result.scalars().all()

        logger.info(f"📋 待同步客户数量：{len(customers)}")

        # 统计结果
        success_count = 0
        failed_count = 0
        skipped_count = 0

        # 从外部 API 客户端导入
        from ..services.external_api import get_external_api_client

        api_client = get_external_api_client()

        for customer in customers:
            try:
                # 检查是否已存在该日期的记录
                existing = await session.execute(
                    select(DailyUsage).where(
                        DailyUsage.customer_id == customer.id,
                        DailyUsage.usage_date == yesterday,
                    )
                )
                if existing.scalar_one_or_none():
                    logger.debug(
                        f"⏭️  客户 {customer.company_name} 已存在 {yesterday} 用量记录，跳过"
                    )
                    skipped_count += 1
                    continue

                # 从外部 API 获取用量数据
                usage_data = await api_client.get_daily_usage(
                    customer_id=customer.external_id or customer.id,
                    start_date=yesterday,
                    end_date=yesterday,
                )

                if usage_data:
                    # 创建用量记录
                    usage_record = DailyUsage(
                        customer_id=customer.id,
                        usage_date=yesterday,
                        device_type=usage_data.get("device_type", "unknown"),
                        layer_type=usage_data.get("layer_type"),
                        quantity=usage_data.get("total_usage", 0),
                    )
                    session.add(usage_record)
                    success_count += 1
                    logger.debug(
                        f"✅ 客户 {customer.company_name} 用量同步成功：{usage_data.get('total_usage', 0)}"
                    )
                else:
                    # API 返回空数据，创建空记录标记为无数据
                    usage_record = DailyUsage(
                        customer_id=customer.id,
                        usage_date=yesterday,
                        device_type="unknown",
                        layer_type=None,
                        quantity=0,
                    )
                    session.add(usage_record)
                    skipped_count += 1
                    logger.debug(f"⚠️  客户 {customer.company_name} 无用量数据")

            except Exception as e:
                failed_count += 1
                logger.error(f"❌ 客户 {customer.company_name} 用量同步失败：{str(e)}")
                continue

        # 提交事务
        await session.commit()

        logger.info(
            f"✅ 每日用量同步完成 | "
            f"成功：{success_count} | "
            f"跳过：{skipped_count} | "
            f"失败：{failed_count}"
        )

        # 记录同步任务日志
        await _log_sync_task(
            session,
            task_name="sync_daily_usage",
            status="success" if failed_count == 0 else "partial",
            total_count=len(customers),
            success_count=success_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            executed_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"❌ 每日用量同步任务执行失败：{str(e)}")
        # 记录失败日志
        try:
            await _log_sync_task(
                session,
                task_name="sync_daily_usage",
                status="failed",
                total_count=0,
                success_count=0,
                failed_count=0,
                skipped_count=0,
                executed_at=datetime.utcnow(),
                error_message=str(e),
            )
        except:
            pass
        await session.rollback()
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
    error_message: str = None,
):
    """记录同步任务日志"""
    log_entry = SyncTaskLog(
        task_name=task_name,
        status=status,
        total_count=total_count,
        success_count=success_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        executed_at=executed_at.strftime("%Y-%m-%d %H:%M:%S"),
        error_message=error_message,
    )
    session.add(log_entry)
    await session.commit()
