"""
测试配置 - 设置测试环境变量
"""

import os
import sys

# 确保项目根目录在 Python 路径中
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 设置测试环境变量
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
