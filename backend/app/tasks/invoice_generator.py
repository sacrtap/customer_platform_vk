"""
P6-3: 月度结算单自动生成任务
为非重点客户自动生成上月结算单
"""

import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.customers import Customer
from ..models.billing import Invoice

logger = logging.getLogger(__name__)


async def generate_monthly_invoices(session: AsyncSession):
    """
    自动生成月度结算单

    执行时间：每月 1 日 02:00
    职责：为非重点客户自动生成上月结算单
    """
    logger.info("📝 开始执行月度结算单自动生成任务")

    try:
        # 计算上月日期范围
        today = date.today()
        first_day_of_last_month = today.replace(day=1) - relativedelta(months=1)
        last_day_of_last_month = first_day_of_last_month + relativedelta(months=1, days=-1)

        logger.info(f"📊 结算周期：{first_day_of_last_month} 至 {last_day_of_last_month}")

        # 获取非重点客户（普通客户自动生成，重点客户需要手动出账）
        result = await session.execute(
            select(Customer).where(
                Customer.deleted_at.is_(None),
                Customer.is_key_customer.is_(False),  # 非重点客户
            )
        )
        customers = result.scalars().all()

        logger.info(f"📋 待生成结算单客户数量：{len(customers)}")

        # 统计结果
        generated_count = 0
        skipped_count = 0
        failed_count = 0

        # 从服务导入
        from ..services.billing import InvoiceService

        invoice_service = InvoiceService(session)

        for customer in customers:
            try:
                # 检查是否已存在该周期的结算单
                existing = await session.execute(
                    select(Invoice).where(
                        Invoice.customer_id == customer.id,
                        Invoice.period_start == first_day_of_last_month,
                        Invoice.period_end == last_day_of_last_month,
                    )
                )
                if existing.scalar_one_or_none():
                    logger.debug(f"⏭️  客户 {customer.company_name} 已存在结算单，跳过")
                    skipped_count += 1
                    continue

                # 生成结算单
                invoice = await invoice_service.generate_invoice(
                    customer_id=customer.id,
                    period_start=first_day_of_last_month,
                    period_end=last_day_of_last_month,
                    items=[],  # 需要从用量数据生成
                    created_by=1,  # 系统生成
                    is_auto_generated=True,
                )

                if invoice:
                    generated_count += 1
                    logger.debug(
                        f"✅ 客户 {customer.company_name} 结算单生成成功，金额：{invoice.final_amount}"
                    )
                else:
                    skipped_count += 1
                    logger.debug(f"⚠️  客户 {customer.company_name} 无用量数据，跳过结算单生成")

            except Exception as e:
                failed_count += 1
                logger.error(f"❌ 客户 {customer.company_name} 结算单生成失败：{str(e)}")
                continue

        logger.info(
            f"✅ 月度结算单自动生成完成 | "
            f"生成：{generated_count} | "
            f"跳过：{skipped_count} | "
            f"失败：{failed_count}"
        )

        # 记录同步任务日志
        await _log_generation_task(
            session,
            task_name="generate_monthly_invoices",
            status="success" if failed_count == 0 else "partial",
            total_count=len(customers),
            generated_count=generated_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            executed_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"❌ 月度结算单自动生成任务执行失败：{str(e)}")
        try:
            await _log_generation_task(
                session,
                task_name="generate_monthly_invoices",
                status="failed",
                total_count=0,
                generated_count=0,
                failed_count=0,
                skipped_count=0,
                executed_at=datetime.utcnow(),
                error_message=str(e),
            )
        except Exception as log_err:
            logger.error(f"记录任务日志失败: {log_err}")
        await session.rollback()
        raise


async def _log_generation_task(
    session: AsyncSession,
    task_name: str,
    status: str,
    total_count: int,
    generated_count: int,
    failed_count: int,
    skipped_count: int,
    executed_at: datetime,
    error_message: str = None,
):
    """记录生成任务日志"""
    from ..models.billing import SyncTaskLog

    log_entry = SyncTaskLog(
        task_name=task_name,
        status=status,
        total_count=total_count,
        success_count=generated_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        executed_at=executed_at.strftime("%Y-%m-%d %H:%M:%S"),
        error_message=error_message,
    )
    session.add(log_entry)
    await session.commit()
