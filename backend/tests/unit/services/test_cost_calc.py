"""CostCalcService 单元测试"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.billing import PricingRule
from app.services.cost_calc import CostCalcService


class TestCostCalcService:
    """费用计算服务测试"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """创建服务实例"""
        return CostCalcService(db=mock_db)

    # ========== 统一价格计算 ==========

    async def test_calc_unified_price(self, service):
        """测试统一价格计算"""
        # 10 层 * 500 元/层 = 5000 元
        cost = service._calc_unified(quantity=10, unit_price=Decimal("500.00"))
        assert cost == Decimal("5000.00")

    # ========== 递增价格计算 ==========

    async def test_calc_incremental_basic(self, service):
        """测试递增价格计算 - 基本场景

        3层房源1套，单价5，其他层单价6
        5×1 + 6×(3-1) = 5 + 12 = 17
        """
        cost = service._calc_incremental(
            order_count=1,
            total_floor_count=3,
            unit_price=Decimal("5"),
            additional_floor_price=Decimal("6"),
        )
        assert cost == Decimal("17")

    async def test_calc_incremental_multiple_orders(self, service):
        """测试递增价格计算 - 多订单

        2套3层房源，单价5，其他层单价6
        总楼层数=6，订单数=2
        5×2 + 6×(6-2) = 10 + 24 = 34
        """
        cost = service._calc_incremental(
            order_count=2,
            total_floor_count=6,
            unit_price=Decimal("5"),
            additional_floor_price=Decimal("6"),
        )
        assert cost == Decimal("34")

    async def test_calc_incremental_single_floor(self, service):
        """测试递增价格计算 - 单层房源（total_floor_count == order_count）

        3套1层房源，单价5，其他层单价6
        总楼层数=3，订单数=3
        5×3 + 6×(3-3) = 15 + 0 = 15
        """
        cost = service._calc_incremental(
            order_count=3,
            total_floor_count=3,
            unit_price=Decimal("5"),
            additional_floor_price=Decimal("6"),
        )
        assert cost == Decimal("15")

    async def test_calc_incremental_mixed_floors(self, service):
        """测试递增价格计算 - 混合楼层

        1套2层 + 1套3层 = 总楼层数5，订单数2
        单价5，其他层单价6
        5×2 + 6×(5-2) = 10 + 18 = 28
        """
        cost = service._calc_incremental(
            order_count=2,
            total_floor_count=5,
            unit_price=Decimal("5"),
            additional_floor_price=Decimal("6"),
        )
        assert cost == Decimal("28")

    # ========== 阶梯价格计算 ==========

    async def test_calc_tiered_price_single_tier(self, service):
        """测试阶梯价格计算 - 单阶梯"""
        pricing_rule = MagicMock(spec=PricingRule)
        pricing_rule.tiers = []
        pricing_rule.unit_price = Decimal("500.00")

        # 无阶梯配置时返回基础价格 * quantity
        cost = service._calc_tiered(quantity=10, pricing_rule=pricing_rule)
        assert cost == Decimal("5000.00")

    async def test_calc_tiered_price_multi_tier(self, service):
        """测试阶梯价格计算 - 多阶梯"""
        pricing_rule = MagicMock(spec=PricingRule)

        # 创建阶梯配置（使用 dict）
        tier1 = {"min_quantity": 0, "max_quantity": 10, "price": Decimal("100.00")}
        tier2 = {"min_quantity": 10, "max_quantity": 100, "price": Decimal("80.00")}

        pricing_rule.tiers = [tier1, tier2]
        pricing_rule.unit_price = Decimal("50.00")

        # 15 层：前 10 层 * 100 + 后 5 层 * 80 = 1000 + 400 = 1400
        cost = service._calc_tiered(quantity=15, pricing_rule=pricing_rule)
        assert cost == Decimal("1400.00")

    # ========== 包年价格计算 ==========

    async def test_calc_package_price(self, service):
        """测试包年价格计算 - 按日分摊（返回 unit_price）"""
        pkg_rule = MagicMock()
        pkg_rule.unit_price = Decimal("100.00")
        cost = service._calc_package(pkg_rule)
        assert cost == Decimal("100.00")

    async def test_calc_package_price_with_remainder(self, service):
        """测试包年价格计算 - 有余数（四舍五入）"""
        pkg_rule = MagicMock()
        pkg_rule.unit_price = Decimal("1000.00") / Decimal("365")
        cost = service._calc_package(pkg_rule)
        assert cost == Decimal("2.74")

    # ========== 分组费用计算 ==========

    async def test_calculate_group_cost_unified(self, service):
        """测试分组费用计算 - 统一价格（按订单数计费）"""
        order_group = {
            "device_type": "X",
            "layer_type": "single",
            "order_count": 5,
            "total_floor_count": 50,
        }

        pricing_rule = MagicMock(spec=PricingRule)
        pricing_rule.pricing_type = "fixed"
        pricing_rule.unit_price = Decimal("100.00")
        pricing_rule.multi_floor_pricing_type = "unified"
        pricing_rule.additional_floor_price = None

        cost = service._calculate_group_cost(order_group, pricing_rule)
        assert cost == Decimal("500.00")  # 5 orders × 100

    async def test_calculate_group_cost_incremental(self, service):
        """测试分组费用计算 - 递增价格

        3层房源1套，单价5，其他层单价6 → 17元
        """
        order_group = {
            "device_type": "L",
            "layer_type": "multi",
            "order_count": 1,
            "total_floor_count": 3,
        }

        pricing_rule = MagicMock(spec=PricingRule)
        pricing_rule.pricing_type = "fixed"
        pricing_rule.unit_price = Decimal("5")
        pricing_rule.multi_floor_pricing_type = "incremental"
        pricing_rule.additional_floor_price = Decimal("6")

        cost = service._calculate_group_cost(order_group, pricing_rule)
        assert cost == Decimal("17")

    async def test_calculate_group_cost_multi_unified(self, service):
        """测试分组费用计算 - 多层统一价格

        多层统一模式：按订单数量 × 单价（不区分楼层）
        2 个订单，总楼层数 6，单价 10 → 2 × 10 = 20 元
        """
        order_group = {
            "device_type": "L",
            "layer_type": "multi",
            "order_count": 2,
            "total_floor_count": 6,
        }

        pricing_rule = MagicMock(spec=PricingRule)
        pricing_rule.pricing_type = "fixed"
        pricing_rule.unit_price = Decimal("10")
        pricing_rule.multi_floor_pricing_type = "unified"
        pricing_rule.additional_floor_price = None

        cost = service._calculate_group_cost(order_group, pricing_rule)
        assert cost == Decimal("20")  # 2 orders × 10

    async def test_calculate_group_cost_tiered(self, service):
        """测试分组费用计算 - 阶梯价格"""
        order_group = {
            "device_type": "X",
            "layer_type": "single",
            "order_count": 5,
            "total_floor_count": 15,
        }

        pricing_rule = MagicMock(spec=PricingRule)
        pricing_rule.pricing_type = "tiered"
        pricing_rule.tiers = []
        pricing_rule.unit_price = Decimal("500.00")

        # 无阶梯时返回 unit_price * total_floor_count
        cost = service._calculate_group_cost(order_group, pricing_rule)
        assert cost == Decimal("7500.00")  # 500 * 15

    async def test_calculate_group_cost_package(self, service):
        """测试分组费用计算 - 包年价格（返回 unit_price）"""
        order_group = {
            "device_type": "X",
            "layer_type": "single",
            "order_count": 5,
            "total_floor_count": 50,
        }

        pricing_rule = MagicMock(spec=PricingRule)
        pricing_rule.pricing_type = "package"
        pricing_rule.unit_price = Decimal("100.00")

        cost = service._calculate_group_cost(order_group, pricing_rule)
        assert cost == Decimal("100.00")

    # ========== 规则查询 ==========

    async def test_get_active_pricing_rules_found(self, service, mock_db):
        """测试查询生效计费规则 - 找到并返回字典"""
        mock_rule = MagicMock(spec=PricingRule)
        mock_rule.id = 1
        mock_rule.device_type = "L"
        mock_rule.layer_type = "multi"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_rule]
        mock_db.execute.return_value = mock_result

        rules_map = await service._get_active_pricing_rules(
            customer_id=1, reference_date=date(2024, 1, 15)
        )

        assert len(rules_map) == 1
        assert ("L", "multi") in rules_map
        assert rules_map[("L", "multi")].id == 1

    async def test_get_active_pricing_rules_empty(self, service, mock_db):
        """测试查询生效计费规则 - 无规则"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        rules_map = await service._get_active_pricing_rules(
            customer_id=999, reference_date=date(2024, 1, 15)
        )

        assert len(rules_map) == 0

    async def test_get_active_pricing_rules_null_layer_type(self, service, mock_db):
        """测试查询生效计费规则 - layer_type 为 NULL 时默认为 single"""
        mock_rule = MagicMock(spec=PricingRule)
        mock_rule.id = 1
        mock_rule.device_type = "X"
        mock_rule.layer_type = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_rule]
        mock_db.execute.return_value = mock_result

        rules_map = await service._get_active_pricing_rules(
            customer_id=1, reference_date=date(2024, 1, 15)
        )

        assert ("X", "single") in rules_map

    async def test_get_active_pricing_rules_multiple(self, service, mock_db):
        """测试查询生效计费规则 - 多条规则按 (device_type, layer_type) 匹配"""
        mock_rule1 = MagicMock(spec=PricingRule)
        mock_rule1.id = 1
        mock_rule1.device_type = "X"
        mock_rule1.layer_type = "single"

        mock_rule2 = MagicMock(spec=PricingRule)
        mock_rule2.id = 2
        mock_rule2.device_type = "L"
        mock_rule2.layer_type = "multi"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_rule1, mock_rule2]
        mock_db.execute.return_value = mock_result

        rules_map = await service._get_active_pricing_rules(
            customer_id=1, reference_date=date(2024, 1, 15)
        )

        assert len(rules_map) == 2
        assert ("X", "single") in rules_map
        assert ("L", "multi") in rules_map

    # ========== 客户费用计算 ==========

    async def test_calculate_customer_cost_with_rule(self, service, mock_db):
        """测试客户费用计算 - 有计费规则"""
        # Mock _get_order_groups
        order_groups = [
            {"device_type": "X", "layer_type": "single", "order_count": 5, "total_floor_count": 50}
        ]
        service._get_order_groups = AsyncMock(return_value=order_groups)

        # Mock _get_active_pricing_rules
        mock_rule = MagicMock(spec=PricingRule)
        mock_rule.id = 1
        mock_rule.pricing_type = "fixed"
        mock_rule.unit_price = Decimal("100.00")
        mock_rule.multi_floor_pricing_type = "unified"
        mock_rule.additional_floor_price = None
        service._get_active_pricing_rules = AsyncMock(return_value={("X", "single"): mock_rule})

        result = await service._calculate_customer_cost(
            customer_id=1, consumption_date=date(2024, 1, 15)
        )

        assert result["has_rule"] is True
        assert result["cost_result_list"] == [5]
        mock_db.add.assert_called_once()
        assert mock_db.commit.call_count == 1

    async def test_calculate_customer_cost_without_rule(self, service, mock_db):
        """测试客户费用计算 - 无计费规则"""
        # Mock _get_order_groups
        order_groups = [
            {"device_type": "X", "layer_type": "single", "order_count": 5, "total_floor_count": 50}
        ]
        service._get_order_groups = AsyncMock(return_value=order_groups)

        # Mock _get_active_pricing_rules
        service._get_active_pricing_rules = AsyncMock(return_value={})

        result = await service._calculate_customer_cost(
            customer_id=1, consumption_date=date(2024, 1, 15)
        )

        assert result["has_rule"] is False
        assert result["cost_result_list"] == [5]
        mock_db.add.assert_called_once()
        assert mock_db.commit.call_count == 1

    async def test_calculate_customer_cost_incremental(self, service, mock_db):
        """测试客户费用计算 - 递增模式

        3层房源1套，单价5，其他层单价6 → 17元
        """
        order_groups = [
            {"device_type": "L", "layer_type": "multi", "order_count": 1, "total_floor_count": 3}
        ]
        service._get_order_groups = AsyncMock(return_value=order_groups)

        mock_rule = MagicMock(spec=PricingRule)
        mock_rule.id = 1
        mock_rule.pricing_type = "fixed"
        mock_rule.unit_price = Decimal("5")
        mock_rule.multi_floor_pricing_type = "incremental"
        mock_rule.additional_floor_price = Decimal("6")
        service._get_active_pricing_rules = AsyncMock(return_value={("L", "multi"): mock_rule})

        result = await service._calculate_customer_cost(
            customer_id=1, consumption_date=date(2024, 1, 15)
        )

        assert result["has_rule"] is True
        # 验证 DailyConsumption 被创建，且 total_cost 为 17
        mock_db.add.assert_called_once()
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.total_cost == Decimal("17.00")
        assert added_obj.total_floor_count == 3

    async def test_calculate_customer_cost_rule_fallback(self, service, mock_db):
        """测试客户费用计算 - 规则回退到 single

        当订单分组为 multi 但无 multi 规则时，回退到 single 规则
        """
        order_groups = [
            {"device_type": "X", "layer_type": "multi", "order_count": 2, "total_floor_count": 5}
        ]
        service._get_order_groups = AsyncMock(return_value=order_groups)

        # 只有 single 规则，无 multi 规则
        mock_rule = MagicMock(spec=PricingRule)
        mock_rule.id = 1
        mock_rule.pricing_type = "fixed"
        mock_rule.unit_price = Decimal("10")
        mock_rule.multi_floor_pricing_type = "unified"
        mock_rule.additional_floor_price = None
        service._get_active_pricing_rules = AsyncMock(return_value={("X", "single"): mock_rule})

        result = await service._calculate_customer_cost(
            customer_id=1, consumption_date=date(2024, 1, 15)
        )

        assert result["has_rule"] is True
        # 回退到 single 规则：按订单数 × 单价 = 2 × 10 = 20
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.total_cost == Decimal("20.00")

    # ========== 每日费用计算 ==========

    async def test_calculate_daily_cost(self, service, mock_db):
        """测试每日费用计算"""
        # Mock 查询有订单的客户 ID
        mock_result = MagicMock()
        mock_result.all.return_value = [(1,), (2,), (3,)]
        mock_db.execute.return_value = mock_result

        # Mock _calculate_customer_cost
        service._calculate_customer_cost = AsyncMock(
            side_effect=[
                {"has_rule": True, "cost_result_list": [5]},
                {"has_rule": False, "cost_result_list": [3]},
                {"has_rule": True, "cost_result_list": [7]},
            ]
        )

        result = await service.calculate_daily_cost(consumption_date=date(2024, 1, 15))

        assert result["total_customers"] == 3
        assert result["calculated"] == 2
        assert result["no_rule"] == 1
        assert service._calculate_customer_cost.call_count == 3
