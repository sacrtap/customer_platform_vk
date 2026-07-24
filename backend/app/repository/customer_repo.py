"""客户 Repository 实现"""

from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.customers import Customer
from .base import BaseRepository
from .protocols import CustomerRepositoryProtocol


class CustomerRepository(BaseRepository[Customer], CustomerRepositoryProtocol):
    """客户 Repository"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Customer)

    async def find_by_company_id(
        self, company_id: int, include_deleted: bool = False
    ) -> Optional[Customer]:
        """根据公司 ID 查询客户"""
        stmt = self._base_query(include_deleted).where(Customer.company_id == company_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_manager_id(
        self, manager_id: int, include_deleted: bool = False
    ) -> List[Customer]:
        """根据客户经理 ID 查询"""
        stmt = self._base_query(include_deleted).where(Customer.manager_id == manager_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search(self, keyword: str, include_deleted: bool = False) -> List[Customer]:
        """搜索客户（名称、公司 ID 模糊匹配）"""
        stmt = self._base_query(include_deleted).where(
            or_(
                Customer.name.ilike(f"%{keyword}%"),
                Customer.company_id.cast(str).ilike(f"%{keyword}%"),  # pyright: ignore[reportArgumentType]
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
