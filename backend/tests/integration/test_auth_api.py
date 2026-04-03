"""
客户运营中台 - Auth API 集成测试
测试认证模块的所有端点

使用 Sanic TestClient 进行同步测试，避免 ASGI 事件循环冲突
"""

import pytest
from sanic_testing.testing import SanicTestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from app.main import create_app
from app.models.base import Base


# 测试数据库配置
# 使用 Postgres.app 默认配置（无密码，当前用户）
TEST_DATABASE_URL = "postgresql+asyncpg://localhost:5432/customer_platform_test"


@pytest.fixture(scope="function")
async def test_engine():
    """创建测试数据库引擎（function 范围，避免事件循环问题）"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncSession:
    """创建数据库会话（与测试应用共享引擎）"""
    async_session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def app(test_engine):
    """创建应用实例（使用测试数据库引擎）"""
    app_instance = create_app(
        app_name="test_customer_platform_api",
        database_engine=test_engine,
    )
    yield app_instance


@pytest.fixture(scope="function")
def client(app) -> SanicTestClient:
    """创建 Sanic 测试客户端（同步模式）"""
    return app.test_client


# ==================== 登录端点测试 ====================


class TestAuthLogin:
    """登录端点测试"""

    def test_login_success(self, client: SanicTestClient, test_user):
        """测试登录成功 - 使用正确的用户名和密码"""
        username, password = test_user

        # 测试登录
        request, response = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )

        assert response.status_code == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "登录成功"
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["token_type"] == "Bearer"
        assert data["data"]["user"]["username"] == username

    def test_login_wrong_password(
        self, client: SanicTestClient, db_session: AsyncSession
    ):
        """测试登录失败 - 密码错误"""
        from app.models.users import User
        import bcrypt

        # 创建测试用户
        password = "test123456"
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(
            username="wrong_pwd_test",
            password_hash=password_hash,
            email="wrong_pwd@example.com",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        # 测试登录 - 使用错误密码
        request, response = client.post(
            "/api/v1/auth/login",
            json={"username": "wrong_pwd_test", "password": "wrong_password"},
        )

        assert response.status_code == 401
        data = response.json
        assert data["code"] == 40101
        assert data["message"] == "用户名或密码错误"

    def test_login_user_not_found(self, client: SanicTestClient):
        """测试登录失败 - 用户不存在"""
        # 测试登录 - 使用不存在的用户名
        request, response = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent_user", "password": "any_password"},
        )

        assert response.status_code == 401
        data = response.json
        assert data["code"] == 40101
        assert data["message"] == "用户名或密码错误"


@pytest.fixture(scope="function")
def test_user(test_engine):
    """创建测试用户 fixture（同步模式）"""
    import asyncio
    import bcrypt
    from sqlalchemy import text

    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    async def create_user():
        async with test_engine.begin() as conn:
            await conn.execute(
                text("""
                INSERT INTO users (username, password_hash, email, is_active, created_at)
                VALUES (:username, :password_hash, :email, :is_active, NOW())
            """),
                {
                    "username": "login_success_test",
                    "password_hash": password_hash,
                    "email": "login_success@example.com",
                    "is_active": True,
                },
            )

    asyncio.run(create_user())

    yield ("login_success_test", password)

    def test_login_user_not_found(self, client: SanicTestClient):
        """测试登录失败 - 用户不存在"""
        # 测试登录 - 使用不存在的用户名
        request, response = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent_user", "password": "any_password"},
        )

        assert response.status_code == 401
        data = response.json
        assert data["code"] == 40101
        assert data["message"] == "用户名或密码错误"


# ==================== Token 刷新端点测试 ====================


class TestAuthRefresh:
    """Token 刷新端点测试"""

    def test_refresh_token_success(
        self, client: SanicTestClient, db_session: AsyncSession
    ):
        """测试刷新 Token 成功"""
        from app.models.users import User
        from app.services.auth import AuthService
        import bcrypt

        # 创建测试用户
        password = "test123456"
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(
            username="refresh_test",
            password_hash=password_hash,
            email="refresh@example.com",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # 生成有效的 refresh token
        refresh_token = AuthService.create_refresh_token(user_id=user.id)

        # 测试刷新 token
        request, response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "Token 刷新成功"
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    def test_refresh_token_invalid(self, client: SanicTestClient):
        """测试刷新 Token - 无效的 token"""
        # 测试刷新 token - 使用无效的 refresh token
        request, response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token"},
        )

        assert response.status_code == 401
        data = response.json
        assert data["code"] == 40102
        assert "无效" in data["message"] or "invalid" in data["message"].lower()
