"""VR编辑费用结算路由 — 创建、审批流、减免、客户确认自动扣款、取消/删除"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from sanic.request import Request
from sanic.response import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...cache.base import cache_service
from ...constants.error_codes import ErrorCodes
from ...middleware.auth import (
    auth_required,
    customer_scope_user_id,
    get_current_user,
    require_permission,
)
from ...models.customers import Customer
from ...models.users import User
from ...models.vr_settlement import VrSettlementStatus
from ...services.vr_settlement import VrSettlementService
from ...utils.audit_helpers import create_audit_entry
from ...utils.timezone import local_date_range_to_utc
from . import billing_bp

logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> str:
    """提取客户端 IP（与审计中间件口径一致）"""
    return request.headers.get("x-real-ip", request.headers.get("x-forwarded-for", request.ip))


async def _ensure_settlement_scope(request: Request, settlement: Any) -> Any | None:
    """数据可见性（服务端强制）：无 customers:view_all 时，非本人负责客户的结算单拒绝访问。

    返回 403 响应对象时调用方应直接返回；返回 None 表示通过。
    """
    scope_user_id = await customer_scope_user_id(request)
    if scope_user_id is not None and not (
        settlement.customer
        and (
            settlement.customer.manager_id == scope_user_id
            or settlement.customer.sales_manager_id == scope_user_id
        )
    ):
        return json({"code": ErrorCodes.FORBIDDEN, "message": "无权访问该结算单"}, status=403)
    return None


async def _ensure_customer_scope(request: Request, customer: Any) -> Any | None:
    """创建前客户可见性校验：无 customers:view_all 时，仅可为自己负责的客户创建。

    返回 403 响应对象时调用方应直接返回；返回 None 表示通过。
    """
    scope_user_id = await customer_scope_user_id(request)
    if scope_user_id is not None and not (
        customer.manager_id == scope_user_id or customer.sales_manager_id == scope_user_id
    ):
        return json({"code": ErrorCodes.FORBIDDEN, "message": "无权访问该客户"}, status=403)
    return None


async def _resolve_operator_names(db: AsyncSession, user_ids: set[int | None]) -> dict[int, str]:
    """批量查询操作人姓名（照抄 invoices.py 详情端点模式）"""
    user_ids.discard(None)
    if not user_ids:
        return {}
    result = await db.execute(
        select(User.id, User.real_name, User.username).where(User.id.in_(user_ids))
    )
    return {row.id: row.real_name or row.username for row in result}


@billing_bp.get("/vr-settlements")
@auth_required
@require_permission("vr_settlement:view")
async def get_vr_settlements(request: Request):
    """获取 VR 结算单列表

    Query: keyword/status/customer_id/page/page_size/sort_by/sort_order
    """
    db: AsyncSession = request.ctx.db_session
    service = VrSettlementService(db)

    customer_id = int(request.args.get("customer_id")) if request.args.get("customer_id") else None
    keyword = request.args.get("keyword")  # 客户名称/结算单号模糊搜索
    status = request.args.get("status")
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))

    # 排序参数（非法 sort_order 归一化为 desc；非法 sort_by 由服务层静默回退 created_at）
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    # 状态值校验（与 invoices.py 列表一致）
    if status:
        valid_statuses = [s.value for s in VrSettlementStatus]
        if status not in valid_statuses:
            return json(
                {
                    "code": 40001,
                    "message": f"无效的状态值，有效值：{', '.join(valid_statuses)}",
                },
                status=400,
            )

    # 数据可见性（服务端强制）：无 customers:view_all 时仅返回当前用户负责客户的结算单
    scope_user_id = await customer_scope_user_id(request)

    settlements, total = await service.get_settlements(
        keyword=keyword,
        status=status,
        customer_id=customer_id,
        mine_user_id=scope_user_id,
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
                        "id": s.id,
                        "settlement_no": s.settlement_no,
                        "customer_id": s.customer_id,
                        "customer_name": s.customer.name if s.customer else None,
                        # 客户指定的运营/销售经理（前端据此判断按钮是否可点击）
                        "customer_manager_id": s.customer.manager_id if s.customer else None,
                        "customer_sales_manager_id": s.customer.sales_manager_id
                        if s.customer
                        else None,
                        "period_start": s.period_start.isoformat() if s.period_start else None,  # pyright: ignore[reportGeneralTypeIssues]
                        "period_end": s.period_end.isoformat() if s.period_end else None,  # pyright: ignore[reportGeneralTypeIssues]
                        "total_amount": float(s.total_amount),  # pyright: ignore[reportArgumentType]
                        "discount_amount": float(s.discount_amount) if s.discount_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                        "final_amount": float(s.total_amount - (s.discount_amount or 0)),  # pyright: ignore[reportArgumentType]
                        "status": s.status,
                        "detail_file_path": s.detail_file_path,  # pyright: ignore[reportGeneralTypeIssues]
                        "detail_file_name": s.detail_file_name,  # pyright: ignore[reportGeneralTypeIssues]
                        "created_at": s.created_at.isoformat() if s.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                    }
                    for s in settlements
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@billing_bp.get("/vr-settlements/<settlement_id:int>")
@auth_required
@require_permission("vr_settlement:view")
async def get_vr_settlement(request: Request, settlement_id: int):
    """获取 VR 结算单详情"""
    db: AsyncSession = request.ctx.db_session
    service = VrSettlementService(db)

    settlement = await service.get_settlement_by_id(settlement_id)
    if not settlement:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)

    # 数据可见性（服务端强制）：无 customers:view_all 时仅可查看自己负责客户的结算单
    denied = await _ensure_settlement_scope(request, settlement)
    if denied is not None:
        return denied

    # 批量查询操作人姓名
    operator_ids = {
        settlement.created_by,
        settlement.discount_approver_id,
        settlement.cs_supervisor_confirmed_by,
        settlement.sales_confirmed_by,
        settlement.sales_supervisor_confirmed_by,
        settlement.customer_confirmed_by,
        settlement.completed_by,
        settlement.cancelled_by,
    }

    # 查询减免历史记录（按时间倒序）
    discount_histories = await service.get_discount_histories(settlement_id)

    # 收集历史记录中的操作人 ID
    for dh in discount_histories:
        if dh.applied_by:
            operator_ids.add(dh.applied_by)

    operator_names = await _resolve_operator_names(db, operator_ids)

    def resolve_name(uid):
        return operator_names.get(uid) if uid else None

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": settlement.id,
                "settlement_no": settlement.settlement_no,
                "customer_id": settlement.customer_id,
                "customer_name": settlement.customer.name if settlement.customer else None,
                "customer_manager_id": settlement.customer.manager_id
                if settlement.customer
                else None,
                "customer_sales_manager_id": settlement.customer.sales_manager_id
                if settlement.customer
                else None,
                "period_start": settlement.period_start.isoformat()  # pyright: ignore[reportGeneralTypeIssues]
                if settlement.period_start
                else None,
                "period_end": settlement.period_end.isoformat()  # pyright: ignore[reportGeneralTypeIssues]
                if settlement.period_end
                else None,
                "total_amount": float(settlement.total_amount),  # pyright: ignore[reportArgumentType]
                "discount_amount": float(settlement.discount_amount)  # pyright: ignore[reportArgumentType]
                if settlement.discount_amount
                else 0,
                "discount_reason": settlement.discount_reason,
                "discount_attachment": settlement.discount_attachment,
                "final_amount": float(settlement.total_amount - (settlement.discount_amount or 0)),  # pyright: ignore[reportArgumentType]
                "status": settlement.status,
                "discount_applied_at": settlement.discount_applied_at,  # pyright: ignore[reportGeneralTypeIssues]
                "discount_approver_id": settlement.discount_approver_id,
                "discount_approver_name": resolve_name(settlement.discount_approver_id),
                "discount_approved_at": settlement.discount_approved_at,
                "discount_approval_comment": settlement.discount_approval_comment,
                "cs_supervisor_confirmed_by": settlement.cs_supervisor_confirmed_by,
                "cs_supervisor_confirmed_name": resolve_name(settlement.cs_supervisor_confirmed_by),
                "cs_supervisor_confirmed_at": settlement.cs_supervisor_confirmed_at,  # pyright: ignore[reportGeneralTypeIssues]
                "sales_confirmed_by": settlement.sales_confirmed_by,
                "sales_confirmed_name": resolve_name(settlement.sales_confirmed_by),
                "sales_confirmed_at": settlement.sales_confirmed_at,  # pyright: ignore[reportGeneralTypeIssues]
                "sales_supervisor_confirmed_by": settlement.sales_supervisor_confirmed_by,
                "sales_supervisor_confirmed_name": resolve_name(
                    settlement.sales_supervisor_confirmed_by
                ),
                "sales_supervisor_confirmed_at": settlement.sales_supervisor_confirmed_at,  # pyright: ignore[reportGeneralTypeIssues]
                "customer_confirmed_at": settlement.customer_confirmed_at,  # pyright: ignore[reportGeneralTypeIssues]
                "customer_confirmed_by": settlement.customer_confirmed_by,
                "customer_confirmed_name": resolve_name(settlement.customer_confirmed_by),
                "completed_at": settlement.completed_at,  # pyright: ignore[reportGeneralTypeIssues]
                "completed_by": settlement.completed_by,
                "completed_name": resolve_name(settlement.completed_by),
                "cancelled_at": settlement.cancelled_at,  # pyright: ignore[reportGeneralTypeIssues]
                "cancelled_by": settlement.cancelled_by,
                "cancelled_name": resolve_name(settlement.cancelled_by),
                "created_by": settlement.created_by,
                "created_by_name": resolve_name(settlement.created_by),
                "is_auto_generated": settlement.is_auto_generated,
                "detail_file_path": settlement.detail_file_path,  # pyright: ignore[reportGeneralTypeIssues]
                "detail_file_name": settlement.detail_file_name,  # pyright: ignore[reportGeneralTypeIssues]
                "created_at": settlement.created_at.isoformat()  # pyright: ignore[reportGeneralTypeIssues]
                if settlement.created_at
                else None,
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


@billing_bp.post("/vr-settlements")
@auth_required
@require_permission("vr_settlement:create")
async def create_vr_settlement(request: Request):
    """手动创建 VR 结算单（草稿）

    Body:
    {
        "customer_id": 1,
        "period_start": "2026-11-01",
        "period_end": "2026-11-30",
        "total_amount": 500.00,
        "detail_file_path": "/uploads/xxx.xlsx",
        "detail_file_name": "结算明细.xlsx"
    }
    """
    db: AsyncSession = request.ctx.db_session
    data = request.json or {}
    user = get_current_user(request)

    # 参数校验（先于权限/业务校验，缺参返回 400）
    if not data.get("customer_id"):
        return json(
            {"code": ErrorCodes.MISSING_PARAMETER, "message": "客户 ID 不能为空"},
            status=400,
        )
    if not data.get("detail_file_path"):
        return json(
            {"code": ErrorCodes.MISSING_PARAMETER, "message": "请上传结算明细文件"},
            status=400,
        )
    try:
        total_amount = Decimal(str(data.get("total_amount")))
        if total_amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, TypeError, ValueError):
        return json(
            {"code": ErrorCodes.INVALID_FORMAT, "message": "结算金额必须大于 0"},
            status=400,
        )

    service = VrSettlementService(db)

    # 客户存在性 + 数据可见性（服务端强制）：无 customers:view_all 时仅可为自己负责的客户创建
    customer = (
        await db.execute(
            select(Customer).where(
                Customer.id == data["customer_id"], Customer.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if customer is None:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "客户不存在"}, status=404)
    denied = await _ensure_customer_scope(request, customer)
    if denied is not None:
        return denied

    # 日期转换：前端本地日期 → UTC datetime 范围
    try:
        period_start, period_end = local_date_range_to_utc(data["period_start"], data["period_end"])
    except (ValueError, TypeError):
        return json(
            {"code": ErrorCodes.INVALID_FORMAT, "message": "日期格式错误，应为 YYYY-MM-DD"},
            status=400,
        )

    settlement = await service.create_settlement(
        customer_id=data["customer_id"],
        period_start=period_start,
        period_end=period_end,
        total_amount=total_amount,
        detail_file_path=data.get("detail_file_path"),
        detail_file_name=data.get("detail_file_name"),
        created_by=user["user_id"] if user else 1,
    )

    # 创建后清除相关缓存
    await cache_service.invalidate_billing_cache()

    return json(
        {
            "code": 0,
            "message": "创建成功",
            "data": {
                "id": settlement.id,
                "settlement_no": settlement.settlement_no,
                "total_amount": float(settlement.total_amount),  # pyright: ignore[reportArgumentType]
            },
        },
        status=201,
    )


@billing_bp.post("/vr-settlements/<settlement_id:int>/submit")
@auth_required
@require_permission("vr_settlement:create")
async def submit_vr_settlement(request: Request, settlement_id: int):
    """提交审批：draft → pending_cs_supervisor"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    service = VrSettlementService(db)

    settlement_before = await service.get_settlement_by_id(settlement_id)
    if not settlement_before:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)

    denied = await _ensure_settlement_scope(request, settlement_before)
    if denied is not None:
        return denied

    status_before = settlement_before.status

    success, message = await service.submit_settlement(
        settlement_id=settlement_id,
        user_id=user["user_id"] if user else 1,
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    settlement_after = await service.get_settlement_by_id(settlement_id)
    await cache_service.invalidate_billing_cache()

    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="submit_vr_settlement",
        module="billing",
        record_id=settlement_id,
        record_type="vr_settlement",
        changes={
            "before": {"status": status_before},
            "after": {"status": settlement_after.status if settlement_after else None},
        },
        operation_type="standard",
        ip_address=_client_ip(request),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.post("/vr-settlements/<settlement_id:int>/confirm-cs")
@auth_required
@require_permission("vr_settlement:cs_approve")
async def confirm_cs_supervisor(request: Request, settlement_id: int):
    """客服主管审批（第一步）：pending_cs_supervisor → pending_sales"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    service = VrSettlementService(db)

    settlement_before = await service.get_settlement_by_id(settlement_id)
    if not settlement_before:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)

    denied = await _ensure_settlement_scope(request, settlement_before)
    if denied is not None:
        return denied

    status_before = settlement_before.status

    success, message = await service.confirm_cs_supervisor(
        settlement_id=settlement_id,
        user_id=user["user_id"] if user else 1,
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    settlement_after = await service.get_settlement_by_id(settlement_id)
    await cache_service.invalidate_billing_cache()

    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="confirm_cs_supervisor",
        module="billing",
        record_id=settlement_id,
        record_type="vr_settlement",
        changes={
            "before": {"status": status_before},
            "after": {"status": settlement_after.status if settlement_after else None},
        },
        operation_type="standard",
        ip_address=_client_ip(request),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.post("/vr-settlements/<settlement_id:int>/confirm-sales")
@auth_required
@require_permission("vr_settlement:sales_approve")
async def confirm_vr_sales(request: Request, settlement_id: int):
    """销售审批（第二步）：pending_sales → pending_sales_supervisor"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    service = VrSettlementService(db)

    settlement_before = await service.get_settlement_by_id(settlement_id)
    if not settlement_before:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)

    denied = await _ensure_settlement_scope(request, settlement_before)
    if denied is not None:
        return denied

    status_before = settlement_before.status

    success, message = await service.confirm_sales(
        settlement_id=settlement_id,
        user_id=user["user_id"] if user else 1,
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    settlement_after = await service.get_settlement_by_id(settlement_id)
    await cache_service.invalidate_billing_cache()

    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="confirm_sales",
        module="billing",
        record_id=settlement_id,
        record_type="vr_settlement",
        changes={
            "before": {"status": status_before},
            "after": {"status": settlement_after.status if settlement_after else None},
        },
        operation_type="standard",
        ip_address=_client_ip(request),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.post("/vr-settlements/<settlement_id:int>/confirm-sales-supervisor")
@auth_required
@require_permission("vr_settlement:sales_supervisor_approve")
async def confirm_sales_supervisor(request: Request, settlement_id: int):
    """销售主管审批通过（第三步，含减免一并审批）

    Body: { "comment": "审批意见（选填）" }
    """
    db: AsyncSession = request.ctx.db_session
    data = request.json or {}
    user = get_current_user(request)
    service = VrSettlementService(db)

    settlement_before = await service.get_settlement_by_id(settlement_id)
    if not settlement_before:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)

    denied = await _ensure_settlement_scope(request, settlement_before)
    if denied is not None:
        return denied

    status_before = settlement_before.status

    success, message = await service.confirm_sales_supervisor(
        settlement_id=settlement_id,
        user_id=user["user_id"] if user else 1,
        comment=data.get("comment"),
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    settlement_after = await service.get_settlement_by_id(settlement_id)
    await cache_service.invalidate_billing_cache()

    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="confirm_sales_supervisor",
        module="billing",
        record_id=settlement_id,
        record_type="vr_settlement",
        changes={
            "before": {"status": status_before},
            "after": {"status": settlement_after.status if settlement_after else None},
        },
        operation_type="standard",
        ip_address=_client_ip(request),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.post("/vr-settlements/<settlement_id:int>/reject-sales-supervisor")
@auth_required
@require_permission("vr_settlement:sales_supervisor_approve")
async def reject_sales_supervisor(request: Request, settlement_id: int):
    """销售主管审批驳回：退回销售审批节点（comment 必填）"""
    db: AsyncSession = request.ctx.db_session
    data = request.json or {}
    user = get_current_user(request)
    service = VrSettlementService(db)

    comment = (data.get("comment") or "").strip()
    if not comment:
        return json({"code": 40001, "message": "驳回必须填写理由"}, status=400)

    settlement_before = await service.get_settlement_by_id(settlement_id)
    if not settlement_before:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)

    denied = await _ensure_settlement_scope(request, settlement_before)
    if denied is not None:
        return denied

    status_before = settlement_before.status

    success, message = await service.reject_sales_supervisor(
        settlement_id=settlement_id,
        user_id=user["user_id"] if user else 1,
        comment=comment,
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    settlement_after = await service.get_settlement_by_id(settlement_id)
    await cache_service.invalidate_billing_cache()

    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="reject_sales_supervisor",
        module="billing",
        record_id=settlement_id,
        record_type="vr_settlement",
        changes={
            "before": {"status": status_before},
            "after": {"status": settlement_after.status if settlement_after else None},
            "comment": comment,
        },
        operation_type="standard",
        ip_address=_client_ip(request),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.put("/vr-settlements/<settlement_id:int>/discount")
@auth_required
@require_permission("vr_settlement:edit")
async def apply_vr_discount(request: Request, settlement_id: int):
    """提交/修改减免（draft / pending_cs_supervisor / pending_sales 可改）

    Body:
    {
        "discount_amount": 100.00,
        "discount_reason": "大客户优惠",
        "discount_attachment": "/uploads/proof.pdf"
    }
    """
    db: AsyncSession = request.ctx.db_session
    data = request.json or {}
    user = get_current_user(request)
    service = VrSettlementService(db)

    settlement_before = await service.get_settlement_by_id(settlement_id)
    if not settlement_before:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)

    denied = await _ensure_settlement_scope(request, settlement_before)
    if denied is not None:
        return denied

    try:
        discount_amount = Decimal(str(data.get("discount_amount")))
    except (InvalidOperation, TypeError, ValueError):
        return json(
            {"code": ErrorCodes.INVALID_FORMAT, "message": "减免金额不能为 0"},
            status=400,
        )

    success, message = await service.apply_discount(
        settlement_id=settlement_id,
        discount_amount=discount_amount,
        discount_reason=data.get("discount_reason", ""),
        discount_attachment=data.get("discount_attachment"),
        user_id=user["user_id"] if user else 1,
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    settlement_after = await service.get_settlement_by_id(settlement_id)
    await cache_service.invalidate_billing_cache()

    return json(
        {
            "code": 0,
            "message": message,
            "data": {
                "discount_amount": float(settlement_after.discount_amount)  # pyright: ignore[reportArgumentType, reportOptionalMemberAccess]
                if settlement_after
                else None,
                "final_amount": float(
                    settlement_after.total_amount  # pyright: ignore[reportOptionalMemberAccess]
                    - (settlement_after.discount_amount or 0)  # pyright: ignore[reportOptionalMemberAccess]
                )
                if settlement_after
                else None,
                "status": settlement_after.status if settlement_after else None,  # pyright: ignore[reportOptionalMemberAccess]
            },
        }
    )


@billing_bp.post("/vr-settlements/<settlement_id:int>/confirm")
@auth_required
@require_permission("vr_settlement:confirm")
async def confirm_vr_settlement(request: Request, settlement_id: int):
    """客户确认：pending_customer → customer_confirmed → 自动扣款 → completed"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    service = VrSettlementService(db)

    settlement_before = await service.get_settlement_by_id(settlement_id)
    if not settlement_before:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)

    denied = await _ensure_settlement_scope(request, settlement_before)
    if denied is not None:
        return denied

    status_before = settlement_before.status

    success, message = await service.confirm_customer(
        settlement_id=settlement_id,
        user_id=user["user_id"] if user else 1,
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    settlement_after = await service.get_settlement_by_id(settlement_id)
    await cache_service.invalidate_billing_cache()

    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="confirm_vr_settlement",
        module="billing",
        record_id=settlement_id,
        record_type="vr_settlement",
        changes={
            "before": {"status": status_before},
            "after": {"status": settlement_after.status if settlement_after else None},
        },
        operation_type="standard",
        ip_address=_client_ip(request),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.post("/vr-settlements/<settlement_id:int>/retry-deduction")
@auth_required
@require_permission("vr_settlement:confirm")
async def retry_vr_deduction(request: Request, settlement_id: int):
    """重试扣款（扣款失败后手动重试）"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    service = VrSettlementService(db)

    settlement_before = await service.get_settlement_by_id(settlement_id)
    if not settlement_before:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)

    denied = await _ensure_settlement_scope(request, settlement_before)
    if denied is not None:
        return denied

    success, message = await service.retry_deduction(
        settlement_id=settlement_id,
        user_id=user["user_id"] if user else 1,
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    await cache_service.invalidate_billing_cache()

    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="retry_vr_deduction",
        module="billing",
        record_id=settlement_id,
        record_type="vr_settlement",
        changes={
            "before": {"status": "customer_confirmed"},
            "after": {"status": "completed"},
        },
        operation_type="standard",
        ip_address=_client_ip(request),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.post("/vr-settlements/<settlement_id:int>/cancel")
@auth_required
@require_permission("vr_settlement:edit")
async def cancel_vr_settlement(request: Request, settlement_id: int):
    """取消 VR 结算单（非终态可取消）"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    service = VrSettlementService(db)

    settlement_before = await service.get_settlement_by_id(settlement_id)
    if not settlement_before:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)

    denied = await _ensure_settlement_scope(request, settlement_before)
    if denied is not None:
        return denied

    status_before = settlement_before.status

    success, message = await service.cancel_settlement(
        settlement_id=settlement_id,
        user_id=user["user_id"] if user else 1,
    )

    if not success:
        return json({"code": 40001, "message": message}, status=400)

    await cache_service.invalidate_billing_cache()

    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="cancel_vr_settlement",
        module="billing",
        record_id=settlement_id,
        record_type="vr_settlement",
        changes={
            "before": {"status": status_before},
            "after": {"status": "cancelled"},
        },
        operation_type="standard",
        ip_address=_client_ip(request),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})


@billing_bp.delete("/vr-settlements/<settlement_id:int>")
@auth_required
@require_permission("vr_settlement:delete")
async def delete_vr_settlement(request: Request, settlement_id: int):
    """删除 VR 结算单（软删除）"""
    db: AsyncSession = request.ctx.db_session
    service = VrSettlementService(db)

    # 数据可见性（服务端强制）：无 customers:view_all 时仅可删除自己负责客户的结算单
    settlement = await service.get_settlement_by_id(settlement_id)
    if not settlement:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)
    denied = await _ensure_settlement_scope(request, settlement)
    if denied is not None:
        return denied

    success = await service.delete_settlement(settlement_id)

    if not success:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)

    await cache_service.invalidate_billing_cache()

    return json({"code": 0, "message": "删除成功"})
