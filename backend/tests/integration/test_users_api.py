"""
Users API 集成测试

测试覆盖：
1. GET /api/v1/users - 获取用户列表、筛选用户
2. POST /api/v1/users - 创建用户成功、创建重复用户
3. PUT /api/v1/users/:id - 更新用户成功、用户不存在
4. DELETE /api/v1/users/:id - 删除用户成功
"""

import bcrypt
import pytest
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
        text("""
        INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
        VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
        """),
        {
            "username": f"{username}_1",
            "password_hash": password_hash,
            "email": "list1@example.com",
            "real_name": "用户一",
            "is_active": True,
        },
    )
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
        VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
        """),
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
        text("""
        INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
        VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
        """),
        {
            "username": f"{username}_active",
            "password_hash": password_hash,
            "email": "filter_active@example.com",
            "real_name": "活跃用户",
            "is_active": True,
        },
    )
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
        VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
        """),
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
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
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
        text("""
        INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
        VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
        """),
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
        text("""
        INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
        VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
        """),
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


@pytest.mark.asyncio
async def test_upload_avatar_success(test_client, test_user):
    """测试头像上传成功"""
    import io

    from PIL import Image

    # 创建测试图片
    img = Image.new("RGB", (200, 200), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)

    # 登录
    _, login_resp = await test_client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    token = login_resp.json["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 上传头像
    _, response = await test_client.post(
        "/api/v1/users/avatar",
        headers=headers,
        files={"file": ("test.jpg", buffer, "image/jpeg")},
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["avatar_url"].startswith("/uploads/avatars/")


@pytest.mark.asyncio
async def test_user_options_unauthenticated(test_client):
    """测试获取用户选项列表 - 未认证应返回 401"""
    _, response = await test_client.get("/api/v1/users/options")
    assert response.status == 401


@pytest.mark.asyncio
async def test_user_options_returns_managers(test_client, db_session, test_user):
    """测试获取用户选项列表 - 返回 id/username/real_name 基础字段"""
    username = "options_test"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
        VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
        """),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "options_test@example.com",
            "real_name": "选项测试员",
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

        _, response = await test_client.get("/api/v1/users/options", headers=headers)

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["data"]["total"] >= 1
        # 返回的选项中应能找到刚创建的用户，且含 real_name/username
        created_user = next((u for u in data["data"]["list"] if u["username"] == username), None)
        assert created_user is not None
        assert created_user["real_name"] == "选项测试员"
        assert created_user["username"] == username
        # 选项接口不暴露邮箱等敏感字段
        assert "email" not in created_user
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_user_options_no_users_view_permission(test_client, db_session, test_user):
    """测试无 users:view 权限的角色也能访问 /users/options

    回归验证：运营/销售经理等非 admin 角色缺少 users:view 时，
    客户管理页的经理下拉/姓名展示仍正常（根因：GET /users 需要 users:view，
    导致非 admin 拿不到经理列表，前端回退显示 #id）。
    """
    username = "no_users_view"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db_session.execute(text("DELETE FROM users WHERE username = :username"), {"username": username})
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "no_users_view@example.com",
            "is_active": True,
        },
    )
    db_session.commit()

    try:
        _, login_resp = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert login_resp.status == 200
        token = login_resp.json["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Patch permission cache：模拟该角色无任何权限（默认 mock 会给所有用户完整权限）
        from unittest.mock import AsyncMock

        from app.cache import permissions as perm_module

        original_get = perm_module.permission_cache.get_permissions
        perm_module.permission_cache.get_permissions = AsyncMock(return_value=set())
        try:
            # 无 users:view 时访问完整用户列表应被拒绝（权限校验仍有效）
            _, forbidden_resp = await test_client.get("/api/v1/users", headers=headers)
            assert forbidden_resp.status == 403

            # 但 /users/options 应可访问（仅需登录）
            _, response = await test_client.get("/api/v1/users/options", headers=headers)
            assert response.status == 200
            data = response.json
            assert data["code"] == 0
            assert data["data"]["total"] >= 1
        finally:
            perm_module.permission_cache.get_permissions = original_get
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"), {"username": username}
        )
        db_session.commit()
