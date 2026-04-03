"""
集成测试配置 - 完全同步方法

架构说明：
- 使用 sanic-testing 提供的 SanicTestClient
- 同步测试函数，避免事件循环冲突
- 数据库使用同步引擎 (psycopg2)，避免异步事件循环问题
- 所有组件在同一线程同一事件循环中运行
"""

# 必须在导入任何应用代码之前设置环境变量
import os

os.environ["JWT_SECRET"] = "test_jwt_secret_key_for_testing_only_12345678"
os.environ["WEBHOOK_SECRET"] = "test_webhook_secret_key_for_testing_only_12345678"

import pytest
import bcrypt
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.main import create_app
from app.models.base import Base

# 测试数据库配置 - 使用同步驱动
TEST_DATABASE_URL = "postgresql://localhost:5432/customer_platform_test"


@pytest.fixture(scope="function")
def mock_scheduler():
    """Mock APScheduler 避免初始化问题"""
    with patch("app.tasks.scheduler.scheduler") as mock_sched:
        mock_sched.running = False
        mock_sched.start = MagicMock()
        mock_sched.shutdown = MagicMock()
        mock_sched.get_jobs = MagicMock(return_value=[])
        yield mock_sched


@pytest.fixture(scope="function")
def test_engine():
    """创建测试数据库引擎（同步）"""
    engine = create_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )

    # 创建所有表
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield engine

    # 清理
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_engine) -> Session:
    """创建数据库会话（同步）"""
    SessionLocal = sessionmaker(bind=test_engine, class_=Session)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def app(test_engine, mock_scheduler):
    """创建 Sanic 应用实例（使用测试数据库引擎和 mock 调度器）"""
    import uuid

    unique_app_name = f"test_app_{uuid.uuid4().hex[:8]}"

    app_instance = create_app(
        app_name=unique_app_name,
        database_engine=test_engine,
    )
    yield app_instance


@pytest.fixture(scope="function")
def test_user(db_session: Session):
    """创建测试用户"""
    username = "test_user"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # 清理旧数据并创建新用户
    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "test@example.com",
            "is_active": True,
        },
    )
    db_session.commit()

    yield {"username": username, "password": password}

    # 清理
    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    db_session.commit()


@pytest.fixture(scope="function")
def client(app):
    """创建 Sanic 测试客户端

    使用 sanic-testing 的 SanicTestClient
    同步方式访问，避免事件循环冲突
    """
    try:
        from sanic_testing.testing import SanicTestClient

        return SanicTestClient(app)
    except ImportError:
        # 如果没有 sanic-testing，使用内置的 test_client
        return app.test_client
