"""API-Key 管理路由"""

from datetime import datetime
from typing import Optional

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import auth_required, get_current_user, require_permission
from ..services.api_key_service import ApiKeyService

api_keys_bp = Blueprint("api_keys", url_prefix="/api/v1/api-keys")


def _format_api_key(api_key) -> dict:
    """格式化 API-Key 列表项（脱敏显示）"""
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key_prefix": api_key.key_prefix + "****",
        "status": api_key.status,
        "description": api_key.description,
        "created_by": api_key.created_by,
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
        "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
        "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
    }


@api_keys_bp.get("")
@auth_required
@require_permission("api_keys:manage")
async def list_api_keys(request: Request):
    """
    获取 API-Key 列表（分页）

    Query:
    - page: int (default 1)
    - page_size: int (default 20)
    """
    db_session: AsyncSession = request.ctx.db_session
    service = ApiKeyService(db_session)

    page = int(request.args.get("page", "1"))
    page_size = int(request.args.get("page_size", "20"))

    items, total = await service.get_all(page=page, page_size=page_size)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": [_format_api_key(item) for item in items],
            "meta": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        }
    )


@api_keys_bp.post("")
@auth_required
@require_permission("api_keys:manage")
async def create_api_key(request: Request):
    """
    创建 API-Key

    Request Body:
    - name: str (required)
    - description: str (optional)
    - expires_at: str ISO datetime (optional)

    Response:
    - data: {id, name, key, key_prefix, status, ...}  — key 仅此一次返回
    """
    db_session: AsyncSession = request.ctx.db_session
    service = ApiKeyService(db_session)
    user = get_current_user(request)

    data = request.json or {}
    name = data.get("name")
    description = data.get("description")
    expires_at_str: Optional[str] = data.get("expires_at")

    if not name or not str(name).strip():
        return json(
            {"code": 40001, "message": "API-Key 名称不能为空"},
            status=400,
        )

    expires_at = None
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return json(
                {"code": 40002, "message": "过期时间格式不正确，请使用 ISO 8601 格式"},
                status=400,
            )

    try:
        api_key, raw_key = await service.create_key(
            name=name,
            created_by=user["user_id"] if user else None,
            description=description,
            expires_at=expires_at,
        )
    except ValueError as e:
        return json(
            {"code": 40001, "message": str(e)},
            status=400,
        )

    # 返回完整 Key（仅此一次）
    result = _format_api_key(api_key)
    result["key"] = raw_key

    return json(
        {
            "code": 0,
            "message": "success",
            "data": result,
        },
        status=201,
    )


@api_keys_bp.patch("/<id:int>/toggle-status")
@auth_required
@require_permission("api_keys:manage")
async def toggle_api_key_status(request: Request, id: int):
    """
    切换 API-Key 状态（active ↔ disabled）
    """
    db_session: AsyncSession = request.ctx.db_session
    service = ApiKeyService(db_session)

    api_key = await service.toggle_status(id)

    if not api_key:
        return json(
            {"code": 40401, "message": "API-Key 不存在"},
            status=404,
        )

    return json(
        {
            "code": 0,
            "message": "success",
            "data": _format_api_key(api_key),
        }
    )


@api_keys_bp.delete("/<id:int>")
@auth_required
@require_permission("api_keys:manage")
async def delete_api_key(request: Request, id: int):
    """
    删除 API-Key（软删除）
    """
    db_session: AsyncSession = request.ctx.db_session
    service = ApiKeyService(db_session)

    success = await service.soft_delete(id)

    if not success:
        return json(
            {"code": 40401, "message": "API-Key 不存在"},
            status=404,
        )

    return json(
        {
            "code": 0,
            "message": "success",
        }
    )
