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
    """创建测试用户（异步），并分配超级管理员角色"""
    username = "test_user"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # 清理旧数据并创建新用户
    await db_session.execute(
        text(
            "DELETE FROM customer_groups WHERE created_by = (SELECT id FROM users WHERE username = :username)"
        ),
        {"username": username},
    )
    await db_session.execute(
        text(
            "DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE username = :username)"
        ),
        {"username": username},
    )
    await db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    await db_session.commit()

    # 确保超级管理员角色存在
    await db_session.execute(
        text("""
        INSERT INTO roles (name, description, is_system, created_at)
        VALUES ('超级管理员', '拥有系统所有权限', true, NOW())
        ON CONFLICT (name) DO NOTHING
        """)
    )

    # 确保需要的权限存在
    await db_session.execute(
        text("""
        INSERT INTO permissions (code, name, description, module, created_at)
        VALUES ('users:manage', '平台账号管理', '管理平台用户账号的增删改查', 'users', NOW())
        ON CONFLICT (code) DO NOTHING
        """)
    )
    await db_session.execute(
        text("""
        INSERT INTO permissions (code, name, description, module, created_at)
        VALUES ('customers:read', '客户管理读取', '读取客户信息的权限', 'customers', NOW())
        ON CONFLICT (code) DO NOTHING
        """)
    )
    await db_session.execute(
        text("""
        INSERT INTO permissions (code, name, description, module, created_at)
        VALUES ('customers:manage', '客户管理', '管理客户信息的权限', 'customers', NOW())
        ON CONFLICT (code) DO NOTHING
        """)
    )

    # 获取角色 ID 和权限 ID
    result = await db_session.execute(
        text("SELECT id FROM roles WHERE name = '超级管理员'")
    )
    role_id = result.scalar_one()

    # 获取所有权限 ID
    result = await db_session.execute(
        text(
            "SELECT id FROM permissions WHERE code IN ('users:manage', 'customers:read', 'customers:manage')"
        )
    )
    perm_ids = result.scalars().all()

    # 将权限关联到角色
    for perm_id in perm_ids:
        await db_session.execute(
            text("""
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES (:role_id, :perm_id)
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """),
            {"role_id": role_id, "perm_id": perm_id},
        )

    await db_session.commit()

    # 创建测试用户
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

    # 获取用户 ID 并分配角色
    result = await db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username},
    )
    user_id = result.scalar_one()

    await db_session.execute(
        text("""
        INSERT INTO user_roles (user_id, role_id)
        VALUES (:user_id, :role_id)
        ON CONFLICT (user_id, role_id) DO NOTHING
        """),
        {"user_id": user_id, "role_id": role_id},
    )
    await db_session.commit()

    yield {"username": username, "password": password}

    # 清理
    await db_session.execute(
        text(
            "DELETE FROM customer_groups WHERE created_by = (SELECT id FROM users WHERE username = :username)"
        ),
        {"username": username},
    )
    await db_session.execute(
        text(
            "DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE username = :username)"
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
async def mock_cache():
    """Mock 缓存服务，避免依赖 Redis 和 distutils"""
    from unittest.mock import AsyncMock, MagicMock
    from app.cache import base, permissions

    # Mock 缓存服务
    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock(return_value=True)
    mock_cache.delete = AsyncMock(return_value=True)
    mock_cache.invalidate_pattern = AsyncMock(return_value=True)
    mock_cache.invalidate_customer_cache = AsyncMock(return_value=True)
    mock_cache.invalidate_tag_cache = AsyncMock(return_value=True)
    mock_cache.invalidate_analytics_cache = AsyncMock(return_value=True)
    mock_cache.invalidate_billing_cache = AsyncMock(return_value=True)

    # Mock 权限缓存 - 返回超级管理员的所有权限
    mock_perm_cache = MagicMock()
    mock_perm_cache.get_permissions = AsyncMock(
        return_value={
            "users:manage",
            "customers:read",
            "customers:manage",
        }
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
    创建 Sanic ASGI 测试客户端（异步方式）

    使用 Sanic 内置的 asgi_client，与 pytest-asyncio 完全兼容
    支持异步数据库操作和异步 API 调用

    ASGI 客户端不需要手动启动/关闭服务器，由 Sanic 内部管理
    """
    yield app.asgi_client
