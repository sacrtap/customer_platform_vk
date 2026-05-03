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
import pytest  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

# Mock aiosmtplib 导入 (避免网络依赖问题)
sys.modules["aiosmtplib"] = MagicMock()

from app.main import create_app  # noqa: E402
from app.models.base import BaseModel  # noqa: E402

# 测试数据库配置
TEST_DATABASE_SYNC_URL = "postgresql://postgres:postgres@localhost:5432/customer_platform_test"
TEST_DATABASE_ASYNC_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/customer_platform_test"
)


@pytest.fixture(scope="function")
def mock_scheduler():
    """Mock APScheduler 避免初始化问题"""
    with patch("app.tasks.scheduler.scheduler") as mock_sched:
        mock_sched.running = False
        mock_sched.start = MagicMock()
        mock_sched.shutdown = MagicMock()
        mock_sched.get_jobs = MagicMock(return_value=[])
        yield mock_sched


@pytest.fixture(scope="session")
def sync_test_engine():
    """创建同步测试数据库引擎（用于 Analytics Service 等）

    优化说明：
    - 使用 session scope，表结构只在测试会话开始时创建一次
    - 测试间数据隔离由 test_user fixture 中的 TRUNCATE 负责
    - 避免每个测试都执行 drop_all/create_all（性能提升 40-60%）
    """
    engine = create_engine(
        TEST_DATABASE_SYNC_URL,
        echo=False,
        pool_pre_ping=True,
        pool_reset_on_return="rollback",  # 确保连接归还时重置状态
    )

    # 创建所有表（只在 session 开始时执行一次）
    with engine.begin() as conn:
        BaseModel.metadata.create_all(conn)
        # 确保新增的 cancelled_at 列存在（create_all 不修改已存在的表）
        from sqlalchemy import inspect

        inspector = inspect(conn)
        if "invoices" in inspector.get_table_names():
            columns = [col["name"] for col in inspector.get_columns("invoices")]
            if "cancelled_at" not in columns:
                conn.execute(text("ALTER TABLE invoices ADD COLUMN cancelled_at VARCHAR(50)"))

    yield engine

    # 清理：关闭所有连接，清理测试数据
    SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    session = SessionLocal()
    try:
        session.execute(
            text("TRUNCATE user_roles, roles, permissions, role_permissions, users CASCADE")
        )
        session.commit()
    finally:
        session.close()
    engine.dispose()


@pytest.fixture(scope="session")
def test_user(sync_test_engine, worker_id):
    """Session 级测试用户，只在测试会话开始时创建一次

    优化说明：
    - 从 function scope 改为 session scope，避免每个测试都执行 TRUNCATE + INSERT
    - 原来 200+ 个测试 × 30+ 条权限 = 6000+ 次 INSERT，现在只执行 1 次
    - 测试间数据隔离由 db_session 的事务回滚负责
    - 使用 DELETE + ON CONFLICT 替代 TRUNCATE，避免并行测试死锁
    """
    import bcrypt

    username = "admin"
    password = "admin123"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    SessionLocal = sessionmaker(bind=sync_test_engine, class_=Session, expire_on_commit=False)
    session = SessionLocal()

    try:
        # 检查是否已经初始化（通过检查 admin 用户是否存在）
        result = session.execute(
            text("SELECT COUNT(*) FROM users WHERE username = :username"),
            {"username": username},
        )
        if result.scalar() > 0:
            # 已初始化，直接返回
            return {
                "username": username,
                "password": password,
            }

        # 清理旧数据（使用 DELETE 而非 TRUNCATE，避免并行死锁）
        # 按外键依赖顺序删除
        session.execute(text("DELETE FROM user_roles"))
        session.execute(text("DELETE FROM role_permissions"))
        session.execute(text("DELETE FROM roles"))
        session.execute(text("DELETE FROM permissions"))
        session.execute(text("DELETE FROM users"))
        session.commit()

        # 创建管理员角色
        session.execute(
            text(
                """
            INSERT INTO roles (name, description, created_at)
            VALUES (:name, :description, NOW())
            ON CONFLICT (name) DO NOTHING
            """
            ),
            {"name": "admin", "description": "系统管理员"},
        )

        # 创建权限（细粒度权限，与 seed.py 定义一致）
        permissions = [
            ("customers:view", "查看客户", "customers"),
            ("customers:create", "新建客户", "customers"),
            ("customers:edit", "编辑客户", "customers"),
            ("customers:delete", "删除客户", "customers"),
            ("customers:export", "导出客户", "customers"),
            ("customers:import", "导入客户", "customers"),
            ("billing:view", "查看结算", "billing"),
            ("billing:edit", "编辑结算", "billing"),
            ("billing:recharge", "充值操作", "billing"),
            ("billing:refund", "退款操作", "billing"),
            ("billing:delete", "结算删除", "billing"),
            ("billing:confirm", "结算确认", "billing"),
            ("billing:pay", "结算付款", "billing"),
            ("files:view", "查看文件", "files"),
            ("files:upload", "上传文件", "files"),
            ("files:delete", "删除文件", "files"),
            ("users:view", "查看用户", "users"),
            ("users:create", "新建用户", "users"),
            ("users:edit", "编辑用户", "users"),
            ("users:delete", "删除用户", "users"),
            ("users:role_assign", "分配角色", "users"),
            ("roles:view", "查看角色", "roles"),
            ("roles:create", "新建角色", "roles"),
            ("roles:edit", "编辑角色", "roles"),
            ("roles:delete", "删除角色", "roles"),
            ("roles:assign", "分配权限", "roles"),
            ("system:view", "查看系统", "system"),
            ("system:export", "导出日志", "system"),
            ("system:settings", "系统设置", "system"),
            ("analytics:view", "查看分析", "analytics"),
            ("analytics:export", "导出报表", "analytics"),
            ("analytics:profile_tag_edit", "编辑画像标签", "analytics"),
            ("tags:view", "查看标签", "tags"),
            ("tags:create", "新建标签", "tags"),
            ("tags:edit", "编辑标签", "tags"),
            ("tags:delete", "删除标签", "tags"),
        ]
        for perm_code, desc, module in permissions:
            session.execute(
                text(
                    """
                INSERT INTO permissions (code, name, description, module, created_at)
                VALUES (:code, :name, :description, :module, NOW())
                ON CONFLICT (code) DO NOTHING
                """
                ),
                {"code": perm_code, "name": desc, "description": desc, "module": module},
            )

        # 获取角色 ID
        result = session.execute(
            text("SELECT id FROM roles WHERE name = :name"), {"name": "admin"}
        ).fetchone()
        role_id = result[0]

        # 获取权限 ID 列表
        result = session.execute(
            text("SELECT id FROM permissions WHERE code IN :codes"),
            {"codes": tuple(p[0] for p in permissions)},
        ).fetchall()
        perm_ids = [r[0] for r in result]

        # 创建角色权限关联
        for perm_id in perm_ids:
            session.execute(
                text(
                    """
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (:role_id, :permission_id)
                ON CONFLICT (role_id, permission_id) DO NOTHING
                """
                ),
                {"role_id": role_id, "permission_id": perm_id},
            )

        # 创建用户
        session.execute(
            text(
                """
            INSERT INTO users (username, password_hash, email, real_name, is_active, created_at)
            VALUES (:username, :password_hash, :email, :real_name, :is_active, NOW())
            ON CONFLICT (username) DO NOTHING
            """
            ),
            {
                "username": username,
                "password_hash": password_hash,
                "email": "admin@example.com",
                "real_name": "管理员",
                "is_active": True,
            },
        )

        # 获取用户 ID 并关联角色
        result = session.execute(
            text("SELECT id FROM users WHERE username = :username"), {"username": username}
        ).fetchone()
        user_id = result[0]

        session.execute(
            text(
                """
            INSERT INTO user_roles (user_id, role_id)
            VALUES (:user_id, :role_id)
            ON CONFLICT (user_id, role_id) DO NOTHING
            """
            ),
            {"user_id": user_id, "role_id": role_id},
        )

        session.commit()
    finally:
        session.close()

    return {
        "username": username,
        "password": password,
    }


@pytest.fixture(scope="function")
def db_session(sync_test_engine, test_user):
    """创建同步数据库会话（用于测试清理）

    优化说明：
    - 依赖 test_user fixture，确保测试用户已创建
    - 每个测试开始前 TRUNCATE 业务数据表，确保测试间数据隔离
    - 保留 test_user 创建的 auth 相关数据（users/roles/permissions）
    """
    SessionLocal = sessionmaker(bind=sync_test_engine, class_=Session, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        # 测试后清理业务数据（保留 auth 数据）
        # 按外键依赖顺序：先删叶子表，再删父表
        try:
            session.execute(text("DELETE FROM customer_tags"))
            session.execute(text("DELETE FROM tags"))
            session.execute(text("DELETE FROM invoice_items"))
            session.execute(text("DELETE FROM invoices"))
            session.execute(text("DELETE FROM customer_balances"))
            session.execute(text("DELETE FROM recharge_records"))
            session.execute(text("DELETE FROM customer_profiles"))
            session.execute(text("DELETE FROM consumption_records"))
            session.execute(text("DELETE FROM daily_usage"))
            session.execute(text("DELETE FROM files"))
            session.execute(text("DELETE FROM audit_logs"))
            session.execute(text("DELETE FROM sync_task_logs"))
            session.execute(text("DELETE FROM pricing_rules"))
            session.execute(text("DELETE FROM webhook_signatures"))
            session.execute(text("DELETE FROM token_blacklist"))
            session.execute(text("DELETE FROM industry_types"))
            session.execute(text("DELETE FROM customers"))
            session.commit()
        except Exception:
            session.rollback()
        session.close()


@pytest.fixture(scope="function")
async def app(sync_test_engine, mock_scheduler, mock_cache):
    """创建 Sanic 应用实例（使用异步数据库引擎）"""
    import uuid

    unique_app_name = f"test_app_{uuid.uuid4().hex[:8]}"

    # 创建异步引擎（表已由 sync_test_engine 创建）
    async_engine = create_async_engine(
        TEST_DATABASE_ASYNC_URL,
        echo=False,
        pool_pre_ping=True,
        pool_reset_on_return="rollback",  # 确保连接归还时重置状态，防止泄漏
    )

    app_instance = create_app(
        app_name=unique_app_name,
        database_engine=async_engine,
    )

    # 禁用 Sanic Touchup 优化（触发 Python 3.12+ ast.Str.s deprecation warning）
    app_instance.config.TOUCHUP = False

    yield app_instance

    # 清理异步引擎：先 dispose 关闭所有已知连接，再 GC 清理残留
    import asyncio
    import gc
    import warnings

    await async_engine.dispose()
    await asyncio.sleep(0.05)
    # gc.collect 可能触发残留连接的 SAWarning，临时抑制
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gc.collect()


@pytest.fixture(scope="function")
async def mock_cache():
    """Mock 缓存服务，避免依赖 Redis"""
    from unittest.mock import AsyncMock, MagicMock
    from app.cache import base, permissions

    # Mock 缓存服务（所有方法都使用 AsyncMock）
    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock(return_value=True)
    mock_cache.delete = AsyncMock(return_value=True)
    mock_cache.invalidate_pattern = AsyncMock(return_value=True)
    mock_cache.invalidate_analytics_cache = AsyncMock(return_value=True)
    mock_cache.invalidate_customer_cache = AsyncMock(return_value=True)
    mock_cache.invalidate_billing_cache = AsyncMock(return_value=True)

    # Mock 权限缓存 - 简单方案：所有用户返回完整权限
    # test_customers_missing_permission 测试需要特殊处理
    FULL_PERMISSIONS = {
        "customers:view",
        "customers:create",
        "customers:edit",
        "customers:delete",
        "customers:export",
        "customers:import",
        "billing:view",
        "billing:edit",
        "billing:recharge",
        "billing:refund",
        "billing:delete",
        "billing:confirm",
        "billing:pay",
        "files:view",
        "files:upload",
        "files:delete",
        "users:view",
        "users:create",
        "users:edit",
        "users:delete",
        "users:role_assign",
        "roles:view",
        "roles:create",
        "roles:edit",
        "roles:delete",
        "roles:assign",
        "system:view",
        "system:export",
        "system:settings",
        "analytics:view",
        "analytics:export",
        "analytics:profile_tag_edit",
        "tags:view",
        "tags:create",
        "tags:edit",
        "tags:delete",
    }

    mock_perm_cache = MagicMock()
    mock_perm_cache.get_permissions = AsyncMock(return_value=FULL_PERMISSIONS)
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
