"""余额管理路由 — 充值、记录、统计、趋势"""

import logging
from datetime import datetime
from decimal import Decimal

from sanic.request import Request
from sanic.response import json
from sqlalchemy.ext.asyncio import AsyncSession

from ...cache.base import cache_service
from ...middleware.auth import auth_required, get_current_user, require_permission
from ...models.industry_type import IndustryType
from ...repository import BalanceRepository
from ...services.billing import BalanceService
from ...utils.audit_helpers import create_audit_entry
from . import billing_bp

logger = logging.getLogger(__name__)


@billing_bp.get("/balances")
@auth_required
@require_permission("billing:view")
async def get_balances(request: Request):
    """获取余额列表（支持服务端筛选、排序和分页）"""
    db: AsyncSession = request.ctx.db_session

    from sqlalchemy import func, select
    from sqlalchemy.orm import selectinload

    from ...models.billing import CustomerBalance, RechargeRecord
    from ...models.customers import Customer, CustomerProfile

    # 分页参数
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    page_size = min(page_size, 100)

    # 筛选参数
    keyword = request.args.get("keyword")  # 客户名称模糊搜索
    customer_id = int(request.args.get("customer_id")) if request.args.get("customer_id") else None

    # 新增筛选参数
    account_type = request.args.get("account_type")
    industry = request.args.get("industry")  # 多选逗号分隔
    manager_id = int(request.args.get("manager_id")) if request.args.get("manager_id") else None
    sales_manager_id = (
        int(request.args.get("sales_manager_id")) if request.args.get("sales_manager_id") else None
    )
    recharge_date_from = request.args.get("recharge_date_from")
    recharge_date_to = request.args.get("recharge_date_to")
    tag_ids = request.args.get("tag_ids")  # 多选逗号分隔
    is_key_customer = request.args.get("is_key_customer")
    if is_key_customer is not None and is_key_customer.strip() != "":
        if is_key_customer.lower() not in ("true", "false"):
            return json(
                {"code": 40001, "message": "is_key_customer 参数必须为 'true' 或 'false'"},
                status=400,
            )
        is_key_customer = is_key_customer.lower() == "true"

    is_real_estate = request.args.get("is_real_estate")
    if is_real_estate is not None and is_real_estate.strip() != "":
        if is_real_estate.lower() not in ("true", "false"):
            return json(
                {"code": 40001, "message": "is_real_estate 参数必须为 'true' 或 'false'"},
                status=400,
            )
        is_real_estate = is_real_estate.lower() == "true"
    else:
        is_real_estate = None

    settlement_type = request.args.get("settlement_type")
    if settlement_type is not None and settlement_type.strip() == "":
        settlement_type = None

    # 余额范围筛选
    balance_min = (
        float(request.args.get("balance_min")) if request.args.get("balance_min") else None
    )
    balance_max = (
        float(request.args.get("balance_max")) if request.args.get("balance_max") else None
    )

    # 排序参数
    sort_by = request.args.get("sort_by", "customer.id")  # 默认按客户 ID 升序
    sort_order = request.args.get("sort_order", "asc")
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"

    # 排序字段映射（前端字段 -> SQLAlchemy 表达式）
    sort_field_map = {
        "company_id": Customer.company_id,
        "customer_name": Customer.name,
        "total_amount": CustomerBalance.total_amount,
        "used_total": CustomerBalance.used_total,
        "last_recharge_at": "last_recharge_at",  # 特殊处理
    }

    base_stmt = (
        select(CustomerBalance)
        .join(Customer, CustomerBalance.customer_id == Customer.id)
        .outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
        .where(
            CustomerBalance.deleted_at.is_(None),
            Customer.deleted_at.is_(None),
        )
    )

    # 服务端过滤
    if customer_id:
        base_stmt = base_stmt.where(CustomerBalance.customer_id == customer_id)
    if keyword:
        base_stmt = base_stmt.where(Customer.name.ilike(f"%{keyword}%"))
    if account_type:
        base_stmt = base_stmt.where(Customer.account_type == account_type)
    if industry:
        # 多选逗号分隔，使用 IN 查询（JOIN IndustryType 按名称过滤）
        industry_list = [i.strip() for i in industry.split(",") if i.strip()]
        if industry_list:
            base_stmt = base_stmt.outerjoin(
                IndustryType, CustomerProfile.industry_type_id == IndustryType.id
            ).where(IndustryType.name.in_(industry_list))
    if manager_id:
        base_stmt = base_stmt.where(Customer.manager_id == manager_id)
    if sales_manager_id:
        base_stmt = base_stmt.where(Customer.sales_manager_id == sales_manager_id)
    if is_key_customer is not None:
        base_stmt = base_stmt.where(Customer.is_key_customer == is_key_customer)

    if is_real_estate is not None:
        base_stmt = base_stmt.where(Customer.is_real_estate == is_real_estate)

    if settlement_type:
        base_stmt = base_stmt.where(Customer.settlement_type == settlement_type)

    # 余额范围过滤
    if balance_min is not None:
        base_stmt = base_stmt.where(CustomerBalance.total_amount >= balance_min)
    if balance_max is not None:
        base_stmt = base_stmt.where(CustomerBalance.total_amount <= balance_max)

    # 充值时间范围过滤（需要 JOIN RechargeRecord 子查询）
    if recharge_date_from or recharge_date_to:
        recharge_filter_stmt = (
            select(RechargeRecord.customer_id)
            .where(RechargeRecord.deleted_at.is_(None))
            .group_by(RechargeRecord.customer_id)
        )
        # 使用 HAVING 子句过滤（聚合函数必须在 HAVING 中）
        if recharge_date_from:
            try:
                from_dt = datetime.fromisoformat(recharge_date_from)
                recharge_filter_stmt = recharge_filter_stmt.having(
                    func.max(RechargeRecord.created_at) >= from_dt
                )
            except (ValueError, TypeError):
                logger.warning("Invalid recharge_date_from format: %s", recharge_date_from)
        if recharge_date_to:
            try:
                to_dt = datetime.fromisoformat(recharge_date_to).replace(
                    hour=23, minute=59, second=59
                )
                recharge_filter_stmt = recharge_filter_stmt.having(
                    func.max(RechargeRecord.created_at) <= to_dt
                )
            except (ValueError, TypeError):
                logger.warning("Invalid recharge_date_to format: %s", recharge_date_to)

        base_stmt = base_stmt.where(CustomerBalance.customer_id.in_(recharge_filter_stmt))

    # 标签筛选（需要 JOIN CustomerTag 表）
    if tag_ids:
        from ...models.customers import CustomerTag  # pyright: ignore[reportAttributeAccessIssue]

        tag_id_list = [int(t.strip()) for t in tag_ids.split(",") if t.strip()]
        if tag_id_list:
            tag_customer_subq = (
                select(CustomerTag.customer_id)
                .where(
                    CustomerTag.tag_id.in_(tag_id_list),
                    CustomerTag.deleted_at.is_(None),
                )
                .group_by(CustomerTag.customer_id)
            )
            base_stmt = base_stmt.where(Customer.id.in_(tag_customer_subq))

    # 总数查询
    count_stmt = (
        select(func.count(CustomerBalance.id))
        .join(Customer, CustomerBalance.customer_id == Customer.id)
        .outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
        .where(
            CustomerBalance.deleted_at.is_(None),
            Customer.deleted_at.is_(None),
        )
    )
    if customer_id:
        count_stmt = count_stmt.where(CustomerBalance.customer_id == customer_id)
    if keyword:
        count_stmt = count_stmt.where(Customer.name.ilike(f"%{keyword}%"))
    if account_type:
        count_stmt = count_stmt.where(Customer.account_type == account_type)
    if industry:
        industry_list = [i.strip() for i in industry.split(",") if i.strip()]
        if industry_list:
            count_stmt = count_stmt.outerjoin(
                IndustryType, CustomerProfile.industry_type_id == IndustryType.id
            ).where(IndustryType.name.in_(industry_list))
    if manager_id:
        count_stmt = count_stmt.where(Customer.manager_id == manager_id)
    if sales_manager_id:
        count_stmt = count_stmt.where(Customer.sales_manager_id == sales_manager_id)
    if is_key_customer is not None:
        count_stmt = count_stmt.where(Customer.is_key_customer == is_key_customer)

    if is_real_estate is not None:
        count_stmt = count_stmt.where(Customer.is_real_estate == is_real_estate)

    if settlement_type:
        count_stmt = count_stmt.where(Customer.settlement_type == settlement_type)
    if balance_min is not None:
        count_stmt = count_stmt.where(CustomerBalance.total_amount >= balance_min)
    if balance_max is not None:
        count_stmt = count_stmt.where(CustomerBalance.total_amount <= balance_max)
    if recharge_date_from or recharge_date_to:
        recharge_filter_stmt = (
            select(RechargeRecord.customer_id)
            .where(RechargeRecord.deleted_at.is_(None))
            .group_by(RechargeRecord.customer_id)
        )
        if recharge_date_from:
            from_dt = datetime.fromisoformat(recharge_date_from)
            recharge_filter_stmt = recharge_filter_stmt.having(
                func.max(RechargeRecord.created_at) >= from_dt
            )
        if recharge_date_to:
            to_dt = datetime.fromisoformat(recharge_date_to).replace(hour=23, minute=59, second=59)
            recharge_filter_stmt = recharge_filter_stmt.having(
                func.max(RechargeRecord.created_at) <= to_dt
            )
        count_stmt = count_stmt.where(CustomerBalance.customer_id.in_(recharge_filter_stmt))
    if tag_ids:
        from ...models.customers import CustomerTag  # pyright: ignore[reportAttributeAccessIssue]

        tag_id_list = [int(t.strip()) for t in tag_ids.split(",") if t.strip()]
        if tag_id_list:
            tag_customer_subq = (
                select(CustomerTag.customer_id)
                .where(
                    CustomerTag.tag_id.in_(tag_id_list),
                    CustomerTag.deleted_at.is_(None),
                )
                .group_by(CustomerTag.customer_id)
            )
            count_stmt = count_stmt.where(Customer.id.in_(tag_customer_subq))

    total = (await db.execute(count_stmt)).scalar()

    # 排序
    if sort_by in sort_field_map:
        field = sort_field_map[sort_by]
        if field == "last_recharge_at":
            # 最新充值时间排序：使用子查询
            last_recharge_subq = (
                select(
                    RechargeRecord.customer_id,
                    func.max(RechargeRecord.created_at).label("last_recharge_at"),
                )
                .where(RechargeRecord.deleted_at.is_(None))
                .group_by(RechargeRecord.customer_id)
                .subquery()
            )
            base_stmt = base_stmt.outerjoin(
                last_recharge_subq, CustomerBalance.customer_id == last_recharge_subq.c.customer_id
            )
            order_expr = last_recharge_subq.c.last_recharge_at
            # NULL 值统一排到最后，二级排序按客户 ID 保证稳定性
            if sort_order == "asc":
                base_stmt = base_stmt.order_by(order_expr.asc().nulls_last(), Customer.id.asc())
            else:
                base_stmt = base_stmt.order_by(order_expr.desc().nulls_last(), Customer.id.asc())
        else:
            order_expr = field
            base_stmt = base_stmt.order_by(
                order_expr.asc() if sort_order == "asc" else order_expr.desc()
            )
    else:
        # 默认排序：按客户 ID 升序
        base_stmt = base_stmt.order_by(Customer.id.asc())

    # 分页查询
    stmt = base_stmt.options(
        selectinload(CustomerBalance.customer)
        .selectinload(Customer.profile)
        .selectinload(CustomerProfile.industry_type)
    )
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    balances = result.scalars().all()

    # 批量获取最新充值时间
    customer_ids = [b.customer_id for b in balances]
    last_recharge_map = {}
    if customer_ids:
        recharge_result = await db.execute(
            select(
                RechargeRecord.customer_id,
                func.max(RechargeRecord.created_at).label("last_recharge_at"),
            )
            .where(
                RechargeRecord.customer_id.in_(customer_ids), RechargeRecord.deleted_at.is_(None)
            )
            .group_by(RechargeRecord.customer_id)
        )
        for row in recharge_result.all():
            last_recharge_map[row.customer_id] = row.last_recharge_at

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": b.id,
                        "customer_id": b.customer_id,
                        "company_id": b.customer.company_id if b.customer else None,
                        "customer_name": b.customer.name if b.customer else None,
                        "account_type": b.customer.account_type if b.customer else None,
                        "industry_type": b.customer.profile.industry_type.name
                        if b.customer and b.customer.profile and b.customer.profile.industry_type
                        else None,
                        "settlement_type": (b.customer.settlement_type if b.customer else None),
                        "is_key_customer": (b.customer.is_key_customer if b.customer else False),
                        "total_amount": float(b.total_amount) if b.total_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                        "real_amount": float(b.real_amount) if b.real_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                        "bonus_amount": float(b.bonus_amount) if b.bonus_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                        "used_total": float(b.used_total) if b.used_total else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                        "used_real": float(b.used_real) if b.used_real else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                        "used_bonus": float(b.used_bonus) if b.used_bonus else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                        "last_recharge_at": (
                            last_recharge_map[b.customer_id].isoformat()
                            if b.customer_id in last_recharge_map
                            and last_recharge_map[b.customer_id]
                            else None
                        ),
                    }
                    for b in balances
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@billing_bp.get("/balance-stats")
@auth_required
@require_permission("billing:view")
async def get_balance_stats(request: Request):
    """获取余额统计概览（用于 KPI 卡片）

    支持与列表页一致的筛选参数（industry, account_type），
    确保 KPI 统计数字与列表筛选结果保持一致。
    """
    db: AsyncSession = request.ctx.db_session

    from sqlalchemy import func, select

    from ...models.billing import CustomerBalance, RechargeRecord
    from ...models.customers import Customer, CustomerProfile
    from ...models.industry_type import IndustryType

    # 筛选参数（与列表页 get_balances 保持一致）
    industry = request.args.get("industry")  # 多选逗号分隔
    account_type = request.args.get("account_type")

    # 基础条件
    base_condition = [
        CustomerBalance.deleted_at.is_(None),
        Customer.deleted_at.is_(None),
    ]

    # 行业过滤条件（需要 JOIN IndustryType）
    industry_filter_stmts = []
    if industry:
        industry_list = [i.strip() for i in industry.split(",") if i.strip()]
        if industry_list:
            industry_filter_stmts.append(IndustryType.name.in_(industry_list))

    # 账号类型过滤条件
    account_type_filter_stmts = []
    if account_type:
        account_type_filter_stmts.append(Customer.account_type == account_type)

    def apply_filters(stmt, need_industry_join=False):
        """为查询语句添加基础 + 筛选条件"""
        for cond in base_condition:
            stmt = stmt.where(cond)
        if account_type_filter_stmts:
            for cond in account_type_filter_stmts:
                stmt = stmt.where(cond)
        if industry_filter_stmts and need_industry_join:
            for cond in industry_filter_stmts:
                stmt = stmt.where(cond)
        return stmt

    # 总余额（所有客户余额总和）
    total_balance_stmt = select(func.coalesce(func.sum(CustomerBalance.total_amount), 0)).join(
        Customer, CustomerBalance.customer_id == Customer.id
    )
    if industry_filter_stmts:
        total_balance_stmt = total_balance_stmt.outerjoin(
            CustomerProfile, Customer.id == CustomerProfile.customer_id
        ).outerjoin(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)
        total_balance_stmt = apply_filters(total_balance_stmt, need_industry_join=True)
    else:
        total_balance_stmt = apply_filters(total_balance_stmt)
    total_balance = (await db.execute(total_balance_stmt)).scalar() or 0

    # 本月充值笔数和金额（需要关联客户表应用筛选条件）
    # 金额 = 实充金额 + 赠送金额，与充值记录的 total_amount 一致
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_recharge_base = select(
        func.count(RechargeRecord.id).label("count"),
        func.coalesce(func.sum(RechargeRecord.real_amount + RechargeRecord.bonus_amount), 0).label(
            "amount"
        ),
        func.coalesce(func.sum(RechargeRecord.real_amount), 0).label("real_amount_sum"),
        func.coalesce(func.sum(RechargeRecord.bonus_amount), 0).label("bonus_amount_sum"),
    ).where(
        RechargeRecord.deleted_at.is_(None),
        RechargeRecord.created_at >= month_start,
    )

    # 如果有行业/账号类型筛选，需要关联客户表
    if industry_filter_stmts or account_type_filter_stmts:
        this_month_recharge_base = this_month_recharge_base.join(
            Customer, RechargeRecord.customer_id == Customer.id
        )
        if industry_filter_stmts:
            this_month_recharge_base = this_month_recharge_base.outerjoin(
                CustomerProfile, Customer.id == CustomerProfile.customer_id
            ).outerjoin(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)
        this_month_recharge_base = this_month_recharge_base.where(Customer.deleted_at.is_(None))
        if account_type_filter_stmts:
            for cond in account_type_filter_stmts:
                this_month_recharge_base = this_month_recharge_base.where(cond)
        if industry_filter_stmts:
            for cond in industry_filter_stmts:
                this_month_recharge_base = this_month_recharge_base.where(cond)

    this_month_result = (await db.execute(this_month_recharge_base)).one()
    this_month_count = this_month_result.count or 0
    this_month_amount = float(this_month_result.amount or 0)
    this_month_real_amount = float(this_month_result.real_amount_sum or 0)
    this_month_bonus_amount = float(this_month_result.bonus_amount_sum or 0)

    # 余额不足客户数（余额 < 10000 且 > 0）
    LOW_BALANCE_THRESHOLD = 10000
    low_balance_stmt = (
        select(func.count(CustomerBalance.id))
        .join(Customer, CustomerBalance.customer_id == Customer.id)
        .where(
            CustomerBalance.total_amount < LOW_BALANCE_THRESHOLD,
            CustomerBalance.total_amount > 0,
        )
    )
    if industry_filter_stmts:
        low_balance_stmt = low_balance_stmt.outerjoin(
            CustomerProfile, Customer.id == CustomerProfile.customer_id
        ).outerjoin(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)
        low_balance_stmt = apply_filters(low_balance_stmt, need_industry_join=True)
    else:
        low_balance_stmt = apply_filters(low_balance_stmt)
    low_balance_count = (await db.execute(low_balance_stmt)).scalar() or 0

    # 零余额客户数
    zero_balance_stmt = (
        select(func.count(CustomerBalance.id))
        .join(Customer, CustomerBalance.customer_id == Customer.id)
        .where(CustomerBalance.total_amount == 0)
    )
    if industry_filter_stmts:
        zero_balance_stmt = zero_balance_stmt.outerjoin(
            CustomerProfile, Customer.id == CustomerProfile.customer_id
        ).outerjoin(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)
        zero_balance_stmt = apply_filters(zero_balance_stmt, need_industry_join=True)
    else:
        zero_balance_stmt = apply_filters(zero_balance_stmt)
    zero_balance_count = (await db.execute(zero_balance_stmt)).scalar() or 0

    # 客户总数
    total_customers_stmt = select(func.count(CustomerBalance.id)).join(
        Customer, CustomerBalance.customer_id == Customer.id
    )
    if industry_filter_stmts:
        total_customers_stmt = total_customers_stmt.outerjoin(
            CustomerProfile, Customer.id == CustomerProfile.customer_id
        ).outerjoin(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)
        total_customers_stmt = apply_filters(total_customers_stmt, need_industry_join=True)
    else:
        total_customers_stmt = apply_filters(total_customers_stmt)
    total_customers = (await db.execute(total_customers_stmt)).scalar() or 0

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "total_balance": float(total_balance),
                "total_customers": total_customers,
                "this_month_count": this_month_count,
                "this_month_amount": this_month_amount,
                "this_month_real_amount": this_month_real_amount,
                "this_month_bonus_amount": this_month_bonus_amount,
                "low_balance_count": low_balance_count,
                "zero_balance_count": zero_balance_count,
            },
        }
    )


@billing_bp.get("/customers/<customer_id:int>/balance")
@auth_required
@require_permission("billing:view")
async def get_customer_balance(request: Request, customer_id: int):
    """获取客户余额"""
    db: AsyncSession = request.ctx.db_session
    balance_service = BalanceService(BalanceRepository(db))

    balance = await balance_service.get_balance_by_customer_id(customer_id)

    if not balance:
        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "total_amount": 0,
                    "real_amount": 0,
                    "bonus_amount": 0,
                    "used_total": 0,
                    "used_real": 0,
                    "used_bonus": 0,
                },
            }
        )

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "total_amount": float(balance.total_amount) if balance.total_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "real_amount": float(balance.real_amount) if balance.real_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "bonus_amount": float(balance.bonus_amount) if balance.bonus_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "used_total": float(balance.used_total) if balance.used_total else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "used_real": float(balance.used_real) if balance.used_real else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "used_bonus": float(balance.used_bonus) if balance.used_bonus else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
            },
        }
    )


@billing_bp.post("/recharge")
@auth_required
@require_permission("billing:recharge")
async def recharge(request: Request):
    """
    客户充值

    Body:
    {
        "customer_id": 1,
        "real_amount": 10000.00,
        "bonus_amount": 2000.00,
        "payment_proof": "/uploads/proof.png",
        "remark": "Q1 季度充值"
    }
    """
    db: AsyncSession = request.ctx.db_session
    data = request.json
    user = get_current_user(request)

    customer_id = data.get("customer_id")
    real_amount = Decimal(str(data.get("real_amount", 0)))
    bonus_amount = Decimal(str(data.get("bonus_amount", 0)))

    if not customer_id or real_amount == 0:
        return json(
            {"code": 40001, "message": "客户 ID 和实充金额不能为空"},
            status=400,
        )

    balance_service = BalanceService(BalanceRepository(db))

    # 获取充值前余额
    balance_before = await balance_service.get_balance_by_customer_id(customer_id)

    record = await balance_service.recharge(
        customer_id=customer_id,
        real_amount=real_amount,
        bonus_amount=bonus_amount,
        operator_id=user["user_id"] if user else 1,
        payment_proof=data.get("payment_proof"),
        remark=data.get("remark"),
    )

    # 充值后清除相关缓存
    await cache_service.invalidate_analytics_cache("health")
    await cache_service.invalidate_analytics_cache("dashboard")
    await cache_service.invalidate_customer_cache(customer_id)

    # 获取充值后的余额（用于返回给前端局部更新）
    balance_after = await balance_service.get_balance_by_customer_id(customer_id)

    # 记录充值审计日志
    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="recharge",
        module="billing",
        record_id=record.id,  # pyright: ignore[reportArgumentType]
        record_type="recharge",
        changes={
            "before": {
                "real_amount": float(balance_before.real_amount) if balance_before else 0,  # pyright: ignore[reportArgumentType]
                "bonus_amount": float(balance_before.bonus_amount) if balance_before else 0,  # pyright: ignore[reportArgumentType]
            },
            "after": {
                "real_amount": float(balance_after.real_amount) if balance_after else 0,  # pyright: ignore[reportArgumentType]
                "bonus_amount": float(balance_after.bonus_amount) if balance_after else 0,  # pyright: ignore[reportArgumentType]
                "recharge_real": float(real_amount),
                "recharge_bonus": float(bonus_amount),
            },
            "customer_id": customer_id,
        },
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json(
        {
            "code": 0,
            "message": "充值成功",
            "data": {
                "id": record.id,
                "customer_id": record.customer_id,
                "real_amount": float(record.real_amount),  # pyright: ignore[reportArgumentType]
                "bonus_amount": float(record.bonus_amount),  # pyright: ignore[reportArgumentType]
                "total_amount": float(record.real_amount + record.bonus_amount),  # pyright: ignore[reportArgumentType]
                # 充值后的完整余额信息（用于前端局部更新）
                "balance": {
                    "total_amount": (
                        float(balance_after.total_amount)  # pyright: ignore[reportArgumentType]
                        if balance_after and balance_after.total_amount  # pyright: ignore[reportGeneralTypeIssues]
                        else 0
                    ),
                    "real_amount": (
                        float(balance_after.real_amount)  # pyright: ignore[reportArgumentType]
                        if balance_after and balance_after.real_amount  # pyright: ignore[reportGeneralTypeIssues]
                        else 0
                    ),
                    "bonus_amount": (
                        float(balance_after.bonus_amount)  # pyright: ignore[reportArgumentType]
                        if balance_after and balance_after.bonus_amount  # pyright: ignore[reportGeneralTypeIssues]
                        else 0
                    ),
                    "used_total": (
                        float(balance_after.used_total)  # pyright: ignore[reportArgumentType]
                        if balance_after and balance_after.used_total  # pyright: ignore[reportGeneralTypeIssues]
                        else 0
                    ),
                    "used_real": float(balance_after.used_real)  # pyright: ignore[reportArgumentType]
                    if balance_after and balance_after.used_real  # pyright: ignore[reportGeneralTypeIssues]
                    else 0,
                    "used_bonus": (
                        float(balance_after.used_bonus)  # pyright: ignore[reportArgumentType]
                        if balance_after and balance_after.used_bonus  # pyright: ignore[reportGeneralTypeIssues]
                        else 0
                    ),
                },
            },
        },
        status=201,
    )


@billing_bp.get("/recharge-records")
@auth_required
@require_permission("billing:view")
async def get_recharge_records(request: Request):
    """获取充值记录列表"""
    db: AsyncSession = request.ctx.db_session
    balance_service = BalanceService(BalanceRepository(db))

    customer_id = int(request.args.get("customer_id")) if request.args.get("customer_id") else None
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))

    records, total = await balance_service.get_recharge_records(
        customer_id=customer_id,
        page=page,
        page_size=page_size,
    )
    # 批量查询客户名称
    from sqlalchemy import select

    from ...models.customers import Customer

    customer_ids = list(set(r.customer_id for r in records if r.customer_id))  # pyright: ignore[reportGeneralTypeIssues]
    customer_name_map = {}
    if customer_ids:
        customer_result = await db.execute(
            select(Customer.id, Customer.name).where(Customer.id.in_(customer_ids))
        )
        customer_name_map = {row[0]: row[1] for row in customer_result}

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": r.id,
                        "customer_id": r.customer_id,
                        "customer_name": customer_name_map.get(r.customer_id, ""),
                        "real_amount": float(r.real_amount),  # pyright: ignore[reportArgumentType]
                        "bonus_amount": float(r.bonus_amount),  # pyright: ignore[reportArgumentType]
                        "total_amount": float(r.real_amount + r.bonus_amount),  # pyright: ignore[reportArgumentType]
                        "operator_id": r.operator_id,
                        "payment_proof": r.payment_proof,
                        "remark": r.remark,
                        "created_at": r.created_at.isoformat() if r.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                    }
                    for r in records
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@billing_bp.get("/consumption-records")
@auth_required
@require_permission("billing:view")
async def get_consumption_records(request: Request):
    """获取消费记录列表"""
    db: AsyncSession = request.ctx.db_session
    from sqlalchemy import select

    from ...models.billing import ConsumptionRecord

    customer_id = int(request.args.get("customer_id")) if request.args.get("customer_id") else None
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))

    stmt = select(ConsumptionRecord).where(ConsumptionRecord.deleted_at.is_(None))

    if customer_id:
        stmt = stmt.where(ConsumptionRecord.customer_id == customer_id)

    # 总数
    from sqlalchemy import func

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar()

    # 分页
    stmt = stmt.order_by(ConsumptionRecord.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    records = result.scalars().all()

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": r.id,
                        "customer_id": r.customer_id,
                        "invoice_id": r.invoice_id,
                        "amount": float(r.amount),  # pyright: ignore[reportArgumentType]
                        "bonus_used": float(r.bonus_used) if r.bonus_used else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                        "real_used": float(r.real_used) if r.real_used else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                        "balance_after": float(r.balance_after) if r.balance_after else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                        "consumed_at": r.created_at.isoformat() if r.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                    }
                    for r in records
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@billing_bp.get("/customers/<customer_id:int>/balance-trend")
@auth_required
@require_permission("billing:view")
async def get_customer_balance_trend(request: Request, customer_id: int):
    """
    获取客户余额趋势（按月聚合）

    查询参数:
    - months: 查询月数（默认 6，最大 12）

    返回:
    [
        {"month": "2025-10", "total_amount": 10000, "real_amount": 8000, "bonus_amount": 2000},
        ...
    ]
    """
    from ...services.analytics import AnalyticsService

    db: AsyncSession = request.ctx.db_session
    months = int(request.args.get("months", 6))
    if months > 12:
        months = 12

    service = AnalyticsService(db)
    trend = await service.get_balance_trend(customer_id=customer_id, months=months)

    return json({"code": 0, "message": "success", "data": trend})


# ==================== 余额导入 ====================
