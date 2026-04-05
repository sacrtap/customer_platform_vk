"""基础模型定义"""

from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.sql import func
from . import Base


class TimestampMixin:
    """时间戳混入类"""

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class SoftDeleteMixin:
    """软删除混入类"""

    deleted_at = Column(DateTime, nullable=True)


class BaseModel(Base, TimestampMixin, SoftDeleteMixin):
    """基础模型"""

    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
