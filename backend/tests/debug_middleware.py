"""测试中间件执行"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置环境变量
os.environ["JWT_SECRET"] = "test_jwt_secret_123"
os.environ["WEBHOOK_SECRET"] = "test_webhook_secret_123"

from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine

# Mock scheduler
with patch("app.tasks.scheduler.scheduler") as mock_sched:
    mock_sched.running = False
    mock_sched.start = MagicMock()
    mock_sched.shutdown = MagicMock()
    mock_sched.get_jobs = MagicMock(return_value=[])

    from app.main import create_app
    from app.middleware.auth import auth_middleware

    # 创建测试数据库引擎
    engine = create_engine("postgresql://localhost:5432/customer_platform_test")

    # 创建应用
    print("Creating app...")
    app = create_app("test_app", engine)

    # 检查中间件
    print(f"\nMiddleware count: {len(app.request_middleware)}")
    for i, mw in enumerate(app.request_middleware):
        print(f"  {i}: {mw}")

    # 创建测试客户端
    from sanic_testing.testing import SanicTestClient

    client = SanicTestClient(app)

    # 测试 /health (应该跳过认证)
    print("\n=== Testing /health ===")
    _, response = client.get("/health")
    print(f"Status: {response.status}")

    # 测试 /api/v1/auth/login (应该跳过认证)
    print("\n=== Testing /api/v1/auth/login ===")
    _, response = client.post(
        "/api/v1/auth/login", json={"username": "test", "password": "test123"}
    )
    print(f"Status: {response.status}")

    # 测试 /api/v1/customer-groups (需要认证)
    print("\n=== Testing /api/v1/customer-groups (no auth) ===")
    _, response = client.post(
        "/api/v1/customer-groups", json={"name": "test", "group_type": "dynamic"}
    )
    print(f"Status: {response.status}")
    print(f"Body: {response.text}")

    # 测试 /api/v1/customer-groups (带认证)
    print("\n=== Testing /api/v1/customer-groups (with auth) ===")
    _, response = client.post(
        "/api/v1/customer-groups",
        json={"name": "test", "group_type": "dynamic"},
        headers={"Authorization": "Bearer fake_token"},
    )
    print(f"Status: {response.status}")
    print(f"Body: {response.text}")

print("\nDone!")
