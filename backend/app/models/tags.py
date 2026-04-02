"""标签管理模型"""

from sqlalchemy import Column, String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .base import BaseModel


class Tag(BaseModel):
    """标签定义表"""

    __tablename__ = "tags"

    name = Column(String(50), nullable=False)
    type = Column(String(50), nullable=False)  # customer/profile
    category = Column(String(50))
    created_by = Column(Integer, ForeignKey("users.id"))

    __table_args__ = (UniqueConstraint("name", "type", name="uq_tags_name_type"),)

    # 关联
    creator = relationship("User", back_populates="created_tags")

    def __repr__(self):
        return f"<Tag {self.name} ({self.type})>"


class CustomerTag(BaseModel):
    """客户 - 标签关联表"""

    __tablename__ = "customer_tags"

    customer_id = Column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id = Column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    # 关联
    customer = relationship("Customer", back_populates="tags")
    tag = relationship("Tag")


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

    # 关联
    profile = relationship("CustomerProfile", back_populates="tags")
    tag = relationship("Tag")
