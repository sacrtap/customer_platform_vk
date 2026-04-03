"""
集成测试 - API 端点测试

使用同步数据库操作，避免事件循环冲突
所有测试函数都是同步的
"""

import pytest
import bcrypt
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_health_check(client):
    """测试健康检查端点"""
    request, response = client.get("/health")

    assert response.status_code == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["status"] == "healthy"


def test_login_success(client, db_session: Session):
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
        request, response = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )

        assert response.status_code == 200
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


def test_login_invalid_credentials(client):
    """测试登录 API - 无效凭证"""
    request, response = client.post(
        "/api/v1/auth/login",
        json={"username": "nonexistent", "password": "wrongpassword"},
    )

    assert response.status_code == 401
    data = response.json
    assert "error" in data or "message" in data


def test_get_customers_list(client, db_session: Session, test_user):
    """测试客户列表 API - 需要认证"""
    # 先登录获取 token
    login_request, login_response = client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    token = login_response.json["data"]["access_token"]

    # 使用 token 访问客户列表
    headers = {"Authorization": f"Bearer {token}"}
    request, response = client.get("/api/v1/customers", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert "customers" in data["data"] or "data" in data
    assert isinstance(data["data"].get("customers", []), list)


def test_get_billing_balance(client, test_user):
    """测试账单余额查询 API - 需要认证"""
    # 先登录获取 token
    login_request, login_response = client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    token = login_response.json["data"]["access_token"]

    # 使用 token 访问余额查询
    headers = {"Authorization": f"Bearer {token}"}
    request, response = client.get("/api/v1/billing/balance", headers=headers)

    # 应该返回 200 或 404（取决于是否有账单数据）
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        data = response.json
        assert "balance" in data.get("data", {}) or "data" in data
