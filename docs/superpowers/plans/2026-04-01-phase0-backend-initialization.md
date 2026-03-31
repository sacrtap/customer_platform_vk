# Phase 0: 后端项目初始化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建完整的 Python Sanic 后端项目骨架，包括数据库配置、认证框架、代码规范工具

**Architecture:** 采用模块化单体架构，按业务域划分包结构。使用 SQLAlchemy 2.0 进行 ORM 操作，Alembic 进行数据库迁移，JWT 进行认证，Black + Flake8 保证代码质量。

**Tech Stack:** Python 3.11 + Sanic + SQLAlchemy 2.0 + Alembic + PyJWT + APScheduler + PostgreSQL

---

## 文件结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── base.py
│   ├── routes/
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── auth.py
│   └── tasks/
│       └── __init__.py
├── migrations/
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── tests/
├── requirements.txt
├── pyproject.toml
├── .flake8
└── .pre-commit-config.yaml
```

---

## 任务清单

### Task 1: 创建项目目录结构和 requirements.txt

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/base.py`
- Create: `backend/app/routes/__init__.py`
- Create: `backend/app/routes/auth.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/auth.py`
- Create: `backend/app/middleware/__init__.py`
- Create: `backend/app/middleware/auth.py`
- Create: `backend/app/tasks/__init__.py`
- Create: `backend/requirements.txt`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p backend/app/models
mkdir -p backend/app/routes
mkdir -p backend/app/services
mkdir -p backend/app/middleware
mkdir -p backend/app/tasks
mkdir -p backend/migrations/versions
mkdir -p backend/tests
```

- [ ] **Step 2: 创建 requirements.txt**

```bash
cat > backend/requirements.txt << 'EOF'
# Web Framework
sanic==23.12.0
sanic-cors==3.0.0b1

# Database
sqlalchemy==2.0.25
alembic==1.13.1
asyncpg==0.29.0

# Authentication
pyjwt==2.8.0
passlib[bcrypt]==1.7.4

# Configuration
pydantic-settings==2.2.1

# Scheduling
apscheduler==3.10.4

# Code Quality
black==23.12.1
flake8==7.0.0
pre-commit==3.6.2

# Testing
pytest==7.4.4
pytest-asyncio==0.21.2
httpx==0.26.0

# Utilities
python-dotenv==1.0.1
EOF
```

- [ ] **Step 3: 创建 app/__init__.py**

```python
"""Customer Platform Backend Application."""

__version__ = "0.1.0"
```

- [ ] **Step 4: 创建 app/models/__init__.py**

```python
"""Database models package."""
```

- [ ] **Step 5: 创建 app/routes/__init__.py**

```python
"""API routes package."""
```

- [ ] **Step 6: 创建 app/services/__init__.py**

```python
"""Business logic services package."""
```

- [ ] **Step 7: 创建 app/middleware/__init__.py**

```python
"""Middleware package."""
```

- [ ] **Step 8: 创建 app/tasks/__init__.py**

```python
"""Background tasks package."""
```

- [ ] **Step 9: Commit directory structure**

```bash
cd backend
git add .
git commit -m "feat: initial backend directory structure"
```

---

### Task 2: 配置管理 (config.py)

**Files:**
- Create: `backend/app/config.py`

- [ ] **Step 1: 创建 app/config.py**

```python
"""Application configuration management using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Application
    APP_NAME: str = "Customer Platform API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENV: str = "development"

    # Database
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Logging
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
```

- [ ] **Step 2: Commit config.py**

```bash
git add app/config.py
git commit -m "feat: add configuration management with pydantic-settings"
```

---

### Task 3: SQLAlchemy 和数据库基础模型

**Files:**
- Create: `backend/app/models/base.py`

- [ ] **Step 1: 创建 app/models/base.py**

```python
"""Base database models and utilities."""

from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy.ext.declarative import as_declarative


class Base(DeclarativeBase):
    """Base class for all database models."""

    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        return cls.__name__.lower() + "s"


@as_declarative()
class BaseModel:
    """Base model with common columns."""

    id: Any
    created_at: datetime
    updated_at: datetime

    @declared_attr
    def created_at(cls) -> Column:
        """Created at timestamp."""
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        )

    @declared_attr
    def updated_at(cls) -> Column:
        """Updated at timestamp."""
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )


# Import all models here to register them
from app.models.base import Base, BaseModel

__all__ = ["Base", "BaseModel"]
```

- [ ] **Step 2: Fix the import issue in base.py**

```python
"""Base database models and utilities."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy.ext.declarative import as_declarative
from sqlalchemy.dialects.postgresql import UUID
import uuid


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


@as_declarative()
class BaseModel:
    """Base model with common columns."""

    id: Any
    created_at: datetime
    updated_at: datetime

    @declared_attr
    def created_at(cls) -> Column:
        """Created at timestamp."""
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        )

    @declared_attr
    def updated_at(cls) -> Column:
        """Updated at timestamp."""
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""

    deleted_at: Optional[datetime]

    @declared_attr
    def deleted_at(cls) -> Column:
        """Soft delete timestamp."""
        return Column(DateTime(timezone=True), nullable=True)


class UUIDMixin:
    """Mixin for UUID primary key."""

    id: Any

    @declared_attr
    def id(cls) -> Column:
        """UUID primary key."""
        return Column(
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            unique=True,
            nullable=False,
        )
```

- [ ] **Step 3: Commit base.py**

```bash
git add app/models/base.py
git commit -m "feat: add base model with common columns and mixins"
```

---

### Task 4: Sanic 应用入口和 Hello World API

**Files:**
- Create: `backend/app/main.py`

- [ ] **Step 1: 创建 app/main.py**

```python
"""Sanic application entry point."""

from sanic import Sanic
from sanic.response import json
from sanic_cors import CORS

from app.config import settings
from app.routes.auth import bp as auth_bp


def create_app() -> Sanic:
    """Create and configure the Sanic application."""
    app = Sanic(__name__)

    # Load configuration
    app.config.update(
        {
            "NAME": settings.APP_NAME,
            "VERSION": settings.APP_VERSION,
            "DEBUG": settings.DEBUG,
        }
    )

    # Enable CORS
    CORS(
        app,
        origins=settings.CORS_ORIGINS,
        supports_credentials=True,
        automatic_options=True,
    )

    # Register blueprints
    app.blueprint(auth_bp, url_prefix="/api/v1")

    # Health check endpoint
    @app.get("/health")
    async def health_check(request):
        return json(
            {
                "status": "healthy",
                "service": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "timestamp": request.ctx.start_time.isoformat()
                if hasattr(request.ctx, "start_time")
                else None,
            }
        )

    return app


# Create app instance
app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=settings.DEBUG,
        access_log=settings.DEBUG,
    )
```

- [ ] **Step 2: Commit main.py**

```bash
git add app/main.py
git commit -m "feat: add Sanic app entry point with health check"
```

---

### Task 5: 认证路由和登录 API

**Files:**
- Create: `backend/app/routes/auth.py`

- [ ] **Step 1: 创建 app/routes/auth.py**

```python
"""Authentication routes."""

from sanic import Blueprint, Request, text
from sanic.response import json
from sanic_ext import validate
from passlib.hash import bcrypt

from app.services.auth import create_access_token, create_refresh_token
from app.models.base import User


bp = Blueprint("auth", url_prefix="/auth")


@bp.post("/login")
async def login(request: Request):
    """User login endpoint."""
    data = request.json
    username = data.get("username")
    password = data.get("password")

    # Validate input
    if not username or not password:
        return json(
            {"error": "Missing username or password"}, status=400
        )

    # TODO: Query user from database
    # For now, use hardcoded credentials for testing
    if username == "admin" and password == "admin123":
        # Create tokens
        access_token = create_access_token({"sub": username})
        refresh_token = create_refresh_token({"sub": username})

        return json(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
            }
        )

    return json({"error": "Invalid credentials"}, status=401)


@bp.get("/me")
async def get_current_user(request: Request):
    """Get current authenticated user."""
    # TODO: Implement with JWT validation
    return json({"user": request.ctx.user if hasattr(request.ctx, "user") else None})
```

- [ ] **Step 2: Commit auth routes**

```bash
git add app/routes/auth.py
git commit -m "feat: add authentication routes with login endpoint"
```

---

### Task 6: JWT 认证服务

**Files:**
- Create: `backend/app/services/auth.py`

- [ ] **Step 1: 创建 app/services/auth.py**

```python
"""Authentication service using JWT."""

import jwt
from datetime import datetime, timedelta, timezone

from app.config import settings


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Create a new access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: timedelta = None) -> str:
    """Create a new refresh token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


def get_token_expiration(token: str) -> datetime:
    """Get token expiration time."""
    payload = verify_token(token)
    return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
```

- [ ] **Step 2: Commit auth service**

```bash
git add app/services/auth.py
git commit -m "feat: add JWT authentication service"
```

---

### Task 7: 认证中间件

**Files:**
- Create: `backend/app/middleware/auth.py`

- [ ] **Step 1: 创建 app/middleware/auth.py**

```python
"""Authentication middleware."""

from sanic import Request, Response
from sanic.exceptions import Unauthorized

from app.services.auth import verify_token


async def authenticate_request(request: Request) -> None:
    """Authenticate request using JWT token."""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        raise Unauthorized("Missing Authorization header")
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise Unauthorized("Invalid Authorization header format")
    
    token = parts[1]
    
    try:
        payload = verify_token(token)
        request.ctx.user = payload
        request.ctx.token = token
    except ValueError as e:
        raise Unauthorized(str(e))


def require_auth():
    """Decorator to require authentication for a route."""
    def decorator(route):
        route.middleware(authenticate_request, attach_to="request")
        return route
    return decorator
```

- [ ] **Step 2: Commit auth middleware**

```bash
git add app/middleware/auth.py
git commit -m "feat: add authentication middleware"
```

---

### Task 8: Alembic 配置

**Files:**
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/pyproject.toml`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = ["setuptools.build_meta"]

[project]
name = "customer-platform-backend"
version = "0.1.0"
description = "Customer Platform Backend API"
requires-python = ">=3.11"
dependencies = [
    "sanic==23.12.0",
    "sanic-cors==3.0.0b1",
    "sqlalchemy==2.0.25",
    "alembic==1.13.1",
    "asyncpg==0.29.0",
    "pyjwt==2.8.0",
    "passlib[bcrypt]==1.7.4",
    "pydantic-settings==2.2.1",
    "apscheduler==3.10.4",
    "python-dotenv==1.0.1",
]

[project.scripts]
run-app = "app.main:app"
migrate = "migrations.env:main"

[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
exclude = '''
/(
    \.git
  | \.venv
  | build
  | dist
)/
'''

[tool.flake8]
max-line-length = 88
extend-ignore = ["E203", "W503"]
exclude = [
    ".git",
    "__pycache__",
    ".venv",
    "build",
    "dist",
    "migrations",
]
```

- [ ] **Step 2: 初始化 Alembic**

```bash
cd backend
alembic init migrations
```

- [ ] **Step 3: 配置 migrations/env.py**

```python
"""Alembic environment configuration."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine
from sqlalchemy.pool import NullPool
import asyncio

from alembic import context

from app.config import settings
from app.models.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Enable batch mode for SQLite compatibility
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)


asyncio.run(run_migrations_online())
```

- [ ] **Step 4: 配置 migrations/script.py.mako**

```python
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 5: Commit Alembic config**

```bash
git add pyproject.toml migrations/env.py migrations/script.py.mako
git commit -m "feat: add Alembic database migration configuration"
```

---

### Task 9: Black 和 Flake8 配置

**Files:**
- Create: `backend/.flake8`
- Create: `backend/.pre-commit-config.yaml`

- [ ] **Step 1: 创建 .flake8**

```ini
[flake8]
max-line-length = 88
extend-ignore = 
    E203,  # whitespace before ':'
    W503,  # line break before binary operator
exclude = 
    .git,
    __pycache__,
    .venv,
    build,
    dist,
    migrations,
    *.pyc,
    *.pyi,
```

- [ ] **Step 2: 创建 .pre-commit-config.yaml**

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ["--profile", "black"]
```

- [ ] **Step 3: Commit code quality config**

```bash
git add .flake8 .pre-commit-config.yaml
git commit -m "feat: add Black and Flake8 code quality configuration"
```

---

### Task 10: 测试和验证

- [ ] **Step 1: 安装依赖**

```bash
cd backend
pip install -r requirements.txt
```

- [ ] **Step 2: 初始化数据库**

```bash
# Set environment variables
export DATABASE_URL="postgresql://user:password@localhost:5432/customer_platform"

# Run migrations
alembic upgrade head
```

- [ ] **Step 3: 启动应用**

```bash
python -m app.main
```

- [ ] **Step 4: 测试健康检查**

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "Customer Platform API",
  "version": "0.1.0",
  "timestamp": "2026-04-01T12:00:00+00:00"
}
```

- [ ] **Step 5: 测试登录接口**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

Expected response:
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

- [ ] **Step 6: 运行 Black 检查**

```bash
black --check backend/
```

- [ ] **Step 7: 运行 Flake8 检查**

```bash
flake8 backend/
```

- [ ] **Step 8: Commit all changes**

```bash
git add .
git commit -m "feat: complete Phase 0 backend initialization"
```

---

## 验收检查清单

- [ ] `pip install -r requirements.txt` 成功
- [ ] `python -m uvicorn app.main:app` 启动成功 (Note: Should be `python -m app.main`)
- [ ] `GET /health` 返回 200
- [ ] `POST /api/v1/auth/login` 可颁发 Token（临时硬编码验证）
- [ ] `GET /api/v1/auth/me` 需要有效 Token
- [ ] Alembic 可执行 `alembic upgrade head`
- [ ] Black + Flake8 检查通过

---

## 注意事项

1. **数据库连接**: 确保 PostgreSQL 数据库已创建并可访问
2. **环境变量**: 创建 `.env` 文件配置数据库 URL 和 JWT 密钥
3. **JWT 密钥**: 使用强随机密钥，生产环境使用环境变量
4. **密码安全**: 当前使用硬编码验证，后续需集成数据库查询
5. **迁移**: 数据库迁移需要先运行 `alembic revision --autogenerate -m "message"`

---

## 后续步骤

1. 实现用户模型和数据库查询
2. 完善 JWT 认证中间件
3. 实现完整的 RBAC 权限系统
4. 添加单元测试和集成测试
