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
                text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name != 'alembic_version'
            """)
            )
            tables = [row[0] for row in result.fetchall()]
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
        password_hash="hashed_password",
        email="test@example.com",
        real_name="测试用户",
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
        name="Test Customer",
        company_id=10001,
        account_type="enterprise",
        manager_id=sample_user.id,
        settlement_cycle="monthly",
        settlement_type="prepaid",
        is_key_customer=False,
        is_real_estate=False,
        email="test@example.com",
        erp_system="test_erp",
        first_payment_date=date.today(),
        onboarding_date=date.today(),
        sales_manager_id=sample_user.id,
        cooperation_status="active",
        is_settlement_enabled=True,
        is_disabled=False,
        notes="Test customer",
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
        total_amount=Decimal("1000.00"),
        real_amount=Decimal("800.00"),
        bonus_amount=Decimal("200.00"),
        used_total=Decimal("100.00"),
        used_real=Decimal("80.00"),
        used_bonus=Decimal("20.00"),
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
        invoice_no="INV-2026-001",
        invoice_date=date.today(),
        due_date=date.today(),
        total_amount=Decimal("500.00"),
        paid_amount=Decimal("0.00"),
        status="pending",
        notes="Test invoice",
    )
    db_session.add(invoice)
    await db_session.commit()
    await db_session.refresh(invoice)
    return invoice


@pytest.fixture
async def sample_pricing_rule(db_session: AsyncSession, sample_customer: Customer) -> PricingRule:
    """创建测试定价规则"""
    pricing_rule = PricingRule(
        customer_id=sample_customer.id,
        device_type="X",
        layer_type="single",
        pricing_type="fixed",
        unit_price=Decimal("1.00"),
        effective_date=date(2026, 1, 1),
        expiry_date=date(2026, 12, 31),
        created_by=1,
    )
    db_session.add(pricing_rule)
    await db_session.commit()
    await db_session.refresh(pricing_rule)
    return pricing_rule
