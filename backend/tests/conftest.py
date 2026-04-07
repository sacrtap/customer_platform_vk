"""
测试配置 - 设置测试环境变量

注意：此文件在 pytest 启动时最先加载，必须确保环境变量在任何 app 代码导入前设置。
"""

import os
import sys
import pytest
import asyncio

# ============================================================
# 必须在导入 ANY 应用代码之前设置环境变量和清除缓存
# ============================================================

# 设置测试环境变量
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://localhost:5432/customer_platform_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

# 清除所有可能的 app 模块缓存
modules_to_clear = [k for k in list(sys.modules.keys()) if k.startswith("app")]
for mod in modules_to_clear:
    del sys.modules[mod]


def pytest_configure(config):
    """pytest 配置 hook - 确保环境变量在任何测试前设置"""
    # 再次清除缓存，防止 pytest 插件提前导入 app 模块
    modules_to_clear = [k for k in list(sys.modules.keys()) if k.startswith("app")]
    for mod in modules_to_clear:
        del sys.modules[mod]


# 确保项目根目录在 Python 路径中
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


# pytest-asyncio 配置
# 注意：事件循环由 pytest-asyncio 自动管理（通过 pytest.ini 中的 asyncio_default_fixture_loop_scope）
