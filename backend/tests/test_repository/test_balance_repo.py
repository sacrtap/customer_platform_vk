"""BalanceRepository 单元测试"""

from decimal import Decimal

import pytest

from app.repository import BalanceRepository


@pytest.mark.asyncio
class TestBalanceRepository:
    """BalanceRepository 测试类"""

    async def test_get_by_customer_id(self, db_session, sample_balance):
        """测试根据客户 ID 获取余额"""
        repo = BalanceRepository(db_session)

        result = await repo.get_by_customer_id(sample_balance.customer_id)

        assert result is not None
        assert result.customer_id == sample_balance.customer_id
        assert isinstance(result.balance, Decimal)

    async def test_get_by_customer_id_not_found(self, db_session):
        """测试查询不存在的客户余额"""
        repo = BalanceRepository(db_session)

        result = await repo.get_by_customer_id(99999)

        assert result is None

    async def test_get_or_create_existing(self, db_session, sample_balance):
        """测试获取已存在的余额记录"""
        repo = BalanceRepository(db_session)

        result = await repo.get_or_create(sample_balance.customer_id)

        assert result is not None
        assert result.customer_id == sample_balance.customer_id
        assert result.id == sample_balance.id

    async def test_get_or_create_new(self, db_session, sample_customer):
        """测试创建新的余额记录"""
        repo = BalanceRepository(db_session)

        # 确保客户没有余额记录
        existing = await repo.get_by_customer_id(sample_customer.id)
        if existing:
            await repo.soft_delete(existing.id)

        result = await repo.get_or_create(sample_customer.id)

        assert result is not None
        assert result.customer_id == sample_customer.id
        assert result.id is not None
        assert result.balance == Decimal("0.00")
