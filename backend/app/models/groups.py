"""客户群组模型"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    ForeignKey,
    Text,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from .base import BaseModel


class CustomerGroup(BaseModel):
    """客户群组表"""

    __tablename__ = "customer_groups"

    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    group_type = Column(String(20), nullable=False, index=True)
    filter_conditions = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id"), index=True)

    __table_args__ = (Index("idx_group_type_created_by", "group_type", "created_by"),)

    creator = relationship("User", back_populates="created_groups")
    members = relationship(
        "CustomerGroupMember", back_populates="group", cascade="all, delete-orphan"
    )


class CustomerGroupMember(BaseModel):
    """静态群组成员表"""

    __tablename__ = "customer_group_members"

    group_id = Column(
        Integer, ForeignKey("customer_groups.id", ondelete="CASCADE"), primary_key=True
    )
    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    group = relationship("CustomerGroup", back_populates="members")
    customer = relationship("Customer", back_populates="group_memberships")

    __table_args__ = (
        Index("idx_member_group_customer", "group_id", "customer_id"),
        Index("idx_member_customer", "customer_id"),
    )
