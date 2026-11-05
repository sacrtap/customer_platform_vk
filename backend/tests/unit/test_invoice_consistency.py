"""F1 结算单生成前一致性校验单元测试

覆盖：逐日比对方向判定（外部多/本地多/一致）、外部引擎未配置放行、
外部查询异常放行、+ INTERVAL 8 HOUR 的 CST 分桶正确性（16:00 边界）、
拒绝文案含客户名与差异日期清单。
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.invoice_consistency import (
    DayDiff,
    InvoiceConsistencyError,
    diff_period,
    period_label_of,
)


def _utc(y, m, d, hh=0, mm=0, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)


def _external_engine(rows):
    """构造返回指定分桶行的外部 MySQL 引擎 mock"""
    engine = MagicMock()
    result = MagicMock()
    result.fetchall.return_value = rows

    async def _execute(*args, **kwargs):
        return result

    conn = MagicMock()
    conn.execute = AsyncMock(side_effect=_execute)

    @asynccontextmanager
    async def _connect():
        yield conn

    engine.connect = _connect
    return engine


def _external_engine_raising():
    engine = MagicMock()

    @asynccontextmanager
    async def _connect():
        raise ConnectionError("外部 MySQL 不可达")
        yield  # pragma: no cover

    engine.connect = _connect
    return engine


def _db_session(sync_dates):
    """构造返回 daily_orders.sync_date 行的本地 PG 会话 mock"""
    session = MagicMock()
    result = MagicMock()

    async def _execute(*args, **kwargs):
        return result

    session.execute = AsyncMock(side_effect=_execute)
    # select(DailyOrder.sync_date) 结果按 (sync_date,) 元组迭代
    result.__iter__ = lambda self: iter((d,) for d in sync_dates)
    return session


class TestDiffPeriod:
    @pytest.mark.asyncio
    async def test_external_more_than_local_reports_missing(self):
        """外部有本地无：缺同步 → 差异日 external>local"""
        engine = _external_engine([("2026-10-31", 17)])
        session = _db_session([_utc(2026, 10, 31, 6)])  # UTC 06:00 = CST 14:00 同日
        diffs = await diff_period(
            customer_id=27542,
            company_id=1543,
            period_start=_utc(2026, 9, 30, 16),
            period_end=_utc(2026, 10, 31, 15, 59, 59),
            external_engine=engine,
            db_session=session,
        )
        assert diffs == [DayDiff(day="2026-10-31", external=17, local=1)]

    @pytest.mark.asyncio
    async def test_local_more_than_external_reports_residue(self):
        """本地有外部无：跨日残留 → 差异日 local>external"""
        engine = _external_engine([("2026-10-24", 3)])
        session = _db_session(
            [
                _utc(2026, 10, 24, 6),
                _utc(2026, 10, 24, 7),
                _utc(2026, 10, 24, 8),
                _utc(2026, 10, 30, 9),  # 10-30 外部已无（订单过期改期），本地残留 1 行
            ]
        )
        diffs = await diff_period(
            customer_id=27542,
            company_id=1543,
            period_start=_utc(2026, 9, 30, 16),
            period_end=_utc(2026, 10, 31, 15, 59, 59),
            external_engine=engine,
            db_session=session,
        )
        assert diffs == [DayDiff(day="2026-10-30", external=0, local=1)]

    @pytest.mark.asyncio
    async def test_consistent_returns_empty(self):
        """逐日一致 → 空列表"""
        engine = _external_engine([("2026-10-01", 5), ("2026-10-02", 7)])
        session = _db_session(
            [_utc(2026, 10, 1, h) for h in range(5)] + [_utc(2026, 10, 2, h) for h in range(7)]
        )
        diffs = await diff_period(
            customer_id=27542,
            company_id=1543,
            period_start=_utc(2026, 9, 30, 16),
            period_end=_utc(2026, 10, 31, 15, 59, 59),
            external_engine=engine,
            db_session=session,
        )
        assert diffs == []

    @pytest.mark.asyncio
    async def test_engine_none_returns_none(self):
        """外部引擎未配置 → None（放行，不阻塞业务）"""
        session = _db_session([_utc(2026, 10, 31, 6)])
        result = await diff_period(
            customer_id=27542,
            company_id=1543,
            period_start=_utc(2026, 9, 30, 16),
            period_end=_utc(2026, 10, 31, 15, 59, 59),
            external_engine=None,
            db_session=session,
        )
        assert result is None
        # 本地查询也不应执行
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_external_query_failure_returns_none(self):
        """外部查询异常 → None（放行 + warning）"""
        engine = _external_engine_raising()
        session = _db_session([_utc(2026, 10, 31, 6)])
        result = await diff_period(
            customer_id=27542,
            company_id=1543,
            period_start=_utc(2026, 9, 30, 16),
            period_end=_utc(2026, 10, 31, 15, 59, 59),
            external_engine=engine,
            db_session=session,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_cst_day_bucketing_16h_boundary(self):
        """16:00 UTC 边界：本地 sync_date 落在 CST 次日，与外部 +8h 分桶同桶

        UTC 2026-10-31 16:00:00 = CST 2026-11-01 00:00:00，应归 11-01；
        UTC 2026-10-31 15:59:59 = CST 2026-10-31 23:59:59，应归 10-31。
        """
        engine = _external_engine([("2026-11-01", 1), ("2026-10-31", 1)])
        session = _db_session([_utc(2026, 10, 31, 16), _utc(2026, 10, 31, 15, 59, 59)])
        diffs = await diff_period(
            customer_id=27542,
            company_id=1543,
            period_start=_utc(2026, 10, 31, 16),
            period_end=_utc(2026, 11, 1, 15, 59, 59),
            external_engine=engine,
            db_session=session,
        )
        assert diffs == []
        # 反向验证：若把 16:00 那行误归 10-31（不加 8h），则 11-01 缺 1、10-31 多 1


class TestInvoiceConsistencyError:
    def test_message_contains_customer_and_days(self):
        """拒绝文案：客户名 + 每个差异日 + 可执行修复动作"""
        err = InvoiceConsistencyError(
            customer_name="住在好房",
            diffs=[DayDiff(day="2026-10-31", external=17, local=7)],
            period_label="2026-10",
        )
        msg = str(err)
        assert "住在好房" in msg
        assert "2026-10" in msg
        assert "2026-10-31 外部可结算订单 17 笔，本地已同步 7 笔（缺 10 笔）" in msg
        assert "强制覆盖" in msg

    def test_message_both_directions(self):
        """两个方向（缺/多）的文案"""
        err = InvoiceConsistencyError(
            customer_name="测试客户",
            diffs=[
                DayDiff(day="2026-10-31", external=17, local=7),
                DayDiff(day="2026-10-24", external=2, local=4),
            ],
            period_label="2026-10",
        )
        msg = str(err)
        assert "缺 10 笔" in msg
        assert "多 2 笔" in msg

    def test_is_value_error_subclass(self):
        """继承 ValueError：路由层可统一按业务错误处理"""
        assert issubclass(InvoiceConsistencyError, ValueError)


class TestPeriodLabel:
    def test_label_from_utc_period_start(self):
        """账期标签取 period_start 的 CST 年月"""
        # UTC 2026-09-30 16:00 = CST 2026-10-01 00:00 → 2026-10
        assert period_label_of(_utc(2026, 9, 30, 16)) == "2026-10"
