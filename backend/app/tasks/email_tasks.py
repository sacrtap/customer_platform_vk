"""
P6-7: 逾期提醒邮件任务
每日 9 点发送逾期账单提醒给商务
"""

import logging
from datetime import datetime, date
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.invoice import Invoice, InvoiceStatus
from ..models.customer import Customer
from ..models.user import User

logger = logging.getLogger(__name__)


async def send_overdue_emails(session: AsyncSession):
    """
    发送逾期账单提醒邮件

    执行时间：每日 09:00
    职责：向商务发送逾期账单提醒
    """
    logger.info("📧 开始执行逾期提醒邮件任务")

    try:
        # 获取所有逾期未付款的结算单
        result = await session.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.customer), selectinload(Invoice.created_by_user)
            )
            .where(
                Invoice.status == InvoiceStatus.OVERDUE, Invoice.deleted_at.is_(None)
            )
        )
        invoices = result.scalars().all()

        logger.info(f"📋 逾期结算单数量：{len(invoices)}")

        if not invoices:
            logger.info("✅ 无逾期结算单，任务结束")
            return

        # 按商务分组
        sales_invoices = {}
        for invoice in invoices:
            creator = invoice.created_by_user
            if creator and creator.email:
                if creator.email not in sales_invoices:
                    sales_invoices[creator.email] = {"user": creator, "invoices": []}
                sales_invoices[creator.email]["invoices"].append(invoice)

        # 统计结果
        sent_count = 0
        failed_count = 0

        # 从服务导入
        from ..services.email import get_email_service

        email_service = get_email_service()

        for email, data in sales_invoices.items():
            try:
                user = data["user"]
                invoices_list = data["invoices"]

                # 渲染邮件模板
                html_content = email_service.render_template(
                    "overdue_invoice_reminder.html",
                    user_name=user.name,
                    invoices=invoices_list,
                    today=date.today(),
                )

                # 发送邮件
                success = await email_service.send_email(
                    to_emails=[email],
                    subject=f"【逾期提醒】您有 {len(invoices_list)} 笔结算单待跟进",
                    html_content=html_content,
                )

                if success:
                    sent_count += 1
                    logger.info(
                        f"✅ 邮件发送成功：{email}, 结算单数：{len(invoices_list)}"
                    )
                else:
                    failed_count += 1
                    logger.error(f"❌ 邮件发送失败：{email}")

            except Exception as e:
                failed_count += 1
                logger.error(f"❌ 邮件发送异常 {email}: {str(e)}")
                continue

        logger.info(
            f"✅ 逾期提醒邮件发送完成 | 成功：{sent_count} | 失败：{failed_count}"
        )

        # 记录任务日志
        await _log_email_task(
            session,
            task_name="send_overdue_emails",
            status="success" if failed_count == 0 else "partial",
            total_count=len(sales_invoices),
            sent_count=sent_count,
            failed_count=failed_count,
            executed_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"❌ 逾期提醒邮件任务执行失败：{str(e)}")
        try:
            await _log_email_task(
                session,
                task_name="send_overdue_emails",
                status="failed",
                total_count=0,
                sent_count=0,
                failed_count=0,
                executed_at=datetime.utcnow(),
                error_message=str(e),
            )
        except:
            pass
        await session.rollback()
        raise


async def _log_email_task(
    session: AsyncSession,
    task_name: str,
    status: str,
    total_count: int,
    sent_count: int,
    failed_count: int,
    executed_at: datetime,
    error_message: str = None,
):
    """记录邮件任务日志"""
    from ..models.billing import SyncTaskLog

    log_entry = SyncTaskLog(
        task_name=task_name,
        status=status,
        total_count=total_count,
        success_count=sent_count,
        failed_count=failed_count,
        skipped_count=0,
        executed_at=executed_at.strftime("%Y-%m-%d %H:%M:%S"),
        error_message=error_message,
    )
    session.add(log_entry)
    await session.commit()
