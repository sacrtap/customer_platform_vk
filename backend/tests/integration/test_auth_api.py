"""
Auth API 集成测试

测试覆盖：
1. /api/v1/auth/login - 登录成功、密码错误、用户不存在
2. /api/v1/auth/refresh - 刷新 Token 成功、无效 Token
3. /api/v1/auth/logout - 登出成功
4. /api/v1/auth/me - 获取当前用户信息
"""

import bcrypt
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_login_success(test_client, db_session):
    """测试登录 API - 成功场景"""
    username = "login_test_user"
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
            "email": "login_test@example.com",
            "real_name": "测试用户",
            "is_active": True,
        },
    )
    db_session.commit()

    try:
        request, response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "登录成功"
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["token_type"] == "Bearer"
        assert data["data"]["user"]["username"] == username
        assert data["data"]["user"]["email"] == "login_test@example.com"
        assert "permissions" in data["data"]
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_login_wrong_password(test_client, db_session):
    """测试登录 API - 密码错误"""
    username = "wrong_pwd_user"
    password = "correct123"
    wrong_password = "wrong456"
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
            "email": "wrongpwd@example.com",
            "is_active": True,
        },
    )
    db_session.commit()

    try:
        request, response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": wrong_password},
        )

        assert response.status == 401
        data = response.json
        assert data["code"] == 40101
        assert data["message"] == "用户名或密码错误"
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_login_user_not_found(test_client):
    """测试登录 API - 用户不存在"""
    request, response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": "nonexistent_user_xyz", "password": "somepassword"},
    )

    assert response.status == 401
    data = response.json
    assert data["code"] == 40101
    assert data["message"] == "用户名或密码错误"


@pytest.mark.asyncio
async def test_refresh_token_success(test_client, db_session):
    """测试刷新 Token API - 成功场景"""

    username = "refresh_test_user"
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
            "email": "refresh@example.com",
            "is_active": True,
        },
    )
    db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert login_response.status == 200
        refresh_token = login_response.json["data"]["refresh_token"]

        request, response = await test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "Token 刷新成功"
        assert "access_token" in data["data"]
        assert data["data"]["token_type"] == "Bearer"
    finally:
        db_session.execute(
            text(
                "DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE username = :username)"
            ),
            {"username": username},
        )
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_refresh_token_invalid(test_client):
    """测试刷新 Token API - 无效 Token"""
    request, response = await test_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid_token_xyz123"},
    )

    assert response.status == 401
    data = response.json
    assert data["code"] == 40101
    assert data["message"] == "Refresh Token 无效或已过期"


@pytest.mark.asyncio
async def test_logout_success(test_client, db_session):
    """测试登出 API - 成功场景"""
    username = "logout_test_user"
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
            "email": "logout@example.com",
            "is_active": True,
        },
    )
    db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        request, response = await test_client.post(
            "/api/v1/auth/logout",
            headers=headers,
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "登出成功"
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_get_me_success(test_client, db_session):
    """测试获取当前用户信息 API - 成功场景"""
    username = "me_test_user"
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
            "email": "me@example.com",
            "real_name": "我的名字",
            "is_active": True,
        },
    )
    db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        request, response = await test_client.get("/api/v1/auth/me", headers=headers)

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "success"
        assert data["data"]["username"] == username
        assert "user_id" in data["data"]
        assert "roles" in data["data"]
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_auth_middleware_exception_returns_json_500(monkeypatch):
    """认证中间件内部异常时返回约定 JSON 500，而非 Sanic 默认 HTML 错误页

    回归背景：中间件内曾误用 ``app.logger``（Sanic 无该属性），使兜底 except
    自身抛 AttributeError —— 客户端收到 HTML 错误页，且真实异常信息彻底丢失。

    这里用独立 app 注册真实 ``auth_middleware``，令黑名单服务在认证过程中抛异常，
    直接验证异常分支的响应形态（不依赖 conftest 的 app 实例与其模块缓存策略）。
    """
    from uuid import uuid4

    from sanic import Sanic
    from sanic.response import json as sanic_json

    import app.middleware.auth as auth_mod
    from app.constants import ErrorCodes
    from app.middleware.auth import auth_middleware
    from app.services.auth import AuthService

    app = Sanic(f"auth_mw_probe_{uuid4().hex[:8]}")

    @app.middleware("request")
    async def _provide_db_session(request):
        request.ctx.db_session = None

    auth_middleware(app)

    @app.get("/probe")
    async def _probe(request):
        return sanic_json({"code": 0})

    calls: list[str] = []

    class _BoomBlacklistService:
        """黑名单服务替身：任何调用都抛异常，触发认证中间件兜底分支"""

        def __init__(self, *_args, **_kwargs):
            pass

        async def is_blacklisted(self, jti: str) -> bool:
            calls.append(jti)
            raise RuntimeError("simulated redis outage")

    monkeypatch.setattr(auth_mod, "TokenBlacklistService", _BoomBlacklistService)

    token = AuthService.create_access_token(1, "probe_user", [])

    _request, response = await app.asgi_client.get(
        "/probe", headers={"Authorization": f"Bearer {token}"}
    )

    assert calls, "测试未能触发认证中间件的黑名单分支"
    assert response.status == 500
    body = response.json
    assert body["code"] == ErrorCodes.INTERNAL_ERROR
    assert "中间件错误" in body["message"]
