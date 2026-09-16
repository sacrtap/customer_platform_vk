"""tiers 阶梯配置的唯一归一化与校验 owner。

全链路（导入、前端表单、服务层结算计算、cost_calc、analytics）的 tiers
统一为如下唯一形态：

    tiers = [
        {"min": 0,    "max": 1000,  "price": 10},
        {"min": 1001, "max": 5000,  "price": 8},
        {"min": 5001, "max": null,  "price": 5},
    ]

- ``min`` / ``max``：整数用量边界；``max = null`` 表示无上界
- ``price``：单价（数值）
- 数组顺序即阶梯顺序
- ``None``（或 DB 中的 JSON ``null``）表示「无阶梯配置」

所有消费 tiers 的服务层代码必须通过 ``normalize_tiers`` 或
``parse_tiers_or_raise`` 获取归一化结果，不得自行解析。
"""

from __future__ import annotations

from typing import Any, List, Optional


class TierFormatError(ValueError):
    """tiers 结构非法。

    归一化或校验过程中遇到无法识别的形态时抛出，消息为可读中文文案。
    调用方应捕获此异常并转换为业务错误码（如 ``40002``），不得让其冒泡成 500。
    """


def _validate_tier_item(item: Any) -> dict:
    """校验单个 tier 条目，返回归一化后的 dict。

    要求 ``min`` 为整数、``max`` 为整数或 ``None`` 且不小于 ``min``、
    ``price`` 为非负数值。
    """
    if not isinstance(item, dict):
        raise TierFormatError(f"阶梯条目必须是对象，得到 {type(item).__name__}")

    min_val = item.get("min")
    max_val = item.get("max")
    price_val = item.get("price")

    # min 必须为整数
    if not isinstance(min_val, int) or isinstance(min_val, bool):
        raise TierFormatError(f"阶梯 min 必须为整数，得到 {type(min_val).__name__}")

    # max 为整数或 None
    if max_val is None:
        pass
    elif isinstance(max_val, int) and not isinstance(max_val, bool):
        pass
    else:
        raise TierFormatError(f"阶梯 max 必须为整数或 null，得到 {type(max_val).__name__}")

    # max 不得小于 min：否则阶梯容量为负，会静默算出错误的（可能为负的）金额
    if max_val is not None and max_val < min_val:
        raise TierFormatError(f"阶梯 max（{max_val}）不能小于 min（{min_val}）")

    # price 为数值（int 或 float，排除 bool）
    if isinstance(price_val, bool) or not isinstance(price_val, (int, float)):
        raise TierFormatError(f"阶梯 price 必须为数值，得到 {type(price_val).__name__}")

    # price 不得为负：负单价会算出负数金额
    if price_val < 0:
        raise TierFormatError(f"阶梯 price 不能为负数，得到 {price_val}")

    return {"min": min_val, "max": max_val, "price": price_val}


def normalize_tiers(raw: Any) -> Optional[List[dict]]:
    """把任意历史形态归一化为唯一数组形态。

    - ``None`` / JSON-null 字符串 ``"null"`` / 空对象 ``{}`` → ``None``
      （表示「无阶梯配置」）
    - ``list`` → 逐项校验 ``min`` / ``max`` / ``price`` 类型
    - ``{"ranges": [...]}`` → 兼容历史对象形态，取 ``ranges``
    - 其它 → ``raise TierFormatError``

    Returns:
        归一化后的 ``list[dict]``，或 ``None`` 表示无阶梯配置。
    """
    if raw is None:
        return None

    # JSON null 字符串
    if isinstance(raw, str):
        stripped = raw.strip().lower()
        if stripped == "" or stripped == "null":
            return None

    # 空对象 {}
    if isinstance(raw, dict) and len(raw) == 0:
        return None

    # {"ranges": [...]} 历史对象形态 → 兼容取 ranges
    if isinstance(raw, dict):
        if "ranges" in raw:
            return normalize_tiers(raw["ranges"])
        raise TierFormatError("tiers 对象形态必须包含 ranges 字段")

    if isinstance(raw, list):
        if len(raw) == 0:
            return None
        return [_validate_tier_item(item) for item in raw]

    raise TierFormatError(f"tiers 必须是数组或 null，得到 {type(raw).__name__}")


def _validate_tier_coverage(tiers: List[dict]) -> None:
    """校验阶梯覆盖完整性（导入路径专用）。

    约束（与前端编辑器 getTierError / coverageGaps 对齐）：
    - 相邻档必须连续：后一档 ``min`` 必须等于前一档 ``max + 1``；
    - 仅最后一档允许 ``max`` 为 ``null``（无上界）。

    ``cost_calc._calc_tiered`` 按 ``max - min + 1`` 逐档切块计费：区间存在缺口时
    超出覆盖范围的用量不会被计费（静默少收），重叠时会被重复计费，因此导入时必须拒绝。

    末档允许有上界（前端编辑器 ``PricingRuleModal`` 同样允许）：此时超出末档 ``max``
    的用量不再计费，属定价语义而非格式错误，故末档不参与连续性校验。

    注：首档 ``min`` 允许非 0（前端编辑器要求为 0）。首档 ``min > 0`` 仅使
    0 ~ min-1 的用量不计费，量级可忽略；强制该约束会与导入模板既有示例
    （``[{"min":1,"max":null,"price":5}]``）冲突，故不在此处校验。
    """
    # 只校验相邻档（末档不校验，见 docstring）
    for index in range(len(tiers) - 1):
        tier = tiers[index]
        if tier["max"] is None:
            raise TierFormatError(f"第 {index + 1} 档阶梯 max 为 null，仅最后一档允许无上界")
        next_tier = tiers[index + 1]
        if next_tier["min"] != tier["max"] + 1:
            raise TierFormatError(
                f"第 {index + 1} 档与第 {index + 2} 档阶梯区间不连续"
                f"（前者 max={tier['max']}，后者 min={next_tier['min']}）"
            )


def parse_tiers_or_raise(raw: Any, row_num: Optional[int] = None) -> List[dict]:
    """供导入路径使用：归一化 tiers 并把 ``TierFormatError`` 翻译为行级错误文案。

    与 ``normalize_tiers`` 的区别：
    - ``None`` → 返回空列表 ``[]``（导入场景下 None 表示未填写，合法）
    - 追加覆盖完整性校验（见 ``_validate_tier_coverage``）
    - 校验失败时抛出 ``ValueError``，消息为行级错误文案
      （如 ``"第 N 行：阶梯配置 JSON 格式错误：…"``）

    Args:
        raw: 原始 tiers 值（已 JSON 解析）。
        row_num: 行号（用于行级错误文案，可选）。

    Returns:
        归一化后的 ``list[dict]``，``None`` 时返回空列表。
    """
    try:
        result = normalize_tiers(raw)
        if result:
            _validate_tier_coverage(result)
    except TierFormatError as e:
        prefix = f"第 {row_num} 行：" if row_num is not None else ""
        raise ValueError(f"{prefix}阶梯配置 JSON 格式错误：{e}") from e

    return result if result is not None else []
