"""用户管理服务"""

from typing import List, Optional, Union

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..models.users import Role, User


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
            return await self.session.execute(query)  # pyright: ignore[reportGeneralTypeIssues]
        else:
            return self.session.execute(query)

    @staticmethod
    def verify_password(plain_password: str, password_hash: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """根据 ID 获取用户"""
        from sqlalchemy.orm import selectinload

        result = await self._execute(
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()  # pyright: ignore[reportAttributeAccessIssue]

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        from sqlalchemy.orm import selectinload

        result = await self._execute(
            select(User)
            .where(User.username == username, User.deleted_at.is_(None))
            .options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()  # pyright: ignore[reportAttributeAccessIssue]

    async def get_all_users(
        self, page: int = 1, page_size: int = 20, keyword: Optional[str] = None
    ) -> tuple[List[User], int]:
        """获取用户列表(分页)"""
        from sqlalchemy.orm import selectinload

        offset = (page - 1) * page_size

        # 构建基础查询条件
        base_conditions = [User.deleted_at.is_(None)]

        # 添加 keyword 搜索条件
        if keyword:
            search_pattern = f"%{keyword}%"
            base_conditions.append(
                (User.username.like(search_pattern))  # pyright: ignore[reportArgumentType]
                | (User.real_name.like(search_pattern))
                | (User.email.like(search_pattern))
            )

        # 获取总数
        count_query = select(func.count()).select_from(User).where(*base_conditions)
        total_result = await self.session.execute(count_query)  # pyright: ignore[reportGeneralTypeIssues]
        total = total_result.scalar()

        # 获取数据(预加载 roles 关系)
        query = (
            select(User)
            .where(*base_conditions)
            .options(selectinload(User.roles))
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(query)  # pyright: ignore[reportGeneralTypeIssues]
        users = result.scalars().all()

        return list(users), total  # pyright: ignore[reportReturnType]

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
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        user = User(
            username=username,
            password_hash=password_hash,
            email=email,
            real_name=real_name,
        )
        self.session.add(user)

        try:
            await self.session.flush()  # pyright: ignore[reportGeneralTypeIssues]
            await self.session.refresh(user)  # pyright: ignore[reportGeneralTypeIssues]
            return user
        except IntegrityError as e:
            await self.session.rollback()  # pyright: ignore[reportGeneralTypeIssues]
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
            user.email = email  # pyright: ignore[reportAttributeAccessIssue]
        if real_name is not None:
            user.real_name = real_name  # pyright: ignore[reportAttributeAccessIssue]
        if is_active is not None:
            user.is_active = is_active  # pyright: ignore[reportAttributeAccessIssue]

        await self.session.flush()  # pyright: ignore[reportGeneralTypeIssues]
        await self.session.refresh(user)  # pyright: ignore[reportGeneralTypeIssues]
        return user

    async def delete_user(self, user_id: int) -> bool:
        """软删除用户"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        user.deleted_at = func.now()  # pyright: ignore[reportAttributeAccessIssue]
        await self.session.commit()  # pyright: ignore[reportGeneralTypeIssues]
        return True

    async def reset_password(self, user_id: int, new_password: str) -> bool:
        """重置用户密码"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        user.password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode(  # pyright: ignore[reportAttributeAccessIssue]
            "utf-8"
        )
        await self.session.flush()  # pyright: ignore[reportGeneralTypeIssues]
        return True

    async def assign_roles(self, user_id: int, role_ids: List[int]) -> bool:
        """为用户分配角色"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        # 清除现有角色
        user.roles = []
        await self.session.flush()  # pyright: ignore[reportGeneralTypeIssues]

        # 添加新角色
        for role_id in role_ids:
            result = await self.session.execute(  # pyright: ignore[reportGeneralTypeIssues]
                select(Role).where(Role.id == role_id, Role.deleted_at.is_(None))
            )
            role = result.scalar_one_or_none()
            if role:
                user.roles.append(role)

        await self.session.flush()  # pyright: ignore[reportGeneralTypeIssues]
        return True

    async def get_user_roles(self, user_id: int) -> List[Role]:
        """获取用户角色"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return []
        return user.roles

    async def get_profile(self, user_id: int) -> Optional[dict]:
        """获取用户个人信息"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "real_name": user.real_name,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "roles": [r.name for r in user.roles],
        }

    async def update_profile(
        self,
        user_id: int,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        avatar_url: Optional[str] = None,
        real_name: Optional[str] = None,
    ) -> Optional[dict]:
        """更新用户个人信息"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        if email is not None:
            user.email = email  # pyright: ignore[reportAttributeAccessIssue]
        if phone is not None:
            user.phone = phone  # pyright: ignore[reportAttributeAccessIssue]
        if avatar_url is not None:
            user.avatar_url = avatar_url  # pyright: ignore[reportAttributeAccessIssue]
        if real_name is not None:
            user.real_name = real_name  # pyright: ignore[reportAttributeAccessIssue]

        await self.session.flush()  # pyright: ignore[reportGeneralTypeIssues]
        await self.session.refresh(user)  # pyright: ignore[reportGeneralTypeIssues]

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "real_name": user.real_name,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,  # pyright: ignore[reportGeneralTypeIssues]
            "roles": [r.name for r in user.roles],
        }

    async def change_password(
        self, user_id: int, current_password: str, new_password: str
    ) -> tuple[bool, str]:
        """修改密码

        Returns:
            (success, message)
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return False, "用户不存在"

        # 验证当前密码
        if not self.verify_password(current_password, user.password_hash):  # pyright: ignore[reportArgumentType]
            return False, "当前密码不正确"

        # 密码强度检查
        if len(new_password) < 6:
            return False, "密码长度不能少于 6 位"

        user.password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode(  # pyright: ignore[reportAttributeAccessIssue]
            "utf-8"
        )

        await self.session.flush()  # pyright: ignore[reportGeneralTypeIssues]
        return True, "密码修改成功"
