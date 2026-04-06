"""
集成测试配置 - 使用 Sanic ASGI Client + pytest-asyncio

架构说明：
- 使用 Sanic 内置的 ASGI 测试客户端
- 数据库使用同步引擎（因为 Analytics Service 使用同步 SQLAlchemy）
- 使用 pytest-asyncio 管理事件循环
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
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import create_app
from app.models.base import BaseModel
from app.models import (
    groups,
    tags,
    billing,
    webhooks,
    customers,
    users,
)  # 确保所有表被创建

# 测试数据库配置
TEST_DATABASE_SYNC_URL = "postgresql://postgres:postgres@localhost:5432/customer_platform_test"
TEST_DATABASE_ASYNC_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/customer_platform_test"


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
def sync_test_engine():
    """创建同步测试数据库引擎（用于 Analytics Service 等）"""
    engine = create_engine(
        TEST_DATABASE_SYNC_URL,
        echo=False,
        pool_pre_ping=True,
    )

    # 创建所有表
    with engine.begin() as conn:
        BaseModel.metadata.drop_all(conn)
        BaseModel.metadata.create_all(conn)

    yield engine

    # 清理
    try:
        with engine.begin() as conn:
            BaseModel.metadata.drop_all(conn)
    except Exception:
        pass


@pytest.fixture(scope="function")
def db_session(sync_test_engine) -> Session:
    """创建数据库会话（同步）"""
    SessionLocal = sessionmaker(
        bind=sync_test_engine, class_=Session, expire_on_commit=False
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def app(sync_test_engine, mock_scheduler):
    """创建 Sanic 应用实例（使用同步数据库引擎，但提供异步 session 工厂以满足 scheduler 需求）"""
    import uuid

    unique_app_name = f"test_app_{uuid.uuid4().hex[:8]}"

    # 创建异步引擎用于 scheduler（虽然不会被真正使用）
    async_engine = create_async_engine(
        TEST_DATABASE_ASYNC_URL,
        echo=False,
        pool_pre_ping=True,
    )
    async_session_maker = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    app_instance = create_app(
        app_name=unique_app_name,
        database_engine=sync_test_engine,
    )
    
    # 手动设置 async_session_maker 以满足 scheduler 需求
    app_instance.ctx.async_session_maker = async_session_maker
    
    yield app_instance
    
    # 清理异步引擎
    import asyncio
    asyncio.get_event_loop().run_until_complete(async_engine.dispose())


@pytest.fixture(scope="function")
async def mock_cache():
    """Mock 缓存服务，避免依赖 Redis"""
    from unittest.mock import AsyncMock, MagicMock
    from app.cache import base, permissions

    # Mock 缓存服务
    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock(return_value=True)
    mock_cache.delete = AsyncMock(return_value=True)
    mock_cache.invalidate_pattern = AsyncMock(return_value=True)
    mock_cache.invalidate_analytics_cache = AsyncMock(return_value=True)

    # Mock 权限缓存
    mock_perm_cache = MagicMock()
    mock_perm_cache.get_permissions = AsyncMock(
        return_value={"users:manage", "customers:read", "customers:manage"}
    )
    mock_perm_cache.set_permissions = AsyncMock(return_value=True)
    mock_perm_cache.invalidate = AsyncMock(return_value=True)

    # 替换全局实例
    original_cache = base.cache_service
    original_perm_cache = permissions.permission_cache

    base.cache_service = mock_cache
    permissions.permission_cache = mock_perm_cache

    yield mock_cache

    # 恢复原始实例
    base.cache_service = original_cache
    permissions.permission_cache = original_perm_cache


@pytest.fixture(scope="function")
async def test_client(app, mock_cache):
    """
    创建 Sanic ASGI 测试客户端
    """
    yield app.asgi_client
