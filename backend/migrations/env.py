from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

import sys
from pathlib import Path

# 添加父目录到路径以便导入 app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models.base import BaseModel
from app.models import users, customers, billing

# Alembic Config object
config = context.config

# 设置数据库 URL
config.set_main_option("sqlalchemy.url", settings.database_url)

# 设置目标元数据
target_metadata = BaseModel.metadata


# 其他配置
def get_section_config(section):
    """获取配置节"""
    if config.config_ini_section:
        return config.get_section(section)
    return {}


def run_migrations_offline() -> None:
    """离线模式运行迁移"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式运行迁移"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
