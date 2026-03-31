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
)
from sqlalchemy.orm import relationship
from .base import BaseModel


class Customer(BaseModel):
    """客户基础信息表"""

    __tablename__ = "customers"

    company_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    account_type = Column(String(50))
    business_type = Column(String(50))
    customer_level = Column(String(50))
    price_policy = Column(String(50))
    manager_id = Column(Integer, ForeignKey("users.id"))
    settlement_cycle = Column(String(20))  # monthly/quarterly/yearly
    settlement_type = Column(String(20))  # prepaid/postpaid
    is_key_customer = Column(Boolean, default=False)
    email = Column(String(100))

    # 关联
    profile = relationship("CustomerProfile", uselist=False, back_populates="customer")
    balance = relationship("CustomerBalance", uselist=False, back_populates="customer")

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

    def __repr__(self):
        return f"<CustomerProfile {self.customer_id}>"


class Tag(BaseModel):
    """标签定义表"""

    __tablename__ = "tags"

    name = Column(String(50), nullable=False)
    type = Column(String(50), nullable=False)  # customer/profile
    category = Column(String(50))
    created_by = Column(Integer, ForeignKey("users.id"))

    __table_args__ = (UniqueConstraint("name", "type", name="uq_tags_name_type"),)

    def __repr__(self):
        return f"<Tag {self.name}>"


class CustomerTag(BaseModel):
    """客户 - 标签关联表"""

    __tablename__ = "customer_tags"

    customer_id = Column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id = Column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class ProfileTag(BaseModel):
    """画像 - 标签关联表"""

    __tablename__ = "profile_tags"

    profile_id = Column(
        Integer,
        ForeignKey("customer_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id = Column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
