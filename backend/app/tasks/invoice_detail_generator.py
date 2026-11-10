"""结算单明细文件异步生成任务

在结算单创建后异步生成 Excel 明细文件。
通过 APScheduler 的 add_job 即时触发。
"""

import asyncio
import logging
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.billing import Invoice, InvoiceItem
from ..models.customers import Customer
from ..services.invoice_excel import InvoiceExcelService

logger = logging.getLogger(__name__)

# 明细生成并发上限：批量生成结算单时会为每张单 add_job 一次性并行触发（实测
# 81 张），若不限流会同时占满本地 PG 池（SQLAlchemy 默认 pool_size=5,
# overflow=10）与后到任务 30s 超时抛 QueuePool limit 错误、单置 failed。
# 取池容量同级的 5：每个任务持 1 条 PG 连接做数据查询（最长的操作），
# 其余排队等待而非失败。
# 注：月份明细已快照化（F9，读 daily_orders 本地列），不再有外部 MySQL
# 连接占用；信号量保留是为保护本地 PG 池。
_DETAIL_GEN_CONCURRENCY = 5
_detail_gen_semaphore = asyncio.Semaphore(_DETAIL_GEN_CONCURRENCY)


def _order_row_to_dict(order) -> dict:
    """DailyOrder 实体 → 月份明细 order dict（26 键，与 _build_and_save_excel 消费口径一致）

    F9：月份明细 sheet 改读本地快照，本函数替代原 InvoiceExcelService._row_to_dict
    （外部 Row → dict）。字符串字段原样返回，控制字符清洗在 _build_and_save_excel
    写入侧统一兜底（单一出口）；datetime/数值字段原样。
    """
    return {
        "project_name": order.project_name,
        "custom_code": order.custom_code,
        "city": order.city,
        "department": order.department,
        "order_code": order.order_code,
        "nest_id": order.nest_id,
        "creator_name": order.creator_name,
        "create_date": order.create_date,
        "personal_name": order.personal_name,
        "nest_area": order.nest_area,
        "order_status": order.order_status,
        "produce_status": order.produce_status,
        "produce_flag": order.produce_flag,
        "remarks": order.remarks,
        "editor_account": order.editor_account,
        "editor_name": order.editor_name,
        "upload_date": order.upload_date,
        "finish_date": order.finish_date,
        "first_send_zb_date": order.first_send_zb_date,
        "first_edit_time": order.first_edit_time,
        "review_release_date": order.review_release_date,
        "floor_count": order.floor_count,
        "device_name": order.device_name,
        "customer_review_result": order.customer_review_result,
        "publisher_name": order.publisher_name,
        "model_fix_status": order.model_fix_status,
    }


async def generate_invoice_detail(
    session: AsyncSession,
    invoice_id: int,
    session_factory=None,
):
    """异步生成结算单明细 Excel 文件

    Args:
        session: 主会话
        invoice_id: 结算单 ID
        session_factory: 可选会话工厂。提供后，余额查询与终态更新改用短会话，
            主 session 在计费项查询后即可关闭——避免 PG 连接+事务覆盖整个
            Excel 构建段（构建段最长可达数秒，5 并发即长占 5 条连接）。
    """
    # 并发限流：排队等待而非耗尽连接池失败（详见 _detail_gen_semaphore 注释）
    async with _detail_gen_semaphore:
        await _generate_invoice_detail_inner(session, invoice_id, session_factory)


async def _generate_invoice_detail_inner(
    session: AsyncSession,
    invoice_id: int,
    session_factory=None,
):
    logger.info(f"开始异步生成结算单 {invoice_id} 的明细文件")

    try:
        # ===== 阶段 0：原子 claim（仅当 pending 才置 generating）=====
        # 防重复触发并发覆盖：批量重试/启动重新入队可能对同一单并发挂多个 job
        # （replace_existing 只替换 jobstore 条目，不取消在跑的协程），条件
        # UPDATE 保证同时仅一个实例进入构建段，其余直接跳过。
        from sqlalchemy import update

        claim = await session.execute(
            update(Invoice)
            .where(Invoice.id == invoice_id, Invoice.detail_file_status == "pending")
            .values(detail_file_status="generating")
        )
        await session.commit()
        if claim.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
            logger.info(f"结算单 {invoice_id} 非待生成状态，跳过（另一实例在跑或已完成）")
            return

        # ===== 阶段 1：数据查询（持主 session）=====
        invoice = await session.get(Invoice, invoice_id)  # claim 成功后重新加载
        if not invoice:
            logger.error(f"结算单 {invoice_id} 不存在")
            return

        customer = await session.get(Customer, invoice.customer_id)
        if not customer:
            logger.error(f"结算单 {invoice_id} 的客户不存在")
            await _update_final_status(session, session_factory, invoice_id, "failed", None)
            return

        if invoice.customer_id is None:
            # DB schema 允许 NULL（历史遗留），但生成明细文件必须有关联客户
            logger.error(f"结算单 {invoice_id} 缺少客户 ID，无法生成明细文件")
            await _update_final_status(session, session_factory, invoice_id, "failed", None)
            return

        # 查询结算明细项（多层计费字段读 invoice_items 冻结列，不再 JOIN PricingRule：
        # 规则后续变更不影响已生成单；历史行 NULL 由展示层兜底）
        from sqlalchemy import select

        from ..models.daily_order import DailyOrder

        result = await session.execute(
            select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
        )
        # scalars() 解包单实体 select 的 Row（否则 rows[0] 是 Row，属性访问 KeyError）
        rows = result.scalars().all()
        # 取第一项的单价作为代表（按设备类型+图层分别计价时取首个）
        unit_price = rows[0].unit_price if rows else None

        # 构造 invoice_items 列表传给 Excel（含 F3 落库的 subtotal/order_count，
        # 使「合计」数量口径与「计费明细」小计同源）
        invoice_items = []
        for item in rows:
            invoice_items.append(
                {
                    "device_type": item.device_type,
                    "layer_type": item.layer_type,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "subtotal": item.subtotal,
                    "order_count": item.order_count,
                    "multi_floor_pricing_type": item.multi_floor_pricing_type,
                    "additional_floor_price": item.additional_floor_price,
                }
            )

        # 查询本单计费周期内的订单快照行（daily_orders，F9）：「月份明细」
        # sheet 直接由这些行渲染，与「计费明细」「合计」同源（此前实时查外部
        # MySQL，外部删单/改期即行数对不上，且补生成历史单拿到「当前」状态）。
        # 排序口径对齐原 DETAIL_SQL 的 ORDER BY create_date DESC，并列时按
        # (order_code, custom_code)（唯一键）兜底，保证重复生成文件逐行一致。
        order_rows = (
            (
                await session.execute(
                    select(DailyOrder)
                    .where(
                        DailyOrder.customer_id == invoice.customer_id,
                        DailyOrder.sync_date >= invoice.period_start,
                        DailyOrder.sync_date < invoice.period_end + timedelta(seconds=1),
                        DailyOrder.deleted_at.is_(None),
                    )
                    .order_by(
                        DailyOrder.create_date.desc(),
                        DailyOrder.order_code,
                        DailyOrder.custom_code,
                    )
                )
            )
            .scalars()
            .all()
        )
        order_details = [_order_row_to_dict(row) for row in order_rows]

        # 查询完毕：提交并关闭主会话，释放 PG 连接与事务。
        # 余额查询/终态更新改用短会话（见 InvoiceExcelService.session_factory）。
        await session.commit()
        await session.close()

        # 快照生成所需的单头字段（session 关闭后 ORM 实例已 detached，
        # 提前取标量值避免 expired attribute 访问）
        customer_name = customer.name
        period_start = invoice.period_start
        period_end = invoice.period_end
        total_amount = invoice.total_amount
        discount_amount = invoice.discount_amount or Decimal(0)
        invoice_status = invoice.status or "draft"

        # ===== 阶段 2：生成 Excel（不持 DB 连接）=====
        # InvoiceExcelService 余额查询走 session_factory 短会话；Excel 构建
        # 在 asyncio.to_thread 中执行（见 generate_detail_file），不阻塞事件循环。
        # order_details 为本地快照行（F9，外部引擎/group_type 已无需传入）。
        excel_service = InvoiceExcelService(
            db=session,  # 仅为兼容签名，实际 DB 访问已走 session_factory
            session_factory=session_factory,
        )
        file_path = await excel_service.generate_detail_file(
            invoice_id=invoice_id,
            customer_id=invoice.customer_id,
            customer_name=customer_name,
            period_start=period_start,
            period_end=period_end,
            total_amount=total_amount,
            discount_amount=discount_amount,
            unit_price=unit_price,
            invoice_status=invoice_status,
            invoice_items=invoice_items,
            order_details=order_details,
        )

        # ===== 阶段 3：更新终态（短会话或主会话）=====
        if file_path:
            logger.info(f"结算单 {invoice_id} 明细文件生成成功: {file_path}")
            new_status, new_path = "completed", file_path
        else:
            logger.warning(f"结算单 {invoice_id} 明细文件生成失败")
            new_status, new_path = "failed", None

        await _update_final_status(session, session_factory, invoice_id, new_status, new_path)

    except Exception as e:
        logger.error(f"结算单 {invoice_id} 明细文件生成异常: {e}", exc_info=True)
        # 尝试标记为失败
        try:
            await _update_final_status(session, session_factory, invoice_id, "failed", None)
        except Exception:
            pass
    finally:
        await session.close()


async def _update_final_status(
    session: AsyncSession,
    session_factory,
    invoice_id: int,
    status: str,
    file_path: str | None,
):
    """更新结算单明细文件终态（条件 UPDATE：仅当处于 generating 才写终态）。

    条件化保证终态写对陈旧运行幂等：`replace_existing=True` 只替换 jobstore
    条目，不取消在跑的协程（APScheduler AsyncIOExecutor 不取消进行中的 task），
    若无条件写终态，后启动的实例会覆盖先启动实例的结果（last-writer-wins）。

    有 session_factory 时用短会话（主会话已在构建前关闭）；否则回退主会话
    （兼容未传工厂的调用方，如测试）。
    """
    from sqlalchemy import update

    async def _apply(s: AsyncSession) -> int:
        result = await s.execute(
            update(Invoice)
            .where(Invoice.id == invoice_id, Invoice.detail_file_status == "generating")
            .values(
                detail_file_status=status,
                **({"detail_file_path": file_path} if file_path else {}),
            )
        )
        await s.commit()
        return result.rowcount or 0  # pyright: ignore[reportAttributeAccessIssue]

    if session_factory is not None:
        async with session_factory() as s:
            n = await _apply(s)
    else:
        n = await _apply(session)
    if n == 0:
        logger.info(f"结算单 {invoice_id} 非生成中，跳过终态写（已被其他运行覆盖）")
