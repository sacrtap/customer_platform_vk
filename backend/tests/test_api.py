"""
客户运营中台 - API 集成测试
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from app.main import create_app
from app.config import settings
from app.models.base import Base


# 测试数据库配置 (使用内存数据库或独立测试数据库)
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


@pytest.fixture(scope="function")
async def auth_token(db_session: AsyncSession) -> str:
    """创建测试用户并返回 Token"""
    from app.models.users import User
    from app.services.auth import AuthService
    import bcrypt

    # 创建测试用户
    password_hash = bcrypt.hashpw(b"test123456", bcrypt.gensalt()).decode()
    user = User(
        username="test_user",
        password_hash=password_hash,
        email="test@example.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # 生成 Token
    token = AuthService.create_access_token(
        user_id=user.id, username=user.username, roles=["user"]
    )

    return token


# ==================== 认证模块测试 ====================


class TestAuth:
    """认证模块测试"""

    async def test_login_success(
        self, client: SanicTestClient, db_session: AsyncSession
    ):
        """测试登录成功"""
        from app.models.users import User
        import bcrypt

        # 创建测试用户
        password = "test123456"
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(
            username="login_test",
            password_hash=password_hash,
            email="login@example.com",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        # 测试登录
        request, response = await client.post(
            "/api/v1/auth/login", json={"username": "login_test", "password": password}
        )

        assert response.status == 200
        assert response.json["code"] == 0
        assert "access_token" in response.json["data"]
        assert "refresh_token" in response.json["data"]

    async def test_login_wrong_password(
        self, client: SanicTestClient, db_session: AsyncSession
    ):
        """测试密码错误"""
        from app.models.users import User
        import bcrypt

        password_hash = bcrypt.hashpw(b"test123456", bcrypt.gensalt()).decode()
        user = User(
            username="wrong_pwd",
            password_hash=password_hash,
            email="wrong@example.com",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()

        request, response = await client.post(
            "/api/v1/auth/login",
            json={"username": "wrong_pwd", "password": "wrong_password"},
        )

        assert response.status == 401
        assert response.json["code"] == 40101

    async def test_get_me(self, client: SanicTestClient, auth_token: str):
        """测试获取当前用户信息"""
        request, response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status == 200
        assert response.json["code"] == 0
        assert "user_id" in response.json["data"]


# ==================== 用户模块测试 ====================


class TestUsers:
    """用户模块测试"""

    async def test_create_user(self, client: SanicTestClient, auth_token: str):
        """测试创建用户"""
        request, response = await client.post(
            "/api/v1/users",
            json={
                "username": "new_user",
                "password": "password123",
                "email": "new@example.com",
                "real_name": "新用户",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 201
        assert response.json["code"] == 0
        assert response.json["data"]["username"] == "new_user"

    async def test_get_users(self, client: SanicTestClient, auth_token: str):
        """测试获取用户列表"""
        request, response = await client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status == 200
        assert response.json["code"] == 0
        assert "list" in response.json["data"]

    async def test_update_user(
        self, client: SanicTestClient, auth_token: str, db_session: AsyncSession
    ):
        """测试更新用户"""
        from app.models.users import User
        import bcrypt

        password_hash = bcrypt.hashpw(b"test123456", bcrypt.gensalt()).decode()
        user = User(
            username="update_test",
            password_hash=password_hash,
            email="update@example.com",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        request, response = await client.put(
            f"/api/v1/users/{user.id}",
            json={"email": "updated@example.com", "real_name": "更新用户"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 200
        assert response.json["code"] == 0
        assert response.json["data"]["email"] == "updated@example.com"

    async def test_delete_user(
        self, client: SanicTestClient, auth_token: str, db_session: AsyncSession
    ):
        """测试删除用户"""
        from app.models.users import User
        import bcrypt

        password_hash = bcrypt.hashpw(b"test123456", bcrypt.gensalt()).decode()
        user = User(
            username="delete_test",
            password_hash=password_hash,
            email="delete@example.com",
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        request, response = await client.delete(
            f"/api/v1/users/{user.id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 200
        assert response.json["code"] == 0


# ==================== 客户模块测试 ====================


class TestCustomers:
    """客户模块测试"""

    async def test_create_customer(self, client: SanicTestClient, auth_token: str):
        """测试创建客户"""
        request, response = await client.post(
            "/api/v1/customers",
            json={
                "company_id": "TEST001",
                "name": "测试公司",
                "account_type": "formal",
                "business_type": "A",
                "customer_level": "KA",
                "is_key_customer": False,
                "email": "test@company.com",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 201
        assert response.json["code"] == 0
        assert response.json["data"]["company_id"] == "TEST001"

    async def test_get_customers(self, client: SanicTestClient, auth_token: str):
        """测试获取客户列表"""
        request, response = await client.get(
            "/api/v1/customers", headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status == 200
        assert response.json["code"] == 0
        assert "list" in response.json["data"]

    async def test_update_customer(
        self, client: SanicTestClient, auth_token: str, db_session: AsyncSession
    ):
        """测试更新客户"""
        from app.models.customers import Customer

        customer = Customer(
            company_id="UPDATE001",
            name="更新公司",
            account_type="formal",
            is_key_customer=False,
        )
        db_session.add(customer)
        await db_session.commit()
        await db_session.refresh(customer)

        request, response = await client.put(
            f"/api/v1/customers/{customer.id}",
            json={"customer_level": "SKA", "is_key_customer": True},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 200
        assert response.json["code"] == 0
        assert response.json["data"]["customer_level"] == "SKA"


# ==================== 标签模块测试 ====================


class TestTags:
    """标签模块测试"""

    async def test_create_tag(self, client: SanicTestClient, auth_token: str):
        """测试创建标签"""
        request, response = await client.post(
            "/api/v1/tags",
            json={"name": "测试标签", "type": "customer", "category": "测试分类"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 201
        assert response.json["code"] == 0
        assert response.json["data"]["name"] == "测试标签"

    async def test_get_tags(self, client: SanicTestClient, auth_token: str):
        """测试获取标签列表"""
        request, response = await client.get(
            "/api/v1/tags", headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status == 200
        assert response.json["code"] == 0
        assert "list" in response.json["data"]


# ==================== 结算模块测试 ====================


class TestBilling:
    """结算模块测试"""

    async def test_get_balances(self, client: SanicTestClient, auth_token: str):
        """测试获取余额列表"""
        request, response = await client.get(
            "/api/v1/billing/balances",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 200
        assert response.json["code"] == 0

    async def test_recharge(
        self, client: SanicTestClient, auth_token: str, db_session: AsyncSession
    ):
        """测试充值"""
        from app.models.customers import Customer

        customer = Customer(
            company_id="RECHARGE001",
            name="充值测试公司",
            is_key_customer=False,
        )
        db_session.add(customer)
        await db_session.commit()
        await db_session.refresh(customer)

        request, response = await client.post(
            "/api/v1/billing/recharge",
            json={
                "customer_id": customer.id,
                "real_amount": 10000.00,
                "bonus_amount": 2000.00,
                "remark": "测试充值",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 201
        assert response.json["code"] == 0
        assert response.json["data"]["real_amount"] == 10000.00


# ==================== 分析模块测试 ====================


class TestAnalytics:
    """分析模块测试"""

    async def test_get_dashboard_stats(self, client: SanicTestClient, auth_token: str):
        """测试获取仪表盘统计"""
        request, response = await client.get(
            "/api/v1/analytics/dashboard/stats",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 200
        assert response.json["code"] == 0
        assert "total_customers" in response.json["data"]

    async def test_get_consumption_trend(
        self, client: SanicTestClient, auth_token: str
    ):
        """测试获取消耗趋势"""
        from datetime import date, timedelta

        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        request, response = await client.get(
            "/api/v1/analytics/consumption/trend",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 200
        assert response.json["code"] == 0


# ==================== 文件上传测试 ====================


class TestFiles:
    """文件上传测试"""

    async def test_upload_file(
        self, client: SanicTestClient, auth_token: str, tmp_path
    ):
        """测试文件上传"""
        import io

        # 创建测试文件
        test_content = b"test content"

        request, response = await client.post(
            "/api/v1/files/upload",
            files={
                "file": (
                    "test.xlsx",
                    io.BytesIO(test_content),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status == 201
        assert response.json["code"] == 0
        assert "file_path" in response.json["data"]


if __name__ == "__main__":
    pytest.main(["-v", __file__])
