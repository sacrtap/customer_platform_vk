"""用户管理路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.users import UserService
from ..middleware.auth import get_current_user, require_permission
from ..cache.permissions import permission_cache

users_bp = Blueprint("users", url_prefix="/api/v1/users")


@users_bp.get("")
async def list_users(request: Request):
    """
    获取用户列表

    Query:
    - page: 页码 (默认 1)
    - page_size: 每页数量 (默认 20)
    """
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))

    # 限制 page_size 范围
    page_size = min(page_size, 100)

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    users, total = await service.get_all_users(page=page, page_size=page_size)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "real_name": user.real_name,
                        "is_active": user.is_active,
                        "is_system": user.is_system,
                        "created_at": user.created_at.isoformat()
                        if user.created_at
                        else None,
                    }
                    for user in users
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@users_bp.get("/<user_id:int>")
async def get_user(request: Request, user_id: int):
    """获取用户详情"""
    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    user = await service.get_user_by_id(user_id)

    if not user:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "real_name": user.real_name,
                "is_active": user.is_active,
                "is_system": user.is_system,
                "roles": [{"id": r.id, "name": r.name} for r in user.roles],
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
        }
    )


@users_bp.post("")
async def create_user(request: Request):
    """
    创建用户

    Body:
    {
        "username": "string (required)",
        "password": "string (required)",
        "email": "string (optional)",
        "real_name": "string (optional)"
    }
    """
    data = request.json

    username = data.get("username")
    password = data.get("password")
    email = data.get("email")
    real_name = data.get("real_name")

    if not username or not password:
        return json({"code": 40001, "message": "用户名和密码不能为空"}, status=400)

    # 密码强度检查
    if len(password) < 6:
        return json({"code": 40002, "message": "密码长度不能少于 6 位"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    try:
        user = await service.create_user(
            username=username, password=password, email=email, real_name=real_name
        )
    except ValueError as e:
        return json({"code": 40003, "message": str(e)}, status=400)

    return json(
        {
            "code": 0,
            "message": "创建成功",
            "data": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "real_name": user.real_name,
            },
        },
        status=201,
    )


@users_bp.put("/<user_id:int>")
async def update_user(request: Request, user_id: int):
    """
    更新用户信息

    Body:
    {
        "email": "string (optional)",
        "real_name": "string (optional)",
        "is_active": "boolean (optional)"
    }
    """
    data = request.json

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    user = await service.update_user(
        user_id=user_id,
        email=data.get("email"),
        real_name=data.get("real_name"),
        is_active=data.get("is_active"),
    )

    if not user:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    return json(
        {
            "code": 0,
            "message": "更新成功",
            "data": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "real_name": user.real_name,
                "is_active": user.is_active,
            },
        }
    )


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
    await permission_cache.delete_permissions(user_id)

    return json({"code": 0, "message": "删除成功"})


@users_bp.post("/<user_id:int>/reset-password")
async def reset_password(request: Request, user_id: int):
    """
    重置用户密码

    Body:
    {
        "new_password": "string (required)"
    }
    """
    data = request.json
    new_password = data.get("new_password")

    if not new_password:
        return json({"code": 40001, "message": "新密码不能为空"}, status=400)

    if len(new_password) < 6:
        return json({"code": 40002, "message": "密码长度不能少于 6 位"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    success = await service.reset_password(user_id, new_password)

    if not success:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    return json({"code": 0, "message": "密码重置成功"})


@users_bp.post("/<user_id:int>/roles")
async def assign_roles(request: Request, user_id: int):
    """
    为用户分配角色

    Body:
    {
        "role_ids": [1, 2, 3]
    }
    """
    data = request.json
    role_ids = data.get("role_ids", [])

    if not role_ids:
        return json({"code": 40001, "message": "角色 ID 列表不能为空"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    success = await service.assign_roles(user_id, role_ids)

    if not success:
        return json({"code": 40401, "message": "用户不存在"}, status=404)

    return json({"code": 0, "message": "角色分配成功"})


@users_bp.get("/<user_id:int>/roles")
async def get_user_roles(request: Request, user_id: int):
    """获取用户角色"""
    db_session: AsyncSession = request.ctx.db_session
    service = UserService(db_session)

    roles = await service.get_user_roles(user_id)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": [
                {"id": r.id, "name": r.name, "description": r.description}
                for r in roles
            ],
        }
    )
