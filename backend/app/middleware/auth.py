"""认证中间件"""

from sanic import Sanic
from sanic.response import json
from sanic.request import Request
from functools import wraps
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.auth import AuthService
from ..services import get_user_permissions
# Lazy import to avoid capturing real permission_cache at module load time
# Tests can mock app.cache.permissions.permission_cache before routes are loaded
from ..services.token_blacklist import TokenBlacklistService


def auth_middleware(app: Sanic):
    """注册认证中间件"""

    @app.middleware("request")
    async def authenticate(request: Request):
        """请求认证中间件"""
        try:
            # 跳过不需要认证的路径（使用精确匹配或特定前缀）
            skip_paths = [
                "/health",
                "/api/v1/auth/login",
                "/api/v1/auth/refresh",
            ]

            # 精确匹配跳过路径
            if request.path in skip_paths or request.path == "/":
                return

            # 获取 Authorization Header (Sanic 将 headers 转为小写)
            auth_header = request.headers.get("authorization")

            if not auth_header or not auth_header.lower().startswith("bearer "):
                return json({"code": 40101, "message": "缺少认证 Token"}, status=401)

            token = auth_header.split(" ")[1]

            try:
                payload = AuthService.verify_token(token)
            except Exception as e:
                app.logger.warning(f"Token verification failed: {e}")
                return json({"code": 40102, "message": f"Token 验证失败：{str(e)}"}, status=401)

            if not payload:
                return json({"code": 40102, "message": "Token 无效或已过期"}, status=401)

            # 检查 Token 是否在黑名单中
            jti = payload.get("jti")
            if jti:
                blacklist_service = TokenBlacklistService(request.ctx.db_session)
                is_blacklisted = await blacklist_service.is_blacklisted(jti)
                if is_blacklisted:
                    app.logger.info(f"Blacklisted token used: {jti}")
                    return json({"code": 40103, "message": "Token 已失效"}, status=401)

            # 将用户信息存储到 request 上下文
            request.ctx.user = payload
            print(f"[AUTH DEBUG] User set in request.ctx: {payload}")
        except Exception as e:
            print(f"[AUTH DEBUG] Unexpected error in middleware: {e}")
            import traceback

            traceback.print_exc()
            return json({"code": 50000, "message": f"中间件错误：{str(e)}"}, status=500)


def get_current_user(request: Request) -> dict | None:
    """获取当前登录用户"""
    return getattr(request.ctx, "user", None)


def require_permission(permission_code: str):
    """权限校验装饰器

    支持权限通配符匹配：
    - 用户有 'system:view' 权限时，自动拥有 'system:audit_read'
    - 模块级 `*:manage` 权限自动包含 read/write/delete/create/update 操作
    """

    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            user = get_current_user(request)

            if not user:
                return json({"code": 40101, "message": "未认证"}, status=401)

            # Lazy import to support test mocking
            from ..cache.permissions import permission_cache

            # 从缓存或数据库获取用户权限
            user_id = user["user_id"]
            user_permissions = await permission_cache.get_permissions(user_id)

            if user_permissions is None:
                # 缓存未命中，从数据库查询
                db_session: AsyncSession = request.ctx.db_session
                user_permissions = await get_user_permissions(db_session, user_id)
                # 设置缓存
                await permission_cache.set_permissions(user_id, user_permissions)

            # 校验权限（支持通配符匹配）
            if not _check_permission(user_permissions, permission_code):
                return json({"code": 40301, "message": "权限不足"}, status=403)

            return await f(request, *args, **kwargs)

        return decorated_function

    return decorator


def _check_permission(user_permissions: set, required_permission: str) -> bool:
    """检查用户是否有指定权限（支持通配符匹配）

    Args:
        user_permissions: 用户权限集合
        required_permission: 需要的权限

    Returns:
        是否有权限
    """
    if not user_permissions:
        return False

    # 直接匹配
    if required_permission in user_permissions:
        return True

    # 解析权限模块和操作（支持 : 和 . 两种分隔符）
    if ":" not in required_permission and "." not in required_permission:
        return False

    # 支持 : 和 . 两种分隔符
    if ":" in required_permission:
        module, action = required_permission.split(":", 1)
    else:
        module, action = required_permission.split(".", 1)

    # 检查是否有 manage 权限（manage 包含 read/write/delete）
    manage_permission = f"{module}:manage"
    if manage_permission in user_permissions:
        # manage 权限包含所有操作，除了特定的子权限
        if action in ["read", "write", "delete", "create", "update"]:
            return True

    # 特殊映射：system:view 包含 system:audit_read
    if module == "system" and action == "audit_read":
        if "system:view" in user_permissions:
            return True

    return False


def auth_required(f):
    """认证装饰器（不需要特定权限）"""

    @wraps(f)
    async def decorated_function(request, *args, **kwargs):
        user = get_current_user(request)

        if not user:
            return json({"code": 40101, "message": "未认证"}, status=401)

        return await f(request, *args, **kwargs)

    return decorated_function
