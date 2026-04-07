"""认证相关路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import jwt
import uuid
from ..services.auth import AuthService
from ..services.users import UserService
from ..services.permissions import get_user_permissions
from ..middleware.auth import get_current_user
from ..cache.permissions import permission_cache
from ..services.token_blacklist import TokenBlacklistService
from ..config import settings

auth_bp = Blueprint("auth", url_prefix="/api/v1/auth")


@auth_bp.post("/login")
async def login(request: Request):
    """
    用户登录

    Body:
    {
        "username": "admin",
        "password": "password123"
    }
    """
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return json({"code": 40001, "message": "用户名和密码不能为空"}, status=400)

    session: AsyncSession = request.ctx.db_session
    user_service = UserService(session)

    user = await user_service.get_user_by_username(username)
    if not user:
        return json({"code": 40101, "message": "用户名或密码错误"}, status=401)

    if not user_service.verify_password(password, user.password_hash):
        return json({"code": 40101, "message": "用户名或密码错误"}, status=401)

    if not user.is_active:
        return json({"code": 40102, "message": "账号已被禁用"}, status=401)

    roles = [role.name for role in user.roles]

    access_token = AuthService.create_access_token(user_id=user.id, username=username, roles=roles)
    refresh_token = AuthService.create_refresh_token(user_id=user.id)

    # 获取用户权限
    user_permissions = await get_user_permissions(session, user.id)
    await permission_cache.set_permissions(user.id, user_permissions)

    return json(
        {
            "code": 0,
            "message": "登录成功",
            "data": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "user": {
                    "id": user.id,
                    "username": username,
                    "email": user.email,
                    "real_name": user.real_name,
                    "roles": roles,
                },
                "permissions": list(user_permissions),
            },
        }
    )


@auth_bp.post("/logout")
async def logout(request: Request):
    """用户登出"""
    user = get_current_user(request)

    if user:
        # 获取当前 token（从请求头）
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ")[1]
            # 验证 token 以获取 payload（包含 jti 和 exp）
            payload = AuthService.verify_token(token)
            if payload:
                jti = payload.get("jti")
                exp_timestamp = payload.get("exp")
                if jti and exp_timestamp:
                    # 将 access token 加入黑名单
                    blacklist_service = TokenBlacklistService(request.ctx.db_session)
                    await blacklist_service.add_to_blacklist(
                        jti=jti,
                        token_type="access",
                        expires_at=datetime.fromtimestamp(exp_timestamp),
                    )

        # 清除权限缓存
        user_id = user.get("user_id")
        if user_id:
            await permission_cache.invalidate(user_id)

    return json({"code": 0, "message": "登出成功"})


@auth_bp.get("/me")
async def get_me(request: Request):
    """获取当前用户信息"""
    user = get_current_user(request)

    if not user:
        return json({"code": 40101, "message": "未认证"}, status=401)

    return json({"code": 0, "message": "success", "data": user})


@auth_bp.post("/refresh")
async def refresh_token(request: Request):
    """使用 Refresh Token 刷新 Access Token"""
    data = request.json
    refresh_token = data.get("refresh_token")

    if not refresh_token:
        return json({"code": 40001, "message": "Refresh Token 不能为空"}, status=400)

    payload = AuthService.decode_refresh_token(refresh_token)

    if not payload:
        return json({"code": 40101, "message": "Refresh Token 无效或已过期"}, status=401)

    session: AsyncSession = request.ctx.db_session
    user_service = UserService(session)

    user = await user_service.get_user_by_id(payload["user_id"])
    if not user or not user.is_active:
        return json({"code": 40101, "message": "用户不存在或已被禁用"}, status=401)

    # 将旧 Refresh Token 加入黑名单
    jti = payload.get("jti")
    exp_timestamp = payload.get("exp")
    if jti and exp_timestamp:
        blacklist_service = TokenBlacklistService(request.ctx.db_session)
        await blacklist_service.add_to_blacklist(
            jti=jti,
            token_type="refresh",
            expires_at=datetime.fromtimestamp(exp_timestamp),
        )

    roles = [role.name for role in user.roles]

    new_access_token = AuthService.create_access_token(
        user_id=user.id,
        username=user.username,
        roles=roles,
    )
    new_refresh_token = AuthService.create_refresh_token(user_id=user.id)

    return json(
        {
            "code": 0,
            "message": "Token 刷新成功",
            "data": {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "token_type": "Bearer",
            },
        }
    )


@auth_bp.post("/forgot-password")
async def forgot_password(request: Request):
    """
    忘记密码 - 发送密码重置链接

    Body:
    {
        "username": "string (required)",
        "email": "string (required)"
    }
    """
    data = request.json
    username = data.get("username")
    email = data.get("email")

    if not username or not email:
        return json({"code": 40001, "message": "用户名和邮箱不能为空"}, status=400)

    session: AsyncSession = request.ctx.db_session
    user_service = UserService(session)

    # 查找用户（通过用户名或邮箱）
    user = await user_service.get_user_by_username(username)

    if not user or user.email != email:
        # 为了安全，不暴露用户是否存在
        return json(
            {"code": 0, "message": "如果账号存在，密码重置链接已发送到邮箱"},
        )

    if not user.is_active:
        return json({"code": 40002, "message": "账号已被禁用，请联系管理员"}, status=400)

    # 生成重置 token（2 小时有效期）
    reset_token = jwt.encode(
        {
            "user_id": user.id,
            "type": "password_reset",
            "exp": datetime.utcnow() + timedelta(hours=2),
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    # TODO: 发送重置邮件到 user.email
    # 临时方案：在日志中输出重置链接（开发环境使用）
    reset_link = f"http://localhost:5173/reset-password?token={reset_token}"
    print(f"\n🔑 密码重置链接 (开发环境): {reset_link}")
    print(f"   用户：{user.username} ({user.email})\n")

    return json({"code": 0, "message": "如果账号存在，密码重置链接已发送到邮箱"})


@auth_bp.post("/reset-password")
async def reset_password(request: Request):
    """
    重置密码

    Body:
    {
        "token": "string (required)",
        "new_password": "string (required)"
    }
    """
    data = request.json
    token = data.get("token")
    new_password = data.get("new_password")

    if not token or not new_password:
        return json({"code": 40001, "message": "Token 和新密码不能为空"}, status=400)

    if len(new_password) < 6:
        return json({"code": 40002, "message": "密码长度不能少于 6 位"}, status=400)

    try:
        # 验证重置 token
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

        if payload.get("type") != "password_reset":
            return json({"code": 40101, "message": "无效的 Token 类型"}, status=401)

        user_id = payload.get("user_id")
        if not user_id:
            return json({"code": 40102, "message": "Token 无效"}, status=401)

        session: AsyncSession = request.ctx.db_session
        user_service = UserService(session)

        user = await user_service.get_user_by_id(user_id)
        if not user or not user.is_active:
            return json({"code": 40103, "message": "用户不存在或已被禁用"}, status=401)

        # 重置密码
        await user_service.reset_password(user_id, new_password)

        return json({"code": 0, "message": "密码重置成功"})

    except jwt.ExpiredSignatureError:
        return json({"code": 40104, "message": "重置链接已过期，请重新申请"}, status=401)
    except jwt.InvalidTokenError:
        return json({"code": 40105, "message": "重置链接无效"}, status=401)
