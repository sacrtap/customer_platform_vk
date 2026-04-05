# -*- coding: utf-8 -*-
"""权限管理路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.users import Permission
from ..middleware.auth import require_permission

permissions_bp = Blueprint("permissions", url_prefix="/api/v1/permissions")


@permissions_bp.get("")
async def list_permissions(request: Request):
    """
    获取所有权限列表
    """
    db_session: AsyncSession = request.ctx.db_session

    query = select(Permission).order_by(Permission.module, Permission.id)
    result = await db_session.execute(query)
    permissions = list(result.scalars().all())

    return json(
        {
            "code": 0,
            "message": "success",
            "data": [
                {
                    "id": perm.id,
                    "code": perm.code,
                    "name": perm.name,
                    "description": perm.description,
                    "module": perm.module,
                }
                for perm in permissions
            ],
        }
    )


@permissions_bp.post("")
@require_permission("permissions.create")
async def create_permission(request: Request):
    """
    创建权限

    Body:
    {
        "code": "string (required)",
        "name": "string (required)",
        "description": "string (optional)",
        "module": "string (required)"
    }
    """
    data = request.json

    code = data.get("code")
    name = data.get("name")
    description = data.get("description", "")
    module = data.get("module")

    if not code or not name or not module:
        return json(
            {"code": 40001, "message": "权限代码、名称和模块不能为空"}, status=400
        )

    db_session: AsyncSession = request.ctx.db_session

    # 检查权限代码是否已存在
    existing_query = select(Permission).where(Permission.code == code)
    existing_result = await db_session.execute(existing_query)
    if existing_result.scalar_one_or_none():
        return json({"code": 40002, "message": "权限代码已存在"}, status=400)

    permission = Permission(
        code=code, name=name, description=description, module=module
    )
    db_session.add(permission)
    await db_session.commit()
    await db_session.refresh(permission)

    return json(
        {
            "code": 0,
            "message": "创建成功",
            "data": {
                "id": permission.id,
                "code": permission.code,
                "name": permission.name,
                "description": permission.description,
                "module": permission.module,
            },
        },
        status=201,
    )
