"""包年余额口径共享模块 — 单元测试（无 DB）

覆盖 `app/services/package_balance.py`：
- `resolve_effective_balance`: 包年取套餐剩余额度 / 非包年取 CustomerBalance / 过期归 0
- `batch_query_package_info`: 生效与过期规则分支（与旧 balances.py 实现等价，验证抽取后无回归）

SQL 侧 `build_package_remaining_cte` 的正确性由集成测试
（tests/integration/test_billing_balance_package.py）验证。
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.package_balance import (
    batch_query_package_info,
    resolve_effective_balance,
)


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
        expiry_date=datetime.now(timezone.utc) + timedelta(days=days_ahead),
        effective_date=datetime.now(timezone.utc) - timedelta(days=200),
        pricing_type="package",
    )


# ────────────────────────────────────────────────────────────
# resolve_effective_balance: 跨页口径核心决策
# ────────────────────────────────────────────────────────────


def test_resolve_effective_balance_package_uses_remaining():
    """包年客户：有效余额 = 套餐剩余额度（忽略 CustomerBalance 的 0/负值）"""
    pkg = {"is_expired": False, "remaining_amount": 90000.0}
    assert resolve_effective_balance(0.0, pkg) == (90000.0, True)
    assert resolve_effective_balance(-500.0, pkg) == (90000.0, True)


def test_resolve_effective_balance_expired_package_is_zero():
    """过期包年：剩余额度为 0（不落回 CustomerBalance 的欠费负值）"""
    pkg = {"is_expired": True, "remaining_amount": 0.0}
    assert resolve_effective_balance(-1500.0, pkg) == (0.0, True)


def test_resolve_effective_balance_non_package_uses_customer_balance():
    """非包年客户：有效余额 = CustomerBalance.total_amount（无余额行 None 记 0）"""
    assert resolve_effective_balance(5000.0, None) == (5000.0, False)
    assert resolve_effective_balance(None, None) == (0.0, False)


# ────────────────────────────────────────────────────────────
# batch_query_package_info: 抽取后行为等价
# ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_batch_query_effective_rule_and_consumed():
    """生效限量套餐：剩余额度/次数 + 实时累计消耗"""
    rule = _make_rule(1, base_fee=120000.0, limit_count=1200.0)
    consumed = SimpleNamespace(pricing_rule_id=rule.id, total_cost=30000.0, order_count=200)

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_FakeResult([rule]), _FakeResult([consumed])])

    info = await batch_query_package_info(db, [1])
    assert info[1]["remaining_amount"] == 90000.0
    assert info[1]["remaining_count"] == 1000.0
    assert info[1]["consumed_amount"] == 30000.0
    assert info[1]["is_expired"] is False


@pytest.mark.asyncio
async def test_batch_query_expired_rule_consumed_is_none():
    """过期包年：consumed_amount 为 None（展示层回退 CustomerBalance.used_total）"""
    expired_rule = SimpleNamespace(
        id=40,
        customer_id=4,
        package_limits={"base_fee": 50000.0, "is_unlimited": False, "limit_count": 500},
        expiry_date=datetime.now(timezone.utc) - timedelta(days=30),
        effective_date=datetime.now(timezone.utc) - timedelta(days=400),
    )

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_FakeResult([]), _FakeResult([expired_rule])])

    info = await batch_query_package_info(db, [4])
    assert info[4]["is_expired"] is True
    assert info[4]["remaining_amount"] == 0.0
    assert info[4]["consumed_amount"] is None


@pytest.mark.asyncio
async def test_batch_query_empty_ids_skips_db():
    """空 customer_ids → 不查库，直接返回空映射"""
    db = AsyncMock()
    info = await batch_query_package_info(db, [])
    assert info == {}
    db.execute.assert_not_called()
