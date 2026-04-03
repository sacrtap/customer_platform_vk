"""结算与余额模型"""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    ForeignKey,
    Text,
    DECIMAL,
    Date,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from .base import BaseModel


class CustomerBalance(BaseModel):
    """客户余额表"""

    __tablename__ = "customer_balances"

    customer_id = Column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), unique=True
    )
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
    pricing_type = Column(String(20), nullable=False)  # fixed/tier/package
    unit_price = Column(DECIMAL(10, 2))
    tiers = Column(JSON)  # 阶梯配置
    package_type = Column(String(20))  # A/B/C/D
    package_limits = Column(JSON)
    effective_date = Column(Date, nullable=False, index=True)
    expiry_date = Column(Date)
    created_by = Column(Integer, ForeignKey("users.id"))


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
    )  # draft/pending_customer/customer_confirmed/paid/completed/cancelled
    approver_id = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(String(50))
    customer_confirmed_at = Column(String(50))
    payment_proof = Column(String(255))
    paid_at = Column(String(50))
    completed_at = Column(String(50))
    is_auto_generated = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))

    # 关联
    items = relationship(
        "InvoiceItem", back_populates="invoice", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "idx_invoice_customer_period", "customer_id", "period_start", "period_end"
        ),
        Index("idx_invoice_status_period", "status", "period_start"),
    )


class InvoiceItem(BaseModel):
    """结算单明细表"""

    __tablename__ = "invoice_items"

    invoice_id = Column(
        Integer, ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
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


class DailyUsage(BaseModel):
    """每日用量表"""

    __tablename__ = "daily_usage"

    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    usage_date = Column(Date, nullable=False, index=True)
    device_type = Column(String(20), nullable=False)
    layer_type = Column(String(20))
    quantity = Column(DECIMAL(10, 2), nullable=False)

    __table_args__ = (
        Index("idx_daily_usage_customer_date", "customer_id", "usage_date"),
        Index("idx_daily_usage_customer_device", "customer_id", "device_type"),
    )


class SyncTaskLog(BaseModel):
    """同步任务日志表"""

    __tablename__ = "sync_task_logs"

    task_name = Column(String(100), nullable=False, index=True, comment="任务名称")
    status = Column(
        String(20), nullable=False, comment="任务状态"
    )  # success/partial/failed

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
