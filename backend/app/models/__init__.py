"""数据库模型入口"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """基础模型类"""

    pass


# isort: off
# 导入所有模型以便 alembic 自动发现
from . import users  # noqa: E402
from . import customers  # noqa: E402
from . import billing  # noqa: E402
from . import tags  # noqa: E402
from . import webhooks  # noqa: E402
from . import groups  # noqa: E402
from . import files  # noqa: E402

# isort: on

# 导出所有模型
__all__ = [
    "Base",
    "users",
    "customers",
    "billing",
    "tags",
    "webhooks",
    "groups",
    "files",
]
