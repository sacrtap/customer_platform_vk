"""行业类型服务 - 行业类型 CRUD 操作"""

from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.industry_type import IndustryType


class IndustryTypeService:
    """行业类型业务逻辑"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all(self) -> list[IndustryType]:
        """获取所有未删除的行业类型，按 sort_order 升序"""
        stmt = (
            select(IndustryType)
            .where(IndustryType.deleted_at.is_(None))
            .order_by(IndustryType.sort_order.asc())
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: int) -> IndustryType | None:
        """根据 ID 获取行业类型"""
        stmt = select(IndustryType).where(
            IndustryType.id == id,
            IndustryType.deleted_at.is_(None),
        )
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, name: str, sort_order: int) -> IndustryType:
        """新增行业类型，校验名称唯一性"""
        # 检查名称是否已存在（排除已删除记录）
        existing = await self.db_session.execute(
            select(IndustryType).where(
                IndustryType.name == name,
                IndustryType.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"行业类型 '{name}' 已存在")

        industry_type = IndustryType(name=name, sort_order=sort_order)
        self.db_session.add(industry_type)
        await self.db_session.commit()
        await self.db_session.refresh(industry_type)
        return industry_type

    async def update(self, id: int, name: str, sort_order: int) -> IndustryType | None:
        """更新行业类型，校验名称唯一性"""
        industry_type = await self.get_by_id(id)
        if industry_type is None:
            return None

        # 检查名称是否已被其他记录使用（排除已删除记录）
        existing = await self.db_session.execute(
            select(IndustryType).where(
                IndustryType.name == name,
                IndustryType.id != id,
                IndustryType.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"行业类型 '{name}' 已存在")

        industry_type.name = name
        industry_type.sort_order = sort_order
        await self.db_session.commit()
        await self.db_session.refresh(industry_type)
        return industry_type

    async def soft_delete(self, id: int) -> bool:
        """软删除行业类型"""
        stmt = (
            update(IndustryType)
            .where(IndustryType.id == id, IndustryType.deleted_at.is_(None))
            .values(deleted_at=datetime.utcnow())
        )
        result = await self.db_session.execute(stmt)
        await self.db_session.commit()
        return result.rowcount > 0
