"""VrSettlementService 单元测试 - 状态机、减免、扣款编排

集成测试（test_vr_settlement_api.py）覆盖 HTTP 全流程；本文件聚焦服务层
分支细节：状态机守卫、减免编辑窗口、扣款失败/重试/降级、软删除。
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from app.models.customers import Customer
from app.models.vr_settlement import VrSettlement, VrSettlementDiscountHistory
from app.services.vr_settlement import VrSettlementService


@pytest.fixture
def mock_db_session():
    """Mock 异步数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def service(mock_db_session):
    return VrSettlementService(mock_db_session)


def _result(scalar_one=None, scalars_list=None, scalar_value=None):
    """构造 db.execute 的返回值 mock"""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=scalar_one)
    scalars = MagicMock()
    scalars.unique = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=scalars_list or []))
    )
    scalars.all = MagicMock(return_value=scalars_list or [])
    result.scalars = MagicMock(return_value=scalars)
    result.scalar = MagicMock(return_value=scalar_value)
    return result


def _settlement(status="draft", **overrides):
    """构造 VrSettlement 实体（不落库）"""
    defaults = dict(
        id=1,
        settlement_no="VR-20261103-1-ABCD",
        customer_id=100,
        period_start=datetime(2026, 11, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 11, 30, tzinfo=timezone.utc),
        total_amount=Decimal("500.00"),
        discount_amount=Decimal("0"),
        status=status,
    )
    defaults.update(overrides)
    return VrSettlement(**defaults)


# ==================== 创建 ====================


class TestCreateSettlement:
    @pytest.mark.asyncio
    async def test_create_generates_vr_prefixed_no(self, service, mock_db_session):
        """结算单号形如 VR-{CST日期}-{客户ID}-{4位随机码}"""
        settlement = await service.create_settlement(
            customer_id=100,
            period_start=datetime(2026, 11, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 11, 30, tzinfo=timezone.utc),
            total_amount=Decimal("500.00"),
            detail_file_path="/uploads/a.xlsx",
            detail_file_name="a.xlsx",
            created_by=1,
        )
        assert settlement.settlement_no.startswith("VR-")
        parts = settlement.settlement_no.split("-")
        assert len(parts) == 4  # VR / 日期 / 客户ID / 随机码
        assert parts[2] == "100"
        assert len(parts[3]) == 4
        assert settlement.status == "draft"
        assert settlement.discount_amount == Decimal("0")
        assert settlement.is_auto_generated is False
        mock_db_session.add.assert_called_once()


# ==================== 查询 ====================


class TestQueries:
    @pytest.mark.asyncio
    async def test_get_settlements_with_filters_and_sort(self, service, mock_db_session):
        """筛选 + 排序 + mine_user_id 均进入查询；返回列表与总数"""
        mock_db_session.execute = AsyncMock(
            side_effect=[
                _result(scalar_value=2),
                _result(scalars_list=[_settlement(), _settlement(id=2)]),
            ]
        )
        rows, total = await service.get_settlements(
            keyword="测试",
            status="draft",
            customer_id=100,
            mine_user_id=7,
            page=2,
            page_size=10,
            sort_by="total_amount",
            sort_order="asc",
        )
        assert total == 2
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_get_settlements_invalid_sort_falls_back(self, service, mock_db_session):
        """非法 sort_by 静默回退 created_at（不报错）"""
        mock_db_session.execute = AsyncMock(
            side_effect=[_result(scalar_value=0), _result(scalars_list=[])]
        )
        rows, total = await service.get_settlements(sort_by="bogus_field", sort_order="desc")
        assert rows == [] and total == 0

    @pytest.mark.asyncio
    async def test_get_settlement_by_id_found_and_missing(self, service, mock_db_session):
        s = _settlement()
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=s))
        assert (await service.get_settlement_by_id(1)) is s

        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=None))
        assert await service.get_settlement_by_id(999) is None

    @pytest.mark.asyncio
    async def test_get_discount_histories_returns_list(self, service, mock_db_session):
        history = VrSettlementDiscountHistory(
            id=1,
            settlement_id=1,
            discount_amount=Decimal("100"),
            discount_reason="优惠",
            applied_at="2026-11-03 10:00:00",
            applied_by=1,
        )
        mock_db_session.execute = AsyncMock(return_value=_result(scalars_list=[history]))
        rows = await service.get_discount_histories(1)
        assert len(rows) == 1
        assert rows[0].discount_amount == Decimal("100")


# ==================== 状态机 ====================


class TestStateMachine:
    @pytest.mark.asyncio
    async def test_submit_requires_sales_manager(self, service, mock_db_session):
        """客户未指定销售 → 拒绝提交"""
        settlement = _settlement(status="draft")
        customer = Customer(id=100, name="x", sales_manager_id=None)
        mock_db_session.execute = AsyncMock(
            side_effect=[_result(scalar_one=settlement), _result(scalar_one=customer)]
        )
        ok, msg = await service.submit_settlement(1, user_id=1)
        assert ok is False
        assert msg == "该客户未指定销售经理，无法提交审批"

    @pytest.mark.asyncio
    async def test_submit_success(self, service, mock_db_session):
        settlement = _settlement(status="draft")
        customer = Customer(id=100, name="x", sales_manager_id=5)
        mock_db_session.execute = AsyncMock(
            side_effect=[_result(scalar_one=settlement), _result(scalar_one=customer)]
        )
        ok, msg = await service.submit_settlement(1, user_id=1)
        assert ok is True
        assert settlement.status == "pending_cs_supervisor"

    @pytest.mark.asyncio
    async def test_wrong_status_rejected_uniform_message(self, service, mock_db_session):
        """状态不匹配统一消息格式"""
        settlement = _settlement(status="draft")
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        ok, msg = await service.confirm_cs_supervisor(1, user_id=1)
        assert ok is False
        assert msg == "当前状态（draft）不允许该操作"

    @pytest.mark.asyncio
    async def test_settlement_not_found(self, service, mock_db_session):
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=None))
        ok, msg = await service.confirm_sales(999, user_id=1)
        assert ok is False and msg == "结算单不存在"

    @pytest.mark.asyncio
    async def test_confirm_sales_identity_check(self, service, mock_db_session):
        """非指定销售 → 拒绝"""
        settlement = _settlement(status="pending_sales")
        customer = Customer(id=100, name="x", sales_manager_id=5)
        mock_db_session.execute = AsyncMock(
            side_effect=[_result(scalar_one=settlement), _result(scalar_one=customer)]
        )
        ok, msg = await service.confirm_sales(1, user_id=99)
        assert ok is False
        assert msg == "您不是该客户指定的销售，无权确认"

    @pytest.mark.asyncio
    async def test_confirm_sales_supervisor_writes_discount_approval(
        self, service, mock_db_session
    ):
        """有减免时一并写审批三字段"""
        settlement = _settlement(status="pending_sales_supervisor", discount_amount=Decimal("100"))
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        ok, _ = await service.confirm_sales_supervisor(1, user_id=9, comment="同意减免")
        assert ok is True
        assert settlement.status == "pending_customer"
        assert settlement.discount_approver_id == 9
        assert settlement.discount_approved_at is not None
        assert settlement.discount_approval_comment == "同意减免"

    @pytest.mark.asyncio
    async def test_confirm_sales_supervisor_without_discount(self, service, mock_db_session):
        """无减免时不写审批字段"""
        settlement = _settlement(status="pending_sales_supervisor", discount_amount=Decimal("0"))
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        ok, _ = await service.confirm_sales_supervisor(1, user_id=9)
        assert ok is True
        assert settlement.discount_approver_id is None
        assert settlement.status == "pending_customer"

    @pytest.mark.asyncio
    async def test_reject_reverts_to_pending_sales(self, service, mock_db_session):
        """驳回到待销售，理由落库"""
        settlement = _settlement(status="pending_sales_supervisor")
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        ok, _ = await service.reject_sales_supervisor(1, user_id=9, comment="金额有误")
        assert ok is True
        assert settlement.status == "pending_sales"
        assert settlement.discount_approval_comment == "金额有误"

    @pytest.mark.asyncio
    async def test_cancel_non_terminal(self, service, mock_db_session):
        settlement = _settlement(status="pending_customer")
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        ok, _ = await service.cancel_settlement(1, user_id=1)
        assert ok is True
        assert settlement.status == "cancelled"
        assert settlement.cancelled_by == 1

    @pytest.mark.asyncio
    async def test_cancel_completed_rejected(self, service, mock_db_session):
        settlement = _settlement(status="completed")
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        ok, msg = await service.cancel_settlement(1, user_id=1)
        assert ok is False
        assert "不允许该操作" in msg


# ==================== 减免 ====================


class TestDiscount:
    @pytest.mark.asyncio
    async def test_apply_discount_zero_rejected(self, service, mock_db_session):
        settlement = _settlement(status="draft")
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        ok, msg = await service.apply_discount(
            1,
            discount_amount=Decimal("0"),
            discount_reason="x",
            discount_attachment=None,
            user_id=1,
        )
        assert ok is False
        assert msg == "减免金额不能为 0"

    @pytest.mark.asyncio
    async def test_apply_discount_allowed_at_sales_supervisor(self, service, mock_db_session):
        """销售主管审批通过前（pending_sales_supervisor）仍可提交/修改减免"""
        settlement = _settlement(status="pending_sales_supervisor")
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        ok, _ = await service.apply_discount(
            1,
            discount_amount=Decimal("100"),
            discount_reason="x",
            discount_attachment=None,
            user_id=1,
        )
        assert ok is True
        assert settlement.discount_amount == Decimal("100")

    @pytest.mark.asyncio
    async def test_apply_discount_locked_after_customer(self, service, mock_db_session):
        """销售主管审批通过（pending_customer）起锁定，防止绕过已生效的减免审批"""
        settlement = _settlement(status="pending_customer")
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        ok, msg = await service.apply_discount(
            1,
            discount_amount=Decimal("100"),
            discount_reason="x",
            discount_attachment=None,
            user_id=1,
        )
        assert ok is False
        assert "不允许该操作" in msg

    @pytest.mark.asyncio
    async def test_apply_discount_success_writes_history(self, service, mock_db_session):
        settlement = _settlement(status="pending_sales")
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        ok, _ = await service.apply_discount(
            1,
            discount_amount=Decimal("100"),
            discount_reason="大客户优惠",
            discount_attachment="/uploads/p.pdf",
            user_id=1,
        )
        assert ok is True
        assert settlement.discount_amount == Decimal("100")
        assert settlement.discount_applied_at is not None
        # 重新提交减免清空上一轮审批结果
        assert settlement.discount_approver_id is None
        mock_db_session.add.assert_called_once()
        history = mock_db_session.add.call_args[0][0]
        assert isinstance(history, VrSettlementDiscountHistory)
        assert history.discount_amount == Decimal("100")


# ==================== 扣款 ====================


class TestDeduction:
    @pytest.mark.asyncio
    async def test_confirm_customer_deducts_and_completes(self, service, mock_db_session):
        """客户确认 → 扣款成功 → completed"""
        settlement = _settlement(status="pending_customer", total_amount=Decimal("500"))
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        with patch("app.services.vr_settlement.BalanceService") as mock_bs:
            mock_bs.return_value.consume = AsyncMock(return_value=(True, "扣款成功"))
            ok, msg = await service.confirm_customer(1, user_id=1)
        assert ok is True
        assert msg == "客户确认成功，已自动完成扣款"
        assert settlement.status == "completed"
        assert settlement.completed_by == 1
        # 扣款金额 = final_amount，带 vr_settlement_id
        call_kwargs = mock_bs.return_value.consume.call_args.kwargs
        assert call_kwargs["customer_id"] == 100
        assert call_kwargs["amount"] == Decimal("500")
        assert call_kwargs["vr_settlement_id"] == 1

    @pytest.mark.asyncio
    async def test_confirm_customer_deduct_failure_keeps_status(self, service, mock_db_session):
        """扣款失败：保持 customer_confirmed，返回带前缀的失败消息"""
        settlement = _settlement(status="pending_customer")
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        with patch("app.services.vr_settlement.BalanceService") as mock_bs:
            mock_bs.return_value.consume = AsyncMock(return_value=(False, "客户余额账户不存在"))
            ok, msg = await service.confirm_customer(1, user_id=1)
        assert ok is False
        assert msg == "客户确认成功，但扣款失败：客户余额账户不存在"
        assert settlement.status == "customer_confirmed"

    @pytest.mark.asyncio
    async def test_confirm_customer_operational_error_degraded(self, service, mock_db_session):
        """OperationalError 降级为业务消息（不穿透 500）"""
        settlement = _settlement(status="pending_customer")
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        with patch("app.services.vr_settlement.BalanceService") as mock_bs:
            mock_bs.return_value.consume = AsyncMock(
                side_effect=OperationalError("SELECT ...", {}, Exception("busy"))
            )
            ok, msg = await service.confirm_customer(1, user_id=1)
        assert ok is False
        assert msg == "客户确认成功，但扣款失败：数据库繁忙，请稍后重试"
        assert settlement.status == "customer_confirmed"

    @pytest.mark.asyncio
    async def test_retry_deduction_strips_prefix_on_failure(self, service, mock_db_session):
        """重试失败消息去掉「客户确认成功」前缀"""
        settlement = _settlement(status="customer_confirmed")
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        with patch("app.services.vr_settlement.BalanceService") as mock_bs:
            mock_bs.return_value.consume = AsyncMock(return_value=(False, "客户余额账户不存在"))
            ok, msg = await service.retry_deduction(1, user_id=1)
        assert ok is False
        assert msg == "扣款失败：客户余额账户不存在"

    @pytest.mark.asyncio
    async def test_retry_deduction_success(self, service, mock_db_session):
        settlement = _settlement(status="customer_confirmed")
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        with patch("app.services.vr_settlement.BalanceService") as mock_bs:
            mock_bs.return_value.consume = AsyncMock(return_value=(True, "扣款成功"))
            ok, msg = await service.retry_deduction(1, user_id=1)
        assert ok is True
        assert msg == "重试扣款成功"
        assert settlement.status == "completed"

    @pytest.mark.asyncio
    async def test_retry_deduction_wrong_status(self, service, mock_db_session):
        settlement = _settlement(status="draft")
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        ok, msg = await service.retry_deduction(1, user_id=1)
        assert ok is False
        assert "不允许该操作" in msg


# ==================== 删除 ====================


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_success(self, service, mock_db_session):
        settlement = _settlement()
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=settlement))
        assert await service.delete_settlement(1) is True
        assert settlement.deleted_at is not None

    @pytest.mark.asyncio
    async def test_delete_not_found(self, service, mock_db_session):
        mock_db_session.execute = AsyncMock(return_value=_result(scalar_one=None))
        assert await service.delete_settlement(999) is False
