"""认证中间件"""

from sanic import Sanic
from sanic.response import json
from sanic.request import Request
from functools import wraps
from sqlalchemy.ext.asyncio import AsyncSession
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
                return json({"code": 40301, "message": "权限不足"}, status=403)

            return await f(request, *args, **kwargs)

        return decorated_function

    return decorator
