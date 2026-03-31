"""用户管理服务"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from ..models.users import User, user_roles, Role
from ..models.base import BaseModel
import bcrypt


class UserService:
    """用户服务类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """根据 ID 获取用户"""
        result = await self.session.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        result = await self.session.execute(
            select(User).where(User.username == username, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_all_users(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[List[User], int]:
        """获取用户列表（分页）"""
        offset = (page - 1) * page_size

        # 获取总数
        count_query = (
            select(func.count()).select_from(User).where(User.deleted_at.is_(None))
        )
        total_result = await self.session.execute(count_query)
        total = total_result.scalar()

        # 获取数据
        query = (
            select(User)
            .where(User.deleted_at.is_(None))
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(query)
        users = result.scalars().all()

        return list(users), total

    async def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        real_name: Optional[str] = None,
    ) -> User:
        """创建用户"""
        # 检查用户名是否已存在
        existing = await self.get_user_by_username(username)
        if existing:
            raise ValueError(f"用户名 {username} 已存在")

        # 密码加密
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        user = User(
            username=username,
            password_hash=password_hash,
            email=email,
            real_name=real_name,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_user(
        self,
        user_id: int,
        email: Optional[str] = None,
        real_name: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[User]:
        """更新用户信息"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        if email is not None:
            user.email = email
        if real_name is not None:
            user.real_name = real_name
        if is_active is not None:
            user.is_active = is_active

        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def delete_user(self, user_id: int) -> bool:
        """软删除用户"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        user.deleted_at = func.now()
        await self.session.flush()
        return True

    async def reset_password(self, user_id: int, new_password: str) -> bool:
        """重置用户密码"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        user.password_hash = bcrypt.hashpw(
            new_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        await self.session.flush()
        return True

    async def assign_roles(self, user_id: int, role_ids: List[int]) -> bool:
        """为用户分配角色"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        # 清除现有角色
        user.roles = []
        await self.session.flush()

        # 添加新角色
        for role_id in role_ids:
            result = await self.session.execute(
                select(Role).where(Role.id == role_id, Role.deleted_at.is_(None))
            )
            role = result.scalar_one_or_none()
            if role:
                user.roles.append(role)

        await self.session.flush()
        return True

    async def get_user_roles(self, user_id: int) -> List[Role]:
        """获取用户角色"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return []
        return user.roles
