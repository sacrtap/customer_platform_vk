"""余额 Repository 实现"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.billing import CustomerBalance
from .base import BaseRepository
from .protocols import BalanceRepositoryProtocol


class BalanceRepository(BaseRepository[CustomerBalance], BalanceRepositoryProtocol):
    """余额 Repository"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, CustomerBalance)

    async def get_by_customer_id(self, customer_id: int) -> Optional[CustomerBalance]:
        """根据客户 ID 获取余额"""
        stmt = self._base_query().where(CustomerBalance.customer_id == customer_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, customer_id: int) -> CustomerBalance:
        """获取或创建余额记录"""
        balance = await self.get_by_customer_id(customer_id)
        if balance:
            return balance

        balance = CustomerBalance(customer_id=customer_id)
        self.db.add(balance)
        await self.db.flush()
        return balance
