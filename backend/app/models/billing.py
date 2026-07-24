"""结算与余额模型"""

from enum import Enum

from sqlalchemy import (
    DECIMAL,
    JSON,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import BaseModel


class InvoiceStatus(str, Enum):
    """结算单状态枚举

    新流程（多角色协作）：
        draft → pending_ops → pending_sales → pending_customer → customer_confirmed → completed

    旧流程（兼容历史数据）：
        draft → pending_customer → customer_confirmed → paid → completed

    任意非 completed 状态均可 → cancelled
    """

    DRAFT = "draft"  # 草稿（生成）
    PENDING_OPS = "pending_ops"  # 待运营经理确认
    PENDING_SALES = "pending_sales"  # 待销售经理确认
    PENDING_CUSTOMER = "pending_customer"  # 待客户确认（线下）
    CUSTOMER_CONFIRMED = "customer_confirmed"  # 客户已确认（自动扣款中/扣款失败可重试）
    PAID = "paid"  # 已付款（旧流程兼容）
    COMPLETED = "completed"  # 已完成（扣款成功）
    CANCELLED = "cancelled"  # 已取消


class CustomerBalance(BaseModel):
    """客户余额表"""

    __tablename__ = "customer_balances"

    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), unique=True)
    total_amount = Column(DECIMAL(12, 2), default=0)
    real_amount = Column(DECIMAL(12, 2), default=0)
    bonus_amount = Column(DECIMAL(12, 2), default=0)
    used_total = Column(DECIMAL(12, 2), default=0)
    used_real = Column(DECIMAL(12, 2), default=0)
    used_bonus = Column(DECIMAL(12, 2), default=0)

    # 关联
    customer = relationship("Customer", back_populates="balance")

    def __repr__(self):
        return f"<CustomerBalance {self.customer_id}>"


class RechargeRecord(BaseModel):
    """充值记录表"""

    __tablename__ = "recharge_records"

    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    real_amount = Column(DECIMAL(12, 2), nullable=False)
    bonus_amount = Column(DECIMAL(12, 2), default=0)
    # total_amount 通过计算字段生成
    operator_id = Column(Integer, ForeignKey("users.id"))
    payment_proof = Column(String(255))
    remark = Column(Text)


class PricingRule(BaseModel):
    """计费规则表"""

    __tablename__ = "pricing_rules"

    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    device_type = Column(String(20), nullable=False)  # X/N/L
    layer_type = Column(String(20))  # single/multi
    pricing_type = Column(String(20), nullable=False)  # fixed/tier/package
    unit_price = Column(DECIMAL(10, 2))
    tiers = Column(JSON)  # 阶梯配置
    package_type = Column(String(20))  # A/B/C/D
    package_limits = Column(JSON)
    effective_date = Column(Date, nullable=False, index=True)
    expiry_date = Column(Date)
    created_by = Column(Integer, ForeignKey("users.id"))

    # 关联
    customer = relationship("Customer", lazy="selectin")
    daily_consumptions = relationship("DailyConsumption", back_populates="pricing_rule")


class Invoice(BaseModel):
    """结算单表"""

    __tablename__ = "invoices"

    invoice_no = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    total_amount = Column(DECIMAL(12, 2), nullable=False)
    discount_amount = Column(DECIMAL(12, 2), default=0)
    discount_reason = Column(Text)
    discount_attachment = Column(String(255))
    # final_amount = total_amount - discount_amount
    status = Column(
        String(20), default="draft", index=True
    )  # draft/pending_ops/pending_sales/pending_customer/customer_confirmed/paid/completed/cancelled
    approver_id = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(String(50))
    discount_applied_at = Column(String(50))  # 折扣申请时间
    customer_confirmed_at = Column(String(50))
    customer_confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 客户确认操作人
    payment_proof = Column(String(255))
    paid_at = Column(String(50))
    completed_at = Column(String(50))
    completed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 完成结算操作人
    cancelled_at = Column(String(50))  # 取消时间
    cancelled_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 取消操作人
    is_auto_generated = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))

    # 多角色协作确认追踪
    ops_confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 运营经理确认人
    ops_confirmed_at = Column(String(50), nullable=True)  # 运营经理确认时间
    sales_confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 销售经理确认人
    sales_confirmed_at = Column(String(50), nullable=True)  # 销售经理确认时间

    # 关联
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    customer = relationship("Customer")

    __table_args__ = (
        Index("idx_invoice_customer_period", "customer_id", "period_start", "period_end"),
        Index("idx_invoice_status_period", "status", "period_start"),
    )


class InvoiceItem(BaseModel):
    """结算单明细表"""

    __tablename__ = "invoice_items"

    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    device_type = Column(String(20), nullable=False)
    layer_type = Column(String(20))  # single/multi
    quantity = Column(DECIMAL(10, 2), nullable=False)
    unit_price = Column(DECIMAL(10, 2), nullable=False)
    # subtotal = quantity * unit_price
    pricing_rule_id = Column(Integer, ForeignKey("pricing_rules.id"))

    # 关联
    invoice = relationship("Invoice", back_populates="items")


class ConsumptionRecord(BaseModel):
    """消费流水表"""

    __tablename__ = "consumption_records"

    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), index=True)
    amount = Column(DECIMAL(12, 2), nullable=False)
    bonus_used = Column(DECIMAL(12, 2), default=0)
    real_used = Column(DECIMAL(12, 2), default=0)
    balance_after = Column(DECIMAL(12, 2))


class SyncTaskLog(BaseModel):
    """同步任务日志表"""

    __tablename__ = "sync_task_logs"

    task_name = Column(String(100), nullable=False, index=True, comment="任务名称")
    status = Column(String(20), nullable=False, comment="任务状态")  # success/partial/failed

    # 统计数据
    total_count = Column(Integer, default=0, comment="总处理数量")
    success_count = Column(Integer, default=0, comment="成功数量")
    failed_count = Column(Integer, default=0, comment="失败数量")
    skipped_count = Column(Integer, default=0, comment="跳过数量")

    # 执行时间
    executed_at = Column(String(50), comment="执行时间")
    duration_seconds = Column(Integer, nullable=True, comment="执行耗时 (秒)")

    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误信息")

    # 消费同步审计字段
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sync_tasks.id"),
        nullable=True,
        comment="关联任务ID",
    )
    operator_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        comment="操作人",
    )
    start_date = Column(Date, nullable=True, comment="同步开始日期")
    end_date = Column(Date, nullable=True, comment="同步结束日期")
    sync_mode = Column(
        String(20),
        nullable=True,
        comment="同步模式: skip_existing/force_overwrite",
    )


class PackagePlan(BaseModel):
    """包年套餐表

    管理包年结算的套餐明细，支持"限量"和"不限量"两种模式。
    与 PricingRule.package_type 通过 package_type 字段关联。
    """

    __tablename__ = "package_plans"

    name = Column(String(100), nullable=False, comment="套餐名称")  # 如 "A 套餐"
    package_type = Column(
        String(20), nullable=False, unique=True, index=True, comment="套餐类型标识"
    )  # 如 A/B/C/D
    device_type = Column(String(20), nullable=True, comment="设备类型 (X/N/L)，为空表示通用")
    layer_type = Column(String(20), nullable=True, comment="楼层类型 (single/multi)，为空表示通用")
    is_unlimited = Column(
        Boolean, default=False, nullable=False, comment="是否不限量：true=不限量，false=限量"
    )
    limit_count = Column(
        Integer, nullable=True, comment="限量数量（is_unlimited=false 时必填，否则为空）"
    )
    base_fee = Column(DECIMAL(12, 2), nullable=False, comment="套餐基础费用（年费）")
    description = Column(Text, nullable=True, comment="套餐描述")
    status = Column(
        String(20), default="active", nullable=False, index=True, comment="状态：active/inactive"
    )


class AuditLog(BaseModel):
    """审计日志表"""

    __tablename__ = "audit_logs"

    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(50), nullable=False)
    module = Column(String(50), nullable=False)
    record_id = Column(Integer)
    record_type = Column(String(50))
    changes = Column(JSON)  # {"before": {...}, "after": {...}}
    ip_address = Column(String(45))
    operation_type = Column(
        String(20),
        default="standard",
        comment="操作类型: standard/batch/relation/sensitive",
    )
    extra_metadata = Column(
        JSON,
        nullable=True,
        comment="扩展元数据: 批量统计、关系ID列表等",
    )
