"""AnalyticsService 单元测试

覆盖：
- get_inactive_customers 日期计算（date 与 datetime 相减的修复）
- get_unit_prices 表缺失兜底
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import ProgrammingError

from app.services.analytics import AnalyticsService


class TestGetInactiveCustomers:
    """长期未消耗客户列表日期计算"""

    @pytest.fixture
    def service(self):
        db = AsyncMock()
        return AnalyticsService(db=db)

    async def _mock_rows(self, db, rows):
        result = MagicMock()
        result.all.return_value = rows
        db.execute.return_value = result

    async def test_days_calculated_with_datetime_last_consumption(self, service):
        """consumption_date 为 datetime（timestamptz）时正确计算天数

        回归：修复前 now(date) - last_consumption_date(datetime) 抛 TypeError
        """
        db = service.db
        last_date = datetime.utcnow() - timedelta(days=10)
        rows = [
            SimpleNamespace(
                id=1,
                company_id="1001",
                name="测试客户",
                manager_id=5,
                manager_name="运营A",
                last_consumption_date=last_date,
            )
        ]
        await self._mock_rows(db, rows)

        result = await service.get_inactive_customers(days=30)

        assert len(result) == 1
        assert result[0]["customer_id"] == 1
        assert result[0]["days"] == 10
        assert result[0]["last_consumption_date"] == last_date.isoformat()

    async def test_days_calculated_with_date_last_consumption(self, service):
        """consumption_date 为纯 date 时也能正确计算"""
        db = service.db
        last_date = (datetime.utcnow() - timedelta(days=5)).date()
        rows = [
            SimpleNamespace(
                id=2,
                company_id="1002",
                name="测试客户B",
                manager_id=None,
                manager_name=None,
                last_consumption_date=last_date,
            )
        ]
        await self._mock_rows(db, rows)

        result = await service.get_inactive_customers(days=30)

        assert result[0]["days"] == 5
        assert result[0]["manager_name"] == "未分配"

    async def test_no_last_consumption_falls_back_to_days(self, service):
        """无消耗日期时 days 回退为入参 days"""
        db = service.db
        rows = [
            SimpleNamespace(
                id=3,
                company_id="1003",
                name="测试客户C",
                manager_id=None,
                manager_name=None,
                last_consumption_date=None,
            )
        ]
        await self._mock_rows(db, rows)

        result = await service.get_inactive_customers(days=30)

        assert result[0]["days"] == 30
        assert result[0]["last_consumption_date"] is None


class TestGetUnitPrices:
    """单价配置读取"""

    @pytest.fixture
    def service(self):
        db = AsyncMock()
        return AnalyticsService(db=db)

    async def test_returns_rows_when_table_exists(self, service):
        """表存在且有数据时返回表内单价"""
        db = service.db
        result = MagicMock()
        result.scalars.return_value.all.return_value = [
            SimpleNamespace(device_type="L", unit_price=15.0),
            SimpleNamespace(device_type="N", unit_price=25.0),
        ]
        db.execute.return_value = result

        prices = await service.get_unit_prices()

        assert prices == {"L": 15.0, "N": 25.0}

    async def test_falls_back_to_defaults_when_table_missing(self, service):
        """表缺失（未跑迁移）时兜底返回默认单价，不抛 500"""
        db = service.db
        db.execute.side_effect = ProgrammingError(
            "relation forecast_unit_prices does not exist", {}, Exception()
        )

        prices = await service.get_unit_prices()

        # 默认值直接来自 config.py，避免期望值过时
        from app.config import get_settings

        expected = dict(get_settings().consumption_forecast_unit_prices)
        assert prices == expected

    async def test_falls_back_to_defaults_when_table_empty(self, service):
        """表存在但为空时回退默认单价"""
        db = service.db
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        db.execute.return_value = result

        prices = await service.get_unit_prices()

        from app.config import get_settings

        assert prices == dict(get_settings().consumption_forecast_unit_prices)


class TestGetCustomerHealthScore:
    """客户健康度评分排除规则测试"""

    @pytest.fixture
    def service(self):
        db = AsyncMock()
        return AnalyticsService(db=db)

    @staticmethod
    def _mock_customer(db, **attrs):
        """mock 首次 execute 返回客户查询结果"""
        customer = SimpleNamespace(**attrs)
        result = MagicMock()
        result.scalars.return_value.first.return_value = customer
        db.execute.return_value = result
        return customer

    @pytest.mark.asyncio
    async def test_excluded_when_not_settlement_enabled(self, service):
        """不结算客户（is_settlement_enabled=False）返回 score=None、not_applicable"""
        db = service.db
        self._mock_customer(db, id=1, is_settlement_enabled=False, account_type="正式账号")

        result = await service.get_customer_health_score(1)

        assert result["score"] is None
        assert result["health_level"] == "not_applicable"
        # 排除后不再执行评分计算查询
        assert db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_excluded_when_test_account(self, service):
        """客户测试账号返回 score=None、not_applicable"""
        db = service.db
        self._mock_customer(db, id=2, is_settlement_enabled=True, account_type="客户测试账号")

        result = await service.get_customer_health_score(2)

        assert result["score"] is None
        assert result["health_level"] == "not_applicable"
        assert db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_excluded_when_internal_account(self, service):
        """内部账号返回 score=None、not_applicable"""
        db = service.db
        self._mock_customer(db, id=3, is_settlement_enabled=True, account_type="内部账号")

        result = await service.get_customer_health_score(3)

        assert result["score"] is None
        assert result["health_level"] == "not_applicable"
        assert db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_normal_customer_still_scored(self, service):
        """正常客户（结算且为正式账号）不触发排除，评分照常计算"""
        db = service.db
        # 客户查询结果：结算且正式账号 → 不触发排除
        customer_result = MagicMock()
        customer_result.scalars.return_value.first.return_value = SimpleNamespace(
            id=4, is_settlement_enabled=True, account_type="正式账号"
        )
        # 后续评分查询：usage/pricing/baseline/balance/avg/payment 均 mock 为 0 或 None
        usage = MagicMock()
        usage.first.return_value = SimpleNamespace(total_quantity=0)
        pricing = MagicMock()
        # 服务层以 .scalars().first() 消费定价规则结果；None → 无阶梯配置 → 走历史基线
        pricing.scalars.return_value.first.return_value = None
        baseline = MagicMock()
        baseline.first.return_value = SimpleNamespace(total_quantity=0, earliest=None)
        balance = MagicMock()
        balance.first.return_value = SimpleNamespace(
            total_amount=100.0, real_amount=100.0, bonus_amount=0.0
        )
        avg = MagicMock()
        avg.first.return_value = SimpleNamespace(avg_amount=0)
        payment = MagicMock()
        payment.scalar.return_value = 0

        db.execute.side_effect = [
            customer_result,
            usage,
            pricing,
            baseline,
            balance,
            avg,
            payment,
            payment,
        ]

        result = await service.get_customer_health_score(4)

        assert result["score"] is not None
        assert result["health_level"] != "not_applicable"

    @pytest.mark.asyncio
    async def test_customer_not_found_raises(self, service):
        """客户不存在（含已删除）时抛 ValueError，不与「不参与评估」语义混淆"""
        db = service.db
        result = MagicMock()
        result.scalars.return_value.first.return_value = None
        db.execute.return_value = result

        with pytest.raises(ValueError, match="客户不存在或已删除"):
            await service.get_customer_health_score(999)

        # 查询客户即返回，不再执行任何评分查询
        assert db.execute.call_count == 1
