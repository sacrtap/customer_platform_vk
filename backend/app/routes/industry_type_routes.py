"""行业类型管理路由"""

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache.base import cache_service
from ..middleware.auth import auth_required, require_permission
from ..services.industry_type_service import IndustryTypeService

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
                    "created_at": it.created_at.isoformat() if it.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                }
                for it in industry_types
            ],
        }
    )


@industry_type_bp.post("")
@auth_required
@require_permission("industry_types:manage")
async def create_industry_type(request: Request):
    """
    新增行业类型

    Request Body:
    - name: str (required)
    - sort_order: int (required)
    - id: int (optional) 指定行业类型 ID；缺省自增。已被占用（含软删记录）时返回 409

    Response:
    - data: {id, name, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    data = request.json or {}
    name = data.get("name")
    sort_order = data.get("sort_order")
    id = data.get("id")

    if not name or sort_order is None:
        return json(
            {"code": 422, "message": "name 和 sort_order 为必填字段"},
            status=422,
        )

    # id 可选；提供时必须为正整数
    if id is not None and (not isinstance(id, int) or isinstance(id, bool) or id <= 0):
        return json(
            {"code": 422, "message": "id 必须为正整数"},
            status=422,
        )

    try:
        industry_type = await service.create(name, sort_order, id=id)

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
@require_permission("industry_types:manage")
async def update_industry_type(request: Request, id: int):
    """
    更新行业类型

    Request Body:
    - name: str (required)
    - sort_order: int (required)
    - id: int (optional) 新 ID；缺省保持不变。与当前 id 不同时执行主键修改，
      目标 id 已被占用（含软删记录）或行业正被客户引用时返回 409

    Response:
    - data: {id, name, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    data = request.json or {}
    name = data.get("name")
    sort_order = data.get("sort_order")
    new_id = data.get("id")

    if not name or sort_order is None:
        return json(
            {"code": 422, "message": "name 和 sort_order 为必填字段"},
            status=422,
        )

    # 新 id 可选；提供时必须为正整数
    if new_id is not None and (
        not isinstance(new_id, int) or isinstance(new_id, bool) or new_id <= 0
    ):
        return json(
            {"code": 422, "message": "id 必须为正整数"},
            status=422,
        )

    try:
        industry_type = await service.update(id, name, sort_order, new_id=new_id)

        if industry_type is None:
            return json(
                {"code": 404, "message": "行业类型不存在"},
                status=404,
            )

        # 审计留痕：行业属共享主数据，改名须可追溯（防止「_编辑」式脏名无人负责）
        from ..middleware.auth import get_current_user
        from ..utils.audit_helpers import create_audit_entry

        current_user = get_current_user(request)
        await create_audit_entry(
            db_session=db_session,
            user_id=current_user.get("user_id") if current_user else None,
            action="update",
            module="industry_type",
            record_id=industry_type.id,
            record_type="industry_type",
            changes={
                "before": {"id": id},
                "after": {
                    "id": industry_type.id,
                    "name": name,
                    "sort_order": sort_order,
                },
            },
            ip_address=request.headers.get(
                "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
            ),
            auto_commit=True,
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
    finally:
        # 行业类型名称变更后，清除客户列表缓存
        await cache_service.invalidate_customer_cache()


@industry_type_bp.delete("/<id:int>")
@auth_required
@require_permission("industry_types:manage")
async def delete_industry_type(request: Request, id: int):
    """
    软删除行业类型

    Response:
    - success: true/false
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    try:
        success = await service.soft_delete(id)
    except ValueError as e:
        # 引用保护：被客户画像使用的行业禁止删除
        return json(
            {"code": 409, "message": str(e)},
            status=409,
        )

    if not success:
        return json(
            {"code": 404, "message": "行业类型不存在"},
            status=404,
        )

    # 审计留痕：共享主数据删除须可追溯
    from ..middleware.auth import get_current_user
    from ..utils.audit_helpers import create_audit_entry

    current_user = get_current_user(request)
    await create_audit_entry(
        db_session=db_session,
        user_id=current_user.get("user_id") if current_user else None,
        action="delete",
        module="industry_type",
        record_id=id,
        record_type="industry_type",
        changes={"after": {"id": id, "deleted": True}},
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    # 行业类型删除后，清除客户列表缓存
    await cache_service.invalidate_customer_cache()

    return json(
        {
            "code": 0,
            "message": "success",
        }
    )
