"""阶梯覆盖完整性校验（`parse_tiers_or_raise` / `validate_tiers_or_raise`）的边界用例。

`cost_calc._calc_tiered` 按 `max - min + 1` 逐档切块计费：相邻档有缺口会让缺口内的
用量不计费（静默少收），有重叠则会被重复计费。这类错误一入导入库就是脏数据，且全程
静默，故必须锁住这些边界。

首档 `min` 的非 0 取值同样必须拒绝：`_calc_tiered` 不减去首档 `min` 偏移，
`min > 0` 时档位跨度整体前移，超出首档 `max` 的用量会落到更便宜的下一档（静默少收），
单档无上界时 `min` 更是完全不参与计算。见 `app/utils/tiers.py` 的实测说明。
"""

import pytest

from app.utils.tiers import parse_tiers_or_raise, validate_tiers_or_raise


def _tiers(*specs: tuple[int, int | None]) -> list[dict]:
    return [{"min": lo, "max": hi, "price": 5.0} for lo, hi in specs]


@pytest.mark.parametrize(
    ("tiers", "expected_error"),
    [
        pytest.param(_tiers((0, 100), (101, None)), None, id="连续-末档无上界"),
        pytest.param(_tiers((0, 100), (101, 999)), None, id="连续-末档有上界"),
        pytest.param(_tiers((0, None)), None, id="单档"),
        pytest.param(_tiers((0, 100), (150, None)), "区间不连续", id="相邻档有缺口"),
        pytest.param(_tiers((0, 100), (99, None)), "区间不连续", id="相邻档重叠"),
        pytest.param(_tiers((0, None), (101, None)), "仅最后一档允许无上界", id="非末档无上界"),
        pytest.param(_tiers((5, None)), "首档阶梯 min 必须为 0", id="首档-min-非-0-单档"),
        pytest.param(
            _tiers((5, 100), (101, None)), "首档阶梯 min 必须为 0", id="首档-min-非-0-多档"
        ),
    ],
)
def test_validate_tier_coverage(tiers: list[dict], expected_error: str | None) -> None:
    if expected_error is None:
        result = parse_tiers_or_raise(tiers, row_num=3)
        assert [t["min"] for t in result] == [t["min"] for t in tiers]
        return

    with pytest.raises(ValueError) as exc:
        parse_tiers_or_raise(tiers, row_num=3)

    # 行级错误文案须同时含行号与具体原因，否则用户在 Excel 里定位不到出错行
    assert str(exc.value).startswith("第 3 行：")
    assert expected_error in str(exc.value)


class TestValidateTiersOrRaise:
    """规则写入路径（创建/编辑计费规则）专用入口。"""

    def test_none_keeps_none(self) -> None:
        """None 表示「无阶梯配置」，与 normalize_tiers 语义一致（导入路径才需要 []）"""
        assert validate_tiers_or_raise(None) is None

    def test_valid_tiers_normalized(self) -> None:
        result = validate_tiers_or_raise([{"min": 0, "max": 100, "price": 5}])
        assert result == [{"min": 0, "max": 100, "price": 5}]

    def test_non_zero_first_min_rejected(self) -> None:
        """首档 min 非 0 必须拒绝 —— 否则超档用量会静默落到更便宜的下一档"""
        with pytest.raises(ValueError) as exc:
            validate_tiers_or_raise([{"min": 5, "max": None, "price": 10}])
        assert "首档阶梯 min 必须为 0" in str(exc.value)

    def test_continuity_violation_rejected(self) -> None:
        """覆盖完整性校验对写入路径同样生效（缺口会让缺口内用量不计费）"""
        with pytest.raises(ValueError) as exc:
            validate_tiers_or_raise(
                [{"min": 0, "max": 100, "price": 10}, {"min": 150, "max": None, "price": 8}]
            )
        assert "区间不连续" in str(exc.value)

    def test_malformed_shape_rejected(self) -> None:
        """非法形态仍由 normalize_tiers 拦下"""
        with pytest.raises(ValueError):
            validate_tiers_or_raise("not-a-json-array")
