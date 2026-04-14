"""
客户运营中台 - Analytics Service 单元测试

测试目标：
1. 消耗分析 - get_consumption_trend, get_top_customers, get_device_type_distribution
2. 回款分析 - get_payment_analysis, get_invoice_status_stats
3. 健康度分析 - get_customer_health_stats, get_balance_warning_list, get_inactive_customers
4. 画像分析 - get_industry_distribution, get_customer_level_stats, get_real_estate_stats
5. 预测回款 - predict_monthly_payment
6. 首页仪表盘 - get_dashboard_stats, get_dashboard_chart_data
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import date, datetime


class MockDBSession:
    """Mock 数据库会话（支持异步操作）"""

    def __init__(self):
        self.execute = AsyncMock()
        self._add_calls = []
        self._add_all_calls = []
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.refresh = AsyncMock()
        self._new = []

    def add(self, obj):
        """模拟 add 方法，跟踪新对象"""
        self._add_calls.append(obj)
        self._new.append(obj)

    def add_all(self, objects):
        """模拟 add_all 方法"""
        self._add_all_calls.append(objects)
        self._new.extend(objects)

    @property
    def new(self):
        return self._new

    class _AsyncCM:
        """异步上下文管理器"""

        def __await__(self):
            return iter([])

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    def begin(self):
        """模拟异步事务上下文"""
        return self._AsyncCM()


def make_mock_row(data):
    """创建具名 mock 行对象（支持属性访问和索引访问）

    Args:
        data: 字典或元组，如果是元组则按位置映射到预定义字段
    """
    row = MagicMock()

    # 支持索引访问 (row[0], row[1], ...)
    if isinstance(data, (list, tuple)):
        for i, value in enumerate(data):
            setattr(row, f"_{i}", value)
        # 只设置一次 __getitem__
        row.__getitem__ = MagicMock(side_effect=lambda i, d=data: d[i])

    if isinstance(data, dict):
        for key, value in data.items():
            setattr(row, key, value)
        return row

    # 元组数据，根据长度和上下文推断字段
    # 4 元素：(id, name, company_id, total_amount) - Top 客户查询
    if len(data) == 4:
        setattr(row, "id", data[0])
        setattr(row, "name", data[1])
        setattr(row, "company_id", data[2])
        setattr(row, "total_amount", data[3])
    # 3 元素：(year, month, total_amount) - 消耗趋势
    # 或 (device_type, total_quantity, total_amount) - 设备类型分布
    # 或 (status, count, total_amount) - 结算单状态统计
    # 或 (total_balance, real_balance, bonus_balance) - 仪表盘余额
    elif len(data) == 3:
        setattr(row, "year", data[0])
        setattr(row, "month", data[1])
        setattr(row, "total_amount", data[2])
        # 检查是否是设备类型分布 (device_type, total_quantity, total_amount)
        if isinstance(data[0], str) and data[0] in ["X", "N", "L"]:
            setattr(row, "device_type", data[0])
            setattr(row, "total_quantity", data[1])
            setattr(row, "total_amount", data[2])
        # 检查是否是结算单状态统计 (status, count, total_amount)
        elif isinstance(data[0], str) and data[0] in [
            "draft",
            "pending_customer",
            "paid",
            "completed",
            "cancelled",
        ]:
            setattr(row, "status", data[0])
            setattr(row, "count", data[1])
            setattr(row, "total_amount", data[2])
        # 检查是否是余额统计 (total_balance, real_balance, bonus_balance)
        elif isinstance(data[0], Decimal):
            setattr(row, "total_balance", data[0])
            setattr(row, "real_balance", data[1])
            setattr(row, "bonus_balance", data[2])
    # 2 元素：(device_type, total_quantity) 或 (status, count) 或 (industry, count) 或 (None, count) 等
    elif len(data) == 2:
        setattr(row, "_0", data[0])
        setattr(row, "_1", data[1])
        # 尝试推断字段名
        # None 表示未分类
        if data[0] is None:
            setattr(row, "level", "未分类")
            setattr(row, "customer_level", "未分类")
            setattr(row, "count", data[1])
        elif isinstance(data[0], str):
            # 设备类型
            if data[0] in ["X", "N", "L"]:
                setattr(row, "device_type", data[0])
                setattr(row, "total_quantity", data[1])
            # 结算单状态
            elif data[0] in [
                "draft",
                "pending_customer",
                "paid",
                "completed",
                "cancelled",
            ]:
                setattr(row, "status", data[0])
                setattr(row, "count", data[1])
            # 客户等级 (A, B, C, etc.) 或 None (未分类)
            elif data[0] in ["A", "B", "C", "D", "E"]:
                setattr(row, "level", data[0])
                setattr(row, "customer_level", data[0])
                setattr(row, "count", data[1])
            # None 表示未分类
            elif data[0] is None:
                setattr(row, "level", "未分类")
                setattr(row, "customer_level", "未分类")
                setattr(row, "count", data[1])
            # 行业分布、健康等级等
            else:
                setattr(row, "industry", data[0])
                setattr(row, "count", data[1])
                setattr(row, "health_level", data[0])
        setattr(row, "total_quantity", data[1])
        setattr(row, "count", data[1])
    # 1 元素：标量值
    elif len(data) == 1:
        setattr(row, "_0", data[0])
        setattr(row, "total_amount", data[0])
        setattr(row, "count", data[0])
    # 6 元素：(id, name, company_id, total_amount, real_amount, bonus_amount) - 余额预警
    # 或 (id, name, company_id, balance, threshold, amount_due) - 旧格式
    elif len(data) == 6:
        setattr(row, "id", data[0])
        setattr(row, "customer_id", data[0])
        setattr(row, "name", data[1])
        setattr(row, "customer_name", data[1])
        setattr(row, "company_id", data[2])
        # 检查是否是 Decimal 类型（余额预警）
        if isinstance(data[3], Decimal):
            setattr(row, "total_amount", data[3])
            setattr(row, "real_amount", data[4])
            setattr(row, "bonus_amount", data[5])
        else:
            setattr(row, "balance", data[3])
            setattr(row, "threshold", data[4])
            setattr(row, "amount_due", data[5])
    # 5 元素：(id, name, company_id, last_order_date, days_inactive) - 未下单客户
    # 或 (customer_id, customer_name, company_id, device_type, predicted_amount)
    # 或 (id, name, company_id, manager_id, manager_name) - 长期未消耗客户
    elif len(data) == 5:
        setattr(row, "id", data[0])
        setattr(row, "customer_id", data[0])
        setattr(row, "name", data[1])
        setattr(row, "customer_name", data[1])
        setattr(row, "company_id", data[2])
        setattr(row, "last_order_date", data[3])
        setattr(row, "days_inactive", data[4])
        setattr(row, "device_type", data[3])
        setattr(row, "predicted_amount", data[4])
        # 检查是否是长期未消耗客户查询
        if isinstance(data[3], int):
            setattr(row, "manager_id", data[3])
            # None 转换为 "未分配"
            if data[4] is None:
                setattr(row, "manager_name", "未分配")
            else:
                setattr(row, "manager_name", data[4])
    # 4 元素：(id, name, company_id, total_amount) - Top 客户/行业分布
    elif len(data) == 4:
        setattr(row, "id", data[0])
        setattr(row, "customer_id", data[0])
        setattr(row, "name", data[1])
        setattr(row, "company_id", data[2])
        setattr(row, "total_amount", data[3])
    # 7 元素：(id, name, company_id, device_type, pricing_type, unit_price, tiers) - 定价规则
    # 或 (id, name, company_id, device_type, pricing_model, unit_price, min_quantity)
    elif len(data) == 7:
        setattr(row, "id", data[0])
        setattr(row, "customer_id", data[0])
        setattr(row, "name", data[1])
        setattr(row, "customer_name", data[1])
        setattr(row, "company_id", data[2])
        setattr(row, "device_type", data[3])
        setattr(row, "pricing_type", data[4])
        setattr(row, "pricing_model", data[4])
        setattr(row, "unit_price", data[5])
        setattr(row, "min_quantity", data[6])
        setattr(row, "tiers", data[6])
    # 8 元素：(id, name, company_id, device_type, pricing_type, unit_price, tiers, package_type) - 定价规则
    # 或 (id, name, company_id, device_type, pricing_model, unit_price, min_quantity, max_quantity)
    elif len(data) == 8:
        setattr(row, "id", data[0])
        setattr(row, "customer_id", data[0])
        setattr(row, "name", data[1])
        setattr(row, "customer_name", data[1])
        setattr(row, "company_id", data[2])
        setattr(row, "device_type", data[3])
        setattr(row, "pricing_type", data[4])
        setattr(row, "pricing_model", data[4])
        setattr(row, "unit_price", data[5])
        setattr(row, "min_quantity", data[6])
        setattr(row, "max_quantity", data[7])
        setattr(row, "tiers", data[6])
        setattr(row, "package_type", data[7])

    return row


def make_mock_execute_result(rows, scalar_value=None):
    """创建 execute 返回结果

    Args:
        rows: 返回的行列表（可以是元组或字典）
        scalar_value: 标量值（用于 .scalar()），默认取 rows[0][0] 如果 rows 是元组列表
    """
    # 将元组转换为具名 mock 对象
    mock_rows = [
        (
            make_mock_row(row)
            if not hasattr(row, "__dict__") and not isinstance(row, MagicMock)
            else row
        )
        for row in rows
    ]

    result = MagicMock()
    result.all = MagicMock(return_value=mock_rows)
    result.scalar_one_or_none = MagicMock(return_value=mock_rows[0] if mock_rows else None)

    # 处理 .scalar() 调用（用于 count 查询）
    if scalar_value is not None:
        result.scalar = MagicMock(return_value=scalar_value)
    elif rows and isinstance(rows[0], (list, tuple)):
        result.scalar = MagicMock(return_value=rows[0][0])
    else:
        result.scalar = MagicMock(return_value=None)

    # 处理 .first() 调用
    result.first = MagicMock(return_value=mock_rows[0] if mock_rows else None)

    scalars_result = MagicMock()
    scalars_result.all = MagicMock(return_value=mock_rows)
    scalars_result.unique = MagicMock(return_value=scalars_result)
    result.scalars.return_value = scalars_result
    return result


# ==================== Fixtures ====================


@pytest.fixture
def mock_db():
    """创建 Mock 数据库会话"""
    return MockDBSession()


@pytest.fixture
def analytics_service(mock_db):
    """创建 AnalyticsService 实例"""
    from app.services.analytics import AnalyticsService

    service = AnalyticsService(mock_db)
    yield service, mock_db


# ==================== 消耗分析测试 ====================


class TestGetConsumptionTrend:
    """get_consumption_trend 测试"""

    async def test_get_consumption_trend_success(self, analytics_service):
        """测试获取消耗趋势成功"""
        service, mock_db = analytics_service

        mock_rows = [
            {"year": 2026, "month": 1, "total_amount": Decimal("10000.00")},
            {"year": 2026, "month": 2, "total_amount": Decimal("12000.00")},
            {"year": 2026, "month": 3, "total_amount": Decimal("15000.00")},
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_consumption_trend(
            start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)
        )

        assert len(result) == 3
        assert result[0]["year"] == 2026
        assert result[0]["month"] == 1
        assert result[0]["period"] == "2026-01"
        assert result[0]["total_amount"] == 10000.00
        assert result[1]["total_amount"] == 12000.00
        assert result[2]["total_amount"] == 15000.00

    async def test_get_consumption_trend_with_customer_filter(self, analytics_service):
        """测试按客户 ID 筛选消耗趋势"""
        service, mock_db = analytics_service

        mock_rows = [{"year": 2026, "month": 3, "total_amount": Decimal("5000.00")}]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_consumption_trend(
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            customer_id=100,
        )

        assert len(result) == 1
        assert result[0]["total_amount"] == 5000.00

    async def test_get_consumption_trend_empty(self, analytics_service):
        """测试空结果"""
        service, mock_db = analytics_service

        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.get_consumption_trend(
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)
        )

        assert len(result) == 0

    async def test_get_consumption_trend_with_null_amount(self, analytics_service):
        """测试包含 null 金额的情况"""
        service, mock_db = analytics_service

        mock_rows = [
            {"year": 2026, "month": 1, "total_amount": None},
            {"year": 2026, "month": 2, "total_amount": Decimal("1000.00")},
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_consumption_trend(
            start_date=date(2026, 1, 1), end_date=date(2026, 2, 28)
        )

        assert len(result) == 2
        assert result[0]["total_amount"] == 0.0
        assert result[1]["total_amount"] == 1000.00


class TestGetTopCustomers:
    """get_top_customers 测试"""

    async def test_get_top_customers_success(self, analytics_service):
        """测试获取 Top 客户成功"""
        service, mock_db = analytics_service

        mock_rows = [
            (1, "客户 A", "COMP001", Decimal("50000.00")),
            (2, "客户 B", "COMP002", Decimal("30000.00")),
            (3, "客户 C", "COMP003", Decimal("20000.00")),
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_top_customers(
            start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), limit=10
        )

        assert len(result) == 3
        assert result[0]["customer_id"] == 1
        assert result[0]["customer_name"] == "客户 A"
        assert result[0]["company_id"] == "COMP001"
        assert result[0]["total_amount"] == 50000.00
        assert result[1]["total_amount"] == 30000.00

    async def test_get_top_customers_limit(self, analytics_service):
        """测试限制返回数量"""
        service, mock_db = analytics_service

        mock_rows = [
            (1, "客户 A", "COMP001", Decimal("50000.00")),
            (2, "客户 B", "COMP002", Decimal("30000.00")),
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_top_customers(
            start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), limit=2
        )

        assert len(result) == 2

    async def test_get_top_customers_empty(self, analytics_service):
        """测试空结果"""
        service, mock_db = analytics_service

        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.get_top_customers(
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)
        )

        assert len(result) == 0


class TestGetDeviceTypeDistribution:
    """get_device_type_distribution 测试"""

    async def test_get_device_type_distribution_success(self, analytics_service):
        """测试获取设备类型分布成功"""
        service, mock_db = analytics_service

        mock_rows = [
            ("X", Decimal("1000"), Decimal("10000.00")),
            ("N", Decimal("500"), Decimal("7500.00")),
            ("L", Decimal("200"), Decimal("4000.00")),
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_device_type_distribution(
            start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)
        )

        assert len(result) == 3
        assert result[0]["device_type"] == "X"
        assert result[0]["total_quantity"] == 1000.0
        assert result[0]["total_amount"] == 10000.00
        assert result[1]["device_type"] == "N"
        assert result[2]["device_type"] == "L"

    async def test_get_device_type_distribution_with_customer_filter(self, analytics_service):
        """测试按客户 ID 筛选设备类型分布"""
        service, mock_db = analytics_service

        mock_rows = [("X", Decimal("500"), Decimal("5000.00"))]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_device_type_distribution(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            customer_id=100,
        )

        assert len(result) == 1
        assert result[0]["device_type"] == "X"

    async def test_get_device_type_distribution_empty(self, analytics_service):
        """测试空结果"""
        service, mock_db = analytics_service

        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.get_device_type_distribution(
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)
        )

        assert len(result) == 0


# ==================== 回款分析测试 ====================


class TestGetInvoiceStatusStats:
    """get_invoice_status_stats 测试"""

    async def test_get_invoice_status_stats_success(self, analytics_service):
        """测试获取结算单状态统计成功"""
        service, mock_db = analytics_service

        mock_rows = [
            ("draft", 5, Decimal("5000.00")),
            ("pending_customer", 3, Decimal("3000.00")),
            ("paid", 10, Decimal("10000.00")),
            ("completed", 8, Decimal("8000.00")),
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_invoice_status_stats(
            start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)
        )

        assert len(result) == 4
        assert result[0]["status"] == "draft"
        assert result[0]["count"] == 5
        assert result[0]["total_amount"] == 5000.00
        assert result[1]["status"] == "pending_customer"
        assert result[2]["status"] == "paid"

    async def test_get_invoice_status_stats_empty(self, analytics_service):
        """测试空结果"""
        service, mock_db = analytics_service

        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.get_invoice_status_stats(
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)
        )

        assert len(result) == 0

    async def test_get_invoice_status_stats_with_null_amount(self, analytics_service):
        """测试包含 null 金额"""
        service, mock_db = analytics_service

        mock_rows = [("draft", 0, None)]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_invoice_status_stats(
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)
        )

        assert len(result) == 1
        assert result[0]["count"] == 0
        assert result[0]["total_amount"] == 0.0


# ==================== 健康度分析测试 ====================


class TestGetCustomerHealthStats:
    """get_customer_health_stats 测试"""

    async def test_get_customer_health_stats_success(self, analytics_service):
        """测试获取客户健康度统计成功"""
        service, mock_db = analytics_service

        # 模拟 2 次查询：stats 聚合 + churn 计数
        stats_row = MagicMock()
        stats_row.total_count = 100
        stats_row.active_count = 50
        stats_row.warning_count = 10
        mock_db.execute.side_effect = [
            make_mock_execute_result([stats_row]),  # stats 聚合查询
            make_mock_execute_result([], scalar_value=15),  # churn 计数
        ]

        result = await service.get_customer_health_stats()

        assert result["total_customers"] == 100
        assert result["active_customers"] == 50
        assert result["inactive_customers"] == 50
        assert result["warning_customers"] == 10
        assert result["churn_risk_customers"] == 15
        assert result["active_rate"] == 50.0

    async def test_get_customer_health_stats_no_recent_customers(self, analytics_service):
        """测试无最近消耗客户（全部为流失风险）"""
        service, mock_db = analytics_service

        stats_row = MagicMock()
        stats_row.total_count = 50
        stats_row.active_count = 30
        stats_row.warning_count = 5
        mock_db.execute.side_effect = [
            make_mock_execute_result([stats_row]),  # stats 聚合查询
            make_mock_execute_result([], scalar_value=20),  # churn 计数
        ]

        result = await service.get_customer_health_stats()

        assert result["total_customers"] == 50
        assert result["active_customers"] == 30
        assert result["churn_risk_customers"] == 20

    async def test_get_customer_health_stats_all_recent(self, analytics_service):
        """测试所有客户最近都有消耗（无流失风险）"""
        service, mock_db = analytics_service

        stats_row = MagicMock()
        stats_row.total_count = 50
        stats_row.active_count = 30
        stats_row.warning_count = 5
        mock_db.execute.side_effect = [
            make_mock_execute_result([stats_row]),  # stats 聚合查询
            make_mock_execute_result([], scalar_value=0),  # churn 计数
        ]

        result = await service.get_customer_health_stats()

        assert result["churn_risk_customers"] == 0

    async def test_get_customer_health_stats_zero_total(self, analytics_service):
        """测试总客户数为 0 的情况"""
        service, mock_db = analytics_service

        stats_row = MagicMock()
        stats_row.total_count = 0
        stats_row.active_count = 0
        stats_row.warning_count = 0
        mock_db.execute.side_effect = [
            make_mock_execute_result([stats_row]),  # stats 聚合查询
            make_mock_execute_result([], scalar_value=0),  # churn 计数
        ]

        result = await service.get_customer_health_stats()

        assert result["total_customers"] == 0
        assert result["active_rate"] == 0  # 避免除零错误


class TestGetBalanceWarningList:
    """get_balance_warning_list 测试"""

    async def test_get_balance_warning_list_success(self, analytics_service):
        """测试获取余额预警客户列表成功"""
        service, mock_db = analytics_service

        mock_rows = [
            (
                1,
                "客户 A",
                "COMP001",
                Decimal("500.00"),
                Decimal("400.00"),
                Decimal("100.00"),
            ),
            (
                2,
                "客户 B",
                "COMP002",
                Decimal("800.00"),
                Decimal("600.00"),
                Decimal("200.00"),
            ),
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_balance_warning_list(threshold=1000)

        assert len(result) == 2
        assert result[0]["customer_id"] == 1
        assert result[0]["customer_name"] == "客户 A"
        assert result[0]["company_id"] == "COMP001"
        assert result[0]["total_amount"] == 500.00
        assert result[0]["real_amount"] == 400.00
        assert result[0]["bonus_amount"] == 100.00
        assert result[1]["total_amount"] == 800.00

    async def test_get_balance_warning_list_empty(self, analytics_service):
        """测试空结果（无预警客户）"""
        service, mock_db = analytics_service

        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.get_balance_warning_list(threshold=1000)

        assert len(result) == 0

    async def test_get_balance_warning_list_custom_threshold(self, analytics_service):
        """测试自定义阈值"""
        service, mock_db = analytics_service

        mock_rows = [
            (
                1,
                "客户 A",
                "COMP001",
                Decimal("2000.00"),
                Decimal("1500.00"),
                Decimal("500.00"),
            ),
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_balance_warning_list(threshold=5000)

        assert len(result) == 1
        assert result[0]["total_amount"] == 2000.00


class TestGetInactiveCustomers:
    """get_inactive_customers 测试"""

    async def test_get_inactive_customers_success(self, analytics_service):
        """测试获取长期未消耗客户成功"""
        service, mock_db = analytics_service

        # 优化后：单次查询（使用子查询）
        mock_rows = [
            (1, "客户 A", "COMP001", 1, "经理 A"),
            (2, "客户 B", "COMP002", 2, None),  # manager_name 为 None
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_inactive_customers(days=90)

        assert len(result) == 2
        assert result[0]["customer_id"] == 1
        assert result[0]["customer_name"] == "客户 A"
        assert result[0]["manager_name"] == "经理 A"
        assert result[1]["customer_id"] == 2
        assert result[1]["manager_name"] == "未分配"  # None 转为"未分配"

    async def test_get_inactive_customers_all_recent(self, analytics_service):
        """测试所有客户最近都有消耗"""
        service, mock_db = analytics_service

        # 优化后：单次查询，返回空结果
        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.get_inactive_customers(days=90)

        assert len(result) == 0

    async def test_get_inactive_customers_empty(self, analytics_service):
        """测试无任何消耗记录的客户"""
        service, mock_db = analytics_service

        # 优化后：单次查询，返回空结果
        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.get_inactive_customers(days=90)

        assert len(result) == 0


# ==================== 画像分析测试 ====================


class TestGetIndustryDistribution:
    """get_industry_distribution 测试"""

    async def test_get_industry_distribution_success(self, analytics_service):
        """测试获取行业分布成功"""
        service, mock_db = analytics_service

        mock_rows = [
            ("房地产", 30),
            ("制造业", 25),
            ("零售业", 20),
            ("未分类", 5),
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_industry_distribution()

        assert len(result) == 4
        total = 80
        assert result[0]["industry"] == "房地产"
        assert result[0]["count"] == 30
        assert result[0]["percentage"] == round(30 / total * 100, 2)
        assert result[1]["industry"] == "制造业"
        assert result[2]["industry"] == "零售业"

    async def test_get_industry_distribution_empty(self, analytics_service):
        """测试空结果"""
        service, mock_db = analytics_service

        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.get_industry_distribution()

        assert len(result) == 0

    async def test_get_industry_distribution_single(self, analytics_service):
        """测试只有一个行业"""
        service, mock_db = analytics_service

        mock_rows = [("房地产", 100)]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_industry_distribution()

        assert len(result) == 1
        assert result[0]["percentage"] == 100.0


class TestGetCustomerLevelStats:
    """get_customer_level_stats 测试"""

    async def test_get_customer_level_stats_success(self, analytics_service):
        """测试获取客户等级统计成功"""
        service, mock_db = analytics_service

        mock_rows = [
            ("A", 50),
            ("B", 30),
            ("C", 15),
            (None, 5),  # 未分类
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_customer_level_stats()

        assert len(result) == 4
        assert result[0]["level"] == "A"
        assert result[0]["count"] == 50
        assert result[0]["percentage"] == round(50 / 100 * 100, 2)
        assert result[3]["level"] == "未分类"  # None 转为"未分类"

    async def test_get_customer_level_stats_empty(self, analytics_service):
        """测试空结果"""
        service, mock_db = analytics_service

        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.get_customer_level_stats()

        assert len(result) == 0


class TestGetRealEstateStats:
    """get_real_estate_stats 测试"""

    async def test_get_real_estate_stats_success(self, analytics_service):
        """测试获取房产客户统计成功"""
        service, mock_db = analytics_service

        mock_db.execute.side_effect = [
            make_mock_execute_result([], scalar_value=100),  # total
            make_mock_execute_result([], scalar_value=40),  # real_estate
        ]

        result = await service.get_real_estate_stats()

        assert result["total_customers"] == 100
        assert result["real_estate_customers"] == 40
        assert result["non_real_estate_customers"] == 60
        assert result["real_estate_percentage"] == 40.0

    async def test_get_real_estate_stats_zero_total(self, analytics_service):
        """测试总客户数为 0"""
        service, mock_db = analytics_service

        mock_db.execute.side_effect = [
            make_mock_execute_result([], scalar_value=0),  # total
            make_mock_execute_result([], scalar_value=0),  # real_estate
        ]

        result = await service.get_real_estate_stats()

        assert result["total_customers"] == 0
        assert result["real_estate_percentage"] == 0  # 避免除零错误


# ==================== 预测回款测试 ====================


class TestPredictMonthlyPayment:
    """predict_monthly_payment 测试"""

    async def test_predict_monthly_payment_success(self, analytics_service):
        """测试预测月度回款成功"""
        service, mock_db = analytics_service

        # 定价规则查询结果
        pricing_rows = [
            (1, "客户 A", "COMP001", "X", "fixed", Decimal("10.00"), None, None),
        ]
        # 用量查询结果
        usage_rows = [("X", Decimal("1000"))]

        mock_db.execute.side_effect = [
            make_mock_execute_result(pricing_rows),  # 定价规则
            make_mock_execute_result(usage_rows),  # 用量
        ]

        result = await service.predict_monthly_payment(year=2026, month=4)

        assert len(result) == 1
        assert result[0]["customer_id"] == 1
        assert result[0]["customer_name"] == "客户 A"
        assert result[0]["device_type"] == "X"
        assert result[0]["quantity"] == 1000.0
        assert result[0]["pricing_type"] == "fixed"
        assert result[0]["predicted_amount"] == 10000.00  # 1000 * 10

    async def test_predict_monthly_payment_with_customer_filter(self, analytics_service):
        """测试按客户 ID 筛选预测"""
        service, mock_db = analytics_service

        pricing_rows = [(1, "客户 A", "COMP001", "X", "fixed", Decimal("10.00"), None, None)]
        usage_rows = [("X", Decimal("500"))]

        mock_db.execute.side_effect = [
            make_mock_execute_result(pricing_rows),
            make_mock_execute_result(usage_rows),
        ]

        result = await service.predict_monthly_payment(year=2026, month=4, customer_id=1)

        assert len(result) == 1
        assert result[0]["quantity"] == 500.0
        assert result[0]["predicted_amount"] == 5000.00

    async def test_predict_monthly_payment_empty_pricing(self, analytics_service):
        """测试无定价规则"""
        service, mock_db = analytics_service

        mock_db.execute.return_value = make_mock_execute_result([])

        result = await service.predict_monthly_payment(year=2026, month=4)

        assert len(result) == 0

    async def test_predict_monthly_payment_tiered_pricing(self, analytics_service):
        """测试阶梯定价预测"""
        service, mock_db = analytics_service

        tiers = [
            {"threshold": 100, "price": 10},
            {"threshold": 500, "price": 8},
        ]
        pricing_rows = [(1, "客户 A", "COMP001", "X", "tiered", Decimal("5.00"), tiers, None)]
        usage_rows = [("X", Decimal("600"))]

        mock_db.execute.side_effect = [
            make_mock_execute_result(pricing_rows),
            make_mock_execute_result(usage_rows),
        ]

        result = await service.predict_monthly_payment(year=2026, month=4)

        assert len(result) == 1
        # 100 * 10 + 500 * 8 = 1000 + 4000 = 5000
        assert result[0]["predicted_amount"] == 5000.00

    async def test_predict_monthly_payment_package_pricing(self, analytics_service):
        """测试套餐定价预测"""
        service, mock_db = analytics_service

        pricing_rows = [(1, "客户 A", "COMP001", "L", "package", Decimal("0"), None, "A")]
        usage_rows = [("L", Decimal("1000"))]

        mock_db.execute.side_effect = [
            make_mock_execute_result(pricing_rows),
            make_mock_execute_result(usage_rows),
        ]

        result = await service.predict_monthly_payment(year=2026, month=4)

        assert len(result) == 1
        assert result[0]["predicted_amount"] == 10000.00  # 套餐 A 价格


# ==================== 首页仪表盘测试 ====================


class TestGetDashboardStats:
    """get_dashboard_stats 测试"""

    async def test_get_dashboard_stats_success(self, analytics_service):
        """测试获取仪表盘统计数据成功"""
        service, mock_db = analytics_service

        # 优化后：单次聚合查询
        with patch("app.services.analytics.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2026, 4, 3, 12, 0, 0)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            stats_row = MagicMock()
            stats_row.total_customers = 100
            stats_row.key_customers = 20
            stats_row.total_balance = Decimal("50000.00")
            stats_row.real_balance = Decimal("40000.00")
            stats_row.bonus_balance = Decimal("10000.00")
            stats_row.month_invoice_count = 15
            stats_row.pending_confirmation = 5
            stats_row.month_consumption = Decimal("25000.00")

            mock_db.execute.return_value = make_mock_execute_result([stats_row])

            result = await service.get_dashboard_stats()

            assert result["total_customers"] == 100
            assert result["key_customers"] == 20
            assert result["total_balance"] == 50000.00
            assert result["real_balance"] == 40000.00
            assert result["bonus_balance"] == 10000.00
            assert result["month_invoice_count"] == 15
            assert result["pending_confirmation"] == 5
            assert result["month_consumption"] == 25000.00

    async def test_get_dashboard_stats_empty(self, analytics_service):
        """测试空数据"""
        service, mock_db = analytics_service

        with patch("app.services.analytics.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2026, 4, 3, 12, 0, 0)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            stats_row = MagicMock()
            stats_row.total_customers = 0
            stats_row.key_customers = 0
            stats_row.total_balance = None
            stats_row.real_balance = None
            stats_row.bonus_balance = None
            stats_row.month_invoice_count = 0
            stats_row.pending_confirmation = 0
            stats_row.month_consumption = None

            mock_db.execute.return_value = make_mock_execute_result([stats_row])

            result = await service.get_dashboard_stats()

            assert result["total_customers"] == 0
            assert result["key_customers"] == 0
            assert result["total_balance"] == 0.0
            assert result["month_consumption"] == 0.0


class TestGetDashboardChartData:
    """get_dashboard_chart_data 测试"""

    async def test_get_dashboard_chart_data_success(self, analytics_service):
        """测试获取仪表盘图表数据成功"""
        service, mock_db = analytics_service

        # Mock 消耗趋势
        consumption_trend_data = [
            {"period": "2025-11", "total_amount": 10000.00},
            {"period": "2025-12", "total_amount": 12000.00},
            {"period": "2026-01", "total_amount": 15000.00},
        ]

        # Mock 回款分析数据
        payment_data = {
            "total_invoiced": 10000.00,
            "total_paid": 8000.00,
            "completion_rate": 80.0,
        }

        with patch.object(service, "get_consumption_trend", return_value=consumption_trend_data):
            with patch.object(service, "get_payment_analysis", return_value=payment_data):
                result = await service.get_dashboard_chart_data(months=3)

                assert "consumption_trend" in result
                assert "payment_trend" in result
                assert len(result["consumption_trend"]) == 3
                assert len(result["payment_trend"]) == 3
                assert result["payment_trend"][0]["invoiced"] == 10000.00
                assert result["payment_trend"][0]["paid"] == 8000.00


# ==================== 辅助方法测试 ====================


class TestCalculatePredictedAmount:
    """_calculate_predicted_amount 辅助方法测试"""

    async def test_calculate_fixed_pricing(self, analytics_service):
        """测试固定价格计算"""
        service, mock_db = analytics_service

        result = await service._calculate_predicted_amount(
            pricing_type="fixed",
            unit_price=10.00,
            tiers=None,
            package_type=None,
            quantity=100,
        )

        assert result == 1000.00

    async def test_calculate_tiered_pricing_single_tier(self, analytics_service):
        """测试单阶梯定价计算"""
        service, mock_db = analytics_service

        tiers = [{"threshold": 500, "price": 8}]

        result = await service._calculate_predicted_amount(
            pricing_type="tiered",
            unit_price=10.00,
            tiers=tiers,
            package_type=None,
            quantity=300,
        )

        # 300 < 500, 所以 300 * 8 = 2400
        assert result == 2400.00

    async def test_calculate_tiered_pricing_multiple_tiers(self, analytics_service):
        """测试多阶梯定价计算"""
        service, mock_db = analytics_service

        tiers = [
            {"threshold": 100, "price": 10},
            {"threshold": 500, "price": 8},
        ]

        result = await service._calculate_predicted_amount(
            pricing_type="tiered",
            unit_price=5.00,
            tiers=tiers,
            package_type=None,
            quantity=600,
        )

        # 100 * 10 + 500 * 8 + (600-600) * 5 = 1000 + 4000 = 5000
        assert result == 5000.00

    async def test_calculate_package_pricing_type_a(self, analytics_service):
        """测试套餐 A 定价"""
        service, mock_db = analytics_service

        result = await service._calculate_predicted_amount(
            pricing_type="package",
            unit_price=0,
            tiers=None,
            package_type="A",
            quantity=1000,
        )

        assert result == 10000.00

    async def test_calculate_package_pricing_type_b(self, analytics_service):
        """测试套餐 B 定价"""
        service, mock_db = analytics_service

        result = await service._calculate_predicted_amount(
            pricing_type="package",
            unit_price=0,
            tiers=None,
            package_type="B",
            quantity=1000,
        )

        assert result == 20000.00

    async def test_calculate_package_pricing_type_c(self, analytics_service):
        """测试套餐 C 定价"""
        service, mock_db = analytics_service

        result = await service._calculate_predicted_amount(
            pricing_type="package",
            unit_price=0,
            tiers=None,
            package_type="C",
            quantity=1000,
        )

        assert result == 30000.00

    async def test_calculate_package_pricing_type_d(self, analytics_service):
        """测试套餐 D 定价"""
        service, mock_db = analytics_service

        result = await service._calculate_predicted_amount(
            pricing_type="package",
            unit_price=0,
            tiers=None,
            package_type="D",
            quantity=1000,
        )

        assert result == 50000.00

    async def test_calculate_unknown_package_type(self, analytics_service):
        """测试未知套餐类型"""
        service, mock_db = analytics_service

        result = await service._calculate_predicted_amount(
            pricing_type="package",
            unit_price=0,
            tiers=None,
            package_type="Z",
            quantity=1000,
        )

        assert result == 0

    async def test_calculate_default_fallback(self, analytics_service):
        """测试默认回退计算"""
        service, mock_db = analytics_service

        result = await service._calculate_predicted_amount(
            pricing_type="unknown",
            unit_price=15.00,
            tiers=None,
            package_type=None,
            quantity=100,
        )

        assert result == 1500.00


# ==================== 边缘情况测试 ====================


class TestEdgeCases:
    """边缘情况测试"""

    async def test_get_consumption_trend_single_month(self, analytics_service):
        """测试单月消耗趋势"""
        service, mock_db = analytics_service

        mock_rows = [(2026, 3, Decimal("10000.00"))]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_consumption_trend(
            start_date=date(2026, 3, 1), end_date=date(2026, 3, 31)
        )

        assert len(result) == 1
        assert result[0]["period"] == "2026-03"
        assert result[0]["total_amount"] == 10000.00

    async def test_get_top_customers_tie(self, analytics_service):
        """测试 Top 客户金额相同"""
        service, mock_db = analytics_service

        mock_rows = [
            (1, "客户 A", "COMP001", Decimal("10000.00")),
            (2, "客户 B", "COMP002", Decimal("10000.00")),
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_top_customers(
            start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), limit=2
        )

        assert len(result) == 2
        assert result[0]["total_amount"] == result[1]["total_amount"]

    async def test_get_balance_warning_list_boundary(self, analytics_service):
        """测试余额预警边界值"""
        service, mock_db = analytics_service

        # 余额正好等于阈值，不应该出现在预警列表中
        mock_rows = [
            (
                1,
                "客户 A",
                "COMP001",
                Decimal("999.99"),
                Decimal("800.00"),
                Decimal("199.99"),
            ),
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_balance_warning_list(threshold=1000)

        assert len(result) == 1
        assert result[0]["total_amount"] == 999.99

    async def test_get_customer_health_stats_all_zero(self, analytics_service):
        """测试所有统计为 0"""
        service, mock_db = analytics_service

        mock_db.execute.side_effect = [
            make_mock_execute_result([], scalar_value=0),
            make_mock_execute_result([], scalar_value=0),
            make_mock_execute_result([], scalar_value=0),
            make_mock_execute_result([]),
            make_mock_execute_result([]),
        ]

        result = await service.get_customer_health_stats()

        assert result["total_customers"] == 0
        assert result["active_customers"] == 0
        assert result["warning_customers"] == 0
        assert result["churn_risk_customers"] == 0
        assert result["active_rate"] == 0

    async def test_get_industry_distribution_percentage_sum(self, analytics_service):
        """测试行业分布百分比总和"""
        service, mock_db = analytics_service

        mock_rows = [
            ("房地产", 50),
            ("制造业", 30),
            ("零售业", 20),
        ]
        mock_db.execute.return_value = make_mock_execute_result(mock_rows)

        result = await service.get_industry_distribution()

        total_percentage = sum(item["percentage"] for item in result)
        assert abs(total_percentage - 100.0) < 0.01  # 允许浮点误差


# ==================== 余额趋势测试 ====================


class TestBalanceTrendService:
    """get_balance_trend 测试"""

    async def test_get_balance_trend_success(self, analytics_service):
        """测试获取余额趋势成功 - 返回 6 个月数据"""
        service, mock_db = analytics_service

        with patch("app.services.analytics.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2026, 4, 15, 12, 0, 0)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            # 模拟 5 次查询：当前余额 + 充值记录 + 结算单 + 历史充值 + 历史结算
            balance_row = MagicMock()
            balance_row.total_amount = Decimal("50000.00")
            balance_row.real_amount = Decimal("40000.00")
            balance_row.bonus_amount = Decimal("10000.00")

            recharge_row1 = MagicMock()
            recharge_row1.year = 2026
            recharge_row1.month = 3
            recharge_row1.real_amount = Decimal("5000.00")
            recharge_row1.bonus_amount = Decimal("1000.00")

            recharge_row2 = MagicMock()
            recharge_row2.year = 2026
            recharge_row2.month = 2
            recharge_row2.real_amount = Decimal("3000.00")
            recharge_row2.bonus_amount = Decimal("500.00")

            recharge_rows = [recharge_row1, recharge_row2]

            invoice_row1 = MagicMock()
            invoice_row1.year = 2026
            invoice_row1.month = 3
            invoice_row1.total_amount = Decimal("8000.00")

            invoice_row2 = MagicMock()
            invoice_row2.year = 2026
            invoice_row2.month = 2
            invoice_row2.total_amount = Decimal("6000.00")

            invoice_rows = [invoice_row1, invoice_row2]

            # 历史充值 - 返回 None
            hist_recharge_row = MagicMock()
            hist_recharge_row.real_amount = None
            hist_recharge_row.bonus_amount = None

            # 历史结算 - 返回 None
            hist_invoice_row = MagicMock()
            hist_invoice_row.total_amount = None

            mock_db.execute.side_effect = [
                make_mock_execute_result([balance_row]),  # 当前余额
                make_mock_execute_result(recharge_rows),  # 充值记录
                make_mock_execute_result(invoice_rows),  # 结算单
                make_mock_execute_result([hist_recharge_row]),  # 历史充值
                make_mock_execute_result([hist_invoice_row]),  # 历史结算
            ]

            result = await service.get_balance_trend(customer_id=1, months=6)

            assert len(result) == 6
            # 验证返回字段
            for item in result:
                assert "month" in item
                assert "total_amount" in item
                assert "real_amount" in item
                assert "bonus_amount" in item

    async def test_get_balance_trend_no_data(self, analytics_service):
        """测试无余额数据时返回空列表"""
        service, mock_db = analytics_service

        with patch("app.services.analytics.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2026, 4, 15, 12, 0, 0)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            # 当前余额为 None
            balance_row = MagicMock()
            balance_row.total_amount = None
            balance_row.real_amount = None
            balance_row.bonus_amount = None

            mock_db.execute.side_effect = [
                make_mock_execute_result([balance_row]),  # 当前余额为 None，直接返回空列表
            ]

            result = await service.get_balance_trend(customer_id=1, months=6)

            assert result == []


# ==================== 客户健康度评分测试 ====================


class TestCustomerHealthScoreService:
    """get_customer_health_score 测试"""

    async def test_get_health_score_success(self, analytics_service):
        """测试获取健康度评分成功"""
        service, mock_db = analytics_service

        with patch("app.services.analytics.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2026, 4, 15, 12, 0, 0)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            # 模拟查询：
            # 1. DailyUsage 聚合（近30天实际用量）
            usage_row = MagicMock()
            usage_row.total_quantity = Decimal("800")

            # 2. PricingRule（从 tiers 提取预期用量）
            pricing_row = MagicMock()
            pricing_row.tiers = [
                {"threshold": 500, "price": 10},
                {"threshold": 1000, "price": 8},
            ]

            # 3. CustomerBalance（当前余额）
            balance_row = MagicMock()
            balance_row.total_amount = Decimal("15000.00")
            balance_row.real_amount = Decimal("12000.00")
            balance_row.bonus_amount = Decimal("3000.00")

            # 4. 月均消耗（过去90天平均）
            avg_consumption_row = MagicMock()
            avg_consumption_row.avg_amount = Decimal("5000.00")

            # 5. 总结算单数
            total_invoices_row = MagicMock()
            total_invoices_row.total_count = 10

            # 6. 按时付款结算单数
            paid_invoices_row = MagicMock()
            paid_invoices_row.paid_count = 8

            mock_db.execute.side_effect = [
                make_mock_execute_result([usage_row]),  # 实际用量
                make_mock_execute_result([pricing_row]),  # 定价规则
                make_mock_execute_result([balance_row]),  # 当前余额
                make_mock_execute_result([avg_consumption_row]),  # 月均消耗
                make_mock_execute_result([], scalar_value=10),  # 总结算单数
                make_mock_execute_result([], scalar_value=8),  # 按时付款数
            ]

            result = await service.get_customer_health_score(customer_id=1)

            # 验证返回结构
            assert "score" in result
            assert "usage_rate" in result
            assert "balance_rate" in result
            assert "payment_rate" in result
            assert "health_level" in result

            # 用量达标率 = min(800/1000, 1.0) * 100 = 80 (从 tiers[-1].threshold=1000)
            assert result["usage_rate"] == 80.0
            # 余额充足率 = min(15000/5000, 1.0) * 100 = 100
            assert result["balance_rate"] == 100.0
            # 回款及时率 = 8/10 * 100 = 80
            assert result["payment_rate"] == 80.0
            # 健康度 = 80*0.5 + 100*0.3 + 80*0.2 = 40 + 30 + 16 = 86
            assert result["score"] == 86.0
            assert result["health_level"] == "healthy"

    async def test_get_health_score_no_data(self, analytics_service):
        """测试无数据时返回默认值"""
        service, mock_db = analytics_service

        with patch("app.services.analytics.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2026, 4, 15, 12, 0, 0)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            # 所有查询返回 None/0
            mock_db.execute.side_effect = [
                make_mock_execute_result([MagicMock(total_quantity=None)]),
                make_mock_execute_result([MagicMock(expected_quantity=None)]),
                make_mock_execute_result([MagicMock(total_amount=None)]),
                make_mock_execute_result([MagicMock(avg_amount=None)]),
                make_mock_execute_result([MagicMock(total_count=0)]),
                make_mock_execute_result([MagicMock(paid_count=0)]),
            ]

            result = await service.get_customer_health_score(customer_id=1)

            assert result["score"] == 0.0
            assert result["usage_rate"] == 0.0
            assert result["balance_rate"] == 0.0
            assert result["payment_rate"] == 0.0
            assert result["health_level"] == "unhealthy"
