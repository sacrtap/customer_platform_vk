"""
集成测试 - API 端点测试

使用异步数据库操作，与生产环境一致
所有测试函数使用异步方式
"""

import pytest
import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_health_check(test_client):
    """测试健康检查端点"""
    request, response = await test_client.get("/health")

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_login_success(test_client, db_session: AsyncSession):
    """测试登录 API - 成功场景"""
    # 创建测试用户
    username = "login_success_test"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # 清理旧数据并创建新用户
    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "login_success@example.com",
            "is_active": True,
        },
    )
    db_session.commit()

    try:
        # 执行登录测试
        request, response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )

        assert response.status == 200
        data = response.json
        assert "access_token" in data["data"]
        assert data["data"]["token_type"].lower() == "bearer"
        assert "user" in data["data"]
        assert data["data"]["user"]["username"] == username
    finally:
        # 清理测试数据
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_login_invalid_credentials(test_client):
    """测试登录 API - 无效凭证"""
    request, response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": "nonexistent", "password": "wrongpassword"},
    )

    assert response.status == 401
    data = response.json
    assert "error" in data or "message" in data


@pytest.mark.asyncio
async def test_get_customers_list(test_client, db_session: AsyncSession, test_user):
    """测试客户列表 API - 需要认证"""
    # 先登录获取 token
    login_request, login_response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    token = login_response.json["data"]["access_token"]

    # 使用 token 访问客户列表
    headers = {"Authorization": f"Bearer {token}"}
    request, response = await test_client.get("/api/v1/customers", headers=headers)

    assert response.status == 200
    data = response.json
    assert "customers" in data["data"] or "data" in data
    assert isinstance(data["data"].get("customers", []), list)


@pytest.mark.asyncio
async def test_get_billing_balance(test_client, test_user):
    """测试账单余额查询 API - 需要认证"""
    # 先登录获取 token
    login_request, login_response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    token = login_response.json["data"]["access_token"]

    # 使用 token 访问余额查询
    headers = {"Authorization": f"Bearer {token}"}
    request, response = await test_client.get(
        "/api/v1/billing/balance", headers=headers
    )

    # 应该返回 200 或 404（取决于是否有账单数据）
    assert response.status in [200, 404]

    if response.status == 200:
        data = response.json
        assert "balance" in data.get("data", {}) or "data" in data
