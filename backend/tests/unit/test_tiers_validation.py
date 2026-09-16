"""阶梯覆盖完整性校验（`parse_tiers_or_raise`）的边界用例。

`cost_calc._calc_tiered` 按 `max - min + 1` 逐档切块计费：相邻档有缺口会让缺口内的
用量不计费（静默少收），有重叠则会被重复计费。这类错误一入导入库就是脏数据，且全程
静默，故必须锁住这些边界。
"""

import pytest

from app.utils.tiers import parse_tiers_or_raise


def _tiers(*specs: tuple[int, int | None]) -> list[dict]:
    return [{"min": lo, "max": hi, "price": 5.0} for lo, hi in specs]


@pytest.mark.parametrize(
    ("tiers", "expected_error"),
    [
        pytest.param(_tiers((1, 100), (101, None)), None, id="连续-末档无上界"),
        pytest.param(_tiers((1, 100), (101, 999)), None, id="连续-末档有上界"),
        pytest.param(_tiers((1, None)), None, id="单档"),
        pytest.param(_tiers((1, 100), (150, None)), "区间不连续", id="相邻档有缺口"),
        pytest.param(_tiers((1, 100), (99, None)), "区间不连续", id="相邻档重叠"),
        pytest.param(_tiers((1, None), (101, None)), "仅最后一档允许无上界", id="非末档无上界"),
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
