"""套餐计划路由 — CRUD 管理"""

import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sanic.request import Request
from sanic.response import json, raw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...cache.base import cache_service
from ...middleware.auth import auth_required, get_current_user, require_permission
from ...utils.audit_helpers import build_batch_audit_summary, create_audit_entry
from ...utils.excel_import import read_import_dataframe
from . import billing_bp

logger = logging.getLogger(__name__)


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
        "over_limit_unit_price": float(plan.over_limit_unit_price)
        if plan.over_limit_unit_price
        else None,  # pyright: ignore[reportAttributeAccessIssue]
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
        "over_limit_unit_price": 5.00,  // 限量套餐超额单价（可选，不填则自动按 base_fee/limit_count 计算）
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

        # 超额单价：可选，不填则存 NULL（结算时自动按 base_fee / limit_count 计算）
        over_limit_unit_price_raw = data.get("over_limit_unit_price")
        if over_limit_unit_price_raw is not None:
            try:
                over_limit_unit_price = Decimal(str(over_limit_unit_price_raw))
                if over_limit_unit_price < 0:
                    return json(
                        {"code": 40001, "message": "超额单价不能为负数"},
                        status=400,
                    )
            except (ValueError, TypeError):
                return json({"code": 40001, "message": "超额单价格式错误"}, status=400)
        else:
            # 不填则存 NULL，结算时动态计算 base_fee / limit_count
            over_limit_unit_price = None
    else:
        # 不限量时清空 limit_count 和 over_limit_unit_price
        limit_count = None
        over_limit_unit_price = None

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
        over_limit_unit_price=over_limit_unit_price,
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
        "over_limit_unit_price",
        "description",
        "status",
    ]

    for field in updatable_fields:
        if field in data:
            if field in ("base_fee", "over_limit_unit_price") and data[field] is not None:
                try:
                    setattr(plan, field, Decimal(str(data[field])))  # pyright: ignore[reportAttributeAccessIssue]
                except (ValueError, TypeError):
                    if field == "base_fee":
                        return json(
                            {"code": 40001, "message": "基础费用格式错误"},
                            status=400,
                        )
                    else:
                        return json(
                            {"code": 40001, "message": "超额单价格式错误"},
                            status=400,
                        )
            else:
                setattr(plan, field, data[field])  # pyright: ignore[reportAttributeAccessIssue]

    # 处理 is_unlimited 和 limit_count
    if "is_unlimited" in data:
        is_unlimited = bool(data["is_unlimited"])
        plan.is_unlimited = is_unlimited  # pyright: ignore[reportAttributeAccessIssue]

        if is_unlimited:
            # 切换为不限量时清空 limit_count 和 over_limit_unit_price
            plan.limit_count = None  # pyright: ignore[reportAttributeAccessIssue]
            plan.over_limit_unit_price = None  # pyright: ignore[reportAttributeAccessIssue]
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

    from sqlalchemy import func, select

    from ...models.billing import PackagePlan, PricingRule

    result = await db.execute(
        select(PackagePlan).where(PackagePlan.id == plan_id, PackagePlan.deleted_at.is_(None))
    )
    plan = result.scalar_one_or_none()

    if not plan:
        return json({"code": 40401, "message": "套餐不存在"}, status=404)

    # 检查是否有关联的计费规则
    related_rules_count = (
        await db.execute(
            select(func.count(PricingRule.id)).where(
                PricingRule.package_type == plan.package_type,
                PricingRule.deleted_at.is_(None),
            )
        )
    ).scalar() or 0

    if related_rules_count > 0:
        return json(
            {
                "code": 40900,
                "message": f"该套餐被 {related_rules_count} 条计费规则引用，删除后这些规则将失效。请先处理关联规则。",
                "data": {"related_rules_count": related_rules_count},
            },
            status=409,
        )

    before_data = _package_plan_to_dict(plan)

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


# ==================== 包年套餐导入导出 ====================


@billing_bp.post("/package-plans/import")
@auth_required
@require_permission("billing:package_import")
async def import_package_plans(request: Request):
    """
    Excel 批量导入包年套餐

    Form:
    - file: Excel 文件 (.xlsx)

    Excel 列要求:
    - name (必填) - 套餐名称
    - package_type (必填) - 套餐类型标识（唯一）
    - base_fee (必填) - 基础费用（元）
    - device_type (可选) - X/N/L
    - layer_type (可选) - single/multi
    - is_unlimited (可选, 是/否 或 true/false) - 是否不限量，默认否
    - limit_count (可选) - 限量数量（非不限量时必填且 >0）
    - over_limit_unit_price (可选) - 超额单价
    - description (可选) - 描述
    - status (可选, active/inactive) - 状态，默认 active
    """
    import pandas as pd

    from ...models.billing import PackagePlan

    files = request.files
    if "file" not in files:  # pyright: ignore[reportOperatorIssue]
        return json({"code": 40001, "message": "请上传 Excel 文件"}, status=400)

    excel_file = files["file"][0]  # pyright: ignore[reportOptionalSubscript]
    if not excel_file.name.endswith(".xlsx"):
        return json({"code": 40002, "message": "请上传 .xlsx 格式的文件"}, status=400)

    try:
        # 读取 Excel 文件（自动丢弃模板第 2 行的中文说明行）
        df = read_import_dataframe(excel_file.body, "name")

        # 必填列检查
        required_columns = ["name", "package_type", "base_fee"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return json(
                {
                    "code": 40003,
                    "message": f"Excel 缺少必填列：{', '.join(missing_columns)}",
                },
                status=400,
            )

        # 行数限制
        if len(df) > 1000:
            return json(
                {"code": 40004, "message": "单次最多导入 1000 条记录"},
                status=400,
            )

        db_session: AsyncSession = request.ctx.db_session

        # 预加载已存在的 package_type（含软删除过滤）
        existing_rows = await db_session.execute(
            select(PackagePlan.package_type).where(PackagePlan.deleted_at.is_(None))
        )
        existing_types = set(existing_rows.scalars().all())

        current_user = get_current_user(request)
        operator_id = current_user.get("user_id") if current_user else 1

        # 逐行校验并创建
        errors = []
        success_count = 0
        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel 行号（含表头）

            try:
                # 名称
                name_raw = row.get("name")
                if pd.isna(name_raw) or name_raw is None or str(name_raw).strip() == "":
                    errors.append(f"第 {row_num} 行：套餐名称不能为空")
                    continue
                name = str(name_raw).strip()

                # 类型标识
                package_type_raw = row.get("package_type")
                if (
                    pd.isna(package_type_raw)
                    or package_type_raw is None
                    or str(package_type_raw).strip() == ""
                ):
                    errors.append(f"第 {row_num} 行：套餐类型标识不能为空")
                    continue
                package_type = str(package_type_raw).strip()
                if package_type in existing_types:
                    errors.append(f"第 {row_num} 行：套餐类型标识 '{package_type}' 已存在")
                    continue

                # 基础费用
                base_fee_raw = row.get("base_fee")
                if pd.isna(base_fee_raw) or base_fee_raw is None:
                    errors.append(f"第 {row_num} 行：套餐基础费用不能为空")
                    continue
                try:
                    base_fee = Decimal(str(base_fee_raw))
                    if base_fee < 0:
                        errors.append(f"第 {row_num} 行：基础费用不能为负数")
                        continue
                except (InvalidOperation, ValueError, TypeError):
                    errors.append(f"第 {row_num} 行：基础费用格式错误")
                    continue

                # 是否不限量
                is_unlimited_raw = row.get("is_unlimited")
                is_unlimited = False
                if is_unlimited_raw is not None and not pd.isna(is_unlimited_raw):
                    text = str(is_unlimited_raw).strip().lower()
                    if text in ("是", "true", "1", "yes"):
                        is_unlimited = True
                    elif text in ("否", "false", "0", "no", ""):
                        is_unlimited = False
                    else:
                        errors.append(f"第 {row_num} 行：是否不限量为 '是'/'否'")
                        continue

                # 限量数量
                limit_count = None
                if not is_unlimited:
                    limit_count_raw = row.get("limit_count")
                    if pd.isna(limit_count_raw) or limit_count_raw is None:
                        errors.append(f"第 {row_num} 行：限量套餐必须填写具体数量")
                        continue
                    try:
                        limit_count = int(limit_count_raw)
                        if limit_count <= 0:
                            errors.append(f"第 {row_num} 行：限量数量必须大于 0")
                            continue
                    except (ValueError, TypeError):
                        errors.append(f"第 {row_num} 行：限量数量格式错误")
                        continue

                # 超额单价
                over_limit_unit_price = None
                over_limit_raw = row.get("over_limit_unit_price")
                if over_limit_raw is not None and not pd.isna(over_limit_raw):
                    try:
                        over_limit_unit_price = Decimal(str(over_limit_raw))
                        if over_limit_unit_price < 0:
                            errors.append(f"第 {row_num} 行：超额单价不能为负数")
                            continue
                    except (InvalidOperation, ValueError, TypeError):
                        errors.append(f"第 {row_num} 行：超额单价格式错误")
                        continue

                # 可选字段
                device_type_raw = row.get("device_type")
                device_type = str(device_type_raw).strip() if not pd.isna(device_type_raw) else None
                layer_type_raw = row.get("layer_type")
                layer_type = str(layer_type_raw).strip() if not pd.isna(layer_type_raw) else None
                description_raw = row.get("description")
                description = str(description_raw).strip() if not pd.isna(description_raw) else None
                status_raw = row.get("status")
                status = (
                    str(status_raw).strip().lower()
                    if status_raw is not None and not pd.isna(status_raw)
                    else "active"
                )
                if status not in ("active", "inactive"):
                    errors.append(f"第 {row_num} 行：状态必须为 active/inactive")
                    continue

                plan = PackagePlan(
                    name=name,
                    package_type=package_type,
                    device_type=device_type,
                    layer_type=layer_type,
                    is_unlimited=is_unlimited,
                    limit_count=limit_count,
                    base_fee=base_fee,
                    over_limit_unit_price=over_limit_unit_price,
                    description=description,
                    status=status,
                )
                db_session.add(plan)
                await db_session.flush()
                existing_types.add(package_type)
                success_count += 1
            except Exception as e:  # 兜底，避免单行异常中断整个导入
                logger.warning("包年套餐导入第 %d 行失败: %s", row_num, e)
                errors.append(f"第 {row_num} 行：{str(e)}")

        await db_session.commit()

        # 清除缓存
        await cache_service.invalidate_billing_cache()

        # 记录审计日志
        summary = build_batch_audit_summary(
            operation="package_plan_import",
            total_count=len(df),
            success_count=success_count,
            failed_count=len(errors),
            details=errors[:10],
        )

        await create_audit_entry(
            db_session=db_session,
            user_id=operator_id,
            action="batch_create",
            module="billing",
            record_id=None,
            record_type="package_plan",
            changes={"after": {"count": success_count}},
            operation_type="batch",
            extra_metadata=summary,
            ip_address=request.headers.get(
                "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
            ),
            auto_commit=True,
        )

        return json(
            {
                "code": 0,
                "message": "导入完成",
                "data": {
                    "success_count": success_count,
                    "error_count": len(errors),
                    "errors": errors[:10],
                },
            }
        )
    except Exception as e:
        return json({"code": 50001, "message": f"导入失败：{str(e)}"}, status=500)


@billing_bp.get("/package-plans/import-template")
@auth_required
async def download_package_plan_import_template(request: Request):
    """下载包年套餐导入 Excel 模板"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "包年套餐导入模板"  # pyright: ignore[reportOptionalMemberAccess]

    headers = [
        "name",
        "package_type",
        "base_fee",
        "device_type",
        "layer_type",
        "is_unlimited",
        "limit_count",
        "over_limit_unit_price",
        "description",
        "status",
    ]
    ws.append(headers)  # pyright: ignore[reportOptionalMemberAccess]

    notes = [
        "必填：套餐名称",
        "必填：类型标识（唯一）",
        "必填：基础费用（元）",
        "可选：X/N/L",
        "可选：single/multi",
        "可选：是/否（或 true/false）",
        "可选：限量数量（非不限量必填）",
        "可选：超额单价",
        "可选：描述",
        "可选：active/inactive",
    ]
    ws.append(notes)  # pyright: ignore[reportOptionalMemberAccess]

    for col in ws.columns:  # pyright: ignore[reportOptionalMemberAccess]
        ws.column_dimensions[col[0].column_letter].width = 24  # pyright: ignore[reportOptionalMemberAccess]

    # 示例数据
    ws.append(["A 套餐", "A", 50000.00, "X", "single", "否", 10000, 5.00, "示例套餐", "active"])  # pyright: ignore[reportOptionalMemberAccess]

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return raw(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="包年套餐导入模板.xlsx"'},
    )


@billing_bp.get("/package-plans/export")
@auth_required
@require_permission("billing:package_export")
async def export_package_plans(request: Request):
    """导出包年套餐为 Excel（按当前筛选条件导出全部匹配数据，上限 50000 条）"""
    import pandas as pd

    from ...models.billing import PackagePlan

    db: AsyncSession = request.ctx.db_session

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
        base_stmt = base_stmt.where(PackagePlan.is_unlimited == (is_unlimited.lower() == "true"))

    base_stmt = base_stmt.order_by(PackagePlan.created_at.desc()).limit(50000)
    result = await db.execute(base_stmt)
    plans = result.scalars().all()

    if not plans:
        return json(
            {"code": 40002, "message": "没有找到符合条件的包年套餐"},
            status=400,
        )

    data = [_package_plan_to_dict(p) for p in plans]
    df = pd.DataFrame(data)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="包年套餐")

    output.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"package_plans_{timestamp}.xlsx"

    return raw(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
