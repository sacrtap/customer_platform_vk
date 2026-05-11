"""行业类型路由集成测试"""

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


class TestGetIndustryTypes:
    """测试 GET /api/v1/industry-types"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.get("/api/v1/industry-types")
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_returns_success(self, test_client, auth_headers):
        """测试认证后成功返回行业类型列表"""
        _req, response = await test_client.get(
            "/api/v1/industry-types",
            headers=auth_headers,
        )
        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert "data" in data
        assert isinstance(data["data"], list)


class TestCreateIndustryType:
    """测试 POST /api/v1/industry-types"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.post("/api/v1/industry-types")
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_creates_success(self, test_client, auth_headers):
        """测试成功创建行业类型"""
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "测试行业", "sort_order": 100},
            headers=auth_headers,
        )
        assert response.status == 201
        data = response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "测试行业"
        assert data["data"]["sort_order"] == 100
        assert "id" in data["data"]

    @pytest.mark.asyncio
    async def test_validates_required_fields(self, test_client, auth_headers):
        """测试缺少必填字段返回 422"""
        # 缺少 sort_order
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "测试行业"},
            headers=auth_headers,
        )
        assert response.status == 422

        # 缺少 name
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"sort_order": 100},
            headers=auth_headers,
        )
        assert response.status == 422

        # 都缺少
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={},
            headers=auth_headers,
        )
        assert response.status == 422

    @pytest.mark.asyncio
    async def test_prevents_duplicate_name(self, test_client, auth_headers):
        """测试重复名称返回 409"""
        # 创建第一个
        _req, _ = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "重复测试行业", "sort_order": 1},
            headers=auth_headers,
        )

        # 尝试创建同名
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "重复测试行业", "sort_order": 2},
            headers=auth_headers,
        )
        assert response.status == 409
        assert "已存在" in response.json["message"]


class TestUpdateIndustryType:
    """测试 PUT /api/v1/industry-types/{id}"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.put("/api/v1/industry-types/1")
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_updates_success(self, test_client, auth_headers):
        """测试成功更新行业类型"""
        # 先创建一个
        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "原始名称", "sort_order": 1},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        # 更新
        _req, response = await test_client.put(
            f"/api/v1/industry-types/{industry_id}",
            json={"name": "新名称", "sort_order": 2},
            headers=auth_headers,
        )
        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "新名称"
        assert data["data"]["sort_order"] == 2

    @pytest.mark.asyncio
    async def test_returns_404_for_not_found(self, test_client, auth_headers):
        """测试不存在的 ID 返回 404"""
        _req, response = await test_client.put(
            "/api/v1/industry-types/99999",
            json={"name": "新名称", "sort_order": 1},
            headers=auth_headers,
        )
        assert response.status == 404

    @pytest.mark.asyncio
    async def test_validates_required_fields(self, test_client, auth_headers):
        """测试缺少必填字段返回 422"""
        # 先创建一个
        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "原始名称", "sort_order": 1},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        # 缺少 sort_order
        _req, response = await test_client.put(
            f"/api/v1/industry-types/{industry_id}",
            json={"name": "新名称"},
            headers=auth_headers,
        )
        assert response.status == 422

    @pytest.mark.asyncio
    async def test_prevents_duplicate_name(self, test_client, auth_headers):
        """测试更新时重复名称返回 409"""
        # 创建两个行业类型
        _req, resp1 = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "行业A", "sort_order": 1},
            headers=auth_headers,
        )
        id_a = resp1.json["data"]["id"]

        _req, resp2 = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "行业B", "sort_order": 2},
            headers=auth_headers,
        )

        # 尝试将行业A更新为行业B的名称（应失败）
        _req, response = await test_client.put(
            f"/api/v1/industry-types/{id_a}",
            json={"name": "行业B", "sort_order": 3},
            headers=auth_headers,
        )
        assert response.status == 409
        assert "已存在" in response.json["message"]


class TestDeleteIndustryType:
    """测试 DELETE /api/v1/industry-types/{id}"""

    @pytest.mark.asyncio
    async def test_requires_auth(self, test_client):
        """测试未认证访问被拒绝"""
        _req, response = await test_client.delete("/api/v1/industry-types/1")
        assert response.status in (401, 403)

    @pytest.mark.asyncio
    async def test_deletes_success(self, test_client, auth_headers):
        """测试成功软删除"""
        # 先创建一个
        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "待删除", "sort_order": 1},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        # 删除
        _req, response = await test_client.delete(
            f"/api/v1/industry-types/{industry_id}",
            headers=auth_headers,
        )
        assert response.status == 200
        assert response.json["code"] == 0

        # 验证不再出现在列表中
        _req, list_resp = await test_client.get("/api/v1/industry-types", headers=auth_headers)
        ids = [item["id"] for item in list_resp.json["data"]]
        assert industry_id not in ids

    @pytest.mark.asyncio
    async def test_returns_404_for_not_found(self, test_client, auth_headers):
        """测试不存在的 ID 返回 404"""
        _req, response = await test_client.delete(
            "/api/v1/industry-types/99999",
            headers=auth_headers,
        )
        assert response.status == 404
