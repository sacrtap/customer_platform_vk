"""字典服务 - 行业类型等字典数据查询"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.industry_type import IndustryType


class DictService:
    """字典数据服务"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_industry_types(self) -> list[IndustryType]:
        """获取所有行业类型，按 sort_order 升序排列"""
        stmt = (
            select(IndustryType)
            .where(IndustryType.deleted_at.is_(None))
            .order_by(IndustryType.sort_order.asc())
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())
