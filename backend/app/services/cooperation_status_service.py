"""合作状态管理服务"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.cooperation_status import CooperationStatus


class CooperationStatusService:
    """合作状态服务类"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all(self) -> list[CooperationStatus]:
        """获取所有合作状态，按 sort_order 升序排列"""
        stmt = (
            select(CooperationStatus)
            .where(CooperationStatus.deleted_at.is_(None))
            .order_by(CooperationStatus.sort_order.asc())
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: int) -> Optional[CooperationStatus]:
        """根据 ID 获取合作状态"""
        result = await self.db_session.execute(
            select(CooperationStatus).where(
                CooperationStatus.id == id,
                CooperationStatus.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[CooperationStatus]:
        """根据名称获取合作状态（用于重复检查）"""
        result = await self.db_session.execute(
            select(CooperationStatus).where(
                CooperationStatus.name == name,
                CooperationStatus.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_value(self, value: str) -> Optional[CooperationStatus]:
        """根据存储值获取合作状态（用于重复检查）"""
        result = await self.db_session.execute(
            select(CooperationStatus).where(
                CooperationStatus.value == value,
                CooperationStatus.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, name: str, value: str, sort_order: int) -> CooperationStatus:
        """
        创建合作状态

        Raises:
            ValueError: 当合作状态名称或值已存在时
        """
        # 检查名称是否已存在
        existing_name = await self.get_by_name(name)
        if existing_name:
            raise ValueError(f"合作状态名称 '{name}' 已存在")

        # 检查值是否已存在
        existing_value = await self.get_by_value(value)
        if existing_value:
            raise ValueError(f"合作状态值 '{value}' 已存在")

        cooperation_status = CooperationStatus(
            name=name,
            value=value,
            sort_order=sort_order,
        )

        self.db_session.add(cooperation_status)
        await self.db_session.commit()
        await self.db_session.refresh(cooperation_status)

        return cooperation_status

    async def update(
        self, id: int, name: str, value: str, sort_order: int
    ) -> Optional[CooperationStatus]:
        """
        更新合作状态

        Raises:
            ValueError: 当合作状态名称或值已存在（其他记录）时
        """
        cooperation_status = await self.get_by_id(id)
        if not cooperation_status:
            return None

        # 检查名称是否重复（排除当前记录和已删除记录）
        existing_name = await self.db_session.execute(
            select(CooperationStatus).where(
                CooperationStatus.name == name,
                CooperationStatus.id != id,
                CooperationStatus.deleted_at.is_(None),
            )
        )
        existing_name = existing_name.scalar_one_or_none()
        if existing_name:
            raise ValueError(f"合作状态名称 '{name}' 已存在")

        # 检查值是否重复（排除当前记录和已删除记录）
        existing_value = await self.db_session.execute(
            select(CooperationStatus).where(
                CooperationStatus.value == value,
                CooperationStatus.id != id,
                CooperationStatus.deleted_at.is_(None),
            )
        )
        existing_value = existing_value.scalar_one_or_none()
        if existing_value:
            raise ValueError(f"合作状态值 '{value}' 已存在")

        cooperation_status.name = name  # pyright: ignore[reportAttributeAccessIssue]
        cooperation_status.value = value  # pyright: ignore[reportAttributeAccessIssue]
        cooperation_status.sort_order = sort_order  # pyright: ignore[reportAttributeAccessIssue]

        await self.db_session.commit()
        await self.db_session.refresh(cooperation_status)

        return cooperation_status

    async def soft_delete(self, id: int) -> bool:
        """
        软删除合作状态

        Returns:
            True: 删除成功
            False: 合作状态不存在
        """
        cooperation_status = await self.get_by_id(id)
        if not cooperation_status:
            return False

        # 注意：BaseModel.deleted_at 使用 TIMESTAMP WITHOUT TIME ZONE
        # 因此使用 datetime.utcnow() 而非 datetime.now(timezone.utc)
        # 以避免时区转换问题
        cooperation_status.deleted_at = datetime.utcnow()  # pyright: ignore[reportAttributeAccessIssue]
        await self.db_session.commit()

        return True
