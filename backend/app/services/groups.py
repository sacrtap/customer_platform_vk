"""客户群组管理服务"""

from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from sqlalchemy import select, func, and_, inspect
from ..models.groups import CustomerGroup, CustomerGroupMember
from ..models.customers import Customer


def _is_async_session(session) -> bool:
    """检查是否为异步 Session"""
    # 检查 Session 类型
    session_class_name = session.__class__.__name__
    return "AsyncSession" in session_class_name


class CustomerGroupService:
    """客户群组服务"""

    def __init__(self, db_session):
        self.db = db_session
        self._is_async = _is_async_session(db_session)

    async def _commit(self):
        """提交事务（支持同步/异步）"""
        if self._is_async:
            await self.db.commit()
        else:
            self.db.commit()

    async def create_group(
        self,
        name: str,
        description: Optional[str],
        group_type: str,
        filter_conditions: Optional[Dict[str, Any]],
        created_by: int,
    ) -> CustomerGroup:
        """创建群组

        Args:
            name: 群组名称
            description: 群组描述
            group_type: 群组类型 (dynamic/static)
            filter_conditions: 筛选条件（动态群组使用）
            created_by: 创建者 ID

        Returns:
            CustomerGroup: 创建的群组对象
        """
        group = CustomerGroup(
            name=name,
            description=description,
            group_type=group_type,
            filter_conditions=filter_conditions if group_type == "dynamic" else None,
            created_by=created_by,
        )
        self.db.add(group)
        await self._commit()
        return group

    async def get_user_groups(self, user_id: int) -> List[CustomerGroup]:
        """获取用户的群组列表

        Args:
            user_id: 用户 ID

        Returns:
            List[CustomerGroup]: 群组列表
        """
        stmt = (
            select(CustomerGroup)
            .where(
                CustomerGroup.created_by == user_id,
                CustomerGroup.deleted_at.is_(None),
            )
            .order_by(CustomerGroup.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_group_detail(self, group_id: int) -> Optional[CustomerGroup]:
        """获取群组详情

        Args:
            group_id: 群组 ID

        Returns:
            Optional[CustomerGroup]: 群组对象，不存在返回 None
        """
        stmt = select(CustomerGroup).where(
            CustomerGroup.id == group_id,
            CustomerGroup.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_group(self, group_id: int, data: dict) -> Optional[CustomerGroup]:
        """更新群组

        Args:
            group_id: 群组 ID
            data: 更新数据字典

        Returns:
            Optional[CustomerGroup]: 更新后的群组对象，不存在返回 None
        """
        group = await self.get_group_detail(group_id)
        if not group:
            return None

        # 可更新的字段
        updatable_fields = [
            "name",
            "description",
            "group_type",
            "filter_conditions",
        ]

        for key, value in data.items():
            if key in updatable_fields and hasattr(group, key):
                setattr(group, key, value)

        await self._commit()
        return group

    async def delete_group(self, group_id: int) -> bool:
        """删除群组（软删除）

        Args:
            group_id: 群组 ID

        Returns:
            bool: 删除成功返回 True，不存在返回 False
        """
        group = await self.get_group_detail(group_id)
        if not group:
            return False

        group.deleted_at = datetime.utcnow()
        await self._commit()
        return True

    async def add_member(self, group_id: int, customer_id: int) -> bool:
        """添加成员到静态群组

        Args:
            group_id: 群组 ID
            customer_id: 客户 ID

        Returns:
            bool: 添加成功返回 True，已存在返回 False
        """
        # 检查是否已存在
        stmt = select(CustomerGroupMember).where(
            CustomerGroupMember.group_id == group_id,
            CustomerGroupMember.customer_id == customer_id,
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            return False

        member = CustomerGroupMember(group_id=group_id, customer_id=customer_id)
        self.db.add(member)
        await self._commit()
        return True

    async def remove_member(self, group_id: int, customer_id: int) -> bool:
        """移除群组成员

        Args:
            group_id: 群组 ID
            customer_id: 客户 ID

        Returns:
            bool: 移除成功返回 True，不存在返回 False
        """
        stmt = select(CustomerGroupMember).where(
            CustomerGroupMember.group_id == group_id,
            CustomerGroupMember.customer_id == customer_id,
        )
        result = await self.db.execute(stmt)
        member = result.scalar_one_or_none()

        if not member:
            return False

        await self.db.delete(member)
        await self._commit()
        return True

    async def get_group_members(
        self, group_id: int, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Customer], int]:
        """获取群组成员列表

        Args:
            group_id: 群组 ID
            page: 页码
            page_size: 每页数量

        Returns:
            Tuple[List[Customer], int]: (客户列表，总数)
        """
        # 计数
        count_stmt = (
            select(func.count())
            .select_from(CustomerGroupMember)
            .where(CustomerGroupMember.group_id == group_id)
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # 查询成员
        stmt = (
            select(Customer)
            .join(CustomerGroupMember)
            .where(
                CustomerGroupMember.group_id == group_id,
                Customer.deleted_at.is_(None),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(stmt)
        customers = list(result.scalars().all())

        return customers, total

    async def apply_group_filter(
        self, group_id: int, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Customer], int]:
        """应用群组筛选

        Args:
            group_id: 群组 ID
            page: 页码
            page_size: 每页数量

        Returns:
            Tuple[List[Customer], int]: (客户列表，总数)
        """
        group = await self.get_group_detail(group_id)
        if not group:
            return [], 0

        if group.group_type == "static":
            # 静态群组：返回成员列表
            return await self.get_group_members(group_id, page, page_size)
        else:
            # 动态群组：应用筛选条件
            return await self._apply_dynamic_filter(
                group.filter_conditions, page, page_size
            )

    async def _apply_dynamic_filter(
        self, conditions: Optional[Dict[str, Any]], page: int, page_size: int
    ) -> Tuple[List[Customer], int]:
        """应用动态筛选条件

        Args:
            conditions: 筛选条件字典
            page: 页码
            page_size: 每页数量

        Returns:
            Tuple[List[Customer], int]: (客户列表，总数)
        """
        if not conditions:
            # 无条件：返回所有客户
            count_stmt = (
                select(func.count())
                .select_from(Customer)
                .where(Customer.deleted_at.is_(None))
            )
            total = (await self.db.execute(count_stmt)).scalar() or 0

            stmt = (
                select(Customer)
                .where(Customer.deleted_at.is_(None))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        else:
            # 构建筛选条件
            filters = []
            for key, value in conditions.items():
                if value is not None and hasattr(Customer, key):
                    filters.append(getattr(Customer, key) == value)

            if filters:
                count_stmt = (
                    select(func.count())
                    .select_from(Customer)
                    .where(and_(*filters), Customer.deleted_at.is_(None))
                )
                stmt = (
                    select(Customer)
                    .where(and_(*filters), Customer.deleted_at.is_(None))
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            else:
                # 条件无效时返回所有客户
                count_stmt = (
                    select(func.count())
                    .select_from(Customer)
                    .where(Customer.deleted_at.is_(None))
                )
                stmt = (
                    select(Customer)
                    .where(Customer.deleted_at.is_(None))
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )

            total = (await self.db.execute(count_stmt)).scalar() or 0

        result = await self.db.execute(stmt)
        customers = list(result.scalars().all())

        return customers, total

    async def get_group_stats(self, group_id: int) -> dict:
        """获取群组统计信息

        Args:
            group_id: 群组 ID

        Returns:
            dict: 统计信息字典
        """
        group = await self.get_group_detail(group_id)
        if not group:
            return {}

        if group.group_type == "static":
            # 静态群组：统计成员数
            count_stmt = (
                select(func.count())
                .select_from(CustomerGroupMember)
                .where(CustomerGroupMember.group_id == group_id)
            )
            member_count = (await self.db.execute(count_stmt)).scalar() or 0
        else:
            # 动态群组：实时计算
            _, member_count = await self.apply_group_filter(group_id, 1, 1)

        return {
            "id": group.id,
            "name": group.name,
            "group_type": group.group_type,
            "member_count": member_count,
        }
