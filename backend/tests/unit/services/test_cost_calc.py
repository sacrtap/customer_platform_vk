"""CostCalcService 单元测试"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.billing import PricingRule
from app.services.cost_calc import CostCalcService
from app.utils.timezone import local_date_to_utc_start


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

        # 创建阶梯配置（唯一形态：min/max 为闭区间整数边界，max=null 表示无上界；
        # price 为 JSON 原生数值，DB 层 tiers 为 JSON 列）
        tier1 = {"min": 0, "max": 9, "price": 100.0}
        tier2 = {"min": 10, "max": 99, "price": 80.0}

        pricing_rule.tiers = [tier1, tier2]
        pricing_rule.unit_price = Decimal("50.00")

        # 15 层：前 10 层 * 100 + 后 5 层 * 80 = 1000 + 400 = 1400
        cost = service._calc_tiered(quantity=15, pricing_rule=pricing_rule)
        assert cost == Decimal("1400.00")

    # ========== 包年价格计算 ==========

    async def test_calc_package_price_unlimited(self, service):
        """测试包年价格计算 - 不限量套餐按日分摊"""
        pkg_rule = MagicMock()
        pkg_rule.package_limits = {"base_fee": 36500, "is_unlimited": True}
        cost = service._calc_package(pkg_rule)
        assert cost == Decimal("100.00")  # 36500 / 365 = 100.00

    async def test_calc_package_price_limited_with_orders(self, service):
        """测试包年价格计算 - 限量套餐按用量计收"""
        pkg_rule = MagicMock()
        pkg_rule.package_limits = {
            "base_fee": 10000,
            "is_unlimited": False,
            "limit_count": 100,
        }
        # 5 单 × (10000 / 100) = 5 × 100 = 500
        cost = service._calc_package(pkg_rule, {"order_count": 5})
        assert cost == Decimal("500.00")

    async def test_calc_package_price_limited_no_orders(self, service):
        """测试包年价格计算 - 限量套餐当天无订单时费用为 0"""
        pkg_rule = MagicMock()
        pkg_rule.package_limits = {
            "base_fee": 10000,
            "is_unlimited": False,
            "limit_count": 100,
        }
        cost = service._calc_package(pkg_rule, None)
        assert cost == Decimal("0")

    async def test_calc_package_price_with_remainder(self, service):
        """测试包年价格计算 - 不限量套餐有余数（四舍五入）"""
        pkg_rule = MagicMock()
        pkg_rule.package_limits = {"base_fee": 1000, "is_unlimited": True}
        cost = service._calc_package(pkg_rule)
        assert cost == Decimal("2.74")  # 1000 / 365 = 2.739... → 2.74

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

    async def test_calculate_group_cost_package_unlimited(self, service):
        """测试分组费用计算 - 不限量包年价格（按日分摊）"""
        order_group = {
            "device_type": "X",
            "layer_type": "single",
            "order_count": 5,
            "total_floor_count": 50,
        }

        pricing_rule = MagicMock(spec=PricingRule)
        pricing_rule.pricing_type = "package"
        pricing_rule.unit_price = Decimal("100.00")
        pricing_rule.package_limits = {"base_fee": 36500, "is_unlimited": True}

        cost = service._calculate_group_cost(order_group, pricing_rule)
        assert cost == Decimal("100.00")  # 36500 / 365 = 100.00

    async def test_calculate_group_cost_package_limited(self, service):
        """测试分组费用计算 - 限量包年价格（按用量计收）

        base_fee=10000, limit_count=100, order_count=5
        → 5 × (10000/100) = 5 × 100 = 500
        """
        order_group = {
            "device_type": "X",
            "layer_type": "single",
            "order_count": 5,
            "total_floor_count": 50,
        }

        pricing_rule = MagicMock(spec=PricingRule)
        pricing_rule.pricing_type = "package"
        pricing_rule.unit_price = None
        pricing_rule.package_limits = {
            "base_fee": 10000,
            "is_unlimited": False,
            "limit_count": 100,
        }

        cost = service._calculate_group_cost(order_group, pricing_rule)
        assert cost == Decimal("500.00")

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
            customer_id=1, reference_date=local_date_to_utc_start("2024-01-15")
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
            customer_id=999, reference_date=local_date_to_utc_start("2024-01-15")
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
            customer_id=1, reference_date=local_date_to_utc_start("2024-01-15")
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
            customer_id=1, reference_date=local_date_to_utc_start("2024-01-15")
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
        service._get_active_package_rule = AsyncMock(return_value=None)

        result = await service._calculate_customer_cost(
            customer_id=1, consumption_date=local_date_to_utc_start("2024-01-15")
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
        service._get_active_package_rule = AsyncMock(return_value=None)

        result = await service._calculate_customer_cost(
            customer_id=1, consumption_date=local_date_to_utc_start("2024-01-15")
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
        service._get_active_package_rule = AsyncMock(return_value=None)

        result = await service._calculate_customer_cost(
            customer_id=1, consumption_date=local_date_to_utc_start("2024-01-15")
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
        service._get_active_package_rule = AsyncMock(return_value=None)

        result = await service._calculate_customer_cost(
            customer_id=1, consumption_date=local_date_to_utc_start("2024-01-15")
        )

        assert result["has_rule"] is True
        # 回退到 single 规则：按订单数 × 单价 = 2 × 10 = 20
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.total_cost == Decimal("20.00")

    async def test_calculate_customer_cost_package_priority(self, service, mock_db):
        """测试客户费用计算 - 包年规则优先于 (device_type, layer_type) 匹配

        不限量套餐：所有分组共用按日分摊费用（100.00/天）
        """
        order_groups = [
            {"device_type": "X", "layer_type": "single", "order_count": 5, "total_floor_count": 50},
            {"device_type": "L", "layer_type": "multi", "order_count": 3, "total_floor_count": 20},
        ]
        service._get_order_groups = AsyncMock(return_value=order_groups)

        # 存在包年规则，所有分组都用包年规则计费
        mock_package = MagicMock(spec=PricingRule)
        mock_package.id = 9
        mock_package.pricing_type = "package"
        mock_package.unit_price = Decimal("100.00")
        mock_package.package_limits = {"base_fee": 36500, "is_unlimited": True}
        service._get_active_pricing_rules = AsyncMock(return_value={})
        service._get_active_package_rule = AsyncMock(return_value=mock_package)

        result = await service._calculate_customer_cost(
            customer_id=1, consumption_date=local_date_to_utc_start("2024-01-15")
        )

        assert result["has_rule"] is True
        # 两个分组都使用包年规则（按日分摊 unit_price）
        assert mock_db.add.call_count == 2
        added_objs = [call.args[0] for call in mock_db.add.call_args_list]
        for obj in added_objs:
            assert obj.has_pricing_rule is True
            assert obj.pricing_rule_id == 9
            assert obj.total_cost == Decimal("100.00")

    async def test_calculate_customer_cost_package_rule_no_device_match(self, service, mock_db):
        """测试包年规则不参与 (device_type, layer_type) 匹配"""
        mock_rule = MagicMock(spec=PricingRule)
        mock_rule.id = 7
        mock_rule.pricing_type = "package"
        mock_rule.device_type = None
        mock_rule.layer_type = None
        mock_rule.unit_price = Decimal("50.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_rule]
        mock_db.execute.return_value = mock_result

        rules_map = await service._get_active_pricing_rules(
            customer_id=1, reference_date=local_date_to_utc_start("2024-01-15")
        )

        # 包年规则不应出现在 (device_type, layer_type) 匹配字典中
        assert len(rules_map) == 0

    async def test_get_active_package_rule_found(self, service, mock_db):
        """测试查询生效包年规则 - 找到"""
        mock_package = MagicMock(spec=PricingRule)
        mock_package.id = 9
        mock_package.pricing_type = "package"
        mock_package.unit_price = Decimal("100.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_package
        mock_db.execute.return_value = mock_result

        package_rule = await service._get_active_package_rule(
            customer_id=1, reference_date=local_date_to_utc_start("2024-01-15")
        )

        assert package_rule is not None
        assert package_rule.id == 9

    async def test_get_active_package_rule_not_found(self, service, mock_db):
        """测试查询生效包年规则 - 未找到"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        package_rule = await service._get_active_package_rule(
            customer_id=1, reference_date=local_date_to_utc_start("2024-01-15")
        )

        assert package_rule is None

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

        result = await service.calculate_daily_cost(
            consumption_date=local_date_to_utc_start("2024-01-15")
        )

        assert result["total_customers"] == 3
        assert result["calculated"] == 2
        assert result["no_rule"] == 1
        assert service._calculate_customer_cost.call_count == 3
