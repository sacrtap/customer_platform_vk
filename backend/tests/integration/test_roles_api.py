"""角色管理 API 集成测试

覆盖测试计划中的 API 测试用例:
- TC-API-ROLE-001: 创建角色 API
- TC-API-ROLE-002: 更新角色 API
- TC-API-ROLE-003: 分配权限 API
- TC-API-ROLE-004: 删除系统角色 API
- TC-API-ROLE-005: 获取角色列表 API
- TC-API-ROLE-006: 获取权限列表 API
"""

import pytest
from sqlalchemy import text


@pytest.fixture
async def auth_token(test_client, test_user):
    """获取认证 Token"""
    login_request, login_response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    assert login_response.status == 200
    return login_response.json["data"]["access_token"]


# ==================== TC-API-ROLE-005: 获取角色列表 API ====================


class TestGetRoles:
    """测试获取角色列表 API"""

    @pytest.mark.asyncio
    async def test_get_roles_list(self, test_client, auth_token):
        """TC-API-ROLE-005: 测试获取角色列表成功"""
        request, response = await test_client.get(
            "/api/v1/roles", headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert "list" in data["data"]
        assert "total" in data["data"]
        assert isinstance(data["data"]["list"], list)

    @pytest.mark.asyncio
    async def test_get_roles_pagination(self, test_client, auth_token):
        """TC-API-ROLE-005: 测试分页参数"""
        request, response = await test_client.get(
            "/api/v1/roles?page=1&page_size=10",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 200
        data = response.json
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 10

    @pytest.mark.asyncio
    async def test_get_roles_search(self, test_client, auth_token, db_session):
        """TC-API-ROLE-005: 测试搜索功能"""
        # 创建测试角色
        db_session.execute(
            text(
                """
            INSERT INTO roles (name, description, created_at)
            VALUES (:name, :description, NOW())
            """
            ),
            {"name": "测试角色", "description": "用于测试的角色"},
        )
        db_session.commit()

        request, response = await test_client.get(
            "/api/v1/roles?keyword=测试",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 200
        data = response.json
        assert data["data"]["total"] >= 1


# ==================== TC-API-ROLE-001: 创建角色 API ====================


class TestCreateRole:
    """测试创建角色 API"""

    @pytest.mark.asyncio
    async def test_create_role_success(self, test_client, auth_token):
        """TC-API-ROLE-001: 测试创建角色成功"""
        request, response = await test_client.post(
            "/api/v1/roles",
            json={"name": "新测试角色", "description": "这是一个新的测试角色"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 201
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "创建成功"
        assert data["data"]["name"] == "新测试角色"

    @pytest.mark.asyncio
    async def test_create_role_duplicate(self, test_client, auth_token, db_session):
        """TC-API-ROLE-005: 测试创建重复角色"""
        db_session.execute(
            text(
                """
            INSERT INTO roles (name, description, created_at)
            VALUES (:name, :description, NOW())
            """
            ),
            {"name": "重复角色", "description": "已有角色"},
        )
        db_session.commit()

        request, response = await test_client.post(
            "/api/v1/roles",
            json={"name": "重复角色", "description": "重复的角色"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 400
        data = response.json
        assert data["code"] == 40002
        assert "已存在" in data["message"]

    @pytest.mark.asyncio
    async def test_create_role_empty_name(self, test_client, auth_token):
        """TC-API-ROLE-016: 测试创建角色 - 空名称验证"""
        request, response = await test_client.post(
            "/api/v1/roles",
            json={"name": "", "description": "测试"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 400
        data = response.json
        assert "不能为空" in data["message"]

    @pytest.mark.asyncio
    async def test_create_role_with_permissions(self, test_client, auth_token, db_session):
        """TC-API-ROLE-001: 测试创建角色时分配权限"""
        result = db_session.execute(text("SELECT id FROM permissions LIMIT 3")).fetchall()
        permission_ids = [r[0] for r in result]

        request, response = await test_client.post(
            "/api/v1/roles",
            json={
                "name": "带权限的角色",
                "description": "测试角色",
                "permission_ids": permission_ids,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 201


# ==================== TC-API-ROLE-002: 更新角色 API ====================


class TestUpdateRole:
    """测试更新角色 API"""

    @pytest.mark.asyncio
    async def test_update_role_success(self, test_client, auth_token, db_session):
        """TC-API-ROLE-002: 测试更新角色成功"""
        db_session.execute(
            text(
                """
            INSERT INTO roles (name, description, created_at)
            VALUES (:name, :description, NOW())
            """
            ),
            {"name": "待更新角色", "description": "原始描述"},
        )
        db_session.commit()

        result = db_session.execute(
            text("SELECT id FROM roles WHERE name = :name"), {"name": "待更新角色"}
        ).fetchone()
        role_id = result[0]

        request, response = await test_client.put(
            f"/api/v1/roles/{role_id}",
            json={"name": "更新后的角色", "description": "更新后的描述"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "更新成功"
        assert data["data"]["name"] == "更新后的角色"

    @pytest.mark.asyncio
    async def test_update_system_role_name(self, test_client, auth_token, db_session):
        """TC-API-ROLE-007: 测试编辑系统角色 - 名称保护"""
        db_session.execute(
            text(
                """
            INSERT INTO roles (name, description, is_system, created_at)
            VALUES (:name, :description, :is_system, NOW())
            """
            ),
            {"name": "系统管理员", "description": "系统角色", "is_system": True},
        )
        db_session.commit()

        result = db_session.execute(
            text("SELECT id FROM roles WHERE name = :name"), {"name": "系统管理员"}
        ).fetchone()
        role_id = result[0]

        request, response = await test_client.put(
            f"/api/v1/roles/{role_id}",
            json={"name": "新的系统管理员"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 400
        data = response.json
        assert "系统角色" in data["message"]

    @pytest.mark.asyncio
    async def test_update_role_not_found(self, test_client, auth_token):
        """测试更新不存在的角色"""
        request, response = await test_client.put(
            "/api/v1/roles/99999",
            json={"name": "不存在的角色"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 404


# ==================== TC-API-ROLE-003: 分配权限 API ====================


class TestAssignPermissions:
    """测试分配权限 API"""

    @pytest.mark.asyncio
    async def test_assign_permissions_success(self, test_client, auth_token, db_session):
        """TC-API-ROLE-003: 测试分配权限成功"""
        db_session.execute(
            text(
                """
            INSERT INTO roles (name, description, created_at)
            VALUES (:name, :description, NOW())
            """
            ),
            {"name": "权限测试角色", "description": "测试角色"},
        )
        db_session.commit()

        result = db_session.execute(
            text("SELECT id FROM roles WHERE name = :name"), {"name": "权限测试角色"}
        ).fetchone()
        role_id = result[0]

        result = db_session.execute(text("SELECT id FROM permissions LIMIT 3")).fetchall()
        permission_ids = [r[0] for r in result]

        request, response = await test_client.post(
            f"/api/v1/roles/{role_id}/permissions",
            json={"permission_ids": permission_ids},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "权限分配成功"

    @pytest.mark.asyncio
    async def test_assign_permissions_empty(self, test_client, auth_token, db_session):
        """TC-API-ROLE-015: 测试分配权限 - 空权限验证"""
        db_session.execute(
            text(
                """
            INSERT INTO roles (name, description, created_at)
            VALUES (:name, :description, NOW())
            """
            ),
            {"name": "空权限测试角色", "description": "测试角色"},
        )
        db_session.commit()

        result = db_session.execute(
            text("SELECT id FROM roles WHERE name = :name"), {"name": "空权限测试角色"}
        ).fetchone()
        role_id = result[0]

        request, response = await test_client.post(
            f"/api/v1/roles/{role_id}/permissions",
            json={"permission_ids": []},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 400
        data = response.json
        assert "不能为空" in data["message"]

    @pytest.mark.asyncio
    async def test_assign_permissions_invalid_id(self, test_client, auth_token, db_session):
        """测试分配不存在的权限"""
        db_session.execute(
            text(
                """
            INSERT INTO roles (name, description, created_at)
            VALUES (:name, :description, NOW())
            """
            ),
            {"name": "无效权限测试角色", "description": "测试角色"},
        )
        db_session.commit()

        result = db_session.execute(
            text("SELECT id FROM roles WHERE name = :name"),
            {"name": "无效权限测试角色"},
        ).fetchone()
        role_id = result[0]

        request, response = await test_client.post(
            f"/api/v1/roles/{role_id}/permissions",
            json={"permission_ids": [99999]},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 200


# ==================== TC-API-ROLE-004: 删除系统角色 API ====================


class TestDeleteRole:
    """测试删除角色 API"""

    @pytest.mark.asyncio
    async def test_delete_custom_role(self, test_client, auth_token, db_session):
        """TC-API-ROLE-008: 测试删除自定义角色"""
        db_session.execute(
            text(
                """
            INSERT INTO roles (name, description, created_at)
            VALUES (:name, :description, NOW())
            """
            ),
            {"name": "待删除角色", "description": "测试角色"},
        )
        db_session.commit()

        result = db_session.execute(
            text("SELECT id FROM roles WHERE name = :name"), {"name": "待删除角色"}
        ).fetchone()
        role_id = result[0]

        request, response = await test_client.delete(
            f"/api/v1/roles/{role_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "删除成功"

    @pytest.mark.asyncio
    async def test_delete_system_role(self, test_client, auth_token, db_session):
        """TC-API-ROLE-009: 测试删除系统角色 - 保护机制"""
        db_session.execute(
            text(
                """
            INSERT INTO roles (name, description, is_system, created_at)
            VALUES (:name, :description, :is_system, NOW())
            """
            ),
            {"name": "待删除系统角色", "description": "系统角色", "is_system": True},
        )
        db_session.commit()

        result = db_session.execute(
            text("SELECT id FROM roles WHERE name = :name"), {"name": "待删除系统角色"}
        ).fetchone()
        role_id = result[0]

        request, response = await test_client.delete(
            f"/api/v1/roles/{role_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 400
        data = response.json
        assert "系统角色" in data["message"]

    @pytest.mark.asyncio
    async def test_delete_role_not_found(self, test_client, auth_token):
        """测试删除不存在的角色"""
        request, response = await test_client.delete(
            "/api/v1/roles/99999", headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status == 404


# ==================== TC-API-ROLE-006: 获取权限列表 API ====================


class TestGetPermissions:
    """测试获取权限列表 API"""

    @pytest.mark.asyncio
    async def test_get_permissions_list(self, test_client, auth_token):
        """TC-API-ROLE-006: 测试获取权限列表"""
        request, response = await test_client.get(
            "/api/v1/permissions", headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0

    @pytest.mark.asyncio
    async def test_get_permissions_structure(self, test_client, auth_token):
        """TC-API-ROLE-006: 测试权限数据结构"""
        request, response = await test_client.get(
            "/api/v1/permissions", headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status == 200
        data = response.json
        perm = data["data"][0]

        assert "id" in perm
        assert "code" in perm
        assert "name" in perm
        assert "module" in perm


# ==================== TC-API-ROLE-020: API 错误处理 ====================


class TestApiErrorHandling:
    """测试 API 错误处理"""

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, test_client):
        """测试未授权访问"""
        request, response = await test_client.get("/api/v1/roles")
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_invalid_token(self, test_client):
        """测试无效 token"""
        request, response = await test_client.get(
            "/api/v1/roles", headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status == 401
