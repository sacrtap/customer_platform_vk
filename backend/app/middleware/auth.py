"""认证中间件"""

from sanic import Sanic
from sanic.response import json
from sanic.request import Request
from functools import wraps
from ..services.auth import AuthService
from ..config import settings


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

            # TODO: 从数据库获取用户权限列表
            # user_permissions = await get_user_permissions(user['user_id'])
            # if permission_code not in user_permissions:
            #     return json({
            #         'code': 40301,
            #         'message': '权限不足'
            #     }, status=403)

            return await f(request, *args, **kwargs)

        return decorated_function

    return decorator
