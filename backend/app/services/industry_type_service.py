"""行业类型管理服务"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.customers import CustomerProfile
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
        """根据名称获取行业类型（用于重复检查，仅查未删除）"""
        result = await self.db_session.execute(
            select(IndustryType).where(
                IndustryType.name == name,
                IndustryType.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_any_by_name(self, name: str) -> list[IndustryType]:
        """按名称获取全部行业类型（含软删除记录）"""
        result = await self.db_session.execute(
            select(IndustryType).where(IndustryType.name == name)
        )
        return list(result.scalars().all())

    async def get_any_by_id(self, id: int) -> Optional[IndustryType]:
        """按 ID 获取行业类型（含软删除记录，用于主键重复校验）"""
        result = await self.db_session.execute(select(IndustryType).where(IndustryType.id == id))
        return result.scalar_one_or_none()

    async def _sync_id_sequence(self) -> None:
        """将 id 序列同步到当前最大值，防止显式指定 id 后自增撞主键"""
        max_id = (await self.db_session.execute(select(func.max(IndustryType.id)))).scalar()
        if max_id:
            await self.db_session.execute(
                text("SELECT setval(pg_get_serial_sequence('industry_types', 'id'), :max_id)"),
                {"max_id": max_id},
            )

    async def create(
        self,
        name: str,
        sort_order: int,
        id: Optional[int] = None,
    ) -> IndustryType:
        """
        创建行业类型

        行为：
        - 指定 id 时：按指定 id 创建（id 已被占用——含软删记录——则报错）
        - 未指定 id 时：自增生成
        - 仅存在软删除的同名记录时：恢复该记录（保留原 id 与客户引用），
          解决 name 唯一索引被软删记录占用导致「同名无法新增」的问题

        Raises:
            ValueError: 名称已存在、或指定的 id 已被占用
        """
        # 检查是否已存在相同名称（含软删记录——name 唯一索引对软删记录仍生效，
        # 仅查未删除会漏掉占用，导致 INSERT 撞数据库唯一约束报 500）
        matches = await self.get_any_by_name(name)
        active = [m for m in matches if m.deleted_at is None]
        if active:
            raise ValueError(f"行业类型名称 '{name}' 已存在")

        # 仅剩软删同名记录 → 恢复而非新建（保留原 id，客户引用不悬空）
        if matches:
            industry_type = matches[0]
            if id is not None and id != industry_type.id:
                raise ValueError(f"恢复已删除的同名行业时必须沿用原 ID {industry_type.id}")
            industry_type.deleted_at = None  # pyright: ignore[reportAttributeAccessIssue]
            industry_type.sort_order = sort_order  # pyright: ignore[reportAttributeAccessIssue]
            await self.db_session.commit()
            await self.db_session.refresh(industry_type)
            return industry_type

        # 指定 id 时校验唯一（含软删记录）
        if id is not None:
            if await self.get_any_by_id(id):
                raise ValueError(f"行业类型 ID {id} 已存在")
            industry_type = IndustryType(
                id=id,
                name=name,
                sort_order=sort_order,
            )
        else:
            industry_type = IndustryType(
                name=name,
                sort_order=sort_order,
            )

        self.db_session.add(industry_type)
        await self.db_session.commit()
        await self.db_session.refresh(industry_type)

        # 显式 id 可能越过当前序列值，同步序列避免后续自增撞主键
        if id is not None:
            await self._sync_id_sequence()
            await self.db_session.commit()

        return industry_type

    async def update(
        self,
        id: int,
        name: str,
        sort_order: int,
        new_id: Optional[int] = None,
    ) -> Optional[IndustryType]:
        """
        更新行业类型

        行为：
        - new_id 与 id 不同时：修改主键 id（目标 id 被其他记录占用则报错；
          被客户画像引用的行业禁止修改 id——改 id 会使 customer_profiles 外键
          悬空，与软删除引用保护同理）

        Raises:
            ValueError: 名称已存在（其他记录）、或目标 id 已被占用、或行业被客户引用
        """
        industry_type = await self.get_by_id(id)
        if not industry_type:
            return None

        # 检查名称是否重复：name 唯一索引覆盖软删记录（ix_industry_types_name unique），
        # 仅查未删除会漏掉占用，改名撞唯一约束报 500；与 create 的 get_any_by_name 一致
        matches = await self.get_any_by_name(name)
        if any(m.id != id for m in matches):
            raise ValueError(f"行业类型名称 '{name}' 已存在")

        # 修改主键 id：目标 id 占用校验（含软删记录）+ 引用保护
        if new_id is not None and new_id != id:
            if await self.get_any_by_id(new_id):
                raise ValueError(f"行业类型 ID {new_id} 已存在")
            # 引用保护：被 customer_profiles 引用的行业禁止修改 id，
            # 否则客户画像外键悬空（与 soft_delete 引用保护同理）
            ref_count = (
                await self.db_session.execute(
                    select(func.count())
                    .select_from(CustomerProfile)
                    .where(CustomerProfile.industry_type_id == id)
                )
            ).scalar()
            if ref_count:
                raise ValueError(
                    f"行业类型 '{industry_type.name}' 正被 {ref_count} 个客户使用，不能修改 ID"
                )
            industry_type.id = new_id  # pyright: ignore[reportAttributeAccessIssue]

        industry_type.name = name  # pyright: ignore[reportAttributeAccessIssue]
        industry_type.sort_order = sort_order  # pyright: ignore[reportAttributeAccessIssue]

        await self.db_session.commit()
        await self.db_session.refresh(industry_type)

        # 显式新 id 可能越过当前序列值，同步序列避免后续自增撞主键（未实际改 id 则跳过）
        if new_id is not None and new_id != id:
            await self._sync_id_sequence()
            await self.db_session.commit()

        return industry_type

    async def soft_delete(self, id: int) -> bool:
        """
        软删除行业类型

        Returns:
            True: 删除成功
            False: 行业类型不存在

        Raises:
            ValueError: 行业类型仍被客户画像引用（硬规则：共享主数据被引用禁止删除，
                避免客户列表行业列悬空、导出回灌时行业名失配）
        """
        industry_type = await self.get_by_id(id)
        if not industry_type:
            return False

        # 引用保护：被 customer_profiles.industry_type_id 引用的行业禁止删除。
        # 与导入侧（customers.py import）行业名→id 映射保持一致——行业一旦删除，
        # 客户画像仍持有其 id，列表 join 显示悬空，导出文件回灌时行业名失配报错。
        ref_count = (
            await self.db_session.execute(
                select(func.count())
                .select_from(CustomerProfile)
                .where(CustomerProfile.industry_type_id == id)
            )
        ).scalar()
        if ref_count:
            raise ValueError(
                f"行业类型 '{industry_type.name}' 正被 {ref_count} 个客户使用，不能删除"
            )

        # 注意：BaseModel.deleted_at 使用 TIMESTAMP WITHOUT TIME ZONE
        # 因此使用 datetime.utcnow() 而非 datetime.now(timezone.utc)
        # 以避免时区转换问题
        industry_type.deleted_at = datetime.utcnow()  # pyright: ignore[reportAttributeAccessIssue]
        await self.db_session.commit()

        return True
