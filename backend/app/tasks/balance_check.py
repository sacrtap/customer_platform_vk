"""
P6-4: 余额预警检查任务
每小时检查客户余额，标记预警状态
"""

import logging
from datetime import datetime
from typing import List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.customers import Customer
from ..models.billing import CustomerBalance

logger = logging.getLogger(__name__)

# 预警阈值配置
WARNING_THRESHOLD = 1000  # 余额低于 1000 元预警
CRITICAL_THRESHOLD = 500  # 余额低于 500 元严重预警


async def check_balance_warning(session: AsyncSession):
    """
    检查客户余额预警

    执行时间：每小时
    职责：检查所有客户余额，标记预警状态
    """
    logger.info("⚠️ 开始执行余额预警检查任务")

    try:
        # 获取所有活跃客户及其余额
        result = await session.execute(
            select(Customer, CustomerBalance)
            .join(CustomerBalance, Customer.id == CustomerBalance.customer_id)
            .where(Customer.deleted_at.is_(None))
        )
        rows = result.all()

        logger.info(f"📋 待检查客户数量：{len(rows)}")

        # 统计结果
        warning_count = 0
        critical_count = 0
        normal_count = 0

        for customer, balance in rows:
            total_balance = balance.actual_balance + balance.gift_balance

            try:
                if total_balance <= CRITICAL_THRESHOLD:
                    # 严重预警
                    if customer.balance_warning_level != "critical":
                        await session.execute(
                            update(Customer)
                            .where(Customer.id == customer.id)
                            .values(
                                balance_warning_level="critical",
                                balance_warning_updated_at=datetime.utcnow(),
                            )
                        )
                        critical_count += 1
                        logger.warning(
                            f"🚨 客户 {customer.company_name} 余额严重不足 | "
                            f"总余额：{total_balance:.2f} 元"
                        )
                    else:
                        normal_count += 1

                elif total_balance <= WARNING_THRESHOLD:
                    # 预警
                    if customer.balance_warning_level != "warning":
                        await session.execute(
                            update(Customer)
                            .where(Customer.id == customer.id)
                            .values(
                                balance_warning_level="warning",
                                balance_warning_updated_at=datetime.utcnow(),
                            )
                        )
                        warning_count += 1
                        logger.warning(
                            f"⚠️  客户 {customer.company_name} 余额不足 | "
                            f"总余额：{total_balance:.2f} 元"
                        )
                    else:
                        normal_count += 1

                else:
                    # 正常
                    if customer.balance_warning_level is not None:
                        await session.execute(
                            update(Customer)
                            .where(Customer.id == customer.id)
                            .values(
                                balance_warning_level=None,
                                balance_warning_updated_at=datetime.utcnow(),
                            )
                        )
                    normal_count += 1

            except Exception as e:
                logger.error(f"❌ 客户 {customer.company_name} 余额检查失败：{str(e)}")
                continue

        await session.commit()

        logger.info(
            f"✅ 余额预警检查完成 | "
            f"正常：{normal_count} | "
            f"预警：{warning_count} | "
            f"严重预警：{critical_count}"
        )

        # 记录任务日志
        await _log_check_task(
            session,
            task_name="check_balance_warning",
            status="success",
            total_count=len(rows),
            warning_count=warning_count,
            critical_count=critical_count,
            normal_count=normal_count,
            executed_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"❌ 余额预警检查任务执行失败：{str(e)}")
        try:
            await _log_check_task(
                session,
                task_name="check_balance_warning",
                status="failed",
                total_count=0,
                warning_count=0,
                critical_count=0,
                normal_count=0,
                executed_at=datetime.utcnow(),
                error_message=str(e),
            )
        except:
            pass
        await session.rollback()
        raise


async def _log_check_task(
    session: AsyncSession,
    task_name: str,
    status: str,
    total_count: int,
    warning_count: int,
    critical_count: int,
    normal_count: int,
    executed_at: datetime,
    error_message: str = None,
):
    """记录检查任务日志"""
    from ..models.billing import SyncTaskLog

    log_entry = SyncTaskLog(
        task_name=task_name,
        status=status,
        total_count=total_count,
        success_count=normal_count,
        failed_count=critical_count,
        skipped_count=warning_count,
        executed_at=executed_at.strftime("%Y-%m-%d %H:%M:%S"),
        error_message=error_message,
    )
    session.add(log_entry)
    await session.commit()
