"""审计辅助函数单元测试"""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models.base import Base
from app.models.billing import AuditLog
from app.models.users import User
from app.utils.audit_helpers import (
    create_audit_entry,
    build_batch_audit_summary,
    mask_sensitive_data,
)

# 测试数据库配置（修复：缺少用户凭证）
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/customer_platform_test"

# 使用 xdist_group 标记，确保数据库操作测试串行执行
pytestmark = pytest.mark.xdist_group("db_models")


@pytest.fixture(scope="function")
async def async_engine():
    """创建异步测试数据库引擎

    注意：此 fixture 会 drop_all + create_all，在并行模式下会导致表冲突。
    通过 pytest.mark.xdist_group("db_models") 确保这些测试串行执行。
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    # 创建所有表（不 drop，避免影响其他并行测试）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 清理：只关闭连接，不 drop 表
    await engine.dispose()


@pytest.fixture(scope="function")
async def async_session(async_engine):
    """创建异步数据库会话

    每个测试开始前清理相关表数据，确保测试间数据隔离。
    注意：需要按外键依赖顺序删除（先删引用表，再删被引用表）。
    """
    from sqlalchemy import delete, text
    from app.models.billing import AuditLog
    from app.models.users import User

    async_session_maker = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        # 测试前清理：使用 TRUNCATE CASCADE 清理所有相关数据
        await session.execute(text("TRUNCATE audit_logs, customers, customer_group_members, customer_groups, users CASCADE"))
        await session.commit()

        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class TestBuildBatchAuditSummary:
    def test_basic_summary(self):
        result = build_batch_audit_summary(
            operation="customer_import",
            total_count=10,
            success_count=8,
        )
        assert result["operation"] == "customer_import"
        assert result["total_count"] == 10
        assert result["success_count"] == 8
        assert result["failed_count"] == 2
        assert result["details"] == []

    def test_custom_failed_count(self):
        result = build_batch_audit_summary(
            operation="user_import",
            total_count=5,
            success_count=3,
            failed_count=1,
        )
        assert result["failed_count"] == 1

    def test_with_details(self):
        details = [
            {"row": 3, "error": "用户名已存在"},
            {"row": 5, "error": "邮箱格式错误"},
        ]
        result = build_batch_audit_summary(
            operation="user_import",
            total_count=5,
            success_count=3,
            details=details,
        )
        assert len(result["details"]) == 2
        assert result["details"][0]["row"] == 3


class TestMaskSensitiveData:
    def test_default_fields(self):
        data = {
            "username": "test",
            "password": "secret123",
            "password_hash": "abc123",
            "email": "test@example.com",
        }
        result = mask_sensitive_data(data)
        assert result["username"] == "test"
        assert result["password"] == "***MASKED***"
        assert result["password_hash"] == "***MASKED***"
        assert result["email"] == "test@example.com"

    def test_custom_fields(self):
        data = {
            "api_key": "key123",
            "token": "tok_abc",
            "name": "Test",
        }
        result = mask_sensitive_data(data, fields=["api_key", "token"])
        assert result["api_key"] == "***MASKED***"
        assert result["token"] == "***MASKED***"
        assert result["name"] == "Test"

    def test_missing_fields(self):
        data = {"username": "test"}
        result = mask_sensitive_data(data)
        assert result["username"] == "test"

    def test_does_not_modify_original(self):
        data = {"password": "secret"}
        original = data.copy()
        mask_sensitive_data(data)
        assert data == original


class TestCreateAuditEntry:
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
