# 权限校验装饰器实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的权限校验系统，包括数据库查询、Redis缓存和装饰器模式

**Architecture:** 基于用户-角色-权限三层关联模型，使用Redis缓存减少数据库查询，通过装饰器模式实现路由级权限校验

**Tech Stack:** Python, SQLAlchemy, Redis, Sanic

---

## 文件结构

### 新建文件
- `backend/app/services/permissions.py` - 权限服务层
- `backend/app/cache/permissions.py` - 权限缓存层

### 修改文件
- `backend/app/middleware/auth.py` - 完善权限校验装饰器
- `backend/app/services/__init__.py` - 导出权限服务
- `backend/app/routes/users.py` - 添加权限装饰器到删除用户路由
- `backend/app/routes/billing.py` - 添加权限装饰器到充值路由

---

## 任务分解

### Task 1: 创建权限服务层

**Files:**
- Create: `backend/app/services/permissions.py`
- Modify: `backend/app/services/__init__.py`

- [ ] **Step 1: 创建 permissions.py 服务文件**

实现 `get_user_permissions` 函数，通过用户ID查询所有权限代码：
- 通过 user → user_roles → roles 关联获取用户角色
- 通过 roles → role_permissions → permissions 关联获取角色权限
- 返回权限代码列表

```python
"""权限服务"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Set
from ..models.users import User, Role, Permission, user_roles, role_permissions


async def get_user_permissions(session: AsyncSession, user_id: int) -> Set[str]:
    """
    获取用户所有权限代码
    
    Args:
        session: 数据库会话
        user_id: 用户ID
        
    Returns:
        权限代码集合
    """
    # 查询用户所有角色的权限代码
    stmt = (
        select(Permission.code)
        .select_from(User)
        .join(user_roles, User.id == user_roles.c.user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .join(role_permissions, Role.id == role_permissions.c.role_id)
        .join(Permission, Permission.id == role_permissions.c.permission_id)
        .where(User.id == user_id, User.deleted_at.is_(None))
    )
    
    result = await session.execute(stmt)
    permissions = result.scalars().all()
    
    return set(permissions)
```

- [ ] **Step 2: 更新 services/__init__.py**

导出权限服务：

```python
"""服务层入口"""

from .auth import AuthService
from .permissions import get_user_permissions

__all__ = ["AuthService", "get_user_permissions"]
```

- [ ] **Step 3: 运行测试验证**

```bash
cd backend
python -c "from app.services import get_user_permissions; print('Import successful')"
```

预期: 没有导入错误

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/permissions.py backend/app/services/__init__.py
git commit -m "feat: add get_user_permissions function"
```

---

### Task 2: 创建权限缓存层

**Files:**
- Create: `backend/app/cache/permissions.py`

- [ ] **Step 1: 创建权限缓存文件**

实现 Redis 缓存逻辑：

```python
"""权限缓存服务"""

import json
from typing import Set, Optional
from ..config import settings
import aioredis


class PermissionCache:
    """权限缓存类"""
    
    def __init__(self):
        self.redis_url = settings.redis_url
        self._redis: Optional[aioredis.Redis] = None
        self.default_ttl = 300  # 5 minutes
    
    async def _get_redis(self) -> aioredis.Redis:
        """获取 Redis 连接"""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis
    
    async def get_permissions(self, user_id: int) -> Optional[Set[str]]:
        """
        从缓存获取用户权限
        
        Args:
            user_id: 用户ID
            
        Returns:
            权限代码集合，如果缓存不存在返回 None
        """
        redis = await self._get_redis()
        key = f"permissions:user:{user_id}"
        data = await redis.get(key)
        
        if data is None:
            return None
        
        return set(json.loads(data))
    
    async def set_permissions(self, user_id: int, permissions: Set[str]) -> None:
        """
        设置用户权限到缓存
        
        Args:
            user_id: 用户ID
            permissions: 权限代码集合
        """
        redis = await self._get_redis()
        key = f"permissions:user:{user_id}"
        data = json.dumps(list(permissions))
        await redis.setex(key, self.default_ttl, data)
    
    async def delete_permissions(self, user_id: int) -> None:
        """
        删除用户权限缓存
        
        Args:
            user_id: 用户ID
        """
        redis = await self._get_redis()
        key = f"permissions:user:{user_id}"
        await redis.delete(key)
    
    async def clear_all(self) -> None:
        """清空所有权限缓存"""
        redis = await self._get_redis()
        pattern = "permissions:user:*"
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)


# 全局缓存实例
permission_cache = PermissionCache()
```

- [ ] **Step 2: 更新配置文件**

在 `backend/app/config.py` 中添加 Redis 配置：

```python
# Redis 配置
redis_url: str = "redis://localhost:6379/0"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/cache/permissions.py backend/app/config.py
git commit -m "feat: add permission caching with Redis"
```

---

### Task 3: 完善权限校验装饰器

**Files:**
- Modify: `backend/app/middleware/auth.py`

- [ ] **Step 1: 更新 auth.py 装饰器**

```python
"""认证中间件"""

from sanic import Sanic
from sanic.response import json
from sanic.request import Request
from functools import wraps
from ..services.auth import AuthService
from ..config import settings
from ..services import get_user_permissions
from ..cache.permissions import permission_cache


def auth_middleware(app: Sanic):
    """注册认证中间件"""

    @app.middleware("request")
    async def authenticate(request: Request):
        """请求认证中间件"""
        # 跳过不需要认证的路径
        skip_paths = [
            "/health",
            "/",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
        ]

        if any(request.path.startswith(path) for path in skip_paths):
            return

        # 获取 Authorization Header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return json({"code": 40101, "message": "缺少认证 Token"}, status=401)

        token = auth_header.split(" ")[1]
        payload = AuthService.verify_token(token)

        if not payload:
            return json({"code": 40102, "message": "Token 无效或已过期"}, status=401)

        # 将用户信息存储到 request 上下文
        request.ctx.user = payload


def get_current_user(request: Request) -> dict | None:
    """获取当前登录用户"""
    return getattr(request.ctx, "user", None)


def require_permission(permission_code: str):
    """权限校验装饰器"""

    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            user = get_current_user(request)

            if not user:
                return json({"code": 40101, "message": "未认证"}, status=401)

            # 从缓存或数据库获取用户权限
            user_id = user["user_id"]
            user_permissions = await permission_cache.get_permissions(user_id)
            
            if user_permissions is None:
                # 缓存未命中，从数据库查询
                db_session: AsyncSession = request.ctx.db_session
                user_permissions = await get_user_permissions(db_session, user_id)
                # 设置缓存
                await permission_cache.set_permissions(user_id, user_permissions)
            
            # 校验权限
            if permission_code not in user_permissions:
                return json({
                    'code': 40301,
                    'message': '权限不足'
                }, status=403)

            return await f(request, *args, **kwargs)

        return decorated_function

    return decorator
```

- [ ] **Step 2: 添加 AsyncSession 导入**

```python
from sqlalchemy.ext.asyncio import AsyncSession
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/middleware/auth.py
git commit -m "feat: implement require_permission decorator with caching"
```

---

### Task 4: 在路由中添加权限校验

**Files:**
- Modify: `backend/app/routes/users.py`
- Modify: `backend/app/routes/billing.py`

- [ ] **Step 1: 更新 users.py - 删除用户路由**

```python
"""用户管理路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.users import UserService
from ..middleware.auth import get_current_user, require_permission

users_bp = Blueprint("users", url_prefix="/api/v1/users")
```

修改删除用户路由：

```python
@users_bp.delete("/<user_id:int>")
@require_permission("user.delete")
async def delete_user(request: Request, user_id: int):
    """删除用户（软删除）"""
    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    # 获取当前用户
    current_user = get_current_user(request)
    if current_user and user_id == current_user.get("user_id"):
        return json({"code": 40001, "message": "不能删除当前登录的用户"}, status=400)

    success = await service.delete_user(user_id)

    if not success:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    # 清除被删除用户的权限缓存
    from ..cache.permissions import permission_cache
    await permission_cache.delete_permissions(user_id)

    return json({"code": 0, "message": "删除成功"})
```

- [ ] **Step 2: 更新 billing.py - 充值路由**

```python
"""结算管理路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from decimal import Decimal
from ..services.billing import BalanceService, PricingService, InvoiceService
from ..middleware.auth import get_current_user, require_permission

billing_bp = Blueprint("billing", url_prefix="/api/v1/billing")
```

修改充值路由：

```python
@billing_bp.post("/recharge")
@require_permission("billing.recharge")
async def recharge(request: Request):
    """
    客户充值

    Body:
    {
        "customer_id": 1,
        "real_amount": 10000.00,
        "bonus_amount": 2000.00,
        "payment_proof": "/uploads/proof.png",
        "remark": "Q1 季度充值"
    }
    """
    db: AsyncSession = request.ctx.db_session
    data = request.json
    user = get_current_user(request)

    customer_id = data.get("customer_id")
    real_amount = Decimal(str(data.get("real_amount", 0)))
    bonus_amount = Decimal(str(data.get("bonus_amount", 0)))

    if not customer_id or real_amount <= 0:
        return json(
            {"code": 40001, "message": "客户 ID 和实充金额不能为空"},
            status=400,
        )

    balance_service = BalanceService(db)

    record = await balance_service.recharge(
        customer_id=customer_id,
        real_amount=real_amount,
        bonus_amount=bonus_amount,
        operator_id=user["user_id"] if user else 1,
        payment_proof=data.get("payment_proof"),
        remark=data.get("remark"),
    )

    return json(
        {
            "code": 0,
            "message": "充值成功",
            "data": {
                "id": record.id,
                "customer_id": record.customer_id,
                "real_amount": float(record.real_amount),
                "bonus_amount": float(record.bonus_amount),
                "total_amount": float(record.real_amount + record.bonus_amount),
            },
        },
        status=201,
    )
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routes/users.py backend/app/routes/billing.py
git commit -m "feat: add permission decorator to delete user and recharge routes"
```

---

## 验收标准

- [ ] `get_user_permissions` 函数正确实现
- [ ] `require_permission` 装饰器工作正常
- [ ] 权限缓存生效（Redis）
- [ ] 至少 2 个路由使用新装饰器（删除用户、充值）

---

## 测试方法

### 1. 单元测试

```bash
# 测试权限服务
python -c "
import asyncio
from app.services import get_user_permissions
from app.models.users import User, Role, Permission

# 验证函数签名
print('get_user_permissions signature OK')
"
```

### 2. 集成测试

```bash
# 启动应用
cd backend
python -m app.main

# 测试权限校验
# 1. 无权限用户尝试删除用户 - 应返回 403
curl -X DELETE http://localhost:8000/api/v1/users/2 \
  -H "Authorization: Bearer <no_permission_token>"

# 2. 有权限用户尝试删除用户 - 应成功
curl -X DELETE http://localhost:8000/api/v1/users/2 \
  -H "Authorization: Bearer <admin_token>"

# 3. 测试充值权限
curl -X POST http://localhost:8000/api/v1/billing/recharge \
  -H "Authorization: Bearer <no_permission_token>" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": 1, "real_amount": 100}'
```

### 3. 缓存测试

```bash
# 查看 Redis 缓存
redis-cli
> KEYS "permissions:*"
> GET "permissions:user:1"
> TTL "permissions:user:1"  # 应该是 300 左右
```

### 4. 性能测试

```bash
# 测试缓存命中率
# 1. 第一次请求应该查询数据库
# 2. 第二次请求应该从缓存读取
# 3. 比较响应时间
```

---

## 预期结果

1. **权限校验生效**: 无权限用户尝试删除用户或充值时返回 403 错误
2. **缓存生效**: 相同用户多次请求只查询一次数据库
3. **性能提升**: 缓存命中时响应时间 < 50ms
4. **路由保护**: 删除用户和充值路由需要特定权限
