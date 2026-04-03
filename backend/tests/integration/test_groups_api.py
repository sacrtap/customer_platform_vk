"""客户群组 API 集成测试"""

import pytest
from sqlalchemy import text


class TestCreateGroup:
    """测试创建群组"""

    def test_create_dynamic_group(self, client, test_user, db_session):
        """测试创建动态群组"""
        # 先登录获取 token
        login_request, login_response = client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status_code == 200
        login_data = login_response.json
        assert login_data.get("code") == 0, f"Login failed: {login_data}"
        token = login_data["data"]["access_token"]

        request, response = client.post(
            "/api/v1/customer-groups",
            json={
                "name": "测试动态群组",
                "description": "测试描述",
                "group_type": "dynamic",
                "filter_conditions": {"customer_level": "KA"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "测试动态群组"
        assert "id" in data["data"]

    def test_create_static_group(self, client, test_user, db_session):
        """测试创建静态群组"""
        # 先登录获取 token
        login_request, login_response = client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status_code == 200
        token = login_response.json["data"]["access_token"]

        request, response = client.post(
            "/api/v1/customer-groups",
            json={"name": "测试静态群组", "group_type": "static"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "测试静态群组"

    def test_create_group_missing_name(self, client, test_user, db_session):
        """测试创建群组缺少名称"""
        # 先登录获取 token
        login_request, login_response = client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status_code == 200
        token = login_response.json["data"]["access_token"]

        request, response = client.post(
            "/api/v1/customer-groups",
            json={"description": "测试描述"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        data = response.json
        assert "不能为空" in data["message"]


class TestListGroups:
    """测试获取群组列表"""

    def test_list_user_groups(self, client, test_user, db_session):
        """测试获取用户的群组列表"""
        # 先登录获取 token
        login_request, login_response = client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status_code == 200
        token = login_response.json["data"]["access_token"]

        # 先创建一个群组
        client.post(
            "/api/v1/customer-groups",
            json={"name": "测试群组", "group_type": "dynamic"},
            headers={"Authorization": f"Bearer {token}"},
        )

        request, response = client.get(
            "/api/v1/customer-groups",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json
        assert data["code"] == 0
        assert len(data["data"]["list"]) >= 1

    def test_list_groups_unauthorized(self, client):
        """测试未认证访问群组列表"""
        request, response = client.get("/api/v1/customer-groups")

        assert response.status_code == 401
        data = response.json
        assert data["code"] == 40101


class TestGetGroup:
    """测试获取群组详情"""

    def test_get_group_detail(self, client, test_user, db_session):
        """测试获取群组详情"""
        # 先登录获取 token
        login_request, login_response = client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status_code == 200
        token = login_response.json["data"]["access_token"]

        # 先创建一个群组
        create_request, create_response = client.post(
            "/api/v1/customer-groups",
            json={"name": "测试详情群组", "group_type": "dynamic"},
            headers={"Authorization": f"Bearer {token}"},
        )
        group_id = create_response.json["data"]["id"]

        # 获取群组详情
        get_request, get_response = client.get(
            f"/api/v1/customer-groups/{group_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert get_response.status_code == 200
        data = get_response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "测试详情群组"

    def test_get_group_not_found(self, client, test_user, db_session):
        """测试获取不存在的群组"""
        # 先登录获取 token
        login_request, login_response = client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status_code == 200
        token = login_response.json["data"]["access_token"]

        request, response = client.get(
            "/api/v1/customer-groups/99999",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404
        data = response.json
        assert data["code"] == 40401


class TestDeleteGroup:
    """测试删除群组"""

    def test_delete_group(self, client, test_user, db_session):
        """测试删除群组"""
        # 先登录获取 token
        login_request, login_response = client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status_code == 200
        token = login_response.json["data"]["access_token"]

        # 先创建一个群组
        create_request, create_response = client.post(
            "/api/v1/customer-groups",
            json={"name": "待删除群组", "group_type": "dynamic"},
            headers={"Authorization": f"Bearer {token}"},
        )
        group_id = create_response.json["data"]["id"]

        # 删除群组
        delete_request, delete_response = client.delete(
            f"/api/v1/customer-groups/{group_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert delete_response.status_code == 200
        assert delete_response.json["code"] == 0

        # 验证群组已被删除
        get_request, get_response = client.get(
            f"/api/v1/customer-groups/{group_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_response.status_code == 404


class TestGroupMembers:
    """测试群组成员管理"""

    def test_add_and_remove_member(self, client, test_user, db_session):
        """测试添加和移除成员"""
        # 先登录获取 token
        login_request, login_response = client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status_code == 200
        token = login_response.json["data"]["access_token"]

        # 创建静态群组
        create_request, create_response = client.post(
            "/api/v1/customer-groups",
            json={"name": "测试成员群组", "group_type": "static"},
            headers={"Authorization": f"Bearer {token}"},
        )
        group_id = create_response.json["data"]["id"]

        # 创建一个测试客户
        db_session.execute(
            text("""
            INSERT INTO customers (company_id, name, created_at)
            VALUES ('TEST001', '测试客户', NOW())
            ON CONFLICT (company_id) DO NOTHING
            """)
        )
        db_session.commit()

        # 获取客户 ID
        result = db_session.execute(
            text("SELECT id FROM customers WHERE company_id = 'TEST001'")
        )
        customer_id = result.scalar()

        # 添加成员
        add_request, add_response = client.post(
            f"/api/v1/customer-groups/{group_id}/members",
            json={"customer_id": customer_id},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert add_response.status_code == 200
        assert add_response.json["code"] == 0

        # 获取成员列表
        members_request, members_response = client.get(
            f"/api/v1/customer-groups/{group_id}/members",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert members_response.status_code == 200
        members_data = members_response.json
        assert len(members_data["data"]["list"]) >= 1

        # 移除成员
        remove_request, remove_response = client.delete(
            f"/api/v1/customer-groups/{group_id}/members/{customer_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert remove_response.status_code == 200
        assert remove_response.json["code"] == 0


class TestGroupStats:
    """测试群组统计"""

    def test_get_group_stats(self, client, test_user, db_session):
        """测试获取群组统计信息"""
        # 先登录获取 token
        login_request, login_response = client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status_code == 200
        token = login_response.json["data"]["access_token"]

        # 创建群组
        create_request, create_response = client.post(
            "/api/v1/customer-groups",
            json={"name": "测试统计群组", "group_type": "dynamic"},
            headers={"Authorization": f"Bearer {token}"},
        )
        group_id = create_response.json["data"]["id"]

        # 获取统计
        stats_request, stats_response = client.get(
            f"/api/v1/customer-groups/{group_id}/stats",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert stats_response.status_code == 200
        stats_data = stats_response.json
        assert stats_data["code"] == 0
        assert "member_count" in stats_data["data"]
        assert stats_data["data"]["name"] == "测试统计群组"
