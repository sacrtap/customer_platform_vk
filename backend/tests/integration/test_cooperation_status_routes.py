"""合作状态路由集成测试"""

import pytest


@pytest.fixture
async def auth_token(test_client, test_user):
    """获取认证 Token"""
    _login_request, login_response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    assert login_response.status == 200
    return login_response.json["data"]["access_token"]


@pytest.fixture
async def auth_headers(auth_token):
    """获取认证请求头"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestGetCooperationStatuses:
    """测试 GET /api/v1/cooperation-statuses"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.get("/api/v1/cooperation-statuses")
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_returns_success(self, test_client, auth_headers):
        """测试认证后成功返回合作状态列表"""
        _req, response = await test_client.get(
            "/api/v1/cooperation-statuses",
            headers=auth_headers,
        )
        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert "data" in data
        assert isinstance(data["data"], list)


class TestCreateCooperationStatus:
    """测试 POST /api/v1/cooperation-statuses"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.post("/api/v1/cooperation-statuses")
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_creates_success(self, test_client, auth_headers):
        """测试成功创建合作状态"""
        _req, response = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "测试状态_创建", "value": "test_create_status", "sort_order": 100},
            headers=auth_headers,
        )
        assert response.status == 201
        data = response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "测试状态_创建"
        assert data["data"]["value"] == "test_create_status"
        assert data["data"]["sort_order"] == 100
        assert "id" in data["data"]

    @pytest.mark.asyncio
    async def test_validates_required_fields(self, test_client, auth_headers):
        """测试缺少必填字段返回 422"""
        # 缺少 sort_order
        _req, response = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "缺排序", "value": "missing_sort"},
            headers=auth_headers,
        )
        assert response.status == 422

        # 缺少 value
        _req, response = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "缺值", "sort_order": 100},
            headers=auth_headers,
        )
        assert response.status == 422

        # 缺少 name
        _req, response = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"value": "missing_name", "sort_order": 100},
            headers=auth_headers,
        )
        assert response.status == 422

        # 都缺少
        _req, response = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={},
            headers=auth_headers,
        )
        assert response.status == 422

    @pytest.mark.asyncio
    async def test_prevents_duplicate_name(self, test_client, auth_headers):
        """测试重复名称返回 409"""
        # 创建第一个
        _req, _ = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "重复名测试_1", "value": "dup_name_val_1", "sort_order": 1},
            headers=auth_headers,
        )

        # 尝试用相同名称、不同值创建
        _req, response = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "重复名测试_1", "value": "dup_name_val_2", "sort_order": 2},
            headers=auth_headers,
        )
        assert response.status == 409
        assert "已存在" in response.json["message"]

    @pytest.mark.asyncio
    async def test_prevents_duplicate_value(self, test_client, auth_headers):
        """测试重复值返回 409"""
        # 创建第一个
        _req, _ = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "重值测试_A", "value": "dup_val_test", "sort_order": 1},
            headers=auth_headers,
        )

        # 尝试用相同值、不同名称创建
        _req, response = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "重值测试_B", "value": "dup_val_test", "sort_order": 2},
            headers=auth_headers,
        )
        assert response.status == 409
        assert "已存在" in response.json["message"]


class TestUpdateCooperationStatus:
    """测试 PUT /api/v1/cooperation-statuses/{id}"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.put("/api/v1/cooperation-statuses/1")
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_updates_success(self, test_client, auth_headers):
        """测试成功更新合作状态"""
        # 先创建一个
        _req, create_resp = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "更新前状态", "value": "before_update_val", "sort_order": 1},
            headers=auth_headers,
        )
        status_id = create_resp.json["data"]["id"]

        # 更新
        _req, response = await test_client.put(
            f"/api/v1/cooperation-statuses/{status_id}",
            json={"name": "更新后状态", "value": "after_update_val", "sort_order": 2},
            headers=auth_headers,
        )
        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "更新后状态"
        assert data["data"]["value"] == "after_update_val"
        assert data["data"]["sort_order"] == 2

    @pytest.mark.asyncio
    async def test_returns_404_for_not_found(self, test_client, auth_headers):
        """测试不存在的 ID 返回 404"""
        _req, response = await test_client.put(
            "/api/v1/cooperation-statuses/99999",
            json={"name": "不存在", "value": "not_found_val", "sort_order": 1},
            headers=auth_headers,
        )
        assert response.status == 404

    @pytest.mark.asyncio
    async def test_validates_required_fields(self, test_client, auth_headers):
        """测试缺少必填字段返回 422"""
        # 先创建一个
        _req, create_resp = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "校验前状态", "value": "validate_before_val", "sort_order": 1},
            headers=auth_headers,
        )
        status_id = create_resp.json["data"]["id"]

        # 缺少 value
        _req, response = await test_client.put(
            f"/api/v1/cooperation-statuses/{status_id}",
            json={"name": "校验后状态", "sort_order": 2},
            headers=auth_headers,
        )
        assert response.status == 422

    @pytest.mark.asyncio
    async def test_prevents_duplicate_name(self, test_client, auth_headers):
        """测试更新时重复名称返回 409"""
        # 创建两个合作状态
        _req, resp1 = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "upd_dup_name_A", "value": "upd_dup_name_a", "sort_order": 1},
            headers=auth_headers,
        )
        id_a = resp1.json["data"]["id"]

        _req, _ = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "upd_dup_name_B", "value": "upd_dup_name_b", "sort_order": 2},
            headers=auth_headers,
        )

        # 尝试将 A 更新为 B 的名称（应失败）
        _req, response = await test_client.put(
            f"/api/v1/cooperation-statuses/{id_a}",
            json={"name": "upd_dup_name_B", "value": "upd_dup_name_a", "sort_order": 3},
            headers=auth_headers,
        )
        assert response.status == 409
        assert "已存在" in response.json["message"]

    @pytest.mark.asyncio
    async def test_prevents_duplicate_value(self, test_client, auth_headers):
        """测试更新时重复值返回 409"""
        # 创建两个合作状态
        _req, resp1 = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "upd_dup_val_C", "value": "upd_dup_val_c", "sort_order": 1},
            headers=auth_headers,
        )
        id_c = resp1.json["data"]["id"]

        _req, _ = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "upd_dup_val_D", "value": "upd_dup_val_d", "sort_order": 2},
            headers=auth_headers,
        )

        # 尝试将 C 更新为 D 的值（应失败）
        _req, response = await test_client.put(
            f"/api/v1/cooperation-statuses/{id_c}",
            json={"name": "upd_dup_val_C", "value": "upd_dup_val_d", "sort_order": 3},
            headers=auth_headers,
        )
        assert response.status == 409
        assert "已存在" in response.json["message"]


class TestDeleteCooperationStatus:
    """测试 DELETE /api/v1/cooperation-statuses/{id}"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.delete("/api/v1/cooperation-statuses/1")
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_deletes_success(self, test_client, auth_headers):
        """测试成功软删除"""
        # 先创建一个
        _req, create_resp = await test_client.post(
            "/api/v1/cooperation-statuses",
            json={"name": "待删除状态", "value": "del_status_val", "sort_order": 1},
            headers=auth_headers,
        )
        status_id = create_resp.json["data"]["id"]

        # 删除
        _req, response = await test_client.delete(
            f"/api/v1/cooperation-statuses/{status_id}",
            headers=auth_headers,
        )
        assert response.status == 200
        assert response.json["code"] == 0

        # 验证不再出现在列表中
        _req, list_resp = await test_client.get(
            "/api/v1/cooperation-statuses", headers=auth_headers
        )
        ids = [item["id"] for item in list_resp.json["data"]]
        assert status_id not in ids

    @pytest.mark.asyncio
    async def test_returns_404_for_not_found(self, test_client, auth_headers):
        """测试不存在的 ID 返回 404"""
        _req, response = await test_client.delete(
            "/api/v1/cooperation-statuses/99999",
            headers=auth_headers,
        )
        assert response.status == 404
