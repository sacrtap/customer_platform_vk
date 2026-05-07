"""审计辅助函数集成测试（需要数据库）"""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models.base import BaseModel
from app.models.users import User
from app.models.billing import AuditLog
from app.utils.audit_helpers import (
    create_audit_entry,
    build_batch_audit_summary,
)

# 使用 xdist_group 标记，确保数据库操作测试串行执行
pytestmark = pytest.mark.xdist_group("db_models")


@pytest.fixture(scope="function")
async def async_engine():
    """创建异步测试数据库引擎（使用与 integration conftest 一致的配置）"""
    import os
    from app.config import settings

    # 从环境变量覆盖数据库URL（CI环境需要）
    db_user = os.environ.get("POSTGRES_USER", "postgres")
    db_password = os.environ.get("POSTGRES_PASSWORD", "postgres")
    db_host = os.environ.get("POSTGRES_HOST", "localhost")
    db_name = os.environ.get("POSTGRES_DB", "customer_platform_test")
    
    test_db_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:5432/{db_name}"

    engine = create_async_engine(
        test_db_url,
        echo=False,
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture(scope="function")
async def async_session(async_engine):
    """创建异步数据库会话"""
    from sqlalchemy import text

    async_session_maker = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        # 测试前清理：使用 TRUNCATE CASCADE 清理所有相关数据
        await session.execute(text("TRUNCATE audit_logs, customers, users CASCADE"))
        await session.commit()

        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class TestCreateAuditEntry:
    """审计日志创建功能集成测试（需要数据库）"""

    @pytest.mark.asyncio
    async def test_create_standard_audit_entry(self, async_session):
        # 先创建用户
        user = User(
            username="test_user",
            password_hash="hashed_password",
            email="test@example.com",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        audit = await create_audit_entry(
            db_session=async_session,
            user_id=user.id,
            action="create",
            module="customers",
            record_id=123,
            record_type="customer",
            ip_address="127.0.0.1",
        )
        assert audit.user_id == user.id
        assert audit.action == "create"
        assert audit.module == "customers"
        assert audit.record_id == 123
        assert audit.operation_type == "standard"
        assert audit.extra_metadata is None

        # 验证数据已持久化
        await async_session.refresh(audit)
        assert audit.id is not None

    @pytest.mark.asyncio
    async def test_create_batch_audit_entry(self, async_session):
        # 先创建用户
        user = User(
            username="batch_user",
            password_hash="hashed_password",
            email="batch@example.com",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        metadata = build_batch_audit_summary(
            operation="customer_import",
            total_count=10,
            success_count=8,
        )
        audit = await create_audit_entry(
            db_session=async_session,
            user_id=user.id,
            action="batch_create",
            module="customers",
            operation_type="batch",
            extra_metadata=metadata,
            ip_address="127.0.0.1",
        )
        assert audit.operation_type == "batch"
        assert audit.extra_metadata["total_count"] == 10
        assert audit.extra_metadata["success_count"] == 8

        # 验证数据已持久化
        await async_session.refresh(audit)
        assert audit.id is not None

    @pytest.mark.asyncio
    async def test_create_sensitive_audit_entry(self, async_session):
        # 先创建用户
        user = User(
            username="sensitive_user",
            password_hash="hashed_password",
            email="sensitive@example.com",
        )
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        audit = await create_audit_entry(
            db_session=async_session,
            user_id=user.id,
            action="reset_password",
            module="users",
            record_id=123,
            record_type="user",
            operation_type="sensitive",
            ip_address="127.0.0.1",
        )
        assert audit.operation_type == "sensitive"
        assert audit.action == "reset_password"

        # 验证数据已持久化
        await async_session.refresh(audit)
        assert audit.id is not None
