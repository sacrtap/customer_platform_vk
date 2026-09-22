"""行业类型字典模型"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class IndustryType(BaseModel):
    """行业类型字典表"""

    __tablename__ = "industry_types"

    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

    def __repr__(self):
        return f"<IndustryType {self.name}>"
