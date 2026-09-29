"""枚举转换函数方向性单测

契约（2026-09-29 扩散排查后强制）：
- 中文 → 英文存储值（convert_*_to_storage）
- 英文存储值 → 原样透传（幂等）
- 未知值 → None（由调用方报行级错误，禁止静默透传脏值落库）
- convert_*_to_display：英文存储值 → 中文显示值；未知值原样透传
"""

import pytest

from app.services.customers import (
    PRICE_POLICY_MAP,
    SETTLEMENT_CYCLE_MAP,
    SETTLEMENT_TYPE_MAP,
    convert_bool_field,
    convert_price_policy_to_display,
    convert_price_policy_to_storage,
    convert_settlement_cycle_to_display,
    convert_settlement_cycle_to_storage,
    convert_settlement_type_to_display,
    convert_settlement_type_to_storage,
)


class TestConvertPricePolicy:
    @pytest.mark.parametrize(
        "value",
        ["定价", "阶梯", "包年"],
    )
    def test_chinese_to_english(self, value):
        assert convert_price_policy_to_storage(value) == PRICE_POLICY_MAP[value]

    @pytest.mark.parametrize("value", ["pricing", "tiered", "yearly"])
    def test_english_passthrough(self, value):
        assert convert_price_policy_to_storage(value) == value

    @pytest.mark.parametrize("value", ["免费", "custom", "Pricing", " 定价 "])
    def test_unknown_returns_none(self, value):
        # 未知值必须返回 None，绝不透传原值；「 定价 」带空格也视为未知
        assert convert_price_policy_to_storage(value) is None

    def test_display_roundtrip(self):
        assert convert_price_policy_to_display("pricing") == "定价"
        assert convert_price_policy_to_display("未知") == "未知"


class TestConvertSettlementType:
    @pytest.mark.parametrize("value", ["预付费", "后付费"])
    def test_chinese_to_english(self, value):
        assert convert_settlement_type_to_storage(value) == SETTLEMENT_TYPE_MAP[value]

    @pytest.mark.parametrize("value", ["prepaid", "postpaid"])
    def test_english_passthrough(self, value):
        assert convert_settlement_type_to_storage(value) == value

    @pytest.mark.parametrize("value", ["月结", "Prepaid", None, ""])
    def test_unknown_returns_none(self, value):
        assert convert_settlement_type_to_storage(value) is None

    def test_display_roundtrip(self):
        assert convert_settlement_type_to_display("prepaid") == "预付费"
        assert convert_settlement_type_to_display("postpaid") == "后付费"


class TestConvertSettlementCycle:
    @pytest.mark.parametrize("value", ["日结", "周结", "月结", "季结", "年结"])
    def test_chinese_to_english(self, value):
        assert convert_settlement_cycle_to_storage(value) == SETTLEMENT_CYCLE_MAP[value]

    @pytest.mark.parametrize("value", ["daily", "weekly", "monthly", "quarterly", "yearly"])
    def test_english_passthrough(self, value):
        assert convert_settlement_cycle_to_storage(value) == value

    @pytest.mark.parametrize("value", ["半月", "Monthly", None, ""])
    def test_unknown_returns_none(self, value):
        assert convert_settlement_cycle_to_storage(value) is None

    def test_display_roundtrip(self):
        assert convert_settlement_cycle_to_display("monthly") == "月结"
        assert convert_settlement_cycle_to_display("未知") == "未知"


class TestConvertBoolField:
    @pytest.mark.parametrize("value", ["是", "true", "1", "yes", True, 1])
    def test_true_values(self, value):
        assert convert_bool_field(value) is True

    @pytest.mark.parametrize("value", ["否", "false", "0", "no", False, 0])
    def test_false_values(self, value):
        assert convert_bool_field(value) is False

    @pytest.mark.parametrize("value", [None, "", "未知", "y", "是是"])
    def test_unknown_returns_none(self, value):
        # 未知/空值不猜测，返回 None 由调用方决定默认语义
        # （注意：「是 」等带空格输入会被 strip 后正常解析，属预期容错）
        assert convert_bool_field(value) is None
