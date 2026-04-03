"""客户信息与画像模型"""

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
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from .base import BaseModel


class Customer(BaseModel):
    """客户基础信息表"""

    __tablename__ = "customers"

    company_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    account_type = Column(String(50), index=True)
    business_type = Column(String(50), index=True)
    customer_level = Column(String(50), index=True)
    price_policy = Column(String(50))
    manager_id = Column(Integer, ForeignKey("users.id"), index=True)
    settlement_cycle = Column(String(20))  # monthly/quarterly/yearly
    settlement_type = Column(String(20), index=True)  # prepaid/postpaid
    is_key_customer = Column(Boolean, default=False, index=True)
    email = Column(String(100), index=True)

    __table_args__ = (
        Index("idx_customer_manager_level", "manager_id", "customer_level"),
        Index("idx_customer_business_settlement", "business_type", "settlement_type"),
    )

    # 关联
    profile = relationship("CustomerProfile", uselist=False, back_populates="customer")
    balance = relationship("CustomerBalance", uselist=False, back_populates="customer")
    tags = relationship("CustomerTag", back_populates="customer", lazy="selectin")
    group_memberships = relationship("CustomerGroupMember", back_populates="customer")

    def __repr__(self):
        return f"<Customer {self.name}>"


class CustomerProfile(BaseModel):
    """客户画像表"""

    __tablename__ = "customer_profiles"

    customer_id = Column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), unique=True
    )
    scale_level = Column(String(50))  # 客户规模等级
    consume_level = Column(String(50))  # 客户消费等级
    industry = Column(String(100))
    is_real_estate = Column(Boolean, default=False)
    description = Column(Text)

    # 关联
    customer = relationship("Customer", back_populates="profile")
    tags = relationship("ProfileTag", back_populates="profile", lazy="selectin")

    def __repr__(self):
        return f"<CustomerProfile {self.customer_id}>"
