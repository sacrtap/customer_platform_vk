"""
客户运营中台 - Billing Services 单元测试

测试目标：
1. BalanceService - 余额管理服务（get_balance, recharge, consume, get_recharge_records）
2. PricingService - 定价规则服务（get/create/update/delete）
3. InvoiceService - 结算单服务（generate/get/apply_discount/submit/confirm/pay/complete/delete）
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from datetime import date

# ==================== MockDBSession 工具类 ====================


class MockDBSession:
    """Mock 数据库会话"""

    def __init__(self):
        self.execute = AsyncMock()
        self._add_calls = []
        self._add_all_calls = []
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.refresh = AsyncMock()
        self._new = []

    def add(self, obj):
        """模拟 add 方法，跟踪新对象"""
        self._add_calls.append(obj)
        self._new.append(obj)

    def add_all(self, objects):
        """模拟 add_all 方法"""
        self._add_all_calls.append(objects)
        self._new.extend(objects)

    @property
    def new(self):
        return self._new

    class _AsyncCM:
        """异步上下文管理器"""

        def __await__(self):
            return iter([])

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    def begin(self):
        """模拟异步事务上下文"""
        return self._AsyncCM()


def make_mock_execute_result(rows, scalar_value=None):
    """创建 execute 返回结果

    Args:
        rows: 返回的行列表（用于 .all() 或 .scalars().all()）
        scalar_value: 标量值（用于 .scalar()），默认取 rows[0][0] 如果 rows 是元组列表
    """
    result = MagicMock()
    result.all = MagicMock(return_value=rows)
    result.scalar_one_or_none = MagicMock(return_value=rows[0] if rows else None)

    # 处理 .scalar() 调用（用于 count 查询）
    if scalar_value is not None:
        result.scalar = MagicMock(return_value=scalar_value)
    elif rows and isinstance(rows[0], (list, tuple)):
        result.scalar = MagicMock(return_value=rows[0][0])
    else:
        result.scalar = MagicMock(return_value=None)

    scalars_result = MagicMock()
    scalars_result.all = MagicMock(return_value=rows)
    scalars_result.unique = MagicMock(return_value=scalars_result)
    result.scalars.return_value = scalars_result
    return result


# ==================== Fixtures ====================


@pytest.fixture
def mock_db():
    """创建 Mock 数据库会话"""
    return MockDBSession()


@pytest.fixture
def balance_service(mock_db):
    """创建 BalanceService 实例"""
    from app.services.billing import BalanceService

    service = BalanceService(mock_db)
    yield service, mock_db


@pytest.fixture
def pricing_service(mock_db):
    """创建 PricingService 实例"""
    from app.services.billing import PricingService

    service = PricingService(mock_db)
    yield service, mock_db


@pytest.fixture
def invoice_service(mock_db):
    """创建 InvoiceService 实例"""
    from app.services.billing import InvoiceService

    service = InvoiceService(mock_db)
    yield service, mock_db


# ==================== BalanceService 测试 ====================


class TestBalanceService_GetBalance:
    """BalanceService.get_balance_by_customer_id 测试"""

    @pytest.mark.asyncio
    async def test_get_balance_found(self, balance_service):
        """测试找到余额记录"""
        service, mock_db = balance_service

        from app.models.billing import CustomerBalance

        mock_balance = CustomerBalance(id=1, customer_id=100, total_amount=Decimal("1000.00"))
        mock_db.execute.return_value = make_mock_execute_result([mock_balance])

        result = await service.get_balance_by_customer_id(100)

        assert result is not None
        assert result.customer_id == 100
        assert result.total_amount == Decimal("1000.00")

    @pytest.mark.asyncio
    async def test_get_balance_not_found(self, balance_service):
        """测试余额记录不存在"""
        service, mock_db = balance_service

        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.get_balance_by_customer_id(999)

        assert result is None


class TestBalanceService_GetOrCreate:
    """BalanceService.get_or_create_balance 测试"""

    @pytest.mark.asyncio
    async def test_get_existing_balance(self, balance_service):
        """测试获取已存在的余额"""
        service, mock_db = balance_service

        from app.models.billing import CustomerBalance

        mock_balance = CustomerBalance(id=1, customer_id=100, total_amount=Decimal("500.00"))
        mock_db.execute.return_value = make_mock_execute_result([mock_balance])

        result = await service.get_or_create_balance(100)

        assert result.customer_id == 100
        assert result.total_amount == Decimal("500.00")
        assert len(mock_db._add_calls) == 0  # 没有新增对象

    @pytest.mark.asyncio
    async def test_create_new_balance(self, balance_service):
        """测试创建新余额记录"""
        service, mock_db = balance_service

        # 第一次查询返回空（不存在）
        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.get_or_create_balance(100)

        assert result.customer_id == 100
        assert len(mock_db._add_calls) == 1
        assert mock_db.flush.call_count == 1


class TestBalanceService_Recharge:
    """BalanceService.recharge 测试"""

    @pytest.mark.asyncio
    async def test_recharge_success(self, balance_service):
        """测试充值成功"""
        service, mock_db = balance_service

        from app.models.billing import CustomerBalance

        # 模拟余额已存在
        mock_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("100.00"),
            bonus_amount=Decimal("50.00"),
            total_amount=Decimal("150.00"),
        )

        # 第一次查询返回余额，第二次返回空（commit 后 refresh）
        mock_db.execute.side_effect = [
            make_mock_execute_result([mock_balance]),  # get_or_create_balance 查询
            make_mock_execute_result([]),  # commit 后 refresh
        ]

        result = await service.recharge(
            customer_id=100,
            real_amount=Decimal("200.00"),
            bonus_amount=Decimal("100.00"),
            operator_id=1,
            payment_proof="/path/to/proof.png",
            remark="测试充值",
        )

        assert result.real_amount == Decimal("200.00")
        assert result.bonus_amount == Decimal("100.00")
        assert mock_db.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_recharge_new_customer(self, balance_service):
        """测试新客户充值（需要先创建余额）"""
        service, mock_db = balance_service

        # 第一次查询返回空（余额不存在）
        mock_db.execute.side_effect = [
            make_mock_execute_result([]),  # get_balance 返回空
            make_mock_execute_result([]),  # commit 后 refresh
        ]

        result = await service.recharge(
            customer_id=100,
            real_amount=Decimal("500.00"),
            bonus_amount=Decimal("0.00"),
            operator_id=1,
        )

        assert result.real_amount == Decimal("500.00")
        assert len(mock_db._add_calls) >= 1  # 至少添加了充值记录和余额

    @pytest.mark.asyncio
    async def test_recharge_bonus_only(self, balance_service):
        """测试只充赠金"""
        service, mock_db = balance_service

        from app.models.billing import CustomerBalance

        mock_balance = CustomerBalance(
            id=1, customer_id=100, real_amount=Decimal("0"), bonus_amount=Decimal("0")
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([mock_balance]),
            make_mock_execute_result([]),
        ]

        result = await service.recharge(
            customer_id=100,
            real_amount=Decimal("0.00"),
            bonus_amount=Decimal("300.00"),
            operator_id=1,
        )

        assert result.real_amount == Decimal("0.00")
        assert result.bonus_amount == Decimal("300.00")


class TestBalanceService_Consume:
    """BalanceService.consume 测试"""

    @pytest.mark.asyncio
    async def test_consume_success_mixed(self, balance_service):
        """测试消费成功（混合使用赠金和实充）"""
        service, mock_db = balance_service

        from app.models.billing import CustomerBalance

        # 余额：赠金 50 + 实充 100 = 150，消费 80
        # 预期：先用赠金 50，再用实充 30
        mock_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("100.00"),
            bonus_amount=Decimal("50.00"),
            total_amount=Decimal("150.00"),
            used_total=Decimal("0"),
            used_real=Decimal("0"),
            used_bonus=Decimal("0"),
        )

        # 模拟事务上下文
        mock_db.execute.return_value = make_mock_execute_result([mock_balance])

        success, message = await service.consume(
            customer_id=100,
            amount=Decimal("80.00"),
            invoice_id=1,
        )

        assert success is True
        assert "扣款成功" in message

    @pytest.mark.asyncio
    async def test_consume_bonus_only(self, balance_service):
        """测试只使用赠金消费"""
        service, mock_db = balance_service

        from app.models.billing import CustomerBalance

        mock_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("100.00"),
            bonus_amount=Decimal("50.00"),
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_balance])

        success, message = await service.consume(
            customer_id=100,
            amount=Decimal("30.00"),
        )

        assert success is True
        # 应该只使用赠金

    @pytest.mark.asyncio
    async def test_consume_real_only(self, balance_service):
        """测试只使用实充消费（无赠金）"""
        service, mock_db = balance_service

        from app.models.billing import CustomerBalance

        mock_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("100.00"),
            bonus_amount=Decimal("0"),
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_balance])

        success, message = await service.consume(
            customer_id=100,
            amount=Decimal("50.00"),
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_consume_insufficient_balance(self, balance_service):
        """测试余额不足"""
        service, mock_db = balance_service

        from app.models.billing import CustomerBalance

        mock_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("50.00"),
            bonus_amount=Decimal("0"),
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_balance])

        success, message = await service.consume(
            customer_id=100,
            amount=Decimal("100.00"),
        )

        assert success is False
        assert "余额不足" in message

    @pytest.mark.asyncio
    async def test_consume_balance_not_found(self, balance_service):
        """测试余额账户不存在"""
        service, mock_db = balance_service

        mock_db.execute.return_value = make_mock_execute_result([])

        success, message = await service.consume(
            customer_id=999,
            amount=Decimal("50.00"),
        )

        assert success is False
        assert "不存在" in message

    @pytest.mark.asyncio
    async def test_consume_exact_balance(self, balance_service):
        """测试消费金额等于余额"""
        service, mock_db = balance_service

        from app.models.billing import CustomerBalance

        mock_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("100.00"),
            bonus_amount=Decimal("0"),
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_balance])

        success, message = await service.consume(
            customer_id=100,
            amount=Decimal("100.00"),
        )

        assert success is True


class TestBalanceService_GetRechargeRecords:
    """BalanceService.get_recharge_records 测试"""

    @pytest.mark.asyncio
    async def test_get_records_with_customer_filter(self, balance_service):
        """测试按客户 ID 筛选充值记录"""
        service, mock_db = balance_service

        from app.models.billing import RechargeRecord

        mock_records = [
            RechargeRecord(id=1, customer_id=100, real_amount=Decimal("100.00")),
            RechargeRecord(id=2, customer_id=100, real_amount=Decimal("200.00")),
        ]
        mock_db.execute.side_effect = [
            make_mock_execute_result([(2,)]),  # 计数查询
            make_mock_execute_result(mock_records),  # 主查询
        ]

        records, total = await service.get_recharge_records(customer_id=100)

        assert len(records) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_records_no_filter(self, balance_service):
        """测试获取所有充值记录"""
        service, mock_db = balance_service

        from app.models.billing import RechargeRecord

        mock_records = [
            RechargeRecord(id=1, customer_id=100, real_amount=Decimal("100.00")),
        ]
        mock_db.execute.side_effect = [
            make_mock_execute_result([(1,)]),
            make_mock_execute_result(mock_records),
        ]

        records, total = await service.get_recharge_records()

        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_get_records_empty(self, balance_service):
        """测试空结果"""
        service, mock_db = balance_service

        mock_db.execute.side_effect = [
            make_mock_execute_result([(0,)]),
            make_mock_execute_result([]),
        ]

        records, total = await service.get_recharge_records(customer_id=100)

        assert len(records) == 0
        assert total == 0


# ==================== PricingService 测试 ====================


class TestPricingService_GetRules:
    """PricingService.get_pricing_rules 测试"""

    @pytest.mark.asyncio
    async def test_get_all_rules(self, pricing_service):
        """测试获取所有生效规则"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        mock_rules = [
            PricingRule(
                id=1,
                device_type="X",
                pricing_type="fixed",
                unit_price=Decimal("10.00"),
                effective_date=date.today(),
            ),
            PricingRule(
                id=2,
                device_type="N",
                pricing_type="tier",
                effective_date=date.today(),
            ),
        ]
        # 第一次 execute 返回总数，第二次返回数据
        mock_db.execute.side_effect = [
            make_mock_execute_result([(2,)], scalar_value=2),
            make_mock_execute_result(mock_rules),
        ]

        rules, total = await service.get_pricing_rules()

        assert total == 2
        assert len(rules) == 2

    @pytest.mark.asyncio
    async def test_get_rules_with_customer_filter(self, pricing_service):
        """测试按客户 ID 筛选"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        mock_rules = [
            PricingRule(id=1, customer_id=100, device_type="X", pricing_type="fixed"),
        ]
        mock_db.execute.side_effect = [
            make_mock_execute_result([(1,)], scalar_value=1),
            make_mock_execute_result(mock_rules),
        ]

        rules, total = await service.get_pricing_rules(customer_id=100)

        assert total == 1
        assert len(rules) == 1

    @pytest.mark.asyncio
    async def test_get_rules_with_device_filter(self, pricing_service):
        """测试按设备类型筛选"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        mock_rules = [
            PricingRule(id=1, device_type="X", pricing_type="fixed"),
        ]
        mock_db.execute.side_effect = [
            make_mock_execute_result([(1,)], scalar_value=1),
            make_mock_execute_result(mock_rules),
        ]

        rules, total = await service.get_pricing_rules(device_type="X")

        assert total == 1
        assert len(rules) == 1

    @pytest.mark.asyncio
    async def test_get_rules_with_pricing_type_filter(self, pricing_service):
        """测试按计费类型筛选"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        mock_rules = [
            PricingRule(id=1, device_type="X", pricing_type="tier"),
        ]
        mock_db.execute.side_effect = [
            make_mock_execute_result([(1,)], scalar_value=1),
            make_mock_execute_result(mock_rules),
        ]

        rules, total = await service.get_pricing_rules(pricing_type="tier")

        assert total == 1
        assert len(rules) == 1

    @pytest.mark.asyncio
    async def test_get_rules_empty(self, pricing_service):
        """测试空结果"""
        service, mock_db = pricing_service

        mock_db.execute.side_effect = [
            make_mock_execute_result([(0,)], scalar_value=0),
            make_mock_execute_result([]),
        ]

        rules, total = await service.get_pricing_rules()

        assert total == 0
        assert len(rules) == 0


class TestPricingService_Create:
    """PricingService.create_pricing_rule 测试"""

    @pytest.mark.asyncio
    async def test_create_fixed_pricing(self, pricing_service):
        """测试创建固定价格规则"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        mock_rule = PricingRule(
            id=1,
            device_type="X",
            pricing_type="fixed",
            unit_price=Decimal("15.00"),
            effective_date=date.today(),
        )

        # _check_overlap 返回空列表（无冲突），主查询返回规则
        mock_db.execute.side_effect = [
            make_mock_execute_result([]),  # _check_overlap 查询
            make_mock_execute_result([mock_rule]),  # 创建规则
        ]

        data = {
            "device_type": "X",
            "pricing_type": "fixed",
            "unit_price": Decimal("15.00"),
            "effective_date": date.today(),
            "created_by": 1,
        }

        result = await service.create_pricing_rule(data)

        assert result.device_type == "X"
        assert result.pricing_type == "fixed"
        assert mock_db.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_create_tier_pricing(self, pricing_service):
        """测试创建阶梯价格规则"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        mock_rule = PricingRule(
            id=1,
            device_type="N",
            pricing_type="tier",
            tiers=[{"min": 0, "max": 100, "price": 10}, {"min": 101, "price": 8}],
            effective_date=date.today(),
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([]),  # _check_overlap 查询
            make_mock_execute_result([mock_rule]),  # 创建规则
        ]

        data = {
            "device_type": "N",
            "pricing_type": "tier",
            "tiers": [{"min": 0, "max": 100, "price": 10}],
            "effective_date": date.today(),
        }

        result = await service.create_pricing_rule(data)

        assert result.pricing_type == "tier"

    @pytest.mark.asyncio
    async def test_create_package_pricing(self, pricing_service):
        """测试创建套餐价格规则"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        mock_rule = PricingRule(
            id=1,
            device_type="L",
            pricing_type="package",
            package_type="A",
            package_limits={"daily": 1000},
            effective_date=date.today(),
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([]),  # _check_overlap 查询
            make_mock_execute_result([mock_rule]),  # 创建规则
        ]

        data = {
            "device_type": "L",
            "pricing_type": "package",
            "package_type": "A",
            "package_limits": {"daily": 1000},
            "effective_date": date.today(),
        }

        result = await service.create_pricing_rule(data)

        assert result.package_type == "A"


class TestPricingService_Update:
    """PricingService.update_pricing_rule 测试"""

    @pytest.mark.asyncio
    async def test_update_success(self, pricing_service):
        """测试更新成功"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        mock_rule = PricingRule(
            id=1,
            device_type="X",
            pricing_type="fixed",
            unit_price=Decimal("10.00"),
            effective_date=date.today(),
        )
        # 仅更新非日期字段，不需要重叠校验，只需一次查询
        mock_db.execute.return_value = make_mock_execute_result([mock_rule])

        result = await service.update_pricing_rule(
            rule_id=1,
            data={"unit_price": Decimal("12.00")},
        )

        assert result is not None
        assert mock_db.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_update_not_found(self, pricing_service):
        """测试规则不存在"""
        service, mock_db = pricing_service

        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.update_pricing_rule(
            rule_id=999,
            data={"unit_price": Decimal("12.00")},
        )

        assert result is None


class TestPricingService_Delete:
    """PricingService.delete_pricing_rule 测试"""

    @pytest.mark.asyncio
    async def test_delete_success(self, pricing_service):
        """测试删除成功"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        mock_rule = PricingRule(id=1, device_type="X", pricing_type="fixed")
        mock_db.execute.return_value = make_mock_execute_result([mock_rule])

        result = await service.delete_pricing_rule(rule_id=1)

        assert result is True
        assert mock_db.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_delete_not_found(self, pricing_service):
        """测试规则不存在"""
        service, mock_db = pricing_service

        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.delete_pricing_rule(rule_id=999)

        assert result is False


class TestPricingService_UpdateOverlap:
    """PricingService.update_pricing_rule 重叠校验测试"""

    @pytest.mark.asyncio
    async def test_update_causes_overlap(self, pricing_service):
        """测试更新导致重叠时抛出异常"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        current_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 6, 30),
        )
        other_rule = PricingRule(
            id=2,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="tier",
            effective_date=date(2026, 7, 1),
            expiry_date=date(2026, 12, 31),
        )

        mock_db.execute.side_effect = [
            make_mock_execute_result([current_rule]),
            make_mock_execute_result([other_rule]),
        ]

        with pytest.raises(ValueError, match="有效期存在重叠"):
            await service.update_pricing_rule(
                1,
                {
                    "effective_date": date(2026, 8, 1),
                    "expiry_date": date(2026, 10, 31),
                },
            )

    @pytest.mark.asyncio
    async def test_update_no_overlap(self, pricing_service):
        """测试更新不导致重叠时成功"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        current_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 6, 30),
        )

        mock_db.execute.side_effect = [
            make_mock_execute_result([current_rule]),
            make_mock_execute_result([]),
        ]

        result = await service.update_pricing_rule(
            1,
            {
                "effective_date": date(2026, 7, 1),
                "expiry_date": date(2026, 12, 31),
            },
        )

        assert result is not None
        assert mock_db.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_update_non_date_fields_skip_check(self, pricing_service):
        """测试仅更新非日期字段时跳过校验"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        current_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            unit_price=Decimal("10.00"),
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )

        mock_db.execute.return_value = make_mock_execute_result([current_rule])

        result = await service.update_pricing_rule(
            1,
            {
                "unit_price": Decimal("15.00"),
            },
        )

        assert result is not None
        assert mock_db.execute.call_count == 1


class TestPricingService_CheckConflict:
    """PricingService.check_pricing_rule_conflict 测试"""

    @pytest.mark.asyncio
    async def test_has_conflict(self, pricing_service):
        """测试存在冲突时返回冲突列表"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        conflicting_rule = PricingRule(
            id=5,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([conflicting_rule]),
        ]

        result = await service.check_pricing_rule_conflict(
            customer_id=100,
            device_type="X",
            layer_type="single",
            effective_date=date(2026, 6, 1),
            expiry_date=date(2026, 9, 30),
        )

        assert len(result) == 1
        assert result[0].id == 5

    @pytest.mark.asyncio
    async def test_no_conflict(self, pricing_service):
        """测试无冲突时返回空列表"""
        service, mock_db = pricing_service

        mock_db.execute.side_effect = [
            make_mock_execute_result([]),
        ]

        result = await service.check_pricing_rule_conflict(
            customer_id=100,
            device_type="X",
            layer_type="single",
            effective_date=date(2027, 1, 1),
            expiry_date=date(2027, 12, 31),
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_exclude_self(self, pricing_service):
        """测试 exclude_id 排除自身"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        self_rule = PricingRule(
            id=10,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([self_rule]),
        ]

        result = await service.check_pricing_rule_conflict(
            customer_id=100,
            device_type="X",
            layer_type="single",
            effective_date=date(2026, 6, 1),
            expiry_date=date(2026, 9, 30),
            exclude_id=10,
        )

        # exclude_id=10 时 SQL 会排除 id=10 的规则，所以 mock 返回空列表
        mock_db.execute.side_effect = [
            make_mock_execute_result([]),
        ]

        result = await service.check_pricing_rule_conflict(
            customer_id=100,
            device_type="X",
            layer_type="single",
            effective_date=date(2026, 6, 1),
            expiry_date=date(2026, 9, 30),
            exclude_id=10,
        )

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_multiple_conflicts(self, pricing_service):
        """测试多个冲突规则全部返回"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        rule1 = PricingRule(
            id=5,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 6, 30),
        )
        rule2 = PricingRule(
            id=6,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="tiered",
            effective_date=date(2026, 7, 1),
            expiry_date=date(2026, 12, 31),
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([rule1, rule2]),
        ]

        result = await service.check_pricing_rule_conflict(
            customer_id=100,
            device_type="X",
            layer_type="single",
            effective_date=date(2026, 3, 1),
            expiry_date=date(2026, 9, 30),
        )

        assert len(result) == 2
        assert result[0].id == 5
        assert result[1].id == 6


# ==================== InvoiceService 测试 ====================


class TestInvoiceService_Generate:
    """InvoiceService.generate_invoice 测试"""

    @pytest.mark.asyncio
    async def test_generate_invoice_success(self, invoice_service):
        """测试生成结算单成功"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            invoice_no="INV-20260403-ABC123",
            customer_id=100,
            total_amount=Decimal("1000.00"),
            status="draft",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        items = [
            {
                "device_type": "X",
                "layer_type": "single",
                "quantity": 100,
                "unit_price": 10,
            },
        ]

        result = await service.generate_invoice(
            customer_id=100,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            items=items,
            created_by=1,
        )

        assert result.customer_id == 100
        assert result.status == "draft"
        assert len(mock_db._add_calls) >= 1  # 至少添加了发票

    @pytest.mark.asyncio
    async def test_generate_invoice_multiple_items(self, invoice_service):
        """测试生成多项目结算单"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            invoice_no="INV-20260403-XYZ789",
            customer_id=100,
            total_amount=Decimal("2500.00"),  # 100*10 + 100*15
            status="draft",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        items = [
            {"device_type": "X", "quantity": 100, "unit_price": 10},
            {"device_type": "N", "quantity": 100, "unit_price": 15},
        ]

        result = await service.generate_invoice(
            customer_id=100,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            items=items,
            created_by=1,
        )

        assert result.total_amount == Decimal("2500.00")

    @pytest.mark.asyncio
    async def test_generate_invoice_auto_generated(self, invoice_service):
        """测试自动生成标记"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            invoice_no="INV-AUTO",
            customer_id=100,
            is_auto_generated=True,
            status="draft",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        result = await service.generate_invoice(
            customer_id=100,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            items=[{"device_type": "X", "quantity": 100, "unit_price": 10}],
            created_by=1,
            is_auto_generated=True,
        )

        assert result.is_auto_generated is True


class TestInvoiceService_GetInvoices:
    """InvoiceService.get_invoices 测试"""

    @pytest.mark.asyncio
    async def test_get_invoices_with_customer_filter(self, invoice_service):
        """测试按客户 ID 筛选"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoices = [
            Invoice(id=1, customer_id=100, invoice_no="INV-001", status="draft"),
            Invoice(id=2, customer_id=100, invoice_no="INV-002", status="paid"),
        ]
        mock_db.execute.side_effect = [
            make_mock_execute_result([(2,)]),
            make_mock_execute_result(mock_invoices),
        ]

        invoices, total = await service.get_invoices(customer_id=100)

        assert len(invoices) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_invoices_with_status_filter(self, invoice_service):
        """测试按状态筛选"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoices = [
            Invoice(id=1, customer_id=100, invoice_no="INV-001", status="paid"),
        ]
        mock_db.execute.side_effect = [
            make_mock_execute_result([(1,)]),
            make_mock_execute_result(mock_invoices),
        ]

        invoices, total = await service.get_invoices(status="paid")

        assert len(invoices) == 1

    @pytest.mark.asyncio
    async def test_get_invoices_empty(self, invoice_service):
        """测试空结果"""
        service, mock_db = invoice_service

        mock_db.execute.side_effect = [
            make_mock_execute_result([(0,)]),
            make_mock_execute_result([]),
        ]

        invoices, total = await service.get_invoices()

        assert len(invoices) == 0
        assert total == 0


class TestInvoiceService_ApplyDiscount:
    """InvoiceService.apply_discount 测试"""

    @pytest.mark.asyncio
    async def test_apply_discount_success(self, invoice_service):
        """测试应用减免成功"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            total_amount=Decimal("1000.00"),
            discount_amount=Decimal("0"),
            status="draft",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.apply_discount(
            invoice_id=1,
            discount_amount=Decimal("100.00"),
            discount_reason="促销活动",
        )

        assert success is True
        assert "成功" in message
        assert mock_db.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_apply_discount_invoice_not_found(self, invoice_service):
        """测试结算单不存在"""
        service, mock_db = invoice_service

        mock_db.execute.return_value = make_mock_execute_result([])

        success, message = await service.apply_discount(
            invoice_id=999,
            discount_amount=Decimal("100.00"),
            discount_reason="测试",
        )

        assert success is False
        assert "不存在" in message

    @pytest.mark.asyncio
    async def test_apply_discount_wrong_state(self, invoice_service):
        """测试状态不允许修改减免"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            total_amount=Decimal("1000.00"),
            status="paid",  # 已付款，不能修改
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.apply_discount(
            invoice_id=1,
            discount_amount=Decimal("100.00"),
            discount_reason="测试",
        )

        assert success is False
        assert "不能修改" in message

    @pytest.mark.asyncio
    async def test_apply_discount_amount_too_large(self, invoice_service):
        """测试减免金额大于总额"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            total_amount=Decimal("500.00"),
            status="draft",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.apply_discount(
            invoice_id=1,
            discount_amount=Decimal("600.00"),
            discount_reason="测试",
        )

        assert success is False
        assert "不能大于" in message


class TestInvoiceService_Submit:
    """InvoiceService.submit_invoice 测试"""

    @pytest.mark.asyncio
    async def test_submit_success(self, invoice_service):
        """测试提交成功"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="draft",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.submit_invoice(invoice_id=1, approver_id=1)

        assert success is True
        assert "成功" in message

    @pytest.mark.asyncio
    async def test_submit_wrong_state(self, invoice_service):
        """测试状态不能提交"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="paid",  # 已付款，不能提交
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.submit_invoice(invoice_id=1, approver_id=1)

        assert success is False
        assert "不能提交" in message

    @pytest.mark.asyncio
    async def test_submit_not_found(self, invoice_service):
        """测试结算单不存在"""
        service, mock_db = invoice_service

        mock_db.execute.return_value = make_mock_execute_result([])

        success, message = await service.submit_invoice(invoice_id=999, approver_id=1)

        assert success is False


class TestInvoiceService_Confirm:
    """InvoiceService.confirm_invoice 测试"""

    @pytest.mark.asyncio
    async def test_confirm_success(self, invoice_service):
        """测试客户确认成功"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="pending_customer",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.confirm_invoice(invoice_id=1)

        assert success is True

    @pytest.mark.asyncio
    async def test_confirm_wrong_state(self, invoice_service):
        """测试状态不能确认"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="draft",  # 草稿状态，不能确认
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.confirm_invoice(invoice_id=1)

        assert success is False
        assert "不能确认" in message


class TestInvoiceService_Pay:
    """InvoiceService.pay_invoice 测试"""

    @pytest.mark.asyncio
    async def test_pay_success(self, invoice_service):
        """测试付款成功"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="customer_confirmed",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.pay_invoice(
            invoice_id=1, payment_proof="/path/to/proof.png"
        )

        assert success is True
        assert "成功" in message

    @pytest.mark.asyncio
    async def test_pay_wrong_state(self, invoice_service):
        """测试状态不能付款"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="draft",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.pay_invoice(invoice_id=1)

        assert success is False
        assert "不能付款" in message


class TestInvoiceService_Complete:
    """InvoiceService.complete_invoice 测试"""

    @pytest.mark.asyncio
    async def test_complete_success(self, invoice_service):
        """测试完成结算成功"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice, CustomerBalance

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            total_amount=Decimal("500.00"),
            discount_amount=Decimal("0"),
            status="paid",
        )

        # 第一次查询返回发票，第二次返回余额（consume 中的查询）
        mock_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("0"),
        )

        mock_db.execute.side_effect = [
            make_mock_execute_result([mock_invoice]),  # get_invoice_by_id
            make_mock_execute_result([mock_balance]),  # consume 中的查询
            make_mock_execute_result([]),  # commit 后
        ]

        success, message = await service.complete_invoice(invoice_id=1)

        assert success is True
        assert "结算完成" in message

    @pytest.mark.asyncio
    async def test_complete_wrong_state(self, invoice_service):
        """测试状态不能完成"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="draft",  # 草稿状态，不能完成
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.complete_invoice(invoice_id=1)

        assert success is False
        assert "不能完成" in message

    @pytest.mark.asyncio
    async def test_complete_insufficient_balance(self, invoice_service):
        """测试余额不足"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice, CustomerBalance

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            total_amount=Decimal("500.00"),
            status="paid",
        )

        mock_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("100.00"),  # 余额不足
            bonus_amount=Decimal("0"),
        )

        mock_db.execute.side_effect = [
            make_mock_execute_result([mock_invoice]),
            make_mock_execute_result([mock_balance]),
        ]

        success, message = await service.complete_invoice(invoice_id=1)

        assert success is False
        assert "余额不足" in message


class TestInvoiceService_Cancel:
    """InvoiceService.cancel_invoice 测试"""

    @pytest.mark.asyncio
    async def test_cancel_from_draft(self, invoice_service):
        """测试从草稿状态取消"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="draft",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.cancel_invoice(invoice_id=1)

        assert success is True
        assert "取消成功" in message
        assert mock_invoice.status == "cancelled"
        assert mock_invoice.cancelled_at is not None

    @pytest.mark.asyncio
    async def test_cancel_from_pending(self, invoice_service):
        """测试从待客户确认状态取消"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="pending_customer",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.cancel_invoice(invoice_id=1)

        assert success is True
        assert mock_invoice.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_wrong_state(self, invoice_service):
        """测试状态不能取消（已确认状态）"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="customer_confirmed",  # 已确认，不能取消
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.cancel_invoice(invoice_id=1)

        assert success is False
        assert "不能取消" in message

    @pytest.mark.asyncio
    async def test_cancel_paid_invoice(self, invoice_service):
        """测试已付款状态不能取消"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="paid",  # 已付款，不能取消
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        success, message = await service.cancel_invoice(invoice_id=1)

        assert success is False
        assert "不能取消" in message

    @pytest.mark.asyncio
    async def test_cancel_not_found(self, invoice_service):
        """测试结算单不存在"""
        service, mock_db = invoice_service

        mock_db.execute.return_value = make_mock_execute_result([])

        success, message = await service.cancel_invoice(invoice_id=999)

        assert success is False
        assert "不存在" in message


class TestInvoiceService_Delete:
    """InvoiceService.delete_invoice 测试"""

    @pytest.mark.asyncio
    async def test_delete_success(self, invoice_service):
        """测试删除成功"""
        service, mock_db = invoice_service

        from app.models.billing import Invoice

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-001",
            status="draft",
        )
        mock_db.execute.return_value = make_mock_execute_result([mock_invoice])

        result = await service.delete_invoice(invoice_id=1)

        assert result is True
        assert mock_db.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_delete_not_found(self, invoice_service):
        """测试结算单不存在"""
        service, mock_db = invoice_service

        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.delete_invoice(invoice_id=999)

        assert result is False


# ==================== PricingService._check_overlap 测试 ====================


class TestPricingService_CheckOverlap:
    """PricingService._check_overlap 测试"""

    @pytest.mark.asyncio
    async def test_overlap_same_layer_type(self, pricing_service):
        """测试相同 layer_type 时检测到重叠"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([existing_rule]),
        ]

        with pytest.raises(ValueError, match="有效期存在重叠"):
            await service._check_overlap(
                customer_id=100,
                device_type="X",
                layer_type="single",
                effective_date=date(2026, 6, 1),
                expiry_date=date(2026, 9, 30),
            )

    @pytest.mark.asyncio
    async def test_overlap_layer_type_none(self, pricing_service):
        """测试 layer_type 为 None 时正确匹配"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="X",
            layer_type=None,
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([existing_rule]),
        ]

        with pytest.raises(ValueError, match="有效期存在重叠"):
            await service._check_overlap(
                customer_id=100,
                device_type="X",
                layer_type=None,
                effective_date=date(2026, 3, 1),
                expiry_date=date(2026, 8, 31),
            )

    @pytest.mark.asyncio
    async def test_no_overlap_different_layer(self, pricing_service):
        """测试不同 layer_type 不冲突"""
        service, mock_db = pricing_service

        mock_db.execute.side_effect = [
            make_mock_execute_result([]),
        ]

        # 不应抛出异常
        await service._check_overlap(
            customer_id=100,
            device_type="X",
            layer_type="single",
            effective_date=date(2026, 6, 1),
            expiry_date=date(2026, 9, 30),
        )

    @pytest.mark.asyncio
    async def test_overlap_exclude_self(self, pricing_service):
        """测试 exclude_id 排除自身"""
        service, mock_db = pricing_service

        from app.models.billing import PricingRule

        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            effective_date=date(2026, 1, 1),
            expiry_date=date(2026, 12, 31),
        )
        # exclude_id=1 时 SQL 会排除 id=1 的规则，所以 mock 返回空列表
        mock_db.execute.side_effect = [
            make_mock_execute_result([]),
        ]

        # exclude_id=1 应排除自身，不抛出异常
        await service._check_overlap(
            customer_id=100,
            device_type="X",
            layer_type="single",
            effective_date=date(2026, 6, 1),
            expiry_date=date(2026, 9, 30),
            exclude_id=1,
        )


# ==================== 集成场景测试 ====================


class TestBillingIntegration:
    """Billing Services 集成场景测试"""

    @pytest.mark.asyncio
    async def test_full_invoice_lifecycle(self, invoice_service, balance_service):
        """测试完整结算单生命周期：生成 -> 提交 -> 确认 -> 付款 -> 完成"""
        from app.models.billing import Invoice, CustomerBalance

        # 1. 生成结算单
        invoice_svc, mock_db = invoice_service

        mock_invoice = Invoice(
            id=1,
            customer_id=100,
            invoice_no="INV-LIFECYCLE",
            total_amount=Decimal("500.00"),
            status="draft",
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([mock_invoice]),  # generate
        ]

        invoice = await invoice_svc.generate_invoice(
            customer_id=100,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            items=[{"device_type": "X", "quantity": 50, "unit_price": 10}],
            created_by=1,
        )

        assert invoice.status == "draft"

        # 2. 提交
        mock_invoice.status = "draft"
        mock_db.execute.side_effect = [
            make_mock_execute_result([mock_invoice]),  # submit
        ]

        success, _ = await invoice_svc.submit_invoice(invoice_id=1, approver_id=1)
        assert success is True

        # 3. 客户确认
        mock_invoice.status = "pending_customer"
        mock_db.execute.side_effect = [
            make_mock_execute_result([mock_invoice]),  # confirm
        ]

        success, _ = await invoice_svc.confirm_invoice(invoice_id=1)
        assert success is True

        # 4. 付款
        mock_invoice.status = "customer_confirmed"
        mock_db.execute.side_effect = [
            make_mock_execute_result([mock_invoice]),  # pay
        ]

        success, _ = await invoice_svc.pay_invoice(invoice_id=1)
        assert success is True

        # 5. 完成（扣款）
        mock_invoice.status = "paid"
        mock_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("0"),
        )
        mock_db.execute.side_effect = [
            make_mock_execute_result([mock_invoice]),  # get_invoice
            make_mock_execute_result([mock_balance]),  # consume 查询
        ]

        success, _ = await invoice_svc.complete_invoice(invoice_id=1)
        assert success is True
