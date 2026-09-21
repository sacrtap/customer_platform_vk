"""合作状态字典模型"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class CooperationStatus(BaseModel):
    """合作状态字典表"""

    __tablename__ = "cooperation_statuses"

    name: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )  # 展示名称，如 "合作中"
    value: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )  # 存储值，如 "active"
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

    def __repr__(self):
        return f"<CooperationStatus {self.name} ({self.value})>"
