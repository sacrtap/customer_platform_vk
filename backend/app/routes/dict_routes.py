"""字典数据路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.dict_service import DictService
from ..middleware.auth import auth_required

dict_bp = Blueprint("dicts", url_prefix="/api/v1/dicts")


@dict_bp.get("/industry_types")
@auth_required
async def get_industry_types(request: Request):
    """
    获取行业类型列表

    Response:
    - data: list of {id, name, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = DictService(db_session)

    industry_types = await service.get_industry_types()

    return json(
        {
            "code": 0,
            "message": "success",
            "data": [
                {
                    "id": it.id,
                    "name": it.name,
                    "sort_order": it.sort_order,
                }
                for it in industry_types
            ],
        }
    )
