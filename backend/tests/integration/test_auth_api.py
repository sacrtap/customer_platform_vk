"""
客户运营中台 - Auth API 集成测试
测试认证模块的所有端点
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sanic import Sanic
from sanic_testing.testing import SanicTestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from app.main import create_app
from app.config import settings
from app.models.base import Base


# 测试数据库配置
TEST_DATABASE_URL = (
    "postgresql+asyncpg://user:password@localhost:5432/customer_platform_test"
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """创建测试数据库引擎"""
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
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """创建数据库会话"""
    async_session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="session")
def app() -> Sanic:
    """创建应用实例"""
    return create_app()


@pytest.fixture(scope="session")
def client(app: Sanic) -> SanicTestClient:
    """创建测试客户端"""
    return app.test_client


class TestAuthLogin:
    """登录端点测试"""

    async def test_login_success(
        self, client: SanicTestClient, db_session: AsyncSession
    ):
        """测试登录成功 - 使用正确的用户名和密码"""
        from app.models.users import User
        import bcrypt

        # 创建测试用户
        password = "test123456"
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(
            username="login_success_test",
            password_hash=password_hash,
            email="login_success@example.com",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        # 测试登录
        request, response = await client.post(
            "/api/v1/auth/login",
            json={"username": "login_success_test", "password": password},
        )

        assert response.status == 200
        assert response.json["code"] == 0
        assert response.json["message"] == "登录成功"
        assert "access_token" in response.json["data"]
        assert "refresh_token" in response.json["data"]
        assert response.json["data"]["token_type"] == "Bearer"
        assert response.json["data"]["user"]["username"] == "login_success_test"
        assert response.json["data"]["user"]["email"] == "login_success@example.com"

    async def test_login_wrong_password(
        self, client: SanicTestClient, db_session: AsyncSession
    ):
        """测试登录失败 - 密码错误"""
        from app.models.users import User
        import bcrypt

        # 创建测试用户
        password_hash = bcrypt.hashpw(b"test123456", bcrypt.gensalt()).decode()
        user = User(
            username="wrong_pwd_test",
            password_hash=password_hash,
            email="wrong_pwd@example.com",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        # 测试登录 - 使用错误密码
        request, response = await client.post(
            "/api/v1/auth/login",
            json={"username": "wrong_pwd_test", "password": "wrong_password"},
        )

        assert response.status == 401
        assert response.json["code"] == 40101
        assert response.json["message"] == "用户名或密码错误"

    async def test_login_user_not_found(
        self, client: SanicTestClient, db_session: AsyncSession
    ):
        """测试登录失败 - 用户不存在"""
        # 测试登录 - 使用不存在的用户名
        request, response = await client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent_user", "password": "any_password"},
        )

        assert response.status == 401
        assert response.json["code"] == 40101
        assert response.json["message"] == "用户名或密码错误"


class TestAuthRefresh:
    """Token 刷新端点测试"""

    async def test_refresh_token_success(
        self, client: SanicTestClient, db_session: AsyncSession
    ):
        """测试刷新 Token 成功"""
        from app.models.users import User
        from app.services.auth import AuthService
        import bcrypt

        # 创建测试用户
        password_hash = bcrypt.hashpw(b"test123456", bcrypt.gensalt()).decode()
        user = User(
            username="refresh_test",
            password_hash=password_hash,
            email="refresh@example.com",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # 生成有效的 refresh token
        refresh_token = AuthService.create_refresh_token(user_id=user.id)

        # 测试刷新 token
        request, response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status == 200
        assert response.json["code"] == 0
        assert response.json["message"] == "Token 刷新成功"
        assert "access_token" in response.json["data"]
        assert response.json["data"]["token_type"] == "Bearer"

    async def test_refresh_token_invalid(
        self, client: SanicTestClient, db_session: AsyncSession
    ):
        """测试刷新 Token 失败 - 无效的 token"""
        # 测试刷新 token - 使用无效的 token
        request, response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token_xyz123"},
        )

        assert response.status == 401
        assert response.json["code"] == 40101
        assert response.json["message"] == "Refresh Token 无效或已过期"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
