"""User Service 单元测试"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.services.users import UserService
from app.models.users import User, Role


# ==================== Fixtures ====================


@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def user_service(mock_db_session):
    """创建 UserService 实例"""
    return UserService(session=mock_db_session)


# ==================== Test Create User ====================


class TestUserService_CreateUser:
    """创建用户测试"""

    @pytest.mark.asyncio
    async def test_create_user_success(self, user_service, mock_db_session):
        """测试创建用户成功"""
        # 准备测试数据
        username = "testuser"
        password = "password123"
        email = "test@example.com"
        real_name = "测试用户"

        # Mock 用户名不存在
        mock_db_session.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Mock 添加和刷新
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        mock_db_session.refresh = AsyncMock(side_effect=lambda x: setattr(x, "id", 1))

        # 执行测试
        result = await user_service.create_user(
            username=username,
            password=password,
            email=email,
            real_name=real_name,
        )

        # 验证结果
        assert result is not None
        assert isinstance(result, User)
        assert result.username == username
        assert result.email == email
        assert result.real_name == real_name
        # 验证密码已加密（不是明文）
        assert result.password_hash != password
        assert result.password_hash is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, user_service, mock_db_session):
        """测试创建重复用户名的用户"""
        # 准备测试数据
        username = "existinguser"
        password = "password123"

        # Mock 用户名已存在
        existing_user = User(
            id=1,
            username=username,
            password_hash="hashed_password",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # 执行测试并验证抛出异常
        with pytest.raises(ValueError) as exc_info:
            await user_service.create_user(
                username=username,
                password=password,
            )

        assert f"用户名 {username} 已存在" in str(exc_info.value)
        # 验证没有调用 add（因为提前返回了）
        mock_db_session.add.assert_not_called()


# ==================== Test Assign Role to User ====================


class TestUserService_AssignRoleToUser:
    """分配角色给用户测试"""

    @pytest.mark.asyncio
    async def test_assign_role_to_user_success(self, user_service, mock_db_session):
        """测试分配角色给用户成功"""
        user_id = 1
        role_ids = [1, 2]

        # Mock 用户存在
        mock_user = User(
            id=user_id,
            username="testuser",
            roles=[],
        )

        # Mock 角色存在
        mock_role1 = Role(id=1, name="admin", description="管理员")
        mock_role2 = Role(id=2, name="user", description="普通用户")

        # 设置 execute 的 side_effect
        call_count = {"count": 0}

        async def mock_execute_side_effect(query):
            call_count["count"] += 1
            mock_result = MagicMock()
            if call_count["count"] == 1:
                # 第一次调用：获取用户
                mock_result.scalar_one_or_none.return_value = mock_user
            elif call_count["count"] in [2, 3]:
                # 第二、三次调用：获取角色
                if call_count["count"] == 2:
                    mock_result.scalar_one_or_none.return_value = mock_role1
                else:
                    mock_result.scalar_one_or_none.return_value = mock_role2
            return mock_result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute_side_effect)
        mock_db_session.flush = AsyncMock()

        # 执行测试
        result = await user_service.assign_roles(user_id, role_ids)

        # 验证结果
        assert result is True
        # 验证用户角色被设置
        assert len(mock_user.roles) == 2
        mock_db_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_assign_role_to_user_not_found(self, user_service, mock_db_session):
        """测试分配角色给不存在的用户"""
        user_id = 999
        role_ids = [1]

        # Mock 用户不存在
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # 执行测试
        result = await user_service.assign_roles(user_id, role_ids)

        # 验证结果
        assert result is False
        mock_db_session.flush.assert_not_called()


# ==================== Test Remove Role from User ====================


class TestUserService_RemoveRoleFromUser:
    """移除用户角色测试"""

    @pytest.mark.asyncio
    async def test_remove_role_from_user_success(self, user_service, mock_db_session):
        """测试移除用户角色成功"""
        user_id = 1

        # Mock 用户存在且有角色
        mock_role = Role(id=1, name="admin", description="管理员")
        mock_user = User(
            id=user_id,
            username="testuser",
            roles=[mock_role],
        )

        # Mock 获取用户
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()

        # 执行测试 - 通过 assign_roles 传入空列表来移除所有角色
        result = await user_service.assign_roles(user_id, [])

        # 验证结果
        assert result is True
        # 验证用户角色被清空
        assert len(mock_user.roles) == 0
        mock_db_session.flush.assert_called()


# ==================== Test Get User By ID ====================


class TestUserService_GetUserById:
    """根据 ID 获取用户测试"""

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, user_service, mock_db_session):
        """测试获取存在的用户"""
        user_id = 1

        # Mock 用户存在
        mock_user = User(
            id=user_id,
            username="testuser",
            email="test@example.com",
            real_name="测试用户",
            is_active=True,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # 执行测试
        result = await user_service.get_user_by_id(user_id)

        # 验证结果
        assert result is not None
        assert isinstance(result, User)
        assert result.id == user_id
        assert result.username == "testuser"
        assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, user_service, mock_db_session):
        """测试获取不存在的用户"""
        user_id = 999

        # Mock 用户不存在
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # 执行测试
        result = await user_service.get_user_by_id(user_id)

        # 验证结果
        assert result is None


# ==================== Test Update User ====================


class TestUserService_UpdateUser:
    """更新用户信息测试"""

    @pytest.mark.asyncio
    async def test_update_user_success(self, user_service, mock_db_session):
        """测试更新用户信息成功"""
        user_id = 1
        new_email = "newemail@example.com"
        new_real_name = "新用户名"
        new_is_active = False

        mock_user = User(
            id=user_id,
            username="testuser",
            email="old@example.com",
            real_name="旧用户名",
            is_active=True,
        )

        call_count = {"count": 0}

        async def mock_execute_side_effect(query):
            call_count["count"] += 1
            mock_result = MagicMock()
            if call_count["count"] == 1:
                mock_result.scalar_one_or_none.return_value = mock_user
            return mock_result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute_side_effect)
        mock_db_session.flush = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        result = await user_service.update_user(
            user_id=user_id,
            email=new_email,
            real_name=new_real_name,
            is_active=new_is_active,
        )

        assert result is not None
        assert isinstance(result, User)
        assert result.email == new_email
        assert result.real_name == new_real_name
        assert result.is_active == new_is_active
        mock_db_session.flush.assert_called()
        mock_db_session.refresh.assert_called()

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, user_service, mock_db_session):
        """测试更新不存在的用户"""
        user_id = 999

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await user_service.update_user(
            user_id=user_id,
            email="test@example.com",
        )

        assert result is None
        mock_db_session.flush.assert_not_called()


# ==================== Test Get User Roles ====================


class TestUserService_GetUserRoles:
    """获取用户角色测试"""

    @pytest.mark.asyncio
    async def test_get_user_roles_success(self, user_service, mock_db_session):
        """测试获取用户角色成功"""
        user_id = 1

        mock_role1 = Role(id=1, name="admin", description="管理员")
        mock_role2 = Role(id=2, name="user", description="普通用户")

        mock_user = User(
            id=user_id,
            username="testuser",
            roles=[mock_role1, mock_role2],
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await user_service.get_user_roles(user_id)

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].id == 1
        assert result[0].name == "admin"
        assert result[1].id == 2
        assert result[1].name == "user"

    @pytest.mark.asyncio
    async def test_get_user_roles_not_found(self, user_service, mock_db_session):
        """测试获取不存在用户的角色"""
        user_id = 999

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await user_service.get_user_roles(user_id)

        assert result == []
