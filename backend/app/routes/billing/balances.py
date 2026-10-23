"""余额管理路由 — 充值、记录、统计、趋势"""

import asyncio
import json as _json
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sanic.request import Request
from sanic.response import json, raw
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from ...cache.base import cache_service
from ...middleware.auth import (
    auth_required,
    customer_scope_user_id,
    get_current_user,
    require_permission,
)
from ...models.industry_type import IndustryType
from ...repository import BalanceRepository
from ...services.billing import BalanceService
from ...services.package_balance import (
    batch_query_package_info as _batch_query_package_info,
)
from ...services.package_balance import (
    build_package_remaining_cte as _build_package_remaining_cte,
)
from ...utils.audit_helpers import create_audit_entry
from ...utils.timezone import CST, cst_today, naive_cst_datetime_str
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


def _bool_filter_condition(column, value: bool, *, null_as_true: bool):
    """构建布尔筛选条件（历史 NULL 兼容，语义对齐客户管理页）

    Args:
        column: 客户表布尔列
        value: 筛选值（True=是 / False=否）
        null_as_true: 该字段历史 NULL 的业务默认值是否为「是」
            - 自动发起结算（默认是）：True → 列 IS TRUE OR IS NULL；False → 列 IS FALSE
            - 是否停用（默认否）：True → 列 IS TRUE；False → 列 IS FALSE OR IS NULL
    """
    from sqlalchemy import or_

    if value:
        if null_as_true:
            return or_(column.is_(True), column.is_(None))
        return column.is_(True)
    if null_as_true:
        return column.is_(False)
    return or_(column.is_(False), column.is_(None))


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

    # 统计窗口按 CST 口径：缓存 key 与 30 天窗口都不应跟随运行环境时区
    # （UTC 容器在 CST 00:00-08:00 期间会少算一天数据，且缓存 key 与 CST 部署不一致）
    today = cst_today()
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
    package_info: dict | None = None,
) -> dict:
    """计算燃尽指标

    包年客户的「燃尽」口径为套餐到期剩余天数（而非按消耗推算的可用天数），
    因此优先于预付费/后付费逻辑单独处理。

    Returns:
        {"daily_avg_cost": float|None, "consumption_days": int, "days_remaining": int|None}
    """
    # 有效包年套餐：燃尽 = 到期剩余天数（无到期日则为 None）
    if package_info and not package_info.get("is_expired"):
        expiry = package_info.get("expiry_date")
        if expiry is None:
            return {"daily_avg_cost": None, "consumption_days": 0, "days_remaining": None}
        # 两个日期都按 CST 口径取：expiry 转 CST，今天用 cst_today()。
        # 不能用 date.today()（跟随运行环境时区，UTC 容器下会取到 CST 的次日，
        # 导致剩余天数多算一天）
        days_remaining = (expiry.astimezone(CST).date() - cst_today()).days
        return {
            "daily_avg_cost": None,
            "consumption_days": 0,
            "days_remaining": max(days_remaining, 0),
        }

    # 已过期包年套餐：标记为已耗尽（0 天）
    if package_info and package_info.get("is_expired"):
        return {"daily_avg_cost": None, "consumption_days": 0, "days_remaining": 0}

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

    # 自动发起结算 / 是否停用（与客户管理页筛选项对齐）
    auto_initiate_settlement = request.args.get("auto_initiate_settlement")
    if auto_initiate_settlement is not None and auto_initiate_settlement.strip() != "":
        if auto_initiate_settlement.lower() not in ("true", "false"):
            raise ValueError("auto_initiate_settlement 参数必须为 'true' 或 'false'")
        auto_initiate_settlement = auto_initiate_settlement.lower() == "true"
    else:
        auto_initiate_settlement = None

    is_disabled = request.args.get("is_disabled")
    if is_disabled is not None and is_disabled.strip() != "":
        if is_disabled.lower() not in ("true", "false"):
            raise ValueError("is_disabled 参数必须为 'true' 或 'false'")
        is_disabled = is_disabled.lower() == "true"
    else:
        is_disabled = None

    settlement_type = request.args.get("settlement_type")
    if settlement_type is not None and settlement_type.strip() == "":
        settlement_type = None

    # ERP 系统 / 合作状态（字符串精确匹配，与客户管理页筛选项对齐）
    erp_system = request.args.get("erp_system")
    if erp_system is not None and erp_system.strip() == "":
        erp_system = None

    cooperation_status = request.args.get("cooperation_status")
    if cooperation_status is not None and cooperation_status.strip() == "":
        cooperation_status = None

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
        "auto_initiate_settlement": auto_initiate_settlement,
        "is_disabled": is_disabled,
        "settlement_type": settlement_type,
        "erp_system": erp_system,
        "cooperation_status": cooperation_status,
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
) -> tuple[list, int, dict, dict, dict]:
    """查询余额原始数据（不含行组装），供列表与导出共用

    以 Customer 为驱动表 outerjoin CustomerBalance：无余额行的包年客户也会返回。
    行组装（Decimal→float、燃尽计算等纯 CPU 工作）由 _assemble_balance_rows 单独完成，
    导出场景可在 asyncio.to_thread 中执行，避免阻塞事件循环。

    Args:
        filters: _parse_balance_filters 返回的筛选参数
        sort_by / sort_order: 排序字段与方向
        page / page_size: 分页参数（limit 为 None 时生效）
        limit: 最大返回行数（导出用，传入时忽略分页）

    Returns:
        (Customer 对象列表, 匹配总数, 最新充值时间映射, 消费统计映射, 包年套餐信息映射)
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
    auto_initiate_settlement = filters.get("auto_initiate_settlement")
    is_disabled = filters.get("is_disabled")
    settlement_type = filters["settlement_type"]
    erp_system = filters.get("erp_system")
    cooperation_status = filters.get("cooperation_status")
    settlement_group = filters["settlement_group"]
    balance_min = filters["balance_min"]
    balance_max = filters["balance_max"]

    # 包年剩余额度 CTE：供余额范围筛选、total_amount 排序与 KPI 统计复用
    package_cte = _build_package_remaining_cte()

    # 排序字段映射（前端字段 -> SQLAlchemy 表达式）
    # 包年客户余额以套餐剩余额度（package_remaining.remaining）为准，非包年客户退化为
    # CustomerBalance 原值（无余额行时为 0）
    sort_field_map = {
        "company_id": Customer.company_id,
        "customer_name": Customer.name,
        "total_amount": func.coalesce(package_cte.c.remaining, CustomerBalance.total_amount, 0),
        # 「已消耗」列表展示包年客户为套餐内累计消耗（package_remaining.consumed），
        # 排序须用同一口径，否则展示值与排序顺序相互矛盾
        "used_total": func.coalesce(package_cte.c.consumed, CustomerBalance.used_total, 0),
        "last_recharge_at": "last_recharge_at",  # 特殊处理
        "days_remaining": "days_remaining",  # 特殊处理（CTE）
    }

    # 以 Customer 为驱动表 outerjoin CustomerBalance：无余额行的包年客户也会出现在列表中；
    # CustomerBalance.deleted_at 条件必须放在 outerjoin ON 子句，否则会过滤掉无余额行客户。
    # 无余额档案客户默认不可见（避免惰性补建副作用与空行）；例外是包年客户
    # （price_policy='yearly'）：其「余额」= 套餐剩余额度（含过期归 0），不依赖
    # CustomerBalance 行，与 545b4bf「无余额行的包年客户不再丢失」的意图一致。
    # 用 price_policy 而非 package_cte 命中：CTE 只含生效中的规则，过期包年客户
    # 不在其中但仍须可见（total_amount=0、package_expired=True）。
    # 注意：count_stmt 独立重建（下方），该条件必须共享，否则 total 与实际行数漂移。
    has_balance_row = or_(
        CustomerBalance.id.is_not(None),
        Customer.price_policy == "yearly",
    )
    base_stmt = (
        select(Customer)
        .outerjoin(
            CustomerBalance,
            (CustomerBalance.customer_id == Customer.id) & (CustomerBalance.deleted_at.is_(None)),
        )
        .outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
        .outerjoin(package_cte, Customer.id == package_cte.c.cid)
        .where(Customer.deleted_at.is_(None))
        .where(has_balance_row)
    )

    # 服务端过滤
    if customer_id:
        base_stmt = base_stmt.where(Customer.id == customer_id)
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
    # 数据可见性（服务端强制）：无 customers:view_all 时仅返回当前用户负责的客户
    if filters.get("mine_user_id"):
        base_stmt = base_stmt.where(
            or_(
                Customer.manager_id == filters["mine_user_id"],
                Customer.sales_manager_id == filters["mine_user_id"],
            )
        )
    if is_key_customer is not None:
        base_stmt = base_stmt.where(Customer.is_key_customer == is_key_customer)

    if is_real_estate is not None:
        base_stmt = base_stmt.where(Customer.is_real_estate == is_real_estate)

    if is_settlement_enabled is not None:
        base_stmt = base_stmt.where(Customer.is_settlement_enabled == is_settlement_enabled)

    if auto_initiate_settlement is not None:
        # 「自动发起结算」默认值为「是」，历史 NULL 视为是（语义对齐客户管理页）
        base_stmt = base_stmt.where(
            _bool_filter_condition(
                Customer.auto_initiate_settlement,
                auto_initiate_settlement,
                null_as_true=True,
            )
        )

    if is_disabled is not None:
        # 「是否停用」历史 NULL 视为未停用（语义对齐客户管理页）
        base_stmt = base_stmt.where(
            _bool_filter_condition(Customer.is_disabled, is_disabled, null_as_true=False)
        )

    if settlement_type:
        base_stmt = base_stmt.where(Customer.settlement_type == settlement_type)
    if erp_system:
        base_stmt = base_stmt.where(Customer.erp_system == erp_system)
    if cooperation_status:
        base_stmt = base_stmt.where(Customer.cooperation_status == cooperation_status)
    if settlement_group:
        base_stmt = base_stmt.where(_settlement_group_condition(settlement_group))

    # 余额范围过滤：包年客户按套餐剩余额度参与，非包年客户按 CustomerBalance 余额
    balance_expr = func.coalesce(package_cte.c.remaining, CustomerBalance.total_amount, 0)
    if balance_min is not None:
        base_stmt = base_stmt.where(balance_expr >= balance_min)
    if balance_max is not None:
        base_stmt = base_stmt.where(balance_expr <= balance_max)

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

        base_stmt = base_stmt.where(Customer.id.in_(recharge_filter_stmt))

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

    # 总数查询（Customer 驱动 + outerjoin，保证无余额行的包年客户计入总数）
    # has_balance_row 与 base_stmt 共享，防止 total 与实际返回行数漂移
    count_stmt = (
        select(func.count(Customer.id))
        .outerjoin(
            CustomerBalance,
            (CustomerBalance.customer_id == Customer.id) & (CustomerBalance.deleted_at.is_(None)),
        )
        .outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
        .outerjoin(package_cte, Customer.id == package_cte.c.cid)
        .where(Customer.deleted_at.is_(None))
        .where(has_balance_row)
    )
    if customer_id:
        count_stmt = count_stmt.where(Customer.id == customer_id)
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
    if filters.get("mine_user_id"):
        count_stmt = count_stmt.where(
            or_(
                Customer.manager_id == filters["mine_user_id"],
                Customer.sales_manager_id == filters["mine_user_id"],
            )
        )
    if is_key_customer is not None:
        count_stmt = count_stmt.where(Customer.is_key_customer == is_key_customer)

    if is_real_estate is not None:
        count_stmt = count_stmt.where(Customer.is_real_estate == is_real_estate)

    if is_settlement_enabled is not None:
        count_stmt = count_stmt.where(Customer.is_settlement_enabled == is_settlement_enabled)

    if auto_initiate_settlement is not None:
        count_stmt = count_stmt.where(
            _bool_filter_condition(
                Customer.auto_initiate_settlement,
                auto_initiate_settlement,
                null_as_true=True,
            )
        )

    if is_disabled is not None:
        count_stmt = count_stmt.where(
            _bool_filter_condition(Customer.is_disabled, is_disabled, null_as_true=False)
        )

    if settlement_type:
        count_stmt = count_stmt.where(Customer.settlement_type == settlement_type)
    if erp_system:
        count_stmt = count_stmt.where(Customer.erp_system == erp_system)
    if cooperation_status:
        count_stmt = count_stmt.where(Customer.cooperation_status == cooperation_status)
    if settlement_group:
        count_stmt = count_stmt.where(_settlement_group_condition(settlement_group))
    if balance_min is not None:
        count_stmt = count_stmt.where(balance_expr >= balance_min)
    if balance_max is not None:
        count_stmt = count_stmt.where(balance_expr <= balance_max)
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
        count_stmt = count_stmt.where(Customer.id.in_(recharge_filter_stmt))
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
                last_recharge_subq, Customer.id == last_recharge_subq.c.customer_id
            )
            order_expr = last_recharge_subq.c.last_recharge_at
            # NULL 值统一排到最后，二级排序按客户 ID 保证稳定性
            if sort_order == "asc":
                base_stmt = base_stmt.order_by(order_expr.asc().nulls_last(), Customer.id.asc())
            else:
                base_stmt = base_stmt.order_by(order_expr.desc().nulls_last(), Customer.id.asc())
        elif field == "days_remaining":
            # 燃尽天数排序：使用 CTE 批量聚合所有匹配客户
            from sqlalchemy import Date, case

            from ...models.daily_consumption import DailyConsumption

            # 30 天窗口按 CST 口径，与展示层 days_remaining 的 CST 计算保持一致
            today = cst_today()
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
                Customer.id == consumption_cte.c.cid,
            )
            # SQL 层计算 days_remaining 用于排序（float）
            # 包年客户（package_cte 命中）用「套餐到期剩余天数」，其余沿用消耗推算公式
            # 「今天」显式取 CST 日期：func.current_date() 跟随 PG 会话时区（CI 的
            # postgres 容器为 UTC，会取到 CST 次日），与 Python 侧 cst_today() 差 1 天，
            # 导致排序结果与展示层 days_remaining 不一致
            cst_today_expr = func.cast(func.timezone("Asia/Shanghai", func.now()), Date)
            days_remaining_expr = case(
                (
                    Customer.settlement_type == "postpaid",
                    None,
                ),
                (
                    package_cte.c.cid.is_not(None),
                    func.cast(package_cte.c.expiry_date, Date) - cst_today_expr,
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
        selectinload(Customer.balance),
        selectinload(Customer.profile).selectinload(CustomerProfile.industry_type),
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    else:
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    customers = result.scalars().all()

    customer_ids = [c.id for c in customers]

    # 批量获取最新充值时间
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

    # 批量查询包年套餐信息（剩余额度/次数、到期日、过期标记）
    package_info_map = await _batch_query_package_info(db, customer_ids)

    return list(customers), total or 0, last_recharge_map, consumption_stats_map, package_info_map


def _assemble_balance_rows(
    customers: list,
    last_recharge_map: dict,
    consumption_stats_map: dict,
    package_info_map: dict | None = None,
) -> list[dict]:
    """纯 CPU 行组装：Decimal→float、属性访问与燃尽计算（可安全移入线程）

    入参为 Customer 列表（驱动表），余额取自 `Customer.balance`（无余额行的包年客户为
    None，各金额记 0）。只访问已通过 selectinload 预加载的属性（Customer / CustomerBalance /
    CustomerProfile / IndustryType 均已 eager load），不会在另一线程触发懒加载；
    last_recharge_map / consumption_stats_map / package_info_map 为纯 Python dict，无 ORM 依赖。
    """
    package_info_map = package_info_map or {}
    rows = []
    for c in customers:
        b = c.balance  # CustomerBalance 或 None（无余额行的包年客户）
        package_info = package_info_map.get(c.id)
        is_package = bool(package_info)
        package_expired = bool(package_info.get("is_expired")) if package_info else False

        # 余额口径：包年客户以其套餐剩余额度为准（过期记 0），其余客户保留 CustomerBalance 值
        if is_package:
            total_amount = float(package_info["remaining_amount"]) if not package_expired else 0.0
        else:
            total_amount = float(b.total_amount) if b and b.total_amount else 0

        real_amount = float(b.real_amount) if b and b.real_amount else 0
        bonus_amount = float(b.bonus_amount) if b and b.bonus_amount else 0

        expiry = package_info.get("expiry_date") if package_info else None
        rows.append(
            {
                "id": c.id,
                "customer_id": c.id,
                "company_id": c.company_id,
                "customer_name": c.name,
                "account_type": c.account_type,
                "industry_type": c.profile.industry_type.name
                if c.profile and c.profile.industry_type
                else None,
                "settlement_type": c.settlement_type,
                "is_key_customer": c.is_key_customer,
                "total_amount": total_amount,
                "real_amount": real_amount,
                "bonus_amount": bonus_amount,
                "used_total": float(b.used_total) if b and b.used_total else 0,
                "used_real": float(b.used_real) if b and b.used_real else 0,
                "used_bonus": float(b.used_bonus) if b and b.used_bonus else 0,
                # 包年客户「已消耗」= 套餐内累计消耗（实时，含未结算），与余额列同口径
                # （余额 = base_fee − 实时消耗）；非包年或已过期包年为 None（展示层回退 used_total）
                "package_consumed_amount": (
                    package_info.get("consumed_amount")
                    if package_info and not package_expired
                    else None
                ),
                "last_recharge_at": (
                    # created_at 是 timestamp without time zone（CST 墙钟），
                    # 按墙钟格式化；astimezone 会再偏 8 小时
                    naive_cst_datetime_str(last_recharge_map[c.id])
                    if c.id in last_recharge_map and last_recharge_map[c.id]
                    else None
                ),
                # --- 包年客户额外字段（非包年客户均为 None/False）---
                "price_policy": c.price_policy,
                "is_package": is_package,
                "package_remaining_amount": package_info["remaining_amount"]
                if package_info
                else None,
                "package_remaining_count": package_info["remaining_count"]
                if package_info
                else None,
                "package_base_fee": package_info["base_fee"] if package_info else None,
                "package_limit_count": package_info["limit_count"] if package_info else None,
                "package_is_unlimited": package_info["is_unlimited"] if package_info else None,
                "package_expired": package_expired,
                "package_expiry_date": expiry.astimezone(CST).strftime("%Y-%m-%d")
                if expiry
                else None,
                **_compute_burn_down(
                    real_amount=real_amount,
                    bonus_amount=bonus_amount,
                    settlement_type=c.settlement_type,
                    stats=consumption_stats_map.get(c.id),
                    package_info=package_info,
                ),
            }
        )

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
    (
        customers,
        total,
        last_recharge_map,
        consumption_stats_map,
        package_info_map,
    ) = await _query_balance_rows_raw(db, filters, sort_by, sort_order, page, page_size, limit)
    rows = _assemble_balance_rows(
        customers, last_recharge_map, consumption_stats_map, package_info_map
    )
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

    # 数据可见性（服务端强制）：无 customers:view_all 时仅返回当前用户负责的客户
    scope_user_id = await customer_scope_user_id(request)
    if scope_user_id is not None:
        filters["mine_user_id"] = scope_user_id

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

    # 数据可见性（服务端强制）：无 customers:view_all 时导出仅限当前用户负责的客户
    scope_user_id = await customer_scope_user_id(request)
    if scope_user_id is not None:
        filters["mine_user_id"] = scope_user_id

    # 全量导出（上限 50000 条，不分页）：
    # DB 查询（await）留在异步层，纯 CPU 的行组装移入线程，避免阻塞事件循环。
    (
        customers,
        total,
        last_recharge_map,
        consumption_stats_map,
        package_info_map,
    ) = await _query_balance_rows_raw(
        db,
        filters,
        sort_by="customer.id",
        sort_order="asc",
        limit=50000,
    )

    # 行组装（Decimal→float、燃尽计算）是纯 CPU 工作，5 万行规模下会阻塞事件循环，
    # 与 DataFrame/Excel 生成一起移入线程。此处在线程中直接访问 ORM 实例属性
    # （c.balance、c.profile 等）的安全前提是：
    #   1) _query_balance_rows_raw 已用 selectinload 预加载
    #      （Customer.balance + Customer.profile → CustomerProfile.industry_type），
    #      访问的属性均已 eager load，不会在另一线程触发懒加载；
    #   2) 查询返回后到进入线程之间无 commit/expire，实例属性不会过期、不会触发刷新。
    # 任一前提不成立时，应先在此处取出纯数据再入线程，而非直接传 ORM 实例。
    rows = await asyncio.to_thread(
        _assemble_balance_rows,
        customers,
        last_recharge_map,
        consumption_stats_map,
        package_info_map,
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
                "已消耗（元）": (
                    r.get("package_consumed_amount")
                    if r.get("is_package") and r.get("package_consumed_amount") is not None
                    else r["used_total"]
                ),
                # 包年客户专属列（非包年客户留空）
                "套餐剩余额度（元）": r.get("package_remaining_amount")
                if r.get("is_package")
                else None,
                "套餐剩余次数": (
                    "不限"
                    if r.get("package_is_unlimited")
                    else (r.get("package_remaining_count") if r.get("is_package") else None)
                ),
                "套餐到期日期": r.get("package_expiry_date") if r.get("is_package") else None,
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

    # 自动发起结算 / 是否停用（与列表页及客户管理页筛选项对齐）
    auto_initiate_settlement = request.args.get("auto_initiate_settlement")
    if auto_initiate_settlement is not None and auto_initiate_settlement.strip() != "":
        if auto_initiate_settlement.lower() not in ("true", "false"):
            return json(
                {
                    "code": 40001,
                    "message": "auto_initiate_settlement 参数必须为 'true' 或 'false'",
                },
                status=400,
            )
        auto_initiate_settlement = auto_initiate_settlement.lower() == "true"
    else:
        auto_initiate_settlement = None

    is_disabled = request.args.get("is_disabled")
    if is_disabled is not None and is_disabled.strip() != "":
        if is_disabled.lower() not in ("true", "false"):
            return json(
                {"code": 40001, "message": "is_disabled 参数必须为 'true' 或 'false'"},
                status=400,
            )
        is_disabled = is_disabled.lower() == "true"
    else:
        is_disabled = None

    settlement_type = request.args.get("settlement_type")
    if settlement_type is not None and settlement_type.strip() == "":
        settlement_type = None

    # ERP 系统 / 合作状态（字符串精确匹配）
    erp_system = request.args.get("erp_system")
    if erp_system is not None and erp_system.strip() == "":
        erp_system = None

    cooperation_status = request.args.get("cooperation_status")
    if cooperation_status is not None and cooperation_status.strip() == "":
        cooperation_status = None

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
    # 数据可见性（服务端强制）：无 customers:view_all 时仅统计当前用户负责的客户
    scope_user_id = await customer_scope_user_id(request)
    if scope_user_id is not None:
        customer_filters.append(
            or_(
                Customer.manager_id == scope_user_id,
                Customer.sales_manager_id == scope_user_id,
            )
        )
    if is_key_customer is not None:
        customer_filters.append(Customer.is_key_customer == is_key_customer)
    if is_real_estate is not None:
        customer_filters.append(Customer.is_real_estate == is_real_estate)
    if is_settlement_enabled is not None:
        customer_filters.append(Customer.is_settlement_enabled == is_settlement_enabled)
    if auto_initiate_settlement is not None:
        customer_filters.append(
            _bool_filter_condition(
                Customer.auto_initiate_settlement,
                auto_initiate_settlement,
                null_as_true=True,
            )
        )
    if is_disabled is not None:
        customer_filters.append(
            _bool_filter_condition(Customer.is_disabled, is_disabled, null_as_true=False)
        )
    if settlement_type:
        customer_filters.append(Customer.settlement_type == settlement_type)
    if erp_system:
        customer_filters.append(Customer.erp_system == erp_system)
    if cooperation_status:
        customer_filters.append(Customer.cooperation_status == cooperation_status)

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
        """为余额查询语句添加基础 + 筛选条件

        注意：调用方需自行以 Customer 为驱动表 `outerjoin(CustomerBalance, ... AND
        CustomerBalance.deleted_at IS NULL)`；此处仅保留 Customer 侧条件，避免把无余额行的
        包年客户过滤掉。
        """
        stmt = stmt.where(Customer.deleted_at.is_(None))
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
    # 包年客户余额以套餐剩余额度（package_cte.remaining）参与合计，非包年客户退化为
    # CustomerBalance.total_amount（无余额行时为 0）。
    package_cte = _build_package_remaining_cte()
    balance_amount_expr = func.coalesce(package_cte.c.remaining, CustomerBalance.total_amount, 0)

    async def _balance_totals(group: str) -> tuple[float, int]:
        stmt = (
            select(
                func.coalesce(func.sum(balance_amount_expr), 0),
                func.count(Customer.id),
            )
            .outerjoin(
                CustomerBalance,
                (CustomerBalance.customer_id == Customer.id)
                & (CustomerBalance.deleted_at.is_(None)),
            )
            .outerjoin(package_cte, Customer.id == package_cte.c.cid)
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
        select(func.count(Customer.id))
        .outerjoin(
            CustomerBalance,
            (CustomerBalance.customer_id == Customer.id) & (CustomerBalance.deleted_at.is_(None)),
        )
        .outerjoin(package_cte, Customer.id == package_cte.c.cid)
        .where(
            balance_amount_expr < LOW_BALANCE_THRESHOLD,
            _settlement_group_condition("prepaid"),
        )
    )
    low_balance_stmt = add_industry_joins(low_balance_stmt)
    low_balance_stmt = apply_balance_filters(low_balance_stmt, need_industry_join=True)
    low_balance_count = (await db.execute(low_balance_stmt)).scalar() or 0

    # --- 即将耗尽客户数（days_remaining ≤ 7，仅预付费）---
    from datetime import timedelta

    from sqlalchemy import Date, case

    from ...models.daily_consumption import DailyConsumption

    # 30 天窗口按 CST 口径，与展示层 days_remaining 的 CST 计算保持一致
    today = cst_today()
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
    # 燃尽天数：包年客户用套餐到期剩余天数，其余客户沿用按日均消耗推算
    # 「今天」显式取 CST 日期（同排序层）：func.current_date() 跟随 PG 会话时区，
    # CI 的 postgres 容器为 UTC 会取到 CST 次日，与展示层 days_remaining 差 1 天
    cst_today_expr = func.cast(func.timezone("Asia/Shanghai", func.now()), Date)
    burning_soon_days_expr = case(
        (
            package_cte.c.cid.is_not(None),
            func.cast(package_cte.c.expiry_date, Date) - cst_today_expr,
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
    burning_soon_stmt = (
        select(func.count(Customer.id))
        .outerjoin(
            CustomerBalance,
            (CustomerBalance.customer_id == Customer.id) & (CustomerBalance.deleted_at.is_(None)),
        )
        .outerjoin(consumption_cte, Customer.id == consumption_cte.c.cid)
        .outerjoin(package_cte, Customer.id == package_cte.c.cid)
        .where(
            Customer.deleted_at.is_(None),
            # 未设置结算类型归入预付费，故用分组条件而非 != 'postpaid'（NULL 会被 SQL 过滤掉）
            _settlement_group_condition("prepaid"),
            # 包年客户按到期天数判定（不要求近 30 天有消耗）；其余客户沿用消耗推算（需有消耗）
            or_(
                package_cte.c.cid.is_not(None),
                func.coalesce(consumption_cte.c.total_cost_30d, 0) > 0,
            ),
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

    # 数据可见性（服务端强制）：无 customers:view_all 时仅可查看自己负责客户的余额
    scope_user_id = await customer_scope_user_id(request)
    if scope_user_id is not None:
        from sqlalchemy import select

        from ...models.customers import Customer

        cust = (
            await db.execute(
                select(Customer).where(
                    Customer.id == customer_id,
                    Customer.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if cust is None or not (
            cust.manager_id == scope_user_id or cust.sales_manager_id == scope_user_id
        ):
            return json(
                {"code": 40301, "message": "无权访问该客户", "data": None},
                status=403,
            )

    balance = await balance_service.get_balance_by_customer_id(customer_id)

    # 包年客户年费不进 CustomerBalance：余额以「套餐剩余额度」呈现，与余额管理页/客户列表一致
    from ...services.package_balance import batch_query_package_info

    package_info = (await batch_query_package_info(db, [customer_id])).get(customer_id)

    if not balance:
        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "total_amount": (
                        float(package_info["remaining_amount"]) if package_info is not None else 0
                    ),
                    "real_amount": 0,
                    "bonus_amount": 0,
                    "used_total": 0,
                    "used_real": 0,
                    "used_bonus": 0,
                    "is_package": package_info is not None,
                    "package_expired": (
                        bool(package_info.get("is_expired")) if package_info is not None else False
                    ),
                    "package_remaining_amount": (
                        float(package_info["remaining_amount"])
                        if package_info is not None
                        else None
                    ),
                    "package_remaining_count": (
                        package_info.get("remaining_count") if package_info is not None else None
                    ),
                    "package_is_unlimited": (
                        bool(package_info.get("is_unlimited"))
                        if package_info is not None
                        else False
                    ),
                },
            }
        )

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "total_amount": (
                    float(package_info["remaining_amount"])
                    if package_info is not None
                    else (float(balance.total_amount) if balance.total_amount else 0)
                ),
                "real_amount": float(balance.real_amount) if balance.real_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "bonus_amount": float(balance.bonus_amount) if balance.bonus_amount else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "used_total": float(balance.used_total) if balance.used_total else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "used_real": float(balance.used_real) if balance.used_real else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "used_bonus": float(balance.used_bonus) if balance.used_bonus else 0,  # pyright: ignore[reportArgumentType, reportGeneralTypeIssues]
                "is_package": package_info is not None,
                "package_expired": (
                    bool(package_info.get("is_expired")) if package_info is not None else False
                ),
                "package_remaining_amount": (
                    float(package_info["remaining_amount"]) if package_info is not None else None
                ),
                "package_remaining_count": (
                    package_info.get("remaining_count") if package_info is not None else None
                ),
                "package_is_unlimited": (
                    bool(package_info.get("is_unlimited")) if package_info is not None else False
                ),
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

    # 数据可见性（服务端强制）：无 customers:view_all 时仅可重算自己负责客户的余额
    scope_user_id = await customer_scope_user_id(request)
    if scope_user_id is not None:
        from sqlalchemy import select

        from ...models.customers import Customer

        cust = (
            await db.execute(
                select(Customer).where(
                    Customer.id == customer_id,
                    Customer.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if cust is None or not (
            cust.manager_id == scope_user_id or cust.sales_manager_id == scope_user_id
        ):
            return json(
                {"code": 40301, "message": "无权访问该客户", "data": None},
                status=403,
            )

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

    # 数据可见性（服务端强制）：无 customers:view_all 时仅可为自己负责的客户充值
    scope_user_id = await customer_scope_user_id(request)
    if scope_user_id is not None:
        from sqlalchemy import select

        from ...models.customers import Customer

        cust = (
            await db.execute(
                select(Customer).where(
                    Customer.id == customer_id,
                    Customer.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if cust is None or not (
            cust.manager_id == scope_user_id or cust.sales_manager_id == scope_user_id
        ):
            return json(
                {"code": 40301, "message": "无权访问该客户", "data": None},
                status=403,
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

    # 数据可见性（服务端强制）：无 customers:view_all 时仅返回当前用户负责客户的充值记录
    scope_user_id = await customer_scope_user_id(request)

    records, total = await balance_service.get_recharge_records(
        customer_id=customer_id,
        page=page,
        page_size=page_size,
        mine_user_id=scope_user_id,
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

    # 数据可见性（服务端强制）：无 customers:view_all 时仅返回当前用户负责客户的消费记录
    # 代扣场景放宽：cr.customer 或关联结算单 invoice.customer 任一归属该用户即可见
    # （用 EXISTS 而非 join，避免「两个客户都归属该用户」时产生重复行）
    scope_user_id = await customer_scope_user_id(request)
    if scope_user_id is not None:
        from ...models.customers import Customer

        cr_customer_owned = (
            select(Customer.id)
            .where(
                Customer.id == ConsumptionRecord.customer_id,
                or_(
                    Customer.manager_id == scope_user_id,
                    Customer.sales_manager_id == scope_user_id,
                ),
            )
            .exists()
        )
        invoice_customer_owned = (
            select(Invoice.id)
            .join(Customer, Customer.id == Invoice.customer_id)
            .where(
                Invoice.id == ConsumptionRecord.invoice_id,
                or_(
                    Customer.manager_id == scope_user_id,
                    Customer.sales_manager_id == scope_user_id,
                ),
            )
            .exists()
        )
        stmt = stmt.where(or_(cr_customer_owned, invoice_customer_owned))

    if customer_id:
        # 被结算客户也可见：既看到扣自己余额的记录（cr.customer_id==cid），
        # 也看到「自己的结算单、扣结算账户余额」的记录（invoice.customer_id==cid）
        stmt = stmt.where(
            or_(
                ConsumptionRecord.customer_id == customer_id,
                ConsumptionRecord.invoice_id.in_(
                    select(Invoice.id).where(Invoice.customer_id == customer_id)
                ),
            )
        )

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

    # 批量查询实际扣款客户（cr.customer_id，代扣场景为结算账户客户，可能与页面筛选客户不同）
    from ...models.customers import Customer as _Customer

    cr_customer_ids = [r.customer_id for r in records if r.customer_id]
    customer_name_map: dict[int, tuple[str, int]] = {}
    if cr_customer_ids:
        cust_result = await db.execute(
            select(_Customer.id, _Customer.name, _Customer.company_id).where(
                _Customer.id.in_(cr_customer_ids)
            )
        )
        for row in cust_result:
            customer_name_map[row.id] = (row.name, row.company_id)

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
                        # 实际扣款客户（结算账户）：代扣时与页面入口客户不同，供前端展示
                        "actual_customer_name": customer_name_map[r.customer_id][0]
                        if r.customer_id in customer_name_map
                        else None,
                        "actual_company_id": customer_name_map[r.customer_id][1]
                        if r.customer_id in customer_name_map
                        else None,
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

    # 数据可见性（服务端强制）：无 customers:view_all 时仅可查看自己负责客户的趋势
    scope_user_id = await customer_scope_user_id(request)
    if scope_user_id is not None:
        from sqlalchemy import select

        from ...models.customers import Customer

        cust = (
            await db.execute(
                select(Customer).where(
                    Customer.id == customer_id,
                    Customer.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if cust is None or not (
            cust.manager_id == scope_user_id or cust.sales_manager_id == scope_user_id
        ):
            return json(
                {"code": 40301, "message": "无权访问该客户", "data": None},
                status=403,
            )

    service = AnalyticsService(db)
    trend = await service.get_balance_trend(customer_id=customer_id, months=months)

    return json({"code": 0, "message": "success", "data": trend})


# ==================== 余额导入 ====================
