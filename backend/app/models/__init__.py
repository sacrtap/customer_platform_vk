"""数据库模型入口"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """基础模型类"""

    pass


# 导入所有模型以便 alembic 自动发现
from . import users, customers, billing, tags, webhooks

# 导出所有模型
__all__ = [
    "Base",
    "users",
    "customers",
    "billing",
    "tags",
    "webhooks",
]
