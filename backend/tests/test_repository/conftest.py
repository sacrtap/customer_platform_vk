"""Repository 测试 fixtures"""

import os
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# 导入所有模型以确保 SQLAlchemy relationship 正确解析
from app.models.base import BaseModel
from app.models.billing import (
    CustomerBalance,
    Invoice,
    PricingRule,
)
from app.models.customers import Customer
from app.models.users import User

# 测试数据库配置
_TEST_DB_USER = os.environ.get("POSTGRES_USER", "postgres")
_TEST_DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
_TEST_DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
_TEST_DB_NAME = os.environ.get("POSTGRES_DB", "customer_platform_test")

TEST_DATABASE_ASYNC_URL = (
    f"postgresql+asyncpg://{_TEST_DB_USER}:{_TEST_DB_PASSWORD}@{_TEST_DB_HOST}:5432/{_TEST_DB_NAME}"
)


@pytest.fixture(scope="function")
async def db_session():
    """创建异步数据库会话"""
    engine = create_async_engine(
        TEST_DATABASE_ASYNC_URL,
        echo=False,
        pool_pre_ping=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)

    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as session:
        yield session

    # 清理：TRUNCATE CASCADE 清理所有表
    async with engine.begin() as conn:
        try:
            result = await conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            tables = [row[0] for row in result]
            if tables:
                table_list = ", ".join(tables)
                await conn.execute(text(f"TRUNCATE {table_list} CASCADE"))
        except Exception:
            pass  # 忽略清理错误

    await engine.dispose()


@pytest.fixture
async def sample_user(db_session: AsyncSession) -> User:
    """创建测试用户"""
    user = User(
        username="test_user",
        email="test@example.com",
        password_hash="hashed_password",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def sample_customer(db_session: AsyncSession, sample_user: User) -> Customer:
    """创建测试客户"""
    customer = Customer(
        company_id=10001,
        name="测试客户公司",
        manager_id=sample_user.id,
        account_type="正式账号",
        settlement_type="prepaid",
        created_by=sample_user.id,
    )
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)
    return customer


@pytest.fixture
async def sample_balance(db_session: AsyncSession, sample_customer: Customer) -> CustomerBalance:
    """创建测试余额记录"""
    balance = CustomerBalance(
        customer_id=sample_customer.id,
        balance=Decimal("10000.00"),
        bonus=Decimal("1000.00"),
        frozen=Decimal("0.00"),
    )
    db_session.add(balance)
    await db_session.commit()
    await db_session.refresh(balance)
    return balance


@pytest.fixture
async def sample_invoice(db_session: AsyncSession, sample_customer: Customer) -> Invoice:
    """创建测试发票"""
    invoice = Invoice(
        customer_id=sample_customer.id,
        invoice_no="INV-2026-0001",
        total_amount=Decimal("5000.00"),
        status="draft",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )
    db_session.add(invoice)
    await db_session.commit()
    await db_session.refresh(invoice)
    return invoice


@pytest.fixture
async def sample_pricing_rule(db_session: AsyncSession, sample_customer: Customer) -> PricingRule:
    """创建测试定价规则"""
    pricing_rule = PricingRule(
        name="测试定价规则",
        device_type="server",
        layer_type="standard",
        price_type="unit",
        unit_price=Decimal("100.00"),
        effective_from=date(2026, 1, 1),
        is_active=True,
    )
    db_session.add(pricing_rule)
    await db_session.commit()
    await db_session.refresh(pricing_rule)
    return pricing_rule
