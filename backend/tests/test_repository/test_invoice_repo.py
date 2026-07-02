"""InvoiceRepository 单元测试"""

from decimal import Decimal

import pytest

from app.repository import InvoiceRepository


@pytest.mark.asyncio
class TestInvoiceRepository:
    """InvoiceRepository 测试类"""

    async def test_find_by_id(self, db_session, sample_invoice):
        """测试根据 ID 查询"""
        repo = InvoiceRepository(db_session)

        result = await repo.find_by_id(sample_invoice.id)

        assert result is not None
        assert result.id == sample_invoice.id

    async def test_find_by_customer_id(self, db_session, sample_invoice):
        """测试根据客户 ID 查询"""
        repo = InvoiceRepository(db_session)

        results = await repo.find_by_customer_id(sample_invoice.customer_id)

        assert len(results) > 0
        assert all(r.customer_id == sample_invoice.customer_id for r in results)

    async def test_find_by_customer_id_with_status(self, db_session, sample_invoice):
        """测试根据客户 ID 和状态查询"""
        repo = InvoiceRepository(db_session)

        results = await repo.find_by_customer_id(
            sample_invoice.customer_id, status=sample_invoice.status
        )

        assert len(results) > 0
        assert all(r.status == sample_invoice.status for r in results)

    async def test_find_pending_invoices(self, db_session, sample_invoice):
        """测试查询待处理发票"""
        repo = InvoiceRepository(db_session)

        results = await repo.find_pending_invoices(sample_invoice.customer_id)

        assert isinstance(results, list)

    async def test_get_total_amount(self, db_session, sample_invoice):
        """测试获取总金额"""
        repo = InvoiceRepository(db_session)

        total = await repo.get_total_amount(sample_invoice.customer_id)

        assert isinstance(total, Decimal)
        assert total >= 0

    async def test_get_total_amount_with_status(self, db_session, sample_invoice):
        """测试获取指定状态的总金额"""
        repo = InvoiceRepository(db_session)

        total = await repo.get_total_amount(
            sample_invoice.customer_id, status=sample_invoice.status
        )

        assert isinstance(total, Decimal)
        assert total >= 0
