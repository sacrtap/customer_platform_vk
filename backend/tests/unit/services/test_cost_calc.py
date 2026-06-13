"""CostCalcService 单元测试"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.billing import PricingRule
from app.models.daily_consumption import DailyConsumption
from app.models.daily_order import DailyOrder
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

    async def test_calc_unified_price(self, service):
        """测试统一价格计算"""
        # 10 层 * 500 元/层 = 5000 元
        cost = service._calc_unified(quantity=10, unit_price=Decimal("500.00"))
        assert cost == Decimal("5000.00")

    async def test_calc_tiered_price_single_tier(self, service):
        """测试阶梯价格计算 - 单阶梯"""
        pricing_rule = MagicMock(spec=PricingRule)
        pricing_rule.tiers = []
        pricing_rule.price = Decimal("500.00")

        # 无阶梯配置时返回基础价格
        cost = service._calc_tiered(quantity=10, pricing_rule=pricing_rule)
        assert cost == Decimal("500.00")

    async def test_calc_tiered_price_multi_tier(self, service):
        """测试阶梯价格计算 - 多阶梯"""
        pricing_rule = MagicMock(spec=PricingRule)

        # 创建阶梯配置
        tier1 = MagicMock()
        tier1.min_quantity = 0
        tier1.max_quantity = 10
        tier1.price = Decimal("100.00")

        tier2 = MagicMock()
        tier2.min_quantity = 10
        tier2.max_quantity = 100
        tier2.price = Decimal("80.00")

        pricing_rule.tiers = [tier1, tier2]
        pricing_rule.price = Decimal("50.00")

        # 15 层：前 10 层 * 100 + 后 5 层 * 80 = 1000 + 400 = 1400
        cost = service._calc_tiered(quantity=15, pricing_rule=pricing_rule)
        assert cost == Decimal("1400.00")

    async def test_calc_package_price(self, service):
        """测试包年价格计算 - 按日分摊"""
        # 36500 元/年 / 365 = 100 元/日
        cost = service._calc_package(base_fee=Decimal("36500.00"))
        assert cost == Decimal("100.00")

    async def test_calc_package_price_with_remainder(self, service):
        """测试包年价格计算 - 有余数"""
        # 1000 元/年 / 365 = 2.74 元/日（四舍五入）
        cost = service._calc_package(base_fee=Decimal("1000.00"))
        assert cost == Decimal("2.74")

    async def test_calculate_group_cost_unified(self, service):
        """测试分组费用计算 - 统一价格"""
        order_group = {
            "device_type": "X",
            "layer_type": "single",
            "order_count": 5,
            "total_floor_count": 50,
        }

        pricing_rule = MagicMock(spec=PricingRule)
        pricing_rule.price_type = "unified"
        pricing_rule.price = Decimal("100.00")

        cost = service._calculate_group_cost(order_group, pricing_rule)
        assert cost == Decimal("5000.00")

    async def test_calculate_group_cost_tiered(self, service):
        """测试分组费用计算 - 阶梯价格"""
        order_group = {
            "device_type": "X",
            "layer_type": "single",
            "order_count": 5,
            "total_floor_count": 15,
        }

        pricing_rule = MagicMock(spec=PricingRule)
        pricing_rule.price_type = "tiered"
        pricing_rule.tiers = []
        pricing_rule.price = Decimal("500.00")

        cost = service._calculate_group_cost(order_group, pricing_rule)
        assert cost == Decimal("500.00")

    async def test_calculate_group_cost_package(self, service):
        """测试分组费用计算 - 包年价格"""
        order_group = {
            "device_type": "X",
            "layer_type": "single",
            "order_count": 5,
            "total_floor_count": 50,
        }

        pricing_rule = MagicMock(spec=PricingRule)
        pricing_rule.price_type = "package"
        pricing_rule.base_fee = Decimal("36500.00")

        cost = service._calculate_group_cost(order_group, pricing_rule)
        assert cost == Decimal("100.00")

    async def test_get_active_pricing_rule_found(self, service, mock_db):
        """测试查询生效计费规则 - 找到"""
        mock_result = MagicMock()
        mock_rule = MagicMock(spec=PricingRule)
        mock_rule.id = 1
        mock_result.scalar_one_or_none.return_value = mock_rule
        mock_db.execute.return_value = mock_result

        with patch("app.services.cost_calc.date") as mock_date:
            mock_date.today.return_value = date(2024, 1, 15)
            rule = await service._get_active_pricing_rule(customer_id=1)

        assert rule is not None
        assert rule.id == 1
        mock_db.execute.assert_called_once()

    async def test_get_active_pricing_rule_not_found(self, service, mock_db):
        """测试查询生效计费规则 - 未找到"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("app.services.cost_calc.date") as mock_date:
            mock_date.today.return_value = date(2024, 1, 15)
            rule = await service._get_active_pricing_rule(customer_id=999)

        assert rule is None

    async def test_calculate_customer_cost_with_rule(self, service, mock_db):
        """测试客户费用计算 - 有计费规则"""
        # Mock _get_order_groups
        order_groups = [
            {"device_type": "X", "layer_type": "single", "order_count": 5, "total_floor_count": 50}
        ]
        service._get_order_groups = AsyncMock(return_value=order_groups)

        # Mock _get_active_pricing_rule
        mock_rule = MagicMock(spec=PricingRule)
        mock_rule.id = 1
        mock_rule.price_type = "unified"
        mock_rule.price = Decimal("100.00")
        service._get_active_pricing_rule = AsyncMock(return_value=mock_rule)

        result = await service._calculate_customer_cost(
            customer_id=1, consumption_date=date(2024, 1, 15)
        )

        assert result["has_rule"] is True
        assert result["cost_result_list"] == [5]
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    async def test_calculate_customer_cost_without_rule(self, service, mock_db):
        """测试客户费用计算 - 无计费规则"""
        # Mock _get_order_groups
        order_groups = [
            {"device_type": "X", "layer_type": "single", "order_count": 5, "total_floor_count": 50}
        ]
        service._get_order_groups = AsyncMock(return_value=order_groups)

        # Mock _get_active_pricing_rule
        service._get_active_pricing_rule = AsyncMock(return_value=None)

        result = await service._calculate_customer_cost(
            customer_id=1, consumption_date=date(2024, 1, 15)
        )

        assert result["has_rule"] is False
        assert result["cost_result_list"] == [5]
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

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
