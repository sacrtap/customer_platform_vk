"""发票管理路由 — 生成、审批、支付、导出"""

import asyncio
import logging
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from urllib.parse import quote

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sanic.request import Request
from sanic.response import file as response_file
from sanic.response import json, raw
from sqlalchemy.ext.asyncio import AsyncSession

from ...cache.base import cache_service
from ...config import settings
from ...constants.error_codes import ErrorCodes
from ...middleware.auth import auth_required, get_current_user, require_permission
from ...repository import InvoiceRepository, PricingRepository
from ...services.billing import InvoiceService
from ...tasks.invoice_detail_generator import generate_invoice_detail
from ...utils.audit_helpers import create_audit_entry
from ...utils.excel_import import read_import_dataframe
from ...utils.tiers import TierFormatError
from ...utils.timezone import local_date_range_to_utc
from . import billing_bp

logger = logging.getLogger(__name__)


def _content_disposition(filename: str) -> str:
    """生成 Content-Disposition 响应头值，附带 RFC 5987 的 filename*。

    中文文件名在部分 HTTP 客户端/浏览器下会乱码或下载失败；这里保留原始
    ``filename`` 兜底，并追加百分号编码的 ``filename*=UTF-8''...``，让支持
    RFC 5987 的客户端正确解码中文文件名。
    """
    return f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename, safe='')}"


def _write_cell_text_safe(cell, value):
    """把值写入 xlsx 单元格，防御公式/CSV 注入（CWE-1236）。

    openpyxl 会把以 ``=`` 开头的字符串当作公式存储（data_type=``f``），导入接口
    允许 invoice_no 为任意自由文本，若含 ``=HYPERLINK(...)`` 等前缀，导出的 xlsx
    在 Excel 中打开时会执行公式/外部链接。这里对危险前缀的字符串显式标记
    ``data_type='s'``（以 inlineStr 存储为纯文本）：值本身保持不变（区别于加前导
    单引号/空格会污染值），因此纯数字/普通单号不受影响，导出文件可无损回填导入。
    """
    cell.value = value
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        cell.data_type = "s"


async def _trigger_detail_generation(request: Request, invoice_id: int):
    """触发结算单明细文件异步生成"""
    from ...tasks.scheduler import get_scheduler

    external_engine = getattr(request.app.ctx, "external_mysql_engine", None)
    session_factory = request.app.ctx.async_session_maker

    scheduler = get_scheduler()
    scheduler.add_job(
        generate_invoice_detail,
        args=[session_factory(), external_engine, invoice_id],
        id=f"invoice_detail_{invoice_id}",
        name=f"结算单明细生成-{invoice_id}",
        replace_existing=True,
    )


@billing_bp.get("/invoices")
@auth_required
@require_permission("billing:view")
async def get_invoices(request: Request):
    """获取结算单列表"""
    db: AsyncSession = request.ctx.db_session
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    customer_id = int(request.args.get("customer_id")) if request.args.get("customer_id") else None
    keyword = request.args.get("keyword")  # 客户名称模糊搜索
    status = request.args.get("status")
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))

    # 排序参数
    sort_by = request.args.get("sort_by", "")
    sort_order = request.args.get("sort_order", "desc")
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    invoices, total = await invoice_service.get_invoices(
        customer_id=customer_id,
        keyword=keyword,
        status=status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": i.id,
                        "invoice_no": i.invoice_no,
                        "customer_id": i.customer_id,
                        "customer_name": i.customer.name if i.customer else None,
                        # 客户指定的运营/销售经理（前端据此判断按钮是否可点击）
                        "customer_manager_id": i.customer.manager_id if i.customer else None,
                        "customer_sales_manager_id": i.customer.sales_manager_id
                        if i.customer
                        else None,
                        "period_start": i.period_start.isoformat() if i.period_start else None,  # pyright: ignore[reportGeneralTypeIssues]
                        "period_end": i.period_end.isoformat() if i.period_end else None,  # pyright: ignore[reportGeneralTypeIssues]
                        "total_amount": float(i.total_amount),  # pyright: ignore[reportArgumentType]
                        "discount_amount": float(i.discount_amount) if i.discount_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                        "final_amount": float(i.total_amount - (i.discount_amount or 0)),  # pyright: ignore[reportArgumentType]
                        "status": i.status,
                        "is_auto_generated": i.is_auto_generated,
                        "detail_file_status": i.detail_file_status or "pending",  # pyright: ignore[reportGeneralTypeIssues]
                        "created_at": i.created_at.isoformat() if i.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                    }
                    for i in invoices
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@billing_bp.get("/invoices/<invoice_id:int>")
@auth_required
@require_permission("billing:view")
async def get_invoice(request: Request, invoice_id: int):
    """获取结算单详情"""
    db: AsyncSession = request.ctx.db_session
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    invoice = await invoice_service.get_invoice_by_id(invoice_id)

    if not invoice:
        return json({"code": 40401, "message": "结算单不存在"}, status=404)

    # 批量查询操作人姓名
    from sqlalchemy import select as sa_select

    from ...models.billing import InvoiceDiscountHistory
    from ...models.users import User

    operator_ids = {
        invoice.created_by,
        invoice.approver_id,
        invoice.ops_confirmed_by,
        invoice.sales_confirmed_by,
        invoice.customer_confirmed_by,
        invoice.completed_by,
        invoice.cancelled_by,
    }
    operator_ids.discard(None)

    # 查询减免历史记录
    discount_history_result = await db.execute(
        sa_select(InvoiceDiscountHistory)
        .where(
            InvoiceDiscountHistory.invoice_id == invoice_id,
            InvoiceDiscountHistory.deleted_at.is_(None),
        )
        .order_by(InvoiceDiscountHistory.applied_at.desc())
    )
    discount_histories = discount_history_result.scalars().all()

    # 收集历史记录中的操作人 ID
    for dh in discount_histories:
        if dh.applied_by:
            operator_ids.add(dh.applied_by)

    operator_names: dict[int, str] = {}
    if operator_ids:
        user_result = await db.execute(
            sa_select(User.id, User.real_name, User.username).where(User.id.in_(operator_ids))
        )
        for row in user_result:
            operator_names[row.id] = row.real_name or row.username

    def resolve_name(uid):
        return operator_names.get(uid) if uid else None

    # 重新调用 calculate_items_from_rules 获取完整计费规则信息
    # 数据库 InvoiceItem 只存储基础字段（device_type/layer_type/quantity/unit_price），
    # pricing_type/package_type/tiers/over_limit 等需通过 PricingRule 关联获取
    try:
        recalculated_items, _ = await invoice_service.calculate_items_from_rules(
            customer_id=invoice.customer_id,
            period_start=invoice.period_start,  # pyright: ignore[reportArgumentType]
            period_end=invoice.period_end,  # pyright: ignore[reportArgumentType]
        )
    except TierFormatError as e:
        # 与 calculate-items 一致：阶梯配置非法时返回业务错误码而非 500
        return json(
            {"code": ErrorCodes.INVALID_FORMAT, "message": f"阶梯配置格式错误：{e}"},
            status=400,
        )

    # 格式化 items（与 calculate-items 路由一致的字段结构）
    formatted_items = [
        {
            "id": item.get("pricing_rule_id"),
            "device_type": item["device_type"],
            "layer_type": item["layer_type"],
            "quantity": float(item["quantity"]),
            "unit_price": float(item["unit_price"]),
            "subtotal": float(item["subtotal"]),
            "additional_floor_price": float(item["additional_floor_price"])
            if item.get("additional_floor_price") is not None
            else None,
            "multi_floor_pricing_type": item.get("multi_floor_pricing_type"),
            "order_count": float(item["order_count"])
            if item.get("order_count") is not None
            else None,
            "pricing_type": item.get("pricing_type"),
            "pricing_rule_id": item.get("pricing_rule_id"),
            "package_type": item.get("package_type"),
            "base_fee": float(item["base_fee"]) if item.get("base_fee") is not None else None,
            "limit_count": item.get("limit_count"),
            "over_limit_quantity": item.get("over_limit_quantity"),
            "over_limit_unit_price": float(item["over_limit_unit_price"])
            if item.get("over_limit_unit_price") is not None
            else None,
            "over_limit_cost": float(item["over_limit_cost"])
            if item.get("over_limit_cost") is not None
            else None,
            "usage_cost": float(item["usage_cost"]) if item.get("usage_cost") is not None else None,
            "period_days": item.get("period_days"),
            "tiers": item.get("tiers"),
        }
        for item in recalculated_items
    ]

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": invoice.id,
                "invoice_no": invoice.invoice_no,
                "customer_id": invoice.customer_id,
                "customer_name": invoice.customer.name if invoice.customer else None,
                # 客户指定的运营/销售经理（前端据此判断按钮是否可点击）
                "customer_manager_id": invoice.customer.manager_id if invoice.customer else None,
                "customer_sales_manager_id": invoice.customer.sales_manager_id
                if invoice.customer
                else None,
                "period_start": invoice.period_start.isoformat() if invoice.period_start else None,  # pyright: ignore[reportGeneralTypeIssues]
                "period_end": invoice.period_end.isoformat() if invoice.period_end else None,  # pyright: ignore[reportGeneralTypeIssues]
                "total_amount": float(invoice.total_amount),  # pyright: ignore[reportArgumentType]
                "discount_amount": float(invoice.discount_amount) if invoice.discount_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "discount_reason": invoice.discount_reason,
                "discount_attachment": invoice.discount_attachment,
                "final_amount": float(invoice.total_amount - (invoice.discount_amount or 0)),  # pyright: ignore[reportArgumentType]
                "status": invoice.status,
                "items": formatted_items,
                "approver_id": invoice.approver_id,
                "approver_name": resolve_name(invoice.approver_id),
                "approved_at": invoice.approved_at,
                "discount_applied_at": invoice.discount_applied_at,
                "ops_confirmed_by": invoice.ops_confirmed_by,
                "ops_confirmed_name": resolve_name(invoice.ops_confirmed_by),
                "ops_confirmed_at": invoice.ops_confirmed_at,
                "sales_confirmed_by": invoice.sales_confirmed_by,
                "sales_confirmed_name": resolve_name(invoice.sales_confirmed_by),
                "sales_confirmed_at": invoice.sales_confirmed_at,
                "customer_confirmed_at": invoice.customer_confirmed_at,
                "customer_confirmed_by": invoice.customer_confirmed_by,
                "customer_confirmed_name": resolve_name(invoice.customer_confirmed_by),
                "paid_at": invoice.paid_at,
                "completed_at": invoice.completed_at,
                "completed_by": invoice.completed_by,
                "completed_name": resolve_name(invoice.completed_by),
                "cancelled_at": invoice.cancelled_at,
                "cancelled_by": invoice.cancelled_by,
                "cancelled_name": resolve_name(invoice.cancelled_by),
                "created_by": invoice.created_by,
                "created_by_name": resolve_name(invoice.created_by),
                "detail_file_path": invoice.detail_file_path,  # pyright: ignore[reportGeneralTypeIssues]
                "detail_file_status": invoice.detail_file_status or "pending",  # pyright: ignore[reportGeneralTypeIssues]
                "created_at": invoice.created_at.isoformat() if invoice.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                "discount_history": [
                    {
                        "id": dh.id,
                        "discount_amount": float(dh.discount_amount),  # pyright: ignore[reportArgumentType]
                        "discount_reason": dh.discount_reason,
                        "discount_attachment": dh.discount_attachment,
                        "applied_at": dh.applied_at,
                        "applied_by": dh.applied_by,
                        "applied_by_name": operator_names.get(dh.applied_by)
                        if dh.applied_by
                        else None,
                    }
                    for dh in discount_histories
                ],
            },
        }
    )


@billing_bp.post("/invoices/calculate-items")
@auth_required
@require_permission("billing:edit")
async def calculate_invoice_items(request: Request):
    """
    根据客户 + 结算周期，自动计算结算明细

    Body:
    {
        "customer_id": 1,
        "period_start": "2026-03-01",
        "period_end": "2026-03-31"
    }

    Returns:
    {
        "code": 0,
        "message": "计算成功",
        "data": {
            "items": [
                {"device_type": "N", "layer_type": "single", "quantity": 1234, "unit_price": 10.0, "subtotal": 12340.0}
            ],
            "total_amount": 12340.0
        }
    }
    """
    db: AsyncSession = request.ctx.db_session
    data = request.json

    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    # 日期转换：前端本地日期 → UTC datetime 范围
    period_start, period_end = local_date_range_to_utc(data["period_start"], data["period_end"])

    # 调用服务层计算
    try:
        items, total_amount = await invoice_service.calculate_items_from_rules(
            customer_id=data["customer_id"],
            period_start=period_start,
            period_end=period_end,
        )
    except TierFormatError as e:
        return json(
            {"code": ErrorCodes.INVALID_FORMAT, "message": f"阶梯配置格式错误：{e}"},
            status=400,
        )
    if not items:
        return json(
            {
                "code": 40002,
                "message": "该客户在结算周期内无用量数据或无匹配的计费规则",
            },
            status=400,
        )

    # 格式化返回数据
    formatted_items = [
        {
            "device_type": item["device_type"],
            "layer_type": item["layer_type"],
            "quantity": float(item["quantity"]),
            "unit_price": float(item["unit_price"]),
            "subtotal": float(item["subtotal"]),
            "additional_floor_price": float(item["additional_floor_price"])
            if item.get("additional_floor_price") is not None
            else None,
            "multi_floor_pricing_type": item.get("multi_floor_pricing_type"),
            "order_count": float(item["order_count"])
            if item.get("order_count") is not None
            else None,
            "pricing_type": item.get("pricing_type"),
            "pricing_rule_id": item.get("pricing_rule_id"),
            "package_type": item.get("package_type"),
            "base_fee": float(item["base_fee"]) if item.get("base_fee") is not None else None,
            "limit_count": item.get("limit_count"),
            "over_limit_quantity": item.get("over_limit_quantity"),
            "over_limit_unit_price": float(item["over_limit_unit_price"])
            if item.get("over_limit_unit_price") is not None
            else None,
            "over_limit_cost": float(item["over_limit_cost"])
            if item.get("over_limit_cost") is not None
            else None,
            "usage_cost": float(item["usage_cost"]) if item.get("usage_cost") is not None else None,
            "period_days": item.get("period_days"),
            "tiers": item.get("tiers"),
        }
        for item in items
    ]

    return json(
        {
            "code": 0,
            "message": "计算成功",
            "data": {
                "items": formatted_items,
                "total_amount": float(total_amount),
            },
        }
    )


@billing_bp.post("/invoices/preview-batch")
@auth_required
@require_permission("billing:view")
async def preview_batch_invoices(request: Request):
    """预览批量生成结算单的匹配客户列表

    Body:
    {
        "pricing_type": "fixed",              # 计费类型（可选）
        "industry_type_ids": [1, 2, 3],       # 行业类型 ID 列表（可选）
        "scale_levels": ["S", "A"],           # 规模等级列表（可选）
        "consume_levels": ["C1", "C2"],       # 消费等级列表（可选）
        "is_real_estate": true                # 是否房产客户（可选）
    }

    Returns:
    {
        "code": 0,
        "data": {
            "total": 5,
            "customers": [
                {"id": 1, "name": "客户A", "manager_id": 3, "sales_manager_id": 5, "has_manager": true, "has_sales_manager": true}
            ]
        }
    }
    """
    db: AsyncSession = request.ctx.db_session
    data = request.json or {}

    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    customers = await invoice_service.get_customers_for_batch(
        pricing_type=data.get("pricing_type"),
        industry_type_ids=data.get("industry_type_ids"),
        scale_levels=data.get("scale_levels"),
        consume_levels=data.get("consume_levels"),
        is_real_estate=data.get("is_real_estate"),
    )

    # 标记是否已指定经理
    result_list = [
        {
            "id": c["id"],
            "name": c["name"],
            "manager_id": c["manager_id"],
            "sales_manager_id": c["sales_manager_id"],
            "has_manager": bool(c["manager_id"]),
            "has_sales_manager": bool(c["sales_manager_id"]),
        }
        for c in customers
    ]

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {"total": len(result_list), "customers": result_list},
        }
    )


@billing_bp.post("/invoices/generate-batch")
@auth_required
@require_permission("billing:edit")
async def generate_invoices_batch(request: Request):
    """按计费类型批量生成结算单

    为每个匹配的客户独立生成一张结算单（状态 draft）。

    Body:
    {
        "pricing_type": "fixed",
        "industry_type_ids": [1, 2, 3],
        "scale_levels": ["S", "A"],
        "consume_levels": ["C1", "C2"],
        "is_real_estate": true,
        "period_start": "2026-07-01",
        "period_end": "2026-07-31"
    }

    Returns:
    {
        "code": 0,
        "message": "批量生成完成",
        "data": {
            "success_count": 3,
            "generated": [...],
            "skipped": [...]
        }
    }
    """
    db: AsyncSession = request.ctx.db_session
    data = request.json
    user = get_current_user(request)

    # 日期转换：前端本地日期 → UTC datetime 范围
    period_start, period_end = local_date_range_to_utc(data["period_start"], data["period_end"])

    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    result = await invoice_service.generate_invoices_batch(
        pricing_type=data.get("pricing_type"),
        industry_type_ids=data.get("industry_type_ids"),
        scale_levels=data.get("scale_levels"),
        consume_levels=data.get("consume_levels"),
        is_real_estate=data.get("is_real_estate"),
        period_start=period_start,
        period_end=period_end,
        created_by=user["user_id"] if user else 1,
    )

    # 批量生成后清除缓存
    await cache_service.invalidate_billing_cache()

    # 记录审计日志
    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="generate_batch",
        module="billing",
        record_id=0,
        record_type="invoice",
        changes={
            "after": {
                "success_count": result["success_count"],
                "skipped_count": len(result["skipped"]),
            }
        },
        operation_type="batch",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    # 批量触发明细文件异步生成
    for inv in result.get("generated", []):
        inv_id = inv.get("id") if isinstance(inv, dict) else None
        if inv_id:
            try:
                await _trigger_detail_generation(request, inv_id)
            except Exception:
                pass  # 触发失败不阻塞批量生成返回

    return json(
        {
            "code": 0,
            "message": f"批量生成完成：成功 {result['success_count']} 个，跳过 {len(result['skipped'])} 个",
            "data": result,
        }
    )


@billing_bp.post("/invoices/generate")
@auth_required
@require_permission("billing:edit")
async def generate_invoice(request: Request):
    """
    生成结算单

    Body:
    {
        "customer_id": 1,
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
        "items": [
            {"device_type": "X", "layer_type": "single", "quantity": 100, "unit_price": 10}
        ]
    }

    注意：如果未提供 items，系统会自动根据客户的计费规则和用量数据生成。
    """
    db: AsyncSession = request.ctx.db_session
    data = request.json
    user = get_current_user(request)

    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    # 日期转换：前端本地日期 → UTC datetime 范围
    period_start, period_end = local_date_range_to_utc(data["period_start"], data["period_end"])

    # 区分"未提供 items"和"items 为空列表"
    if "items" not in data:
        # 未提供 items，自动根据计费规则 + 用量计算
        try:
            items, _ = await invoice_service.calculate_items_from_rules(
                customer_id=data["customer_id"],
                period_start=period_start,
                period_end=period_end,
            )
        except TierFormatError as e:
            # 与 calculate-items 一致：阶梯配置非法时返回业务错误码而非 500
            return json(
                {"code": ErrorCodes.INVALID_FORMAT, "message": f"阶梯配置格式错误：{e}"},
                status=400,
            )
        if not items:
            return json(
                {
                    "code": 40002,
                    "message": "该客户在结算周期内无用量数据或无匹配的计费规则",
                },
                status=400,
            )
    elif not data["items"]:
        # 显式传入空列表，拒绝
        return json(
            {
                "code": 40001,
                "message": "结算项不能为空",
            },
            status=400,
        )
    else:
        items = data["items"]
    invoice = await invoice_service.generate_invoice(
        customer_id=data["customer_id"],
        period_start=period_start,
        period_end=period_end,
        items=items,
        created_by=user["user_id"] if user else 1,
    )

    # 结算单生成后清除相关缓存
    await cache_service.invalidate_billing_cache()

    # 触发明细文件异步生成
    await _trigger_detail_generation(request, invoice.id)  # pyright: ignore[reportArgumentType]

    return json(
        {
            "code": 0,
            "message": "生成成功",
            "data": {
                "id": invoice.id,
                "invoice_no": invoice.invoice_no,
                "total_amount": float(invoice.total_amount),  # pyright: ignore[reportArgumentType]
            },
        },
        status=201,
    )


@billing_bp.put("/invoices/<invoice_id:int>/discount")
@auth_required
@require_permission("billing:edit")
async def apply_discount(request: Request, invoice_id: int):
    """
    应用/修改减免

    Body:
    {
        "discount_amount": 500.00,
        "discount_reason": "大客户优惠",
        "discount_attachment": "/uploads/proof.xlsx"
    }

    允许在 draft / pending_ops / pending_sales / pending_customer 状态下修改。
    """
    db: AsyncSession = request.ctx.db_session
    data = request.json
    user = get_current_user(request)

    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    # 获取修改前的值（用于审计日志）
    invoice_before = await invoice_service.get_invoice_by_id(invoice_id)
    old_discount = (
        float(invoice_before.discount_amount)
        if invoice_before and invoice_before.discount_amount
        else 0
    )
    old_reason = invoice_before.discount_reason if invoice_before else ""

    success, message = await invoice_service.apply_discount(
        invoice_id=invoice_id,
        discount_amount=Decimal(str(data.get("discount_amount", 0))),
        discount_reason=data.get("discount_reason", ""),
        discount_attachment=data.get("discount_attachment"),
        applied_by=user.get("user_id") if user else None,
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    # 结算单减免后清除相关缓存
    await cache_service.invalidate_billing_cache()

    # 记录审计日志（每次修改都产生记录）
    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="apply_discount",
        module="billing",
        record_id=invoice_id,
        record_type="invoice",
        changes={
            "old": {"discount_amount": old_discount, "discount_reason": old_reason},
            "new": {
                "discount_amount": float(data.get("discount_amount", 0)),
                "discount_reason": data.get("discount_reason", ""),
                "discount_attachment": data.get("discount_attachment"),
            },
        },
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    # 返回更新后的 invoice 数据
    invoice_after = await invoice_service.get_invoice_by_id(invoice_id)
    if invoice_after is None:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)

    # 如果明细文件已生成，重新生成以更新合计 sheet 中的减免相关数值
    if invoice_after.detail_file_status == "completed":
        try:
            await _trigger_detail_generation(request, invoice_id)
        except Exception:
            pass  # 重新生成失败不影响减免修改结果

    return json(
        {
            "code": 0,
            "message": message,
            "data": {
                "id": invoice_after.id,
                "discount_amount": float(invoice_after.discount_amount)
                if invoice_after.discount_amount
                else 0,
                "discount_reason": invoice_after.discount_reason,
                "discount_attachment": invoice_after.discount_attachment,
                "discount_applied_at": invoice_after.discount_applied_at,
                "final_amount": float(
                    invoice_after.total_amount - (invoice_after.discount_amount or 0)
                ),
                "status": invoice_after.status,
            },
        }
    )


@billing_bp.post("/invoices/<invoice_id:int>/submit")
@auth_required
@require_permission("billing:edit")
async def submit_invoice(request: Request, invoice_id: int):
    """提交结算单（商务确认）

    Body (可选减免信息):
    {
        "discount_amount": 500.00,
        "discount_reason": "大客户优惠",
        "discount_attachment": "/uploads/proof.xlsx"
    }
    """
    db: AsyncSession = request.ctx.db_session
    data = request.json or {}
    user = get_current_user(request)
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    # 如果传入了减免信息，先应用减免
    if "discount_amount" in data and data["discount_amount"]:
        discount_success, discount_msg = await invoice_service.apply_discount(
            invoice_id=invoice_id,
            discount_amount=Decimal(str(data["discount_amount"])),
            discount_reason=data.get("discount_reason", ""),
            discount_attachment=data.get("discount_attachment"),
            applied_by=user.get("user_id") if user else None,
        )
        if not discount_success:
            return json({"code": 40001, "message": discount_msg}, status=400)

    # 获取提交前状态
    invoice_before = await invoice_service.get_invoice_by_id(invoice_id)
    status_before = invoice_before.status if invoice_before else None

    success, message = await invoice_service.submit_invoice(
        invoice_id=invoice_id,
        approver_id=user["user_id"] if user else 1,
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    # 获取提交后状态
    invoice_after = await invoice_service.get_invoice_by_id(invoice_id)

    # 结算单提交后清除相关缓存
    await cache_service.invalidate_billing_cache()

    # 如果传入了减免信息且明细文件已生成，重新生成以更新合计 sheet 中的减免相关数值
    if (
        "discount_amount" in data
        and data["discount_amount"]
        and invoice_after
        and invoice_after.detail_file_status == "completed"  # pyright: ignore[reportOptionalMemberAccess]
    ):
        try:
            await _trigger_detail_generation(request, invoice_id)
        except Exception:
            pass  # 重新生成失败不影响提交结果

    # 记录审计日志
    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="submit",
        module="billing",
        record_id=invoice_id,
        record_type="invoice",
        changes={
            "before": {"status": status_before},
            "after": {"status": invoice_after.status if invoice_after else None},
        },
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.post("/invoices/<invoice_id:int>/confirm")
@auth_required
@require_permission("billing:confirm")
async def confirm_invoice(request: Request, invoice_id: int):
    """客户确认结算单（第三步，线下确认后线上录入）

    确认后系统自动执行余额扣款，成功则进入 completed。
    """
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    # 获取确认前状态
    invoice_before = await invoice_service.get_invoice_by_id(invoice_id)
    status_before = invoice_before.status if invoice_before else None

    success, message = await invoice_service.confirm_invoice(
        invoice_id=invoice_id,
        user_id=user["user_id"] if user else 1,
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    # 获取确认后状态
    invoice_after = await invoice_service.get_invoice_by_id(invoice_id)

    # 结算单确认后清除相关缓存
    await cache_service.invalidate_billing_cache()

    # 记录审计日志
    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="confirm",
        module="billing",
        record_id=invoice_id,
        record_type="invoice",
        changes={
            "before": {"status": status_before},
            "after": {"status": invoice_after.status if invoice_after else None},
        },
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.post("/invoices/<invoice_id:int>/confirm-ops")
@auth_required
@require_permission("billing:ops_approve")
async def confirm_ops(request: Request, invoice_id: int):
    """运营经理确认结算单（第一步）"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    invoice_before = await invoice_service.get_invoice_by_id(invoice_id)
    status_before = invoice_before.status if invoice_before else None

    success, message = await invoice_service.confirm_ops(
        invoice_id=invoice_id,
        user_id=user["user_id"] if user else 1,
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    invoice_after = await invoice_service.get_invoice_by_id(invoice_id)
    await cache_service.invalidate_billing_cache()

    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="confirm_ops",
        module="billing",
        record_id=invoice_id,
        record_type="invoice",
        changes={
            "before": {"status": status_before},
            "after": {"status": invoice_after.status if invoice_after else None},
        },
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.post("/invoices/<invoice_id:int>/confirm-sales")
@auth_required
@require_permission("billing:sales_approve")
async def confirm_sales(request: Request, invoice_id: int):
    """销售经理确认结算单（第二步）"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    invoice_before = await invoice_service.get_invoice_by_id(invoice_id)
    status_before = invoice_before.status if invoice_before else None

    success, message = await invoice_service.confirm_sales(
        invoice_id=invoice_id,
        user_id=user["user_id"] if user else 1,
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    invoice_after = await invoice_service.get_invoice_by_id(invoice_id)
    await cache_service.invalidate_billing_cache()

    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="confirm_sales",
        module="billing",
        record_id=invoice_id,
        record_type="invoice",
        changes={
            "before": {"status": status_before},
            "after": {"status": invoice_after.status if invoice_after else None},
        },
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.post("/invoices/<invoice_id:int>/retry-deduction")
@auth_required
@require_permission("billing:confirm")
async def retry_deduction(request: Request, invoice_id: int):
    """重试扣款（客户确认后扣款失败时手动重试）"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    invoice_before = await invoice_service.get_invoice_by_id(invoice_id)
    status_before = invoice_before.status if invoice_before else None

    success, message = await invoice_service.retry_deduction(
        invoice_id=invoice_id,
        user_id=user.get("user_id") if user else 1,  # pyright: ignore[reportArgumentType]
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    invoice_after = await invoice_service.get_invoice_by_id(invoice_id)
    await cache_service.invalidate_billing_cache()

    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="retry_deduction",
        module="billing",
        record_id=invoice_id,
        record_type="invoice",
        changes={
            "before": {"status": status_before},
            "after": {"status": invoice_after.status if invoice_after else None},
        },
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.post("/invoices/<invoice_id:int>/pay")
@auth_required
@require_permission("billing:pay")
async def pay_invoice(request: Request, invoice_id: int):
    """确认付款"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    data = request.json or {}
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    # 获取付款前状态
    invoice_before = await invoice_service.get_invoice_by_id(invoice_id)
    status_before = invoice_before.status if invoice_before else None

    success, message = await invoice_service.pay_invoice(
        invoice_id=invoice_id,
        payment_proof=data.get("payment_proof"),
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    # 获取付款后状态
    invoice_after = await invoice_service.get_invoice_by_id(invoice_id)

    # 结算单付款后清除相关缓存
    await cache_service.invalidate_billing_cache()

    # 记录审计日志
    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="pay",
        module="billing",
        record_id=invoice_id,
        record_type="invoice",
        changes={
            "before": {"status": status_before, "payment_proof": None},
            "after": {
                "status": invoice_after.status if invoice_after else None,
                "payment_proof": data.get("payment_proof"),
            },
        },
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.post("/invoices/<invoice_id:int>/complete")
@auth_required
@require_permission("billing:pay")
async def complete_invoice(request: Request, invoice_id: int):
    """完成结算（扣款）"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    # 获取完成前状态
    invoice_before = await invoice_service.get_invoice_by_id(invoice_id)
    status_before = invoice_before.status if invoice_before else None

    success, message = await invoice_service.complete_invoice(
        invoice_id=invoice_id,
        user_id=user.get("user_id") if user else 1,  # pyright: ignore[reportArgumentType]
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    # 获取完成后状态
    invoice_after = await invoice_service.get_invoice_by_id(invoice_id)

    # 结算单完成后清除相关缓存
    await cache_service.invalidate_billing_cache()

    # 记录审计日志
    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="complete",
        module="billing",
        record_id=invoice_id,
        record_type="invoice",
        changes={
            "before": {"status": status_before},
            "after": {"status": invoice_after.status if invoice_after else None},
        },
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.post("/invoices/<invoice_id:int>/cancel")
@auth_required
@require_permission("billing:edit")
async def cancel_invoice_route(request: Request, invoice_id: int):
    """取消结算单"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    # 获取取消前状态
    invoice_before = await invoice_service.get_invoice_by_id(invoice_id)
    status_before = invoice_before.status if invoice_before else None

    success, message = await invoice_service.cancel_invoice(
        invoice_id=invoice_id,
        user_id=user["user_id"] if user else None,  # pyright: ignore[reportArgumentType]
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    # 获取取消后状态
    invoice_after = await invoice_service.get_invoice_by_id(invoice_id)

    # 结算单取消后清除相关缓存
    await cache_service.invalidate_billing_cache()

    # 记录审计日志
    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="cancel",
        module="billing",
        record_id=invoice_id,
        record_type="invoice",
        changes={
            "before": {"status": status_before},
            "after": {"status": invoice_after.status if invoice_after else None},
        },
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.delete("/invoices/<invoice_id:int>")
@auth_required
@require_permission("billing:delete")
async def delete_invoice(request: Request, invoice_id: int):
    """删除结算单"""
    db: AsyncSession = request.ctx.db_session
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    success = await invoice_service.delete_invoice(invoice_id)

    if not success:
        return json({"code": 40401, "message": "结算单不存在"}, status=404)

    # 结算单删除后清除相关缓存
    await cache_service.invalidate_billing_cache()

    return json({"code": 0, "message": "删除成功"})


@billing_bp.get("/invoices/export")
@auth_required
@require_permission("billing:invoice_export")
async def export_invoices(request: Request):
    """
    导出结算单为 Excel 文件

    查询参数:
    - customer_id: 客户 ID（可选）
    - status: 结算单状态（可选）
    - start_date: 开始日期（可选，格式：YYYY-MM-DD）
    - end_date: 结束日期（可选，格式：YYYY-MM-DD）

    响应:
    - Excel 文件下载
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from ...models.billing import Invoice, InvoiceStatus
    from ...models.customers import Customer

    # 获取数据库会话
    db: AsyncSession = request.ctx.db_session

    # 获取查询参数
    customer_id = int(request.args.get("customer_id")) if request.args.get("customer_id") else None
    status = request.args.get("status")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    # 构建基础查询
    base_stmt = (
        select(Invoice)
        .join(Customer, Invoice.customer_id == Customer.id)
        .options(selectinload(Invoice.customer))
        .where(
            Invoice.deleted_at.is_(None),
            Customer.deleted_at.is_(None),
        )
    )

    # 应用筛选条件
    if customer_id:
        base_stmt = base_stmt.where(Invoice.customer_id == customer_id)

    if status:
        # 验证状态值
        valid_statuses = [s.value for s in InvoiceStatus]
        if status not in valid_statuses:
            return json(
                {
                    "code": 40001,
                    "message": f"无效的状态值，有效值：{', '.join(valid_statuses)}",
                },
                status=400,
            )
        base_stmt = base_stmt.where(Invoice.status == status)

    if start_date:
        try:
            start = date.fromisoformat(start_date)
            base_stmt = base_stmt.where(Invoice.period_start >= start)
        except ValueError:
            return json(
                {"code": 40001, "message": "开始日期格式错误，应为 YYYY-MM-DD"},
                status=400,
            )

    if end_date:
        try:
            end = date.fromisoformat(end_date)
            base_stmt = base_stmt.where(Invoice.period_end <= end)
        except ValueError:
            return json(
                {"code": 40001, "message": "结束日期格式错误，应为 YYYY-MM-DD"},
                status=400,
            )

    # 执行查询
    result = await db.execute(base_stmt.order_by(Invoice.created_at.desc()))
    invoices = result.scalars().all()

    if not invoices:
        return json(
            {"code": 40002, "message": "没有找到符合条件的结算单"},
            status=400,
        )

    # 创建 Excel 工作簿
    wb = Workbook()
    ws = wb.active
    assert ws is not None  # 新建 Workbook 必有活动工作表
    ws.title = "结算单导出"

    # 定义样式
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    cell_alignment = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # 表头
    headers = [
        "结算单号",
        "客户名称",
        "周期开始",
        "周期结束",
        "总金额",
        "减免金额",
        "最终金额",
        "状态",
        "创建时间",
    ]

    # 写入表头
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)  # pyright: ignore[reportOptionalMemberAccess]
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # 设置列宽
    column_widths = [20, 30, 12, 12, 12, 12, 12, 18, 20]
    for col_num, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(col_num)].width = width  # pyright: ignore[reportOptionalMemberAccess]

    # 写入数据
    status_map = {
        "draft": "草稿",
        "pending_customer": "待客户确认",
        "customer_confirmed": "客户已确认",
        "paid": "已付款",
        "completed": "已完成",
        "cancelled": "已取消",
    }

    for row_num, invoice in enumerate(invoices, 2):
        # 获取客户名称（通过关联或查询）
        customer_name = (
            invoice.customer.name if hasattr(invoice, "customer") and invoice.customer else "未知"
        )

        row_data = [
            invoice.invoice_no,
            customer_name,
            invoice.period_start.isoformat() if invoice.period_start else "",  # pyright: ignore[reportGeneralTypeIssues]
            invoice.period_end.isoformat() if invoice.period_end else "",  # pyright: ignore[reportGeneralTypeIssues]
            float(invoice.total_amount),  # pyright: ignore[reportArgumentType]
            float(invoice.discount_amount) if invoice.discount_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
            float(invoice.total_amount - (invoice.discount_amount or 0)),  # pyright: ignore[reportArgumentType]
            status_map.get(invoice.status, invoice.status),  # pyright: ignore[reportCallIssue, reportArgumentType]
            invoice.created_at.isoformat() if invoice.created_at else "",  # pyright: ignore[reportGeneralTypeIssues]
        ]

        for col_num, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col_num)  # pyright: ignore[reportOptionalMemberAccess]
            # 防御公式注入：invoice_no / customer_name 等文本字段若以 = + - @ 开头，
            # 会被 openpyxl 当作公式存储，导出文件在 Excel 打开时可能执行恶意公式。
            _write_cell_text_safe(cell, value)
            cell.alignment = cell_alignment
            cell.border = thin_border

    # 添加统计信息行
    total_row = len(invoices) + 2
    ws.cell(row=total_row, column=1, value=f"共 {len(invoices)} 条记录")  # pyright: ignore[reportOptionalMemberAccess]
    ws.cell(  # pyright: ignore[reportOptionalMemberAccess]
        row=total_row,
        column=5,
        value=f"总金额：{sum(float(inv.total_amount) for inv in invoices):.2f}",  # pyright: ignore[reportArgumentType]
    )
    ws.cell(  # pyright: ignore[reportOptionalMemberAccess]
        row=total_row,
        column=7,
        value=f"最终总额：{sum(float(inv.total_amount - (inv.discount_amount or 0)) for inv in invoices):.2f}",  # pyright: ignore[reportArgumentType]
    )

    # 保存到内存
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"结算单导出_{timestamp}.xlsx"

    # 返回文件
    return raw(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": _content_disposition(filename),
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


# ==================== 结算单导入 ====================


@billing_bp.post("/invoices/import")
@auth_required
@require_permission("billing:invoice_import")
async def import_invoices(request: Request):
    """
    Excel 批量导入外部/历史结算单

    Form:
    - file: Excel 文件 (.xlsx)

    Excel 列要求:
    - company_id (必填) - 客户编号
    - period_start (必填) - 账期开始 YYYY-MM-DD
    - period_end (必填) - 账期结束 YYYY-MM-DD
    - total_amount (必填) - 结算金额（元，≥0）
    - discount_amount (可选) - 减免金额（元，默认 0）
    - invoice_no (可选) - 结算单号，缺省自动生成

    导入的结算单统一为 draft（草稿）状态，不进入确认/付款流程。
    """
    import random
    import string

    import pandas as pd
    from sqlalchemy import select

    from ...models.billing import Invoice
    from ...models.customers import Customer

    files = request.files
    if "file" not in files:  # pyright: ignore[reportOperatorIssue]
        return json({"code": ErrorCodes.BAD_REQUEST, "message": "请上传 Excel 文件"}, status=400)

    excel_file = files["file"][0]  # pyright: ignore[reportOptionalSubscript]
    if not excel_file.name.endswith(".xlsx"):
        return json(
            {"code": ErrorCodes.INVALID_FORMAT, "message": "请上传 .xlsx 格式的文件"}, status=400
        )

    # 服务端体积上限兜底：前端虽限 10MB，但可被绕过；.xlsx 是 zip 容器，
    # 高压缩比/超大工作簿会在整体读入内存解析时造成内存耗尽（DoS）。在解析前
    # 拦截，上限与前端 ImportModal 的 10MB 口径一致（settings.max_file_size）。
    if len(excel_file.body) > settings.max_file_size:
        return json(
            {
                "code": ErrorCodes.BAD_REQUEST,
                "message": f"文件大小超过限制（最大 {settings.max_file_size // (1024 * 1024)}MB）",
            },
            status=400,
        )

    db: AsyncSession = request.ctx.db_session

    try:
        # 读取 Excel 文件（自动丢弃模板第 2 行的中文说明行）。
        # pd.read_excel 是 CPU+I/O 密集的同步调用，10MB xlsx 可阻塞事件循环数百毫秒至数秒，
        # 与 packages/pricing/imports 三处导入端点保持一致的 to_thread 处理。
        try:
            df = await asyncio.to_thread(read_import_dataframe, excel_file.body, "company_id")
        except Exception as e:
            # 客户端可控输入：损坏/伪 xlsx（BadZipFile 等）应返回可读的 400，而非 500
            logger.warning("结算单导入文件解析失败: %s", e)
            return json(
                {
                    "code": ErrorCodes.INVALID_FILE,
                    "message": "文件无法解析，请确认是有效的 .xlsx 文件（未加密、未损坏）",
                },
                status=400,
            )

        # 必填列检查
        required_columns = ["company_id", "period_start", "period_end", "total_amount"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return json(
                {
                    "code": ErrorCodes.INVALID_FILE,
                    "message": f"Excel 缺少必填列：{', '.join(missing_columns)}",
                },
                status=400,
            )

        # 空文件检查：仅有表头（无数据行）时直接拒绝，避免虚假的导入成功反馈
        if df.empty:
            return json(
                {"code": ErrorCodes.INVALID_FILE, "message": "文件中没有可导入的数据"},
                status=400,
            )

        # 行数限制
        if len(df) > 1000:
            return json(
                {"code": ErrorCodes.MISSING_PARAMETER, "message": "单次最多导入 1000 条记录"},
                status=400,
            )

        # 预加载客户 company_id -> customer_id 映射（排除软删除客户：
        # 列表 get_invoices 与导出 export_invoices 均通过 join 过滤了软删除客户，
        # 导入若仍可命中会为其创建结算单，但这些结算单在列表/导出中不可见，形成
        # 不可见的脏数据；与 pricing.py 导入侧的处理保持一致）
        result = await db.execute(
            select(Customer.id, Customer.company_id).where(Customer.deleted_at.is_(None))
        )
        company_to_customer = {row[1]: row[0] for row in result.all()}

        # 预加载已存在的 invoice_no（避免随机码碰撞 / 用户指定单号重号）。
        # 范围收敛为「本日自动生成前缀」+「本次 Excel 显式指定的单号」：原实现
        # select(Invoice.invoice_no) 会把该列全表加载，随表增长内存与耗时无限膨胀。
        today_prefix = f"INV-{datetime.now().strftime('%Y%m%d')}-"
        existing_invoice_nos = set(
            (
                await db.execute(
                    select(Invoice.invoice_no).where(Invoice.invoice_no.like(f"{today_prefix}%"))
                )
            )
            .scalars()
            .all()
        )
        # 用户显式指定的单号需与全表判重，但只查本次出现的取值（行数上限 1000）
        supplied_nos = {
            str(v).strip()
            for v in (df["invoice_no"].tolist() if "invoice_no" in df.columns else [])
            if v is not None and not bool(pd.isna(v)) and str(v).strip()
        }
        if supplied_nos:
            taken_result = await db.execute(
                select(Invoice.invoice_no).where(Invoice.invoice_no.in_(supplied_nos))
            )
            existing_invoice_nos |= set(taken_result.scalars().all())

        current_user = get_current_user(request)
        operator_id = current_user.get("user_id") if current_user else 1

        errors = []
        success_count = 0
        for idx, row in df.iterrows():
            row_num = int(str(idx)) + 2  # Excel 行号（含表头）
            try:
                # company_id
                company_id = row.get("company_id")
                if bool(pd.isna(company_id)) or company_id is None:
                    errors.append(f"第 {row_num} 行：客户编号为空")
                    continue
                try:
                    # pandas 会把带小数的数字单元格读成 float（如 100001.9），
                    # int() 会静默截断为 100001，把结算单挂到错误客户名下；
                    # 先判定是否为整数值，非整数一律按行级错误拒绝。
                    if isinstance(company_id, float) and not company_id.is_integer():
                        raise ValueError
                    company_id = int(company_id)
                except (ValueError, TypeError):
                    errors.append(f"第 {row_num} 行：客户编号 '{company_id}' 不是有效整数")
                    continue
                if company_id not in company_to_customer:
                    errors.append(f"第 {row_num} 行：客户编号 {company_id} 不存在")
                    continue

                # 账期
                period_start_raw = row.get("period_start")
                period_end_raw = row.get("period_end")
                try:
                    # 先做可读的格式校验，再统一转 UTC 入库
                    period_start_str = str(period_start_raw)[:10]
                    period_end_str = str(period_end_raw)[:10]
                    datetime.strptime(period_start_str, "%Y-%m-%d")
                    datetime.strptime(period_end_str, "%Y-%m-%d")
                except (ValueError, TypeError):
                    errors.append(f"第 {row_num} 行：账期格式错误（应为 YYYY-MM-DD）")
                    continue
                if period_end_str < period_start_str:
                    errors.append(f"第 {row_num} 行：账期结束不能早于开始")
                    continue
                # 与 calculate_invoice_items / generate_invoice 一致，账期须转 UTC 后入库
                period_start, period_end = local_date_range_to_utc(period_start_str, period_end_str)

                # 金额
                total_amount_raw = row.get("total_amount")
                if bool(pd.isna(total_amount_raw)) or total_amount_raw is None:
                    errors.append(f"第 {row_num} 行：结算金额为空")
                    continue
                try:
                    total_amount = Decimal(str(total_amount_raw))
                    # NaN 会抛 InvalidOperation，Infinity 则会绕过 <0 比较，须显式拒绝非有限值
                    if not total_amount.is_finite():
                        errors.append(f"第 {row_num} 行：结算金额格式错误")
                        continue
                    if total_amount < 0:
                        errors.append(f"第 {row_num} 行：结算金额不能为负数")
                        continue
                except (InvalidOperation, ValueError, TypeError):
                    errors.append(f"第 {row_num} 行：结算金额格式错误")
                    continue

                discount_amount = Decimal("0")
                discount_raw = row.get("discount_amount")
                if discount_raw is not None and not bool(pd.isna(discount_raw)):
                    try:
                        discount_amount = Decimal(str(discount_raw))
                        if not discount_amount.is_finite():
                            errors.append(f"第 {row_num} 行：减免金额格式错误")
                            continue
                        if discount_amount < 0:
                            errors.append(f"第 {row_num} 行：减免金额不能为负数")
                            continue
                    except (InvalidOperation, ValueError, TypeError):
                        errors.append(f"第 {row_num} 行：减免金额格式错误")
                        continue
                if discount_amount > total_amount:
                    errors.append(f"第 {row_num} 行：减免金额不能大于结算金额")
                    continue

                # invoice_no（可选，缺省自动生成）
                invoice_no = None
                invoice_no_raw = row.get("invoice_no")
                if (
                    invoice_no_raw is not None
                    and not bool(pd.isna(invoice_no_raw))
                    and str(invoice_no_raw).strip()
                ):
                    invoice_no = str(invoice_no_raw).strip()
                    if invoice_no in existing_invoice_nos:
                        errors.append(f"第 {row_num} 行：结算单号 {invoice_no} 已存在")
                        continue
                else:
                    customer_key = company_to_customer[company_id]
                    while True:
                        # 与 services/billing.py 的既有单号规则一致：4 位随机码取自
                        # 大写字母+数字（36^4 命名空间）。原先仅用数字（10^4）会使同
                        # 客户同日的碰撞概率高出 168 倍，且单日超 1 万条时会无限循环。
                        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
                        invoice_no = (
                            f"INV-{datetime.now().strftime('%Y%m%d')}-{customer_key}-{code}"
                        )
                        if invoice_no not in existing_invoice_nos:
                            break

                invoice = Invoice(
                    invoice_no=invoice_no,
                    customer_id=company_to_customer[company_id],
                    period_start=period_start,
                    period_end=period_end,
                    total_amount=total_amount,
                    discount_amount=discount_amount,
                    status="draft",
                    is_auto_generated=False,
                    created_by=operator_id,
                )
                # SAVEPOINT 行级隔离：单行 flush 触发 DB 错误（唯一约束冲突、字段超长等）
                # 时只回滚该行。原实现仅记录异常而不回滚，会话会进入 PendingRollback
                # 状态，导致后续所有行的 flush 与最终 commit 全部失败 —— 整批（含已成功
                # 的行）一并落空，行级错误隔离形同虚设。
                async with db.begin_nested():
                    db.add(invoice)
                    await db.flush()
                existing_invoice_nos.add(invoice_no)
                success_count += 1
            except Exception as e:  # 兜底，避免单行异常中断整个导入
                logger.warning("结算单导入第 %d 行失败: %s", row_num, e)
                errors.append(f"第 {row_num} 行：{str(e)}")

        await db.commit()

        # 导入成功后清除结算相关缓存
        await cache_service.invalidate_billing_cache()

        # 记录审计日志。审计写入失败不应影响导入结果：结算单已持久化，
        # 若抛异常导致 500，客户端重试会产生重复导入，故将失败解耦处理。
        from ...utils.audit_helpers import build_batch_audit_summary

        summary = build_batch_audit_summary(
            operation="invoice_import",
            total_count=len(df),
            success_count=success_count,
            failed_count=len(errors),
            details=errors[:10],
        )
        try:
            await create_audit_entry(
                db_session=db,
                user_id=operator_id,
                action="batch_create",
                module="billing",
                record_id=None,
                record_type="invoice",
                changes={"after": {"count": success_count}},
                operation_type="batch",
                extra_metadata=summary,
                ip_address=request.headers.get(
                    "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
                ),
                auto_commit=True,
            )
        except Exception:
            logger.exception("结算单导入审计日志写入失败")

        return json(
            {
                "code": 0,
                "message": "导入完成",
                "data": {
                    "success_count": success_count,
                    "error_count": len(errors),
                    "errors": errors[:10],
                },
            }
        )
    except Exception:
        # 外层失败（如最终 commit 抛错）也需回滚，避免把中毒会话归还连接池
        await db.rollback()
        # 不把原始异常信息返回客户端，避免泄露 SQL/驱动层细节；完整堆栈记入服务端日志
        logger.exception("结算单导入失败")
        return json(
            {"code": ErrorCodes.SERVICE_ERROR, "message": "导入失败，请稍后重试"}, status=500
        )


@billing_bp.get("/invoices/import-template")
@auth_required
async def download_invoice_import_template(request: Request):
    """下载结算单导入 Excel 模板"""
    import io

    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    assert ws is not None  # 新建 Workbook 必有活动工作表
    ws.title = "结算单导入模板"

    headers = [
        "company_id",
        "period_start",
        "period_end",
        "total_amount",
        "discount_amount",
        "invoice_no",
    ]
    ws.append(headers)  # pyright: ignore[reportOptionalMemberAccess]

    notes = [
        "必填：客户编号（整数）",
        "必填：账期开始 YYYY-MM-DD",
        "必填：账期结束 YYYY-MM-DD",
        "必填：结算金额（元）",
        "可选：减免金额（元）",
        "可选：结算单号，缺省自动生成",
    ]
    ws.append(notes)  # pyright: ignore[reportOptionalMemberAccess]

    for col_num in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col_num)].width = 24

    # 不写入示例数据行：示例行会被当作真实数据导入（公司 100001 的 draft 结算单）。
    # 表头行（第 1 行）与中文说明行（第 2 行）契约由模板下载测试断言，保持不变。

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return raw(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": _content_disposition("结算单导入模板.xlsx")},
    )


# ==================== 结算单明细文件 ====================


@billing_bp.get("/invoices/<invoice_id:int>/download-detail")
@auth_required
@require_permission("billing:view")
async def download_invoice_detail(request: Request, invoice_id: int):
    """下载结算单明细 Excel 文件"""
    db: AsyncSession = request.ctx.db_session
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    invoice = await invoice_service.get_invoice_by_id(invoice_id)
    if not invoice:
        return json({"code": 40401, "message": "结算单不存在"}, status=404)

    if invoice.detail_file_status != "completed" or not invoice.detail_file_path:  # pyright: ignore[reportGeneralTypeIssues]
        return json({"code": 40001, "message": "明细文件尚未生成完成"}, status=400)

    # 构建完整文件路径
    base_dir = getattr(settings, "file_storage_path", "./uploads")
    file_path = os.path.join(base_dir, invoice.detail_file_path)  # pyright: ignore[reportGeneralTypeIssues]

    if not os.path.exists(file_path):
        return json({"code": 40401, "message": "明细文件不存在"}, status=404)

    filename = f"{invoice.invoice_no}.xlsx"

    return await response_file(
        file_path,
        headers={
            "Content-Disposition": _content_disposition(filename),
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@billing_bp.post("/invoices/<invoice_id:int>/regenerate-detail")
@auth_required
@require_permission("billing:edit")
async def regenerate_invoice_detail(request: Request, invoice_id: int):
    """重新生成结算单明细 Excel 文件"""
    db: AsyncSession = request.ctx.db_session
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    invoice = await invoice_service.get_invoice_by_id(invoice_id)
    if not invoice:
        return json({"code": 40401, "message": "结算单不存在"}, status=404)

    # 重置状态为 pending
    invoice.detail_file_status = "pending"  # pyright: ignore[reportAttributeAccessIssue]
    await db.commit()

    # 触发异步生成
    await _trigger_detail_generation(request, invoice_id)

    return json({"code": 0, "message": "明细文件重新生成中"})


@billing_bp.get("/invoices/detail-logs")
@auth_required
@require_permission("billing:view")
async def get_invoice_detail_logs(request: Request):
    """结算单明细文件生成日志列表"""
    db: AsyncSession = request.ctx.db_session
    from sqlalchemy import func, select
    from sqlalchemy.orm import selectinload

    from ...models.billing import Invoice

    # 筛选参数
    status_filter = request.args.get("status")
    customer_id = request.args.get("customer_id")
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))

    # 预加载 customer：序列化时读取 inv.customer.name，而 Invoice.customer 未配置
    # lazy="selectin"，异步会话下懒加载会抛 MissingGreenlet 导致 500。
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.customer))
        .where(Invoice.detail_file_status != "pending")
    )
    count_stmt = (
        select(func.count()).select_from(Invoice).where(Invoice.detail_file_status != "pending")
    )

    if status_filter:
        stmt = stmt.where(Invoice.detail_file_status == status_filter)
        count_stmt = count_stmt.where(Invoice.detail_file_status == status_filter)

    if customer_id:
        stmt = stmt.where(Invoice.customer_id == int(customer_id))
        count_stmt = count_stmt.where(Invoice.customer_id == int(customer_id))

    # 排序：最近变更在前
    stmt = stmt.order_by(Invoice.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    invoices = result.scalars().all()

    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": inv.id,
                        "invoice_no": inv.invoice_no,
                        "customer_id": inv.customer_id,
                        "customer_name": inv.customer.name if inv.customer else None,
                        "period_start": inv.period_start.isoformat() if inv.period_start else None,  # pyright: ignore[reportGeneralTypeIssues]
                        "period_end": inv.period_end.isoformat() if inv.period_end else None,  # pyright: ignore[reportGeneralTypeIssues]
                        "detail_file_status": inv.detail_file_status or "pending",  # pyright: ignore[reportGeneralTypeIssues]
                        "detail_file_path": inv.detail_file_path,  # pyright: ignore[reportGeneralTypeIssues]
                        "total_amount": float(inv.total_amount),  # pyright: ignore[reportArgumentType]
                        "created_at": inv.created_at.isoformat() if inv.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                        "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                    }
                    for inv in invoices
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


# ==================== 余额趋势 ====================


@billing_bp.get("/invoices/file-status")
@auth_required
@require_permission("billing:view")
async def get_invoice_file_status(request: Request):
    """轻量查询结算单明细文件状态（用于前端轮询）

    支持 ids 参数（逗号分隔的 ID 列表），返回每条结算单的文件状态。
    """
    from sqlalchemy import select as sa_select

    from ...models.billing import Invoice

    db: AsyncSession = request.ctx.db_session
    ids_param = request.args.get("ids", "")
    if not ids_param:
        return json({"code": 0, "message": "success", "data": {"list": []}})

    try:
        ids = [int(x) for x in ids_param.split(",") if x.strip()]
    except ValueError:
        from ...constants.error_codes import ErrorCodes

        return json(
            {"code": ErrorCodes.BAD_REQUEST, "message": "ids 参数格式错误"},
            status=400,
        )

    if not ids:
        return json({"code": 0, "message": "success", "data": {"list": []}})

    result = await db.execute(
        sa_select(Invoice.id, Invoice.detail_file_status, Invoice.detail_file_path).where(
            Invoice.id.in_(ids), Invoice.deleted_at.is_(None)
        )
    )
    rows = result.all()

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": row.id,
                        "detail_file_status": row.detail_file_status or "pending",
                        "detail_file_path": row.detail_file_path,
                    }
                    for row in rows
                ]
            },
        }
    )
