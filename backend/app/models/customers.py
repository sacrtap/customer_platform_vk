"""客户信息与画像模型"""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    ForeignKey,
    Text,
    Index,
    Date,
    Numeric,
)
from sqlalchemy.orm import relationship
from .base import BaseModel


class Customer(BaseModel):
    """客户基础信息表"""

    __tablename__ = "customers"

    company_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    account_type = Column(String(50), index=True)
    price_policy = Column(String(50))
    manager_id = Column(Integer, ForeignKey("users.id"), index=True)
    settlement_cycle = Column(String(20))  # monthly/quarterly/yearly
    settlement_type = Column(String(20), index=True)  # prepaid/postpaid
    is_key_customer = Column(Boolean, default=False, index=True)
    email = Column(String(100), index=True)

    # === 新增字段（方案A） ===
    erp_system = Column(String(100), nullable=True)  # 所属 ERP 系统
    first_payment_date = Column(Date, nullable=True)  # 首次回款时间
    onboarding_date = Column(Date, nullable=True)  # 客户接入时间
    sales_manager_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )  # 销售负责人
    cooperation_status = Column(String(50), nullable=True, index=True, default="active")  # 合作状态：active/suspended/terminated/noused
    is_settlement_enabled = Column(Boolean, nullable=True, default=True)  # 是否启用结算
    is_disabled = Column(Boolean, nullable=True, default=False, index=True)  # 是否停用
    notes = Column(Text, nullable=True)  # 备注

    __table_args__ = (
        Index("idx_customer_sales_manager", "sales_manager_id"),  # 新增
        Index("idx_customer_cooperation_status", "cooperation_status"),  # 新增
        Index("idx_customer_disabled", "is_disabled"),  # 新增
    )

    # 关联
    profile = relationship("CustomerProfile", uselist=False, back_populates="customer")
    balance = relationship("CustomerBalance", uselist=False, back_populates="customer")
    tags = relationship("CustomerTag", back_populates="customer", lazy="selectin")

    def __repr__(self):
        return f"<Customer {self.name}>"


class CustomerProfile(BaseModel):
    """客户画像表"""

    __tablename__ = "customer_profiles"

    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), unique=True)
    scale_level = Column(String(50))  # 客户规模等级
    consume_level = Column(String(50))  # 客户消费等级
    industry = Column(String(100))
    is_real_estate = Column(Boolean, default=False)
    description = Column(Text)

    # === 新增字段（方案A） ===
    monthly_avg_shots = Column(Integer, nullable=True)  # 月均拍摄量（实际）
    monthly_avg_shots_estimated = Column(Integer, nullable=True)  # 月均拍摄量（测算）
    estimated_annual_spend = Column(Numeric(12, 2), nullable=True)  # 预估年消费
    actual_annual_spend_2025 = Column(Numeric(12, 2), nullable=True)  # 2025年实际消费

    # 关联
    customer = relationship("Customer", back_populates="profile")
    tags = relationship("ProfileTag", back_populates="profile", lazy="selectin")

    def __repr__(self):
        return f"<CustomerProfile {self.customer_id}>"
