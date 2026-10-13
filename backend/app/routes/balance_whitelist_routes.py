"""余额白名单管理路由"""

from decimal import Decimal, InvalidOperation

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import ErrorCodes
from ..middleware.auth import auth_required, require_permission
from ..services.balance_whitelist_service import BalanceWhitelistService

balance_whitelist_bp = Blueprint("balance_whitelists", url_prefix="/api/v1/balance-whitelists")


def _parse_balance(value) -> Decimal:
    """解析静态余额（前端可能传 number 或 string）"""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("静态余额格式不正确")


@balance_whitelist_bp.get("")
@auth_required
@require_permission("balance_whitelist:manage")
async def list_balance_whitelists(request: Request):
    """
    获取余额白名单列表（分页）

    Query:
    - page: int (default 1)
    - page_size: int (default 20)
    - keyword: 客户名称模糊 / 公司 ID 精确过滤
    """
    db_session: AsyncSession = request.ctx.db_session
    service = BalanceWhitelistService(db_session)

    page = max(int(request.args.get("page", "1")), 1)
    page_size = int(request.args.get("page_size", "20"))
    keyword = request.args.get("keyword")

    items, total = await service.get_all(page=page, page_size=page_size, keyword=keyword)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {"items": items, "total": total},
            "meta": {"page": page, "page_size": page_size, "total": total},
        }
    )


@balance_whitelist_bp.post("/batch-import")
@auth_required
@require_permission("balance_whitelist:manage")
async def batch_import_by_erp(request: Request):
    """
    按 ERP 名单批量导入该 ERP 下所有有效客户（幂等）

    Request Body:
    - erp_system_value: str (required) — ERP 系统存储值（如 "erp_cloud"）

    Query:
    - dry_run: 可选，true/1/yes/on 时仅预检（计算将导入/跳过数量，不落库），
      前端据此二次确认后真实导入

    Response:
    - data: {imported, skipped}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = BalanceWhitelistService(db_session)

    data = request.json or {}
    erp_system_value = data.get("erp_system_value")
    if not erp_system_value or not str(erp_system_value).strip():
        return json(
            {"code": ErrorCodes.MISSING_PARAMETER, "message": "缺少必要参数: erp_system_value"},
            status=400,
        )

    dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes", "on")

    try:
        imported, skipped = await service.batch_import_by_erp(
            str(erp_system_value).strip(), dry_run=dry_run
        )
    except ValueError as e:
        return json({"code": ErrorCodes.BAD_REQUEST, "message": str(e)}, status=400)

    return json(
        {
            "code": 0,
            "message": "预检查完成" if dry_run else "success",
            "data": {
                "dry_run": dry_run,
                "imported": imported,
                "skipped": skipped,
            },
        }
    )


@balance_whitelist_bp.post("")
@auth_required
@require_permission("balance_whitelist:manage")
async def add_balance_whitelist(request: Request):
    """
    单独添加单个客户到白名单

    Request Body:
    - customer_id: int (required) — 客户主键 id
    - static_balance: number (optional, default 1000) — 静态余额（元）
    """
    db_session: AsyncSession = request.ctx.db_session
    service = BalanceWhitelistService(db_session)

    data = request.json or {}
    customer_id = data.get("customer_id")
    if customer_id is None:
        return json(
            {"code": ErrorCodes.MISSING_PARAMETER, "message": "缺少必要参数: customer_id"},
            status=400,
        )

    static_balance_raw = data.get("static_balance", 1000)
    try:
        static_balance = _parse_balance(static_balance_raw)
    except ValueError as e:
        return json({"code": ErrorCodes.INVALID_FORMAT, "message": str(e)}, status=400)

    try:
        record = await service.add(int(customer_id), static_balance)
    except ValueError as e:
        return json({"code": ErrorCodes.BAD_REQUEST, "message": str(e)}, status=400)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": record.id,
                "customer_id": record.customer_id,
                "static_balance": float(record.static_balance),
            },
        },
        status=201,
    )


@balance_whitelist_bp.put("/<id:int>")
@auth_required
@require_permission("balance_whitelist:manage")
async def update_balance_whitelist(request: Request, id: int):
    """
    编辑白名单客户静态余额

    Request Body:
    - static_balance: number (required)
    """
    db_session: AsyncSession = request.ctx.db_session
    service = BalanceWhitelistService(db_session)

    data = request.json or {}
    static_balance_raw = data.get("static_balance")
    if static_balance_raw is None:
        return json(
            {"code": ErrorCodes.MISSING_PARAMETER, "message": "缺少必要参数: static_balance"},
            status=400,
        )

    try:
        static_balance = _parse_balance(static_balance_raw)
    except ValueError as e:
        return json({"code": ErrorCodes.INVALID_FORMAT, "message": str(e)}, status=400)

    try:
        record = await service.update(id, static_balance)
    except ValueError as e:
        return json({"code": ErrorCodes.BAD_REQUEST, "message": str(e)}, status=400)

    if record is None:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "白名单记录不存在"}, status=404)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": record.id,
                "customer_id": record.customer_id,
                "static_balance": float(record.static_balance),
            },
        }
    )


@balance_whitelist_bp.delete("/<id:int>")
@auth_required
@require_permission("balance_whitelist:manage")
async def remove_balance_whitelist(request: Request, id: int):
    """移出白名单（软删除）"""
    db_session: AsyncSession = request.ctx.db_session
    service = BalanceWhitelistService(db_session)

    success = await service.soft_delete(id)
    if not success:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "白名单记录不存在"}, status=404)

    return json({"code": 0, "message": "success"})
