"""Permission Service 单元测试"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy import select

from app.services.permissions import get_user_permissions
from app.models.users import User, Role, Permission, user_roles, role_permissions


# ==================== Fixtures ====================


@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    return session


# ==================== Test Get User Permissions ====================


class TestPermissionService_GetUserPermissions:
    """获取用户权限测试"""

    @pytest.mark.asyncio
    async def test_get_user_permissions_success(self, mock_db_session):
        """测试获取用户权限成功"""
        user_id = 1

        # Mock 查询结果 - 用户有多个权限
        mock_permissions = ["customer.create", "customer.edit", "customer.view"]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_permissions
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await get_user_permissions(mock_db_session, user_id)

        # 验证结果
        assert result is not None
        assert isinstance(result, set)
        assert result == {"customer.create", "customer.edit", "customer.view"}

        # 验证数据库查询被调用
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_permissions_empty(self, mock_db_session):
        """测试用户没有任何权限"""
        user_id = 1

        # Mock 查询结果 - 用户没有权限
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await get_user_permissions(mock_db_session, user_id)

        # 验证结果
        assert result is not None
        assert isinstance(result, set)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_user_permissions_with_deleted_user(self, mock_db_session):
        """测试已删除用户的权限查询"""
        user_id = 1

        # Mock 查询结果 - 用户已删除，应该返回空
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await get_user_permissions(mock_db_session, user_id)

        # 验证结果
        assert result is not None
        assert isinstance(result, set)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_user_permissions_duplicate_handling(self, mock_db_session):
        """测试权限去重（用户有多个角色包含相同权限）"""
        user_id = 1

        # Mock 查询结果 - 包含重复权限
        mock_permissions = [
            "customer.view",
            "customer.create",
            "customer.view",  # 重复
            "billing.view",
            "customer.create",  # 重复
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_permissions
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await get_user_permissions(mock_db_session, user_id)

        # 验证结果 - 使用 set 自动去重
        assert result is not None
        assert isinstance(result, set)
        assert result == {"customer.view", "customer.create", "billing.view"}
        assert len(result) == 3  # 去重后只有 3 个权限

    @pytest.mark.asyncio
    async def test_get_user_permissions_module_variety(self, mock_db_session):
        """测试获取多个模块的权限"""
        user_id = 1

        # Mock 查询结果 - 不同模块的权限
        mock_permissions = [
            "customer.create",
            "customer.edit",
            "customer.delete",
            "billing.view",
            "billing.edit",
            "user.manage",
            "role.assign",
            "analytics.view",
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_permissions
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await get_user_permissions(mock_db_session, user_id)

        # 验证结果
        assert result is not None
        assert len(result) == 8

        # 验证包含各个模块的权限
        assert "customer.create" in result
        assert "billing.view" in result
        assert "user.manage" in result
        assert "analytics.view" in result


# ==================== Integration Tests ====================


class TestPermissionService_Integration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_get_user_permissions_real_scenario(self, mock_db_session):
        """模拟真实场景下的权限查询"""
        user_id = 1

        # Mock 一个运营经理的典型权限
        manager_permissions = [
            "customer.view",
            "customer.create",
            "customer.edit",
            "billing.view",
            "analytics.view",
            "tag.create",
            "tag.edit",
            "group.manage",
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = manager_permissions
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await get_user_permissions(mock_db_session, user_id)

        # 验证结果
        assert result is not None
        assert isinstance(result, set)
        assert len(result) == 8

        # 验证运营经理有关键权限
        assert "customer.create" in result
        assert "customer.edit" in result
        assert "billing.view" in result

    @pytest.mark.asyncio
    async def test_get_user_permissions_admin_role(self, mock_db_session):
        """测试管理员角色的权限"""
        user_id = 1

        # Mock 管理员的所有权限
        admin_permissions = [
            "customer.*",
            "billing.*",
            "user.*",
            "role.*",
            "permission.*",
            "analytics.*",
            "tag.*",
            "group.*",
            "system.config",
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = admin_permissions
        mock_db_session.execute.return_value = mock_result

        # 执行测试
        result = await get_user_permissions(mock_db_session, user_id)

        # 验证结果
        assert result is not None
        assert len(result) == 9
        assert "system.config" in result
        assert "user.*" in result
        assert "role.*" in result
