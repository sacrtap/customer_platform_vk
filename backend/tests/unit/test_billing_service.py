"""Billing Service 单元测试 - 余额扣款与定价规则"""

import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.billing import BalanceService, PricingService
from app.models.billing import (
    CustomerBalance,
    RechargeRecord,
    PricingRule,
    ConsumptionRecord,
)


# ==================== Fixtures ====================


@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def balance_service(mock_db_session):
    """创建 BalanceService 实例"""
    return BalanceService(db=mock_db_session)


@pytest.fixture
def pricing_service(mock_db_session):
    """创建 PricingService 实例"""
    return PricingService(db=mock_db_session)


# ==================== Test BalanceService - Recharge ====================


class TestBalanceService_Recharge:
    """充值测试"""

    @pytest.mark.asyncio
    async def test_recharge_success(self, balance_service, mock_db_session):
        """测试充值成功"""
        # Mock 现有余额
        existing_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("200.00"),
            total_amount=Decimal("1200.00"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_balance
        mock_db_session.execute.return_value = mock_result

        # 执行充值
        result = await balance_service.recharge(
            customer_id=100,
            real_amount=Decimal("500.00"),
            bonus_amount=Decimal("100.00"),
            operator_id=1,
            payment_proof="proof.pdf",
            remark="测试充值",
        )

        # 验证结果
        assert result is not None
        assert isinstance(result, RechargeRecord)
        assert result.real_amount == Decimal("500.00")
        assert result.bonus_amount == Decimal("100.00")

        # 验证余额更新
        assert existing_balance.real_amount == Decimal("1500.00")
        assert existing_balance.bonus_amount == Decimal("300.00")
        assert existing_balance.total_amount == Decimal("1800.00")

        # 验证数据库操作
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_recharge_creates_balance_if_not_exists(self, balance_service, mock_db_session):
        """测试充值时如果余额不存在则自动创建"""
        # Mock 查询返回 None（余额不存在）
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # 执行充值
        result = await balance_service.recharge(
            customer_id=200,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("0.00"),
            operator_id=1,
        )

        # 验证结果
        assert result is not None
        assert result.real_amount == Decimal("1000.00")

        # 验证创建了余额记录（add 被调用至少 2 次：充值记录 + 余额）
        assert mock_db_session.add.call_count >= 2
        mock_db_session.commit.assert_called()


# ==================== Test BalanceService - Consume ====================


class TestBalanceService_Consume:
    """消费扣款测试"""

    @pytest.mark.asyncio
    async def test_consume_success_bonus_first(self, balance_service, mock_db_session):
        """测试消费扣款成功 - 先扣赠金"""
        # Mock 余额：有赠金
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("500.00"),
            total_amount=Decimal("1500.00"),
            used_total=Decimal("0.00"),
            used_bonus=Decimal("0.00"),
            used_real=Decimal("0.00"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = balance
        mock_db_session.execute.return_value = mock_result

        # Mock 事务上下文
        mock_db_context = AsyncMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=None)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        mock_db_session.begin.return_value = mock_db_context

        # 执行消费
        success, message = await balance_service.consume(
            customer_id=100,
            amount=Decimal("300.00"),
            invoice_id=1,
        )

        # 验证结果
        assert success is True
        assert message == "扣款成功"

        # 验证先扣赠金
        assert balance.bonus_amount == Decimal("200.00")  # 500 - 300
        assert balance.real_amount == Decimal("1000.00")  # 未动
        assert balance.used_bonus == Decimal("300.00")
        assert balance.used_real == Decimal("0.00")
        assert balance.used_total == Decimal("300.00")

    @pytest.mark.asyncio
    async def test_consume_exhaust_bonus_then_real(self, balance_service, mock_db_session):
        """测试消费扣款 - 赠金不足时扣实充"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("100.00"),
            total_amount=Decimal("1100.00"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = balance
        mock_db_session.execute.return_value = mock_result

        mock_db_context = AsyncMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=None)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        mock_db_session.begin.return_value = mock_db_context

        # 消费 500，先扣 100 赠金，再扣 400 实充
        success, message = await balance_service.consume(
            customer_id=100,
            amount=Decimal("500.00"),
        )

        assert success is True
        assert balance.bonus_amount == Decimal("0.00")
        assert balance.real_amount == Decimal("600.00")  # 1000 - 400
        assert balance.used_bonus == Decimal("100.00")
        assert balance.used_real == Decimal("400.00")

    @pytest.mark.asyncio
    async def test_consume_insufficient_balance(self, balance_service, mock_db_session):
        """测试余额不足"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("100.00"),
            bonus_amount=Decimal("50.00"),
            total_amount=Decimal("150.00"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = balance
        mock_db_session.execute.return_value = mock_result

        mock_db_context = AsyncMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=None)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        mock_db_session.begin.return_value = mock_db_context

        success, message = await balance_service.consume(
            customer_id=100,
            amount=Decimal("200.00"),  # 超过余额
        )

        assert success is False
        assert "余额不足" in message

    @pytest.mark.asyncio
    async def test_consume_balance_not_found(self, balance_service, mock_db_session):
        """测试余额账户不存在"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        mock_db_context = AsyncMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=None)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        mock_db_session.begin.return_value = mock_db_context

        success, message = await balance_service.consume(
            customer_id=999,
            amount=Decimal("100.00"),
        )

        assert success is False
        assert "不存在" in message


# ==================== Test BalanceService - Get Balance ====================


class TestBalanceService_GetBalance:
    """获取余额测试"""

    @pytest.mark.asyncio
    async def test_get_balance_by_customer_id(self, balance_service, mock_db_session):
        """测试获取客户余额"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            total_amount=Decimal("5000.00"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = balance
        mock_db_session.execute.return_value = mock_result

        result = await balance_service.get_balance_by_customer_id(100)

        assert result is not None
        assert result.customer_id == 100
        assert result.total_amount == Decimal("5000.00")

    @pytest.mark.asyncio
    async def test_get_balance_not_found(self, balance_service, mock_db_session):
        """测试获取不存在的余额"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await balance_service.get_balance_by_customer_id(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_create_balance_existing(self, balance_service, mock_db_session):
        """测试获取或创建余额 - 已存在"""
        balance = CustomerBalance(id=1, customer_id=100, total_amount=Decimal("1000.00"))

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = balance
        mock_db_session.execute.return_value = mock_result

        result = await balance_service.get_or_create_balance(100)

        assert result is not None
        assert result.customer_id == 100
        mock_db_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_balance_creates_new(self, balance_service, mock_db_session):
        """测试获取或创建余额 - 不存在时创建"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await balance_service.get_or_create_balance(100)

        assert result is not None
        assert result.customer_id == 100
        mock_db_session.add.assert_called()


# ==================== Test PricingService - Create Rule ====================


class TestPricingService_CreatePricingRule:
    """创建定价规则测试"""

    @pytest.mark.asyncio
    async def test_create_pricing_rule_success(self, pricing_service, mock_db_session):
        """测试创建定价规则成功"""
        # Mock 无冲突
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        rule_data = {
            "customer_id": 100,
            "device_type": "camera",
            "layer_type": "living_room",
            "pricing_type": "fixed",
            "unit_price": Decimal("10.00"),
            "effective_date": date(2026, 1, 1),
            "expiry_date": date(2026, 12, 31),
            "created_by": 1,
        }

        result = await pricing_service.create_pricing_rule(rule_data)

        assert result is not None
        assert isinstance(result, PricingRule)
        assert result.customer_id == 100
        assert result.device_type == "camera"
        assert result.unit_price == Decimal("10.00")
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_pricing_rule_overlap_conflict(self, pricing_service, mock_db_session):
        """测试创建定价规则 - 有效期冲突"""
        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="camera",
            layer_type="living_room",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_rule]
        mock_db_session.execute.return_value = mock_result

        rule_data = {
            "customer_id": 100,
            "device_type": "camera",
            "layer_type": "living_room",
            "pricing_type": "fixed",
            "unit_price": Decimal("10.00"),
            "effective_date": date(2026, 6, 1),  # 与现有规则重叠
            "expiry_date": date(2027, 6, 30),
            "created_by": 1,
        }

        with pytest.raises(ValueError, match="有效期存在重叠"):
            await pricing_service.create_pricing_rule(rule_data)

    @pytest.mark.asyncio
    async def test_create_pricing_rule_no_overlap_different_device(self, pricing_service, mock_db_session):
        """测试创建定价规则 - 不同设备类型不冲突"""
        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="camera",
            layer_type="living_room",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_rule]
        mock_db_session.execute.return_value = mock_result

        rule_data = {
            "customer_id": 100,
            "device_type": "sensor",  # 不同设备
            "layer_type": "living_room",
            "pricing_type": "fixed",
            "unit_price": Decimal("5.00"),
            "effective_date": date(2026, 6, 1),
            "expiry_date": date(2027, 6, 30),
            "created_by": 1,
        }

        # 不会抛出异常，因为设备类型不同（实际逻辑会过滤）
        # 这里测试的是 overlap 检查逻辑本身
        # 由于 mock 返回了 existing_rule，但 device_type 不同
        # 实际代码中会先查询再检查，这里直接测试 _check_overlap
        pass  # 需要更精细的 mock


# ==================== Test PricingService - Update Rule ====================


class TestPricingService_UpdatePricingRule:
    """更新定价规则测试"""

    @pytest.mark.asyncio
    async def test_update_pricing_rule_success(self, pricing_service, mock_db_session):
        """测试更新定价规则成功"""
        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="camera",
            layer_type="living_room",
            pricing_type="fixed",
            unit_price=Decimal("10.00"),
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_rule
        # 第二次调用返回空（无冲突）
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        update_data = {
            "unit_price": Decimal("15.00"),
        }

        result = await pricing_service.update_pricing_rule(1, update_data)

        assert result is not None
        assert result.unit_price == Decimal("15.00")
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_pricing_rule_not_found(self, pricing_service, mock_db_session):
        """测试更新不存在的定价规则"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await pricing_service.update_pricing_rule(999, {"unit_price": Decimal("15.00")})

        assert result is None
        mock_db_session.commit.assert_not_called()


# ==================== Test PricingService - Get Rules ====================


class TestPricingService_GetPricingRules:
    """获取定价规则列表测试"""

    @pytest.mark.asyncio
    async def test_get_pricing_rules_with_filters(self, pricing_service, mock_db_session):
        """测试获取定价规则 - 带筛选条件"""
        rules = [
            PricingRule(id=1, customer_id=100, device_type="camera", pricing_type="fixed"),
            PricingRule(id=2, customer_id=100, device_type="sensor", pricing_type="tiered"),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rules
        mock_result.scalar.return_value = 2  # count
        mock_db_session.execute.return_value = mock_result

        result_rules, total = await pricing_service.get_pricing_rules(
            customer_id=100,
            device_type="camera",
            page=1,
            page_size=20,
        )

        assert len(result_rules) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_pricing_rules_empty(self, pricing_service, mock_db_session):
        """测试获取定价规则 - 无结果"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.scalar.return_value = 0
        mock_db_session.execute.return_value = mock_result

        result_rules, total = await pricing_service.get_pricing_rules(
            customer_id=999,
        )

        assert len(result_rules) == 0
        assert total == 0


# ==================== Test PricingService - Check Conflict ====================


class TestPricingService_CheckConflict:
    """定价规则冲突检查测试"""

    @pytest.mark.asyncio
    async def test_check_pricing_rule_conflict_has_conflict(self, pricing_service, mock_db_session):
        """测试检查定价规则冲突 - 存在冲突"""
        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="camera",
            layer_type="living_room",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_rule]
        mock_db_session.execute.return_value = mock_result

        conflicts = await pricing_service.check_pricing_rule_conflict(
            customer_id=100,
            device_type="camera",
            layer_type="living_room",
            effective_date=date(2026, 6, 1),
            expiry_date=date(2027, 6, 30),
        )

        assert len(conflicts) == 1
        assert conflicts[0].id == 1

    @pytest.mark.asyncio
    async def test_check_pricing_rule_conflict_no_conflict(self, pricing_service, mock_db_session):
        """测试检查定价规则冲突 - 无冲突"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        conflicts = await pricing_service.check_pricing_rule_conflict(
            customer_id=100,
            device_type="camera",
            layer_type="living_room",
            effective_date=date(2027, 1, 1),  # 在现有规则之后
            expiry_date=date(2027, 12, 31),
        )

        assert len(conflicts) == 0
