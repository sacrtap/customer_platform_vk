"""tests/_test_data.py::sync_test_schema 的守护测试。

背景（2026-10-13 事故）：测试库若手工维护「补列清单」，模型加字段而清单未同步时，
测试库会静默落后于模型——单测（MagicMock）与全新库集成测试全绿，但真实（增量迁移过的）
库查询报 `column xxx does not exist` → 500。

sync_test_schema 以 metadata 为唯一真相自动补齐缺失列，本测试锁定其两个关键性质：
1. 能补齐已存在表缺失的列（自愈）；
2. 幂等（无缺失时不产生任何 DDL）。

使用独立库名，避免与模块级 migration_db / 共享测试库冲突。
"""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).parent.parent.parent

_TEST_DB_USER = os.environ.get("POSTGRES_USER", "postgres")
_TEST_DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
_TEST_DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
_TEST_DB_PORT = os.environ.get("POSTGRES_PORT", "5432")

_SYNC_DB_NAME = "customer_platform_sync_test"

_admin_url = (
    f"postgresql://{_TEST_DB_USER}:{_TEST_DB_PASSWORD}@{_TEST_DB_HOST}:{_TEST_DB_PORT}/postgres"
)
_sync_url = f"postgresql://{_TEST_DB_USER}:{_TEST_DB_PASSWORD}@{_TEST_DB_HOST}:{_TEST_DB_PORT}/{_SYNC_DB_NAME}"


@pytest.fixture(scope="module")
def sync_engine():
    """独立库：create_all 建全新 schema 后 yield，结束时 DROP。"""
    from app.models.base import BaseModel

    admin_engine = create_engine(_admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{_SYNC_DB_NAME}"'))
        conn.execute(text(f'CREATE DATABASE "{_SYNC_DB_NAME}"'))
    admin_engine.dispose()

    engine = create_engine(_sync_url, isolation_level="AUTOCOMMIT")
    BaseModel.metadata.create_all(engine)
    yield engine

    engine.dispose()
    admin_engine = create_engine(_admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{_SYNC_DB_NAME}"'))
    admin_engine.dispose()


def _has_column(engine, table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(engine).get_columns(table)}


def test_sync_test_schema_heals_missing_columns(sync_engine):
    """已存在表缺失的列必须被自动补齐（自愈）。"""
    from tests._test_data import sync_test_schema

    # 伪造「测试库落后于模型」：删掉模型声明的列
    with sync_engine.begin() as conn:
        conn.execute(text("ALTER TABLE customers DROP COLUMN balance_warning_level"))
        conn.execute(text("ALTER TABLE customers DROP COLUMN balance_warning_updated_at"))
    assert not _has_column(sync_engine, "customers", "balance_warning_level")

    added = sync_test_schema(sync_engine)

    assert "customers.balance_warning_level" in added
    assert "customers.balance_warning_updated_at" in added
    assert _has_column(sync_engine, "customers", "balance_warning_level")
    assert _has_column(sync_engine, "customers", "balance_warning_updated_at")


def test_sync_test_schema_is_idempotent(sync_engine):
    """库已与模型一致时不得产生任何 DDL（幂等，无副作用）。"""
    from tests._test_data import sync_test_schema

    assert sync_test_schema(sync_engine) == []
    assert sync_test_schema(sync_engine) == []
