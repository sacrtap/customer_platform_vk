"""
Users API 集成测试

测试覆盖：
1. GET /api/v1/users - 获取用户列表、筛选用户
2. POST /api/v1/users - 创建用户成功、创建重复用户
3. PUT /api/v1/users/:id - 更新用户成功、用户不存在
4. DELETE /api/v1/users/:id - 删除用户成功
"""

import pytest
import bcrypt
from sqlalchemy import text


@pytest.mark.asyncio
async def test_list_users_success(test_client, db_session, test_user):
    """测试获取用户列表 API - 成功场景"""
    username = "list_users_test"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db_session.execute(
        text("DELETE FROM users WHERE username LIKE :username"),
        {"username": f"{username}%"},
    )
    db_session.execute(
        text(
            """
        INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
        VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
        """
        ),
        {
            "username": f"{username}_1",
            "password_hash": password_hash,
            "email": "list1@example.com",
            "real_name": "用户一",
            "is_active": True,
        },
    )
    db_session.execute(
        text(
            """
        INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
        VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
        """
        ),
        {
            "username": f"{username}_2",
            "password_hash": password_hash,
            "email": "list2@example.com",
            "real_name": "用户二",
            "is_active": True,
        },
    )
    db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        request, response = await test_client.get(
            "/api/v1/users",
            headers=headers,
            params={"page": 1, "page_size": 20},
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "success"
        assert "list" in data["data"]
        assert "total" in data["data"]
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 20
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username LIKE :username"),
            {"username": f"{username}%"},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_list_users_with_filter(test_client, db_session, test_user):
    """测试获取用户列表 API - 筛选用户"""
    username = "filter_users_test"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db_session.execute(
        text("DELETE FROM users WHERE username LIKE :username"),
        {"username": f"{username}%"},
    )
    db_session.execute(
        text(
            """
        INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
        VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
        """
        ),
        {
            "username": f"{username}_active",
            "password_hash": password_hash,
            "email": "filter_active@example.com",
            "real_name": "活跃用户",
            "is_active": True,
        },
    )
    db_session.execute(
        text(
            """
        INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
        VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
        """
        ),
        {
            "username": f"{username}_inactive",
            "password_hash": password_hash,
            "email": "filter_inactive@example.com",
            "real_name": "非活跃用户",
            "is_active": False,
        },
    )
    db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        request, response = await test_client.get(
            "/api/v1/users",
            headers=headers,
            params={"page": 1, "page_size": 10},
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["data"]["total"] >= 2
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username LIKE :username"),
            {"username": f"{username}%"},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_create_user_success(test_client, db_session, test_user):
    """测试创建用户 API - 成功场景"""
    username = "create_user_success_test"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        request, response = await test_client.post(
            "/api/v1/users",
            headers=headers,
            json={
                "username": username,
                "password": password,
                "email": "create_success@example.com",
                "real_name": "创建成功测试用户",
            },
        )

        assert response.status == 201
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "创建成功"
        assert data["data"]["username"] == username
        assert data["data"]["email"] == "create_success@example.com"
        assert data["data"]["real_name"] == "创建成功测试用户"
        assert "id" in data["data"]
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_create_user_duplicate(test_client, db_session, test_user):
    """测试创建用户 API - 创建重复用户"""
    username = "create_user_duplicate_test"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    db_session.execute(
        text(
            """
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """
        ),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "duplicate@example.com",
            "is_active": True,
        },
    )
    db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        request, response = await test_client.post(
            "/api/v1/users",
            headers=headers,
            json={
                "username": username,
                "password": password,
                "email": "duplicate2@example.com",
                "real_name": "重复用户测试",
            },
        )

        assert response.status == 400
        data = response.json
        assert data["code"] == 40003
        assert "已存在" in data["message"]
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_update_user_success(test_client, db_session, test_user):
    """测试更新用户信息 API - 成功场景"""
    username = "update_user_success_test"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    db_session.execute(
        text(
            """
        INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
        VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
        """
        ),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "update_old@example.com",
            "real_name": "旧名字",
            "is_active": True,
        },
    )
    db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        user_result = db_session.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": username},
        )
        user_id = user_result.scalar()

        headers = {"Authorization": f"Bearer {token}"}
        request, response = await test_client.put(
            f"/api/v1/users/{user_id}",
            headers=headers,
            json={
                "email": "update_new@example.com",
                "real_name": "新名字",
                "is_active": False,
            },
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "更新成功"
        assert data["data"]["email"] == "update_new@example.com"
        assert data["data"]["real_name"] == "新名字"
        assert data["data"]["is_active"] is False
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_update_user_not_found(test_client, db_session, test_user):
    """测试更新用户信息 API - 用户不存在"""
    login_request, login_response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    assert login_response.status == 200
    token = login_response.json["data"]["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    request, response = await test_client.put(
        "/api/v1/users/999999",
        headers=headers,
        json={
            "email": "nonexistent@example.com",
            "real_name": "不存在的用户",
        },
    )

    assert response.status == 404
    data = response.json
    assert data["code"] == 40401
    assert data["message"] == "用户不存在"


@pytest.mark.asyncio
async def test_delete_user_success(test_client, db_session, test_user):
    """测试删除用户 API - 成功场景"""
    username = "delete_user_success_test"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    db_session.execute(
        text(
            """
        INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
        VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
        """
        ),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "delete@example.com",
            "real_name": "待删除用户",
            "is_active": True,
        },
    )
    db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        user_result = db_session.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": username},
        )
        user_id = user_result.scalar()

        headers = {"Authorization": f"Bearer {token}"}
        request, response = await test_client.delete(
            f"/api/v1/users/{user_id}",
            headers=headers,
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "删除成功"

        deleted_user_result = db_session.execute(
            text("SELECT deleted_at FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        )
        deleted_at = deleted_user_result.scalar()
        assert deleted_at is not None
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.commit()
