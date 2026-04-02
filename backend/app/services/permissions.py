"""权限服务"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Set
from ..models.users import User, Role, Permission, user_roles, role_permissions


async def get_user_permissions(session: AsyncSession, user_id: int) -> Set[str]:
    """
    获取用户所有权限代码

    Args:
        session: 数据库会话
        user_id: 用户ID

    Returns:
        权限代码集合
    """
    # 查询用户所有角色的权限代码
    stmt = (
        select(Permission.code)
        .select_from(User)
        .join(user_roles, User.id == user_roles.c.user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .join(role_permissions, Role.id == role_permissions.c.role_id)
        .join(Permission, Permission.id == role_permissions.c.permission_id)
        .where(User.id == user_id, User.deleted_at.is_(None))
    )

    result = await session.execute(stmt)
    permissions = result.scalars().all()

    return set(permissions)
