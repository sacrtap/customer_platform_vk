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

    customer_id = Column(Integer, ForeignKey("customers.id"))
    real_amount = Column(DECIMAL(12, 2), nullable=False)
    bonus_amount = Column(DECIMAL(12, 2), default=0)
    # total_amount 通过计算字段生成
    operator_id = Column(Integer, ForeignKey("users.id"))
    payment_proof = Column(String(255))
    remark = Column(Text)


class PricingRule(BaseModel):
    """计费规则表"""

    __tablename__ = "pricing_rules"

    customer_id = Column(Integer, ForeignKey("customers.id"))
    device_type = Column(String(20), nullable=False)  # X/N/L
    pricing_type = Column(String(20), nullable=False)  # fixed/tier/package
    unit_price = Column(DECIMAL(10, 2))
    tiers = Column(JSON)  # 阶梯配置
    package_type = Column(String(20))  # A/B/C/D
    package_limits = Column(JSON)
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date)
    created_by = Column(Integer, ForeignKey("users.id"))


class Invoice(BaseModel):
    """结算单表"""

    __tablename__ = "invoices"

    invoice_no = Column(String(50), unique=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    total_amount = Column(DECIMAL(12, 2), nullable=False)
    discount_amount = Column(DECIMAL(12, 2), default=0)
    discount_reason = Column(Text)
    discount_attachment = Column(String(255))
    # final_amount = total_amount - discount_amount
    status = Column(
        String(20), default="draft"
    )  # draft/pending_customer/customer_confirmed/paid/completed/cancelled
    approver_id = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(String(50))
    customer_confirmed_at = Column(String(50))
    payment_proof = Column(String(255))
    paid_at = Column(String(50))
    completed_at = Column(String(50))
    is_auto_generated = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))


class InvoiceItem(BaseModel):
    """结算单明细表"""

    __tablename__ = "invoice_items"

    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"))
    device_type = Column(String(20), nullable=False)
    layer_type = Column(String(20))  # single/multi
    quantity = Column(DECIMAL(10, 2), nullable=False)
    unit_price = Column(DECIMAL(10, 2), nullable=False)
    # subtotal = quantity * unit_price
    pricing_rule_id = Column(Integer, ForeignKey("pricing_rules.id"))


class ConsumptionRecord(BaseModel):
    """消费流水表"""

    __tablename__ = "consumption_records"

    customer_id = Column(Integer, ForeignKey("customers.id"))
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    amount = Column(DECIMAL(12, 2), nullable=False)
    bonus_used = Column(DECIMAL(12, 2), default=0)
    real_used = Column(DECIMAL(12, 2), default=0)
    balance_after = Column(DECIMAL(12, 2))


class DailyUsage(BaseModel):
    """每日用量表"""

    __tablename__ = "daily_usage"

    customer_id = Column(Integer, ForeignKey("customers.id"))
    usage_date = Column(Date, nullable=False)
    device_type = Column(String(20), nullable=False)
    layer_type = Column(String(20))
    quantity = Column(DECIMAL(10, 2), nullable=False)


class SyncLog(BaseModel):
    """同步任务日志表"""

    __tablename__ = "sync_logs"

    task_name = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    records_synced = Column(Integer, default=0)
    error_message = Column(Text)


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
