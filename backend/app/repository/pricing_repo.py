"""定价规则 Repository 实现"""

from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.billing import PricingRule
from .base import BaseRepository
from .protocols import PricingRepositoryProtocol


class PricingRepository(BaseRepository[PricingRule], PricingRepositoryProtocol):
    """定价规则 Repository"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, PricingRule)

    async def find_active_by_customer_id(
        self, customer_id: int, effective_date: date
    ) -> Optional[PricingRule]:
        """查询指定日期生效的定价规则"""
        stmt = (
            self._base_query()
            .where(
                PricingRule.customer_id == customer_id,
                PricingRule.effective_date <= effective_date,
            )
            .order_by(PricingRule.effective_date.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
