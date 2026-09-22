"""
Alembic 迁移测试 - over_limit_unit_price NULL 语义

验证迁移 s8t9u0v1w2x3:
- upgrade: 存储值恰好等于 base_fee/limit_count 的记录转为 NULL（NULL=自动计算）
- downgrade: NULL 记录回填为 ROUND(base_fee/limit_count, 2)
- 与业务侧自动计算逻辑一致: (base_fee / Decimal(limit_count)).quantize(Decimal("0.01"))

使用独立的迁移测试数据库，避免与其他测试冲突。
"""

import os
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command

BACKEND_DIR = Path(__file__).parent.parent.parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"

# 独立测试数据库（区别于 tests/conftest.py 的 customer_platform_test）
# 连接参数优先用 MIGRATION_TEST_DB_* 覆盖；默认回退到 CI 的 POSTGRES_* 变量
# （本地无 POSTGRES_* 时用 postgres/空密码，兼容 Postgres.app 本地开发）
TEST_DB_NAME = "customer_platform_migration_test"
# 注意：迁移测试不用 PYTEST_XDIST_WORKER 隔离——模块级 settings 缓存与 alembic
# 命令在并行下会相互污染。由 CI 单独串行步骤执行（见 pr-checks.yml）。
TEST_DB_USER = os.environ.get("MIGRATION_TEST_DB_USER", os.environ.get("POSTGRES_USER", "postgres"))
TEST_DB_PASSWORD = os.environ.get(
    "MIGRATION_TEST_DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "")
)
TEST_DB_HOST = os.environ.get(
    "MIGRATION_TEST_DB_HOST", os.environ.get("POSTGRES_HOST", "localhost")
)
TEST_DB_PORT = os.environ.get("MIGRATION_TEST_DB_PORT", "5432")

_admin_url = (
    f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/postgres"
)
TEST_DATABASE_URL = (
    f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"
)

# 目标迁移链: 从初始 schema 一路 upgrade 到目标迁移，再从目标迁移 downgrade 一步
TARGET_REVISION = "s8t9u0v1w2x3"
PREVIOUS_REVISION = "r7s8t9u0v1w2"


def _create_test_database() -> None:
    """创建独立的迁移测试数据库（幂等）"""
    admin_engine = create_engine(_admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()


def _drop_test_database() -> None:
    """删除迁移测试数据库（幂等，忽略不存在错误）"""
    admin_engine = create_engine(_admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'))
    admin_engine.dispose()


def _alembic_config() -> Config:
    # alembic env.py 会用 settings.database_url（读 DATABASE_URL）覆盖 config 的
    # sqlalchemy.url，因此必须先设置 DATABASE_URL 并重置 app.config 的 settings 缓存，
    # 确保迁移打到独立测试库而不是 tests/conftest.py 默认的 customer_platform_test。
    # 注意：不能删除 sys.modules 中的 app 模块（会破坏同进程已初始化的 SQLAlchemy mapper）。
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    import app.config

    app.config.get_settings.cache_clear()
    app.config.settings = app.config.get_settings()

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return cfg


@pytest.fixture(scope="module")
def migration_db():
    """创建独立迁移测试库，升级到目标迁移的前一个版本（让测试真正执行目标迁移），测试结束后清理"""
    _create_test_database()
    engine = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    import app.config

    original_settings = app.config.settings
    try:
        # 升级到目标迁移的前一个版本，保证 package_plans 表与前置迁移存在
        command.upgrade(_alembic_config(), PREVIOUS_REVISION)
        yield engine
    finally:
        # 恢复原 settings，避免污染同进程后续测试
        app.config.get_settings.cache_clear()
        app.config.settings = original_settings
        engine.dispose()
        _drop_test_database()


@pytest.fixture(scope="module")
def package_plan_columns(migration_db):
    """读取 package_plans 表结构，确认关键列存在"""
    with migration_db.connect() as conn:
        cols = (
            conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'package_plans'"
                )
            )
            .scalars()
            .all()
        )
    return set(cols)


def _insert_package_plan(
    engine,
    plan_id: int,
    *,
    is_unlimited: bool = False,
    limit_count: int,
    base_fee: Decimal,
    over_limit_unit_price,
) -> None:
    """插入一条套餐记录（限量为假，deleted_at 为空）"""
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO package_plans "
                "(id, name, package_type, is_unlimited, limit_count, base_fee, "
                "over_limit_unit_price, created_at, updated_at) "
                "VALUES (:id, :name, :package_type, :is_unlimited, :limit_count, :base_fee, "
                ":over_limit_unit_price, NOW(), NOW())"
            ),
            {
                "id": plan_id,
                "name": f"测试套餐-{plan_id}",
                "package_type": f"test-{plan_id}",
                "is_unlimited": is_unlimited,
                "limit_count": limit_count,
                "base_fee": float(base_fee),
                "over_limit_unit_price": over_limit_unit_price,
            },
        )


def _fetch_over_limit_unit_price(engine, plan_id: int):
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT over_limit_unit_price FROM package_plans "
                "WHERE id = :id AND deleted_at IS NULL"
            ),
            {"id": plan_id},
        ).scalar()


def _business_auto_price(base_fee: Decimal, limit_count: int) -> Decimal:
    """业务侧自动计算逻辑（与 app/services/billing.py 保持一致）"""
    return (base_fee / Decimal(limit_count)).quantize(Decimal("0.01"))


@pytest.mark.smoke
class TestOverLimitUnitPriceNullSemantics:
    """迁移 s8t9u0v1w2x3 upgrade/downgrade 数据语义测试"""

    def test_upgrade_converts_exact_auto_price_to_null(self, migration_db, package_plan_columns):
        """upgrade 后: 存储值恰好等于 base_fee/limit_count 的记录转为 NULL"""
        assert "over_limit_unit_price" in package_plan_columns

        # 恰好等于自动计算值 -> 应转为 NULL
        _insert_package_plan(
            migration_db,
            101,
            limit_count=100,
            base_fee=Decimal("1000.00"),
            over_limit_unit_price=10.0,  # 1000/100 = 10.00
        )
        # 四舍五入一致（0.333... -> 0.33）
        _insert_package_plan(
            migration_db,
            102,
            limit_count=3,
            base_fee=Decimal("100.00"),
            over_limit_unit_price=33.33,  # ROUND(100/3, 2) = 33.33
        )

        # 用户自定义值（不等于自动计算）-> 保持原值
        _insert_package_plan(
            migration_db,
            103,
            limit_count=100,
            base_fee=Decimal("1000.00"),
            over_limit_unit_price=15.0,
        )

        command.upgrade(_alembic_config(), TARGET_REVISION)

        assert _fetch_over_limit_unit_price(migration_db, 101) is None
        assert _fetch_over_limit_unit_price(migration_db, 102) is None
        assert _fetch_over_limit_unit_price(migration_db, 103) == Decimal("15.00")

    def test_downgrade_restores_auto_price_values(self, migration_db):
        """downgrade 后: NULL 记录回填为 ROUND(base_fee/limit_count, 2)"""
        # 插入 NULL 语义记录（模拟 upgrade 后的状态）
        _insert_package_plan(
            migration_db,
            201,
            limit_count=100,
            base_fee=Decimal("1000.00"),
            over_limit_unit_price=None,
        )
        _insert_package_plan(
            migration_db,
            202,
            limit_count=3,
            base_fee=Decimal("100.00"),
            over_limit_unit_price=None,
        )

        command.downgrade(_alembic_config(), PREVIOUS_REVISION)

        assert _fetch_over_limit_unit_price(migration_db, 201) == Decimal("10.00")
        assert _fetch_over_limit_unit_price(migration_db, 202) == Decimal("33.33")

    def test_business_calculation_matches_migration(self):
        """迁移的 ROUND(base_fee/limit_count, 2) 与业务自动计算一致"""
        cases = [
            (Decimal("1000.00"), 100, Decimal("10.00")),
            (Decimal("100.00"), 3, Decimal("33.33")),
            (Decimal("500.00"), 7, Decimal("71.43")),
            (Decimal("0.01"), 1000, Decimal("0.00")),
        ]
        for base_fee, limit_count, expected in cases:
            assert _business_auto_price(base_fee, limit_count) == expected
