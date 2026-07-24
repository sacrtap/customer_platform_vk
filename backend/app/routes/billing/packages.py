"""套餐计划路由 — CRUD 管理"""

from decimal import Decimal

from sanic.request import Request
from sanic.response import json
from sqlalchemy.ext.asyncio import AsyncSession

from ...cache.base import cache_service
from ...middleware.auth import auth_required, get_current_user, require_permission
from ...utils.audit_helpers import create_audit_entry
from . import billing_bp


def _package_plan_to_dict(plan):
    """将 PackagePlan 对象序列化为字典"""
    return {
        "id": plan.id,
        "name": plan.name,
        "package_type": plan.package_type,
        "device_type": plan.device_type,
        "layer_type": plan.layer_type,
        "is_unlimited": plan.is_unlimited,
        "limit_count": plan.limit_count,
        "base_fee": float(plan.base_fee) if plan.base_fee else 0,
        "description": plan.description,
        "status": plan.status,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }


@billing_bp.get("/package-plans")
@auth_required
@require_permission("billing:view")
async def get_package_plans(request: Request):
    """获取包年套餐列表（支持分页和筛选）"""
    db: AsyncSession = request.ctx.db_session

    from sqlalchemy import func, select

    from ...models.billing import PackagePlan

    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    page_size = min(page_size, 100)

    keyword = request.args.get("keyword")
    status = request.args.get("status")
    is_unlimited = request.args.get("is_unlimited")

    base_stmt = select(PackagePlan).where(PackagePlan.deleted_at.is_(None))

    if keyword:
        base_stmt = base_stmt.where(
            (PackagePlan.name.ilike(f"%{keyword}%"))
            | (PackagePlan.package_type.ilike(f"%{keyword}%"))
        )
    if status:
        base_stmt = base_stmt.where(PackagePlan.status == status)
    if is_unlimited is not None and is_unlimited.strip() != "":
        if is_unlimited.lower() not in ("true", "false"):
            return json(
                {"code": 40001, "message": "is_unlimited 参数必须为 'true' 或 'false'"},
                status=400,
            )
        is_unlimited_bool = is_unlimited.lower() == "true"
        base_stmt = base_stmt.where(PackagePlan.is_unlimited == is_unlimited_bool)

    # 总数
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar()

    # 分页
    stmt = base_stmt.order_by(PackagePlan.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    plans = result.scalars().all()

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [_package_plan_to_dict(p) for p in plans],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )


@billing_bp.get("/package-plans/<plan_id:int>")
@auth_required
@require_permission("billing:view")
async def get_package_plan(request: Request, plan_id: int):
    """获取包年套餐详情"""
    db: AsyncSession = request.ctx.db_session

    from sqlalchemy import select

    from ...models.billing import PackagePlan

    result = await db.execute(
        select(PackagePlan).where(PackagePlan.id == plan_id, PackagePlan.deleted_at.is_(None))
    )
    plan = result.scalar_one_or_none()

    if not plan:
        return json({"code": 40401, "message": "套餐不存在"}, status=404)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": _package_plan_to_dict(plan),
        }
    )


@billing_bp.post("/package-plans")
@auth_required
@require_permission("billing:edit")
async def create_package_plan(request: Request):
    """
    创建包年套餐

    Body:
    {
        "name": "A 套餐",
        "package_type": "A",
        "device_type": "X",        // 可选
        "layer_type": "single",    // 可选
        "is_unlimited": false,
        "limit_count": 10000,      // is_unlimited=false 时必填
        "base_fee": 50000.00,
        "description": "...",      // 可选
        "status": "active"         // 可选，默认 active
    }
    """
    db: AsyncSession = request.ctx.db_session
    data = request.json
    user = get_current_user(request)

    from sqlalchemy import select

    from ...models.billing import PackagePlan

    # 参数校验
    name = data.get("name", "").strip()
    package_type = data.get("package_type", "").strip()
    is_unlimited = bool(data.get("is_unlimited", False))
    base_fee = data.get("base_fee")

    if not name:
        return json({"code": 40001, "message": "套餐名称不能为空"}, status=400)
    if not package_type:
        return json({"code": 40001, "message": "套餐类型标识不能为空"}, status=400)
    if base_fee is None:
        return json({"code": 40001, "message": "套餐基础费用不能为空"}, status=400)

    try:
        base_fee = Decimal(str(base_fee))
        if base_fee < 0:
            return json({"code": 40001, "message": "基础费用不能为负数"}, status=400)
    except (ValueError, TypeError):
        return json({"code": 40001, "message": "基础费用格式错误"}, status=400)

    # 限量校验：非不限量时 limit_count 必填
    limit_count = data.get("limit_count")
    if not is_unlimited:
        if limit_count is None:
            return json(
                {"code": 40001, "message": "限量套餐必须填写具体数量"},
                status=400,
            )
        try:
            limit_count = int(limit_count)
            if limit_count <= 0:
                return json(
                    {"code": 40001, "message": "限量数量必须大于 0"},
                    status=400,
                )
        except (ValueError, TypeError):
            return json({"code": 40001, "message": "限量数量格式错误"}, status=400)
    else:
        # 不限量时清空 limit_count
        limit_count = None

    # 唯一性校验：package_type 不能重复
    existing = await db.execute(
        select(PackagePlan).where(
            PackagePlan.package_type == package_type,
            PackagePlan.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        return json(
            {"code": 40001, "message": f"套餐类型标识 '{package_type}' 已存在"},
            status=400,
        )

    plan = PackagePlan(
        name=name,
        package_type=package_type,
        device_type=data.get("device_type"),
        layer_type=data.get("layer_type"),
        is_unlimited=is_unlimited,
        limit_count=limit_count,
        base_fee=base_fee,
        description=data.get("description"),
        status=data.get("status", "active"),
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    # 审计日志
    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="create",
        module="billing",
        record_id=plan.id,
        record_type="package_plan",
        changes={"after": _package_plan_to_dict(plan)},
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    # 清除缓存
    await cache_service.invalidate_billing_cache()

    return json(
        {
            "code": 0,
            "message": "创建成功",
            "data": _package_plan_to_dict(plan),
        },
        status=201,
    )


@billing_bp.put("/package-plans/<plan_id:int>")
@auth_required
@require_permission("billing:edit")
async def update_package_plan(request: Request, plan_id: int):
    """更新包年套餐"""
    db: AsyncSession = request.ctx.db_session
    data = request.json
    user = get_current_user(request)

    from sqlalchemy import select

    from ...models.billing import PackagePlan

    result = await db.execute(
        select(PackagePlan).where(PackagePlan.id == plan_id, PackagePlan.deleted_at.is_(None))
    )
    plan = result.scalar_one_or_none()

    if not plan:
        return json({"code": 40401, "message": "套餐不存在"}, status=404)

    before_data = _package_plan_to_dict(plan)

    # 可更新字段
    updatable_fields = [
        "name",
        "device_type",
        "layer_type",
        "base_fee",
        "description",
        "status",
    ]

    for field in updatable_fields:
        if field in data:
            if field == "base_fee" and data[field] is not None:
                try:
                    setattr(plan, field, Decimal(str(data[field])))
                except (ValueError, TypeError):
                    return json(
                        {"code": 40001, "message": "基础费用格式错误"},
                        status=400,
                    )
            else:
                setattr(plan, field, data[field])

    # 处理 is_unlimited 和 limit_count
    if "is_unlimited" in data:
        is_unlimited = bool(data["is_unlimited"])
        plan.is_unlimited = is_unlimited  # pyright: ignore[reportAttributeAccessIssue]

        if is_unlimited:
            # 切换为不限量时清空 limit_count
            plan.limit_count = None  # pyright: ignore[reportAttributeAccessIssue]
        else:
            # 切换为限量时，limit_count 必须有值
            if "limit_count" in data and data["limit_count"] is not None:
                try:
                    limit_count = int(data["limit_count"])
                    if limit_count <= 0:
                        return json(
                            {"code": 40001, "message": "限量数量必须大于 0"},
                            status=400,
                        )
                    plan.limit_count = limit_count  # pyright: ignore[reportAttributeAccessIssue]
                except (ValueError, TypeError):
                    return json(
                        {"code": 40001, "message": "限量数量格式错误"},
                        status=400,
                    )
            elif plan.limit_count is None:
                return json(
                    {"code": 40001, "message": "限量套餐必须填写具体数量"},
                    status=400,
                )
    elif "limit_count" in data and not plan.is_unlimited:  # pyright: ignore[reportGeneralTypeIssues]
        # 单独更新 limit_count（当前为限量模式）
        try:
            limit_count = int(data["limit_count"])
            if limit_count <= 0:
                return json(
                    {"code": 40001, "message": "限量数量必须大于 0"},
                    status=400,
                )
            plan.limit_count = limit_count  # pyright: ignore[reportAttributeAccessIssue]
        except (ValueError, TypeError):
            return json({"code": 40001, "message": "限量数量格式错误"}, status=400)

    # 唯一性校验：package_type（如果修改了）
    if "package_type" in data:
        new_type = data["package_type"].strip()
        if new_type and new_type != plan.package_type:
            existing = await db.execute(
                select(PackagePlan).where(
                    PackagePlan.package_type == new_type,
                    PackagePlan.deleted_at.is_(None),
                    PackagePlan.id != plan_id,
                )
            )
            if existing.scalar_one_or_none():
                return json(
                    {"code": 40001, "message": f"套餐类型标识 '{new_type}' 已存在"},
                    status=400,
                )
            plan.package_type = new_type

    await db.commit()
    await db.refresh(plan)

    after_data = _package_plan_to_dict(plan)

    # 审计日志
    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="update",
        module="billing",
        record_id=plan.id,  # pyright: ignore[reportArgumentType]
        record_type="package_plan",
        changes={"before": before_data, "after": after_data},
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    # 清除缓存
    await cache_service.invalidate_billing_cache()

    return json(
        {
            "code": 0,
            "message": "更新成功",
            "data": after_data,
        }
    )


@billing_bp.delete("/package-plans/<plan_id:int>")
@auth_required
@require_permission("billing:delete")
async def delete_package_plan(request: Request, plan_id: int):
    """删除包年套餐（软删除）"""
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)

    from sqlalchemy import select

    from ...models.billing import PackagePlan

    result = await db.execute(
        select(PackagePlan).where(PackagePlan.id == plan_id, PackagePlan.deleted_at.is_(None))
    )
    plan = result.scalar_one_or_none()

    if not plan:
        return json({"code": 40401, "message": "套餐不存在"}, status=404)

    before_data = _package_plan_to_dict(plan)

    from sqlalchemy import func

    plan.deleted_at = func.now()  # pyright: ignore[reportAttributeAccessIssue]
    await db.commit()

    # 审计日志
    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="delete",
        module="billing",
        record_id=plan_id,
        record_type="package_plan",
        changes={"before": before_data},
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    # 清除缓存
    await cache_service.invalidate_billing_cache()

    return json({"code": 0, "message": "删除成功"})
