"""发票管理路由 — 生成、审批、支付、导出"""

import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

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

    # 如果明细文件已生成，重新生成以更新合计 sheet 中的减免相关数值
    if invoice_after and invoice_after.detail_file_status == "completed":  # pyright: ignore[reportOptionalMemberAccess]
        try:
            await _trigger_detail_generation(request, invoice_id)
        except Exception:
            pass  # 重新生成失败不影响减免修改结果

    return json(
        {
            "code": 0,
            "message": message,
            "data": {
                "id": invoice_after.id,  # pyright: ignore[reportOptionalMemberAccess]
                "discount_amount": float(invoice_after.discount_amount)
                if invoice_after.discount_amount
                else 0,  # pyright: ignore[reportOptionalMemberAccess, reportArgumentType, reportGeneralTypeIssues]
                "discount_reason": invoice_after.discount_reason,  # pyright: ignore[reportOptionalMemberAccess]
                "discount_attachment": invoice_after.discount_attachment,  # pyright: ignore[reportOptionalMemberAccess]
                "discount_applied_at": invoice_after.discount_applied_at,  # pyright: ignore[reportOptionalMemberAccess]
                "final_amount": float(
                    invoice_after.total_amount - (invoice_after.discount_amount or 0)
                ),  # pyright: ignore[reportOptionalMemberAccess, reportArgumentType]
                "status": invoice_after.status,  # pyright: ignore[reportOptionalMemberAccess]
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
    ws.title = "结算单导出"  # pyright: ignore[reportOptionalMemberAccess]

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
            cell = ws.cell(row=row_num, column=col_num, value=value)  # pyright: ignore[reportOptionalMemberAccess]
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
            "Content-Disposition": f'attachment; filename="{filename}"',
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
        return json({"code": 40001, "message": "请上传 Excel 文件"}, status=400)

    excel_file = files["file"][0]  # pyright: ignore[reportOptionalSubscript]
    if not excel_file.name.endswith(".xlsx"):
        return json({"code": 40002, "message": "请上传 .xlsx 格式的文件"}, status=400)

    db: AsyncSession = request.ctx.db_session

    try:
        # 读取 Excel 文件（自动丢弃模板第 2 行的中文说明行）
        df = read_import_dataframe(excel_file.body, "company_id")

        # 必填列检查
        required_columns = ["company_id", "period_start", "period_end", "total_amount"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return json(
                {
                    "code": 40003,
                    "message": f"Excel 缺少必填列：{', '.join(missing_columns)}",
                },
                status=400,
            )

        # 行数限制
        if len(df) > 1000:
            return json(
                {"code": 40004, "message": "单次最多导入 1000 条记录"},
                status=400,
            )

        # 预加载客户 company_id -> customer_id 映射
        result = await db.execute(select(Customer.id, Customer.company_id))
        company_to_customer = {row[1]: row[0] for row in result.all()}

        # 预加载已存在的 invoice_no（避免随机码碰撞）
        existing_no_result = await db.execute(select(Invoice.invoice_no))
        existing_invoice_nos = set(existing_no_result.scalars().all())

        current_user = get_current_user(request)
        operator_id = current_user.get("user_id") if current_user else 1

        errors = []
        success_count = 0
        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel 行号（含表头）

            try:
                # company_id
                company_id = row.get("company_id")
                if pd.isna(company_id) or company_id is None:
                    errors.append(f"第 {row_num} 行：客户编号为空")
                    continue
                try:
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
                    period_start = datetime.strptime(str(period_start_raw)[:10], "%Y-%m-%d")
                    period_end = datetime.strptime(str(period_end_raw)[:10], "%Y-%m-%d")
                except (ValueError, TypeError):
                    errors.append(f"第 {row_num} 行：账期格式错误（应为 YYYY-MM-DD）")
                    continue
                if period_end < period_start:
                    errors.append(f"第 {row_num} 行：账期结束不能早于开始")
                    continue

                # 金额
                total_amount_raw = row.get("total_amount")
                try:
                    total_amount = Decimal(str(total_amount_raw))
                    if total_amount < 0:
                        errors.append(f"第 {row_num} 行：结算金额不能为负数")
                        continue
                except (InvalidOperation, ValueError, TypeError):
                    errors.append(f"第 {row_num} 行：结算金额格式错误")
                    continue

                discount_amount = Decimal("0")
                discount_raw = row.get("discount_amount")
                if discount_raw is not None and not pd.isna(discount_raw):
                    try:
                        discount_amount = Decimal(str(discount_raw))
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
                    and not pd.isna(invoice_no_raw)
                    and str(invoice_no_raw).strip()
                ):
                    invoice_no = str(invoice_no_raw).strip()
                    if invoice_no in existing_invoice_nos:
                        errors.append(f"第 {row_num} 行：结算单号 {invoice_no} 已存在")
                        continue
                else:
                    customer_key = company_to_customer[company_id]
                    while True:
                        code = "".join(random.choices(string.digits, k=4))
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
                db.add(invoice)
                await db.flush()
                existing_invoice_nos.add(invoice_no)
                success_count += 1
            except Exception as e:  # 兜底，避免单行异常中断整个导入
                import logging

                logging.getLogger(__name__).warning("结算单导入第 %d 行失败: %s", row_num, e)
                errors.append(f"第 {row_num} 行：{str(e)}")

        await db.commit()

        # 记录审计日志
        from ...utils.audit_helpers import build_batch_audit_summary

        summary = build_batch_audit_summary(
            operation="invoice_import",
            total_count=len(df),
            success_count=success_count,
            failed_count=len(errors),
            details=errors[:10],
        )
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
    except Exception as e:
        return json({"code": 50001, "message": f"导入失败：{str(e)}"}, status=500)


@billing_bp.get("/invoices/import-template")
@auth_required
async def download_invoice_import_template(request: Request):
    """下载结算单导入 Excel 模板"""
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "结算单导入模板"  # pyright: ignore[reportOptionalMemberAccess]

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

    for col in ws.columns:  # pyright: ignore[reportOptionalMemberAccess]
        ws.column_dimensions[col[0].column_letter].width = 24  # pyright: ignore[reportOptionalMemberAccess]

    # 示例数据
    ws.append([100001, "2026-04-01", "2026-04-30", 12500.50, 0, None])  # pyright: ignore[reportOptionalMemberAccess]

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return raw(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="结算单导入模板.xlsx"'},
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
            "Content-Disposition": f'attachment; filename="{filename}"',
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
