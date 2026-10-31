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
import logging
import os
import sys
import uuid

from tests._test_data import PERMISSION_CODES, PERMISSION_ROWS, sync_test_schema

logger = logging.getLogger(__name__)

# JWT_SECRET 统一由 tests/conftest.py 设置（setdefault "test-secret-key"），此处不得强制覆盖：
# 全量 pytest 会话中 integration/ 与 e2e/ 的 conftest 都会被加载，而 app.config.settings
# 是模块级单例（lru_cache）；各自设置不同密钥会导致「签发用 A、验证用 B」→ 401。
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
from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

# Mock aiosmtplib 导入 (避免网络依赖问题)
sys.modules["aiosmtplib"] = MagicMock()

# 清除可能已注册的 Sanic app 实例（单元测试可能已导入 app.main 触发模块级 app = create_app()），
# 避免下方 import app.main 时再次执行 create_app() 报 "already in use" 错误
from sanic import Sanic  # noqa: E402

Sanic._app_registry.clear()

from app.main import create_app  # noqa: E402
from app.models.base import BaseModel  # noqa: E402

# 测试数据库配置（从环境变量读取，CI环境使用不同的凭证）
_TEST_DB_USER = os.environ.get("POSTGRES_USER", "postgres")
_TEST_DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
_TEST_DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
_BASE_DB_NAME = os.environ.get("POSTGRES_DB", "customer_platform_test")

# 并行化支持：pytest-xdist 会设置 PYTEST_XDIST_WORKER（如 "gw0", "gw1"）
# 每个 worker 使用独立的数据库，避免 TRUNCATE 死锁
_WORKER_ID = os.environ.get("PYTEST_XDIST_WORKER", "")
if _WORKER_ID:
    _TEST_DB_NAME = f"{_BASE_DB_NAME}_{_WORKER_ID}"
else:
    _TEST_DB_NAME = _BASE_DB_NAME

TEST_DATABASE_SYNC_URL = (
    f"postgresql://{_TEST_DB_USER}:{_TEST_DB_PASSWORD}@{_TEST_DB_HOST}:5432/{_TEST_DB_NAME}"
)
TEST_DATABASE_ASYNC_URL = (
    f"postgresql+asyncpg://{_TEST_DB_USER}:{_TEST_DB_PASSWORD}@{_TEST_DB_HOST}:5432/{_TEST_DB_NAME}"
)

# 测试引擎必须与生产引擎（app/main.py create_async_engine）锁定同一 PG 会话时区：
# `TimestampMixin.created_at` 是 `timestamp without time zone`，由
# `server_default=func.now()` 在 **会话时区** 写墙钟。CI 的 postgres:18 容器
# 默认 UTC，runner 亦可能为 UTC，不锁定时测试库里 created_at 是 UTC 墙钟，
# 而读出口 `naive_cst_datetime_str()` 假设它是 CST 墙钟 → 测试通过但生产偏差
# （staging 显示少 8 小时，2026-10-26 事故）。timestamptz 列存绝对 UTC 时刻，
# 不受此设置影响。
# 注意两种驱动的传法不同：asyncpg 用 `server_settings`，psycopg2 不认该参数
# （会报 invalid connection option），须走 libpq 的 `options`。
TEST_ENGINE_CONNECT_ARGS = {
    "server_settings": {"TimeZone": "Asia/Shanghai"},
}
TEST_SYNC_ENGINE_CONNECT_ARGS = {
    "options": "-c timezone=Asia/Shanghai",
}


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
        pool_reset_on_return="rollback",  # 确保连接归还时重置状态，防止泄漏
        connect_args=TEST_SYNC_ENGINE_CONNECT_ARGS,  # 锁定会话时区为 CST，与异步引擎一致
    )

    # 创建所有表（只在 session 开始时执行一次）
    with engine.begin() as conn:
        BaseModel.metadata.create_all(conn)
        # 验证表是否正确创建
        from sqlalchemy import inspect

        inspector = inspect(conn)
        tables = inspector.get_table_names()
        print(f"✅ 已创建 {len(tables)} 个表: {tables[:5]}...")

    # create_all 不修改已存在的表：按 ORM metadata 自动补齐缺失列。
    # 原先此处手写 `if "xxx" not in columns: ALTER TABLE ...` 清单，模型加字段时
    # 忘记同步 → 测试库落后于模型 → 集成测试报 column does not exist（2026-10-13 事故）。
    # 现改为以 metadata 为唯一真相自动同步，模型加列后无需再维护此清单。
    added = sync_test_schema(engine)
    if added:
        print(f"🔧 已按模型自动补齐测试库缺失列: {added}")

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
def test_user(sync_test_engine):
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
        # 检查是否已初始化：admin 用户存在、密码匹配且未禁用才跳过重建。
        # 仅检查存在性会在「admin 残留但密码/完整性不符」的脏状态下返回硬编码
        # password，导致后续 auth_token 登录 401（全量偶发失败根因）。
        result = session.execute(
            text("SELECT password_hash, is_active FROM users WHERE username = :username"),
            {"username": username},
        )
        row = result.fetchone()

        if row is not None and bcrypt.checkpw(password.encode(), row[0].encode()) and row[1]:
            # 已完整初始化，直接返回
            return {
                "username": username,
                "password": password,
            }

        # 清理旧数据（TRUNCATE CASCADE 级联清除所有引用 users/roles/permissions 的表）
        # 解决 audit_logs 等表的外键约束阻止 DELETE FROM users 的问题
        session.execute(
            text("TRUNCATE user_roles, role_permissions, roles, permissions, users CASCADE")
        )
        session.commit()

        # 创建管理员角色（ON CONFLICT 防止并行 worker 竞态）
        session.execute(
            text("""
            INSERT INTO roles (name, description, created_at)
            VALUES (:name, :description, NOW())
            ON CONFLICT (name) DO NOTHING
            """),
            {"name": "admin", "description": "系统管理员"},
        )

        # 创建权限（细粒度权限，与 seed.py 定义一致）
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
                text("""
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (:role_id, :permission_id)
                ON CONFLICT (role_id, permission_id) DO NOTHING
                """),
                {"role_id": role_id, "permission_id": perm_id},
            )

        # 创建用户（ON CONFLICT 防止并行 worker 竞态）
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

        # 获取用户 ID 并关联角色
        result = session.execute(
            text("SELECT id FROM users WHERE username = :username"), {"username": username}
        ).fetchone()
        if result is None:
            logger.error("test_user: 用户创建后查询不到（username=%s）", username)
            raise Exception("用户创建后查询不到")
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
        # 恢复系统字典预置数据：合作状态（与生产迁移 g6b7c8d9e0f1 预置一致）。
        # 客户导入预检查实时查询 cooperation_statuses 表（表驱动校验），
        # 测试库无预置会把 active/noused 等合法值误报「无效的合作状态」。
        session.execute(
            text("""
            INSERT INTO cooperation_statuses (name, value, sort_order, created_at, updated_at)
            VALUES
                ('合作中', 'active', 1, NOW(), NOW()),
                ('暂停', 'suspended', 2, NOW(), NOW()),
                ('终止', 'terminated', 3, NOW(), NOW()),
                ('近一年未使用', 'noused', 4, NOW(), NOW())
            ON CONFLICT (value) DO NOTHING
            """)
        )
        session.commit()
        yield session
    finally:
        # 测试后清理业务数据（保留 auth 数据）。
        # TRUNCATE ... CASCADE 一次性截断所有业务表，比逐表 DELETE 快得多
        # （在 CI 的 Docker PostgreSQL 上，22 次 DELETE 的磁盘 I/O 是主要耗时来源）。
        # 注意：此清理方式不支持 pytest-xdist 并行执行（会截断其他 worker 的数据），
        # workflow 中使用 -n 1 单 worker 执行以避免竞态。
        try:
            session.execute(
                text(
                    "TRUNCATE profile_tags, customer_tags, tags, invoice_items, invoices, "
                    "customer_balances, recharge_records, customer_profiles, consumption_records, "
                    "daily_consumptions, daily_orders, files, audit_logs, sync_task_logs, "
                    "sync_tasks, pricing_rules, package_plans, webhook_signatures, "
                    "token_blacklist, industry_types, cooperation_statuses, balance_whitelists, "
                    "customers CASCADE"
                )
            )
            session.commit()
        except Exception:
            session.rollback()
        session.close()


@pytest.fixture
def import_customer(db_session):
    """创建导入测试客户，返回 {id, company_id}

    余额导入/白名单导入等需要引用真实客户；raw SQL 造数据需显式补
    customer_balances 档案，否则该客户在余额列表/导出中不可见。
    """
    cid = 950000 + abs(hash(uuid.uuid4().hex[:8])) % 40000
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
    db_session.execute(
        text(
            """
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   created_at, updated_at)
            VALUES (:id, :cid, :name, 'enterprise', 'monthly', 'prepaid', NOW(), NOW())
            """
        ),
        {"id": cid, "cid": cid, "name": f"导入测试客户_{cid}"},
    )
    db_session.execute(
        text(
            """
            INSERT INTO customer_balances (customer_id, total_amount, real_amount,
                                           bonus_amount, used_total, used_real, used_bonus,
                                           created_at, updated_at)
            VALUES (:cid, 10000, 8000, 2000, 0, 0, 0, NOW(), NOW())
            """
        ),
        {"cid": cid},
    )
    db_session.commit()

    try:
        yield {"id": cid, "company_id": cid}
    finally:
        for stmt in (
            "DELETE FROM pricing_rules WHERE customer_id = :cid",
            "DELETE FROM invoices WHERE customer_id = :cid",
            "DELETE FROM customer_balances WHERE customer_id = :cid",
            # 余额导入会创建 recharge_records（FK 指向 customers），须先于 customers 删除
            "DELETE FROM recharge_records WHERE customer_id = :cid",
            "DELETE FROM customers WHERE id = :cid",
        ):
            db_session.execute(text(stmt), {"cid": cid})
        db_session.commit()


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
        connect_args=TEST_ENGINE_CONNECT_ARGS,  # 锁定会话时区为 CST，与生产一致
    )

    app_instance = create_app(
        app_name=unique_app_name,
        database_engine=async_engine,
    )

    # 禁用 Sanic Touchup 优化（触发 Python 3.12+ ast.Str.s deprecation warning）
    app_instance.config.TOUCHUP = False

    yield app_instance

    # 清理异步引擎：dispose 关闭连接池中所有连接
    # 注：移除 gc.collect() 和 asyncio.sleep —— 它们在 CI 上每个测试额外耗时 3-5s
    # dispose() 已足够关闭数据库连接，残留的 Python 对象由引用计数自动回收
    await async_engine.dispose()

    # 从 Sanic 注册表中移除已销毁的 app 实例，防止内存累积
    Sanic._app_registry.pop(unique_app_name, None)


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
    mock_cache.invalidate_tag_cache = AsyncMock(return_value=True)
    mock_cache.invalidate_billing_cache = AsyncMock(return_value=True)
    # Mock 权限缓存 - 简单方案：所有用户返回完整权限
    # test_customers_missing_permission 测试需要特殊处理
    FULL_PERMISSIONS = PERMISSION_CODES

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


@pytest.fixture(scope="session")
def auth_token(test_user, sync_test_engine):
    """session 级认证 token：直接签发 JWT，避免每测试重复登录（bcrypt 开销）。

    仅适用于「登录 admin 获取 token」的测试（约 9 个文件）；analytics 等
    需要自签特殊 token 的文件保留自己的 auth_token。
    """
    from app.services.auth import AuthService

    SessionLocal = sessionmaker(bind=sync_test_engine, class_=Session, expire_on_commit=False)
    session = SessionLocal()
    try:
        result = session.execute(
            text(
                """
                SELECT u.id, r.name
                FROM users u
                JOIN user_roles ur ON ur.user_id = u.id
                JOIN roles r ON r.id = ur.role_id
                WHERE u.username = :username
                """
            ),
            {"username": test_user["username"]},
        )
        rows = result.fetchall()
        if not rows:
            raise RuntimeError(f"auth_token: 用户 {test_user['username']} 无角色关联")
        user_id = rows[0][0]
        roles = [row[1] for row in rows]
        return AuthService.create_access_token(
            user_id=user_id, username=test_user["username"], roles=roles
        )
    finally:
        session.close()
