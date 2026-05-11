"""行业类型管理路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.industry_type_service import IndustryTypeService
from ..middleware.auth import auth_required

industry_type_bp = Blueprint("industry_types", url_prefix="/api/v1/industry-types")


@industry_type_bp.get("")
@auth_required
async def get_industry_types(request: Request):
    """
    获取行业类型列表

    Response:
    - data: list of {id, name, sort_order, created_at}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    industry_types = await service.get_all()

    return json(
        {
            "code": 0,
            "message": "success",
            "data": [
                {
                    "id": it.id,
                    "name": it.name,
                    "sort_order": it.sort_order,
                    "created_at": it.created_at.isoformat() if it.created_at else None,
                }
                for it in industry_types
            ],
        }
    )


@industry_type_bp.post("")
@auth_required
async def create_industry_type(request: Request):
    """
    新增行业类型

    Request Body:
    - name: str (required)
    - sort_order: int (required)

    Response:
    - data: {id, name, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    data = request.json or {}
    name = data.get("name")
    sort_order = data.get("sort_order")

    if not name or sort_order is None:
        return json(
            {"code": 422, "message": "name 和 sort_order 为必填字段"},
            status=422,
        )

    try:
        industry_type = await service.create(name, sort_order)

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": industry_type.id,
                    "name": industry_type.name,
                    "sort_order": industry_type.sort_order,
                },
            },
            status=201,
        )
    except ValueError as e:
        return json(
            {"code": 409, "message": str(e)},
            status=409,
        )


@industry_type_bp.put("/<id:int>")
@auth_required
async def update_industry_type(request: Request, id: int):
    """
    更新行业类型

    Request Body:
    - name: str (required)
    - sort_order: int (required)

    Response:
    - data: {id, name, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    data = request.json or {}
    name = data.get("name")
    sort_order = data.get("sort_order")

    if not name or sort_order is None:
        return json(
            {"code": 422, "message": "name 和 sort_order 为必填字段"},
            status=422,
        )

    try:
        industry_type = await service.update(id, name, sort_order)

        if industry_type is None:
            return json(
                {"code": 404, "message": "行业类型不存在"},
                status=404,
            )

        return json(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "id": industry_type.id,
                    "name": industry_type.name,
                    "sort_order": industry_type.sort_order,
                },
            }
        )
    except ValueError as e:
        return json(
            {"code": 409, "message": str(e)},
            status=409,
        )


@industry_type_bp.delete("/<id:int>")
@auth_required
async def delete_industry_type(request: Request, id: int):
    """
    软删除行业类型

    Response:
    - success: true/false
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    success = await service.soft_delete(id)

    if not success:
        return json(
            {"code": 404, "message": "行业类型不存在"},
            status=404,
        )

    return json(
        {
            "code": 0,
            "message": "success",
        }
    )
