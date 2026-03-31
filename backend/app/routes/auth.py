"""认证相关路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from ..services.auth import AuthService
from ..middleware.auth import get_current_user

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

    # TODO: 临时硬编码验证，后续替换为数据库查询
    if username == "admin" and password == "admin123":
        access_token = AuthService.create_access_token(
            user_id=1, username=username, roles=["admin"]
        )
        refresh_token = AuthService.create_refresh_token(user_id=1)

        return json(
            {
                "code": 0,
                "message": "登录成功",
                "data": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "Bearer",
                    "user": {"id": 1, "username": username, "roles": ["admin"]},
                },
            }
        )

    return json({"code": 40101, "message": "用户名或密码错误"}, status=401)


@auth_bp.post("/logout")
async def logout(request: Request):
    """用户登出"""
    # TODO: 将 token 加入黑名单
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
        return json(
            {"code": 40101, "message": "Refresh Token 无效或已过期"}, status=401
        )

    # 生成新的 Access Token
    new_access_token = AuthService.create_access_token(
        user_id=payload["user_id"],
        username=payload.get("username", "user"),
        roles=[],  # TODO: 从数据库获取角色
    )

    return json(
        {
            "code": 0,
            "message": "Token 刷新成功",
            "data": {"access_token": new_access_token, "token_type": "Bearer"},
        }
    )
