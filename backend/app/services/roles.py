"""角色管理服务"""

from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ..models.users import Role, Permission, role_permissions
from sqlalchemy import delete


class RoleService:
    """角色服务类"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all_roles(self, page: int = 1, page_size: int = 20) -> Tuple[List[Role], int]:
        """获取所有角色（分页）"""
        # 计算总数
        count_query = select(func.count()).select_from(Role)
        total_result = await self.db_session.execute(count_query)
        total = total_result.scalar() or 0

        # 查询数据
        query = select(Role).order_by(Role.id)
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db_session.execute(query)
        roles = list(result.scalars().all())

        return roles, total

    async def get_role_by_id(self, role_id: int) -> Optional[Role]:
        """根据 ID 获取角色"""
        query = select(Role).where(Role.id == role_id)
        query = query.options(selectinload(Role.permissions))
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_role_by_name(self, name: str) -> Optional[Role]:
        """根据名称获取角色"""
        query = select(Role).where(Role.name == name)
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def create_role(
        self,
        name: str,
        description: str = "",
        permission_ids: Optional[List[int]] = None,
    ) -> Role:
        """创建角色"""
        # 检查名称是否已存在
        existing = await self.get_role_by_name(name)
        if existing:
            raise ValueError(f"角色 '{name}' 已存在")

        role = Role(name=name, description=description)
        self.db_session.add(role)
        await self.db_session.flush()

        # 分配权限
        if permission_ids:
            await self.assign_permissions(role.id, permission_ids)

        await self.db_session.commit()
        await self.db_session.refresh(role)

        return role

    async def update_role(
        self,
        role_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        permission_ids: Optional[List[int]] = None,
    ) -> Optional[Role]:
        """更新角色"""
        role = await self.get_role_by_id(role_id)
        if not role:
            return None

        # 系统角色不能修改名称
        if role.is_system and name and name != role.name:
            raise ValueError("系统角色不能修改名称")

        if name is not None:
            # 检查新名称是否已被使用
            existing = await self.get_role_by_name(name)
            if existing and existing.id != role_id:
                raise ValueError(f"角色 '{name}' 已存在")
            role.name = name

        if description is not None:
            role.description = description

        # 更新权限
        if permission_ids is not None:
            # 先删除现有权限关联
            await self.db_session.execute(
                delete(role_permissions).where(role_permissions.c.role_id == role_id)
            )
            # 添加新权限
            for perm_id in permission_ids:
                await self.db_session.execute(
                    role_permissions.insert().values(role_id=role_id, permission_id=perm_id)
                )

        await self.db_session.commit()
        await self.db_session.refresh(role)

        return role

    async def delete_role(self, role_id: int) -> bool:
        """删除角色"""
        role = await self.get_role_by_id(role_id)
        if not role:
            return False

        # 系统角色不能删除
        if role.is_system:
            return False

        await self.db_session.delete(role)
        await self.db_session.commit()

        return True

    async def assign_permissions(self, role_id: int, permission_ids: List[int]) -> bool:
        """为角色分配权限"""
        role = await self.get_role_by_id(role_id)
        if not role:
            return False

        # 先删除现有权限关联
        await self.db_session.execute(
            delete(role_permissions).where(role_permissions.c.role_id == role_id)
        )

        # 验证权限 ID 并添加新权限
        for perm_id in permission_ids:
            perm_query = select(Permission).where(Permission.id == perm_id)
            perm_result = await self.db_session.execute(perm_query)
            if perm_result.scalar_one_or_none():
                await self.db_session.execute(
                    role_permissions.insert().values(role_id=role_id, permission_id=perm_id)
                )

        await self.db_session.commit()
        return True

    async def get_role_permissions(self, role_id: int) -> List[Permission]:
        """获取角色的权限列表"""
        role = await self.get_role_by_id(role_id)
        if not role:
            return []

        # 通过关系加载权限
        await self.db_session.refresh(role, attribute_names=["permissions"])
        return list(role.permissions)
