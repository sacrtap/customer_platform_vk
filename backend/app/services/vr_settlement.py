"""VR编辑费用结算服务"""

import logging
import random
import string
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.customers import Customer
from ..models.vr_settlement import VrSettlement, VrSettlementDiscountHistory
from ..repository import BalanceRepository
from ..services.billing import _DB_BUSY_MESSAGE, BalanceService
from ..utils.timezone import cst_now, cst_today

logger = logging.getLogger(__name__)

# 减免允许提交/修改的状态（销售主管审批节点起锁定，与 InvoiceService.apply_discount 对齐）
_DISCOUNT_EDITABLE_STATUSES = ("draft", "pending_cs_supervisor", "pending_sales")

# 可取消的状态（非终态；customer_confirmed/completed/cancelled 不可取消）
_CANCELLABLE_STATUSES = (
    "draft",
    "pending_cs_supervisor",
    "pending_sales",
    "pending_sales_supervisor",
    "pending_customer",
)

# 列表排序字段映射（前端字段 -> SQLAlchemy 列表达式）
_SORT_FIELD_MAP = {
    "settlement_no": VrSettlement.settlement_no,
    "total_amount": VrSettlement.total_amount,
    "created_at": VrSettlement.created_at,
}


class VrSettlementService:
    """VR编辑费用结算单服务类

    状态机：
        draft → pending_cs_supervisor → pending_sales → pending_sales_supervisor
            → pending_customer → customer_confirmed → completed
        任意非终态可 → cancelled

    扣款完全复用 BalanceService.consume（行级锁 + 重试 + 先赠后实），
    扣减对象为结算客户自身余额（不使用 Invoice 的结算账户代扣机制）。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_settlement(
        self,
        customer_id: int,
        period_start: datetime,
        period_end: datetime,
        total_amount: Decimal,
        detail_file_path: Optional[str],
        detail_file_name: Optional[str],
        created_by: int,
    ) -> VrSettlement:
        """手动创建 VR 结算单（草稿）

        生成 settlement_no = VR-{CST日期}-{客户ID}-{4位随机码}
        （日期按 CST 业务日，与 Invoice 编号规则一致）。
        """
        random_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        settlement_no = f"VR-{cst_today().strftime('%Y%m%d')}-{customer_id}-{random_code}"

        settlement = VrSettlement(
            settlement_no=settlement_no,
            customer_id=customer_id,
            period_start=period_start,
            period_end=period_end,
            total_amount=total_amount,
            discount_amount=Decimal(0),
            status="draft",
            is_auto_generated=False,
            detail_file_path=detail_file_path,
            detail_file_name=detail_file_name,
            created_by=created_by,
        )
        self.db.add(settlement)
        await self.db.commit()
        await self.db.refresh(settlement)

        return settlement

    async def get_settlements(
        self,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        customer_id: Optional[int] = None,
        mine_user_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[VrSettlement], int]:
        """获取 VR 结算单列表（支持服务端排序）

        mine_user_id: 数据可见性约束（服务端强制）。非 None 时仅返回该用户
        （作为运营经理或销售经理）负责客户的结算单。
        """
        stmt = (
            select(VrSettlement)
            .options(selectinload(VrSettlement.customer))
            .join(Customer, VrSettlement.customer_id == Customer.id)
            .where(VrSettlement.deleted_at.is_(None), Customer.deleted_at.is_(None))
        )

        if customer_id:
            stmt = stmt.where(VrSettlement.customer_id == customer_id)
        if keyword:
            stmt = stmt.where(
                or_(
                    Customer.name.ilike(f"%{keyword}%"),
                    VrSettlement.settlement_no.ilike(f"%{keyword}%"),
                )
            )
        if status:
            stmt = stmt.where(VrSettlement.status == status)
        if mine_user_id:
            stmt = stmt.where(
                or_(
                    Customer.manager_id == mine_user_id,
                    Customer.sales_manager_id == mine_user_id,
                )
            )

        # 总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar()

        # 排序：非法 sort_by 静默回退 created_at（与 InvoiceService.get_invoices 一致）
        sort_field = _SORT_FIELD_MAP.get(sort_by, VrSettlement.created_at)
        if sort_order == "asc":
            stmt = stmt.order_by(sort_field.asc(), VrSettlement.id.asc())
        else:
            stmt = stmt.order_by(sort_field.desc(), VrSettlement.id.asc())

        # 分页
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        settlements = result.scalars().unique().all()

        return list(settlements), total  # pyright: ignore[reportReturnType]

    async def get_settlement_by_id(self, settlement_id: int) -> Optional[VrSettlement]:
        """获取 VR 结算单详情"""
        result = await self.db.execute(
            select(VrSettlement)
            .options(selectinload(VrSettlement.customer))
            .where(
                VrSettlement.id == settlement_id,
                VrSettlement.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_discount_histories(self, settlement_id: int) -> List[VrSettlementDiscountHistory]:
        """获取减免修改历史（按时间倒序，最新在上）"""
        result = await self.db.execute(
            select(VrSettlementDiscountHistory)
            .where(
                VrSettlementDiscountHistory.settlement_id == settlement_id,
                VrSettlementDiscountHistory.deleted_at.is_(None),
            )
            .order_by(VrSettlementDiscountHistory.applied_at.desc())
        )
        return list(result.scalars().all())

    async def _get_customer(self, customer_id: int) -> Optional[Customer]:
        """查询客户信息（内部方法）"""
        result = await self.db.execute(
            select(Customer).where(Customer.id == customer_id, Customer.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def submit_settlement(self, settlement_id: int, user_id: int) -> Tuple[bool, str]:
        """提交审批：draft → pending_cs_supervisor

        校验客户必须已指定销售经理（后续销售审批节点需要）。
        """
        settlement = await self.get_settlement_by_id(settlement_id)

        if not settlement:
            return False, "结算单不存在"

        if settlement.status != "draft":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态（{settlement.status}）不允许该操作"

        customer = await self._get_customer(settlement.customer_id)  # pyright: ignore[reportArgumentType]
        if not customer:
            return False, "客户不存在"

        if not customer.sales_manager_id:  # pyright: ignore[reportGeneralTypeIssues]
            return False, "该客户未指定销售经理，无法提交审批"

        settlement.status = "pending_cs_supervisor"  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()

        return True, "提交成功"

    async def confirm_cs_supervisor(self, settlement_id: int, user_id: int) -> Tuple[bool, str]:
        """客服主管审批（第一步）：pending_cs_supervisor → pending_sales"""
        settlement = await self.get_settlement_by_id(settlement_id)

        if not settlement:
            return False, "结算单不存在"

        if settlement.status != "pending_cs_supervisor":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态（{settlement.status}）不允许该操作"

        settlement.cs_supervisor_confirmed_by = user_id  # pyright: ignore[reportAttributeAccessIssue]
        settlement.cs_supervisor_confirmed_at = cst_now().strftime(  # pyright: ignore[reportAttributeAccessIssue]
            "%Y-%m-%d %H:%M:%S"
        )
        settlement.status = "pending_sales"  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()

        return True, "客服主管审批成功"

    async def confirm_sales(self, settlement_id: int, user_id: int) -> Tuple[bool, str]:
        """销售审批（第二步）：pending_sales → pending_sales_supervisor

        身份校验：操作人必须为该客户指定的销售（customer.sales_manager_id）。
        """
        settlement = await self.get_settlement_by_id(settlement_id)

        if not settlement:
            return False, "结算单不存在"

        if settlement.status != "pending_sales":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态（{settlement.status}）不允许该操作"

        customer = await self._get_customer(settlement.customer_id)  # pyright: ignore[reportArgumentType]
        if not customer:
            return False, "客户不存在"

        if customer.sales_manager_id != user_id:  # pyright: ignore[reportGeneralTypeIssues]
            return False, "您不是该客户指定的销售，无权确认"

        settlement.sales_confirmed_by = user_id  # pyright: ignore[reportAttributeAccessIssue]
        settlement.sales_confirmed_at = cst_now().strftime("%Y-%m-%d %H:%M:%S")  # pyright: ignore[reportAttributeAccessIssue]
        settlement.status = "pending_sales_supervisor"  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()

        return True, "销售审批成功"

    async def confirm_sales_supervisor(
        self, settlement_id: int, user_id: int, comment: Optional[str] = None
    ) -> Tuple[bool, str]:
        """销售主管审批通过（第三步，含减免一并审批）

        pending_sales_supervisor → pending_customer
        若 discount_amount ≠ 0：一并写减免审批人/时间/意见（减免生效）。
        """
        settlement = await self.get_settlement_by_id(settlement_id)

        if not settlement:
            return False, "结算单不存在"

        if settlement.status != "pending_sales_supervisor":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态（{settlement.status}）不允许该操作"

        settlement.sales_supervisor_confirmed_by = user_id  # pyright: ignore[reportAttributeAccessIssue]
        settlement.sales_supervisor_confirmed_at = cst_now().strftime(  # pyright: ignore[reportAttributeAccessIssue]
            "%Y-%m-%d %H:%M:%S"
        )

        # 减免一并审批：通过=减免生效（记录审批人/时间/意见）
        if settlement.discount_amount and settlement.discount_amount != 0:  # pyright: ignore[reportGeneralTypeIssues]
            settlement.discount_approver_id = user_id  # pyright: ignore[reportAttributeAccessIssue]
            settlement.discount_approved_at = cst_now().strftime("%Y-%m-%d %H:%M:%S")  # pyright: ignore[reportAttributeAccessIssue]
            settlement.discount_approval_comment = comment  # pyright: ignore[reportAttributeAccessIssue]

        settlement.status = "pending_customer"  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()

        return True, "销售主管审批通过"

    async def reject_sales_supervisor(
        self, settlement_id: int, user_id: int, comment: str
    ) -> Tuple[bool, str]:
        """销售主管审批驳回：pending_sales_supervisor → pending_sales

        整单退回销售节点（销售重新确认后可再次提交审批）；
        减免信息保留，待重新一并审批。
        """
        settlement = await self.get_settlement_by_id(settlement_id)

        if not settlement:
            return False, "结算单不存在"

        if settlement.status != "pending_sales_supervisor":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态（{settlement.status}）不允许该操作"

        settlement.sales_supervisor_confirmed_by = user_id  # pyright: ignore[reportAttributeAccessIssue]
        settlement.sales_supervisor_confirmed_at = cst_now().strftime(  # pyright: ignore[reportAttributeAccessIssue]
            "%Y-%m-%d %H:%M:%S"
        )
        settlement.discount_approval_comment = comment  # pyright: ignore[reportAttributeAccessIssue]
        settlement.status = "pending_sales"  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()

        return True, "已驳回，退回销售审批"

    async def apply_discount(
        self,
        settlement_id: int,
        discount_amount: Decimal,
        discount_reason: str,
        discount_attachment: Optional[str],
        user_id: int,
    ) -> Tuple[bool, str]:
        """提交/修改减免

        允许状态：draft / pending_cs_supervisor / pending_sales
        （销售主管审批节点起锁定，防止绕过减免审批）。
        每次修改插入一条 VrSettlementDiscountHistory。
        """
        settlement = await self.get_settlement_by_id(settlement_id)

        if not settlement:
            return False, "结算单不存在"

        if settlement.status not in _DISCOUNT_EDITABLE_STATUSES:  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态（{settlement.status}）不允许该操作"

        if discount_amount == 0:  # pyright: ignore[reportGeneralTypeIssues]
            return False, "减免金额不能为 0"

        # 减免金额允许为负值（加价），不校验上限
        now_str = cst_now().strftime("%Y-%m-%d %H:%M:%S")

        settlement.discount_amount = discount_amount  # pyright: ignore[reportAttributeAccessIssue]
        settlement.discount_reason = discount_reason  # pyright: ignore[reportAttributeAccessIssue]
        settlement.discount_attachment = discount_attachment  # pyright: ignore[reportAttributeAccessIssue]
        settlement.discount_applied_at = now_str  # pyright: ignore[reportAttributeAccessIssue]
        # 重新提交减免时清空上一轮审批结果（若有），避免展示过期审批意见
        settlement.discount_approver_id = None  # pyright: ignore[reportAttributeAccessIssue]
        settlement.discount_approved_at = None  # pyright: ignore[reportAttributeAccessIssue]
        settlement.discount_approval_comment = None  # pyright: ignore[reportAttributeAccessIssue]

        # 写入历史记录
        history = VrSettlementDiscountHistory(
            settlement_id=settlement_id,
            discount_amount=discount_amount,
            discount_reason=discount_reason,
            discount_attachment=discount_attachment,
            applied_at=now_str,
            applied_by=user_id,
        )
        self.db.add(history)

        await self.db.commit()

        return True, "减免应用成功"

    async def confirm_customer(self, settlement_id: int, user_id: int) -> Tuple[bool, str]:
        """客户确认：pending_customer → customer_confirmed → 自动扣款 → completed

        先落库「客户已确认」再尝试扣款：扣款失败时该状态保留，
        可由 retry_deduction 重试（与 InvoiceService.confirm_invoice 一致）。
        """
        settlement = await self.get_settlement_by_id(settlement_id)

        if not settlement:
            return False, "结算单不存在"

        if settlement.status != "pending_customer":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态（{settlement.status}）不允许该操作"

        settlement.status = "customer_confirmed"  # pyright: ignore[reportAttributeAccessIssue]
        settlement.customer_confirmed_at = cst_now().strftime("%Y-%m-%d %H:%M:%S")  # pyright: ignore[reportAttributeAccessIssue]
        settlement.customer_confirmed_by = user_id  # pyright: ignore[reportAttributeAccessIssue]
        # 先落库「客户已确认」再尝试扣款：扣款失败时该状态保留，可由 retry_deduction 重试
        await self.db.commit()

        # 自动执行扣款
        return await self._execute_deduction(settlement, user_id=user_id)

    async def retry_deduction(self, settlement_id: int, user_id: int) -> Tuple[bool, str]:
        """重试扣款（扣款失败后手动重试）

        仅当状态为 customer_confirmed 时可执行。
        """
        settlement = await self.get_settlement_by_id(settlement_id)

        if not settlement:
            return False, "结算单不存在"

        if settlement.status != "customer_confirmed":  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态（{settlement.status}）不允许该操作"

        success, message = await self._execute_deduction(settlement, user_id=user_id)

        if success:
            return True, "重试扣款成功"

        # _execute_deduction 返回的 message 带有 "客户确认成功，但扣款失败：" 前缀，
        # 对重试场景需要去掉该前缀（与 InvoiceService.retry_deduction 一致）
        clean_msg = message.replace("客户确认成功，但扣款失败：", "")
        return False, f"扣款失败：{clean_msg}"

    async def _execute_deduction(self, settlement: VrSettlement, user_id: int) -> Tuple[bool, str]:
        """执行余额扣款（内部方法）

        customer_confirmed → completed（扣款成功）；失败时保持 customer_confirmed。
        扣减对象为结算客户自身余额（customer_id），不使用结算账户代扣。
        """
        # 事务边界由 consume 自行收敛（见其实现），此处无需预先提交
        final_amount = settlement.total_amount - (settlement.discount_amount or 0)
        balance_service = BalanceService(BalanceRepository(self.db))
        try:
            success, message = await balance_service.consume(
                customer_id=settlement.customer_id,  # pyright: ignore[reportArgumentType]
                amount=final_amount,  # pyright: ignore[reportArgumentType]
                vr_settlement_id=settlement.id,  # pyright: ignore[reportArgumentType]
            )
        except OperationalError:
            # 重试耗尽：consume 已记录诊断日志。此处降级为业务错误码，保持本方法的
            # Tuple[bool, str] 契约（不让数据库异常穿透成 500）；结算单状态仍为
            # customer_confirmed，可由 retry_deduction 再次尝试
            return False, f"客户确认成功，但扣款失败：{_DB_BUSY_MESSAGE}"

        if not success:
            # 扣款失败，保持 customer_confirmed 状态
            return False, f"客户确认成功，但扣款失败：{message}"

        settlement.status = "completed"  # pyright: ignore[reportAttributeAccessIssue]
        settlement.completed_at = cst_now().strftime("%Y-%m-%d %H:%M:%S")  # pyright: ignore[reportAttributeAccessIssue]
        settlement.completed_by = user_id  # pyright: ignore[reportAttributeAccessIssue]
        await self.db.commit()

        return True, "客户确认成功，已自动完成扣款"

    async def cancel_settlement(self, settlement_id: int, user_id: int) -> Tuple[bool, str]:
        """取消结算单（非终态可取消）"""
        settlement = await self.get_settlement_by_id(settlement_id)

        if not settlement:
            return False, "结算单不存在"

        if settlement.status not in _CANCELLABLE_STATUSES:  # pyright: ignore[reportGeneralTypeIssues]
            return False, f"当前状态（{settlement.status}）不允许该操作"

        settlement.status = "cancelled"  # pyright: ignore[reportAttributeAccessIssue]
        settlement.cancelled_at = cst_now().strftime("%Y-%m-%d %H:%M:%S")  # pyright: ignore[reportAttributeAccessIssue]
        settlement.cancelled_by = user_id  # pyright: ignore[reportAttributeAccessIssue]

        await self.db.commit()

        return True, "取消成功"

    async def delete_settlement(self, settlement_id: int) -> bool:
        """删除结算单（软删除）"""
        settlement = await self.get_settlement_by_id(settlement_id)

        if not settlement:
            return False

        # deleted_at 是 naive DateTime 列（timestamp without time zone）：
        # func.now() 在引擎锁定的 CST 会话时区下写墙钟，与 InvoiceService.delete_invoice
        # 一致；直接写 cst_now()（aware datetime）会被 asyncpg 以
        # "can't subtract offset-naive and offset-aware datetimes" 拒绝。
        settlement.deleted_at = func.now()  # pyright: ignore[reportAttributeAccessIssue]
        await self.db.commit()

        return True
