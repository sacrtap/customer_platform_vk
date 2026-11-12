"""CRM 充值管理路由

只读 CRM 回款镜像的查询、客户绑定与人工原子导入。所有端点均需鉴权与权限码；
资金写入唯一入口是 `POST /payments/<id>/import`。
"""

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache.base import cache_service
from ..constants.error_codes import ErrorCodes
from ..constants.roles import SUPER_ADMIN_ROLE_NAME
from ..middleware.auth import (
    auth_required,
    customer_scope_user_id,
    get_current_user,
    require_permission,
)
from ..models.crm_recharge import CrmCustomer, CrmPayment, CrmSyncRun
from ..models.customers import Customer
from ..repository import BalanceRepository
from ..services.billing import BalanceService
from ..services.crm_client import (
    CrmAuthError,
    CrmClient,
    CrmConfigError,
    CrmError,
    _validate_base_url,
    is_crm_enabled,
)
from ..services.crm_config import get_crm_config, public_view, save_crm_config
from ..services.crm_recharge import (
    CrmCustomerBindingService,
    CrmImportError,
    CrmRechargeImportService,
    CrmRechargeService,
    _evaluate_payment,
    build_existing_import_response,
    find_imported_recharge,
    resolve_industry_paths,
)
from ..utils.audit_helpers import create_audit_entry
from ..utils.db import begin_write
from ..utils.timezone import cst_today

logger = logging.getLogger(__name__)

crm_recharge_bp = Blueprint("crm_recharge", url_prefix="/api/v1/crm-recharge")


def _error(message: str, status: int):
    mapping = {
        400: ErrorCodes.BAD_REQUEST,
        403: ErrorCodes.FORBIDDEN,
        404: ErrorCodes.NOT_FOUND,
        409: ErrorCodes.BAD_REQUEST,
        502: ErrorCodes.SERVICE_ERROR,
    }
    return json(
        {"code": mapping.get(status, ErrorCodes.BAD_REQUEST), "message": message, "data": None},
        status=status,
    )


def _int_arg(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_month(value) -> Optional[date]:
    if not isinstance(value, str):
        return None
    try:
        year_str, month_str = value.strip().split("-")
        return date(int(year_str), int(month_str), 1)
    except (ValueError, TypeError):
        return None


def _parse_amount_arg(value, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, str):
        raise CrmImportError(f"{field}必须是十进制数字符串", 400)
    text = value.strip()
    if not text:
        raise CrmImportError(f"{field}不能为空", 400)
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError) as e:
        raise CrmImportError(f"{field}格式非法", 400) from e
    if not amount.is_finite():
        raise CrmImportError(f"{field}不能是 NaN 或 Infinity", 400)
    if amount < 0:
        raise CrmImportError(f"{field}不能为负数", 400)
    if amount != amount.quantize(Decimal("0.01")):
        raise CrmImportError(f"{field}最多保留2位小数", 400)
    return amount


async def _get_scoped_customer(
    db: AsyncSession, customer_id: int, scope_user_id: Optional[int]
) -> Optional[Customer]:
    from ..services.crm_recharge import _get_customer_for_scope

    return await _get_customer_for_scope(db, customer_id, scope_user_id)


# ==================== 客户候选 / 绑定 ====================


@crm_recharge_bp.get("/customers/candidates")
@auth_required
@require_permission("customers:edit")
@require_permission("customers:crm_bind")
async def list_crm_customer_candidates(request: Request):
    """CRM 客户推荐/搜索（仅本地镜像，不触发上游请求）"""
    db: AsyncSession = request.ctx.db_session
    customer_id = _int_arg(request.args.get("customer_id"))
    if customer_id is None:
        return _error("缺少 customer_id", 400)

    page = max(1, _int_arg(request.args.get("page")) or 1)
    page_size = min(50, max(1, _int_arg(request.args.get("page_size")) or 20))
    query = request.args.get("query")
    if query is not None and len(query) > 200:
        return _error("搜索关键词最长 200 字符", 400)

    scope_user_id = await customer_scope_user_id(request)
    customer = await _get_scoped_customer(db, customer_id, scope_user_id)
    if customer is None:
        return _error("客户不存在或无权访问", 403)

    service = CrmCustomerBindingService(db)
    data = await service.list_candidates(
        customer=customer,
        corp_id=get_crm_config().corp_id,
        query=query,
        page=page,
        page_size=page_size,
    )
    message = "success"
    if not data["directory_synced"]:
        message = "CRM客户目录尚未同步，请管理员先同步"
    return json({"code": 0, "message": message, "data": data})


@crm_recharge_bp.put("/customers/<customer_id:int>/binding")
@auth_required
@require_permission("customers:edit")
@require_permission("customers:crm_bind")
async def update_crm_customer_binding(request: Request, customer_id: int):
    """绑定/解绑 CRM 客户（独立保存，不依赖客户编辑表单提交）"""
    db: AsyncSession = request.ctx.db_session
    body = request.json if isinstance(request.json, dict) else {}

    raw = body.get("crm_customer_id")
    if raw is None or raw == "":
        crm_customer_id: Optional[int] = None
    elif isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
        return _error("crm_customer_id 非法", 400)
    else:
        crm_customer_id = raw

    scope_user_id = await customer_scope_user_id(request)
    customer = await _get_scoped_customer(db, customer_id, scope_user_id)
    if customer is None:
        return _error("客户不存在或无权访问", 403)

    already_bound = customer.crm_customer_id == crm_customer_id
    candidate_external_id = None
    if crm_customer_id is not None and not already_bound:
        candidate = await db.scalar(
            select(CrmCustomer).where(
                CrmCustomer.id == crm_customer_id,
                CrmCustomer.corp_id == get_crm_config().corp_id,
                CrmCustomer.deleted_at.is_(None),
            )
        )
        if candidate is None:
            return _error("CRM客户不存在或不属于当前企业", 400)
        candidate_external_id = int(candidate.external_id)

        # 上游存在性校验放在事务外（绑定目标必须是当前可见的 CRM 客户）
        if not is_crm_enabled():
            return _error("CRM 未启用，无法绑定时校验上游客户", 400)
        await db.rollback()
        try:
            async with CrmClient() as client:
                upstream = await client.get_customer(candidate_external_id)
        except CrmConfigError as e:
            return _error(str(e), 400)
        except CrmError as e:
            return _error(str(e), 502)
        if _int_arg(upstream.get("id")) != candidate_external_id or not upstream.get("name"):
            return _error("CRM客户不存在或不可见", 502)
    else:
        await db.rollback()

    try:
        async with begin_write(db):
            result = await CrmCustomerBindingService(db).bind(
                customer_id=customer_id,
                crm_customer_id=crm_customer_id,
                corp_id=get_crm_config().corp_id,
            )
    except CrmImportError as e:
        return _error(e.message, e.status)

    await cache_service.invalidate_customer_cache(customer_id)
    return json({"code": 0, "message": "绑定已保存", "data": result})


# ==================== 回款列表 / 详情 ====================


@crm_recharge_bp.get("/payments")
@auth_required
@require_permission("crm_recharge:view")
async def list_crm_payments(request: Request):
    """CRM 回款列表（行级可见性）"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request) or {}
    user_id = _int_arg(user.get("user_id")) or 0

    month = _parse_month(request.args.get("month")) if request.args.get("month") else None
    if request.args.get("month") and month is None:
        return _error("month 格式必须为 YYYY-MM", 400)

    status = request.args.get("status") or "all"
    if status not in ("pending", "imported", "blocked", "all"):
        return _error("status 取值非法", 400)

    page = max(1, _int_arg(request.args.get("page")) or 1)
    page_size = min(100, max(1, _int_arg(request.args.get("page_size")) or 20))
    keyword = request.args.get("keyword")
    if keyword is not None and len(keyword) > 200:
        return _error("搜索关键词最长 200 字符", 400)

    scope_user_id = await customer_scope_user_id(request)
    service = CrmRechargeService(db)
    items, total = await service.list_payments(
        corp_id=get_crm_config().corp_id,
        month=month,
        keyword=keyword,
        status=status,
        page=page,
        page_size=page_size,
        user_id=user_id,
        has_view_all=scope_user_id is None,
    )
    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "crm_enabled": is_crm_enabled(),
            },
        }
    )


@crm_recharge_bp.get("/payments/<payment_id:int>")
@auth_required
@require_permission("crm_recharge:view")
async def get_crm_payment(request: Request, payment_id: int):
    """CRM 回款本地镜像详情"""
    db: AsyncSession = request.ctx.db_session
    scope_user_id = await customer_scope_user_id(request)

    payment = await db.scalar(
        select(CrmPayment).where(
            CrmPayment.id == payment_id,
            CrmPayment.corp_id == get_crm_config().corp_id,
            CrmPayment.deleted_at.is_(None),
        )
    )
    if payment is None:
        return _error("回款不存在", 404)

    if scope_user_id is not None:
        imported = await find_imported_recharge(db, payment.id)
        owner_stmt = select(Customer.id).where(Customer.deleted_at.is_(None))
        if imported is not None:
            owner_stmt = owner_stmt.where(Customer.id == imported.customer_id)
        else:
            owner_stmt = owner_stmt.where(Customer.crm_customer_id == payment.crm_customer_id)
        owner = await db.scalar(
            owner_stmt.where(
                (Customer.manager_id == scope_user_id)
                | (Customer.sales_manager_id == scope_user_id)
            )
        )
        if owner is None:
            return _error("无权查看该回款", 403)

    data = await CrmRechargeService(db).get_payment_detail(payment_id, get_crm_config().corp_id)
    return json({"code": 0, "message": "success", "data": data})


# ==================== 同步 ====================


@crm_recharge_bp.post("/sync-runs")
@auth_required
@require_permission("crm_recharge:sync")
@require_permission("customers:view_all")
async def create_crm_sync_run(request: Request):
    """手动同步指定月份（任意历史月，不可未来月）"""
    db: AsyncSession = request.ctx.db_session
    body = request.json if isinstance(request.json, dict) else {}
    month = _parse_month(body.get("month"))
    if month is None:
        return _error("month 格式必须为 YYYY-MM", 400)
    if month > cst_today().replace(day=1):
        return _error("不能同步未来月份", 400)
    if not is_crm_enabled():
        return _error("CRM 未启用或凭据不完整", 400)

    user = get_current_user(request) or {}
    operator_id = _int_arg(user.get("user_id"))
    service = CrmRechargeService(db)
    # 权限校验/当前用户读取可能已在本 session 上开好隐式事务，先结束再显式开写入事务，
    # 否则 begin() 会抛 "A transaction is already begun"（500）
    await db.rollback()
    try:
        async with begin_write(db):
            run = await service.create_sync_run(
                month=month,
                trigger="manual",
                operator_id=operator_id,
                corp_id=get_crm_config().corp_id,
            )
            run_id = run.id
    except IntegrityError:
        existing = await db.scalar(
            select(CrmSyncRun.id).where(
                CrmSyncRun.corp_id == get_crm_config().corp_id,
                CrmSyncRun.status.in_(("pending", "running")),
            )
        )
        return json(
            {
                "code": ErrorCodes.BAD_REQUEST,
                "message": "已有CRM同步任务正在执行",
                "data": {"run_id": existing},
            },
            status=409,
        )

    request.app.add_task(
        CrmRechargeService.execute_sync_run(run_id, request.app.ctx.async_session_maker)
    )
    return json(
        {"code": 0, "message": "同步任务已创建", "data": {"id": run_id, "status": "pending"}},
        status=202,
    )


@crm_recharge_bp.get("/sync-runs")
@auth_required
@require_permission("crm_recharge:sync")
@require_permission("customers:view_all")
async def list_crm_sync_runs(request: Request):
    """同步执行记录与所选月最近成功时间"""
    db: AsyncSession = request.ctx.db_session
    month = _parse_month(request.args.get("month")) if request.args.get("month") else None
    if request.args.get("month") and month is None:
        return _error("month 格式必须为 YYYY-MM", 400)
    page = max(1, _int_arg(request.args.get("page")) or 1)
    page_size = min(100, max(1, _int_arg(request.args.get("page_size")) or 20))

    stmt = select(CrmSyncRun).where(
        CrmSyncRun.corp_id == get_crm_config().corp_id, CrmSyncRun.deleted_at.is_(None)
    )
    if month is not None:
        stmt = stmt.where(CrmSyncRun.month == month)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await db.scalars(
        stmt.order_by(CrmSyncRun.id.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    items = [
        {
            "id": run.id,
            "month": run.month.isoformat(),
            "trigger": run.trigger,
            "status": run.status,
            "phase": run.phase,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "heartbeat_at": run.heartbeat_at.isoformat() if run.heartbeat_at else None,
            "customer_count": run.customer_count,
            "contract_count": run.contract_count,
            "scanned_contract_count": run.scanned_contract_count,
            "scanned_payment_count": run.scanned_payment_count,
            "payment_count": run.payment_count,
            "eligible_count": run.eligible_count,
            "error_message": run.error_message,
        }
        for run in rows
    ]
    latest_success_at = None
    if month is not None:
        latest_success_at = await CrmRechargeService(db).latest_success_at(
            get_crm_config().corp_id, month
        )
    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "latest_success_at": latest_success_at.isoformat() if latest_success_at else None,
            },
        }
    )


# ==================== 导入充值 ====================


@crm_recharge_bp.post("/payments/<payment_id:int>/import")
@auth_required
@require_permission("crm_recharge:import")
@require_permission("billing:recharge")
async def import_crm_payment(request: Request, payment_id: int):
    """单笔 CRM 回款原子导入（实充 = 源回款金额，赠送额外增加）"""
    db: AsyncSession = request.ctx.db_session
    body = request.json if isinstance(request.json, dict) else {}

    customer_id = _int_arg(body.get("customer_id"))
    if customer_id is None:
        return _error("缺少 customer_id", 400)

    try:
        real_amount = _parse_amount_arg(body.get("real_amount"), "实充金额")
        bonus_raw = body.get("bonus_amount", "0")
        bonus_amount = (
            Decimal("0") if bonus_raw in (None, "") else _parse_amount_arg(bonus_raw, "赠送金额")
        )
        if real_amount == 0 and bonus_amount == 0:
            raise CrmImportError("实充与赠送金额不能同时为0", 400)
    except CrmImportError as e:
        return _error(e.message, e.status)

    user = get_current_user(request) or {}
    operator_id = _int_arg(user.get("user_id")) or 0
    ip_address = request.headers.get(
        "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
    )
    scope_user_id = await customer_scope_user_id(request)

    payment = await db.scalar(
        select(CrmPayment).where(
            CrmPayment.id == payment_id,
            CrmPayment.corp_id == get_crm_config().corp_id,
            CrmPayment.deleted_at.is_(None),
        )
    )
    if payment is None:
        return _error("回款不存在", 404)

    customer = await _get_scoped_customer(db, customer_id, scope_user_id)
    if customer is None:
        return _error("客户不存在或无权访问", 403)

    # 已在别处导入：同目标同金额幂等返回，否则 409（不访问 CRM、不写资金）
    existing = await find_imported_recharge(db, payment_id)
    if existing is not None:
        balance = await BalanceService(BalanceRepository(db)).get_balance_by_customer_id(
            customer_id
        )
        try:
            result = build_existing_import_response(
                existing,
                customer_id=customer_id,
                real_amount=real_amount,
                bonus_amount=bonus_amount,
                balance=balance,
            )
        except CrmImportError as e:
            return _error(e.message, e.status)
        return json({"code": 0, "message": "该回款已导入", "data": result})

    if not is_crm_enabled():
        return _error("CRM 未启用或凭据不完整，无法导入", 400)

    if payment.contract_external_id is None or payment.external_id is None:
        return _error("CRM回款缺少合同信息，无法复核", 502)

    # 事务外实时复核源回款前先复制标量（rollback 后 ORM 对象会过期）
    contract_external_id = int(payment.contract_external_id)
    payment_external_id = int(payment.external_id)
    payment_receive_date = payment.receive_date
    await db.rollback()
    try:
        async with CrmClient() as client:
            fields = await client.get_payment_fields()
            allowed_paths = resolve_industry_paths(fields)
            details = await client.get_payment(contract_external_id, payment_external_id)
    except CrmConfigError as e:
        return _error(str(e), 400)
    except CrmError as e:
        return _error(str(e), 502)

    if _int_arg(details.get("id")) not in (None, payment_external_id):
        return _error("CRM回款详情ID与本地记录不一致", 409)

    evaluated = _evaluate_payment(
        details=details,
        fallback_date=None,
        fallback_status="approved",
        allowed_paths=allowed_paths,
        month_start=payment_receive_date.replace(day=1) if payment_receive_date else date.min,
        month_end=date.max,
        customer_map={},
        contract_external_id=contract_external_id,
    )
    source_values = evaluated["values"]
    if not source_values["eligible"]:
        return _error(source_values["blocked_reason"] or "CRM回款不满足导入条件", 400)
    if source_values["approve_status"] != "approved":
        return _error("CRM回款审批未通过", 400)

    try:
        async with begin_write(db):
            result = await CrmRechargeImportService(db).import_payment(
                payment_id=payment_id,
                customer_id=customer_id,
                real_amount=real_amount,
                bonus_amount=bonus_amount,
                operator_id=operator_id,
                corp_id=get_crm_config().corp_id,
                source_snapshot=evaluated["snapshot"],
                ip_address=ip_address,
                scope_user_id=scope_user_id,
            )
    except CrmImportError as e:
        return _error(e.message, e.status)

    # 提交成功后失效余额/客户/分析缓存（含充值趋势），失败不影响已完成的入账
    await cache_service.invalidate_analytics_cache()
    await cache_service.invalidate_customer_cache(customer_id)
    await cache_service.invalidate_pattern("cache:billing_consumption:*")

    return json({"code": 0, "message": "充值成功", "data": result})


@crm_recharge_bp.post("/payments/<payment_id:int>/import/revoke")
@auth_required
@require_permission("crm_recharge:revoke")
@require_permission("billing:recharge")
async def revoke_crm_import(request: Request, payment_id: int):
    """撤销一笔 CRM 充值导入（回退余额并释放该回款）

    余额已被消耗时仅超级管理员可 `force` 撤销，撤销结果标记 `needs_manual_reconciliation`。
    撤销不会改绑定关系：正确顺序是「撤销 → 改绑 → 重新导入」。
    """
    db: AsyncSession = request.ctx.db_session
    body = request.json if isinstance(request.json, dict) else {}

    customer_id = _int_arg(body.get("customer_id"))
    if customer_id is None:
        return _error("缺少 customer_id", 400)
    reason = str(body.get("reason") or "").strip()
    if not reason:
        return _error("撤销原因必填", 400)
    if len(reason) > 500:
        return _error("撤销原因不能超过500字", 400)
    force = bool(body.get("force"))

    user = get_current_user(request) or {}
    operator_id = _int_arg(user.get("user_id")) or 0
    is_super_admin = SUPER_ADMIN_ROLE_NAME in (user.get("roles") or [])
    ip_address = request.headers.get(
        "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
    )
    scope_user_id = await customer_scope_user_id(request)

    # 权限/用户读取可能已开好隐式事务，先结束再显式开写入事务
    await db.rollback()
    try:
        async with begin_write(db):
            result = await CrmRechargeImportService(db).revoke_import(
                payment_id=payment_id,
                customer_id=customer_id,
                reason=reason,
                operator_id=operator_id,
                corp_id=get_crm_config().corp_id,
                is_super_admin=is_super_admin,
                force=force,
                ip_address=ip_address,
                scope_user_id=scope_user_id,
            )
    except CrmImportError as e:
        return _error(e.message, e.status)

    await cache_service.invalidate_analytics_cache()
    await cache_service.invalidate_customer_cache(customer_id)
    await cache_service.invalidate_pattern("cache:billing_consumption:*")

    message = "已撤销CRM充值导入"
    if result["needs_manual_reconciliation"]:
        message += "（余额不足，已标记线下核对）"
    return json({"code": 0, "message": message, "data": result})


# ============================================================
# CRM 配置（开关 + 凭据）：页面维护、保存前验证、随时更换
# ============================================================


def _settings_payload() -> dict:
    view = public_view()
    view["crm_enabled_for_requests"] = is_crm_enabled()
    return view


def _effective_credentials(body: dict) -> dict:
    """表单值优先，未填写的回退到当前生效配置（用于「验证」不落库场景）"""
    cfg = get_crm_config()
    base_url = str(body.get("base_url") or cfg.base_url).strip()
    corp_id = str(body.get("corp_id") if body.get("corp_id") is not None else cfg.corp_id).strip()
    phone = str(body.get("phone") if body.get("phone") is not None else cfg.phone).strip()
    password = body.get("password")
    password = password if isinstance(password, str) and password else cfg.password
    if body.get("clear_password") is True:
        password = ""
    return {"base_url": base_url, "corp_id": corp_id, "phone": phone, "password": password}


@crm_recharge_bp.get("/settings")
@auth_required
@require_permission("crm_recharge:view")
async def get_crm_settings(request: Request):
    """读取 CRM 开关与凭据状态（密码只返回是否已配置）"""
    return json({"code": 0, "message": "success", "data": _settings_payload()})


@crm_recharge_bp.post("/settings/test")
@auth_required
@require_permission("crm_recharge:config")
async def test_crm_credentials(request: Request):
    """用表单里正在填写的账号密码做只读自检（登录 + 客户列表 1 条）

    不写库、不落镜像、不触发充值；密码留空时使用已保存的密码。
    """
    body = request.json or {}
    try:
        creds = _effective_credentials(body)
    except Exception as e:  # pragma: no cover - 防御
        return _error(f"凭据解析失败: {e}", 400)

    if not creds["corp_id"] or not creds["phone"] or not creds["password"]:
        return _error("企业ID、登录手机号、登录密码必须全部填写后才能验证", 400)
    try:
        _validate_base_url(creds["base_url"])
    except CrmConfigError as e:
        return _error(str(e), 400)

    from ..services.crm_client import probe_credentials

    try:
        result = await probe_credentials(**creds)
    except CrmAuthError as e:
        return _error(str(e), 400)
    except CrmConfigError as e:
        return _error(str(e), 400)
    except CrmError as e:
        return _error(f"CRM 接口不可用，暂时无法验证: {e}", 502)

    warning = result.get("warning")
    return json(
        {
            "code": 0,
            "message": "登录凭据有效（客户列表暂不可读）" if warning else "凭据验证通过",
            "data": {
                "ok": True,
                "corp_id": result.get("corp_id"),
                "customer_total": result.get("customer_total"),
                "warning": warning,
            },
        }
    )


@crm_recharge_bp.put("/settings")
@auth_required
@require_permission("crm_recharge:config")
async def update_crm_settings(request: Request):
    """保存或更换 CRM 开关与凭据

    - 密码留空 = 保留已保存密码；`clear_password=true` = 清除密码
    - 默认保存前先验证账号密码；`force=true` 可在上游临时不可用时跳过验证
    """
    body = request.json or {}
    user = get_current_user(request)
    operator_id = user.get("user_id") if isinstance(user, dict) else None
    db_session: AsyncSession = request.ctx.db_session

    current = get_crm_config()
    enabled = body.get("enabled")
    enabled = current.enabled if enabled is None else bool(enabled)
    try:
        creds = _effective_credentials(body)
        _validate_base_url(creds["base_url"])
    except CrmConfigError as e:
        return _error(str(e), 400)
    except Exception as e:  # pragma: no cover - 防御
        return _error(f"配置解析失败: {e}", 400)

    password_arg = body.get("password")
    password_arg = password_arg if isinstance(password_arg, str) and password_arg else None
    clear_password = body.get("clear_password") is True

    verify = body.get("verify", True) is not False
    force = body.get("force") is True
    verification: dict | None = None
    # 显式清除密码时无凭据可验证，直接保存（等价于停用远程能力）
    if verify and not force and not clear_password:
        if not creds["corp_id"] or not creds["phone"] or not creds["password"]:
            return _error("企业ID、登录手机号、登录密码必须全部填写后才能保存", 400)
        from ..services.crm_client import probe_credentials

        try:
            verification = await probe_credentials(**creds)
        except CrmAuthError as e:
            return json(
                {
                    "code": ErrorCodes.CRM_CREDENTIAL_VERIFY_FAILED,
                    "message": str(e),
                    "data": {"can_force": True},
                },
                status=400,
            )
        except CrmConfigError as e:
            return _error(str(e), 400)
        except CrmError as e:
            return json(
                {
                    "code": ErrorCodes.CRM_UPSTREAM_UNAVAILABLE,
                    "message": f"保存前验证失败（CRM 接口不可用）: {e}",
                    "data": {"can_force": True},
                },
                status=502,
            )

    try:
        # 中间件读取当前用户时已开启隐式事务，先结束再显式开启写入事务
        await db_session.commit()
        async with begin_write(db_session):
            cfg = await save_crm_config(
                db_session,
                enabled=enabled,
                base_url=creds["base_url"],
                corp_id=creds["corp_id"],
                phone=creds["phone"],
                password=password_arg,
                clear_password=clear_password,
                updated_by=operator_id,
            )
            await create_audit_entry(
                db_session,
                user_id=operator_id,
                action="update",
                module="crm_recharge",
                record_type="crm_setting",
                changes={
                    "enabled": {"before": current.enabled, "after": cfg.enabled},
                    "corp_id": {"before": current.corp_id, "after": cfg.corp_id},
                    "phone_changed": current.phone != cfg.phone,
                    "password_changed": bool(password_arg) or clear_password,
                    "base_url": {"before": current.base_url, "after": cfg.base_url},
                },
                ip_address=request.headers.get(
                    "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
                ),
            )
    except Exception as e:
        logger.error("保存 CRM 配置失败: %s", e)
        return _error(f"保存失败: {e}", 500)

    # 配置变更后立即重注册/移除定时同步任务（失败不影响已保存的配置）
    try:
        from ..tasks.scheduler import apply_crm_sync_job

        apply_crm_sync_job(request.app.ctx.async_session_maker, cfg.active)
    except Exception as e:  # pragma: no cover
        logger.warning("CRM 定时同步任务调整失败（配置已保存）: %s", e)

    data = _settings_payload()
    message = "CRM 配置已保存"
    if verification is not None:
        data["verified_customer_total"] = verification.get("customer_total")
        if verification.get("warning"):
            data["verification_warning"] = verification["warning"]
            message = "CRM 配置已保存（登录凭据有效，客户列表暂不可读）"
    return json({"code": 0, "message": message, "data": data})
