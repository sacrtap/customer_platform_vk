"""OrderSyncService 单元测试 - 订单同步"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.dto import SyncResult

# 测试用 UTC datetime（模拟 local_date_to_utc_start 的输出）
TEST_SYNC_DATE = datetime(2024, 1, 15, tzinfo=timezone.utc)

# ==================== Fixtures ====================


def _mock_order_row(
    order_code="ORD-001",
    custom_code="HS-001",
    nest_id="NEST-001",
    company_name="测试公司",
    group_type="G001",
    create_date="2024-01-15",
    floor_count=10,
    device_type="X",
):
    """辅助：创建模拟外部订单行记录"""
    return {
        "order_code": order_code,
        "custom_code": custom_code,
        "nest_id": nest_id,
        "company_name": company_name,
        "group_type": group_type,
        "create_date": create_date,
        "floor_count": floor_count,
        "device_type": device_type,
    }


def _make_mock_customer(customer_id=1, name="测试公司", company_id=1):
    """辅助：创建模拟客户"""
    mock_customer = MagicMock()
    mock_customer.id = customer_id
    mock_customer.name = name
    mock_customer.company_id = company_id
    return mock_customer


# ==================== Test _match_and_save ====================


class TestOrderSyncServiceMatchAndSave:
    """匹配客户并保存订单测试"""

    async def test_match_and_save_success(self):
        """成功匹配客户并保存订单"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        orders = [_mock_order_row()]
        mock_customer = _make_mock_customer()

        # _match_customer 返回客户
        svc._match_customer = AsyncMock(return_value=mock_customer)

        # execute 返回空（无重复订单）
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None
        svc.db.execute = AsyncMock(return_value=existing_result)
        svc.db.add = MagicMock()
        svc.db.commit = AsyncMock()

        result = await OrderSyncService._match_and_save(
            svc, orders=orders, sync_date=TEST_SYNC_DATE
        )

        assert isinstance(result, SyncResult)
        assert result.success == 1
        assert result.failed == 0
        assert result.skipped == 0

    async def test_match_and_save_unmatched_customer(self):
        """客户匹配失败（未找到客户）"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        orders = [_mock_order_row(group_type="G999")]

        # _match_customer 返回 None（未匹配到客户）
        svc._match_customer = AsyncMock(return_value=None)

        result = await OrderSyncService._match_and_save(
            svc, orders=orders, sync_date=TEST_SYNC_DATE
        )

        assert isinstance(result, SyncResult)
        assert result.success == 0
        assert result.unmatched == 1

    async def test_match_and_save_duplicate_order(self):
        """重复订单跳过"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        orders = [_mock_order_row()]
        mock_customer = _make_mock_customer()

        # 客户匹配成功，但订单已存在
        customer_result = MagicMock()
        customer_result.scalar_one_or_none.return_value = mock_customer
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = MagicMock()  # 已存在

        svc.db.execute = AsyncMock(side_effect=[customer_result, existing_result])

        result = await OrderSyncService._match_and_save(
            svc, orders=orders, sync_date=TEST_SYNC_DATE
        )

        assert isinstance(result, SyncResult)
        assert result.skipped == 1

    async def test_match_and_save_db_error(self):
        """批量提交时数据库异常"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        orders = [_mock_order_row()]
        mock_customer = _make_mock_customer()

        # _match_customer 返回客户
        svc._match_customer = AsyncMock(return_value=mock_customer)

        # execute 返回空（无重复订单）
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None
        svc.db.execute = AsyncMock(return_value=existing_result)
        svc.db.add = MagicMock()
        svc.db.commit = AsyncMock(side_effect=Exception("Deadlock detected"))
        svc.db.rollback = AsyncMock()

        result = await OrderSyncService._match_and_save(
            svc, orders=orders, sync_date=TEST_SYNC_DATE
        )

        assert isinstance(result, SyncResult)
        assert result.failed == 1

    async def test_match_and_save_same_code_two_houses_both_saved(self):
        """F8：同一订单号派给两个不同房源——两行都保存、各自计费

        旧实现按 (order_code, sync_date) 去重，第二房源在同步入口即被丢弃，
        导致该笔业务不计费（三表数量差 1）。识别键加入 custom_code 后，
        同号不同房源各自成行。
        """
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        orders = [
            _mock_order_row(order_code="ORD-DUP", custom_code="HS-A"),
            _mock_order_row(order_code="ORD-DUP", custom_code="HS-B"),
        ]
        mock_customer = _make_mock_customer()
        svc._match_customer = AsyncMock(return_value=mock_customer)

        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None
        svc.db.execute = AsyncMock(return_value=existing_result)
        svc.db.add = MagicMock()
        svc.db.commit = AsyncMock()

        result = await OrderSyncService._match_and_save(
            svc, orders=orders, sync_date=TEST_SYNC_DATE
        )

        assert result.success == 2
        assert result.skipped == 0
        assert svc.db.add.call_count == 2

    async def test_match_and_save_null_custom_code_deduped_by_order_code(self):
        """F8：custom_code 为空时保持订单号语义——同号第二行仍去重

        唯一索引用 COALESCE(custom_code, '') 归一空值，内存去重键同步归一，
        避免空房源行绕过「订单号即唯一」的原语义。
        """
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        orders = [
            _mock_order_row(order_code="ORD-001", custom_code=None),
            _mock_order_row(order_code="ORD-001", custom_code=None),
        ]
        mock_customer = _make_mock_customer()
        svc._match_customer = AsyncMock(return_value=mock_customer)

        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None
        svc.db.execute = AsyncMock(return_value=existing_result)
        svc.db.add = MagicMock()
        svc.db.commit = AsyncMock()

        result = await OrderSyncService._match_and_save(
            svc, orders=orders, sync_date=TEST_SYNC_DATE
        )

        assert result.success == 1
        assert result.skipped == 1


# ==================== Test sync_orders ====================


class TestOrderSyncServiceSyncOrders:
    """订单同步主方法测试"""

    async def test_sync_orders_full_success(self):
        """完整同步流程成功"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        orders = [_mock_order_row()]

        match_result = SyncResult(success=1, failed=0, skipped=0, unmatched=0, message="同步完成")

        svc._fetch_orders = AsyncMock(return_value=orders)
        svc._match_and_save = AsyncMock(return_value=match_result)

        result = await OrderSyncService.sync_orders(svc, sync_date=TEST_SYNC_DATE)

        assert isinstance(result, SyncResult)
        assert result.success == 1
        assert result.failed == 0

        svc._fetch_orders.assert_awaited_once_with(TEST_SYNC_DATE)
        svc._match_and_save.assert_awaited_once_with(
            orders=orders, sync_date=TEST_SYNC_DATE, detail_collector=None
        )

    async def test_sync_orders_fetch_fails(self):
        """获取外部订单失败时异常向上传播"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        svc._fetch_orders = AsyncMock(side_effect=Exception("外部数据库连接超时"))

        # 异常应向上传播，由 execute_task 的逐天异常处理器捕获
        with pytest.raises(Exception, match="外部数据库连接超时"):
            await OrderSyncService.sync_orders(svc, sync_date=TEST_SYNC_DATE)

    async def test_sync_orders_no_data(self):
        """没有新订单需要同步"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        svc._fetch_orders = AsyncMock(return_value=[])

        result = await OrderSyncService.sync_orders(svc, sync_date=TEST_SYNC_DATE)

        assert isinstance(result, SyncResult)
        assert result.success == 0
        svc._match_and_save.assert_not_awaited()

    async def test_sync_orders_partial_failure(self):
        """部分订单同步失败"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        orders = [_mock_order_row(), _mock_order_row(order_code="ORD-002", custom_code="HS-002")]

        match_result = SyncResult(
            success=1, failed=1, skipped=0, unmatched=0, message="部分同步失败"
        )

        svc._fetch_orders = AsyncMock(return_value=orders)
        svc._match_and_save = AsyncMock(return_value=match_result)

        result = await OrderSyncService.sync_orders(svc, sync_date=TEST_SYNC_DATE)

        assert isinstance(result, SyncResult)
        assert result.success == 1
        assert result.failed == 1
        assert "部分同步失败" in result.message
