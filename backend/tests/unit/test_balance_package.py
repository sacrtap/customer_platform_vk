"""包年套餐余额显示 — 单元测试（无 DB）

覆盖范围:
- `_compute_burn_down`: 有效包年（到期天数）/ 无到期日 / 过期包年（0 天）分支，
  以及非包年客户行为不受影响
- `_assemble_balance_rows`: 包年字段输出、total_amount 覆盖规则、无 CustomerBalance 行客户
- `_batch_query_package_info`: mock PricingRule + DailyConsumption，验证剩余额度/次数计算与过期判断

真实 SQL 结果正确性由集成测试（tests/integration/test_billing_api.py）验证。
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time

from app.routes.billing.balances import (
    _assemble_balance_rows,
    _batch_query_package_info,
    _compute_burn_down,
)

CST = timezone(timedelta(hours=8))

# 冻结基准时刻：CST 2026-10-22 12:00:00（= UTC 04:00，同一天的白天，
# 远离 CST/UTC 的日期边界）。不依赖真实时钟，测试在任何运行时刻都确定。
# 选 UTC 04:00 而非 UTC 20:00：CI 在 UTC 20 点运行时，真实 now() 转 CST 已是
# 次日——那正是本次修复的 bug 场景，测试必须能在该时刻复现旧代码的失败。
FROZEN_AT = "2026-10-22 04:00:00"


def _utcnow() -> datetime:
    """冻结时刻对应的 UTC datetime（替代 datetime.now(timezone.utc)）。"""
    return datetime(2026, 10, 22, 4, 0, 0, tzinfo=timezone.utc)


def _package_info(**overrides) -> dict:
    """构造 _batch_query_package_info 形态的 package_info"""
    info = {
        "is_expired": False,
        "base_fee": 120000.0,
        "is_unlimited": False,
        "limit_count": 1200.0,
        "remaining_amount": 90000.0,
        "remaining_count": 900.0,
        "consumed_amount": 30000.0,
        "expiry_date": _utcnow() + timedelta(days=200),
        "effective_date": _utcnow() - timedelta(days=160),
    }
    info.update(overrides)
    return info


def _customer(**overrides) -> SimpleNamespace:
    """构造 Customer ORM 形态（含 balance/profile），默认无 CustomerBalance 行"""
    cust = SimpleNamespace(
        id=1,
        company_id=1001,
        name="包年客户",
        account_type="enterprise",
        settlement_type=None,
        is_key_customer=False,
        price_policy="yearly",
        balance=None,
        profile=None,
    )
    for key, value in overrides.items():
        setattr(cust, key, value)
    return cust


# ────────────────────────────────────────────────────────────
# _compute_burn_down: 包年分支
# ────────────────────────────────────────────────────────────


@freeze_time(FROZEN_AT)
def test_burn_down_valid_package_uses_expiry_days():
    """有效包年 → days_remaining = 到期剩余天数（CST 日期差），日均/消耗天数为空"""
    expiry = _utcnow() + timedelta(days=45)
    result = _compute_burn_down(
        real_amount=0.0,
        bonus_amount=0.0,
        settlement_type=None,
        stats={"total_cost_30d": 1000.0, "consumption_days": 10},
        package_info=_package_info(expiry_date=expiry),
    )
    assert result["days_remaining"] == 45
    assert result["daily_avg_cost"] is None
    assert result["consumption_days"] == 0


@freeze_time("2026-10-21 20:00:00")  # UTC 20:00 = CST 次日 04:00（CI nightly 运行时刻）
def test_burn_down_days_remaining_is_cst_not_env_local_date():
    """回归：UTC 容器在 CST 次日时段运行，剩余天数仍按 CST 口径计算

    旧代码用 date.today()（跟随运行环境时区）：UTC 容器此刻 today=10-21，
    而 expiry 转 CST 是 12-06，差值 46（多算一天）。修复后用 cst_today()
    取 CST 的 10-22，差值 45。本测试在 CST 时区环境下运行旧代码会通过，
    因此必须配合 TZ=UTC 才能真正守住回归（见 test_timezone_matrix.py）。
    """
    expiry = datetime(2026, 12, 6, 0, 0, 0, tzinfo=timezone.utc)  # CST 12-06 08:00
    result = _compute_burn_down(
        real_amount=0.0,
        bonus_amount=0.0,
        settlement_type=None,
        stats=None,
        package_info=_package_info(expiry_date=expiry),
    )
    # 冻结在 UTC 10-21 20:00 → CST 10-22 04:00；CST 12-06 - CST 10-22 = 45
    assert result["days_remaining"] == 45


def test_burn_down_valid_package_without_expiry_returns_none():
    """有效包年但无到期日（不限时长）→ days_remaining 为 None"""
    result = _compute_burn_down(
        real_amount=0.0,
        bonus_amount=0.0,
        settlement_type=None,
        stats=None,
        package_info=_package_info(expiry_date=None),
    )
    assert result["days_remaining"] is None


def test_burn_down_expired_package_returns_zero():
    """已过期包年 → 标记 0 天（业务上「已耗尽」）"""
    result = _compute_burn_down(
        real_amount=0.0,
        bonus_amount=0.0,
        settlement_type=None,
        stats=None,
        package_info=_package_info(is_expired=True),
    )
    assert result["days_remaining"] == 0
    assert result["daily_avg_cost"] is None


def test_burn_down_non_package_unchanged():
    """非包年（package_info=None）→ 保持原有按消耗推算逻辑"""
    result = _compute_burn_down(
        real_amount=10000.0,
        bonus_amount=0.0,
        settlement_type="prepaid",
        stats={"total_cost_30d": 7000.0, "consumption_days": 7},
        package_info=None,
    )
    # 日均 = 7000 / max(7,7) = 1000；剩余天数 = 10000 / 1000 = 10
    assert result["days_remaining"] == 10
    assert result["daily_avg_cost"] == 1000.0


# ────────────────────────────────────────────────────────────
# _assemble_balance_rows: 包年字段输出
# ────────────────────────────────────────────────────────────


def test_assemble_package_without_balance_row():
    """包年客户无 CustomerBalance 行 → 仍输出余额/包年字段，total_amount 用套餐剩余额度"""
    cust = _customer(balance=None, price_policy="yearly")
    pkg = _package_info(remaining_amount=88000.0, remaining_count=850.0)
    rows = _assemble_balance_rows([cust], {}, {}, {1: pkg})
    row = rows[0]

    assert row["id"] == 1
    assert row["customer_id"] == 1
    assert row["is_package"] is True
    assert row["package_expired"] is False
    assert row["total_amount"] == 88000.0
    assert row["package_remaining_amount"] == 88000.0
    assert row["package_remaining_count"] == 850.0
    # 已消耗 = 套餐内累计消耗（实时口径，与余额列同口径）
    assert row["package_consumed_amount"] == 30000.0
    assert row["price_policy"] == "yearly"
    # 无余额行 → 实充/赠送记 0
    assert row["real_amount"] == 0
    assert row["bonus_amount"] == 0
    # 燃尽 = 到期天数
    assert row["days_remaining"] is not None
    assert row["days_remaining"] >= 0


def test_assemble_expired_package_zeroes_balance():
    """过期包年 → total_amount 与剩余额度按 0 展示，package_expired=True"""
    cust = _customer(balance=None)
    pkg = _package_info(is_expired=True, remaining_amount=0.0)
    rows = _assemble_balance_rows([cust], {}, {}, {1: pkg})
    row = rows[0]

    assert row["is_package"] is True
    assert row["package_expired"] is True
    assert row["total_amount"] == 0
    assert row["days_remaining"] == 0
    # 过期包年无实时消耗语义 → None（展示层回退 CustomerBalance.used_total）
    assert row["package_consumed_amount"] is None


def test_assemble_unlimited_package_no_count():
    """不限量包年 → remaining_count 为 None"""
    cust = _customer(balance=None)
    pkg = _package_info(is_unlimited=True, remaining_count=None, limit_count=None)
    rows = _assemble_balance_rows([cust], {}, {}, {1: pkg})

    assert rows[0]["package_is_unlimited"] is True
    assert rows[0]["package_remaining_count"] is None


def test_assemble_non_package_unchanged():
    """非包年客户（无 package_info）→ 包年字段为空/False，余额取 CustomerBalance 值"""
    balance = SimpleNamespace(
        total_amount=5000,
        real_amount=5000,
        bonus_amount=0,
        used_total=100,
        used_real=100,
        used_bonus=0,
    )
    cust = _customer(balance=balance, price_policy="pricing", settlement_type="prepaid")
    rows = _assemble_balance_rows([cust], {}, {}, {})
    row = rows[0]

    assert row["is_package"] is False
    assert row["package_expired"] is False
    assert row["package_remaining_amount"] is None
    assert row["package_consumed_amount"] is None
    assert row["total_amount"] == 5000


# ────────────────────────────────────────────────────────────
# _batch_query_package_info: 剩余额度/次数与过期判断
# ────────────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        m = MagicMock()
        m.all.return_value = self._rows
        return m

    def all(self):
        return self._rows


def _make_rule(cid: int, *, base_fee, is_unlimited=False, limit_count=None, days_ahead=100):
    limits: dict = {"base_fee": base_fee, "is_unlimited": is_unlimited}
    if limit_count is not None:
        limits["limit_count"] = limit_count
    return SimpleNamespace(
        id=cid * 10,
        customer_id=cid,
        package_limits=limits,
        expiry_date=_utcnow() + timedelta(days=days_ahead),
        effective_date=_utcnow() - timedelta(days=200),
        pricing_type="package",
    )


@pytest.mark.asyncio
@freeze_time(FROZEN_AT)
async def test_batch_query_package_info_limit_and_count():
    """限量套餐：remaining_amount = base_fee - 累计消耗；remaining_count = limit_count - 累计订单量"""
    rule = _make_rule(1, base_fee=120000.0, limit_count=1200.0)
    consumed = SimpleNamespace(pricing_rule_id=rule.id, total_cost=30000.0, order_count=200)

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _FakeResult([rule]),  # 生效规则
            _FakeResult([consumed]),  # 消费聚合
        ]
    )

    info = await _batch_query_package_info(db, [1])
    assert 1 in info
    assert info[1]["remaining_amount"] == 90000.0
    assert info[1]["remaining_count"] == 1000.0
    assert info[1]["consumed_amount"] == 30000.0
    assert info[1]["is_expired"] is False


@pytest.mark.asyncio
@freeze_time(FROZEN_AT)
async def test_batch_query_package_info_unlimited_has_no_count():
    """不限量套餐：remaining_count 为 None"""
    rule = _make_rule(2, base_fee=80000.0, is_unlimited=True, limit_count=None)
    consumed = SimpleNamespace(pricing_rule_id=rule.id, total_cost=10000.0, order_count=50)

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_FakeResult([rule]), _FakeResult([consumed])])

    info = await _batch_query_package_info(db, [2])
    assert info[2]["remaining_amount"] == 70000.0
    assert info[2]["remaining_count"] is None
    assert info[2]["consumed_amount"] == 10000.0
    assert info[2]["is_unlimited"] is True


@pytest.mark.asyncio
@freeze_time(FROZEN_AT)
async def test_batch_query_package_info_clamps_negative():
    """超量使用 → 剩余额度/次数下限为 0（不出现负值）"""
    rule = _make_rule(3, base_fee=10000.0, limit_count=100.0)
    consumed = SimpleNamespace(pricing_rule_id=rule.id, total_cost=15000.0, order_count=150)

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_FakeResult([rule]), _FakeResult([consumed])])

    info = await _batch_query_package_info(db, [3])
    assert info[3]["remaining_amount"] == 0.0
    assert info[3]["remaining_count"] == 0.0
    # 已消耗为未截断的真实累计消耗（超量时仍展示实际消耗 15000）
    assert info[3]["consumed_amount"] == 15000.0


@pytest.mark.asyncio
@freeze_time(FROZEN_AT)
async def test_batch_query_package_info_expired_flag():
    """无生效规则、客户为 yearly、存在已过期规则 → is_expired=True，剩余额度为 0"""
    expired_rule = SimpleNamespace(
        id=40,
        customer_id=4,
        package_limits={"base_fee": 50000.0, "is_unlimited": False, "limit_count": 500},
        expiry_date=_utcnow() - timedelta(days=30),
        effective_date=_utcnow() - timedelta(days=400),
    )

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_FakeResult([]), _FakeResult([expired_rule])])

    info = await _batch_query_package_info(db, [4])
    assert info[4]["is_expired"] is True
    assert info[4]["remaining_amount"] == 0.0
    assert info[4]["remaining_count"] is None
    assert info[4]["consumed_amount"] is None


@pytest.mark.asyncio
async def test_batch_query_package_info_empty_ids():
    """空 customer_ids → 直接返回空映射（不查库）"""
    db = AsyncMock()
    info = await _batch_query_package_info(db, [])
    assert info == {}
    db.execute.assert_not_called()
