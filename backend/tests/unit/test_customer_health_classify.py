"""客户列表「简易健康度」分类逻辑单元测试

覆盖 routes/customers.py::_classify_customer_health：
- 判定顺序：先用量(inactive)后余额
- 后付费不参与余额判定
- 阈值与 balance_check 同源（app/constants/balance.py）
- 边界值（==500、==1000）
"""

from unittest.mock import MagicMock

from app.constants.balance import BALANCE_CRITICAL_THRESHOLD, BALANCE_WARNING_THRESHOLD
from app.routes.customers import _classify_customer_health


def _make_customer(settlement_type, balance_total=None, customer_id=1):
    """构造带 settlement_type 与 balance 属性的轻量客户对象

    customer_id 必须显式设为 package_info_map 的 key：
    MagicMock 的 .id 默认是新 Mock 实例，dict.get 会失配。
    """
    customer = MagicMock()
    customer.settlement_type = settlement_type
    customer.id = customer_id
    if balance_total is None:
        customer.balance = None
    else:
        customer.balance = MagicMock(total_amount=balance_total)
    return customer


class TestClassifyCustomerHealth:
    """_classify_customer_health 分类规则"""

    # ---- 用量优先：余额再高，零消耗即 inactive ----

    def test_zero_usage_beats_high_balance(self):
        """近30天零消耗 → inactive（余额充足也不标健康）"""
        c = _make_customer("prepaid", balance_total=999999)
        assert _classify_customer_health(c, {}, 0) == "inactive"

    def test_zero_usage_postpaid_also_inactive(self):
        """后付费零消耗同样 inactive（先用量后结算方式）"""
        c = _make_customer("postpaid", balance_total=999999)
        assert _classify_customer_health(c, {}, 0) == "inactive"

    # ---- 后付费豁免余额判定 ----

    def test_postpaid_with_usage_zero_balance_is_healthy(self):
        """后付费有消耗但余额 0 → healthy（不误判 high_risk，旧逻辑的核心 bug）"""
        c = _make_customer("postpaid", balance_total=0)
        assert _classify_customer_health(c, {}, 10) == "healthy"

    def test_postpaid_low_balance_is_healthy(self):
        """后付费余额低于预警阈值仍 healthy（欠款属应收款，不占预付判定）"""
        c = _make_customer("postpaid", balance_total=100)
        assert _classify_customer_health(c, {}, 5) == "healthy"

    def test_postpaid_no_balance_row_is_healthy(self):
        """后付费无余额行 + 有消耗 → healthy"""
        c = _make_customer("postpaid", balance_total=None)
        assert _classify_customer_health(c, {}, 1) == "healthy"

    # ---- 预付费/未设置：余额阈值三档 ----

    def test_prepaid_critical_threshold(self):
        """预付费余额 < 500 → high_risk"""
        c = _make_customer("prepaid", balance_total=BALANCE_CRITICAL_THRESHOLD - 0.01)
        assert _classify_customer_health(c, {}, 10) == "high_risk"

    def test_prepaid_warning_threshold(self):
        """预付费 500 ≤ 余额 < 1000 → attention"""
        c = _make_customer("prepaid", balance_total=BALANCE_WARNING_THRESHOLD - 0.01)
        assert _classify_customer_health(c, {}, 10) == "attention"

    def test_prepaid_above_threshold(self):
        """预付费余额 ≥ 1000 → healthy"""
        c = _make_customer("prepaid", balance_total=5000)
        assert _classify_customer_health(c, {}, 10) == "healthy"

    def test_unset_settlement_type_uses_balance(self):
        """结算方式未设置（None）走预付费同款余额判定，不误入后付费豁免"""
        c = _make_customer(None, balance_total=100)
        assert _classify_customer_health(c, {}, 10) == "high_risk"

    # ---- 边界值：阈值点是「不含等于」语义 ----

    def test_boundary_exactly_critical_is_attention(self):
        """余额恰好 == 500 → attention（判定为 <，不含等于）"""
        c = _make_customer("prepaid", balance_total=BALANCE_CRITICAL_THRESHOLD)
        assert _classify_customer_health(c, {}, 10) == "attention"

    def test_boundary_exactly_warning_is_healthy(self):
        """余额恰好 == 1000 → healthy（判定为 <，不含等于）"""
        c = _make_customer("prepaid", balance_total=BALANCE_WARNING_THRESHOLD)
        assert _classify_customer_health(c, {}, 10) == "healthy"

    # ---- 包年客户走有效余额（套餐剩余额度）----

    def test_package_customer_uses_remaining_amount(self):
        """包年客户按套餐剩余额度判定（package_info_map 优先于 balance 行）"""
        c = _make_customer("prepaid", balance_total=0)
        # 套餐剩余 2000 → attention 区间？不，2000 ≥ 1000 → healthy
        assert _classify_customer_health(c, {1: {"remaining_amount": 2000}}, 10) == "healthy"
        # 套餐剩余 300 → high_risk
        assert _classify_customer_health(c, {1: {"remaining_amount": 300}}, 10) == "high_risk"

    def test_package_customer_zero_remaining_is_high_risk(self):
        """包年套餐剩余 0（含过期）+ 有消耗 → high_risk"""
        c = _make_customer("prepaid", balance_total=5000)
        assert _classify_customer_health(c, {1: {"remaining_amount": 0}}, 10) == "high_risk"


class TestBalanceThresholdConstants:
    """共享阈值常量的契约"""

    def test_critical_below_warning(self):
        """严重阈值必须小于预警阈值（否则 high_risk 区间为空）"""
        assert BALANCE_CRITICAL_THRESHOLD < BALANCE_WARNING_THRESHOLD

    def test_matches_balance_check_task(self):
        """与余额预警任务阈值同源（数值一致，防止口径漂移）"""
        from app.tasks.balance_check import CRITICAL_THRESHOLD, WARNING_THRESHOLD

        assert BALANCE_CRITICAL_THRESHOLD == CRITICAL_THRESHOLD
        assert BALANCE_WARNING_THRESHOLD == WARNING_THRESHOLD
