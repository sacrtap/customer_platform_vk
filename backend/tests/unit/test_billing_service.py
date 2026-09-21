"""Billing Service 单元测试 - 余额扣款与定价规则"""

import logging
import time
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from app.models.billing import (
    CustomerBalance,
    Invoice,
    PricingRule,
    RechargeRecord,
)
from app.services.billing import BalanceService, InvoiceService, PricingService
from app.utils.timezone import (
    local_date_range_to_utc,
    local_date_to_utc_end,
    local_date_to_utc_start,
)

# ==================== Fixtures ====================


@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    # 默认无残留事务（调用方已自行提交的常规路径）；
    # consume 对残留事务的收敛行为由 TestBalanceService_ConsumeFailureRecovery 锁定
    session.in_transaction = MagicMock(return_value=False)
    return session


@pytest.fixture
def balance_service(mock_db_session):
    """创建 BalanceService 实例"""
    from unittest.mock import AsyncMock, MagicMock

    from app.repository import BalanceRepository

    mock_repo = MagicMock(spec=BalanceRepository)
    mock_repo.db = mock_db_session
    mock_repo.get_by_customer_id = AsyncMock(return_value=None)
    mock_repo.get_or_create = AsyncMock(return_value=None)
    return BalanceService(balance_repo=mock_repo)


@pytest.fixture
def pricing_service(mock_db_session):
    """创建 PricingService 实例"""
    from unittest.mock import MagicMock

    from app.repository import PricingRepository

    mock_repo = MagicMock(spec=PricingRepository)
    mock_repo.db = mock_db_session
    return PricingService(pricing_repo=mock_repo)


# ==================== Test BalanceService - Recharge ====================


class TestBalanceService_Recharge:
    """充值测试"""

    @pytest.mark.asyncio
    async def test_recharge_success(self, balance_service, mock_db_session):
        """测试充值成功"""
        # Mock 现有余额
        existing_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("200.00"),
            total_amount=Decimal("1200.00"),
        )
        balance_service.balance_repo.get_or_create.return_value = existing_balance

        # 执行充值
        result = await balance_service.recharge(
            customer_id=100,
            real_amount=Decimal("500.00"),
            bonus_amount=Decimal("100.00"),
            operator_id=1,
            payment_proof="proof.pdf",
            remark="测试充值",
        )

        # 验证结果
        assert result is not None
        assert isinstance(result, RechargeRecord)
        assert result.real_amount == Decimal("500.00")
        assert result.bonus_amount == Decimal("100.00")

        # 验证余额更新
        assert existing_balance.real_amount == Decimal("1500.00")
        assert existing_balance.bonus_amount == Decimal("300.00")
        assert existing_balance.total_amount == Decimal("1800.00")

        # 验证数据库操作
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_recharge_recalculates_total_amount(self, balance_service, mock_db_session):
        """测试充值后 total_amount 通过重算得到（而非累加），修正数据不一致场景"""
        # 模拟 total_amount 与 real+bonus 不一致（如历史脏数据）
        existing_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("200.00"),
            total_amount=Decimal("9999.00"),  # 脏数据：不等于 1000+200=1200
        )
        balance_service.balance_repo.get_or_create.return_value = existing_balance

        # 充值 500 实充 + 100 赠金
        result = await balance_service.recharge(
            customer_id=100,
            real_amount=Decimal("500.00"),
            bonus_amount=Decimal("100.00"),
            operator_id=1,
        )

        assert result is not None
        # real_amount = 1000 + 500 = 1500
        assert existing_balance.real_amount == Decimal("1500.00")
        # bonus_amount = 200 + 100 = 300
        assert existing_balance.bonus_amount == Decimal("300.00")
        # total_amount = 重算(1500 + 300) = 1800，而非脏数据累加(9999 + 500 + 100 = 10599)
        assert existing_balance.total_amount == Decimal("1800.00")

    @pytest.mark.asyncio
    async def test_recharge_creates_balance_if_not_exists(self, balance_service, mock_db_session):
        """测试充值时如果余额不存在则自动创建"""
        # Mock 返回新创建的余额
        new_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("0.00"),
            bonus_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
        )
        balance_service.balance_repo.get_or_create.return_value = new_balance

        # 执行充值
        result = await balance_service.recharge(
            customer_id=200,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("0.00"),
            operator_id=1,
        )

        # 验证结果
        assert result is not None
        assert result.real_amount == Decimal("1000.00")

        # 验证调用了 get_or_create 获取余额
        balance_service.balance_repo.get_or_create.assert_called_once_with(200)
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_recharge_zero_real_with_bonus(self, balance_service, mock_db_session):
        """测试实充为 0、仅赠送金额的充值（允许 real_amount=0）"""
        existing_balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("500.00"),
            bonus_amount=Decimal("100.00"),
            total_amount=Decimal("600.00"),
        )
        balance_service.balance_repo.get_or_create.return_value = existing_balance

        result = await balance_service.recharge(
            customer_id=100,
            real_amount=Decimal("0"),  # 实充为 0
            bonus_amount=Decimal("200.00"),  # 仅赠送
            operator_id=1,
        )

        assert result is not None
        assert result.real_amount == Decimal("0.00")
        assert result.bonus_amount == Decimal("200.00")
        # 余额不变实充，赠金增加
        assert existing_balance.real_amount == Decimal("500.00")
        assert existing_balance.bonus_amount == Decimal("300.00")
        assert existing_balance.total_amount == Decimal("800.00")  # 500 + 300


# ==================== Test BalanceService - Recalculate ====================


class TestBalanceService_Recalculate:
    """余额重算测试"""

    @pytest.mark.asyncio
    async def test_recalculate_fixes_inconsistent_total(self, balance_service, mock_db_session):
        """测试重算修正不一致的 total_amount"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("200.00"),
            total_amount=Decimal("9999.00"),  # 脏数据
        )
        balance_service.balance_repo.get_by_customer_id.return_value = balance

        result = await balance_service.recalculate_balance(100)

        assert result is not None
        assert result.total_amount == Decimal("1200.00")  # 1000 + 200
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_recalculate_no_change_when_consistent(self, balance_service, mock_db_session):
        """测试重算时数据已一致，不触发 commit"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("200.00"),
            total_amount=Decimal("1200.00"),  # 已一致
        )
        balance_service.balance_repo.get_by_customer_id.return_value = balance

        result = await balance_service.recalculate_balance(100)

        assert result is not None
        assert result.total_amount == Decimal("1200.00")
        # 数据一致时不应该 commit
        mock_db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_recalculate_balance_not_found(self, balance_service, mock_db_session):
        """测试余额不存在时返回 None"""
        balance_service.balance_repo.get_by_customer_id.return_value = None

        result = await balance_service.recalculate_balance(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_recalculate_negative_balance(self, balance_service, mock_db_session):
        """测试重算负余额场景"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("-500.00"),
            bonus_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),  # 脏数据：不等于 -500
        )
        balance_service.balance_repo.get_by_customer_id.return_value = balance

        result = await balance_service.recalculate_balance(100)

        assert result is not None
        assert result.total_amount == Decimal("-500.00")  # -500 + 0
        mock_db_session.commit.assert_called()


# ==================== Test BalanceService - Consume ====================


class TestBalanceService_Consume:
    """消费扣款测试"""

    @pytest.mark.asyncio
    async def test_consume_success_bonus_first(self, balance_service, mock_db_session):
        """测试消费扣款成功 - 先扣赠金"""
        # Mock 余额：有赠金
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("500.00"),
            total_amount=Decimal("1500.00"),
            used_total=Decimal("0.00"),
            used_bonus=Decimal("0.00"),
            used_real=Decimal("0.00"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = balance
        mock_db_session.execute.return_value = mock_result

        # Mock 事务上下文
        mock_db_context = AsyncMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=None)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        mock_db_session.begin.return_value = mock_db_context

        # 执行消费
        success, message = await balance_service.consume(
            customer_id=100,
            amount=Decimal("300.00"),
            invoice_id=1,
        )

        # 验证结果
        assert success is True
        assert message == "扣款成功"

        # 验证先扣赠金
        assert balance.bonus_amount == Decimal("200.00")  # 500 - 300
        assert balance.real_amount == Decimal("1000.00")  # 未动
        assert balance.used_bonus == Decimal("300.00")
        assert balance.used_real == Decimal("0.00")
        assert balance.used_total == Decimal("300.00")

    @pytest.mark.asyncio
    async def test_consume_exhaust_bonus_then_real(self, balance_service, mock_db_session):
        """测试消费扣款 - 赠金不足时扣实充"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("100.00"),
            total_amount=Decimal("1100.00"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = balance
        mock_db_session.execute.return_value = mock_result

        mock_db_context = AsyncMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=None)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        mock_db_session.begin.return_value = mock_db_context

        # 消费 500，先扣 100 赠金，再扣 400 实充
        success, message = await balance_service.consume(
            customer_id=100,
            amount=Decimal("500.00"),
        )

        assert success is True
        assert balance.bonus_amount == Decimal("0.00")
        assert balance.real_amount == Decimal("600.00")  # 1000 - 400
        assert balance.used_bonus == Decimal("100.00")
        assert balance.used_real == Decimal("400.00")

    @pytest.mark.asyncio
    async def test_consume_insufficient_balance_allows_negative(
        self, balance_service, mock_db_session
    ):
        """测试余额不足时允许扣款（欠费模式）— real_amount 变为负数"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("100.00"),
            bonus_amount=Decimal("50.00"),
            total_amount=Decimal("150.00"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = balance
        mock_db_session.execute.return_value = mock_result

        mock_db_context = AsyncMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=None)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        mock_db_session.begin.return_value = mock_db_context

        # 消费 200，超过余额 150
        success, message = await balance_service.consume(
            customer_id=100,
            amount=Decimal("200.00"),
        )

        # 余额不足时仍允许扣款，不再拦截
        assert success is True
        assert message == "扣款成功"

        # 赠金全部耗尽
        assert balance.bonus_amount == Decimal("0.00")
        # 实充变为负数（欠费 50）
        assert balance.real_amount == Decimal("-50.00")
        # 总余额为负
        assert balance.total_amount == Decimal("-50.00")
        assert balance.used_total == Decimal("200.00")
        assert balance.used_bonus == Decimal("50.00")
        assert balance.used_real == Decimal("150.00")

    @pytest.mark.asyncio
    async def test_consume_balance_not_found(self, balance_service, mock_db_session):
        """测试余额账户不存在"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        mock_db_context = AsyncMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=None)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        mock_db_session.begin.return_value = mock_db_context

        success, message = await balance_service.consume(
            customer_id=999,
            amount=Decimal("100.00"),
        )

        assert success is False
        assert "不存在" in message

    @pytest.mark.asyncio
    async def test_consume_zero_balance_goes_negative(self, balance_service, mock_db_session):
        """测试余额为零时扣款 — 全部变为负数"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("0.00"),
            bonus_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = balance
        mock_db_session.execute.return_value = mock_result

        mock_db_context = AsyncMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=None)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        mock_db_session.begin.return_value = mock_db_context

        success, message = await balance_service.consume(
            customer_id=100,
            amount=Decimal("500.00"),
        )

        assert success is True
        assert message == "扣款成功"
        assert balance.bonus_amount == Decimal("0.00")
        assert balance.real_amount == Decimal("-500.00")
        assert balance.total_amount == Decimal("-500.00")
        assert balance.used_real == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_consume_bonus_covers_full_amount(self, balance_service, mock_db_session):
        """测试赠金完全覆盖消费 — 实充不动"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("500.00"),
            total_amount=Decimal("1500.00"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = balance
        mock_db_session.execute.return_value = mock_result

        mock_db_context = AsyncMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=None)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        mock_db_session.begin.return_value = mock_db_context

        success, message = await balance_service.consume(
            customer_id=100,
            amount=Decimal("300.00"),
        )

        assert success is True
        # 赠金扣 300，实充不动
        assert balance.bonus_amount == Decimal("200.00")
        assert balance.real_amount == Decimal("1000.00")
        assert balance.used_bonus == Decimal("300.00")
        assert balance.used_real == Decimal("0.00")


class TestBalanceService_ConsumeFailureRecovery:
    """消费扣款失败恢复路径测试

    consume 使用 AsyncRetrying 包装死锁恢复：最多 3 次尝试、仅对 OperationalError
    重试、每次尝试在独立的 db.begin() 事务边界内重放写入、重试耗尽后按原契约抛出。
    以下用例为该恢复路径提供测试锚点。
    """

    @staticmethod
    def _tx_context() -> AsyncMock:
        """构造一次独立事务的 begin() 上下文"""
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=None)
        ctx.__aexit__ = AsyncMock(return_value=None)
        return ctx

    @staticmethod
    def _operational_error(statement: str = "SELECT ... FOR UPDATE") -> OperationalError:
        """构造死锁类 OperationalError（statement, params, orig）"""
        return OperationalError(statement, {}, Exception("deadlock detected"))

    @pytest.mark.asyncio
    async def test_consume_retry_exhausted_raises_with_fresh_transaction_per_attempt(
        self, balance_service, mock_db_session, caplog
    ):
        """重试耗尽：OperationalError 持续触发直至放弃

        每次尝试都必须开启新的 begin() 事务边界；全部失败后抛出 OperationalError
        （而非返回失败元组），不留任何提交与消费记录，并记录诊断上下文。
        """
        mock_db_session.execute = AsyncMock(side_effect=self._operational_error())
        mock_db_session.begin = MagicMock(side_effect=[self._tx_context() for _ in range(3)])

        started = time.monotonic()
        with caplog.at_level(logging.ERROR):
            with pytest.raises(OperationalError):
                await balance_service.consume(
                    customer_id=100,
                    amount=Decimal("300.00"),
                    invoice_id=1,
                )
        elapsed = time.monotonic() - started

        # 重试有限：stop_after_attempt(3) → 3 次尝试后放弃，不会无限重试
        assert mock_db_session.execute.await_count == 3
        # 事务边界：每次重试都开启独立事务，不存在跨尝试复用的事务上下文
        assert mock_db_session.begin.call_count == 3
        # 并发安全语义：重试期间的每次读取都必须带行级锁，
        # 否则重试仍可能基于过期余额扣款（丢失更新）
        for call in mock_db_session.execute.await_args_list:
            assert "FOR UPDATE" in str(call.args[0])
        # 退避重试而非忙等：尝试之间存在真实等待（wait_exponential 下限 0.1s）
        assert elapsed >= 0.1
        # 不变量：失败路径不产生任何部分提交
        mock_db_session.commit.assert_not_called()
        # 不变量：放弃时不留下消费记录（所有写入随事务作废）
        mock_db_session.add.assert_not_called()
        # 错误契约：抛出原异常而非返回失败元组，并留下诊断上下文
        assert any("重试耗尽" in record.getMessage() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_consume_recovers_after_transient_error_without_double_deduction(
        self, balance_service, mock_db_session
    ):
        """瞬时死锁恢复：首次尝试失败后在新事务边界内重试成功

        首次 SELECT FOR UPDATE 抛错时尚未进入写入阶段，重试重新读取余额并完成扣款；
        断言余额只被扣减一次，失败尝试不得留下写入痕迹。
        """
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("500.00"),
            total_amount=Decimal("1500.00"),
        )
        ok_result = MagicMock()
        ok_result.scalar_one_or_none.return_value = balance

        mock_db_session.execute = AsyncMock(side_effect=[self._operational_error(), ok_result])
        mock_db_session.begin = MagicMock(side_effect=[self._tx_context() for _ in range(2)])

        success, message = await balance_service.consume(customer_id=100, amount=Decimal("300.00"))

        assert success is True
        assert message == "扣款成功"
        # 幂等：失败尝试未进入写入阶段，恢复后余额只被扣减一次
        assert balance.bonus_amount == Decimal("200.00")  # 500 - 300
        assert balance.real_amount == Decimal("1000.00")  # 未动
        assert balance.used_total == Decimal("300.00")
        assert mock_db_session.add.call_count == 1
        # 最终一致：恢复后恰好提交一次事务
        assert mock_db_session.commit.await_count == 1
        # 事务边界：2 次尝试 = 2 个独立事务，重试不复用已失败的事务
        assert mock_db_session.begin.call_count == 2
        assert mock_db_session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_consume_commit_failure_replays_write_in_fresh_transaction(
        self, balance_service, mock_db_session
    ):
        """部分写入路径：提交阶段失败后在新事务边界重放写入

        SELECT 与内存改写已完成、commit 抛 OperationalError 时整个事务作废；
        重试须在新的 begin() 边界内重新读取余额（此处模拟已回滚的初始值）并重建
        消费记录，不得把作废事务中的余额对象当作最终结果。
        """
        initial = Decimal("1000.00")
        initial_bonus = Decimal("500.00")
        rolled_back = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=initial,
            bonus_amount=initial_bonus,
            total_amount=Decimal("1500.00"),
        )
        # 第二次 SELECT 读到的是首次尝试已回滚后的数据
        reread = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=initial,
            bonus_amount=initial_bonus,
            total_amount=Decimal("1500.00"),
        )
        first_result, second_result = MagicMock(), MagicMock()
        first_result.scalar_one_or_none.return_value = rolled_back
        second_result.scalar_one_or_none.return_value = reread

        mock_db_session.execute = AsyncMock(side_effect=[first_result, second_result])
        mock_db_session.commit = AsyncMock(side_effect=[self._operational_error("COMMIT"), None])
        mock_db_session.begin = MagicMock(side_effect=[self._tx_context() for _ in range(2)])

        success, message = await balance_service.consume(customer_id=100, amount=Decimal("300.00"))

        assert success is True
        assert message == "扣款成功"
        # 不泄漏：最终结果来自重试事务重新读取的余额，而非作废事务中的对象
        assert reread.bonus_amount == Decimal("200.00")
        assert reread.real_amount == initial
        assert reread.used_total == Decimal("300.00")
        assert rolled_back is not reread
        # 每次尝试各重建一条消费记录：首次随事务作废，重试成功的那条才是最终结果
        assert mock_db_session.add.call_count == 2
        # 最终一致：首次提交失败、重试成功
        assert mock_db_session.commit.await_count == 2
        # 事务边界：首次提交失败后重试开启独立事务
        assert mock_db_session.begin.call_count == 2

    @pytest.mark.asyncio
    async def test_consume_settles_pending_transaction_before_opening_its_own(
        self, balance_service, mock_db_session
    ):
        """残留事务收敛：调用方遗留的 autobegin 事务不再触发 InvalidRequestError

        调用方（如 complete_invoice）常先执行 SELECT 而留下 autobegin 事务，此时
        db.begin() 会抛 InvalidRequestError —— 它不属于 OperationalError，既不会被
        重试也不会被降级，会直接穿透成 500。consume 必须先收敛该事务再开自己的事务。
        """
        order: list[str] = []
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("0.00"),
            total_amount=Decimal("1000.00"),
        )
        ok_result = MagicMock()
        ok_result.scalar_one_or_none.return_value = balance

        def _begin():
            order.append("begin")
            return self._tx_context()

        mock_db_session.in_transaction = MagicMock(return_value=True)
        mock_db_session.execute = AsyncMock(return_value=ok_result)
        mock_db_session.commit = AsyncMock(side_effect=lambda *_: order.append("commit"))
        mock_db_session.begin = MagicMock(side_effect=_begin)

        success, message = await balance_service.consume(customer_id=100, amount=Decimal("300.00"))

        assert success is True
        assert message == "扣款成功"
        # 先收敛残留事务、再开启重试事务，最后提交扣款
        assert order == ["commit", "begin", "commit"]

    @pytest.mark.asyncio
    async def test_consume_opens_transaction_directly_when_nothing_pending(
        self, balance_service, mock_db_session
    ):
        """无残留事务时不产生多余的收敛提交（调用方已自行 commit 的常规路径）"""
        order: list[str] = []
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            real_amount=Decimal("1000.00"),
            bonus_amount=Decimal("0.00"),
            total_amount=Decimal("1000.00"),
        )
        ok_result = MagicMock()
        ok_result.scalar_one_or_none.return_value = balance

        def _begin():
            order.append("begin")
            return self._tx_context()

        mock_db_session.in_transaction = MagicMock(return_value=False)
        mock_db_session.execute = AsyncMock(return_value=ok_result)
        mock_db_session.commit = AsyncMock(side_effect=lambda *_: order.append("commit"))
        mock_db_session.begin = MagicMock(side_effect=_begin)

        success, _ = await balance_service.consume(customer_id=100, amount=Decimal("300.00"))

        assert success is True
        # 直接开启事务，不再有额外提交
        assert order == ["begin", "commit"]


# ==================== Test BalanceService - Get Balance ====================


class TestBalanceService_GetBalance:
    """获取余额测试"""

    @pytest.mark.asyncio
    async def test_get_balance_by_customer_id(self, balance_service, mock_db_session):
        """测试获取客户余额"""
        balance = CustomerBalance(
            id=1,
            customer_id=100,
            total_amount=Decimal("5000.00"),
        )
        balance_service.balance_repo.get_by_customer_id.return_value = balance

        result = await balance_service.get_balance_by_customer_id(100)

        assert result is not None
        assert result.customer_id == 100
        assert result.total_amount == Decimal("5000.00")

    @pytest.mark.asyncio
    async def test_get_balance_not_found(self, balance_service, mock_db_session):
        """测试获取不存在的余额"""
        balance_service.balance_repo.get_by_customer_id.return_value = None

        result = await balance_service.get_balance_by_customer_id(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_create_balance_existing(self, balance_service, mock_db_session):
        """测试获取或创建余额 - 已存在"""
        balance = CustomerBalance(id=1, customer_id=100, total_amount=Decimal("1000.00"))
        balance_service.balance_repo.get_or_create.return_value = balance

        result = await balance_service.get_or_create_balance(100)

        assert result is not None
        assert result.customer_id == 100

    @pytest.mark.asyncio
    async def test_get_or_create_balance_creates_new(self, balance_service, mock_db_session):
        """测试获取或创建余额 - 不存在时创建"""
        balance = CustomerBalance(id=1, customer_id=100, total_amount=Decimal("0.00"))
        balance_service.balance_repo.get_or_create.return_value = balance

        result = await balance_service.get_or_create_balance(100)

        assert result is not None
        assert result.customer_id == 100


# ==================== Test PricingService - Create Rule ====================


class TestPricingService_CreatePricingRule:
    """创建定价规则测试"""

    @pytest.mark.asyncio
    async def test_create_pricing_rule_success(self, pricing_service, mock_db_session):
        """测试创建定价规则成功"""
        # Mock 无冲突
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        rule_data = {
            "customer_id": 100,
            "device_type": "camera",
            "layer_type": "living_room",
            "pricing_type": "fixed",
            "unit_price": Decimal("10.00"),
            "effective_date": local_date_to_utc_start("2026-01-01"),
            "expiry_date": local_date_to_utc_end("2026-12-31"),
            "created_by": 1,
        }

        result = await pricing_service.create_pricing_rule(rule_data)

        assert result is not None
        assert isinstance(result, PricingRule)
        assert result.customer_id == 100
        assert result.device_type == "camera"
        assert result.unit_price == Decimal("10.00")
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_pricing_rule_overlap_conflict(self, pricing_service, mock_db_session):
        """测试创建定价规则 - 有效期冲突"""
        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="camera",
            layer_type="living_room",
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_rule]
        mock_db_session.execute.return_value = mock_result

        rule_data = {
            "customer_id": 100,
            "device_type": "camera",
            "layer_type": "living_room",
            "pricing_type": "fixed",
            "unit_price": Decimal("10.00"),
            "effective_date": local_date_to_utc_start("2026-06-01"),  # 与现有规则重叠
            "expiry_date": local_date_to_utc_end("2027-06-30"),
            "created_by": 1,
        }

        with pytest.raises(ValueError, match="有效期存在重叠"):
            await pricing_service.create_pricing_rule(rule_data)

    @pytest.mark.asyncio
    async def test_create_pricing_rule_no_overlap_different_device(
        self, pricing_service, mock_db_session
    ):
        """测试创建定价规则 - 不同设备类型不冲突"""
        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="camera",
            layer_type="living_room",
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_rule]
        mock_db_session.execute.return_value = mock_result

        _rule_data = {  # noqa: F841
            "customer_id": 100,
            "device_type": "sensor",  # 不同设备
            "layer_type": "living_room",
            "pricing_type": "fixed",
            "unit_price": Decimal("5.00"),
            "effective_date": local_date_to_utc_start("2026-06-01"),
            "expiry_date": local_date_to_utc_end("2027-06-30"),
            "created_by": 1,
        }

        # 不会抛出异常，因为设备类型不同（实际逻辑会过滤）
        # 这里测试的是 overlap 检查逻辑本身
        # 由于 mock 返回了 existing_rule，但 device_type 不同
        # 实际代码中会先查询再检查，这里直接测试 _check_overlap
        pass  # 需要更精细的 mock

    @pytest.mark.asyncio
    async def test_create_package_rule_without_device_type(self, pricing_service, mock_db_session):
        """测试创建包年结算规则 - 不传 device_type/layer_type"""
        # Mock 无冲突
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        # Mock PackagePlan 查询返回 None（不填充 package_limits）
        mock_plan_result = MagicMock()
        mock_plan_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.side_effect = [mock_result, mock_plan_result]

        rule_data = {
            "customer_id": 100,
            "pricing_type": "package",
            "package_type": "A",
            "effective_date": local_date_to_utc_start("2026-01-01"),
            "expiry_date": local_date_to_utc_end("2026-12-31"),
            "created_by": 1,
        }

        result = await pricing_service.create_pricing_rule(rule_data)

        assert result is not None
        assert isinstance(result, PricingRule)
        assert result.pricing_type == "package"
        assert result.package_type == "A"
        assert result.device_type is None
        assert result.layer_type is None
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_package_rule_overlap_conflict(self, pricing_service, mock_db_session):
        """测试创建包年结算规则 - 同一客户已有包年规则则冲突"""
        existing_package = PricingRule(
            id=2,
            customer_id=100,
            device_type=None,
            layer_type=None,
            pricing_type="package",
            package_type="A",
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_package]
        mock_db_session.execute.return_value = mock_result

        rule_data = {
            "customer_id": 100,
            "pricing_type": "package",
            "package_type": "B",
            "effective_date": local_date_to_utc_start("2026-06-01"),  # 与现有包年规则重叠
            "expiry_date": local_date_to_utc_end("2027-06-30"),
            "created_by": 1,
        }

        with pytest.raises(ValueError, match="包年结算规则"):
            await pricing_service.create_pricing_rule(rule_data)


# ==================== Test PricingService - Update Rule ====================


class TestPricingService_UpdatePricingRule:
    """更新定价规则测试"""

    @pytest.mark.asyncio
    async def test_update_pricing_rule_success(self, pricing_service, mock_db_session):
        """测试更新定价规则成功"""
        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="camera",
            layer_type="living_room",
            pricing_type="fixed",
            unit_price=Decimal("10.00"),
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_rule
        # 第二次调用返回空（无冲突）
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        update_data = {
            "unit_price": Decimal("15.00"),
        }

        result = await pricing_service.update_pricing_rule(1, update_data)

        assert result is not None
        assert result.unit_price == Decimal("15.00")
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_pricing_rule_not_found(self, pricing_service, mock_db_session):
        """测试更新不存在的定价规则"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await pricing_service.update_pricing_rule(999, {"unit_price": Decimal("15.00")})

        assert result is None
        mock_db_session.commit.assert_not_called()


# ==================== Test PricingService - Get Rules ====================


class TestPricingService_GetPricingRules:
    """获取定价规则列表测试"""

    @pytest.mark.asyncio
    async def test_get_pricing_rules_with_filters(self, pricing_service, mock_db_session):
        """测试获取定价规则 - 带筛选条件"""
        rules = [
            PricingRule(id=1, customer_id=100, device_type="camera", pricing_type="fixed"),
            PricingRule(id=2, customer_id=100, device_type="sensor", pricing_type="tiered"),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rules
        mock_result.scalar.return_value = 2  # count
        mock_db_session.execute.return_value = mock_result

        result_rules, total = await pricing_service.get_pricing_rules(
            customer_id=100,
            device_type="camera",
            page=1,
            page_size=20,
        )

        assert len(result_rules) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_pricing_rules_empty(self, pricing_service, mock_db_session):
        """测试获取定价规则 - 无结果"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.scalar.return_value = 0
        mock_db_session.execute.return_value = mock_result

        result_rules, total = await pricing_service.get_pricing_rules(
            customer_id=999,
        )

        assert len(result_rules) == 0
        assert total == 0


# ==================== Test PricingService - Check Conflict ====================


class TestPricingService_CheckConflict:
    """定价规则冲突检查测试"""

    @pytest.mark.asyncio
    async def test_check_pricing_rule_conflict_has_conflict(self, pricing_service, mock_db_session):
        """测试检查定价规则冲突 - 存在冲突"""
        existing_rule = PricingRule(
            id=1,
            customer_id=100,
            device_type="camera",
            layer_type="living_room",
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_rule]
        mock_db_session.execute.return_value = mock_result

        conflicts = await pricing_service.check_pricing_rule_conflict(
            customer_id=100,
            pricing_type="fixed",
            device_type="camera",
            layer_type="living_room",
            effective_date=local_date_to_utc_start("2026-06-01"),
            expiry_date=local_date_to_utc_end("2027-06-30"),
        )

        assert len(conflicts) == 1
        assert conflicts[0].id == 1

    @pytest.mark.asyncio
    async def test_check_pricing_rule_conflict_no_conflict(self, pricing_service, mock_db_session):
        """测试检查定价规则冲突 - 无冲突"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        conflicts = await pricing_service.check_pricing_rule_conflict(
            customer_id=100,
            pricing_type="fixed",
            device_type="camera",
            layer_type="living_room",
            effective_date=local_date_to_utc_start("2027-01-01"),  # 在现有规则之后
            expiry_date=local_date_to_utc_end("2027-12-31"),
        )

        assert len(conflicts) == 0

    @pytest.mark.asyncio
    async def test_check_conflict_single_and_multi_has_conflict(
        self, pricing_service, mock_db_session
    ):
        """测试检查冲突 - single_and_multi 模式下存在冲突"""
        existing_single = PricingRule(
            id=1,
            customer_id=100,
            device_type="L",
            layer_type="single",
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
        )

        # 第一次调用返回 single 冲突，第二次返回空（multi 无冲突）
        mock_result_single = MagicMock()
        mock_result_single.scalars.return_value.all.return_value = [existing_single]
        mock_result_multi = MagicMock()
        mock_result_multi.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_result_single, mock_result_multi]

        conflicts = await pricing_service.check_pricing_rule_conflict(
            customer_id=100,
            pricing_type="fixed",
            device_type="L",
            layer_type="single_and_multi",
            effective_date=local_date_to_utc_start("2026-06-01"),
            expiry_date=local_date_to_utc_end("2027-06-30"),
        )

        assert len(conflicts) == 1
        assert conflicts[0].id == 1

    @pytest.mark.asyncio
    async def test_check_conflict_single_and_multi_no_conflict(
        self, pricing_service, mock_db_session
    ):
        """测试检查冲突 - single_and_multi 模式下无冲突"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        conflicts = await pricing_service.check_pricing_rule_conflict(
            customer_id=100,
            pricing_type="fixed",
            device_type="L",
            layer_type="single_and_multi",
            effective_date=local_date_to_utc_start("2027-01-01"),
            expiry_date=local_date_to_utc_end("2027-12-31"),
        )

        assert len(conflicts) == 0

    @pytest.mark.asyncio
    async def test_check_conflict_package_has_conflict(self, pricing_service, mock_db_session):
        """测试检查冲突 - 包年结算存在冲突（忽略设备/楼层类型）"""
        existing_package = PricingRule(
            id=9,
            customer_id=100,
            device_type=None,
            layer_type=None,
            pricing_type="package",
            package_type="A",
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-12-31"),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_package]
        mock_db_session.execute.return_value = mock_result

        # 包年结算冲突检查：只按 customer_id + pricing_type='package' + 有效期判断，
        # 不传 device_type 和 layer_type
        conflicts = await pricing_service.check_pricing_rule_conflict(
            customer_id=100,
            pricing_type="package",
            effective_date=local_date_to_utc_start("2026-06-01"),
            expiry_date=local_date_to_utc_end("2027-06-30"),
        )

        assert len(conflicts) == 1
        assert conflicts[0].id == 9

    @pytest.mark.asyncio
    async def test_check_conflict_package_no_conflict(self, pricing_service, mock_db_session):
        """测试检查冲突 - 包年结算无冲突（时间不重叠）"""
        existing_package = PricingRule(
            id=10,
            customer_id=100,
            device_type=None,
            layer_type=None,
            pricing_type="package",
            package_type="B",
            effective_date=local_date_to_utc_start("2026-01-01"),
            expiry_date=local_date_to_utc_end("2026-06-30"),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_package]
        mock_db_session.execute.return_value = mock_result

        conflicts = await pricing_service.check_pricing_rule_conflict(
            customer_id=100,
            pricing_type="package",
            effective_date=local_date_to_utc_start("2027-01-01"),  # 在现有规则之后，无重叠
            expiry_date=local_date_to_utc_end("2027-12-31"),
        )

        assert len(conflicts) == 0


# ==================== Test PricingService - Create single_and_multi ====================


class TestPricingService_CreateSingleAndMulti:
    """创建单层+多层组合规则测试"""

    @pytest.mark.asyncio
    async def test_create_single_and_multi_success(self, pricing_service, mock_db_session):
        """测试创建 single_and_multi 规则 - 成功拆分为两条"""
        # Mock 无冲突
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        rule_data = {
            "customer_id": 100,
            "device_type": "L",
            "layer_type": "single_and_multi",
            "pricing_type": "fixed",
            "unit_price": Decimal("10.00"),
            "effective_date": local_date_to_utc_start("2026-01-01"),
            "expiry_date": local_date_to_utc_end("2026-12-31"),
            "created_by": 1,
        }

        result = await pricing_service.create_pricing_rule(rule_data)

        assert result is not None
        assert isinstance(result, PricingRule)
        assert result.layer_type == "multi"
        assert result.multi_floor_pricing_type == "unified"
        # 应该 commit 两次（single + multi）
        assert mock_db_session.commit.call_count == 2
        # 应该 add 两次
        assert mock_db_session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_create_single_and_multi_with_incremental_fields(
        self, pricing_service, mock_db_session
    ):
        """测试创建 multi + incremental 规则"""
        # Mock 无冲突
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        rule_data = {
            "customer_id": 100,
            "device_type": "L",
            "layer_type": "multi",
            "pricing_type": "fixed",
            "unit_price": Decimal("5.00"),
            "multi_floor_pricing_type": "incremental",
            "additional_floor_price": Decimal("6.00"),
            "effective_date": local_date_to_utc_start("2026-01-01"),
            "expiry_date": local_date_to_utc_end("2026-12-31"),
            "created_by": 1,
        }

        result = await pricing_service.create_pricing_rule(rule_data)

        assert result is not None
        assert result.layer_type == "multi"
        assert result.multi_floor_pricing_type == "incremental"
        assert result.additional_floor_price == Decimal("6.00")
        mock_db_session.commit.assert_called()


# ==================== Test InvoiceService - Calculate Items with Incremental ====================


class TestInvoiceService_CalculateItemsIncremental:
    """结算单明细计算测试 - 递增模式"""

    @pytest.fixture
    def invoice_service(self, mock_db_session):
        """创建 InvoiceService 实例"""
        from unittest.mock import MagicMock

        from app.repository import InvoiceRepository, PricingRepository

        mock_invoice_repo = MagicMock(spec=InvoiceRepository)
        mock_invoice_repo.db = mock_db_session
        mock_pricing_repo = MagicMock(spec=PricingRepository)
        mock_pricing_repo.db = mock_db_session
        from app.services.billing import InvoiceService

        return InvoiceService(
            invoice_repo=mock_invoice_repo,
            pricing_repo=mock_pricing_repo,
        )

    @pytest.mark.asyncio
    async def test_calculate_items_fixed_incremental(self, invoice_service, mock_db_session):
        """测试结算明细计算 - 递增模式

        3层房源1套，单价5，其他层单价6 → 5×1 + 6×2 = 17
        """

        # Mock 用量查询结果
        usage_row = MagicMock()
        usage_row.device_type = "L"
        usage_row.layer_type = "multi"
        usage_row.total_quantity = 1  # order_count
        usage_row.total_floor_count = 3

        usage_result = MagicMock()
        usage_result.all.return_value = [usage_row]

        # Mock 规则查询结果
        mock_rule = MagicMock(spec=PricingRule)
        mock_rule.id = 1
        mock_rule.device_type = "L"
        mock_rule.layer_type = "multi"
        mock_rule.pricing_type = "fixed"
        mock_rule.unit_price = Decimal("5")
        mock_rule.multi_floor_pricing_type = "incremental"
        mock_rule.additional_floor_price = Decimal("6")

        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_rule]

        # execute 第一次返回用量，第二次返回规则
        mock_db_session.execute.side_effect = [usage_result, rules_result]

        items, total_amount = await invoice_service.calculate_items_from_rules(
            customer_id=100,
            period_start=local_date_range_to_utc("2026-01-01", "2026-01-31")[0],
            period_end=local_date_range_to_utc("2026-01-01", "2026-01-31")[1],
        )

        assert len(items) == 1
        item = items[0]
        assert item["multi_floor_pricing_type"] == "incremental"
        assert item["unit_price"] == Decimal("5")
        assert item["additional_floor_price"] == Decimal("6")
        assert item["subtotal"] == Decimal("17")
        assert total_amount == Decimal("17")

    @pytest.mark.asyncio
    async def test_calculate_items_fixed_unified_multi(self, invoice_service, mock_db_session):
        """测试结算明细计算 - 多层统一模式

        统一模式：按订单数量 × 单价（不区分楼层）
        订单数 2，总楼层数 6，单价 10 → 2 × 10 = 20
        """
        usage_row = MagicMock()
        usage_row.device_type = "L"
        usage_row.layer_type = "multi"
        usage_row.total_quantity = 2
        usage_row.total_floor_count = 6

        usage_result = MagicMock()
        usage_result.all.return_value = [usage_row]

        mock_rule = MagicMock(spec=PricingRule)
        mock_rule.id = 1
        mock_rule.device_type = "L"
        mock_rule.layer_type = "multi"
        mock_rule.pricing_type = "fixed"
        mock_rule.unit_price = Decimal("10")
        mock_rule.multi_floor_pricing_type = "unified"
        mock_rule.additional_floor_price = None

        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_rule]

        mock_db_session.execute.side_effect = [usage_result, rules_result]

        items, total_amount = await invoice_service.calculate_items_from_rules(
            customer_id=100,
            period_start=local_date_range_to_utc("2026-01-01", "2026-01-31")[0],
            period_end=local_date_range_to_utc("2026-01-01", "2026-01-31")[1],
        )

        assert len(items) == 1
        assert items[0]["subtotal"] == Decimal("20")
        assert items[0]["quantity"] == Decimal("2")  # 按订单数
        assert total_amount == Decimal("20")

    @pytest.mark.asyncio
    async def test_calculate_items_package_rule(self, invoice_service, mock_db_session):
        """测试结算明细计算 - 限量包年规则（按用量计收 + 超量费用）

        base_fee=10000, limit_count=100, over_limit_unit_price=100
        total_quantity=5 (未超量)
        → usage_cost = 5 × (10000/100) = 5 × 100 = 500
        → over_limit_cost = 0
        → subtotal = 500
        """
        usage_row = MagicMock()
        usage_row.device_type = "X"
        usage_row.layer_type = "single"
        usage_row.total_quantity = 5
        usage_row.total_floor_count = 5

        usage_result = MagicMock()
        usage_result.all.return_value = [usage_row]

        mock_package = MagicMock(spec=PricingRule)
        mock_package.id = 9
        mock_package.device_type = None
        mock_package.layer_type = None
        mock_package.pricing_type = "package"
        mock_package.package_type = "A"
        mock_package.package_limits = {
            "base_fee": 10000,
            "is_unlimited": False,
            "limit_count": 100,
            "over_limit_unit_price": 100,
        }
        mock_package.unit_price = None

        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_package]

        mock_db_session.execute.side_effect = [usage_result, rules_result]

        items, total_amount = await invoice_service.calculate_items_from_rules(
            customer_id=100,
            period_start=local_date_range_to_utc("2026-01-01", "2026-01-31")[0],
            period_end=local_date_range_to_utc("2026-01-01", "2026-01-31")[1],
        )

        assert len(items) == 1
        assert items[0]["pricing_rule_id"] == 9
        assert items[0]["device_type"] is None
        assert items[0]["layer_type"] is None
        assert items[0]["subtotal"] == Decimal("500")  # 5 × (10000/100) = 500
        assert items[0]["package_type"] == "limited"
        assert items[0]["limit_count"] == 100
        assert items[0]["over_limit_quantity"] == 0
        assert total_amount == Decimal("500")

    @pytest.mark.asyncio
    async def test_calculate_items_package_rule_priority_over_fixed(
        self, invoice_service, mock_db_session
    ):
        """测试结算明细计算 - 包年规则优先于固定规则

        限量套餐：base_fee=5000, limit_count=50, over_limit_unit_price=100
        total_quantity=3 (未超量)
        → usage_cost = 3 × (5000/50) = 3 × 100 = 300
        → over_limit_cost = 0
        → subtotal = 300
        """
        usage_row = MagicMock()
        usage_row.device_type = "L"
        usage_row.layer_type = "single"
        usage_row.total_quantity = 3
        usage_row.total_floor_count = 3

        usage_result = MagicMock()
        usage_result.all.return_value = [usage_row]

        mock_fixed = MagicMock(spec=PricingRule)
        mock_fixed.id = 1
        mock_fixed.device_type = "L"
        mock_fixed.layer_type = "single"
        mock_fixed.pricing_type = "fixed"
        mock_fixed.unit_price = Decimal("10")

        mock_package = MagicMock(spec=PricingRule)
        mock_package.id = 9
        mock_package.device_type = None
        mock_package.layer_type = None
        mock_package.pricing_type = "package"
        mock_package.package_type = "A"
        mock_package.package_limits = {
            "base_fee": 5000,
            "is_unlimited": False,
            "limit_count": 50,
            "over_limit_unit_price": 100,
        }
        mock_package.unit_price = None

        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_fixed, mock_package]

        mock_db_session.execute.side_effect = [usage_result, rules_result]

        items, total_amount = await invoice_service.calculate_items_from_rules(
            customer_id=100,
            period_start=local_date_range_to_utc("2026-01-01", "2026-01-31")[0],
            period_end=local_date_range_to_utc("2026-01-01", "2026-01-31")[1],
        )

        # 只生成一条包年明细，固定规则不参与计算
        assert len(items) == 1
        assert items[0]["pricing_rule_id"] == 9
        assert total_amount == Decimal("300")  # 3 × (5000/50) = 300

    @pytest.mark.asyncio
    async def test_calculate_items_package_rule_over_limit(self, invoice_service, mock_db_session):
        """测试结算明细计算 - 限量套餐超额场景（双重计费修复验证）

        base_fee=10000, limit_count=100, over_limit_unit_price=100
        total_quantity=120 (超出 20)
        → in_package_quantity = min(120, 100) = 100
        → usage_cost = 100 × (10000/100) = 100 × 100 = 10000
        → over_limit_quantity = 120 - 100 = 20
        → over_limit_cost = 20 × 100 = 2000
        → subtotal = 10000 + 2000 = 12000

        修复前（bug）：usage_cost = 120 × 100 = 12000，subtotal = 12000 + 2000 = 14000（多收 2000）
        """
        usage_row = MagicMock()
        usage_row.device_type = "X"
        usage_row.layer_type = "single"
        usage_row.total_quantity = 120
        usage_row.total_floor_count = 120

        usage_result = MagicMock()
        usage_result.all.return_value = [usage_row]

        mock_package = MagicMock(spec=PricingRule)
        mock_package.id = 9
        mock_package.device_type = None
        mock_package.layer_type = None
        mock_package.pricing_type = "package"
        mock_package.package_type = "A"
        mock_package.package_limits = {
            "base_fee": 10000,
            "is_unlimited": False,
            "limit_count": 100,
            "over_limit_unit_price": 100,
        }
        mock_package.unit_price = None

        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_package]

        mock_db_session.execute.side_effect = [usage_result, rules_result]

        items, total_amount = await invoice_service.calculate_items_from_rules(
            customer_id=100,
            period_start=local_date_range_to_utc("2026-01-01", "2026-01-31")[0],
            period_end=local_date_range_to_utc("2026-01-01", "2026-01-31")[1],
        )

        assert len(items) == 1
        item = items[0]
        assert item["pricing_rule_id"] == 9
        assert item["package_type"] == "limited"
        assert item["in_package_quantity"] == 100
        assert item["over_limit_quantity"] == 20
        assert item["usage_cost"] == Decimal("10000")
        assert item["over_limit_cost"] == Decimal("2000")
        assert item["subtotal"] == Decimal("12000")
        assert total_amount == Decimal("12000")

    @pytest.mark.asyncio
    async def test_calculate_items_package_null_over_limit_price(
        self, invoice_service, mock_db_session
    ):
        """测试结算明细计算 - 超额单价为 NULL 时自动按 base_fee/limit_count 计算

        base_fee=10000, limit_count=100, over_limit_unit_price=None (自动)
        total_quantity=120 (超出 20)
        → over_limit_unit_price = 10000/100 = 100 (自动计算)
        → in_package_quantity = min(120, 100) = 100
        → usage_cost = 100 × 100 = 10000
        → over_limit_cost = 20 × 100 = 2000
        → subtotal = 10000 + 2000 = 12000
        """
        usage_row = MagicMock()
        usage_row.device_type = "X"
        usage_row.layer_type = "single"
        usage_row.total_quantity = 120
        usage_row.total_floor_count = 120

        usage_result = MagicMock()
        usage_result.all.return_value = [usage_row]

        mock_package = MagicMock(spec=PricingRule)
        mock_package.id = 9
        mock_package.device_type = None
        mock_package.layer_type = None
        mock_package.pricing_type = "package"
        mock_package.package_type = "A"
        mock_package.package_limits = {
            "base_fee": 10000,
            "is_unlimited": False,
            "limit_count": 100,
            "over_limit_unit_price": None,  # NULL = 自动计算
        }
        mock_package.unit_price = None

        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [mock_package]

        mock_db_session.execute.side_effect = [usage_result, rules_result]

        items, total_amount = await invoice_service.calculate_items_from_rules(
            customer_id=100,
            period_start=local_date_range_to_utc("2026-01-01", "2026-01-31")[0],
            period_end=local_date_range_to_utc("2026-01-01", "2026-01-31")[1],
        )

        assert len(items) == 1
        item = items[0]
        assert item["over_limit_unit_price"] == Decimal("100")  # 自动计算 = base_fee/limit_count
        assert item["over_limit_cost"] == Decimal("2000")
        assert item["subtotal"] == Decimal("12000")
        assert total_amount == Decimal("12000")

    @pytest.mark.asyncio
    async def test_generate_invoice_uses_subtotal(self, invoice_service, mock_db_session):
        """测试生成结算单 - 使用 subtotal 字段计算总金额"""
        items = [
            {
                "device_type": "L",
                "layer_type": "multi",
                "quantity": 3,
                "unit_price": Decimal("5"),
                "additional_floor_price": Decimal("6"),
                "subtotal": Decimal("17"),  # 递增模式的 subtotal
                "pricing_rule_id": 1,
            }
        ]

        result = await invoice_service.generate_invoice(
            customer_id=100,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            items=items,
            created_by=1,
        )

        assert result is not None
        assert result.total_amount == Decimal("17")  # 使用 subtotal 而非 quantity × unit_price


# ==================== Test InvoiceService - Deduction Failure Downgrade ====================


class TestInvoiceService_DeductionFailureDowngrade:
    """扣款失败降级测试

    consume 在死锁重试耗尽时抛 OperationalError（其 docstring 与 reraise=True 定义的
    契约）。调用点必须把它降级为 Tuple[bool, str] 业务错误码——否则数据库异常会穿透
    业务方法变成 500，而这些方法声明的返回类型是错误码元组。
    """

    @pytest.fixture
    def invoice_service(self, mock_db_session):
        """创建 InvoiceService 实例"""
        from app.repository import InvoiceRepository, PricingRepository
        from app.services.billing import InvoiceService

        mock_invoice_repo = MagicMock(spec=InvoiceRepository)
        mock_invoice_repo.db = mock_db_session
        mock_pricing_repo = MagicMock(spec=PricingRepository)
        mock_pricing_repo.db = mock_db_session
        return InvoiceService(invoice_repo=mock_invoice_repo, pricing_repo=mock_pricing_repo)

    @staticmethod
    def _invoice(status: str) -> Invoice:
        return Invoice(
            id=1,
            customer_id=100,
            status=status,
            total_amount=Decimal("1000.00"),
            discount_amount=Decimal("0.00"),
        )

    @staticmethod
    def _exhausted_retry() -> OperationalError:
        """构造重试耗尽时 consume 抛出的异常"""
        return OperationalError("SELECT ... FOR UPDATE", {}, Exception("deadlock detected"))

    @pytest.mark.asyncio
    async def test_confirm_invoice_downgrades_and_keeps_customer_confirmed(
        self, invoice_service, mock_db_session
    ):
        """客户确认自动扣款：重试耗尽时返回业务错误码，状态停在 customer_confirmed 可重试"""
        invoice = self._invoice("pending_customer")

        with (
            patch.object(InvoiceService, "get_invoice_by_id", AsyncMock(return_value=invoice)),
            patch.object(BalanceService, "consume", AsyncMock(side_effect=self._exhausted_retry())),
        ):
            success, message = await invoice_service.confirm_invoice(invoice_id=1, user_id=7)

        assert success is False
        assert message == "客户确认成功，但扣款失败：数据库繁忙，请稍后重试"
        # 未被推进为 completed，retry_deduction 仍可执行
        assert invoice.status == "customer_confirmed"

    @pytest.mark.asyncio
    async def test_retry_deduction_downgrades_without_duplicated_prefix(
        self, invoice_service, mock_db_session
    ):
        """手动重试扣款：降级消息经前缀剥离后不出现重复的「扣款失败：」"""
        invoice = self._invoice("customer_confirmed")

        with (
            patch.object(InvoiceService, "get_invoice_by_id", AsyncMock(return_value=invoice)),
            patch.object(BalanceService, "consume", AsyncMock(side_effect=self._exhausted_retry())),
        ):
            success, message = await invoice_service.retry_deduction(invoice_id=1, user_id=7)

        assert success is False
        assert message == "扣款失败：数据库繁忙，请稍后重试"
        assert invoice.status == "customer_confirmed"

    @pytest.mark.asyncio
    async def test_complete_invoice_downgrades_and_keeps_paid(
        self, invoice_service, mock_db_session
    ):
        """完成结算：重试耗尽时返回业务错误码，状态停在 paid 可再次完成"""
        invoice = self._invoice("paid")

        with (
            patch.object(InvoiceService, "get_invoice_by_id", AsyncMock(return_value=invoice)),
            patch.object(BalanceService, "consume", AsyncMock(side_effect=self._exhausted_retry())),
        ):
            success, message = await invoice_service.complete_invoice(invoice_id=1, user_id=7)

        assert success is False
        assert message == "扣款失败：数据库繁忙，请稍后重试"
        assert invoice.status == "paid"  # 未被推进为 completed
