"""
Audit Logs API 集成测试

测试覆盖：
1. GET /api/v1/audit-logs - 获取审计日志列表、筛选审计日志
2. GET /api/v1/audit-logs/actions - 获取操作类型列表
3. GET /api/v1/audit-logs/modules - 获取模块列表
"""

import pytest
from datetime import datetime, timedelta


@pytest.fixture
async def auth_token(test_client, test_user):
    """获取认证 Token"""
    login_request, login_response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    assert login_response.status == 200
    return login_response.json["data"]["access_token"]


@pytest.mark.asyncio
async def test_list_audit_logs_success(test_client, auth_token):
    """测试获取审计日志列表 - 成功场景"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    request, response = await test_client.get(
        "/api/v1/audit-logs",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert "list" in data["data"]
    assert "total" in data["data"]
    assert "page" in data["data"]
    assert "page_size" in data["data"]


@pytest.mark.asyncio
async def test_list_audit_logs_with_filters(test_client, auth_token):
    """测试获取审计日志列表 - 带筛选条件"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    now = datetime.now()
    start_date = (now - timedelta(days=1)).isoformat()
    end_date = (now + timedelta(days=1)).isoformat()

    request, response = await test_client.get(
        "/api/v1/audit-logs",
        headers=headers,
        params={
            "action": "create",
            "module": "customers",
            "start_date": start_date,
            "end_date": end_date,
            "page": "1",
            "page_size": "10",
        },
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert data["data"]["page"] == 1
    assert data["data"]["page_size"] == 10


@pytest.mark.asyncio
async def test_get_audit_actions_success(test_client, auth_token):
    """测试获取操作类型列表 - 成功场景"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    request, response = await test_client.get(
        "/api/v1/audit-logs/actions",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_get_audit_modules_success(test_client, auth_token):
    """测试获取模块列表 - 成功场景"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    request, response = await test_client.get(
        "/api/v1/audit-logs/modules",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert isinstance(data["data"], list)
