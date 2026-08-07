"""费用计算服务 - 每日消耗费用计算"""

import logging
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select

from app.models.billing import PricingRule
from app.models.daily_consumption import DailyConsumption
from app.models.daily_order import DailyOrder

logger = logging.getLogger(__name__)


class CostCalcService:
    """费用计算服务

    根据客户的计费规则 (PricingRule) 计算每日订单的消耗费用。
    支持多层递增计费模式。
    """

    def __init__(self, db):
        """初始化服务

        Args:
            db: SQLAlchemy async session
        """
        self.db = db

    async def calculate_daily_cost(self, consumption_date: date) -> dict:
        """计算指定日期的消耗费用

        Args:
            consumption_date: 消耗日期

        Returns:
            {total_customers, calculated, no_rule}
        """
        # 1. 先清空该日期的所有费用记录
        await self._clear_consumptions(consumption_date)

        # 2. 查询当日有订单的客户 ID 列表（去重）
        result = await self.db.execute(
            select(DailyOrder.customer_id)
            .where(DailyOrder.sync_date == consumption_date, DailyOrder.customer_id.isnot(None))
            .distinct()
        )
        customer_ids = [row[0] for row in result.all()]

        total_customers = len(customer_ids)
        calculated_count = 0
        no_rule_count = 0

        # 3. 对每个客户计算费用
        for customer_id in customer_ids:
            result = await self._calculate_customer_cost(
                customer_id=customer_id, consumption_date=consumption_date
            )
            if result.get("has_rule"):
                calculated_count += 1
            else:
                no_rule_count += 1

        return {
            "total_customers": total_customers,
            "calculated": calculated_count,
            "no_rule": no_rule_count,
        }

    async def _clear_consumptions(self, consumption_date: date) -> None:
        """清空指定日期的所有费用记录"""
        from sqlalchemy import delete

        result = await self.db.execute(
            delete(DailyConsumption).where(DailyConsumption.consumption_date == consumption_date)
        )
        await self.db.commit()
        logger.info(f"已清空 {consumption_date} 的 {result.rowcount} 条费用记录")

    async def _calculate_customer_cost(self, customer_id: int, consumption_date: date) -> dict:
        """计算单个客户的消耗费用

        Args:
            customer_id: 客户 ID
            consumption_date: 消耗日期

        Returns:
            {"has_rule", cost_result_list}
        """
        # 1. 查询当日订单（按 device_type + layer_type 分组）
        order_groups = await self._get_order_groups(
            customer_id=customer_id, consumption_date=consumption_date
        )

        # 2. 查询客户生效中的所有计费规则（按 device_type + layer_type 匹配）
        rules_map = await self._get_active_pricing_rules(
            customer_id=customer_id, reference_date=consumption_date
        )

        has_any_rule = len(rules_map) > 0

        # 3. 为每个分组创建 daily_consumption 记录
        for group in order_groups:
            cost = Decimal("0")
            pricing_rule: Optional[PricingRule] = None

            # 精确匹配 (device_type, layer_type)，再回退到 (device_type, 'single')
            key = (group["device_type"], group["layer_type"])
            pricing_rule = rules_map.get(key) or rules_map.get((group["device_type"], "single"))

            if pricing_rule:
                cost = self._calculate_group_cost(group, pricing_rule)

            daily_consumption = DailyConsumption(
                customer_id=customer_id,
                consumption_date=consumption_date,
                device_type=group["device_type"],
                layer_type=group["layer_type"],
                order_count=group["order_count"],
                total_floor_count=group["total_floor_count"],
                total_cost=cost.quantize(Decimal("0.01")),
                pricing_rule_id=pricing_rule.id if pricing_rule else None,
                has_pricing_rule=pricing_rule is not None,
            )
            self.db.add(daily_consumption)

        await self.db.commit()

        return {
            "has_rule": has_any_rule,
            "cost_result_list": [g["order_count"] for g in order_groups],
        }

    async def _get_order_groups(self, customer_id: int, consumption_date: date) -> List[dict]:
        """查询客户当日订单，按设备类型 + 楼层类型分组

        Args:
            customer_id: 客户 ID
            consumption_date: 消耗日期（同时也是 sync_date）

        Returns:
            List of order groups with device_type, layer_type, order_count, total_floor_count
        """
        result = await self.db.execute(
            select(
                DailyOrder.device_type,
                DailyOrder.floor_count,
            ).where(DailyOrder.customer_id == customer_id, DailyOrder.sync_date == consumption_date)
        )

        # 在 Python 中按 (device_type, layer_type) 分组
        groups_dict: dict[tuple[str, str], dict] = {}
        for row in result.all():
            device_type = row.device_type or "unknown"
            floor_count = row.floor_count or 1
            layer_type = "single" if floor_count <= 1 else "multi"
            key = (device_type, layer_type)
            if key not in groups_dict:
                groups_dict[key] = {
                    "device_type": device_type,
                    "layer_type": layer_type,
                    "order_count": 0,
                    "total_floor_count": 0,
                }
            groups_dict[key]["order_count"] += 1
            groups_dict[key]["total_floor_count"] += floor_count

        return list(groups_dict.values())

    async def _get_active_pricing_rules(
        self, customer_id: int, reference_date: date
    ) -> Dict[Tuple[str, str], PricingRule]:
        """查询客户在指定日期生效中的所有计费规则

        按 (device_type, layer_type) 构建查找字典，支持精确匹配。

        Args:
            customer_id: 客户 ID
            reference_date: 参考日期（用于判断规则是否生效）

        Returns:
            Dict mapping (device_type, layer_type) -> PricingRule
        """
        result = await self.db.execute(
            select(PricingRule)
            .where(
                PricingRule.customer_id == customer_id,
                PricingRule.effective_date <= reference_date,
                (PricingRule.expiry_date >= reference_date) | (PricingRule.expiry_date.is_(None)),
                PricingRule.deleted_at.is_(None),
            )
            .order_by(PricingRule.created_at.desc())
        )
        rules = result.scalars().all()

        # 构建 (device_type, layer_type) -> PricingRule 字典
        # layer_type 为 NULL 时默认为 'single'
        # 同一 key 有多条规则时，取最新一条（已按 created_at desc 排序）
        rules_map: Dict[Tuple[str, str], PricingRule] = {}
        for rule in rules:
            key = (rule.device_type, rule.layer_type or "single")
            if key not in rules_map:
                rules_map[key] = rule

        return rules_map

    def _calculate_group_cost(self, order_group: dict, pricing_rule: PricingRule) -> Decimal:
        """根据计费规则计算分组费用

        Args:
            order_group: Order group dict with total_floor_count and order_count
            pricing_rule: PricingRule object

        Returns:
            Calculated cost as Decimal
        """
        total_floor_count = order_group["total_floor_count"]
        order_count = order_group["order_count"]
        unit_price = Decimal(str(pricing_rule.unit_price or 0))

        if pricing_rule.pricing_type == "tiered":  # pyright: ignore[reportGeneralTypeIssues]
            return self._calc_tiered(total_floor_count, pricing_rule)
        elif pricing_rule.pricing_type == "package":  # pyright: ignore[reportGeneralTypeIssues]
            return self._calc_package(pricing_rule)
        else:  # fixed
            # 判断多层计费类型
            multi_pricing_type = pricing_rule.multi_floor_pricing_type or "unified"  # pyright: ignore[reportGeneralTypeIssues]

            layer_type = order_group.get("layer_type", "single")
            if (
                layer_type == "multi"
                and multi_pricing_type == "incremental"
                and pricing_rule.additional_floor_price is not None  # pyright: ignore[reportGeneralTypeIssues]
            ):
                return self._calc_incremental(
                    order_count,
                    total_floor_count,
                    unit_price,
                    Decimal(str(pricing_rule.additional_floor_price or 0)),  # pyright: ignore[reportGeneralTypeIssues]
                )
            else:
                # 统一模式：按订单数量 × 单价（不区分楼层）
                return self._calc_unified(order_count, unit_price)

    def _calc_unified(self, quantity: int, unit_price: Decimal) -> Decimal:
        """统一价格结算：订单数量 × 单价"""
        return Decimal(quantity) * Decimal(str(unit_price))

    def _calc_incremental(
        self,
        order_count: int,
        total_floor_count: int,
        unit_price: Decimal,
        additional_floor_price: Decimal,
    ) -> Decimal:
        """递增价格结算

        计算公式：
            unit_price × order_count + additional_floor_price × (total_floor_count - order_count)

        其中：
            - unit_price 为首层单价（每个订单的首层费用）
            - additional_floor_price 为其他层单价（每多一层的额外费用）
            - total_floor_count - order_count = 所有订单的非首层楼层数总和

        示例：3层房源1套，单价5，其他层单价6
            5×1 + 6×(3-1) = 5 + 12 = 17 元
        """
        base_cost = Decimal(order_count) * unit_price
        extra_floors = total_floor_count - order_count
        if extra_floors < 0:
            extra_floors = 0
        extra_cost = Decimal(extra_floors) * additional_floor_price
        return base_cost + extra_cost

    def _calc_tiered(self, quantity: int, pricing_rule: PricingRule) -> Decimal:
        """阶梯价格结算"""
        tiers = pricing_rule.tiers or []
        if not tiers:  # pyright: ignore[reportGeneralTypeIssues]
            return Decimal(str(pricing_rule.unit_price or 0)) * quantity

        # Sort tiers by min_quantity
        sorted_tiers = sorted(tiers, key=lambda t: t.get("min_quantity", 0))  # pyright: ignore[reportCallIssue, reportArgumentType, reportAttributeAccessIssue]

        remaining = quantity
        total_cost = Decimal("0")

        for tier in sorted_tiers:
            if remaining <= 0:
                break

            min_qty = tier.get("min_quantity", 0)
            max_qty = tier.get("max_quantity", 999999)
            tier_range = max_qty - min_qty
            tier_quantity = min(remaining, tier_range)
            tier_price = Decimal(str(tier.get("price", pricing_rule.unit_price or 0)))
            total_cost += Decimal(tier_quantity) * tier_price
            remaining -= tier_quantity

        return total_cost

    def _calc_package(self, pricing_rule: PricingRule) -> Decimal:
        """包年价格结算（按日分摊）"""
        return Decimal(str(pricing_rule.unit_price or 0)).quantize(Decimal("0.01"))
