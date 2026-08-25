"""ERP 系统字典模型"""

from sqlalchemy import Column, Integer, String

from .base import BaseModel


class ErpSystem(BaseModel):
    """ERP 系统字典表"""

    __tablename__ = "erp_systems"

    name = Column(String(100), nullable=False, unique=True, index=True)  # 展示名称，如 "ERP云"
    value = Column(String(100), nullable=False, unique=True, index=True)  # 存储值，如 "erp_cloud"
    sort_order = Column(Integer, nullable=False, default=0, index=True)

    def __repr__(self):
        return f"<ErpSystem {self.name} ({self.value})>"
