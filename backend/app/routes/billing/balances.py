"""余额管理路由 — 充值、记录、统计、趋势"""

import asyncio
import json as _json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from sanic.request import Request
from sanic.response import json, raw
from sqlalchemy.ext.asyncio import AsyncSession

from ...cache.base import cache_service
from ...middleware.auth import auth_required, get_current_user, require_permission
from ...models.industry_type import IndustryType
from ...repository import BalanceRepository
from ...services.billing import BalanceService
from ...utils.audit_helpers import create_audit_entry
from . import billing_bp

logger = logging.getLogger(__name__)

# 结算类型分组取值（列表筛选 settlement_group 与 balance-stats 卡片共用）
SETTLEMENT_GROUPS = ("prepaid", "postpaid")


def _settlement_group_condition(group: str):
    """构建结算类型分组过滤条件

    未设置结算类型（NULL）的客户按业务默认归入预付费，因此
    「预付费」= 非后付费，与 balance-stats 卡片的统计口径一致。
    """
    from sqlalchemy import func

    from ...models.customers import Customer

    if group == "postpaid":
        return Customer.settlement_type == "postpaid"
    return func.coalesce(Customer.settlement_type, "prepaid") != "postpaid"


async def _batch_query_consumption_stats(
    db: AsyncSession, customer_ids: list[int]
) -> dict[int, dict]:
    """批量查询客户近 30 天消费统计（带 L1 Redis 缓存）

    Returns:
        {customer_id: {"total_cost_30d": float, "consumption_days": int}}
    """
    if not customer_ids:
        return {}

    from sqlalchemy import func, select

    from ...models.daily_consumption import DailyConsumption

    today = date.today()
    today_str = today.isoformat()
    thirty_days_ago = today - timedelta(days=30)

    # L1 缓存读取
    result_map: dict[int, dict] = {}
    missed_ids: list[int] = []
    try:
        redis = await cache_service._get_redis()
        keys = [f"cache:billing_consumption:{cid}:{today_str}" for cid in customer_ids]
        values = await redis.mget(keys)
        for cid, val in zip(customer_ids, values):
            if val is not None:
                result_map[cid] = _json.loads(val)
            else:
                missed_ids.append(cid)
    except Exception as e:
        logger.warning("L1 缓存读取失败 billing_consumption: %s", e)
        missed_ids = list(customer_ids)

    # 查询未命中部分
    if missed_ids:
        stmt = (
            select(
                DailyConsumption.customer_id,
                func.coalesce(func.sum(DailyConsumption.total_cost), 0).label("total_cost_30d"),
                func.count(func.distinct(DailyConsumption.consumption_date)).label(
                    "consumption_days"
                ),
            )
            .where(
                DailyConsumption.customer_id.in_(missed_ids),
                DailyConsumption.consumption_date >= thirty_days_ago,
                DailyConsumption.deleted_at.is_(None),
            )
            .group_by(DailyConsumption.customer_id)
        )
        sql_result = await db.execute(stmt)

        # 写回缓存
        cache_writes: list[tuple[str, str]] = []
        for row in sql_result.all():
            cid = row.customer_id
            stats = {
                "total_cost_30d": float(row.total_cost_30d),
                "consumption_days": int(row.consumption_days),
            }
            result_map[cid] = stats
            cache_writes.append(
                (f"cache:billing_consumption:{cid}:{today_str}", _json.dumps(stats, default=str))
            )

        # 未出现在结果中的客户 → 无消费记录
        for cid in missed_ids:
            if cid not in result_map:
                result_map[cid] = {"total_cost_30d": 0.0, "consumption_days": 0}

        if cache_writes:
            try:
                redis = await cache_service._get_redis()
                ttl = cache_service.ttl_for("billing_consumption")
                pipe = redis.pipeline()
                for key, val in cache_writes:
                    pipe.setex(key, ttl, val)
                await pipe.execute()
            except Exception as e:
                logger.warning("L1 缓存写入失败 billing_consumption: %s", e)

    return result_map


def _compute_burn_down(
    real_amount: float,
    bonus_amount: float,
    settlement_type: str | None,
    stats: dict | None,
) -> dict:
    """计算燃尽指标

    Returns:
        {"daily_avg_cost": float|None, "consumption_days": int, "days_remaining": int|None}
    """
    if settlement_type == "postpaid":
        return {"daily_avg_cost": None, "consumption_days": 0, "days_remaining": None}

    if not stats or stats.get("total_cost_30d", 0) <= 0:
        return {
            "daily_avg_cost": None,
            "consumption_days": stats.get("consumption_days", 0) if stats else 0,
            "days_remaining": None,
        }

    total_cost = stats["total_cost_30d"]
    consumption_days = stats["consumption_days"]
    # 防止 1 天脉冲拉高日均，下限 7 天
    daily_avg = total_cost / max(consumption_days, 7)

    remaining = real_amount + bonus_amount
    if daily_avg > 0:
        days_remaining = int(remaining / daily_avg)
    else:
        days_remaining = None

    return {
        "daily_avg_cost": round(daily_avg, 2),
        "consumption_days": consumption_days,
        "days_remaining": days_remaining,
    }


def _parse_balance_filters(request: Request) -> dict:
    """解析余额列表/导出共用的筛选参数（含类型转换与校验）

    校验失败时抛出 ValueError（由调用方转换为 400 响应）。
    """
    keyword = request.args.get("keyword")
    customer_id = int(request.args.get("customer_id")) if request.args.get("customer_id") else None
    account_type = request.args.get("account_type")
    industry = request.args.get("industry")
    manager_id = int(request.args.get("manager_id")) if request.args.get("manager_id") else None
    sales_manager_id = (
        int(request.args.get("sales_manager_id")) if request.args.get("sales_manager_id") else None
    )
    recharge_date_from = request.args.get("recharge_date_from")
    recharge_date_to = request.args.get("recharge_date_to")
    tag_ids = request.args.get("tag_ids")

    # 充值日期：解析为 datetime（畸形参数抛 ValueError，由调用方统一转 400）
    recharge_date_from = datetime.fromisoformat(recharge_date_from) if recharge_date_from else None
    recharge_date_to = (
        datetime.fromisoformat(recharge_date_to).replace(hour=23, minute=59, second=59)
        if recharge_date_to
        else None
    )
    # 标签 ID：逗号分隔的整数列表（畸形参数抛 ValueError，由调用方统一转 400）
    tag_ids = [int(t.strip()) for t in tag_ids.split(",") if t.strip()] if tag_ids else None

    is_key_customer = request.args.get("is_key_customer")
    if is_key_customer is not None and is_key_customer.strip() != "":
        if is_key_customer.lower() not in ("true", "false"):
            raise ValueError("is_key_customer 参数必须为 'true' 或 'false'")
        is_key_customer = is_key_customer.lower() == "true"
    else:
        is_key_customer = None

    is_real_estate = request.args.get("is_real_estate")
    if is_real_estate is not None and is_real_estate.strip() != "":
        if is_real_estate.lower() not in ("true", "false"):
            raise ValueError("is_real_estate 参数必须为 'true' 或 'false'")
        is_real_estate = is_real_estate.lower() == "true"
    else:
        is_real_estate = None

    is_settlement_enabled = request.args.get("is_settlement_enabled")
    if is_settlement_enabled is not None and is_settlement_enabled.strip() != "":
        if is_settlement_enabled.lower() not in ("true", "false"):
            raise ValueError("is_settlement_enabled 参数必须为 'true' 或 'false'")
        is_settlement_enabled = is_settlement_enabled.lower() == "true"
    else:
        is_settlement_enabled = None

    settlement_type = request.args.get("settlement_type")
    if settlement_type is not None and settlement_type.strip() == "":
        settlement_type = None

    settlement_group = request.args.get("settlement_group")
    if settlement_group is not None and settlement_group.strip() == "":
        settlement_group = None
    if settlement_group is not None and settlement_group not in SETTLEMENT_GROUPS:
        raise ValueError("settlement_group 参数必须为 'prepaid' 或 'postpaid'")

    balance_min = (
        float(request.args.get("balance_min")) if request.args.get("balance_min") else None
    )
    balance_max = (
        float(request.args.get("balance_max")) if request.args.get("balance_max") else None
    )

    return {
        "keyword": keyword,
        "customer_id": customer_id,
        "account_type": account_type,
        "industry": industry,
        "manager_id": manager_id,
        "sales_manager_id": sales_manager_id,
        "recharge_date_from": recharge_date_from,
        "recharge_date_to": recharge_date_to,
        "tag_ids": tag_ids,
        "is_key_customer": is_key_customer,
        "is_real_estate": is_real_estate,
        "is_settlement_enabled": is_settlement_enabled,
        "settlement_type": settlement_type,
        "settlement_group": settlement_group,
        "balance_min": balance_min,
        "balance_max": balance_max,
    }


async def _query_balance_rows_raw(
    db: AsyncSession,
    filters: dict,
    sort_by: str = "customer.id",
    sort_order: str = "asc",
    page: int = 1,
    page_size: int = 100,
    limit: int | None = None,
) -> tuple[list, int, dict, dict]:
    """查询余额原始数据（不含行组装），供列表与导出共用

    行组装（Decimal→float、燃尽计算等纯 CPU 工作）由 _assemble_balance_rows 单独完成，
    导出场景可在 asyncio.to_thread 中执行，避免阻塞事件循环。

    Args:
        filters: _parse_balance_filters 返回的筛选参数
        sort_by / sort_order: 排序字段与方向
        page / page_size: 分页参数（limit 为 None 时生效）
        limit: 最大返回行数（导出用，传入时忽略分页）

    Returns:
        (balance ORM 对象列表, 匹配总数, 最新充值时间映射, 消费统计映射)
    """
    from sqlalchemy import func, select
    from sqlalchemy.orm import selectinload

    from ...models.billing import CustomerBalance, RechargeRecord
    from ...models.customers import Customer, CustomerProfile

    keyword = filters["keyword"]
    customer_id = filters["customer_id"]
    account_type = filters["account_type"]
    industry = filters["industry"]
    manager_id = filters["manager_id"]
    sales_manager_id = filters["sales_manager_id"]
    recharge_date_from = filters["recharge_date_from"]
    recharge_date_to = filters["recharge_date_to"]
    tag_ids = filters["tag_ids"]
    is_key_customer = filters["is_key_customer"]
    is_real_estate = filters["is_real_estate"]
    is_settlement_enabled = filters["is_settlement_enabled"]
    settlement_type = filters["settlement_type"]
    settlement_group = filters["settlement_group"]
    balance_min = filters["balance_min"]
    balance_max = filters["balance_max"]

    # 排序字段映射（前端字段 -> SQLAlchemy 表达式）
    sort_field_map = {
        "company_id": Customer.company_id,
        "customer_name": Customer.name,
        "total_amount": CustomerBalance.total_amount,
        "used_total": CustomerBalance.used_total,
        "last_recharge_at": "last_recharge_at",  # 特殊处理
        "days_remaining": "days_remaining",  # 特殊处理（CTE）
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

    if is_settlement_enabled is not None:
        base_stmt = base_stmt.where(Customer.is_settlement_enabled == is_settlement_enabled)

    if settlement_type:
        base_stmt = base_stmt.where(Customer.settlement_type == settlement_type)
    if settlement_group:
        base_stmt = base_stmt.where(_settlement_group_condition(settlement_group))

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
            recharge_filter_stmt = recharge_filter_stmt.having(
                func.max(RechargeRecord.created_at) >= recharge_date_from
            )
        if recharge_date_to:
            recharge_filter_stmt = recharge_filter_stmt.having(
                func.max(RechargeRecord.created_at) <= recharge_date_to
            )

        base_stmt = base_stmt.where(CustomerBalance.customer_id.in_(recharge_filter_stmt))

    # 标签筛选（需要 JOIN CustomerTag 表）
    if tag_ids:
        from ...models.customers import CustomerTag  # pyright: ignore[reportAttributeAccessIssue]

        tag_customer_subq = (
            select(CustomerTag.customer_id)
            .where(
                CustomerTag.tag_id.in_(tag_ids),
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

    if is_settlement_enabled is not None:
        count_stmt = count_stmt.where(Customer.is_settlement_enabled == is_settlement_enabled)

    if settlement_type:
        count_stmt = count_stmt.where(Customer.settlement_type == settlement_type)
    if settlement_group:
        count_stmt = count_stmt.where(_settlement_group_condition(settlement_group))
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
            recharge_filter_stmt = recharge_filter_stmt.having(
                func.max(RechargeRecord.created_at) >= recharge_date_from
            )
        if recharge_date_to:
            recharge_filter_stmt = recharge_filter_stmt.having(
                func.max(RechargeRecord.created_at) <= recharge_date_to
            )
        count_stmt = count_stmt.where(CustomerBalance.customer_id.in_(recharge_filter_stmt))
    if tag_ids:
        from ...models.customers import CustomerTag  # pyright: ignore[reportAttributeAccessIssue]

        tag_customer_subq = (
            select(CustomerTag.customer_id)
            .where(
                CustomerTag.tag_id.in_(tag_ids),
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
        elif field == "days_remaining":
            # 燃尽天数排序：使用 CTE 批量聚合所有匹配客户
            from sqlalchemy import case

            from ...models.daily_consumption import DailyConsumption

            today = date.today()
            thirty_days_ago = today - timedelta(days=30)
            consumption_cte = (
                select(
                    DailyConsumption.customer_id.label("cid"),
                    func.coalesce(func.sum(DailyConsumption.total_cost), 0).label("total_cost_30d"),
                    func.count(func.distinct(DailyConsumption.consumption_date)).label(
                        "consumption_days"
                    ),
                )
                .where(
                    DailyConsumption.consumption_date >= thirty_days_ago,
                    DailyConsumption.deleted_at.is_(None),
                )
                .group_by(DailyConsumption.customer_id)
                .cte("consumption_stats")
            )
            base_stmt = base_stmt.outerjoin(
                consumption_cte,
                CustomerBalance.customer_id == consumption_cte.c.cid,
            )
            # SQL 层计算 days_remaining 用于排序（float）
            days_remaining_expr = case(
                (
                    Customer.settlement_type == "postpaid",
                    None,
                ),
                (
                    func.coalesce(consumption_cte.c.total_cost_30d, 0) <= 0,
                    None,
                ),
                else_=(
                    (
                        func.coalesce(CustomerBalance.real_amount, 0)
                        + func.coalesce(CustomerBalance.bonus_amount, 0)
                    )
                    / (
                        func.coalesce(consumption_cte.c.total_cost_30d, 0)
                        / func.greatest(func.coalesce(consumption_cte.c.consumption_days, 0), 7)
                    )
                ),
            )
            if sort_order == "asc":
                base_stmt = base_stmt.order_by(
                    days_remaining_expr.asc().nulls_last(), Customer.id.asc()
                )
            else:
                base_stmt = base_stmt.order_by(
                    days_remaining_expr.desc().nulls_last(), Customer.id.asc()
                )
        else:
            order_expr = field
            base_stmt = base_stmt.order_by(
                order_expr.asc() if sort_order == "asc" else order_expr.desc()
            )
    else:
        # 默认排序：按客户 ID 升序
        base_stmt = base_stmt.order_by(Customer.id.asc())

    # 分页/限制查询
    stmt = base_stmt.options(
        selectinload(CustomerBalance.customer)
        .selectinload(Customer.profile)
        .selectinload(CustomerProfile.industry_type)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    else:
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    balances = result.scalars().all()

    # 批量获取最新充值时间（customer_id 可空，过滤后避免 IN (NULL)）
    customer_ids = [b.customer_id for b in balances if b.customer_id is not None]
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

    # 批量查询消费统计（L1 缓存）
    consumption_stats_map = await _batch_query_consumption_stats(db, customer_ids)

    return list(balances), total or 0, last_recharge_map, consumption_stats_map


def _assemble_balance_rows(
    balances: list,
    last_recharge_map: dict,
    consumption_stats_map: dict,
) -> list[dict]:
    """纯 CPU 行组装：Decimal→float、属性访问与燃尽计算（可安全移入线程）

    只访问已通过 selectinload 预加载的属性（Customer / CustomerProfile /
    IndustryType 均已 eager load），不会在另一线程触发懒加载；
    last_recharge_map / consumption_stats_map 为纯 Python dict，无 ORM 依赖。
    """
    rows = [
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
                if b.customer_id in last_recharge_map and last_recharge_map[b.customer_id]
                else None
            ),
            **_compute_burn_down(
                real_amount=float(b.real_amount) if b.real_amount else 0,
                bonus_amount=float(b.bonus_amount) if b.bonus_amount else 0,
                settlement_type=b.customer.settlement_type if b.customer else None,
                stats=consumption_stats_map.get(b.customer_id),
            ),
        }
        for b in balances
    ]

    return rows


async def _query_balance_rows(
    db: AsyncSession,
    filters: dict,
    sort_by: str = "customer.id",
    sort_order: str = "asc",
    page: int = 1,
    page_size: int = 100,
    limit: int | None = None,
) -> tuple[list[dict], int]:
    """查询余额并组装行（列表用，页大小 ≤ 100，行组装量小可在事件循环内完成）"""
    balances, total, last_recharge_map, consumption_stats_map = await _query_balance_rows_raw(
        db, filters, sort_by, sort_order, page, page_size, limit
    )
    rows = _assemble_balance_rows(balances, last_recharge_map, consumption_stats_map)
    return rows, total


@billing_bp.get("/balances")
@auth_required
@require_permission("billing:view")
async def get_balances(request: Request):
    """获取余额列表（支持服务端筛选、排序和分页）"""
    db: AsyncSession = request.ctx.db_session

    # 分页参数（非数字输入应返回 400，而非抛 ValueError → 500）
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
    except ValueError:
        return json({"code": 40001, "message": "page 和 page_size 必须为整数"}, status=400)
    page_size = min(page_size, 100)

    # 筛选参数（统一解析与校验）
    try:
        filters = _parse_balance_filters(request)
    except ValueError as e:
        return json({"code": 40001, "message": str(e)}, status=400)

    # 排序参数
    sort_by = request.args.get("sort_by", "customer.id")
    sort_order = request.args.get("sort_order", "asc")
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"

    rows, total = await _query_balance_rows(
        db,
        filters,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": rows,
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


# ==================== 余额导出 ====================


@billing_bp.get("/balances/export")
@auth_required
@require_permission("billing:balance_export")
async def export_balances(request: Request):
    """导出余额列表为 Excel（按当前筛选条件导出全部匹配数据，上限 50000 条）"""
    import io

    import pandas as pd

    db: AsyncSession = request.ctx.db_session

    # 筛选参数（统一解析与校验）
    try:
        filters = _parse_balance_filters(request)
    except ValueError as e:
        return json({"code": 40001, "message": str(e)}, status=400)

    # 全量导出（上限 50000 条，不分页）：
    # DB 查询（await）留在异步层，纯 CPU 的行组装移入线程，避免阻塞事件循环。
    balances, total, last_recharge_map, consumption_stats_map = await _query_balance_rows_raw(
        db,
        filters,
        sort_by="customer.id",
        sort_order="asc",
        limit=50000,
    )

    # 行组装（Decimal→float、燃尽计算）是纯 CPU 工作，5 万行规模下会阻塞事件循环，
    # 与 DataFrame/Excel 生成一起移入线程。此处在线程中直接访问 ORM 实例属性
    # （b.customer、b.customer.profile 等）的安全前提是：
    #   1) _query_balance_rows_raw 已用 selectinload 三级预加载
    #      （CustomerBalance.customer → Customer.profile → CustomerProfile.industry_type），
    #      访问的属性均已 eager load，不会在另一线程触发懒加载；
    #   2) 查询返回后到进入线程之间无 commit/expire，实例属性不会过期、不会触发刷新。
    # 任一前提不成立时，应先在此处取出纯数据再入线程，而非直接传 ORM 实例。
    rows = await asyncio.to_thread(
        _assemble_balance_rows, balances, last_recharge_map, consumption_stats_map
    )

    if not rows:
        return json(
            {"code": 40002, "message": "没有找到符合条件的余额数据"},
            status=400,
        )

    # 纯 CPU 的 DataFrame 组装 + Excel 生成移入线程，避免阻塞事件循环
    def _build_excel(rows: list[dict]) -> bytes:
        """在独立线程中完成 DataFrame 组装与 Excel 写入（列与 BalanceTable 对齐）"""
        data = [
            {
                "客户ID": r["company_id"],
                "客户名称": r["customer_name"],
                "行业": r["industry_type"],
                "账号类型": r["account_type"],
                "结算方式": r["settlement_type"],
                "余额（元）": r["total_amount"],
                "实充余额（元）": r["real_amount"],
                "赠送余额（元）": r["bonus_amount"],
                "已消耗（元）": r["used_total"],
                "最新充值时间": r["last_recharge_at"],
                "预计可支撑天数": r["days_remaining"],
                "日均消耗（元）": r["daily_avg_cost"],
                "消耗天数": r["consumption_days"],
            }
            for r in rows
        ]
        df = pd.DataFrame(data)

        output = io.BytesIO()
        df.to_excel(output, index=False, sheet_name="余额列表", engine="openpyxl")  # pyright: ignore[reportArgumentType]  # pandas-stubs 的 WriteExcelBuffer 未含 BytesIO（运行时支持）

        return output.getvalue()

    excel_bytes = await asyncio.to_thread(_build_excel, rows)

    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"balances_{timestamp}.xlsx"

    # 截断标记：匹配总数超过导出上限时通过响应头告知前端
    truncated = total > len(rows)

    return raw(
        excel_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Total-Count": str(total),
            "X-Truncated": "true" if truncated else "false",
        },
    )


@billing_bp.get("/balance-stats")
@auth_required
@require_permission("billing:view")
async def get_balance_stats(request: Request):
    """获取余额统计概览（用于 KPI 卡片）

    支持与列表页一致的筛选参数，确保 KPI 统计数字与列表筛选结果保持一致。

    总余额按结算类型拆分为预付费/后付费两张卡片：未设置结算类型的客户归入预付费，
    「后付费」客户余额为负表示已消耗未回款，其相反数即应收款（postpaid_receivable）。
    """
    db: AsyncSession = request.ctx.db_session

    from sqlalchemy import func, select

    from ...models.billing import CustomerBalance, RechargeRecord
    from ...models.customers import Customer, CustomerProfile
    from ...models.industry_type import IndustryType

    # 筛选参数（与列表页 get_balances 保持一致）
    keyword = request.args.get("keyword")
    industry = request.args.get("industry")
    account_type = request.args.get("account_type")
    manager_id = int(request.args.get("manager_id")) if request.args.get("manager_id") else None
    sales_manager_id = (
        int(request.args.get("sales_manager_id")) if request.args.get("sales_manager_id") else None
    )
    is_key_customer = request.args.get("is_key_customer")
    if is_key_customer is not None and is_key_customer.strip() != "":
        if is_key_customer.lower() not in ("true", "false"):
            return json(
                {"code": 40001, "message": "is_key_customer 参数必须为 'true' 或 'false'"},
                status=400,
            )
        is_key_customer = is_key_customer.lower() == "true"
    else:
        is_key_customer = None

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

    is_settlement_enabled = request.args.get("is_settlement_enabled")
    if is_settlement_enabled is not None and is_settlement_enabled.strip() != "":
        if is_settlement_enabled.lower() not in ("true", "false"):
            return json(
                {"code": 40001, "message": "is_settlement_enabled 参数必须为 'true' 或 'false'"},
                status=400,
            )
        is_settlement_enabled = is_settlement_enabled.lower() == "true"
    else:
        is_settlement_enabled = None

    settlement_type = request.args.get("settlement_type")
    if settlement_type is not None and settlement_type.strip() == "":
        settlement_type = None

    tag_ids = request.args.get("tag_ids")

    # 客户级别筛选条件（适用于所有查询）
    customer_filters = []
    if keyword:
        customer_filters.append(Customer.name.ilike(f"%{keyword}%"))
    if account_type:
        customer_filters.append(Customer.account_type == account_type)
    if manager_id:
        customer_filters.append(Customer.manager_id == manager_id)
    if sales_manager_id:
        customer_filters.append(Customer.sales_manager_id == sales_manager_id)
    if is_key_customer is not None:
        customer_filters.append(Customer.is_key_customer == is_key_customer)
    if is_real_estate is not None:
        customer_filters.append(Customer.is_real_estate == is_real_estate)
    if is_settlement_enabled is not None:
        customer_filters.append(Customer.is_settlement_enabled == is_settlement_enabled)
    if settlement_type:
        customer_filters.append(Customer.settlement_type == settlement_type)

    # 行业筛选条件（需要 JOIN IndustryType）
    industry_filter_stmts = []
    industry_need_join = False
    if industry:
        industry_list = [i.strip() for i in industry.split(",") if i.strip()]
        if industry_list:
            industry_filter_stmts.append(IndustryType.name.in_(industry_list))
            industry_need_join = True

    # 标签筛选（需要子查询）
    tag_subq = None
    if tag_ids:
        from ...models.customers import CustomerTag  # pyright: ignore[reportAttributeAccessIssue]

        tag_id_list = [int(t.strip()) for t in tag_ids.split(",") if t.strip()]
        if tag_id_list:
            tag_subq = (
                select(CustomerTag.customer_id)
                .where(
                    CustomerTag.tag_id.in_(tag_id_list),
                    CustomerTag.deleted_at.is_(None),
                )
                .group_by(CustomerTag.customer_id)
            )

    def apply_balance_filters(stmt, need_industry_join=False):
        """为余额查询语句添加基础 + 筛选条件"""
        stmt = stmt.where(
            CustomerBalance.deleted_at.is_(None),
            Customer.deleted_at.is_(None),
        )
        for cond in customer_filters:
            stmt = stmt.where(cond)
        if industry_need_join and need_industry_join:
            for cond in industry_filter_stmts:
                stmt = stmt.where(cond)
        if tag_subq is not None:
            stmt = stmt.where(Customer.id.in_(tag_subq))
        return stmt

    def apply_recharge_filters(stmt, need_industry_join=False):
        """为充值查询语句添加基础 + 筛选条件"""
        stmt = stmt.where(
            RechargeRecord.deleted_at.is_(None),
            Customer.deleted_at.is_(None),
        )
        for cond in customer_filters:
            stmt = stmt.where(cond)
        if industry_need_join and need_industry_join:
            for cond in industry_filter_stmts:
                stmt = stmt.where(cond)
        if tag_subq is not None:
            stmt = stmt.where(Customer.id.in_(tag_subq))
        return stmt

    def add_industry_joins(stmt):
        """添加行业 JOIN"""
        if industry_need_join:
            stmt = stmt.outerjoin(
                CustomerProfile, Customer.id == CustomerProfile.customer_id
            ).outerjoin(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)
        return stmt

    # --- 总余额（按结算类型拆分）---
    # 「预付费」= 非后付费（含未设置结算类型的客户），「后付费」= settlement_type == 'postpaid'，
    # 与列表筛选 settlement_group 共用同一口径，保证卡片数字与列表条数一致。
    async def _balance_totals(group: str) -> tuple[float, int]:
        stmt = (
            select(
                func.coalesce(func.sum(CustomerBalance.total_amount), 0),
                func.count(CustomerBalance.id),
            )
            .join(Customer, CustomerBalance.customer_id == Customer.id)
            .where(_settlement_group_condition(group))
        )
        stmt = add_industry_joins(stmt)
        stmt = apply_balance_filters(stmt, need_industry_join=True)
        total, count = (await db.execute(stmt)).one()
        return float(total or 0), int(count or 0)

    total_balance_prepaid, prepaid_customers = await _balance_totals("prepaid")
    total_balance_postpaid, postpaid_customers = await _balance_totals("postpaid")
    # 后付费客户余额为负表示已消耗未回款，应收款（净）= 余额合计的相反数；
    # 若为负值则说明后付费客户预存多于欠款（预收）。
    postpaid_receivable = -total_balance_postpaid

    # --- 本月充值 ---
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_recharge_base = select(
        func.count(RechargeRecord.id).label("count"),
        func.coalesce(func.sum(RechargeRecord.real_amount + RechargeRecord.bonus_amount), 0).label(
            "amount"
        ),
        func.coalesce(func.sum(RechargeRecord.real_amount), 0).label("real_amount_sum"),
        func.coalesce(func.sum(RechargeRecord.bonus_amount), 0).label("bonus_amount_sum"),
    ).where(RechargeRecord.created_at >= month_start)
    # 始终 JOIN Customer 以应用客户级别筛选条件
    this_month_recharge_base = this_month_recharge_base.join(
        Customer, RechargeRecord.customer_id == Customer.id
    )
    this_month_recharge_base = add_industry_joins(this_month_recharge_base)
    this_month_recharge_base = apply_recharge_filters(
        this_month_recharge_base, need_industry_join=True
    )

    this_month_result = (await db.execute(this_month_recharge_base)).one()
    this_month_count = this_month_result.count or 0
    this_month_amount = float(this_month_result.amount or 0)
    this_month_real_amount = float(this_month_result.real_amount_sum or 0)
    this_month_bonus_amount = float(this_month_result.bonus_amount_sum or 0)

    # --- 余额不足客户数（含欠费/负余额客户，仅统计预付费）---
    # 后付费客户余额为负属于应收款而非「余额不足」，故与「即将耗尽」一致排除后付费。
    LOW_BALANCE_THRESHOLD = 10000
    low_balance_stmt = (
        select(func.count(CustomerBalance.id))
        .join(Customer, CustomerBalance.customer_id == Customer.id)
        .where(
            CustomerBalance.total_amount < LOW_BALANCE_THRESHOLD,
            _settlement_group_condition("prepaid"),
        )
    )
    low_balance_stmt = add_industry_joins(low_balance_stmt)
    low_balance_stmt = apply_balance_filters(low_balance_stmt, need_industry_join=True)
    low_balance_count = (await db.execute(low_balance_stmt)).scalar() or 0

    # --- 即将耗尽客户数（days_remaining ≤ 7，仅预付费）---
    from datetime import date, timedelta

    from ...models.daily_consumption import DailyConsumption

    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    consumption_cte = (
        select(
            DailyConsumption.customer_id.label("cid"),
            func.coalesce(func.sum(DailyConsumption.total_cost), 0).label("total_cost_30d"),
            func.count(func.distinct(DailyConsumption.consumption_date)).label("consumption_days"),
        )
        .where(
            DailyConsumption.consumption_date >= thirty_days_ago,
            DailyConsumption.deleted_at.is_(None),
        )
        .group_by(DailyConsumption.customer_id)
        .cte("consumption_stats_burning")
    )
    burning_soon_days_expr = (
        func.coalesce(CustomerBalance.real_amount, 0)
        + func.coalesce(CustomerBalance.bonus_amount, 0)
    ) / (
        func.coalesce(consumption_cte.c.total_cost_30d, 0)
        / func.greatest(func.coalesce(consumption_cte.c.consumption_days, 0), 7)
    )
    burning_soon_stmt = (
        select(func.count(CustomerBalance.id))
        .join(Customer, CustomerBalance.customer_id == Customer.id)
        .outerjoin(consumption_cte, CustomerBalance.customer_id == consumption_cte.c.cid)
        .where(
            CustomerBalance.deleted_at.is_(None),
            Customer.deleted_at.is_(None),
            # 未设置结算类型归入预付费，故用分组条件而非 != 'postpaid'（NULL 会被 SQL 过滤掉）
            _settlement_group_condition("prepaid"),
            func.coalesce(consumption_cte.c.total_cost_30d, 0) > 0,
            burning_soon_days_expr <= 7,
        )
    )
    burning_soon_stmt = add_industry_joins(burning_soon_stmt)
    # 应用客户级别筛选
    for cond in customer_filters:
        burning_soon_stmt = burning_soon_stmt.where(cond)
    if industry_need_join:
        for cond in industry_filter_stmts:
            burning_soon_stmt = burning_soon_stmt.where(cond)
    if tag_subq is not None:
        burning_soon_stmt = burning_soon_stmt.where(Customer.id.in_(tag_subq))
    burning_soon_count = (await db.execute(burning_soon_stmt)).scalar() or 0

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "total_balance_prepaid": total_balance_prepaid,
                "prepaid_customers": prepaid_customers,
                "total_balance_postpaid": total_balance_postpaid,
                "postpaid_customers": postpaid_customers,
                "postpaid_receivable": postpaid_receivable,
                "this_month_count": this_month_count,
                "this_month_amount": this_month_amount,
                "this_month_real_amount": this_month_real_amount,
                "this_month_bonus_amount": this_month_bonus_amount,
                "low_balance_count": low_balance_count,
                "burning_soon_count": burning_soon_count,
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


@billing_bp.post("/customers/<customer_id:int>/balance/recalculate")
@auth_required
@require_permission("billing:recharge")
async def recalculate_balance(request: Request, customer_id: int):
    """重算客户余额的 total_amount

    将 total_amount 修正为 real_amount + bonus_amount，
    用于修复因历史脏数据或并发问题导致的不一致。
    """
    db: AsyncSession = request.ctx.db_session
    balance_service = BalanceService(BalanceRepository(db))

    balance = await balance_service.recalculate_balance(customer_id)

    if not balance:
        return json(
            {"code": 40400, "message": "客户余额账户不存在"},
            status=404,
        )

    old_total = float(request.json.get("old_total", 0)) if request.json else 0

    return json(
        {
            "code": 0,
            "message": "重算成功",
            "data": {
                "customer_id": balance.customer_id,
                "real_amount": float(balance.real_amount) if balance.real_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "bonus_amount": float(balance.bonus_amount) if balance.bonus_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "total_amount": float(balance.total_amount) if balance.total_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "used_total": float(balance.used_total) if balance.used_total else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "used_real": float(balance.used_real) if balance.used_real else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "used_bonus": float(balance.used_bonus) if balance.used_bonus else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "old_total": old_total,
                "changed": old_total
                != (float(balance.total_amount) if balance.total_amount else 0),
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

    if not customer_id:
        return json(
            {"code": 40001, "message": "请填写客户 ID"},
            status=400,
        )

    if real_amount == 0 and bonus_amount == 0:
        return json(
            {"code": 40001, "message": "请填写实充金额或赠送金额"},
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
    # 燃尽缓存：余额变化影响 days_remaining
    await cache_service.invalidate_pattern("cache:billing_consumption:*")

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
                "total_amount": float((record.real_amount or 0) + (record.bonus_amount or 0)),
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
                        "total_amount": float((r.real_amount or 0) + (r.bonus_amount or 0)),
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

    from ...models.billing import ConsumptionRecord, Invoice

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

    # 批量查询关联结算单号
    invoice_ids = [r.invoice_id for r in records if r.invoice_id]
    invoice_no_map: dict[int, str] = {}
    if invoice_ids:
        inv_result = await db.execute(
            select(Invoice.id, Invoice.invoice_no).where(Invoice.id.in_(invoice_ids))
        )
        for row in inv_result:
            invoice_no_map[row.id] = row.invoice_no

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
                        "invoice_no": invoice_no_map.get(r.invoice_id) if r.invoice_id else None,
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
