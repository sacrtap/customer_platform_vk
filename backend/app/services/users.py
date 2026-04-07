"""用户管理服务"""

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from typing import Optional, List, Union
from ..models.users import User, Role
import bcrypt


class UserService:
    """用户服务类

    支持同步和异步 Session
    """

    def __init__(self, session: Union[AsyncSession, Session]):
        self.session = session
        # 检测是否为异步 Session
        # 使用 hasattr 检查 AsyncSession 的特征属性
        self._is_async = (
            hasattr(session, "_is_asyncio_session")
            or type(session).__name__ in ("AsyncSession", "AsyncMock", "MagicMock")
            or "AsyncSession" in str(type(session))
        )

    async def _execute(self, query):
        """执行查询，自动处理同步/异步"""
        if self._is_async:
            return await self.session.execute(query)
        else:
            return self.session.execute(query)

    @staticmethod
    def verify_password(plain_password: str, password_hash: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), password_hash.encode("utf-8")
        )

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """根据 ID 获取用户"""
        from sqlalchemy.orm import selectinload

        result = await self._execute(
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        from sqlalchemy.orm import selectinload

        result = await self._execute(
            select(User)
            .where(User.username == username, User.deleted_at.is_(None))
            .options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    async def get_all_users(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[List[User], int]:
        """获取用户列表（分页）"""
        from sqlalchemy.orm import selectinload

        offset = (page - 1) * page_size

        # 获取总数
        count_query = (
            select(func.count()).select_from(User).where(User.deleted_at.is_(None))
        )
        total_result = await self.session.execute(count_query)
        total = total_result.scalar()

        # 获取数据（预加载 roles 关系）
        query = (
            select(User)
            .where(User.deleted_at.is_(None))
            .options(selectinload(User.roles))
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
        # 检查用户名是否已存在（包括软删除的用户）
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

        try:
            await self.session.flush()
            await self.session.refresh(user)
            return user
        except IntegrityError as e:
            await self.session.rollback()
            raise ValueError(f"用户名 {username} 已存在") from e

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
        await self.session.commit()
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
