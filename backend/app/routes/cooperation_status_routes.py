"""合作状态管理路由"""

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache.base import cache_service
from ..middleware.auth import auth_required, require_permission
from ..services.cooperation_status_service import CooperationStatusService

cooperation_status_bp = Blueprint("cooperation_statuses", url_prefix="/api/v1/cooperation-statuses")


@cooperation_status_bp.get("")
@auth_required
async def get_cooperation_statuses(request: Request):
    """
    获取合作状态列表

    Response:
    - data: list of {id, name, value, sort_order, created_at}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = CooperationStatusService(db_session)

    cooperation_statuses = await service.get_all()

    return json(
        {
            "code": 0,
            "message": "success",
            "data": [
                {
                    "id": cs.id,
                    "name": cs.name,
                    "value": cs.value,
                    "sort_order": cs.sort_order,
                    "created_at": cs.created_at.isoformat() if cs.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                }
                for cs in cooperation_statuses
            ],
        }
    )


@cooperation_status_bp.post("")
@auth_required
@require_permission("cooperation_statuses:manage")
async def create_cooperation_status(request: Request):
    """
    新增合作状态

    Request Body:
    - name: str (required) - 展示名称，如 "合作中"
    - value: str (required) - 存储值，如 "active"
    - sort_order: int (required)

    Response:
    - data: {id, name, value, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = CooperationStatusService(db_session)

    data = request.json or {}
    name = data.get("name")
    value = data.get("value")
    sort_order = data.get("sort_order")

    if not name or not value or sort_order is None:
        return json(
            {"code": 422, "message": "name、value 和 sort_order 为必填字段"},
            status=422,
        )

    try:
        cooperation_status = await service.create(name, value, sort_order)

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": cooperation_status.id,
                    "name": cooperation_status.name,
                    "value": cooperation_status.value,
                    "sort_order": cooperation_status.sort_order,
                },
            },
            status=201,
        )
    except ValueError as e:
        return json(
            {"code": 409, "message": str(e)},
            status=409,
        )


@cooperation_status_bp.put("/<id:int>")
@auth_required
@require_permission("cooperation_statuses:manage")
async def update_cooperation_status(request: Request, id: int):
    """
    更新合作状态

    Request Body:
    - name: str (required)
    - value: str (required)
    - sort_order: int (required)

    Response:
    - data: {id, name, value, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = CooperationStatusService(db_session)

    data = request.json or {}
    name = data.get("name")
    value = data.get("value")
    sort_order = data.get("sort_order")

    if not name or not value or sort_order is None:
        return json(
            {"code": 422, "message": "name、value 和 sort_order 为必填字段"},
            status=422,
        )

    try:
        cooperation_status = await service.update(id, name, value, sort_order)

        if cooperation_status is None:
            return json(
                {"code": 404, "message": "合作状态不存在"},
                status=404,
            )

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": cooperation_status.id,
                    "name": cooperation_status.name,
                    "value": cooperation_status.value,
                    "sort_order": cooperation_status.sort_order,
                },
            }
        )
    except ValueError as e:
        return json(
            {"code": 409, "message": str(e)},
            status=409,
        )
    finally:
        # 合作状态变更后，清除客户列表缓存
        await cache_service.invalidate_customer_cache()


@cooperation_status_bp.delete("/<id:int>")
@auth_required
@require_permission("cooperation_statuses:manage")
async def delete_cooperation_status(request: Request, id: int):
    """
    软删除合作状态

    Response:
    - success: true/false
    """
    db_session: AsyncSession = request.ctx.db_session
    service = CooperationStatusService(db_session)

    success = await service.soft_delete(id)

    if not success:
        return json(
            {"code": 404, "message": "合作状态不存在"},
            status=404,
        )

    # 合作状态删除后，清除客户列表缓存
    await cache_service.invalidate_customer_cache()

    return json(
        {
            "code": 0,
            "message": "success",
        }
    )
