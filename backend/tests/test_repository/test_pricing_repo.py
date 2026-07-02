"""PricingRepository 单元测试"""

from datetime import date

import pytest

from app.repository import PricingRepository


@pytest.mark.asyncio
class TestPricingRepository:
    """PricingRepository 测试类"""

    async def test_find_active_by_customer_id(self, db_session, sample_pricing_rule):
        """测试查询客户的有效定价规则"""
        repo = PricingRepository(db_session)

        result = await repo.find_active_by_customer_id(
            sample_pricing_rule.customer_id, date.today()
        )

        assert result is not None
        assert result.customer_id == sample_pricing_rule.customer_id

    async def test_find_active_by_customer_id_not_found(self, db_session):
        """测试查询不存在的有效定价规则"""
        repo = PricingRepository(db_session)

        result = await repo.find_active_by_customer_id(99999, date.today())

        assert result is None

    async def test_find_active_by_customer_id_expired(self, db_session, sample_pricing_rule):
        """测试查询已过期的定价规则"""
        repo = PricingRepository(db_session)

        # 使用过去的日期查询
        past_date = date(2020, 1, 1)
        result = await repo.find_active_by_customer_id(sample_pricing_rule.customer_id, past_date)

        # 应该找不到（因为规则生效日期在过去日期之后）
        assert result is None

    async def test_find_active_by_customer_id_future(self, db_session, sample_pricing_rule):
        """测试查询未来生效的定价规则"""
        repo = PricingRepository(db_session)

        # 使用未来的日期查询
        future_date = date(2030, 12, 31)
        result = await repo.find_active_by_customer_id(sample_pricing_rule.customer_id, future_date)

        # 应该能找到（因为规则生效日期在未来日期之前）
        assert result is not None
