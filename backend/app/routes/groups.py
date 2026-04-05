"""客户群组管理路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from typing import Any
from ..services.groups import CustomerGroupService
from ..middleware.auth import auth_required

groups_bp = Blueprint("groups", url_prefix="/api/v1/customer-groups")


@groups_bp.get("")
@auth_required
async def list_groups(request: Request):
    """获取用户的群组列表"""
    db_session: Any = request.ctx.db_session
    service = CustomerGroupService(db_session)

    groups = await service.get_user_groups(request.ctx.user["user_id"])

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": g.id,
                        "name": g.name,
                        "description": g.description,
                        "group_type": g.group_type,
                        "created_at": g.created_at.isoformat()
                        if g.created_at
                        else None,
                    }
                    for g in groups
                ]
            },
        }
    )


@groups_bp.post("")
@auth_required
async def create_group(request: Request):
    """创建群组"""
    data = request.json
    name = data.get("name")

    if not name:
        return json({"code": 40001, "message": "群组名称不能为空"}, status=400)

    db_session: Any = request.ctx.db_session
    service = CustomerGroupService(db_session)

    group = await service.create_group(
        name=name,
        description=data.get("description"),
        group_type=data.get("group_type", "dynamic"),
        filter_conditions=data.get("filter_conditions"),
        created_by=request.ctx.user["user_id"],
    )

    return json(
        {
            "code": 0,
            "message": "创建成功",
            "data": {"id": group.id, "name": group.name},
        },
        status=201,
    )


@groups_bp.get("/<group_id:int>")
@auth_required
async def get_group(request: Request, group_id: int):
    """获取群组详情"""
    db_session: Any = request.ctx.db_session
    service = CustomerGroupService(db_session)

    group = await service.get_group_detail(group_id)

    if not group:
        return json({"code": 40401, "message": "群组不存在"}, status=404)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": group.id,
                "name": group.name,
                "description": group.description,
                "group_type": group.group_type,
                "filter_conditions": group.filter_conditions,
                "created_at": group.created_at.isoformat()
                if group.created_at
                else None,
            },
        }
    )


@groups_bp.put("/<group_id:int>")
@auth_required
async def update_group(request: Request, group_id: int):
    """更新群组"""
    data = request.json

    db_session: Any = request.ctx.db_session
    service = CustomerGroupService(db_session)

    group = await service.update_group(group_id, data)

    if not group:
        return json({"code": 40401, "message": "群组不存在"}, status=404)

    return json(
        {
            "code": 0,
            "message": "更新成功",
            "data": {"id": group.id, "name": group.name},
        }
    )


@groups_bp.delete("/<group_id:int>")
@auth_required
async def delete_group(request: Request, group_id: int):
    """删除群组"""
    db_session: Any = request.ctx.db_session
    service = CustomerGroupService(db_session)

    success = await service.delete_group(group_id)

    if not success:
        return json({"code": 40401, "message": "群组不存在"}, status=404)

    return json({"code": 0, "message": "删除成功"})


@groups_bp.get("/<group_id:int>/members")
@auth_required
async def get_group_members(request: Request, group_id: int):
    """获取群组成员列表"""
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))

    db_session: Any = request.ctx.db_session
    service = CustomerGroupService(db_session)

    members, total = await service.get_group_members(group_id, page, page_size)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {"id": m.id, "name": m.name, "company_id": m.company_id}
                    for m in members
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@groups_bp.post("/<group_id:int>/members")
@auth_required
async def add_member(request: Request, group_id: int):
    """添加成员（静态群组）"""
    data = request.json
    customer_id = data.get("customer_id")

    if not customer_id:
        return json({"code": 40001, "message": "客户 ID 不能为空"}, status=400)

    db_session: Any = request.ctx.db_session
    service = CustomerGroupService(db_session)

    success = await service.add_member(group_id, customer_id)

    if not success:
        return json({"code": 40002, "message": "添加失败，成员可能已存在"}, status=400)

    return json({"code": 0, "message": "添加成功"})


@groups_bp.delete("/<group_id:int>/members/<customer_id:int>")
@auth_required
async def remove_member(request: Request, group_id: int, customer_id: int):
    """移除成员"""
    db_session: Any = request.ctx.db_session
    service = CustomerGroupService(db_session)

    success = await service.remove_member(group_id, customer_id)

    if not success:
        return json({"code": 40401, "message": "成员不存在"}, status=404)

    return json({"code": 0, "message": "移除成功"})


@groups_bp.post("/<group_id:int>/apply")
@auth_required
async def apply_group_filter(request: Request, group_id: int):
    """应用群组筛选"""
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))

    db_session: Any = request.ctx.db_session
    service = CustomerGroupService(db_session)

    customers, total = await service.apply_group_filter(group_id, page, page_size)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {"id": c.id, "name": c.name, "company_id": c.company_id}
                    for c in customers
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@groups_bp.get("/<group_id:int>/stats")
@auth_required
async def get_group_stats(request: Request, group_id: int):
    """获取群组统计信息"""
    db_session: Any = request.ctx.db_session
    service = CustomerGroupService(db_session)

    stats = await service.get_group_stats(group_id)

    if not stats:
        return json({"code": 40401, "message": "群组不存在"}, status=404)

    return json({"code": 0, "message": "success", "data": stats})
