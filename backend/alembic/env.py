from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models.base import BaseModel

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = BaseModel.metadata


def run_migrations_offline() -> None:
    """离线模式 - 用于生成 SQL 脚本"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=False,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    # 生成 SQL 脚本而不执行
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式 - 执行迁移到数据库"""
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
