import sys
from pathlib import Path

from sqlalchemy import create_engine, pool

from alembic import context

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
    # Alembic 不支持异步引擎，需将 asyncpg URL 转换为 psycopg2
    sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    connectable = create_engine(sync_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
