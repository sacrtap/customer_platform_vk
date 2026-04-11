"""Roles Service 单元测试"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.services.roles import RoleService


# ==================== Fixtures ====================


@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = MagicMock()
    return session


@pytest.fixture
def role_service(mock_db_session):
    """创建 RoleService 实例"""
    return RoleService(mock_db_session)


# ==================== Create Role Tests ====================


class TestRoleService_CreateRole:
    """创建角色测试"""

    @pytest.mark.asyncio
    async def test_create_role_success(self, role_service, mock_db_session):
        """测试创建角色成功"""
        role_name = "test_role"
        description = "测试角色"

        # Mock get_role_by_name 返回 None (角色不存在)
        role_service.get_role_by_name = AsyncMock(return_value=None)

        # Mock 数据库操作
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        # 执行测试
        result = await role_service.create_role(name=role_name, description=description)

        # 验证结果
        assert result is not None
        assert result.name == role_name
        assert result.description == description

        # 验证数据库操作被调用
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_role_duplicate(self, role_service, mock_db_session):
        """测试创建重复角色"""
        role_name = "existing_role"
        description = "已存在的角色"

        # Mock get_role_by_name 返回已存在的角色
        existing_role = Role(id=1, name=role_name, description="已有角色")
        role_service.get_role_by_name = AsyncMock(return_value=existing_role)

        # 执行测试并验证异常
        with pytest.raises(ValueError) as exc_info:
            await role_service.create_role(name=role_name, description=description)

        # 验证异常消息
        assert f"角色 '{role_name}' 已存在" in str(exc_info.value)

        # 验证数据库操作未被调用
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_called()


# ==================== Update Role Tests ====================


class TestRoleService_UpdateRole:
    """更新角色测试"""

    @pytest.mark.asyncio
    async def test_update_role_success(self, role_service, mock_db_session):
        """测试更新角色成功"""
        role_id = 1
        new_name = "updated_role"
        new_description = "更新后的描述"

        # Mock get_role_by_id 返回现有角色
        existing_role = Role(
            id=role_id, name="old_role", description="旧描述", is_system=False
        )
        role_service.get_role_by_id = AsyncMock(return_value=existing_role)

        # Mock get_role_by_name 返回 None (新名称未被使用)
        role_service.get_role_by_name = AsyncMock(return_value=None)

        # Mock 数据库操作
        mock_db_session.execute = AsyncMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        # 执行测试
        result = await role_service.update_role(
            role_id=role_id, name=new_name, description=new_description
        )

        # 验证结果
        assert result is not None
        assert result.name == new_name
        assert result.description == new_description

        # 验证数据库操作被调用
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_role_not_found(self, role_service, mock_db_session):
        """测试更新不存在的角色"""
        role_id = 999

        # Mock get_role_by_id 返回 None
        role_service.get_role_by_id = AsyncMock(return_value=None)

        # 执行测试
        result = await role_service.update_role(
            role_id=role_id, name="new_name", description="新描述"
        )

        # 验证结果
        assert result is None

        # 验证数据库操作未被调用
        mock_db_session.commit.assert_not_called()


# ==================== Assign Permissions Tests ====================


class TestRoleService_AssignPermissions:
    """分配权限测试"""

    @pytest.mark.asyncio
    async def test_assign_permissions_success(self, role_service, mock_db_session):
        """测试为角色分配权限成功"""
        role_id = 1
        permission_ids = [1, 2, 3]

        # Mock get_role_by_id 返回现有角色
        existing_role = Role(id=role_id, name="test_role", is_system=False)
        role_service.get_role_by_id = AsyncMock(return_value=existing_role)

        # Mock 删除现有权限
        mock_db_session.execute = AsyncMock()

        # Mock 权限验证查询 - 所有权限都存在
        mock_perm = Permission(id=1, name="customer.view")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_perm
        mock_db_session.execute.return_value = mock_result

        # Mock 提交
        mock_db_session.commit = AsyncMock()

        # 执行测试
        result = await role_service.assign_permissions(
            role_id=role_id, permission_ids=permission_ids
        )

        # 验证结果
        assert result is True

        # 验证数据库操作
        assert mock_db_session.execute.call_count >= 1  # 至少调用删除操作
        mock_db_session.commit.assert_called_once()


# ==================== Get Role Permissions Tests ====================


class TestRoleService_GetRolePermissions:
    """获取角色权限测试"""

    @pytest.mark.asyncio
    async def test_get_role_permissions(self, role_service, mock_db_session):
        """测试获取角色权限列表"""
        role_id = 1

        # Mock get_role_by_id 返回现有角色
        existing_role = Role(id=role_id, name="test_role", is_system=False)
        existing_role.permissions = [
            Permission(id=1, name="customer.view"),
            Permission(id=2, name="customer.create"),
            Permission(id=3, name="billing.view"),
        ]
        role_service.get_role_by_id = AsyncMock(return_value=existing_role)

        # Mock refresh 操作
        mock_db_session.refresh = AsyncMock()

        # 执行测试
        result = await role_service.get_role_permissions(role_id=role_id)

        # 验证结果
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0].name == "customer.view"
        assert result[1].name == "customer.create"
        assert result[2].name == "billing.view"

        # 验证 refresh 被调用
        mock_db_session.refresh.assert_called_once()


# ==================== Delete Role Tests ====================


class TestRoleService_DeleteRole:
    """删除角色测试"""

    @pytest.mark.asyncio
    async def test_delete_role_success(self, role_service, mock_db_session):
        """测试删除角色成功"""
        role_id = 1

        # Mock get_role_by_id 返回非系统角色
        existing_role = Role(id=role_id, name="test_role", is_system=False)
        role_service.get_role_by_id = AsyncMock(return_value=existing_role)

        # Mock delete 操作 (源码使用 await，需要 AsyncMock)
        mock_db_session.delete = AsyncMock()
        mock_db_session.commit = AsyncMock()

        # 执行测试
        result = await role_service.delete_role(role_id=role_id)

        # 验证结果
        assert result is True

        # 验证数据库操作
        mock_db_session.delete.assert_called_once_with(existing_role)
        mock_db_session.commit.assert_called_once()
