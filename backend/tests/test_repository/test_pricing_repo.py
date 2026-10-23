"""PricingRepository 单元测试"""

from datetime import date, datetime
from decimal import Decimal

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

    async def test_create_rule_without_json_columns_uses_empty_list_default(
        self, db_session, sample_customer
    ):
        """回归：tiers/package_limits 为 NOT NULL JSON 列，未显式传值必须落空列表而非 NULL

        两列在模型中无 nullable=True；若 ORM 侧无 default，未传值的构造会 INSERT NULL
        触发 NotNullViolationError（2026-10 修复：模型加 default=list）。
        生产路径 create_pricing_rule 用 data.get("tiers")，API 不带该字段时同样依赖此默认。
        """
        from datetime import datetime

        from app.models.billing import PricingRule

        rule = PricingRule(
            customer_id=sample_customer.id,
            device_type="X",
            layer_type="single",
            pricing_type="fixed",
            unit_price=Decimal("100.00"),
            effective_date=datetime.utcnow(),
        )
        db_session.add(rule)
        await db_session.commit()
        await db_session.refresh(rule)

        assert rule.tiers == []
        assert rule.package_limits == []

    async def test_create_pricing_rule_service_normalizes_none_json_columns(
        self, db_session, sample_customer
    ):
        """回归：create_pricing_rule 的 data.get("tiers") 为 None 时必须落空列表

        ORM `default=list` 只覆盖「属性未设置」，显式传 None 仍 INSERT NULL；
        而 ORM 对 Mapped[Any] 推断 nullable=False → 测试库 NotNullViolation，
        生产库（历史迁移建的 nullable=YES）不炸 → 行为漂移。
        服务层 `or []` 归一是唯一同时收敛两侧的修法（2026-10-23）。
        """
        from app.repository import PricingRepository
        from app.services.billing import PricingService

        service = PricingService(pricing_repo=PricingRepository(db_session))
        rule = await service.create_pricing_rule(
            {
                "customer_id": sample_customer.id,
                "device_type": "X",
                "layer_type": "single",
                "pricing_type": "fixed",
                "unit_price": Decimal("100.00"),
                "effective_date": datetime.utcnow(),
                # 故意不带 tiers / package_limits（等价于 API 请求缺这两个字段）
            }
        )

        assert rule.tiers == []
        assert rule.package_limits == []
