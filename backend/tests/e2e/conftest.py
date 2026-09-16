"""
E2E 测试配置 — 提供数据库、Redis mock、认证等基础 fixture。

复用 integration conftest 的模式，但用 Sanic 自带 asgi_client 代替 httpx AsyncClient
（httpx ASGI transport 与 Sanic 22.12 的 Signal 系统不兼容）。
"""

# ============================================================
# 必须在导入 ANY 应用代码之前设置环境变量
# ============================================================
import os
import sys

from tests._test_data import PERMISSION_CODES, PERMISSION_ROWS

# JWT_SECRET 统一由 tests/conftest.py 设置（setdefault "test-secret-key"），此处不得强制覆盖：
# 与 integration/conftest.py 共存于同一全量会话时，各自设置不同密钥会让模块级 settings 单例
# 与实际签发/验证使用的密钥不一致，表现为登录成功后请求仍 401。
# WEBHOOK_SECRET 同样由 tests/conftest.py 的 setdefault 提供基线；
# 任一层需要不同值时应在本层测试内 monkeypatch，而非在 conftest 永久覆盖 settings 单例。

# 清除所有可能的 settings 缓存
modules_to_clear = [k for k in list(sys.modules.keys()) if k.startswith("app")]
for mod in modules_to_clear:
    del sys.modules[mod]

# 重置 lru_cache 确保 settings 单例使用新的环境变量
import app.config  # noqa: E402

app.config.get_settings.cache_clear()
app.config.settings = app.config.get_settings()

# 现在才导入应用代码
from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

# Mock aiosmtplib 导入 (避免网络依赖问题)
sys.modules["aiosmtplib"] = MagicMock()

# 清除可能已注册的 Sanic app 实例
from sanic import Sanic  # noqa: E402

Sanic._app_registry.clear()

from app.main import create_app  # noqa: E402
from app.models.base import BaseModel  # noqa: E402

# 测试数据库配置
_TEST_DB_USER = os.environ.get("POSTGRES_USER", "postgres")
_TEST_DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
_TEST_DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
_TEST_DB_NAME = os.environ.get("POSTGRES_DB", "customer_platform_test")

TEST_DATABASE_SYNC_URL = (
    f"postgresql://{_TEST_DB_USER}:{_TEST_DB_PASSWORD}@{_TEST_DB_HOST}:5432/{_TEST_DB_NAME}"
)
TEST_DATABASE_ASYNC_URL = (
    f"postgresql+asyncpg://{_TEST_DB_USER}:{_TEST_DB_PASSWORD}@{_TEST_DB_HOST}:5432/{_TEST_DB_NAME}"
)


@pytest.fixture(scope="session")
def sync_test_engine():
    """创建同步测试数据库引擎（用于建表和创建测试用户）"""
    engine = create_engine(TEST_DATABASE_SYNC_URL, echo=False)
    BaseModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def test_user(sync_test_engine):
    """Session 级测试用户"""
    import bcrypt

    username = "admin"
    password = "admin123"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    SessionLocal = sessionmaker(bind=sync_test_engine, class_=Session, expire_on_commit=False)
    session = SessionLocal()

    try:
        result = session.execute(
            text("SELECT COUNT(*) FROM users WHERE username = :username"),
            {"username": username},
        )
        count = result.scalar()

        if count > 0:
            return {"username": username, "password": password}

        session.execute(
            text("TRUNCATE user_roles, role_permissions, roles, permissions, users CASCADE")
        )
        session.commit()

        session.execute(
            text("""
            INSERT INTO roles (name, description, created_at)
            VALUES (:name, :description, NOW())
            ON CONFLICT (name) DO NOTHING
            """),
            {"name": "admin", "description": "系统管理员"},
        )

        permissions = PERMISSION_ROWS
        for perm_code, desc, module in permissions:
            session.execute(
                text("""
                INSERT INTO permissions (code, name, description, module, created_at)
                VALUES (:code, :name, :description, :module, NOW())
                ON CONFLICT (code) DO NOTHING
                """),
                {"code": perm_code, "name": desc, "description": desc, "module": module},
            )

        result = session.execute(
            text("SELECT id FROM roles WHERE name = :name"), {"name": "admin"}
        ).fetchone()
        role_id = result[0]

        result = session.execute(
            text("SELECT id FROM permissions WHERE code IN :codes"),
            {"codes": tuple(p[0] for p in permissions)},
        ).fetchall()
        perm_ids = [r[0] for r in result]

        for perm_id in perm_ids:
            session.execute(
                text("""
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (:role_id, :permission_id)
                ON CONFLICT (role_id, permission_id) DO NOTHING
                """),
                {"role_id": role_id, "permission_id": perm_id},
            )

        session.execute(
            text("""
            INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
            VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
            ON CONFLICT (username) DO NOTHING
            """),
            {
                "username": username,
                "password_hash": password_hash,
                "email": "admin@example.com",
                "real_name": "管理员",
                "is_active": True,
            },
        )

        result = session.execute(
            text("SELECT id FROM users WHERE username = :username"), {"username": username}
        ).fetchone()
        user_id = result[0]

        session.execute(
            text("""
            INSERT INTO user_roles (user_id, role_id)
            VALUES (:user_id, :role_id)
            ON CONFLICT (user_id, role_id) DO NOTHING
            """),
            {"user_id": user_id, "role_id": role_id},
        )

        session.commit()
    finally:
        session.close()

    return {"username": username, "password": password}


@pytest.fixture(scope="function")
def db_session(sync_test_engine, test_user):
    """创建同步数据库会话（用于测试数据清理）"""
    SessionLocal = sessionmaker(bind=sync_test_engine, class_=Session, expire_on_commit=False)
    session = SessionLocal()
    try:
        # 清理同步任务相关数据，避免跨测试干扰
        session.execute(text("DELETE FROM sync_task_logs"))
        session.execute(text("DELETE FROM sync_tasks"))
        session.commit()
        yield session
    finally:
        session.execute(text("DELETE FROM sync_task_logs"))
        session.execute(text("DELETE FROM sync_tasks"))
        session.commit()
        session.close()


@pytest.fixture(scope="function")
async def mock_cache():
    """Mock 缓存服务，避免依赖 Redis 全局实例"""
    from unittest.mock import AsyncMock

    from app.cache import base, permissions

    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock(return_value=True)
    mock_cache.delete = AsyncMock(return_value=True)
    mock_cache.invalidate_pattern = AsyncMock(return_value=True)
    mock_cache.invalidate_analytics_cache = AsyncMock(return_value=True)
    mock_cache.invalidate_customer_cache = AsyncMock(return_value=True)
    mock_cache.invalidate_billing_cache = AsyncMock(return_value=True)
    mock_cache.check_redis_available = AsyncMock(return_value=True)

    # 提供一个 mock redis 客户端供 SyncTaskService 使用
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock()
    mock_redis.hset = AsyncMock()
    mock_redis.expire = AsyncMock()
    mock_redis.hgetall = AsyncMock(return_value={})
    mock_redis.exists = AsyncMock(return_value=False)
    mock_cache._get_redis = AsyncMock(return_value=mock_redis)

    FULL_PERMISSIONS = PERMISSION_CODES

    mock_perm_cache = MagicMock()
    mock_perm_cache.get_permissions = AsyncMock(return_value=FULL_PERMISSIONS)
    mock_perm_cache.set_permissions = AsyncMock(return_value=True)
    mock_perm_cache.invalidate = AsyncMock(return_value=True)

    original_cache = base.cache_service
    original_perm_cache = permissions.permission_cache

    base.cache_service = mock_cache
    permissions.permission_cache = mock_perm_cache

    # 模块级 `from app.cache.base import cache_service` 在导入时即完成名字绑定，
    # 仅替换 base.cache_service 不会更新这些引用；此处显式覆盖端点实际调用的引用，
    # 否则 sync-tasks 端点会绕过 mock 直连真实 Redis（mock 意图落空）。
    from app.routes import sync_tasks as sync_tasks_routes

    original_routes_cache = sync_tasks_routes.cache_service
    sync_tasks_routes.cache_service = mock_cache

    yield mock_cache

    sync_tasks_routes.cache_service = original_routes_cache
    base.cache_service = original_cache
    permissions.permission_cache = original_perm_cache


@pytest.fixture(scope="function")
def mock_scheduler():
    """Mock APScheduler 避免初始化问题"""
    from unittest.mock import MagicMock, patch

    with patch("app.tasks.scheduler.scheduler") as mock_sched:
        mock_sched.running = False
        mock_sched.start = MagicMock()
        mock_sched.shutdown = MagicMock()
        mock_sched.get_jobs = MagicMock(return_value=[])
        yield mock_sched


@pytest.fixture(scope="function")
async def app(sync_test_engine, mock_cache, mock_scheduler):
    """创建 Sanic 应用实例（使用异步数据库引擎）"""
    import uuid

    unique_app_name = f"e2e_test_app_{uuid.uuid4().hex[:8]}"

    async_engine = create_async_engine(
        TEST_DATABASE_ASYNC_URL,
        echo=False,
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
    )

    app_instance = create_app(
        app_name=unique_app_name,
        database_engine=async_engine,
    )
    app_instance.config.TOUCHUP = False

    yield app_instance

    await async_engine.dispose()
    Sanic._app_registry.pop(unique_app_name, None)


@pytest.fixture(scope="function")
async def test_client(app, mock_cache):
    """创建 Sanic ASGI 测试客户端"""
    yield app.asgi_client


@pytest.fixture(scope="function")
async def auth_headers(test_client, test_user):
    """获取认证 Token 并返回请求头"""
    _request, response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    assert response.status == 200, f"登录失败: {response.text}"
    token = response.json["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
