"""ERP 系统字典模型"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class ErpSystem(BaseModel):
    """ERP 系统字典表"""

    __tablename__ = "erp_systems"

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )  # 展示名称，如 "ERP云"
    value: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )  # 存储值，如 "erp_cloud"
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

    def __repr__(self):
        return f"<ErpSystem {self.name} ({self.value})>"
