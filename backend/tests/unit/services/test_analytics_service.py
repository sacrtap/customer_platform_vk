"""AnalyticsService 单元测试

覆盖：
- get_inactive_customers 日期计算（date 与 datetime 相减的修复）
- get_unit_prices 表缺失兜底
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

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
        db.execute.side_effect = Exception("relation forecast_unit_prices does not exist")

        prices = await service.get_unit_prices()

        # 默认值来自 config.py consumption_forecast_unit_prices
        assert prices == {"L": 14.5, "N": 30.0, "X": 30.0}

    async def test_falls_back_to_defaults_when_table_empty(self, service):
        """表存在但为空时回退默认单价"""
        db = service.db
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        db.execute.return_value = result

        prices = await service.get_unit_prices()

        assert prices == {"L": 14.5, "N": 30.0, "X": 30.0}
