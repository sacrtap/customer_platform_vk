"""
集成测试配置 - 使用 Sanic ASGI Client + pytest-asyncio

架构说明：
- 使用 Sanic 内置的 ASGI 测试客户端
- 数据库使用异步引擎 (asyncpg)，与生产环境一致
- 使用 pytest-asyncio 管理事件循环
- 所有测试函数使用异步方式 (@pytest.mark.asyncio)
"""

# ============================================================
# 必须在导入 ANY 应用代码之前设置环境变量
# ============================================================
import sys
import os

# 强制设置固定的 JWT_SECRET 和 WEBHOOK_SECRET
os.environ["JWT_SECRET"] = "integration_test_jwt_secret_key_fixed_12345678"
os.environ["WEBHOOK_SECRET"] = "integration_test_webhook_secret_key_fixed_12345678"

# 清除所有可能的 settings 缓存
modules_to_clear = [k for k in list(sys.modules.keys()) if k.startswith("app")]
for mod in modules_to_clear:
    del sys.modules[mod]

# 现在才导入应用代码
import pytest
import bcrypt
from unittest.mock import MagicMock, patch
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy import text

from app.main import create_app
from app.models.base import BaseModel
from app.models import groups  # 确保 customer_groups 表被创建

# 测试数据库配置 - 使用异步驱动 (asyncpg)
TEST_DATABASE_URL = "postgresql+asyncpg://localhost:5432/customer_platform_test"


@pytest.fixture(scope="function")
def mock_scheduler():
    """Mock APScheduler 避免初始化问题"""
    with patch("app.tasks.scheduler.scheduler") as mock_sched:
        mock_sched.running = False
        mock_sched.start = MagicMock()
        mock_sched.shutdown = MagicMock()
        mock_sched.get_jobs = MagicMock(return_value=[])
        yield mock_sched


@pytest.fixture(scope="function")
async def test_engine() -> AsyncEngine:
    """创建测试数据库引擎（异步）"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)
        await conn.run_sync(BaseModel.metadata.create_all)

    yield engine

    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncSession:
    """创建数据库会话（异步）"""
    SessionLocal = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture(scope="function")
async def app(test_engine, mock_scheduler):
    """创建 Sanic 应用实例（使用测试数据库引擎和 mock 调度器）"""
    import uuid

    unique_app_name = f"test_app_{uuid.uuid4().hex[:8]}"

    app_instance = create_app(
        app_name=unique_app_name,
        database_engine=test_engine,
    )
    yield app_instance


@pytest.fixture(scope="function")
async def test_user(db_session: AsyncSession):
    """创建测试用户（异步）"""
    username = "test_user"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # 清理旧数据并创建新用户
    # 先删除该用户创建的群组（外键约束）
    await db_session.execute(
        text(
            "DELETE FROM customer_groups WHERE created_by = (SELECT id FROM users WHERE username = :username)"
        ),
        {"username": username},
    )
    await db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    await db_session.commit()

    await db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "test@example.com",
            "is_active": True,
        },
    )
    await db_session.commit()

    yield {"username": username, "password": password}

    # 清理：先删除群组再删除用户
    await db_session.execute(
        text(
            "DELETE FROM customer_groups WHERE created_by = (SELECT id FROM users WHERE username = :username)"
        ),
        {"username": username},
    )
    await db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    await db_session.commit()


# 使用 pytest-asyncio 管理事件循环
# 所有测试函数使用 @pytest.mark.asyncio 标记


@pytest.fixture(scope="function")
async def test_client(app):
    """
    创建 Sanic ASGI 测试客户端（异步方式）

    使用 Sanic 内置的 asgi_client，与 pytest-asyncio 完全兼容
    支持异步数据库操作和异步 API 调用

    ASGI 客户端不需要手动启动/关闭服务器，由 Sanic 内部管理
    """
    yield app.asgi_client
