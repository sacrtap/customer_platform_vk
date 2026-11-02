"""VR编辑费用结算模型"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import DECIMAL, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class VrSettlementStatus(str, Enum):
    """VR结算单状态枚举

    draft → pending_cs_supervisor → pending_sales → pending_sales_supervisor
        → pending_customer → customer_confirmed → completed

    任意非终态均可 → cancelled
    """

    DRAFT = "draft"  # 草稿（待提交）
    PENDING_CS_SUPERVISOR = "pending_cs_supervisor"  # 待客服主管审批
    PENDING_SALES = "pending_sales"  # 待销售审批
    PENDING_SALES_SUPERVISOR = "pending_sales_supervisor"  # 待销售主管审批
    PENDING_CUSTOMER = "pending_customer"  # 待客户确认
    CUSTOMER_CONFIRMED = "customer_confirmed"  # 客户已确认（扣款失败可重试）
    COMPLETED = "completed"  # 已完成（扣款成功）
    CANCELLED = "cancelled"  # 已取消


class VrSettlement(BaseModel):
    """VR编辑费用结算单表"""

    __tablename__ = "vr_settlements"

    settlement_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("customers.id"), index=True)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    discount_amount: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 2), default=0)
    discount_reason: Mapped[str | None] = mapped_column(Text)
    discount_attachment: Mapped[str | None] = mapped_column(String(255))
    # final_amount = total_amount - discount_amount（计算字段，不落库）
    status: Mapped[str | None] = mapped_column(String(30), default="draft", index=True)
    # 减免提交/审批（减免审批由销售主管在审批节点一并完成）
    discount_applied_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discount_approver_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    discount_approved_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discount_approval_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 客服主管审批
    cs_supervisor_confirmed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    cs_supervisor_confirmed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 销售审批（客户指定销售本人）
    sales_confirmed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    sales_confirmed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 销售主管审批（含减免一并审批）
    sales_supervisor_confirmed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    sales_supervisor_confirmed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 客户确认
    customer_confirmed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_confirmed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    # 完成结算（扣款成功）
    completed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    # 取消
    cancelled_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cancelled_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    # 结算明细文件（创建时用户上传，存 /files/upload 返回路径）
    detail_file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 创建方式：手动创建=False；自动创建（待开发）上线后为 True
    is_auto_generated: Mapped[bool | None] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    customer = relationship("Customer", foreign_keys=[customer_id], lazy="selectin")

    __table_args__ = (
        Index("idx_vr_settlement_customer_period", "customer_id", "period_start", "period_end"),
        Index("idx_vr_settlement_status_period", "status", "period_start"),
    )


class VrSettlementDiscountHistory(BaseModel):
    """VR结算单减免修改历史表（每次提交/修改减免插一条，照抄 InvoiceDiscountHistory）"""

    __tablename__ = "vr_settlement_discount_histories"

    settlement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vr_settlements.id", ondelete="CASCADE"), index=True, nullable=False
    )
    discount_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    discount_reason: Mapped[str | None] = mapped_column(Text)
    discount_attachment: Mapped[str | None] = mapped_column(String(255))
    applied_at: Mapped[str] = mapped_column(String(50), nullable=False)
    applied_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (Index("idx_vr_discount_history_settlement", "settlement_id", "applied_at"),)
