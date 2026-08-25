"""ERP 系统管理服务"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.erp_system import ErpSystem


class ErpSystemService:
    """ERP 系统服务类"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all(self) -> list[ErpSystem]:
        """获取所有 ERP 系统，按 sort_order 升序排列"""
        stmt = (
            select(ErpSystem)
            .where(ErpSystem.deleted_at.is_(None))
            .order_by(ErpSystem.sort_order.asc())
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: int) -> Optional[ErpSystem]:
        """根据 ID 获取 ERP 系统"""
        result = await self.db_session.execute(
            select(ErpSystem).where(
                ErpSystem.id == id,
                ErpSystem.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[ErpSystem]:
        """根据名称获取 ERP 系统（用于重复检查）"""
        result = await self.db_session.execute(
            select(ErpSystem).where(
                ErpSystem.name == name,
                ErpSystem.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_value(self, value: str) -> Optional[ErpSystem]:
        """根据存储值获取 ERP 系统（用于重复检查）"""
        result = await self.db_session.execute(
            select(ErpSystem).where(
                ErpSystem.value == value,
                ErpSystem.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, name: str, value: str, sort_order: int) -> ErpSystem:
        """
        创建 ERP 系统

        Raises:
            ValueError: 当名称或存储值已存在时
        """
        existing = await self.get_by_name(name)
        if existing:
            raise ValueError(f"ERP 系统名称 '{name}' 已存在")

        existing_value = await self.get_by_value(value)
        if existing_value:
            raise ValueError(f"ERP 系统存储值 '{value}' 已存在")

        erp_system = ErpSystem(
            name=name,
            value=value,
            sort_order=sort_order,
        )

        self.db_session.add(erp_system)
        await self.db_session.commit()
        await self.db_session.refresh(erp_system)

        return erp_system

    async def update(self, id: int, name: str, value: str, sort_order: int) -> Optional[ErpSystem]:
        """
        更新 ERP 系统

        Raises:
            ValueError: 当名称或存储值已存在（其他记录）时
        """
        erp_system = await self.get_by_id(id)
        if not erp_system:
            return None

        # 检查名称是否重复（排除当前记录和已删除记录）
        existing = await self.db_session.execute(
            select(ErpSystem).where(
                ErpSystem.name == name,
                ErpSystem.id != id,
                ErpSystem.deleted_at.is_(None),
            )
        )
        existing = existing.scalar_one_or_none()
        if existing:
            raise ValueError(f"ERP 系统名称 '{name}' 已存在")

        # 检查存储值是否重复
        existing_value = await self.db_session.execute(
            select(ErpSystem).where(
                ErpSystem.value == value,
                ErpSystem.id != id,
                ErpSystem.deleted_at.is_(None),
            )
        )
        existing_value = existing_value.scalar_one_or_none()
        if existing_value:
            raise ValueError(f"ERP 系统存储值 '{value}' 已存在")

        erp_system.name = name  # pyright: ignore[reportAttributeAccessIssue]
        erp_system.value = value  # pyright: ignore[reportAttributeAccessIssue]
        erp_system.sort_order = sort_order  # pyright: ignore[reportAttributeAccessIssue]

        await self.db_session.commit()
        await self.db_session.refresh(erp_system)

        return erp_system

    async def soft_delete(self, id: int) -> bool:
        """
        软删除 ERP 系统

        Returns:
            True: 删除成功
            False: ERP 系统不存在
        """
        erp_system = await self.get_by_id(id)
        if not erp_system:
            return False

        erp_system.deleted_at = datetime.utcnow()  # pyright: ignore[reportAttributeAccessIssue]
        await self.db_session.commit()

        return True
