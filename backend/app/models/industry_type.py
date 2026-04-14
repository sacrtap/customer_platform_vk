"""行业类型字典模型"""

from sqlalchemy import Column, String, Integer
from .base import BaseModel


class IndustryType(BaseModel):
    """行业类型字典表"""

    __tablename__ = "industry_types"

    name = Column(String(50), nullable=False, unique=True, index=True)
    sort_order = Column(Integer, nullable=False, default=0, index=True)

    def __repr__(self):
        return f"<IndustryType {self.name}>"
