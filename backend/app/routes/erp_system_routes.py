"""ERP 系统管理路由"""

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache.base import cache_service
from ..middleware.auth import auth_required, require_permission
from ..services.erp_system_service import ErpSystemService

erp_system_bp = Blueprint("erp_systems", url_prefix="/api/v1/erp-systems")


@erp_system_bp.get("")
@auth_required
async def get_erp_systems(request: Request):
    """
    获取 ERP 系统列表

    Response:
    - data: list of {id, name, value, sort_order, created_at}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = ErpSystemService(db_session)

    erp_systems = await service.get_all()

    return json(
        {
            "code": 0,
            "message": "success",
            "data": [
                {
                    "id": es.id,
                    "name": es.name,
                    "value": es.value,
                    "sort_order": es.sort_order,
                    "created_at": es.created_at.isoformat() if es.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                }
                for es in erp_systems
            ],
        }
    )


@erp_system_bp.post("")
@auth_required
@require_permission("erp_systems:manage")
async def create_erp_system(request: Request):
    """
    新增 ERP 系统

    Request Body:
    - name: str (required)
    - value: str (required)
    - sort_order: int (required)

    Response:
    - data: {id, name, value, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = ErpSystemService(db_session)

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
        erp_system = await service.create(name, value, sort_order)

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": erp_system.id,
                    "name": erp_system.name,
                    "value": erp_system.value,
                    "sort_order": erp_system.sort_order,
                },
            },
            status=201,
        )
    except ValueError as e:
        return json(
            {"code": 409, "message": str(e)},
            status=409,
        )


@erp_system_bp.put("/<id:int>")
@auth_required
@require_permission("erp_systems:manage")
async def update_erp_system(request: Request, id: int):
    """
    更新 ERP 系统

    Request Body:
    - name: str (required)
    - value: str (required)
    - sort_order: int (required)

    Response:
    - data: {id, name, value, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = ErpSystemService(db_session)

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
        erp_system = await service.update(id, name, value, sort_order)

        if erp_system is None:
            return json(
                {"code": 404, "message": "ERP 系统不存在"},
                status=404,
            )

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": erp_system.id,
                    "name": erp_system.name,
                    "value": erp_system.value,
                    "sort_order": erp_system.sort_order,
                },
            }
        )
    except ValueError as e:
        return json(
            {"code": 409, "message": str(e)},
            status=409,
        )
    finally:
        await cache_service.invalidate_customer_cache()


@erp_system_bp.delete("/<id:int>")
@auth_required
@require_permission("erp_systems:manage")
async def delete_erp_system(request: Request, id: int):
    """
    软删除 ERP 系统

    Response:
    - success: true/false
    """
    db_session: AsyncSession = request.ctx.db_session
    service = ErpSystemService(db_session)

    success = await service.soft_delete(id)

    if not success:
        return json(
            {"code": 404, "message": "ERP 系统不存在"},
            status=404,
        )

    await cache_service.invalidate_customer_cache()

    return json(
        {
            "code": 0,
            "message": "success",
        }
    )
