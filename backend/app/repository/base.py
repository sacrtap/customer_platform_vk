"""基础 Repository 实现"""

from datetime import datetime
from typing import Any, Generic, List, Optional, Sequence, Type, TypeVar

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """基础 Repository 实现"""

    def __init__(self, db: AsyncSession, model: Type[T]):
        self.db = db
        self.model = model

    def _base_query(self, include_deleted: bool = False):
        """构建基础查询，自动处理软删除过滤"""
        stmt = select(self.model)
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))
        return stmt

    async def find_by_id(
        self,
        id: int,
        include_deleted: bool = False,
        options: Optional[Sequence[Any]] = None,
    ) -> Optional[T]:
        """根据 ID 查询，支持 eager loading options"""
        stmt = self._base_query(include_deleted).where(self.model.id == id)
        if options:
            stmt = stmt.options(*options)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_all(
        self, include_deleted: bool = False, limit: int = 100, offset: int = 0, **filters
    ) -> List[T]:
        """查询所有记录，支持过滤和分页"""
        stmt = self._base_query(include_deleted)

        for key, value in filters.items():
            if value is not None and hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)

        stmt = stmt.offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self, include_deleted: bool = False, **filters) -> int:
        """统计记录数"""
        stmt = select(func.count(self.model.id))
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))

        for key, value in filters.items():
            if value is not None and hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)

        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def create(self, entity: T) -> T:
        """创建记录"""
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def update(self, entity: T) -> T:
        """更新记录"""
        entity.updated_at = datetime.utcnow()
        await self.db.flush()
        return entity

    async def soft_delete(self, id: int) -> bool:
        """软删除记录"""
        stmt = (
            update(self.model)
            .where(self.model.id == id, self.model.deleted_at.is_(None))
            .values(deleted_at=datetime.utcnow())
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0
