# -*- coding: utf-8 -*-
"""角色管理路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.roles import RoleService
from ..middleware.auth import require_permission, auth_required

roles_bp = Blueprint("roles", url_prefix="/api/v1/roles")


@roles_bp.get("")
@auth_required
async def list_roles(request: Request):
    """
    获取角色列表

    Query:
    - page: 页码 (默认 1)
    - page_size: 每页数量 (默认 20)
    """
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))

    # 限制 page_size 范围
    page_size = min(page_size, 100)

    db_session: AsyncSession = request.ctx.db_session
    service = RoleService(db_session)

    roles, total = await service.get_all_roles(page=page, page_size=page_size)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": role.id,
                        "name": role.name,
                        "description": role.description,
                        "is_system": role.is_system,
                        "created_at": role.created_at.isoformat()
                        if role.created_at
                        else None,
                    }
                    for role in roles
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@roles_bp.get("/<role_id:int>")
@auth_required
async def get_role(request: Request, role_id: int):
    """获取角色详情"""
    db_session: AsyncSession = request.ctx.db_session
    service = RoleService(db_session)

    role = await service.get_role_by_id(role_id)

    if not role:
        return json({"code": 40401, "message": "角色不存在"}, status=404)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "is_system": role.is_system,
                "permissions": [
                    {"id": p.id, "code": p.code, "name": p.name}
                    for p in role.permissions
                ],
                "created_at": role.created_at.isoformat() if role.created_at else None,
            },
        }
    )


@roles_bp.post("")
@require_permission("roles:create")
async def create_role(request: Request):
    """
    创建角色

    Body:
    {
        "name": "string (required)",
        "description": "string (optional)",
        "permission_ids": [1, 2, 3] (optional)
    }
    """
    data = request.json

    name = data.get("name")
    description = data.get("description", "")
    permission_ids = data.get("permission_ids", [])

    if not name:
        return json({"code": 40001, "message": "角色名称不能为空"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = RoleService(db_session)

    try:
        role = await service.create_role(
            name=name, description=description, permission_ids=permission_ids
        )
    except ValueError as e:
        return json({"code": 40002, "message": str(e)}, status=400)

    return json(
        {
            "code": 0,
            "message": "创建成功",
            "data": {
                "id": role.id,
                "name": role.name,
                "description": role.description,
            },
        },
        status=201,
    )


@roles_bp.put("/<role_id:int>")
@require_permission("roles:update")
async def update_role(request: Request, role_id: int):
    """
    更新角色信息

    Body:
    {
        "name": "string (optional)",
        "description": "string (optional)",
        "permission_ids": [1, 2, 3] (optional)
    }
    """
    data = request.json

    db_session: AsyncSession = request.ctx.db_session
    service = RoleService(db_session)

    try:
        role = await service.update_role(
            role_id=role_id,
            name=data.get("name"),
            description=data.get("description"),
            permission_ids=data.get("permission_ids"),
        )
    except ValueError as e:
        return json({"code": 40001, "message": str(e)}, status=400)

    if not role:
        return json({"code": 40401, "message": "角色不存在"}, status=404)

    return json(
        {
            "code": 0,
            "message": "更新成功",
            "data": {
                "id": role.id,
                "name": role.name,
                "description": role.description,
            },
        }
    )


@roles_bp.delete("/<role_id:int>")
@require_permission("roles:delete")
async def delete_role(request: Request, role_id: int):
    """删除角色（软删除）"""
    db_session: AsyncSession = request.ctx.db_session
    service = RoleService(db_session)

    # 检查是否是系统角色
    role = await service.get_role_by_id(role_id)
    if role and role.is_system:
        return json({"code": 40001, "message": "系统角色不能删除"}, status=400)

    success = await service.delete_role(role_id)

    if not success:
        return json({"code": 40401, "message": "角色不存在"}, status=404)

    return json({"code": 0, "message": "删除成功"})


@roles_bp.post("/<role_id:int>/permissions")
@require_permission("roles:update")
async def assign_permissions(request: Request, role_id: int):
    """
    为角色分配权限

    Body:
    {
        "permission_ids": [1, 2, 3]
    }
    """
    data = request.json
    permission_ids = data.get("permission_ids", [])

    if not permission_ids:
        return json({"code": 40001, "message": "权限 ID 列表不能为空"}, status=400)

    db_session: AsyncSession = request.ctx.db_session
    service = RoleService(db_session)

    success = await service.assign_permissions(role_id, permission_ids)

    if not success:
        return json({"code": 40401, "message": "角色不存在"}, status=404)

    return json({"code": 0, "message": "权限分配成功"})
