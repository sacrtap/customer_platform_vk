"""余额管理页筛选项单元测试（无 DB）

背景: PR 门禁在单元层判定覆盖率 ≥34%（backend-tests job）。
`app/routes/billing/balances.py` 是路由模块，集成测试用 asgi_client 覆盖，
但覆盖度量在部分路径不完整；此文件直接调用解析/条件构建的纯函数，
并借 Mock session 覆盖新筛选条件的 WHERE 组装分支（不连真实 DB）。

覆盖范围（对齐客户管理页新增的 4 项筛选）:
- _parse_balance_filters: auto_initiate_settlement / is_disabled 布尔校验、
  erp_system / cooperation_status 空串归一、settlement_group 枚举校验
- _bool_filter_condition: 历史 NULL 兼容语义的 4 个分支
- _settlement_group_condition: prepaid / postpaid 分组条件
- _query_balance_rows_raw: 新筛选条件被正确拼入 base_stmt（列表）与 count_stmt

注意: 真实 SQL 结果正确性仍由集成测试（tests/integration/test_billing_api.py）验证。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import column
from sqlalchemy.dialects import sqlite

from app.routes.billing.balances import (
    _bool_filter_condition,
    _parse_balance_filters,
    _query_balance_rows_raw,
    _settlement_group_condition,
)

# ────────────────────────────────────────────────────────────
# 辅助
# ────────────────────────────────────────────────────────────


def _req(**params) -> SimpleNamespace:
    """构造最小 Request 形态（只需 args.get）"""
    return SimpleNamespace(args=params)


def _compile(expr) -> str:
    """将 SQLAlchemy 表达式编译为字面量 SQL 字符串（SQLite 方言）"""
    return str(expr.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))


def _full_filters(**overrides) -> dict:
    """基于 _parse_balance_filters 产出的完整 filters 字典（保证键齐全）"""
    params = {
        "keyword": "测试",
        "account_type": "enterprise",
        "manager_id": "3",
        "balance_min": "100",
        "balance_max": "5000",
    }
    params.update(overrides)
    return _parse_balance_filters(_req(**params))


# ────────────────────────────────────────────────────────────
# _parse_balance_filters: 新增字段解析
# ────────────────────────────────────────────────────────────


def test_parse_new_filters_valid_values():
    """合法的布尔/字符串筛选被正确解析"""
    filters = _parse_balance_filters(
        _req(
            auto_initiate_settlement="true",
            is_disabled="false",
            erp_system="yonyou",
            cooperation_status="合作中",
        )
    )
    assert filters["auto_initiate_settlement"] is True
    assert filters["is_disabled"] is False
    assert filters["erp_system"] == "yonyou"
    assert filters["cooperation_status"] == "合作中"


def test_parse_new_filters_absent_are_none():
    """未传新增参数 → None（保持改动前行为）"""
    filters = _parse_balance_filters(_req())
    assert filters["auto_initiate_settlement"] is None
    assert filters["is_disabled"] is None
    assert filters["erp_system"] is None
    assert filters["cooperation_status"] is None


@pytest.mark.parametrize("field", ["auto_initiate_settlement", "is_disabled"])
def test_parse_bool_invalid_raises(field):
    """布尔字段非法值 → ValueError（调用方转 400）"""
    with pytest.raises(ValueError, match=field):
        _parse_balance_filters(_req(**{field: "yes"}))


@pytest.mark.parametrize("field", ["auto_initiate_settlement", "is_disabled"])
def test_parse_bool_empty_string_is_none(field):
    """布尔字段空串 → None（视为未传，不报错）"""
    filters = _parse_balance_filters(_req(**{field: "   "}))
    assert filters[field] is None


@pytest.mark.parametrize("field", ["erp_system", "cooperation_status"])
def test_parse_string_empty_becomes_none(field):
    """字符串字段空串/空白 → None"""
    filters = _parse_balance_filters(_req(**{field: "  "}))
    assert filters[field] is None


def test_parse_settlement_group_valid():
    """settlement_group 合法值被保留"""
    filters = _parse_balance_filters(_req(settlement_group="postpaid"))
    assert filters["settlement_group"] == "postpaid"


def test_parse_settlement_group_invalid_raises():
    """settlement_group 非法值 → ValueError"""
    with pytest.raises(ValueError, match="settlement_group"):
        _parse_balance_filters(_req(settlement_group="monthly"))


# ────────────────────────────────────────────────────────────
# _bool_filter_condition: 历史 NULL 兼容语义
# ────────────────────────────────────────────────────────────


def test_bool_filter_condition_matrix():
    """4 个分支的 NULL 兼容语义（对齐客户管理页 services/customers.py）"""
    col = column("auto_initiate_settlement")

    # 自动发起结算（默认值=是）: True → IS TRUE OR IS NULL
    sql = _compile(_bool_filter_condition(col, True, null_as_true=True))
    assert "IS 1" in sql and "IS NULL" in sql

    # 自动发起结算: False → IS FALSE
    sql = _compile(_bool_filter_condition(col, False, null_as_true=True))
    assert "IS 0" in sql and "IS NULL" not in sql

    # 是否停用（默认值=否）: True → IS TRUE
    sql = _compile(_bool_filter_condition(col, True, null_as_true=False))
    assert "IS 1" in sql and "IS NULL" not in sql

    # 是否停用: False → IS FALSE OR IS NULL
    sql = _compile(_bool_filter_condition(col, False, null_as_true=False))
    assert "IS 0" in sql and "IS NULL" in sql


def test_settlement_group_condition_grouping():
    """结算类型分组：postpaid 精确匹配，prepaid 用 coalesce 兜底"""
    postpaid = _compile(_settlement_group_condition("postpaid"))
    assert "postpaid" in postpaid and "IS NULL" not in postpaid

    prepaid = _compile(_settlement_group_condition("prepaid"))
    assert "coalesce" in prepaid.lower() and "postpaid" in prepaid


# ────────────────────────────────────────────────────────────
# _query_balance_rows_raw: 新筛选条件拼入 SQL
# ────────────────────────────────────────────────────────────


class _FakeResult:
    """最小 Result 桩：count_stmt 用 scalar()，主查询用 scalars().all()"""

    def __init__(self, *, count=0, rows=None):
        self._count = count
        self._rows = rows or []

    def scalar(self):
        return self._count

    def scalars(self):
        m = MagicMock()
        m.all.return_value = self._rows
        return m

    def all(self):
        return self._rows


async def _run_query(filters: dict) -> list[str]:
    """执行 _query_balance_rows_raw，返回所有被下发的 SQL 字符串"""
    captured: list[str] = []

    async def fake_execute(stmt):  # noqa: ANN001
        captured.append(str(stmt))
        # 第一次是 count_stmt，之后是主查询（返回空行 → 跳过后续 recharge/消费查询）
        return _FakeResult(count=0) if len(captured) == 1 else _FakeResult(rows=[])

    db = AsyncMock()
    db.execute = fake_execute
    await _query_balance_rows_raw(db, filters)
    return captured


@pytest.mark.asyncio
async def test_query_applies_new_filters():
    """新增 4 项筛选同时作用于 base_stmt 与 count_stmt"""
    filters = _full_filters(
        auto_initiate_settlement="true",
        is_disabled="false",
        erp_system="yonyou",
        cooperation_status="合作中",
    )
    captured = await _run_query(filters)
    assert len(captured) == 2  # count_stmt + 主查询

    for sql in captured:
        assert "auto_initiate_settlement" in sql
        assert "is_disabled" in sql
        assert "erp_system" in sql
        assert "cooperation_status" in sql


@pytest.mark.asyncio
async def test_query_without_new_filters_omits_conditions():
    """未传新增筛选 → SQL 不含对应条件（行为与改动前一致）"""
    captured = await _run_query(_full_filters())
    assert len(captured) == 2

    for sql in captured:
        assert "auto_initiate_settlement" not in sql
        assert "is_disabled" not in sql
        assert "erp_system" not in sql
        assert "cooperation_status" not in sql


@pytest.mark.asyncio
async def test_query_bool_filter_null_semantics_in_sql():
    """自动发起结算=true（默认是）与 是否停用=false（默认否）在 SQL 中均含 IS NULL 兜底"""
    filters = _full_filters(auto_initiate_settlement="true", is_disabled="false")
    captured = await _run_query(filters)
    sql = str(captured[-1])
    # auto_initiate_settlement: IS TRUE OR IS NULL；is_disabled: IS FALSE OR IS NULL
    assert sql.count("IS NULL") >= 2
