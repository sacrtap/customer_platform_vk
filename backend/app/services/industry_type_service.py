"""行业类型管理服务"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.industry_type import IndustryType


class IndustryTypeService:
    """行业类型服务类"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all(self) -> list[IndustryType]:
        """获取所有行业类型，按 sort_order 升序排列"""
        stmt = (
            select(IndustryType)
            .where(IndustryType.deleted_at.is_(None))
            .order_by(IndustryType.sort_order.asc())
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: int) -> Optional[IndustryType]:
        """根据 ID 获取行业类型"""
        result = await self.db_session.execute(
            select(IndustryType).where(
                IndustryType.id == id,
                IndustryType.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[IndustryType]:
        """根据名称获取行业类型（用于重复检查）"""
        result = await self.db_session.execute(
            select(IndustryType).where(
                IndustryType.name == name,
                IndustryType.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, name: str, sort_order: int) -> IndustryType:
        """
        创建行业类型

        Raises:
            ValueError: 当行业类型名称已存在时
        """
        # 检查是否已存在相同名称
        existing = await self.get_by_name(name)
        if existing:
            raise ValueError(f"行业类型名称 '{name}' 已存在")

        industry_type = IndustryType(
            name=name,
            sort_order=sort_order,
        )

        self.db_session.add(industry_type)
        await self.db_session.commit()
        await self.db_session.refresh(industry_type)

        return industry_type

    async def update(self, id: int, name: str, sort_order: int) -> Optional[IndustryType]:
        """
        更新行业类型

        Raises:
            ValueError: 当行业类型名称已存在（其他记录）时
        """
        industry_type = await self.get_by_id(id)
        if not industry_type:
            return None

        # 检查名称是否重复（排除当前记录和已删除记录）
        existing = await self.db_session.execute(
            select(IndustryType).where(
                IndustryType.name == name,
                IndustryType.id != id,
                IndustryType.deleted_at.is_(None),
            )
        )
        existing = existing.scalar_one_or_none()
        if existing:
            raise ValueError(f"行业类型名称 '{name}' 已存在")

        industry_type.name = name  # pyright: ignore[reportAttributeAccessIssue]
        industry_type.sort_order = sort_order  # pyright: ignore[reportAttributeAccessIssue]

        await self.db_session.commit()
        await self.db_session.refresh(industry_type)

        return industry_type

    async def soft_delete(self, id: int) -> bool:
        """
        软删除行业类型

        Returns:
            True: 删除成功
            False: 行业类型不存在
        """
        industry_type = await self.get_by_id(id)
        if not industry_type:
            return False

        # 注意：BaseModel.deleted_at 使用 TIMESTAMP WITHOUT TIME ZONE
        # 因此使用 datetime.utcnow() 而非 datetime.now(timezone.utc)
        # 以避免时区转换问题
        industry_type.deleted_at = datetime.utcnow()  # pyright: ignore[reportAttributeAccessIssue]
        await self.db_session.commit()

        return True
