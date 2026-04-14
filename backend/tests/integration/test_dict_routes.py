"""字典路由集成测试"""

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


@pytest.mark.asyncio
async def test_get_industry_types_requires_auth(test_client):
    """测试未认证访问被拒绝"""
    _req, response = await test_client.get("/api/v1/dicts/industry_types")
    assert response.status in (401, 403)


@pytest.mark.asyncio
async def test_get_industry_types_returns_success(test_client, auth_headers):
    """测试认证后成功返回行业类型列表"""
    _req, response = await test_client.get(
        "/api/v1/dicts/industry_types",
        headers=auth_headers,
    )
    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert "data" in data
    assert isinstance(data["data"], list)
    if len(data["data"]) > 0:
        item = data["data"][0]
        assert "id" in item
        assert "name" in item
        assert "sort_order" in item
