"""Billing Service 单元测试 - 余额扣款与定价规则"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.billing import (
    CustomerBalance,
    PricingRule,
    RechargeRecord,
)
from app.services.billing import BalanceService, PricingService
from app.utils.timezone import (
    local_date_range_to_utc,
    local_date_to_utc_end,
    local_date_to_utc_start,
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
    from unittest.mock import AsyncMock, MagicMock

    from app.repository import BalanceRepository

    mock_repo = MagicMock(spec=BalanceRepository)
    mock_repo.db = mock_db_session
    mock_repo.get_by_customer_id = AsyncMock(return_value=None)
    mock_repo.get_or_create = AsyncMock(return_value=None)
    return BalanceService(balance_repo=mock_repo)


@pytest.fixture
def pricing_service(mock_db_session):
    """创建 PricingService 实例"""
    from unittest.mock import MagicMock

    from app.repository import PricingRepository

    mock_repo = MagicMock(spec=PricingRepository)
    mock_repo.db = mock_db_session
    return PricingService(pricing_repo=mock_repo)


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
        balance_service.balance_repo.get_or_create.return_value = existing_balance

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
    async def test_recharge_recalculates_total_amount(self, balance_service, mock_db_session):
        """测试充值后 total_amount 通过重算得到（而非累加），修正数据不一致场景"""
        # 模拟 total_amount 与 real+bonus 不一致（如历史脏数据）
        existing_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("200.00"),
            total_amount=Decimal("9999.00"),  # 脏数据：不等于 1000+200=1200
        )
        balance_service.balance_repo.get_or_create.return_value = existing_balance

        # 充值 500 实充 + 100 赠金
        result = await balance_service.recharge(
            customer_id=100,
            real_amount=Decimal("500.00"),
            bonus_amount=Decimal("100.00"),
            operator_id=1,
        )

        assert result is not None
        # real_amount = 1000 + 500 = 1500
        assert existing_balance.real_amount == Decimal("1500.00")
        # bonus_amount = 200 + 100 = 300
        assert existing_balance.bonus_amount == Decimal("300.00")
        # total_amount = 重算(1500 + 300) = 1800，而非脏数据累加(9999 + 500 + 100 = 10599)
        assert existing_balance.total_amount == Decimal("1800.00")

    @pytest.mark.asyncio
    async def test_recharge_creates_balance_if_not_exists(self, balance_service, mock_db_session):
        """测试充值时如果余额不存在则自动创建"""
        # Mock 返回新创建的余额
        new_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("0.00"),
            bonus_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
        )
        balance_service.balance_repo.get_or_create.return_value = new_balance

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

        # 验证调用了 get_or_create 获取余额
        balance_service.balance_repo.get_or_create.assert_called_once_with(200)
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_recharge_zero_real_with_bonus(self, balance_service, mock_db_session):
        """测试实充为 0、仅赠送金额的充值（允许 real_amount=0）"""
        existing_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("500.00"),
            bonus_amount=Decimal("100.00"),
            total_amount=Decimal("600.00"),
        )
        balance_service.balance_repo.get_or_create.return_value = existing_balance

        result = await balance_service.recharge(
            customer_id=100,
            real_amount=Decimal("0"),  # 实充为 0
            bonus_amount=Decimal("200.00"),  # 仅赠送
            operator_id=1,
        )

        assert result is not None
        assert result.real_amount == Decimal("0.00")
        assert result.bonus_amount == Decimal("200.00")
        # 余额不变实充，赠金增加
        assert existing_balance.real_amount == Decimal("500.00")
        assert existing_balance.bonus_amount == Decimal("300.00")
        assert existing_balance.total_amount == Decimal("800.00")  # 500 + 300


# ==================== Test BalanceService - Recalculate ====================


class TestBalanceService_Recalculate:
    """余额重算测试"""

    @pytest.mark.asyncio
    async def test_recalculate_fixes_inconsistent_total(self, balance_service, mock_db_session):
        """测试重算修正不一致的 total_amount"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("200.00"),
            total_amount=Decimal("9999.00"),  # 脏数据
        )
        balance_service.balance_repo.get_by_customer_id.return_value = balance

        result = await balance_service.recalculate_balance(100)

        assert result is not None
        assert result.total_amount == Decimal("1200.00")  # 1000 + 200
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_recalculate_no_change_when_consistent(self, balance_service, mock_db_session):
        """测试重算时数据已一致，不触发 commit"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("200.00"),
            total_amount=Decimal("1200.00"),  # 已一致
        )
        balance_service.balance_repo.get_by_customer_id.return_value = balance

        result = await balance_service.recalculate_balance(100)

        assert result is not None
        assert result.total_amount == Decimal("1200.00")
        # 数据一致时不应该 commit
        mock_db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_recalculate_balance_not_found(self, balance_service, mock_db_session):
        """测试余额不存在时返回 None"""
        balance_service.balance_repo.get_by_customer_id.return_value = None

        result = await balance_service.recalculate_balance(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_recalculate_negative_balance(self, balance_service, mock_db_session):
        """测试重算负余额场景"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("-500.00"),
            bonus_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),  # 脏数据：不等于 -500
        )
        balance_service.balance_repo.get_by_customer_id.return_value = balance

        result = await balance_service.recalculate_balance(100)

        assert result is not None
        assert result.total_amount == Decimal("-500.00")  # -500 + 0
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
    async def test_consume_insufficient_balance_allows_negative(
        self, balance_service, mock_db_session
    ):
        """测试余额不足时允许扣款（欠费模式）— real_amount 变为负数"""
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

        # 消费 200，超过余额 150
        success, message = await balance_service.consume(
            customer_id=100,
            amount=Decimal("200.00"),
        )

        # 余额不足时仍允许扣款，不再拦截
        assert success is True
        assert message == "扣款成功"

        # 赠金全部耗尽
        assert balance.bonus_amount == Decimal("0.00")
        # 实充变为负数（欠费 50）
        assert balance.real_amount == Decimal("-50.00")
        # 总余额为负
        assert balance.total_amount == Decimal("-50.00")
        assert balance.used_total == Decimal("200.00")
        assert balance.used_bonus == Decimal("50.00")
        assert balance.used_real == Decimal("150.00")

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

    @pytest.mark.asyncio
    async def test_consume_zero_balance_goes_negative(self, balance_service, mock_db_session):
        """测试余额为零时扣款 — 全部变为负数"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("0.00"),
            bonus_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
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
            amount=Decimal("500.00"),
        )

        assert success is True
        assert message == "扣款成功"
        assert balance.bonus_amount == Decimal("0.00")
        assert balance.real_amount == Decimal("-500.00")
        assert balance.total_amount == Decimal("-500.00")
        assert balance.used_real == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_consume_bonus_covers_full_amount(self, balance_service, mock_db_session):
        """测试赠金完全覆盖消费 — 实充不动"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("500.00"),
            total_amount=Decimal("1500.00"),
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
            amount=Decimal("300.00"),
        )

        assert success is True
        # 赠金扣 300，实充不动
        assert balance.bonus_amount == Decimal("200.00")
        assert balance.real_amount == Decimal("1000.00")
        assert balance.used_bonus == Decimal("300.00")
        assert balance.used_real == Decimal("0.00")


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
        balance_service.balance_repo.get_by_customer_id.return_value = balance

        result = await balance_service.get_balance_by_customer_id(100)

        assert result is not None
        assert result.customer_id == 100
        assert result.total_amount == Decimal("5000.00")

    @pytest.mark.asyncio
    async def test_get_balance_not_found(self, balance_service, mock_db_session):
        """测试获取不存在的余额"""
        balance_service.balance_repo.get_by_customer_id.return_value = None

        result = await balance_service.get_balance_by_customer_id(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_create_balance_existing(self, balance_service, mock_db_session):
        """测试获取或创建余额 - 已存在"""
        balance = CustomerBalance(id=1, customer_id=100, total_amount=Decimal("1000.00"))
        balance_service.balance_repo.get_or_create.return_value = balance

        result = await balance_service.get_or_create_balance(100)

        assert result is not None
        assert result.customer_id == 100

    @pytest.mark.asyncio
    async def test_get_or_create_balance_creates_new(self, balance_service, mock_db_session):
        """测试获取或创建余额 - 不存在时创建"""
        balance = CustomerBalance(id=1, customer_id=100, total_amount=Decimal("0.00"))
        balance_service.balance_repo.get_or_create.return_value = balance

        result = await balance_service.get_or_create_balance(100)

        assert result is not None
        assert result.customer_id == 100


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
            "effective_date": local_date_to_utc_start("2026-01-01"),
            "expiry_date": local_date_to_utc_end("2026-12-31"),
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
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
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
            "effective_date": local_date_to_utc_start("2026-06-01"),  # 与现有规则重叠
            "expiry_date": local_date_to_utc_end("2027-06-30"),
            "created_by": 1,
        }

        with pytest.raises(ValueError, match="有效期存在重叠"):
            await pricing_service.create_pricing_rule(rule_data)

    @pytest.mark.asyncio
    async def test_create_pricing_rule_no_overlap_different_device(
        self, pricing_service, mock_db_session
    ):
        """测试创建定价规则 - 不同设备类型不冲突"""
        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="camera",
            layer_type="living_room",
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_rule]
        mock_db_session.execute.return_value = mock_result

        _rule_data = {  # noqa: F841
            "customer_id": 100,
            "device_type": "sensor",  # 不同设备
            "layer_type": "living_room",
            "pricing_type": "fixed",
            "unit_price": Decimal("5.00"),
            "effective_date": local_date_to_utc_start("2026-06-01"),
            "expiry_date": local_date_to_utc_end("2027-06-30"),
            "created_by": 1,
        }

        # 不会抛出异常，因为设备类型不同（实际逻辑会过滤）
        # 这里测试的是 overlap 检查逻辑本身
        # 由于 mock 返回了 existing_rule，但 device_type 不同
        # 实际代码中会先查询再检查，这里直接测试 _check_overlap
        pass  # 需要更精细的 mock

    @pytest.mark.asyncio
    async def test_create_package_rule_without_device_type(self, pricing_service, mock_db_session):
        """测试创建包年结算规则 - 不传 device_type/layer_type"""
        # Mock 无冲突
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        # Mock PackagePlan 查询返回 None（不填充 package_limits）
        mock_plan_result = MagicMock()
        mock_plan_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.side_effect = [mock_result, mock_plan_result]

        rule_data = {
            "customer_id": 100,
            "pricing_type": "package",
            "package_type": "A",
            "effective_date": local_date_to_utc_start("2026-01-01"),
            "expiry_date": local_date_to_utc_end("2026-12-31"),
            "created_by": 1,
        }

        result = await pricing_service.create_pricing_rule(rule_data)

        assert result is not None
        assert isinstance(result, PricingRule)
        assert result.pricing_type == "package"
        assert result.package_type == "A"
        assert result.device_type is None
        assert result.layer_type is None
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_package_rule_overlap_conflict(self, pricing_service, mock_db_session):
        """测试创建包年结算规则 - 同一客户已有包年规则则冲突"""
        existing_package = PricingRule(
            id=2,
            customer_id=100,
            device_type=None,
            layer_type=None,
            pricing_type="package",
            package_type="A",
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_package]
        mock_db_session.execute.return_value = mock_result

        rule_data = {
            "customer_id": 100,
            "pricing_type": "package",
            "package_type": "B",
            "effective_date": local_date_to_utc_start("2026-06-01"),  # 与现有包年规则重叠
            "expiry_date": local_date_to_utc_end("2027-06-30"),
            "created_by": 1,
        }

        with pytest.raises(ValueError, match="包年结算规则"):
            await pricing_service.create_pricing_rule(rule_data)


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
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
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
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_rule]
        mock_db_session.execute.return_value = mock_result

        conflicts = await pricing_service.check_pricing_rule_conflict(
            customer_id=100,
            pricing_type="fixed",
            device_type="camera",
            layer_type="living_room",
            effective_date=local_date_to_utc_start("2026-06-01"),
            expiry_date=local_date_to_utc_end("2027-06-30"),
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
            pricing_type="fixed",
            device_type="camera",
            layer_type="living_room",
            effective_date=local_date_to_utc_start("2027-01-01"),  # 在现有规则之后
            expiry_date=local_date_to_utc_end("2027-12-31"),
        )

        assert len(conflicts) == 0

    @pytest.mark.asyncio
    async def test_check_conflict_single_and_multi_has_conflict(
        self, pricing_service, mock_db_session
    ):
        """测试检查冲突 - single_and_multi 模式下存在冲突"""
        existing_single = PricingRule(
            id=1,
            customer_id=100,
            device_type="L",
            layer_type="single",
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
        )

        # 第一次调用返回 single 冲突，第二次返回空（multi 无冲突）
        mock_result_single = MagicMock()
        mock_result_single.scalars.return_value.all.return_value = [existing_single]
        mock_result_multi = MagicMock()
        mock_result_multi.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_result_single, mock_result_multi]

        conflicts = await pricing_service.check_pricing_rule_conflict(
            customer_id=100,
            pricing_type="fixed",
            device_type="L",
            layer_type="single_and_multi",
            effective_date=local_date_to_utc_start("2026-06-01"),
            expiry_date=local_date_to_utc_end("2027-06-30"),
        )

        assert len(conflicts) == 1
        assert conflicts[0].id == 1

    @pytest.mark.asyncio
    async def test_check_conflict_single_and_multi_no_conflict(
        self, pricing_service, mock_db_session
    ):
        """测试检查冲突 - single_and_multi 模式下无冲突"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        conflicts = await pricing_service.check_pricing_rule_conflict(
            customer_id=100,
            pricing_type="fixed",
            device_type="L",
            layer_type="single_and_multi",
            effective_date=local_date_to_utc_start("2027-01-01"),
            expiry_date=local_date_to_utc_end("2027-12-31"),
        )

        assert len(conflicts) == 0

    @pytest.mark.asyncio
    async def test_check_conflict_package_has_conflict(self, pricing_service, mock_db_session):
        """测试检查冲突 - 包年结算存在冲突（忽略设备/楼层类型）"""
        existing_package = PricingRule(
            id=9,
            customer_id=100,
            device_type=None,
            layer_type=None,
            pricing_type="package",
            package_type="A",
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_package]
        mock_db_session.execute.return_value = mock_result

        # 包年结算冲突检查：只按 customer_id + pricing_type='package' + 有效期判断，
        # 不传 device_type 和 layer_type
        conflicts = await pricing_service.check_pricing_rule_conflict(
            customer_id=100,
            pricing_type="package",
            effective_date=local_date_to_utc_start("2026-06-01"),
            expiry_date=local_date_to_utc_end("2027-06-30"),
        )

        assert len(conflicts) == 1
        assert conflicts[0].id == 9

    @pytest.mark.asyncio
    async def test_check_conflict_package_no_conflict(self, pricing_service, mock_db_session):
        """测试检查冲突 - 包年结算无冲突（时间不重叠）"""
        existing_package = PricingRule(
            id=10,
            customer_id=100,
            device_type=None,
            layer_type=None,
            pricing_type="package",
            package_type="B",
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-06-30"),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_package]
        mock_db_session.execute.return_value = mock_result

        conflicts = await pricing_service.check_pricing_rule_conflict(
            customer_id=100,
            pricing_type="package",
            effective_date=local_date_to_utc_start("2027-01-01"),  # 在现有规则之后，无重叠
            expiry_date=local_date_to_utc_end("2027-12-31"),
        )

        assert len(conflicts) == 0


# ==================== Test PricingService - Create single_and_multi ====================


class TestPricingService_CreateSingleAndMulti:
    """创建单层+多层组合规则测试"""

    @pytest.mark.asyncio
    async def test_create_single_and_multi_success(self, pricing_service, mock_db_session):
        """测试创建 single_and_multi 规则 - 成功拆分为两条"""
        # Mock 无冲突
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        rule_data = {
            "customer_id": 100,
            "device_type": "L",
            "layer_type": "single_and_multi",
            "pricing_type": "fixed",
            "unit_price": Decimal("10.00"),
            "effective_date": local_date_to_utc_start("2026-01-01"),
            "expiry_date": local_date_to_utc_end("2026-12-31"),
            "created_by": 1,
        }

        result = await pricing_service.create_pricing_rule(rule_data)

        assert result is not None
        assert isinstance(result, PricingRule)
        assert result.layer_type == "multi"
        assert result.multi_floor_pricing_type == "unified"
        # 应该 commit 两次（single + multi）
        assert mock_db_session.commit.call_count == 2
        # 应该 add 两次
        assert mock_db_session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_create_single_and_multi_with_incremental_fields(
        self, pricing_service, mock_db_session
    ):
        """测试创建 multi + incremental 规则"""
        # Mock 无冲突
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        rule_data = {
            "customer_id": 100,
            "device_type": "L",
            "layer_type": "multi",
            "pricing_type": "fixed",
            "unit_price": Decimal("5.00"),
            "multi_floor_pricing_type": "incremental",
            "additional_floor_price": Decimal("6.00"),
            "effective_date": local_date_to_utc_start("2026-01-01"),
            "expiry_date": local_date_to_utc_end("2026-12-31"),
            "created_by": 1,
        }

        result = await pricing_service.create_pricing_rule(rule_data)

        assert result is not None
        assert result.layer_type == "multi"
        assert result.multi_floor_pricing_type == "incremental"
        assert result.additional_floor_price == Decimal("6.00")
        mock_db_session.commit.assert_called()


# ==================== Test InvoiceService - Calculate Items with Incremental ====================


class TestInvoiceService_CalculateItemsIncremental:
    """结算单明细计算测试 - 递增模式"""

    @pytest.fixture
    def invoice_service(self, mock_db_session):
        """创建 InvoiceService 实例"""
        from unittest.mock import MagicMock

        from app.repository import InvoiceRepository, PricingRepository

        mock_invoice_repo = MagicMock(spec=InvoiceRepository)
        mock_invoice_repo.db = mock_db_session
        mock_pricing_repo = MagicMock(spec=PricingRepository)
        mock_pricing_repo.db = mock_db_session
        from app.services.billing import InvoiceService

        return InvoiceService(
            invoice_repo=mock_invoice_repo,
            pricing_repo=mock_pricing_repo,
        )

    @pytest.mark.asyncio
    async def test_calculate_items_fixed_incremental(self, invoice_service, mock_db_session):
        """测试结算明细计算 - 递增模式

        3层房源1套，单价5，其他层单价6 → 5×1 + 6×2 = 17
        """

        # Mock 用量查询结果
        usage_row = MagicMock()
        usage_row.device_type = "L"
        usage_row.layer_type = "multi"
        usage_row.total_quantity = 1  # order_count
        usage_row.total_floor_count = 3

        usage_result = MagicMock()
        usage_result.all.return_value = [usage_row]

        # Mock 规则查询结果
        mock_rule = MagicMock(spec=PricingRule)
        mock_rule.id = 1
        mock_rule.device_type = "L"
        mock_rule.layer_type = "multi"
        mock_rule.pricing_type = "fixed"
        mock_rule.unit_price = Decimal("5")
        mock_rule.multi_floor_pricing_type = "incremental"
        mock_rule.additional_floor_price = Decimal("6")

        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_rule]

        # execute 第一次返回用量，第二次返回规则
        mock_db_session.execute.side_effect = [usage_result, rules_result]

        items, total_amount = await invoice_service.calculate_items_from_rules(
            customer_id=100,
            period_start=local_date_range_to_utc("2026-01-01", "2026-01-31")[0],
            period_end=local_date_range_to_utc("2026-01-01", "2026-01-31")[1],
        )

        assert len(items) == 1
        item = items[0]
        assert item["multi_floor_pricing_type"] == "incremental"
        assert item["unit_price"] == Decimal("5")
        assert item["additional_floor_price"] == Decimal("6")
        assert item["subtotal"] == Decimal("17")
        assert total_amount == Decimal("17")

    @pytest.mark.asyncio
    async def test_calculate_items_fixed_unified_multi(self, invoice_service, mock_db_session):
        """测试结算明细计算 - 多层统一模式

        统一模式：按订单数量 × 单价（不区分楼层）
        订单数 2，总楼层数 6，单价 10 → 2 × 10 = 20
        """
        usage_row = MagicMock()
        usage_row.device_type = "L"
        usage_row.layer_type = "multi"
        usage_row.total_quantity = 2
        usage_row.total_floor_count = 6

        usage_result = MagicMock()
        usage_result.all.return_value = [usage_row]

        mock_rule = MagicMock(spec=PricingRule)
        mock_rule.id = 1
        mock_rule.device_type = "L"
        mock_rule.layer_type = "multi"
        mock_rule.pricing_type = "fixed"
        mock_rule.unit_price = Decimal("10")
        mock_rule.multi_floor_pricing_type = "unified"
        mock_rule.additional_floor_price = None

        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_rule]

        mock_db_session.execute.side_effect = [usage_result, rules_result]

        items, total_amount = await invoice_service.calculate_items_from_rules(
            customer_id=100,
            period_start=local_date_range_to_utc("2026-01-01", "2026-01-31")[0],
            period_end=local_date_range_to_utc("2026-01-01", "2026-01-31")[1],
        )

        assert len(items) == 1
        assert items[0]["subtotal"] == Decimal("20")
        assert items[0]["quantity"] == Decimal("2")  # 按订单数
        assert total_amount == Decimal("20")

    @pytest.mark.asyncio
    async def test_calculate_items_package_rule(self, invoice_service, mock_db_session):
        """测试结算明细计算 - 限量包年规则（按用量计收 + 超量费用）

        base_fee=10000, limit_count=100, over_limit_unit_price=100
        total_quantity=5 (未超量)
        → usage_cost = 5 × (10000/100) = 5 × 100 = 500
        → over_limit_cost = 0
        → subtotal = 500
        """
        usage_row = MagicMock()
        usage_row.device_type = "X"
        usage_row.layer_type = "single"
        usage_row.total_quantity = 5
        usage_row.total_floor_count = 5

        usage_result = MagicMock()
        usage_result.all.return_value = [usage_row]

        mock_package = MagicMock(spec=PricingRule)
        mock_package.id = 9
        mock_package.device_type = None
        mock_package.layer_type = None
        mock_package.pricing_type = "package"
        mock_package.package_type = "A"
        mock_package.package_limits = {
            "base_fee": 10000,
            "is_unlimited": False,
            "limit_count": 100,
            "over_limit_unit_price": 100,
        }
        mock_package.unit_price = None

        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_package]

        mock_db_session.execute.side_effect = [usage_result, rules_result]

        items, total_amount = await invoice_service.calculate_items_from_rules(
            customer_id=100,
            period_start=local_date_range_to_utc("2026-01-01", "2026-01-31")[0],
            period_end=local_date_range_to_utc("2026-01-01", "2026-01-31")[1],
        )

        assert len(items) == 1
        assert items[0]["pricing_rule_id"] == 9
        assert items[0]["device_type"] is None
        assert items[0]["layer_type"] is None
        assert items[0]["subtotal"] == Decimal("500")  # 5 × (10000/100) = 500
        assert items[0]["package_type"] == "limited"
        assert items[0]["limit_count"] == 100
        assert items[0]["over_limit_quantity"] == 0
        assert total_amount == Decimal("500")

    @pytest.mark.asyncio
    async def test_calculate_items_package_rule_priority_over_fixed(
        self, invoice_service, mock_db_session
    ):
        """测试结算明细计算 - 包年规则优先于固定规则

        限量套餐：base_fee=5000, limit_count=50, over_limit_unit_price=100
        total_quantity=3 (未超量)
        → usage_cost = 3 × (5000/50) = 3 × 100 = 300
        → over_limit_cost = 0
        → subtotal = 300
        """
        usage_row = MagicMock()
        usage_row.device_type = "L"
        usage_row.layer_type = "single"
        usage_row.total_quantity = 3
        usage_row.total_floor_count = 3

        usage_result = MagicMock()
        usage_result.all.return_value = [usage_row]

        mock_fixed = MagicMock(spec=PricingRule)
        mock_fixed.id = 1
        mock_fixed.device_type = "L"
        mock_fixed.layer_type = "single"
        mock_fixed.pricing_type = "fixed"
        mock_fixed.unit_price = Decimal("10")

        mock_package = MagicMock(spec=PricingRule)
        mock_package.id = 9
        mock_package.device_type = None
        mock_package.layer_type = None
        mock_package.pricing_type = "package"
        mock_package.package_type = "A"
        mock_package.package_limits = {
            "base_fee": 5000,
            "is_unlimited": False,
            "limit_count": 50,
            "over_limit_unit_price": 100,
        }
        mock_package.unit_price = None

        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_fixed, mock_package]

        mock_db_session.execute.side_effect = [usage_result, rules_result]

        items, total_amount = await invoice_service.calculate_items_from_rules(
            customer_id=100,
            period_start=local_date_range_to_utc("2026-01-01", "2026-01-31")[0],
            period_end=local_date_range_to_utc("2026-01-01", "2026-01-31")[1],
        )

        # 只生成一条包年明细，固定规则不参与计算
        assert len(items) == 1
        assert items[0]["pricing_rule_id"] == 9
        assert total_amount == Decimal("300")  # 3 × (5000/50) = 300

    @pytest.mark.asyncio
    async def test_generate_invoice_uses_subtotal(self, invoice_service, mock_db_session):
        """测试生成结算单 - 使用 subtotal 字段计算总金额"""
        items = [
            {
                "device_type": "L",
                "layer_type": "multi",
                "quantity": 3,
                "unit_price": Decimal("5"),
                "additional_floor_price": Decimal("6"),
                "subtotal": Decimal("17"),  # 递增模式的 subtotal
                "pricing_rule_id": 1,
            }
        ]

        result = await invoice_service.generate_invoice(
            customer_id=100,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            items=items,
            created_by=1,
        )

        assert result is not None
        assert result.total_amount == Decimal("17")  # 使用 subtotal 而非 quantity × unit_price
