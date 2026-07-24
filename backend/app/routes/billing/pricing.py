"""定价规则路由 — CRUD 和冲突检测"""

from datetime import date

from sanic.request import Request
from sanic.response import json
from sqlalchemy.ext.asyncio import AsyncSession

from ...cache.base import cache_service
from ...middleware.auth import auth_required, get_current_user, require_permission
from ...repository import PricingRepository
from ...services.billing import PricingService
from . import billing_bp


@billing_bp.get("/pricing-rules")
@auth_required
@require_permission("billing:view")
async def get_pricing_rules(request: Request):
    """获取定价规则列表（支持分页）"""
    db: AsyncSession = request.ctx.db_session
    pricing_service = PricingService(PricingRepository(db))

    # 分页参数
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    page_size = min(page_size, 100)

    # 筛选参数
    customer_id = int(request.args.get("customer_id")) if request.args.get("customer_id") else None
    keyword = request.args.get("keyword")  # 客户名称模糊搜索
    device_type = request.args.get("device_type")
    layer_type = request.args.get("layer_type")
    pricing_type = request.args.get("pricing_type")

    rules, total = await pricing_service.get_pricing_rules(
        customer_id=customer_id,
        keyword=keyword,
        device_type=device_type,
        layer_type=layer_type,
        pricing_type=pricing_type,
        page=page,
        page_size=page_size,
    )

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": r.id,
                        "customer_id": r.customer_id,
                        "customer_name": r.customer.name if r.customer else None,
                        "device_type": r.device_type,
                        "layer_type": r.layer_type or "single",
                        "pricing_type": r.pricing_type,
                        "unit_price": float(r.unit_price) if r.unit_price else None,
                        "tiers": r.tiers,
                        "package_type": r.package_type,
                        "package_limits": r.package_limits,
                        "effective_date": (
                            r.effective_date.isoformat() if r.effective_date else None
                        ),
                        "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
                    }
                    for r in rules
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@billing_bp.post("/pricing-rules")
@auth_required
@require_permission("billing:edit")
async def create_pricing_rule(request: Request):
    """
    创建定价规则

    Body:
    {
        "customer_id": 1,
        "device_type": "X",
        "pricing_type": "fixed",
        "unit_price": 10.00,
        "effective_date": "2026-04-01",
        "expiry_date": "2026-12-31"
    }
    """
    db: AsyncSession = request.ctx.db_session
    data = request.json
    user = get_current_user(request)

    pricing_service = PricingService(PricingRepository(db))
    data["created_by"] = user["user_id"] if user else 1

    # 日期转换
    if "effective_date" in data and isinstance(data["effective_date"], str):
        data["effective_date"] = date.fromisoformat(data["effective_date"])
    if "expiry_date" in data and isinstance(data["expiry_date"], str):
        data["expiry_date"] = date.fromisoformat(data["expiry_date"])

    try:
        rule = await pricing_service.create_pricing_rule(data)
    except ValueError as e:
        return json({"code": 40001, "message": str(e)}, status=400)

    # 定价规则变更后清除相关缓存
    await cache_service.invalidate_billing_cache()

    return json(
        {
            "code": 0,
            "message": "创建成功",
            "data": {
                "id": rule.id,
                "device_type": rule.device_type,
                "layer_type": rule.layer_type or "single",
                "pricing_type": rule.pricing_type,
                "unit_price": float(rule.unit_price) if rule.unit_price else None,
            },
        },
        status=201,
    )


@billing_bp.put("/pricing-rules/<rule_id:int>")
@auth_required
@require_permission("billing:edit")
async def update_pricing_rule(request: Request, rule_id: int):
    """更新定价规则"""
    db: AsyncSession = request.ctx.db_session
    data = request.json

    pricing_service = PricingService(PricingRepository(db))

    # 日期转换
    if "effective_date" in data and isinstance(data["effective_date"], str):
        data["effective_date"] = date.fromisoformat(data["effective_date"])
    if "expiry_date" in data and isinstance(data["expiry_date"], str):
        data["expiry_date"] = date.fromisoformat(data["expiry_date"])

    try:
        rule = await pricing_service.update_pricing_rule(rule_id, data)
    except ValueError as e:
        return json({"code": 40001, "message": str(e)}, status=400)

    if not rule:
        return json({"code": 40401, "message": "规则不存在"}, status=404)

    # 定价规则变更后清除相关缓存
    await cache_service.invalidate_billing_cache()

    return json(
        {
            "code": 0,
            "message": "更新成功",
            "data": {
                "id": rule.id,
                "device_type": rule.device_type,
                "layer_type": rule.layer_type or "single",
                "pricing_type": rule.pricing_type,
            },
        }
    )


@billing_bp.delete("/pricing-rules/<rule_id:int>")
@auth_required
@require_permission("billing:delete")
async def delete_pricing_rule(request: Request, rule_id: int):
    """删除定价规则"""
    db: AsyncSession = request.ctx.db_session
    pricing_service = PricingService(PricingRepository(db))

    success = await pricing_service.delete_pricing_rule(rule_id)

    if not success:
        return json({"code": 40401, "message": "规则不存在"}, status=404)

    # 定价规则变更后清除相关缓存
    await cache_service.invalidate_billing_cache()

    return json({"code": 0, "message": "删除成功"})


@billing_bp.get("/pricing-rules/check-conflict")
@auth_required
@require_permission("billing:view")
async def check_pricing_rule_conflict(request: Request):
    """
    检查定价规则有效期冲突

    Query params:
    - customer_id (必填, int)
    - device_type (必填, string)
    - layer_type (必填, string)
    - effective_date (必填, date)
    - expiry_date (可选, date)
    - exclude_id (可选, int) — 编辑时排除自身
    """
    db: AsyncSession = request.ctx.db_session

    # 参数校验
    try:
        customer_id = int(request.args.get("customer_id", 0))
        device_type = request.args.get("device_type", "")
        layer_type = request.args.get("layer_type")
        effective_date_str = request.args.get("effective_date", "")
        expiry_date_str = request.args.get("expiry_date")
        exclude_id_str = request.args.get("exclude_id")

        if not customer_id or not device_type or not effective_date_str:
            return json(
                {
                    "code": 40001,
                    "message": "缺少必填参数：customer_id, device_type, effective_date",
                },
                status=400,
            )

        effective_date = date.fromisoformat(effective_date_str)
        expiry_date = date.fromisoformat(expiry_date_str) if expiry_date_str else None
        exclude_id = int(exclude_id_str) if exclude_id_str else None
    except (ValueError, TypeError):
        return json(
            {
                "code": 40001,
                "message": "参数格式错误",
            },
            status=400,
        )

    pricing_service = PricingService(PricingRepository(db))

    conflicting_rules = await pricing_service.check_pricing_rule_conflict(
        customer_id=customer_id,
        device_type=device_type,
        layer_type=layer_type,
        effective_date=effective_date,
        expiry_date=expiry_date,
        exclude_id=exclude_id,
    )

    return json(
        {
            "code": 0,
            "data": {
                "has_conflict": len(conflicting_rules) > 0,
                "conflicting_rules": [
                    {
                        "id": r.id,
                        "pricing_type": r.pricing_type,
                        "effective_date": (
                            r.effective_date.isoformat() if r.effective_date else None
                        ),
                        "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
                    }
                    for r in conflicting_rules
                ],
            },
        }
    )


# ==================== 结算单管理 ====================
