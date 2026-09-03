"""结算单明细文件异步生成任务

在结算单创建后异步生成 Excel 明细文件。
通过 APScheduler 的 add_job 即时触发。
"""

import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ..models.billing import Invoice, InvoiceItem
from ..models.customers import Customer
from ..services.invoice_excel import InvoiceExcelService

logger = logging.getLogger(__name__)


async def generate_invoice_detail(
    session: AsyncSession,
    external_engine: AsyncEngine | None,
    invoice_id: int,
):
    """异步生成结算单明细 Excel 文件

    Args:
        session: 数据库 session
        external_engine: 外部 MySQL 引擎
        invoice_id: 结算单 ID
    """
    logger.info(f"开始异步生成结算单 {invoice_id} 的明细文件")

    try:
        # 1. 查询结算单
        invoice = await session.get(Invoice, invoice_id)
        if not invoice:
            logger.error(f"结算单 {invoice_id} 不存在")
            return

        # 2. 标记为生成中
        invoice.detail_file_status = "generating"  # pyright: ignore[reportAttributeAccessIssue]
        await session.commit()

        # 3. 查询客户信息
        customer = await session.get(Customer, invoice.customer_id)
        if not customer:
            logger.error(f"结算单 {invoice_id} 的客户不存在")
            invoice.detail_file_status = "failed"  # pyright: ignore[reportAttributeAccessIssue]
            await session.commit()
            return

        # 4. 查询结算明细项获取单价
        from sqlalchemy import select

        result = await session.execute(
            select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
        )
        items = result.scalars().all()
        # 取第一项的单价作为代表（按设备类型+图层分别计价时取首个）
        unit_price = items[0].unit_price if items else None

        # 5. 获取客户的 company_id（对应外部数据库的 group_type）
        group_type = customer.company_id

        # 6. 生成 Excel
        excel_service = InvoiceExcelService(db=session, external_engine=external_engine)
        file_path = await excel_service.generate_detail_file(
            invoice_id=invoice_id,
            customer_id=invoice.customer_id,
            customer_name=customer.name,
            period_start=invoice.period_start,
            period_end=invoice.period_end,
            total_amount=invoice.total_amount,
            discount_amount=invoice.discount_amount or Decimal(0),
            unit_price=unit_price,
            group_type=group_type,
            invoice_status=invoice.status,
        )

        # 7. 更新结算单
        if file_path:
            invoice.detail_file_path = file_path  # pyright: ignore[reportAttributeAccessIssue]
            invoice.detail_file_status = "completed"  # pyright: ignore[reportAttributeAccessIssue]
            logger.info(f"结算单 {invoice_id} 明细文件生成成功: {file_path}")
        else:
            invoice.detail_file_status = "failed"  # pyright: ignore[reportAttributeAccessIssue]
            logger.warning(f"结算单 {invoice_id} 明细文件生成失败")

        await session.commit()

    except Exception as e:
        logger.error(f"结算单 {invoice_id} 明细文件生成异常: {e}", exc_info=True)
        # 尝试标记为失败
        try:
            invoice = await session.get(Invoice, invoice_id)
            if invoice:
                invoice.detail_file_status = "failed"  # pyright: ignore[reportAttributeAccessIssue]
                await session.commit()
        except Exception:
            pass
    finally:
        await session.close()
