"""充值记录撤销单元测试 —— 软删、余额回退、超管强制与线下核对标记"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.billing import CustomerBalance, RechargeRecord
from app.models.customers import Customer
from app.services.billing import BalanceService, RechargeRevokeError

RECORD_ID = 4662
CUSTOMER_ID = 27647


class TestRevokeRecharge:
    """撤销手动/导入充值：软删记录 + 回退余额"""

    def _service(self, scalars):
        db = MagicMock()
        db.scalar = AsyncMock(side_effect=scalars)
        db.execute = AsyncMock()
        db.flush = AsyncMock()
        db.in_transaction = MagicMock(return_value=True)
        repo = MagicMock()
        repo.db = db
        return BalanceService(repo), db

    def _rows(
        self,
        *,
        balance_real: str = "50000.00",
        balance_bonus: str = "0.00",
        record_real: str = "50000.00",
        record_bonus: str = "0.00",
        crm_payment_id: int | None = None,
    ):
        customer = Customer(id=CUSTOMER_ID, company_id=1001, name="宿州诚信房产")
        target = RechargeRecord(
            id=RECORD_ID,
            customer_id=CUSTOMER_ID,
            real_amount=Decimal(record_real),
            bonus_amount=Decimal(record_bonus),
            crm_payment_id=crm_payment_id,
            recharge_date=date(2026, 11, 6),
            created_at=datetime(2026, 11, 6, 10, 0),
            payment_proof="/uploads/proof.png",
            remark="Q1 充值",
        )
        record = RechargeRecord(
            id=RECORD_ID,
            customer_id=CUSTOMER_ID,
            real_amount=Decimal(record_real),
            bonus_amount=Decimal(record_bonus),
            crm_payment_id=crm_payment_id,
            recharge_date=date(2026, 11, 6),
            created_at=datetime(2026, 11, 6, 10, 0),
            payment_proof="/uploads/proof.png",
            remark="Q1 充值",
        )
        balance = CustomerBalance(
            customer_id=CUSTOMER_ID,
            real_amount=Decimal(balance_real),
            bonus_amount=Decimal(balance_bonus),
            total_amount=Decimal(balance_real) + Decimal(balance_bonus),
        )
        return customer, target, balance, record

    async def _revoke(self, service, **kwargs):
        params = {
            "record_id": RECORD_ID,
            "reason": "误充到错误客户",
            "operator_id": 1,
            "is_super_admin": False,
            "force": False,
        }
        params.update(kwargs)
        return await service.revoke_recharge(**params)

    @pytest.mark.asyncio
    async def test_revoke_rolls_back_balance_and_soft_deletes(self, monkeypatch):
        audit = AsyncMock()
        monkeypatch.setattr("app.services.billing.create_audit_entry", audit)

        customer, target, balance, record = self._rows(
            balance_real="50000.00",
            balance_bonus="200.00",
            record_real="1000.00",
            record_bonus="200.00",
        )
        service, db = self._service([target, customer, balance, record])

        result = await self._revoke(service)

        assert result["balance"] == {
            "real_amount": "49000.00",
            "bonus_amount": "0.00",
            "total_amount": "49000.00",
        }
        assert result["needs_manual_reconciliation"] is False
        assert record.deleted_at is not None
        # 软删：原始凭据不丢失
        assert record.payment_proof == "/uploads/proof.png"
        assert record.remark == "Q1 充值"
        db.flush.assert_awaited()
        assert audit.await_args is not None
        changes = audit.await_args.kwargs["changes"]
        assert changes["reason"] == "误充到错误客户"
        assert changes["record_snapshot"]["payment_proof"] == "/uploads/proof.png"
        assert changes["balance_before"]["real_amount"] == "50000.00"
        assert changes["balance_after"]["real_amount"] == "49000.00"

    @pytest.mark.asyncio
    async def test_crm_sourced_record_rejected(self):
        customer, target, balance, record = self._rows(crm_payment_id=6)
        service, db = self._service([target, customer, balance, record])

        with pytest.raises(RechargeRevokeError) as exc:
            await self._revoke(service)

        assert exc.value.status == 400
        assert "CRM" in exc.value.message
        assert record.deleted_at is None
        db.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_already_revoked_rejected(self):
        customer, target, balance, record = self._rows()
        target.deleted_at = datetime(2026, 11, 7, 9, 0)
        service, _ = self._service([target, customer, balance, record])

        with pytest.raises(RechargeRevokeError) as exc:
            await self._revoke(service)

        assert exc.value.status == 400
        assert "已撤销" in exc.value.message

    @pytest.mark.asyncio
    async def test_missing_record_404(self):
        service, _ = self._service([None])
        with pytest.raises(RechargeRevokeError) as exc:
            await self._revoke(service)
        assert exc.value.status == 404

    @pytest.mark.asyncio
    async def test_scope_user_mismatch_forbidden(self):
        customer, target, balance, record = self._rows()
        service, _ = self._service([target, customer, balance, record])

        with pytest.raises(RechargeRevokeError) as exc:
            await self._revoke(service, scope_user_id=99999)

        assert exc.value.status == 403
        assert "无权操作" in exc.value.message

    @pytest.mark.asyncio
    async def test_insufficient_balance_requires_super_admin(self):
        customer, target, balance, record = self._rows(balance_real="20000.00")
        service, db = self._service([target, customer, balance, record])

        with pytest.raises(RechargeRevokeError) as exc:
            await self._revoke(service)

        assert exc.value.status == 403
        assert "超级管理员" in exc.value.message
        assert record.deleted_at is None
        db.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_super_admin_must_confirm_force(self):
        customer, target, balance, record = self._rows(balance_real="20000.00")
        service, _ = self._service([target, customer, balance, record])

        with pytest.raises(RechargeRevokeError) as exc:
            await self._revoke(service, is_super_admin=True, force=False)

        assert exc.value.status == 409

    @pytest.mark.asyncio
    async def test_forced_revoke_marks_manual_reconciliation(self, monkeypatch):
        audit = AsyncMock()
        monkeypatch.setattr("app.services.billing.create_audit_entry", audit)

        customer, target, balance, record = self._rows(balance_real="20000.00")
        service, db = self._service([target, customer, balance, record])

        result = await self._revoke(service, is_super_admin=True, force=True)

        assert result["needs_manual_reconciliation"] is True
        assert result["shortfall_real"] == "30000.00"
        assert result["balance"]["real_amount"] == "-30000.00"
        assert record.deleted_at is not None
        assert audit.await_args is not None
        changes = audit.await_args.kwargs["changes"]
        assert changes["needs_manual_reconciliation"] is True
        assert changes["forced"] is True
        assert changes["balance_after"]["real_amount"] == "-30000.00"
        db.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_requires_outer_transaction(self):
        customer, target, balance, record = self._rows()
        service, db = self._service([target, customer, balance, record])
        db.in_transaction = MagicMock(return_value=False)

        with pytest.raises(RuntimeError):
            await self._revoke(service)
