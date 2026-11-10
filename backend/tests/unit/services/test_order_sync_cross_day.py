"""F6 跨日迁移清理单测 - order_sync._migrate_cross_day_orders

- 本批订单码在旧 sync_date 有残留行 → 删除残留 + 按旧日重算消耗 + order_move warning 明细；
- 无残留行 → 不删不重算（同步正常路径零额外开销）。
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dto import SyncDetail
from app.services.order_sync import OrderSyncService

TEST_SYNC_DATE = datetime(2024, 1, 15, tzinfo=timezone.utc)
TEST_OLD_DAY = TEST_SYNC_DATE - timedelta(days=1)


def _make_svc():
    svc = MagicMock(spec=OrderSyncService)
    svc.db = AsyncMock()
    return svc


def _stale_result(rows):
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _make_emit(details: list):
    """复刻 _match_and_save 内的 _emit 闭包签名（测试替身）"""

    def emit(level: str, category: str, message: str, **kwargs):
        details.append(
            SyncDetail(
                sync_date=TEST_SYNC_DATE.date(),
                level=level,
                category=category,
                message=message,
                **kwargs,
            )
        )

    return emit


def _make_stale_row(order_code="ORD-001", customer_id=100):
    row = MagicMock()
    row.id = 7
    row.order_code = order_code
    row.customer_id = customer_id
    row.sync_date = TEST_OLD_DAY
    return row


pytestmark = pytest.mark.asyncio


class TestMigrateCrossDayOrders:
    """跨日迁移清理测试"""

    async def test_stale_rows_deleted_and_old_day_recalculated(self):
        """残留行：删除 + 旧日重算 + order_move warning 明细"""
        svc = _make_svc()
        stale_row = _make_stale_row()
        svc.db.execute = AsyncMock(side_effect=[_stale_result([stale_row]), MagicMock()])
        svc.db.commit = AsyncMock()
        saved_orders = [MagicMock(order_code="ORD-001")]
        details = []

        with patch("app.services.cost_calc.CostCalcService") as MockCostCalc:
            mock_cost = AsyncMock()
            mock_cost.calculate_daily_cost = AsyncMock(return_value={})
            MockCostCalc.return_value = mock_cost

            await OrderSyncService._migrate_cross_day_orders(
                svc,
                sync_date=TEST_SYNC_DATE,
                saved_orders=saved_orders,
                detail_collector=details,
                emit=_make_emit(details),
            )

        # 1 次查残留 + 1 次 DELETE，1 次 commit
        assert svc.db.execute.await_count == 2
        assert svc.db.commit.await_count == 1
        # 旧日重算一次（传入旧日 UTC datetime）
        mock_cost.calculate_daily_cost.assert_awaited_once_with(TEST_OLD_DAY)
        # order_move warning 明细含订单码与新旧日期
        move = [d for d in details if d.category == "order_move"]
        assert len(move) == 1
        assert "ORD-001" in move[0].message
        assert "2024-01-14" in move[0].message  # 旧日
        assert "2024-01-15" in move[0].message  # 新日
        assert move[0].order_code == "ORD-001"
        assert move[0].customer_id == 100

    async def test_multiple_stale_rows_same_old_day_recalc_once(self):
        """同一旧日多条残留：聚合后仅重算一次"""
        svc = _make_svc()
        rows = [_make_stale_row("ORD-001"), _make_stale_row("ORD-002")]
        svc.db.execute = AsyncMock(side_effect=[_stale_result(rows), MagicMock()])
        svc.db.commit = AsyncMock()
        saved_orders = [MagicMock(order_code="ORD-001"), MagicMock(order_code="ORD-002")]
        details = []

        with patch("app.services.cost_calc.CostCalcService") as MockCostCalc:
            mock_cost = AsyncMock()
            mock_cost.calculate_daily_cost = AsyncMock(return_value={})
            MockCostCalc.return_value = mock_cost

            await OrderSyncService._migrate_cross_day_orders(
                svc,
                sync_date=TEST_SYNC_DATE,
                saved_orders=saved_orders,
                detail_collector=details,
                emit=_make_emit(details),
            )

        mock_cost.calculate_daily_cost.assert_awaited_once_with(TEST_OLD_DAY)
        assert len([d for d in details if d.category == "order_move"]) == 2

    async def test_no_stale_rows_no_op(self):
        """无残留行：不删不重算（同步正常路径零额外开销）"""
        svc = _make_svc()
        svc.db.execute = AsyncMock(side_effect=[_stale_result([])])
        svc.db.commit = AsyncMock()
        details = []

        with patch("app.services.cost_calc.CostCalcService") as MockCostCalc:
            mock_cost = AsyncMock()
            mock_cost.calculate_daily_cost = AsyncMock(return_value={})
            MockCostCalc.return_value = mock_cost

            await OrderSyncService._migrate_cross_day_orders(
                svc,
                sync_date=TEST_SYNC_DATE,
                saved_orders=[MagicMock(order_code="ORD-001")],
                detail_collector=details,
                emit=_make_emit(details),
            )

        # 仅 1 次查残留，无 DELETE、无 commit、无重算、无明细
        assert svc.db.execute.await_count == 1
        assert svc.db.commit.await_count == 0
        mock_cost.calculate_daily_cost.assert_not_awaited()
        assert details == []

    async def test_empty_saved_orders_returns_early(self):
        """无本批订单：直接返回（不查库）"""
        svc = _make_svc()
        details = []

        await OrderSyncService._migrate_cross_day_orders(
            svc,
            sync_date=TEST_SYNC_DATE,
            saved_orders=[],
            detail_collector=details,
            emit=_make_emit(details),
        )

        svc.db.execute.assert_not_awaited()
        assert details == []

    async def test_delete_key_includes_custom_code(self):
        """F8：残留删除键为 (order_code, custom_code)，不是仅 order_code

        旧实现按 order_code 一把删，会把同一订单号的其他房源行误删
        （该笔业务不计费）。此处断言残留查询的 WHERE 条件含 custom_code。
        """
        svc = _make_svc()
        svc.db.execute = AsyncMock(side_effect=[_stale_result([])])
        svc.db.commit = AsyncMock()
        details = []

        with patch("app.services.cost_calc.CostCalcService"):
            await OrderSyncService._migrate_cross_day_orders(
                svc,
                sync_date=TEST_SYNC_DATE,
                saved_orders=[MagicMock(order_code="ORD-001", custom_code="HS-A")],
                detail_collector=details,
                emit=_make_emit(details),
            )

        stmt = svc.db.execute.call_args_list[0].args[0]
        sql = str(stmt)
        assert "custom_code" in sql
        # 键中同时出现订单号与房源号（tuple_ + COALESCE 归一的表达式索引键）
        assert "ORD-001" not in sql  # 参数化占位，非字面量
        # 无残留 → 不删不重算
        assert svc.db.execute.await_count == 1
        assert svc.db.commit.await_count == 0
