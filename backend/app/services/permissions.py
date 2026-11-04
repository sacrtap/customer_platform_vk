"""权限服务"""

from typing import Set

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.users import Permission, Role, User, role_permissions, user_roles


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


async def count_users_with_permission(session: AsyncSession, permission_code: str) -> int:
    """统计持指定权限码且可用的用户数（deleted_at IS NULL 且 is_active IS NOT FALSE）。

    用于「系统内是否存在持某权限的用户」判断（VR 减免审批门禁的兜底条件）。
    count(distinct User.id)：同一用户经多个角色获得同一权限只计一次。
    """
    stmt = (
        select(func.count(User.id.distinct()))
        .select_from(User)
        .join(user_roles, User.id == user_roles.c.user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .join(role_permissions, Role.id == role_permissions.c.role_id)
        .join(Permission, Permission.id == role_permissions.c.permission_id)
        .where(
            Permission.code == permission_code,
            User.deleted_at.is_(None),
            User.is_active.is_not(False),
        )
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())
