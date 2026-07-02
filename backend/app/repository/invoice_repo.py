"""发票 Repository 实现"""

from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.billing import Invoice
from .base import BaseRepository
from .protocols import InvoiceRepositoryProtocol


class InvoiceRepository(BaseRepository[Invoice], InvoiceRepositoryProtocol):
    """发票 Repository"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Invoice)

    async def find_by_customer_id(
        self,
        customer_id: int,
        status: Optional[str] = None,
        include_deleted: bool = False,
    ) -> List[Invoice]:
        """根据客户 ID 查询发票"""
        stmt = self._base_query(include_deleted).where(Invoice.customer_id == customer_id)
        if status:
            stmt = stmt.where(Invoice.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_pending_invoices(self, customer_id: int) -> List[Invoice]:
        """查询待处理发票"""
        stmt = self._base_query().where(
            Invoice.customer_id == customer_id,
            Invoice.status.in_(["draft", "pending"]),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_total_amount(self, customer_id: int, status: Optional[str] = None) -> Decimal:
        """获取发票总金额"""
        stmt = select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(
            Invoice.customer_id == customer_id,
            Invoice.deleted_at.is_(None),
        )
        if status:
            stmt = stmt.where(Invoice.status == status)
        result = await self.db.execute(stmt)
        return Decimal(str(result.scalar()))
