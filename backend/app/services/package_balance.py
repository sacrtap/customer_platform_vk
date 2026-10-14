"""包年套餐余额口径 — 跨页面共享模块

包年客户（`Customer.price_policy='yearly'` / `PricingRule.pricing_type='package'`）
的年费只存在 `PricingRule.package_limits.base_fee`，**不写入 `CustomerBalance`**
（合同式预收）。因此「包年余额」必须由 `base_fee − 套餐内累计消耗` 独立计算。

余额管理页与客户管理页（列表/详情/预览/预测）共用本模块，避免两处各写一份口径
导致同一客户在两个页面显示不一致。改动此处即同时影响所有消费方。

两个入口:
- `build_package_remaining_cte()`: SQL 侧 CTE，供列表筛选/排序/KPI 聚合复用。
- `batch_query_package_info()`: Python 侧批量查询，供行组装（追加包年字段）复用。

两者必须保持同一口径（每客户取最新一条生效规则；过期规则单独判定）。
"""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.billing import PricingRule
from ..models.customers import Customer
from ..models.daily_consumption import DailyConsumption
from ..utils.timezone import utc_now


def build_package_remaining_cte():
    """构建包年剩余额度 CTE（每客户最新一条生效包年规则）

    `remaining = GREATEST(base_fee - 套餐内累计消耗, 0)`,同时暴露未截断的
    `consumed`(套餐内累计消耗),供列表的余额范围筛选、total_amount/used_total
    排序与 KPI 统计复用。窗口函数取「每客户最新一条」生效规则,
    与 `batch_query_package_info` 的口径保持一致。
    """
    from sqlalchemy import func

    # 套餐内累计消耗：关联子查询按 pricing_rule_id 聚合，避免 GROUP BY JSON 列
    # （PostgreSQL 的 json 类型无相等操作符，不能出现在 GROUP BY 中）
    consumed_subq = (
        select(func.coalesce(func.sum(DailyConsumption.total_cost), 0))
        .where(
            DailyConsumption.pricing_rule_id == PricingRule.id,
            DailyConsumption.deleted_at.is_(None),
        )
        .correlate(PricingRule)
        .scalar_subquery()
    )

    rules_subq = (
        select(
            PricingRule.customer_id.label("cid"),
            # package_limits 为 JSON 列：base_fee 提取并转 NUMERIC（PG: package_limits->>'base_fee'）
            PricingRule.package_limits["base_fee"].as_numeric(12, 2).label("base_fee"),  # pyright: ignore[reportAttributeAccessIssue]
            PricingRule.expiry_date.label("expiry_date"),
            consumed_subq.label("consumed"),
            func.row_number()
            .over(partition_by=PricingRule.customer_id, order_by=PricingRule.created_at.desc())
            .label("rn"),
        )
        .where(
            PricingRule.pricing_type == "package",
            PricingRule.deleted_at.is_(None),
            PricingRule.effective_date <= func.now(),
            or_(PricingRule.expiry_date >= func.now(), PricingRule.expiry_date.is_(None)),
        )
        .subquery()
    )

    return (
        select(
            rules_subq.c.cid,
            func.greatest(rules_subq.c.base_fee - rules_subq.c.consumed, 0).label("remaining"),
            # 未截断的套餐内累计消耗:供「已消耗」列展示与排序复用
            # (包年客户已消耗 = 套餐内累计消耗,实时含未结算)
            rules_subq.c.consumed.label("consumed"),
            rules_subq.c.expiry_date.label("expiry_date"),
        )
        .where(rules_subq.c.rn == 1)
        .cte("package_remaining")
    )


async def batch_query_package_info(db: AsyncSession, customer_ids: list[int]) -> dict[int, dict]:
    """批量查询客户包年套餐信息（生效规则 / 累计消耗 / 剩余额度与次数 / 过期标记）

    包年客户年费不进 `CustomerBalance`，其可用额度由 `PricingRule.package_limits.base_fee`
    减去套餐内累计消耗得出，故列表/详情页需单独查询。

    Args:
        db: 异步会话
        customer_ids: 待查询客户 ID 列表

    Returns:
        {customer_id: {
            "is_expired": bool,              # 无生效规则但有已过期包年规则
            "base_fee": float,
            "is_unlimited": bool,
            "limit_count": float | None,     # 不限量套餐为 None
            "remaining_amount": float,       # 未过期: max(base_fee - 累计消耗, 0); 过期: 0
            "remaining_count": float | None,  # 未过期且限量: max(limit_count - 累计订单量, 0)
            "consumed_amount": float | None,  # 套餐内累计消耗（实时,含未结算;过期包年为 None）
            "expiry_date": datetime | None,
            "effective_date": datetime | None,
        }}
    """
    if not customer_ids:
        return {}

    from sqlalchemy import func

    now = utc_now()

    # 1. 生效包年规则（每客户取最新一条：order_by 后首次出现的即最新）
    rules_result = await db.execute(
        select(PricingRule)
        .where(
            PricingRule.customer_id.in_(customer_ids),
            PricingRule.pricing_type == "package",
            PricingRule.effective_date <= now,
            or_(PricingRule.expiry_date >= now, PricingRule.expiry_date.is_(None)),
            PricingRule.deleted_at.is_(None),
        )
        .order_by(PricingRule.customer_id, PricingRule.created_at.desc())
    )
    latest_rules: dict = {}
    for rule in rules_result.scalars().all():
        if rule.customer_id is not None and rule.customer_id not in latest_rules:
            latest_rules[rule.customer_id] = rule

    # 2. 生效规则的累计消耗与累计订单量（按 pricing_rule_id 精确关联套餐内消费记录）
    consumed_map: dict[int, dict] = {}
    rule_ids = [r.id for r in latest_rules.values()]
    if rule_ids:
        consumption_result = await db.execute(
            select(
                DailyConsumption.pricing_rule_id,
                func.coalesce(func.sum(DailyConsumption.total_cost), 0).label("total_cost"),
                func.coalesce(func.sum(DailyConsumption.order_count), 0).label("order_count"),
            )
            .where(
                DailyConsumption.pricing_rule_id.in_(rule_ids),
                DailyConsumption.deleted_at.is_(None),
            )
            .group_by(DailyConsumption.pricing_rule_id)
        )
        for row in consumption_result.all():
            consumed_map[row.pricing_rule_id] = {
                "total_cost": float(row.total_cost or 0),
                "order_count": int(row.order_count or 0),
            }

    # 3. 组装生效客户的剩余额度与剩余次数
    info_map: dict[int, dict] = {}
    for cid, rule in latest_rules.items():
        limits = rule.package_limits or {}
        base_fee = float(limits.get("base_fee", 0) or 0)
        is_unlimited = bool(limits.get("is_unlimited", False))
        limit_count = float(limits.get("limit_count", 0) or 0)
        consumed = consumed_map.get(rule.id, {"total_cost": 0.0, "order_count": 0})
        remaining_amount = max(base_fee - consumed["total_cost"], 0.0)
        remaining_count: float | None = None
        if not is_unlimited:
            remaining_count = max(limit_count - consumed["order_count"], 0.0)
        info_map[cid] = {
            "is_expired": False,
            "base_fee": base_fee,
            "is_unlimited": is_unlimited,
            "limit_count": None if is_unlimited else limit_count,
            "remaining_amount": remaining_amount,
            "remaining_count": remaining_count,
            # 套餐内累计消耗（实时,含未结算）：供「已消耗」列展示
            "consumed_amount": consumed["total_cost"],
            "expiry_date": rule.expiry_date,
            "effective_date": rule.effective_date,
        }

    # 4. 过期判断：无生效规则、客户 price_policy='yearly'、存在已过期包年规则
    missing_ids = [cid for cid in customer_ids if cid not in latest_rules]
    if missing_ids:
        expired_result = await db.execute(
            select(PricingRule)
            .join(Customer, PricingRule.customer_id == Customer.id)
            .where(
                PricingRule.customer_id.in_(missing_ids),
                PricingRule.pricing_type == "package",
                PricingRule.expiry_date.is_not(None),
                PricingRule.expiry_date < now,
                PricingRule.deleted_at.is_(None),
                Customer.price_policy == "yearly",
            )
            .order_by(PricingRule.customer_id, PricingRule.expiry_date.desc())
        )
        for rule in expired_result.scalars().all():
            if rule.customer_id is None or rule.customer_id in info_map:
                continue  # 同一客户只取最近一条已过期规则
            limits = rule.package_limits or {}
            info_map[rule.customer_id] = {
                "is_expired": True,
                "base_fee": float(limits.get("base_fee", 0) or 0),
                "is_unlimited": bool(limits.get("is_unlimited", False)),
                "limit_count": None,
                "remaining_amount": 0.0,
                "remaining_count": None,
                # 过期包年无「实时套餐内消耗」语义：置 None，展示层回退 CustomerBalance.used_total
                "consumed_amount": None,
                "expiry_date": rule.expiry_date,
                "effective_date": rule.effective_date,
            }

    return info_map


def resolve_effective_balance(
    balance_total: float | None, package_info: dict | None
) -> tuple[float, bool]:
    """解析客户「有效余额」——包年客户以套餐剩余额度为准

    Args:
        balance_total: `CustomerBalance.total_amount`（无余额行时为 None）
        package_info: `batch_query_package_info` 返回的该客户包年信息（非包年为 None）

    Returns:
        (有效余额, 是否包年)。包年（含已过期）→ 套餐剩余额度（过期为 0）；
        非包年 → `balance_total`（None 记 0）。
    """
    if package_info is not None:
        return float(package_info.get("remaining_amount", 0.0) or 0.0), True
    return float(balance_total or 0.0), False
