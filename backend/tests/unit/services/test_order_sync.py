"""OrderSyncService 单元测试 - 订单同步"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from pytest import raises

from app.services.dto import CustomerCalcResult, SyncResult

# ==================== Fixtures ====================


def _mock_order_row(
    order_code: str = "ORD-001",
    custom_code: str = "HS-001",
    nest_id: str = "NEST-001",
    company_name: str = "测试公司",
    group_type: str = "G001",
    create_date: str = "2024-01-15",
    floor_count: int = 10,
    device_type: str = "X",
):
    """辅助：创建模拟外部订单行记录"""
    row = MagicMock()
    row.order_code = order_code
    row.custom_code = custom_code
    row.nest_id = nest_id
    row.company_name = company_name
    row.group_type = group_type
    row.create_date = create_date
    row.floor_count = floor_count
    row.device_type = device_type
    return row


# ==================== Test _calculate_cost ====================


class TestOrderSyncService_CalculateCost:
    """费用计算逻辑测试"""

    async def test_calculate_cost_basic(self):
        """基本费用计算 - 按楼层数"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        # 模拟定价规则
        pricing_rule = MagicMock()
        pricing_rule.price = Decimal("500.00")
        pricing_rule.floor_count = 0  # 基础价格，不限楼层
        pricing_rule.price_type = "unified"
        pricing_rule.price_policy = "pricing"

        result = await OrderSyncService._calculate_cost(
            svc,
            customer_id=1,
            floor_count=10,
            pricing_rule=pricing_rule,
        )

        assert isinstance(result, CustomerCalcResult)
        assert result.customer_id == 1
        assert result.total_cost == Decimal("500.00")
        assert result.has_rule is True

    async def test_calculate_cost_tiered_pricing(self):
        """阶梯计费 - 按楼层区间"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        # 模拟多条阶梯规则
        rule_50 = MagicMock()
        rule_50.floor_count = 50
        rule_50.price = Decimal("300.00")
        rule_50.price_type = "tiered"
        rule_50.price_policy = "tiered"

        rule_100 = MagicMock()
        rule_100.floor_count = 100
        rule_100.price = Decimal("200.00")
        rule_100.price_type = "tiered"
        rule_100.price_policy = "tiered"

        result = await OrderSyncService._calculate_cost(
            svc,
            customer_id=1,
            floor_count=75,
            pricing_rule=rule_50,
        )

        assert isinstance(result, CustomerCalcResult)
        assert result.has_rule is True
        assert result.total_cost == Decimal("300.00")

    async def test_calculate_cost_no_rule(self):
        """没有定价规则时返回 no_rule 状态"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        result = await OrderSyncService._calculate_cost(
            svc,
            customer_id=1,
            floor_count=10,
            pricing_rule=None,
        )

        assert isinstance(result, CustomerCalcResult)
        assert result.has_rule is False
        assert result.total_cost == Decimal("0.00")
        assert "no_rule" in result.message or not result.has_rule

    async def test_calculate_cost_zero_floor(self):
        """楼层数为 0 的费用计算"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        pricing_rule = MagicMock()
        pricing_rule.price = Decimal("500.00")
        pricing_rule.floor_count = 0
        pricing_rule.price_type = "unified"
        pricing_rule.price_policy = "pricing"

        result = await OrderSyncService._calculate_cost(
            svc,
            customer_id=1,
            floor_count=0,
            pricing_rule=pricing_rule,
        )

        assert isinstance(result, CustomerCalcResult)
        assert result.total_cost == Decimal("500.00")


# ==================== Test _fetch_orders ====================


class TestOrderSyncService_FetchOrders:
    """从外部 MySQL 获取订单测试"""

    async def test_fetch_orders_success(self):
        """成功获取订单数据"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.__aenter__.return_value = mock_cursor
        mock_cursor.__aexit__.return_value = None
        mock_conn.__aenter__.return_value = mock_conn
        mock_conn.__aexit__.return_value = None

        # 模拟查询结果
        mock_cursor.fetchall = AsyncMock(
            return_value=[
                ("ORD-001", "HS-001", "NEST-001", "测试公司", "G001", "2024-01-15", 10, "X"),
                ("ORD-002", "HS-002", "NEST-002", "测试公司2", "G002", "2024-01-16", 20, "N"),
            ]
        )

        # 模拟外部 MySQL 连接
        external_conn = MagicMock()
        external_conn.cursor.return_value = mock_cursor
        mock_conn = AsyncMock()
        mock_conn.__aenter__.return_value = external_conn
        mock_conn.__aexit__.return_value = None

        # patch 外部数据库连接创建
        with patch(
            "app.services.order_sync.aiomysql.connect", new_callable=AsyncMock
        ) as mock_connect:
            mock_connect.return_value = mock_conn

            # 设置外部数据库配置
            type(svc).external_db_config = PropertyMock(
                return_value={
                    "host": "192.168.1.100",
                    "port": 3306,
                    "user": "sync_user",
                    "password": "sync_pass",
                    "db": "erp_orders",
                }
            )

            result = await OrderSyncService._fetch_orders(svc, sync_date="2024-01-15")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["order_code"] == "ORD-001"
        assert result[1]["order_code"] == "ORD-002"

    async def test_fetch_orders_empty(self):
        """外部 MySQL 无数据"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        mock_cursor = AsyncMock()
        mock_cursor.__aenter__.return_value = mock_cursor
        mock_cursor.__aexit__.return_value = None
        mock_cursor.fetchall = AsyncMock(return_value=[])

        external_conn = MagicMock()
        external_conn.cursor.return_value = mock_cursor
        mock_conn = AsyncMock()
        mock_conn.__aenter__.return_value = external_conn
        mock_conn.__aexit__.return_value = None

        with patch(
            "app.services.order_sync.aiomysql.connect", new_callable=AsyncMock
        ) as mock_connect:
            mock_connect.return_value = mock_conn
            type(svc).external_db_config = PropertyMock(
                return_value={
                    "host": "192.168.1.100",
                    "port": 3306,
                    "user": "sync_user",
                    "password": "sync_pass",
                    "db": "erp_orders",
                }
            )

            result = await OrderSyncService._fetch_orders(svc, sync_date="2024-01-15")

        assert isinstance(result, list)
        assert len(result) == 0

    async def test_fetch_orders_connection_failed(self):
        """外部 MySQL 连接失败"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        with patch(
            "app.services.order_sync.aiomysql.connect",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused: 192.168.1.100:3306"),
        ):
            type(svc).external_db_config = PropertyMock(
                return_value={
                    "host": "192.168.1.100",
                    "port": 3306,
                    "user": "sync_user",
                    "password": "sync_pass",
                    "db": "erp_orders",
                }
            )

            with raises(Exception) as excinfo:
                await OrderSyncService._fetch_orders(svc, sync_date="2024-01-15")

            assert "Connection refused" in str(excinfo.value)

    async def test_fetch_orders_query_error(self):
        """外部 MySQL 查询异常"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        mock_cursor = AsyncMock()
        mock_cursor.__aenter__.return_value = mock_cursor
        mock_cursor.__aexit__.return_value = None
        mock_cursor.execute = AsyncMock(
            side_effect=Exception("Table 'erp_orders.orders' doesn't exist")
        )

        external_conn = MagicMock()
        external_conn.cursor.return_value = mock_cursor
        mock_conn = AsyncMock()
        mock_conn.__aenter__.return_value = external_conn
        mock_conn.__aexit__.return_value = None

        with patch(
            "app.services.order_sync.aiomysql.connect", new_callable=AsyncMock
        ) as mock_connect:
            mock_connect.return_value = mock_conn
            type(svc).external_db_config = PropertyMock(
                return_value={
                    "host": "192.168.1.100",
                    "port": 3306,
                    "user": "sync_user",
                    "password": "sync_pass",
                    "db": "erp_orders",
                }
            )

            with raises(Exception) as excinfo:
                await OrderSyncService._fetch_orders(svc, sync_date="2024-01-15")

            assert "doesn't exist" in str(excinfo.value)


# ==================== Test _match_and_save ====================


class TestOrderSyncService_MatchAndSave:
    """匹配客户并保存订单测试"""

    async def test_match_and_save_success(self):
        """成功匹配客户并保存订单"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        # 模拟外部订单数据
        orders = [
            {
                "order_code": "ORD-001",
                "custom_code": "HS-001",
                "nest_id": "NEST-001",
                "company_name": "测试公司",
                "group_type": "G001",
                "create_date": "2024-01-15",
                "floor_count": 10,
                "device_type": "X",
            }
        ]

        # 模拟 SQLAlchemy 查询结果（匹配到客户）
        mock_result = MagicMock()
        mock_scalar = MagicMock()
        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer.name = "测试公司"
        mock_scalar.scalar_one_or_none.return_value = mock_customer

        svc.db.execute = AsyncMock(return_value=mock_scalar)

        result = await OrderSyncService._match_and_save(svc, orders=orders, sync_date="2024-01-15")

        assert isinstance(result, SyncResult)
        assert result.success == 1
        assert result.failed == 0
        assert result.skipped == 0

    async def test_match_and_save_unmatched_customer(self):
        """客户匹配失败（未找到客户）"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        orders = [
            {
                "order_code": "ORD-001",
                "custom_code": "HS-999",
                "nest_id": "NEST-999",
                "company_name": "未知公司",
                "group_type": "G999",
                "create_date": "2024-01-15",
                "floor_count": 10,
                "device_type": "X",
            }
        ]

        # 模拟未匹配到客户
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        svc.db.execute = AsyncMock(return_value=mock_result)

        result = await OrderSyncService._match_and_save(svc, orders=orders, sync_date="2024-01-15")

        assert isinstance(result, SyncResult)
        assert result.success == 0
        assert result.unmatched == 1

    async def test_match_and_save_duplicate_order(self):
        """重复订单跳过"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        orders = [
            {
                "order_code": "ORD-001",
                "custom_code": "HS-001",
                "nest_id": "NEST-001",
                "company_name": "测试公司",
                "group_type": "G001",
                "create_date": "2024-01-15",
                "floor_count": 10,
                "device_type": "X",
            }
        ]

        # 模拟匹配到客户
        mock_customer_result = MagicMock()
        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer_result.scalar_one_or_none.return_value = mock_customer

        # 模拟检测到订单已存在
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = MagicMock()

        svc.db.execute = AsyncMock()
        svc.db.execute.side_effect = [mock_customer_result, mock_existing_result]

        result = await OrderSyncService._match_and_save(svc, orders=orders, sync_date="2024-01-15")

        assert isinstance(result, SyncResult)
        assert result.skipped == 1

    async def test_match_and_save_db_error(self):
        """保存订单时数据库异常"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        orders = [
            {
                "order_code": "ORD-001",
                "custom_code": "HS-001",
                "nest_id": "NEST-001",
                "company_name": "测试公司",
                "group_type": "G001",
                "create_date": "2024-01-15",
                "floor_count": 10,
                "device_type": "X",
            }
        ]

        # 模拟匹配到客户但保存时出错
        mock_customer_result = MagicMock()
        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer_result.scalar_one_or_none.return_value = mock_customer

        # 模拟没有重复
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None

        svc.db.execute.side_effect = [mock_customer_result, mock_existing_result]
        svc.db.commit = AsyncMock(side_effect=Exception("Deadlock detected, retry transaction"))

        result = await OrderSyncService._match_and_save(svc, orders=orders, sync_date="2024-01-15")

        assert isinstance(result, SyncResult)
        assert result.failed == 1


# ==================== Test sync_orders ====================


class TestOrderSyncService_SyncOrders:
    """订单同步主方法测试"""

    async def test_sync_orders_full_success(self):
        """完整同步流程成功"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        # Mock _fetch_orders 返回数据
        orders = [
            {
                "order_code": "ORD-001",
                "custom_code": "HS-001",
                "nest_id": "NEST-001",
                "company_name": "测试公司",
                "group_type": "G001",
                "create_date": "2024-01-15",
                "floor_count": 10,
                "device_type": "X",
            }
        ]

        # Mock _match_and_save 返回成功
        match_result = SyncResult(success=1, failed=0, skipped=0, unmatched=0, message="同步完成")

        svc._fetch_orders = AsyncMock(return_value=orders)
        svc._match_and_save = AsyncMock(return_value=match_result)

        result = await OrderSyncService.sync_orders(svc, sync_date="2024-01-15")

        assert isinstance(result, SyncResult)
        assert result.success == 1
        assert result.failed == 0

        svc._fetch_orders.assert_awaited_once_with(sync_date="2024-01-15")
        svc._match_and_save.assert_awaited_once_with(orders=orders, sync_date="2024-01-15")

    async def test_sync_orders_fetch_fails(self):
        """获取外部订单失败时同步中止"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        svc._fetch_orders = AsyncMock(side_effect=Exception("外部数据库连接超时"))

        # sync_orders 应该吞掉异常并返回错误 SyncResult
        result = await OrderSyncService.sync_orders(svc, sync_date="2024-01-15")

        assert isinstance(result, SyncResult)
        assert result.success == 0
        assert "外部数据库连接超时" in result.message

    async def test_sync_orders_no_data(self):
        """没有新订单需要同步"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        svc._fetch_orders = AsyncMock(return_value=[])
        svc._match_and_save = AsyncMock()

        result = await OrderSyncService.sync_orders(svc, sync_date="2024-01-15")

        assert isinstance(result, SyncResult)
        assert result.success == 0
        svc._match_and_save.assert_not_awaited()

    async def test_sync_orders_partial_failure(self):
        """部分订单同步失败"""
        from app.services.order_sync import OrderSyncService

        svc = MagicMock(spec=OrderSyncService)
        svc.db = AsyncMock()

        orders = [
            {
                "order_code": "ORD-001",
                "custom_code": "HS-001",
                "create_date": "2024-01-15",
                "floor_count": 10,
                "device_type": "X",
            },
            {
                "order_code": "ORD-002",
                "custom_code": "HS-002",
                "create_date": "2024-01-15",
                "floor_count": 20,
                "device_type": "N",
            },
        ]

        match_result = SyncResult(
            success=1, failed=1, skipped=0, unmatched=0, message="部分同步失败"
        )

        svc._fetch_orders = AsyncMock(return_value=orders)
        svc._match_and_save = AsyncMock(return_value=match_result)

        result = await OrderSyncService.sync_orders(svc, sync_date="2024-01-15")

        assert isinstance(result, SyncResult)
        assert result.success == 1
        assert result.failed == 1
        assert "部分同步失败" in result.message
