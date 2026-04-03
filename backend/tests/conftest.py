"""
测试配置 - 设置测试环境变量
"""

import os
import sys
import pytest
import asyncio

# 确保项目根目录在 Python 路径中
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 设置测试环境变量
# 使用本地 PostgreSQL 测试数据库（Postgres.app 默认无密码）
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://localhost:5432/customer_platform_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("JWT_ALGORITHM", "HS256")


# pytest-asyncio 配置
pytest_plugins = ("pytest_asyncio",)
pytestmark = pytest.mark.asyncio(scope="function")


@pytest.fixture(scope="session")
def event_loop():
    """创建会话级事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
