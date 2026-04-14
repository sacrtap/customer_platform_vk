"""客户群组 API 集成测试"""

import pytest
from sqlalchemy import text


class TestCreateGroup:
    """测试创建群组"""

    @pytest.mark.asyncio
    async def test_create_dynamic_group(self, test_client, test_user, db_session):
        """测试创建动态群组"""
        # 诊断：检查 settings.jwt_secret
        from app.config import settings, get_settings

        print("\n=== DEBUG: Settings ===")
        print(f"JWT_SECRET: {settings.jwt_secret[:20]}...")
        print(f"Settings cache info: {get_settings.cache_info()}")

        # 先登录获取 token
        _, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        print("\n=== DEBUG: Login Response ===")
        print(f"Status: {login_response.status}")

        assert login_response.status == 200, (
            f"Login failed with status {login_response.status}"
        )

        login_data = login_response.json
        print(f"Parsed JSON: {login_data}")

        assert login_data.get("code") == 0, f"Login failed: {login_data}"
        token = login_data["data"]["access_token"]
        print(f"Token obtained: {token[:50]}...")

        # 验证 token 解码
        from app.services.auth import AuthService

        payload = AuthService.verify_token(token)
        print(f"Token payload: {payload}")

        # 发送创建群组请求
        _, response = await test_client.post(
            "/api/v1/customer-groups",
            json={
                "name": "测试动态群组",
                "description": "测试描述",
                "group_type": "dynamic",
                "filter_conditions": {"customer_level": "KA"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        print("\n=== DEBUG: Create Group Response ===")
        print(f"Status: {response.status}")
        print(f"Body: {response.text}")
        print(f"Headers: {dict(response.headers)}")

        request, response = await test_client.post(
            "/api/v1/customer-groups",
            json={
                "name": "测试动态群组",
                "description": "测试描述",
                "group_type": "dynamic",
                "filter_conditions": {"customer_level": "KA"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status == 201
        data = response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "测试动态群组"
        assert "id" in data["data"]

    @pytest.mark.asyncio
    async def test_create_static_group(self, test_client, test_user, db_session):
        """测试创建静态群组"""
        # 先登录获取 token
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        request, response = await test_client.post(
            "/api/v1/customer-groups",
            json={"name": "测试静态群组", "group_type": "static"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status == 201
        data = response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "测试静态群组"

    @pytest.mark.asyncio
    async def test_create_group_missing_name(self, test_client, test_user, db_session):
        """测试创建群组缺少名称"""
        # 先登录获取 token
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        request, response = await test_client.post(
            "/api/v1/customer-groups",
            json={"description": "测试描述"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status == 400
        data = response.json
        assert "不能为空" in data["message"]


class TestListGroups:
    """测试获取群组列表"""

    @pytest.mark.asyncio
    async def test_list_user_groups(self, test_client, test_user, db_session):
        """测试获取用户的群组列表"""
        # 先登录获取 token
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        # 先创建一个群组
        await test_client.post(
            "/api/v1/customer-groups",
            json={"name": "测试群组", "group_type": "dynamic"},
            headers={"Authorization": f"Bearer {token}"},
        )

        request, response = await test_client.get(
            "/api/v1/customer-groups",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert len(data["data"]["list"]) >= 1

    @pytest.mark.asyncio
    async def test_list_groups_unauthorized(self, test_client):
        """测试未认证访问群组列表"""
        request, response = await test_client.get("/api/v1/customer-groups")

        assert response.status == 401
        data = response.json
        assert data["code"] == 40101


class TestGetGroup:
    """测试获取群组详情"""

    @pytest.mark.asyncio
    async def test_get_group_detail(self, test_client, test_user, db_session):
        """测试获取群组详情"""
        # 先登录获取 token
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        # 先创建一个群组
        create_request, create_response = await test_client.post(
            "/api/v1/customer-groups",
            json={"name": "测试详情群组", "group_type": "dynamic"},
            headers={"Authorization": f"Bearer {token}"},
        )
        group_id = create_response.json["data"]["id"]

        # 获取群组详情
        get_request, get_response = await test_client.get(
            f"/api/v1/customer-groups/{group_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert get_response.status == 200
        data = get_response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "测试详情群组"

    @pytest.mark.asyncio
    async def test_get_group_not_found(self, test_client, test_user, db_session):
        """测试获取不存在的群组"""
        # 先登录获取 token
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        request, response = await test_client.get(
            "/api/v1/customer-groups/99999",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status == 404
        data = response.json
        assert data["code"] == 40401


class TestDeleteGroup:
    """测试删除群组"""

    @pytest.mark.asyncio
    async def test_delete_group(self, test_client, test_user, db_session):
        """测试删除群组"""
        # 先登录获取 token
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        # 先创建一个群组
        create_request, create_response = await test_client.post(
            "/api/v1/customer-groups",
            json={"name": "待删除群组", "group_type": "dynamic"},
            headers={"Authorization": f"Bearer {token}"},
        )
        group_id = create_response.json["data"]["id"]

        # 删除群组
        delete_request, delete_response = await test_client.delete(
            f"/api/v1/customer-groups/{group_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert delete_response.status == 200
        assert delete_response.json["code"] == 0

        # 验证群组已被删除
        get_request, get_response = await test_client.get(
            f"/api/v1/customer-groups/{group_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_response.status == 404


class TestGroupMembers:
    """测试群组成员管理"""

    @pytest.mark.asyncio
    async def test_add_and_remove_member(self, test_client, test_user, db_session):
        """测试添加和移除成员"""
        # 先登录获取 token
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        # 创建静态群组
        create_request, create_response = await test_client.post(
            "/api/v1/customer-groups",
            json={"name": "测试成员群组", "group_type": "static"},
            headers={"Authorization": f"Bearer {token}"},
        )
        group_id = create_response.json["data"]["id"]

        # 创建一个测试客户
        await db_session.execute(
            text(
                """
            INSERT INTO customers (company_id, name, created_at)
            VALUES ('TEST001', '测试客户', NOW())
            ON CONFLICT (company_id) DO NOTHING
            """
            )
        )
        await db_session.commit()

        # 获取客户 ID
        result = await db_session.execute(
            text("SELECT id FROM customers WHERE company_id = 'TEST001'")
        )
        customer_id = result.scalar()

        # 添加成员
        add_request, add_response = await test_client.post(
            f"/api/v1/customer-groups/{group_id}/members",
            json={"customer_id": customer_id},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert add_response.status == 200
        assert add_response.json["code"] == 0

        # 获取成员列表
        members_request, members_response = await test_client.get(
            f"/api/v1/customer-groups/{group_id}/members",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert members_response.status == 200
        members_data = members_response.json
        assert len(members_data["data"]["list"]) >= 1

        # 移除成员
        remove_request, remove_response = await test_client.delete(
            f"/api/v1/customer-groups/{group_id}/members/{customer_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert remove_response.status == 200
        assert remove_response.json["code"] == 0


class TestGroupStats:
    """测试群组统计"""

    @pytest.mark.asyncio
    async def test_get_group_stats(self, test_client, test_user, db_session):
        """测试获取群组统计信息"""
        # 先登录获取 token
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        # 创建群组
        create_request, create_response = await test_client.post(
            "/api/v1/customer-groups",
            json={"name": "测试统计群组", "group_type": "dynamic"},
            headers={"Authorization": f"Bearer {token}"},
        )
        group_id = create_response.json["data"]["id"]

        # 获取统计
        stats_request, stats_response = await test_client.get(
            f"/api/v1/customer-groups/{group_id}/stats",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert stats_response.status == 200
        stats_data = stats_response.json
        assert stats_data["code"] == 0
        assert "member_count" in stats_data["data"]
        assert stats_data["data"]["name"] == "测试统计群组"
