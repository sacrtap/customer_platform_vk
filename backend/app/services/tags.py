"""标签管理服务"""

from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from ..models.tags import Tag, CustomerTag, ProfileTag
from ..models.customers import Customer, CustomerProfile


class TagService:
    """标签服务类"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    # ========== 标签管理 ==========

    async def get_tag_by_id(self, tag_id: int) -> Optional[Tag]:
        """根据 ID 获取标签"""
        result = await self.db.execute(
            select(Tag).where(Tag.id == tag_id, Tag.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_all_tags(
        self,
        page: int = 1,
        page_size: int = 20,
        tag_type: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Tuple[List[Tag], int]:
        """
        获取标签列表（支持筛选和分页）

        Args:
            page: 页码
            page_size: 每页数量
            tag_type: 标签类型 (customer/profile)
            category: 标签分类

        Returns:
            (tags, total)
        """
        stmt = select(Tag).where(Tag.deleted_at.is_(None))

        conditions = []
        if tag_type:
            conditions.append(Tag.type == tag_type)
        if category:
            conditions.append(Tag.category == category)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar()

        stmt = stmt.order_by(Tag.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        tags = result.scalars().all()

        return list(tags), total

    async def create_tag(self, data: dict, created_by: int) -> Tag:
        """创建标签"""
        tag = Tag(
            name=data["name"],
            type=data["type"],
            category=data.get("category"),
            created_by=created_by,
        )

        self.db.add(tag)
        await self.db.commit()
        await self.db.refresh(tag)

        return tag

    async def update_tag(self, tag_id: int, data: dict) -> Optional[Tag]:
        """更新标签"""
        tag = await self.get_tag_by_id(tag_id)
        if not tag:
            return None

        updatable_fields = ["name", "category"]
        for field in updatable_fields:
            if field in data:
                setattr(tag, field, data[field])

        await self.db.commit()
        await self.db.refresh(tag)

        return tag

    async def delete_tag(self, tag_id: int) -> bool:
        """删除标签（软删除）"""
        tag = await self.get_tag_by_id(tag_id)
        if not tag:
            return False

        tag.deleted_at = func.now()
        await self.db.commit()

        return True

    async def get_tag_usage_count(self, tag_id: int) -> dict:
        """获取标签使用次数"""
        customer_count = await self.db.execute(
            select(func.count())
            .select_from(CustomerTag)
            .where(CustomerTag.tag_id == tag_id, CustomerTag.deleted_at.is_(None))
        )
        customer_count = customer_count.scalar()

        profile_count = await self.db.execute(
            select(func.count())
            .select_from(ProfileTag)
            .where(ProfileTag.tag_id == tag_id, ProfileTag.deleted_at.is_(None))
        )
        profile_count = profile_count.scalar()

        return {"customer_count": customer_count, "profile_count": profile_count}

    # ========== 客户标签管理 ==========

    async def get_customer_tags(self, customer_id: int) -> List[Tag]:
        """获取客户的所有标签"""
        result = await self.db.execute(
            select(Tag)
            .join(CustomerTag, Tag.id == CustomerTag.tag_id)
            .where(
                CustomerTag.customer_id == customer_id,
                CustomerTag.deleted_at.is_(None),
                Tag.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def add_customer_tag(self, customer_id: int, tag_id: int) -> bool:
        """给客户添加标签"""
        customer = await self.db.execute(
            select(Customer).where(
                Customer.id == customer_id, Customer.deleted_at.is_(None)
            )
        )
        if not customer.scalar_one_or_none():
            return False

        tag = await self.get_tag_by_id(tag_id)
        if not tag:
            return False

        existing = await self.db.execute(
            select(CustomerTag).where(
                CustomerTag.customer_id == customer_id,
                CustomerTag.tag_id == tag_id,
                CustomerTag.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            return True

        customer_tag = CustomerTag(customer_id=customer_id, tag_id=tag_id)
        self.db.add(customer_tag)
        await self.db.commit()

        return True

    async def remove_customer_tag(self, customer_id: int, tag_id: int) -> bool:
        """移除客户标签"""
        result = await self.db.execute(
            select(CustomerTag).where(
                CustomerTag.customer_id == customer_id,
                CustomerTag.tag_id == tag_id,
                CustomerTag.deleted_at.is_(None),
            )
        )
        customer_tag = result.scalar_one_or_none()

        if not customer_tag:
            return False

        customer_tag.deleted_at = func.now()
        await self.db.commit()

        return True

    async def batch_add_customer_tags(
        self, customer_ids: List[int], tag_ids: List[int]
    ) -> Tuple[int, int]:
        """
        批量给客户添加标签

        Args:
            customer_ids: 客户 ID 列表
            tag_ids: 标签 ID 列表

        Returns:
            (success_count, error_count)
        """
        success_count = 0
        error_count = 0

        for customer_id in customer_ids:
            customer = await self.db.execute(
                select(Customer).where(
                    Customer.id == customer_id, Customer.deleted_at.is_(None)
                )
            )
            if not customer.scalar_one_or_none():
                error_count += 1
                continue

            for tag_id in tag_ids:
                tag = await self.get_tag_by_id(tag_id)
                if not tag:
                    error_count += 1
                    continue

                existing = await self.db.execute(
                    select(CustomerTag).where(
                        CustomerTag.customer_id == customer_id,
                        CustomerTag.tag_id == tag_id,
                        CustomerTag.deleted_at.is_(None),
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                customer_tag = CustomerTag(customer_id=customer_id, tag_id=tag_id)
                self.db.add(customer_tag)
                success_count += 1

        await self.db.commit()
        return success_count, error_count

    async def batch_remove_customer_tags(
        self, customer_ids: List[int], tag_ids: List[int]
    ) -> int:
        """
        批量移除客户标签

        Args:
            customer_ids: 客户 ID 列表
            tag_ids: 标签 ID 列表

        Returns:
            removed_count
        """
        removed_count = 0

        for customer_id in customer_ids:
            for tag_id in tag_ids:
                result = await self.db.execute(
                    select(CustomerTag).where(
                        CustomerTag.customer_id == customer_id,
                        CustomerTag.tag_id == tag_id,
                        CustomerTag.deleted_at.is_(None),
                    )
                )
                customer_tag = result.scalar_one_or_none()

                if customer_tag:
                    customer_tag.deleted_at = func.now()
                    removed_count += 1

        await self.db.commit()
        return removed_count

    # ========== 画像标签管理 ==========

    async def get_profile_tags(self, profile_id: int) -> List[Tag]:
        """获取画像的所有标签"""
        result = await self.db.execute(
            select(Tag)
            .join(ProfileTag, Tag.id == ProfileTag.tag_id)
            .where(
                ProfileTag.profile_id == profile_id,
                ProfileTag.deleted_at.is_(None),
                Tag.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def add_profile_tag(self, profile_id: int, tag_id: int) -> bool:
        """给画像添加标签"""
        profile = await self.db.execute(
            select(CustomerProfile).where(
                CustomerProfile.id == profile_id, CustomerProfile.deleted_at.is_(None)
            )
        )
        if not profile.scalar_one_or_none():
            return False

        tag = await self.get_tag_by_id(tag_id)
        if not tag:
            return False

        existing = await self.db.execute(
            select(ProfileTag).where(
                ProfileTag.profile_id == profile_id,
                ProfileTag.tag_id == tag_id,
                ProfileTag.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            return True

        profile_tag = ProfileTag(profile_id=profile_id, tag_id=tag_id)
        self.db.add(profile_tag)
        await self.db.commit()

        return True

    async def remove_profile_tag(self, profile_id: int, tag_id: int) -> bool:
        """移除画像标签"""
        result = await self.db.execute(
            select(ProfileTag).where(
                ProfileTag.profile_id == profile_id,
                ProfileTag.tag_id == tag_id,
                ProfileTag.deleted_at.is_(None),
            )
        )
        profile_tag = result.scalar_one_or_none()

        if not profile_tag:
            return False

        profile_tag.deleted_at = func.now()
        await self.db.commit()

        return True
