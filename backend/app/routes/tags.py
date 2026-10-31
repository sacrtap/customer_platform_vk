"""标签管理路由"""

import asyncio
import logging

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache.base import cache_service
from ..middleware.auth import auth_required, get_current_user, require_permission
from ..services.tags import TagService
from ..utils.audit_helpers import build_batch_audit_summary, create_audit_entry
from ..utils.excel_export import excel_response
from ..utils.excel_import import read_import_dataframe
from ..utils.excel_template import template_response

logger = logging.getLogger(__name__)

tags_bp = Blueprint("tags", url_prefix="/api/v1/tags")


@tags_bp.get("")
@auth_required
@require_permission("tags:view")
async def list_tags(request: Request):
    """
    获取标签列表（支持筛选）

    Query:
    - page: 页码 (默认 1)
    - page_size: 每页数量 (默认 20)
    - type: 标签类型 (customer/profile)
    - category: 标签分类
    """
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    page_size = min(page_size, 100)

    tag_type = request.args.get("type")
    category = request.args.get("category")

    # 尝试从缓存获取
    cache_key = f"p{page}_ps{page_size}_{tag_type or 'all'}_{category or 'all'}"
    cached = await cache_service.get("tag_list", cache_key)
    if cached is not None:
        return json(cached)

    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    tags, total = await service.get_all_tags(
        page=page, page_size=page_size, tag_type=tag_type, category=category
    )

    result = {
        "code": 0,
        "message": "success",
        "data": {
            "list": [
                {
                    "id": tag.id,
                    "name": tag.name,
                    "type": tag.type,
                    "category": tag.category,
                    "created_by": tag.created_by,
                    "created_at": tag.created_at.isoformat() if tag.created_at else None,  # pyright: ignore[reportGeneralTypeIssues]
                }
                for tag in tags
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }

    # 写入缓存
    await cache_service.set("tag_list", result, cache_key)

    return json(result)


@tags_bp.get("/<tag_id:int>")
@auth_required
@require_permission("tags:view")
async def get_tag(request: Request, tag_id: int):
    """获取标签详情"""
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    tag = await service.get_tag_by_id(tag_id)

    if not tag:
        return json({"code": 40401, "message": "标签不存在"}, status=404)

    usage = await service.get_tag_usage_count(tag_id)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": tag.id,
                "name": tag.name,
                "type": tag.type,
                "category": tag.category,
                "created_by": tag.created_by,
                "usage_count": usage,
            },
        }
    )


@tags_bp.post("")
@auth_required
@require_permission("tags:create")
async def create_tag(request: Request):
    """
    创建标签

    Body:
    {
        "name": "string (required)",
        "type": "string (required, customer/profile)",
        "category": "string (optional)"
    }
    """
    data = request.json

    if not data.get("name") or not data.get("type"):
        return json({"code": 40001, "message": "标签名称和类型不能为空"}, status=400)

    if data["type"] not in ["customer", "profile"]:
        return json(
            {"code": 40002, "message": "标签类型必须是 customer 或 profile"},
            status=400,
        )

    current_user = get_current_user(request)
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    try:
        tag = await service.create_tag(data, created_by=current_user["user_id"])  # pyright: ignore[reportOptionalSubscript]
    except ValueError as e:
        # 业务逻辑错误（如重复标签）
        return json({"code": 40901, "message": str(e)}, status=409)
    except IntegrityError:
        # 数据库约束错误（并发情况下可能发生）
        return json(
            {
                "code": 40902,
                "message": f"标签名称 '{data.get('name')}' 已存在，请使用其他名称",
            },
            status=409,
        )
    except Exception:
        # 其他未知错误（不暴露详细信息给用户）
        return json({"code": 50001, "message": "创建标签失败，请稍后重试"}, status=500)

    # 清除缓存
    await cache_service.invalidate_tag_cache()

    return json(
        {
            "code": 0,
            "message": "创建成功",
            "data": {
                "id": tag.id,
                "name": tag.name,
                "type": tag.type,
                "category": tag.category,
            },
        },
        status=201,
    )


@tags_bp.put("/<tag_id:int>")
@auth_required
@require_permission("tags:edit")
async def update_tag(request: Request, tag_id: int):
    """
    更新标签

    Body:
    {
        "name": "string (optional)",
        "category": "string (optional)"
    }
    """
    data = request.json

    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    tag = await service.update_tag(tag_id, data)

    if not tag:
        return json({"code": 40401, "message": "标签不存在"}, status=404)

    # 清除缓存
    await cache_service.invalidate_tag_cache()

    return json(
        {
            "code": 0,
            "message": "更新成功",
            "data": {
                "id": tag.id,
                "name": tag.name,
                "type": tag.type,
                "category": tag.category,
            },
        }
    )


@tags_bp.delete("/<tag_id:int>")
@auth_required
@require_permission("tags:delete")
async def delete_tag(request: Request, tag_id: int):
    """删除标签"""
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    success = await service.delete_tag(tag_id)

    if not success:
        return json({"code": 40401, "message": "标签不存在"}, status=404)

    # 清除缓存
    await cache_service.invalidate_tag_cache()

    return json({"code": 0, "message": "删除成功"})


@tags_bp.get("/usage/<tag_id:int>")
@auth_required
@require_permission("tags:view")
async def get_tag_usage(request: Request, tag_id: int):
    """获取标签使用次数"""
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    tag = await service.get_tag_by_id(tag_id)
    if not tag:
        return json({"code": 40401, "message": "标签不存在"}, status=404)

    usage = await service.get_tag_usage_count(tag_id)

    return json({"code": 0, "message": "success", "data": usage})


# ========== 导入导出 ==========


@tags_bp.get("/export")
@auth_required
@require_permission("tags:export")
async def export_tags(request: Request):
    """
    Excel 导出标签列表

    Query:
    - type: 标签类型（可选，customer/profile）
    """
    tag_type = request.args.get("type")

    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    # 获取所有匹配的标签（不分页，上限 50000 条）
    tags, total = await service.get_all_tags(page=1, page_size=50000, tag_type=tag_type)

    records = [
        {
            "name": t.name,
            "type": "客户标签" if t.type == "customer" else "画像标签",
            "category": t.category,
        }
        for t in tags
    ]

    return excel_response(records, "标签", "tags", total)


@tags_bp.get("/import-template")
@auth_required
@require_permission("tags:import")
async def download_tag_import_template(request: Request):
    """下载标签导入模板"""
    columns = [
        ("name", "必填：标签名称（≤50），如 重点客户"),
        ("type", "必填：标签类型，仅 customer 或 profile"),
        ("category", "可选：标签分类，如 优先级"),
    ]
    return template_response(columns, "标签导入模板.xlsx")


@tags_bp.post("/import")
@auth_required
@require_permission("tags:import")
async def import_tags(request: Request):
    """
    Excel 批量导入标签

    Form:
    - file: Excel 文件 (.xlsx)

    Query:
    - dry_run: 可选，true/1/yes/on 时仅预检查（完整行级校验、不落库），
      返回可入库条数 + 错误列表（含行号），供前端二次确认

    Excel 列要求:
    - name (text, required) - 标签名称（≤50）
    - type (text, required) - 标签类型，仅 customer 或 profile
    - category (text, optional) - 标签分类
    """
    import pandas as pd

    files = request.files
    if "file" not in files:  # pyright: ignore[reportOperatorIssue]
        return json({"code": 40001, "message": "请上传 Excel 文件"}, status=400)

    excel_file = files["file"][0]  # pyright: ignore[reportOptionalSubscript]
    if not excel_file.name.endswith(".xlsx"):
        return json({"code": 40002, "message": "请上传 .xlsx 格式的文件"}, status=400)

    try:
        # 读取 Excel 文件（自动丢弃模板第 2 行的中文说明行）。pd.read_excel 为 CPU+I/O
        # 密集操作，10MB xlsx 解析可能阻塞事件循环数百毫秒到数秒，移到线程执行。
        df = await asyncio.to_thread(read_import_dataframe, excel_file.body, "name")

        # 必填列检查
        required_columns = ["name", "type"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return json(
                {
                    "code": 40003,
                    "message": f"Excel 缺少必填列：{', '.join(missing_columns)}",
                },
                status=400,
            )

        # 行数限制（与其他管理类导入端点一致）
        if len(df) > 1000:
            return json(
                {"code": 40004, "message": "单次最多导入 1000 条记录"},
                status=400,
            )

        db_session: AsyncSession = request.ctx.db_session
        service = TagService(db_session)

        dry_run = request.args.get("dry_run", "").lower() in ("1", "true", "yes", "on")

        # 预加载全部标签 (name, type) 键集用于查重。注意 get_tag_by_name_and_type
        # 仅查未软删行，但 tags 表的 uq_tags_name_type 约束未带 deleted_at 条件，
        # 软删占用的 (name, type) 仍会触发唯一约束冲突，故查重必须覆盖所有行
        # （含软删），否则会漏判并将错误延后到 commit 抛 IntegrityError。
        existing_keys = await service.get_existing_tag_keys()

        # 逐行校验
        errors = []
        valid_rows = []

        for idx, row in df.iterrows():
            row_num = int(str(idx)) + 2  # Excel 行号（含表头）

            # 校验 name
            name = row.get("name")
            if bool(pd.isna(name)) or name is None:  # pyright: ignore[reportArgumentType, reportCallIssue]
                errors.append(f"第 {row_num} 行：标签名称为空")
                continue
            name = str(name).strip()
            if not name:
                errors.append(f"第 {row_num} 行：标签名称为空")
                continue
            if len(name) > 50:
                errors.append(f"第 {row_num} 行：标签名称长度不能超过 50 个字符")
                continue

            # 校验 type
            tag_type = row.get("type")
            if bool(pd.isna(tag_type)) or tag_type is None:  # pyright: ignore[reportArgumentType, reportCallIssue]
                errors.append(f"第 {row_num} 行：标签类型必须是 customer 或 profile")
                continue
            tag_type = str(tag_type).strip()
            if tag_type not in ("customer", "profile"):
                errors.append(f"第 {row_num} 行：标签类型必须是 customer 或 profile")
                continue

            # 校验 category（可空，NaN → None）
            category = row.get("category")
            if bool(pd.isna(category)) or category is None:  # pyright: ignore[reportArgumentType, reportCallIssue]
                category = None
            else:
                category = str(category).strip()
                if not category:
                    category = None

            # 查重（按 (name, type) 唯一键，覆盖软删行）
            if (name, tag_type) in existing_keys:
                errors.append(f"第 {row_num} 行：标签 '{name}'（类型 {tag_type}）已存在")
                continue

            # 文件内重复行：同一 (name, type) 多次出现，仅首行有效
            if (name, tag_type) in {(r["name"], r["type"]) for r in valid_rows}:
                errors.append(f"第 {row_num} 行：标签 '{name}'（类型 {tag_type}）已存在")
                continue

            valid_rows.append({"name": name, "type": tag_type, "category": category})

        # 预检查（dry_run=true）：完整行级校验但不落库、不失效缓存，返回可入库条数
        # 与错误明细（含行号），供前端二次确认后才真正导入。
        if dry_run:
            return json(
                {
                    "code": 0,
                    "message": "预检查完成",
                    "data": {
                        "dry_run": True,
                        "success_count": len(valid_rows),
                        "error_count": len(errors),
                        "errors": errors[:50],
                    },
                }
            )

        if not valid_rows:
            return json(
                {
                    "code": 0,
                    "message": "导入完成",
                    "data": {
                        "success_count": 0,
                        "error_count": len(errors),
                        "errors": errors[:10],
                    },
                }
            )

        current_user = get_current_user(request)
        created_by = current_user["user_id"]  # pyright: ignore[reportOptionalSubscript]

        from ..models.tags import Tag

        # 正式导入：逐行落库。事务块内 add + commit；成功后在事务块外失效缓存
        # （dry_run 不失效）。IntegrityError 作为并发查重的兜底——预加载的 existing_keys
        # 与本次 add 之间可能有并发写入，兜底返回行级错误而非 500。
        try:
            for row_data in valid_rows:
                tag = Tag(
                    name=row_data["name"],
                    type=row_data["type"],
                    category=row_data["category"],
                    created_by=created_by,
                )
                db_session.add(tag)
            await db_session.commit()
        except IntegrityError:
            await db_session.rollback()
            return json(
                {
                    "code": 40902,
                    "message": "存在重复标签（可能由并发导入引起），请重试",
                },
                status=409,
            )

        # 正式导入成功后失效标签缓存（事务块外，dry_run 不失效）
        await cache_service.invalidate_tag_cache()

        # 记录审计日志
        summary = build_batch_audit_summary(
            operation="tag_import",
            total_count=len(df),
            success_count=len(valid_rows),
            failed_count=len(errors),
            details=errors[:10],
        )

        await create_audit_entry(
            db_session=db_session,
            user_id=created_by,
            action="import",
            module="tags",
            record_id=None,
            record_type="tag",
            changes={"after": {"count": len(valid_rows)}},
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
                    "success_count": len(valid_rows),
                    "error_count": len(errors),
                    "errors": errors[:10],
                },
            }
        )

    except Exception as e:
        logger.exception("标签导入失败")
        return json({"code": 50001, "message": f"导入失败：{str(e)}"}, status=500)


# ========== 客户标签管理 ==========

customer_tags_bp = Blueprint("customer_tags", url_prefix="/api/v1/customers")


@customer_tags_bp.get("/<customer_id:int>/tags")
@auth_required
@require_permission("customers:view")
async def get_customer_tags(request: Request, customer_id: int):
    """获取客户的所有标签"""
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    tags = await service.get_customer_tags(customer_id)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": [
                {
                    "id": tag.id,
                    "name": tag.name,
                    "type": tag.type,
                    "category": tag.category,
                }
                for tag in tags
            ],
        }
    )


@customer_tags_bp.post("/<customer_id:int>/tags/<tag_id:int>")
@auth_required
@require_permission("customers:edit")
async def add_customer_tag(request: Request, customer_id: int, tag_id: int):
    """给客户添加标签"""
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)
    current_user = get_current_user(request)

    success = await service.add_customer_tag(customer_id, tag_id)

    if not success:
        return json(
            {"code": 40001, "message": "添加失败，请检查客户和标签是否存在"},
            status=400,
        )

    # 记录审计日志
    await create_audit_entry(
        db_session=db_session,
        user_id=current_user.get("user_id") if current_user else None,
        action="add_tag",
        module="customer-tags",
        record_id=customer_id,
        record_type="customer-tag",
        changes={"tag_id": tag_id, "customer_id": customer_id},
        operation_type="relation",
        extra_metadata={"tag_id": tag_id},
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    await cache_service.invalidate_customer_cache()
    return json({"code": 0, "message": "添加成功"})


@customer_tags_bp.delete("/<customer_id:int>/tags/<tag_id:int>")
@auth_required
@require_permission("customers:edit")
async def remove_customer_tag(request: Request, customer_id: int, tag_id: int):
    """移除客户标签"""
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)
    current_user = get_current_user(request)

    success = await service.remove_customer_tag(customer_id, tag_id)

    if not success:
        return json({"code": 40001, "message": "移除失败，标签可能不存在"}, status=400)

    # 记录审计日志
    await create_audit_entry(
        db_session=db_session,
        user_id=current_user.get("user_id") if current_user else None,
        action="remove_tag",
        module="customer-tags",
        record_id=customer_id,
        record_type="customer-tag",
        changes={"tag_id": tag_id, "customer_id": customer_id},
        operation_type="relation",
        extra_metadata={"tag_id": tag_id},
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    # 清除缓存（标签变更会影响客户列表筛选结果）
    await cache_service.invalidate_tag_cache()
    await cache_service.invalidate_customer_cache()
    return json({"code": 0, "message": "移除成功"})


@customer_tags_bp.post("/tags/batch-add")
@auth_required
@require_permission("customers:edit")
async def batch_add_customer_tags(request: Request):
    """
    批量给客户添加标签

    Body:
    {
        "customer_ids": [1, 2, 3],
        "tag_ids": [1, 2]
    }
    """
    data = request.json

    customer_ids = data.get("customer_ids", [])
    tag_ids = data.get("tag_ids", [])

    if not customer_ids or not tag_ids:
        return json({"code": 40001, "message": "客户 ID 和标签 ID 不能为空"}, status=400)

    current_user = get_current_user(request)
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    success_count, error_count = await service.batch_add_customer_tags(customer_ids, tag_ids)

    # 清除缓存
    # 清除缓存（标签变更会影响客户列表筛选结果）
    await cache_service.invalidate_tag_cache()
    await cache_service.invalidate_customer_cache()
    # 记录批量操作审计日志
    summary = build_batch_audit_summary(
        operation="batch_add_tags",
        total_count=len(customer_ids),
        success_count=success_count,
        failed_count=error_count,
    )

    await create_audit_entry(
        db_session=db_session,
        user_id=current_user.get("user_id") if current_user else None,
        action="batch_add_tags",
        module="customer-tags",
        record_id=None,  # 批量操作
        record_type="customer-tag",
        changes={
            "after": {"success_count": success_count, "error_count": error_count},
        },
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
            "message": "批量添加完成",
            "data": {
                "success_count": success_count,
                "error_count": error_count,
            },
        }
    )


@customer_tags_bp.post("/tags/batch-remove")
@auth_required
@require_permission("customers:edit")
async def batch_remove_customer_tags(request: Request):
    """
    批量移除客户标签

    Body:
    {
        "customer_ids": [1, 2, 3],
        "tag_ids": [1, 2]
    }
    """
    data = request.json

    customer_ids = data.get("customer_ids", [])
    tag_ids = data.get("tag_ids", [])

    if not customer_ids or not tag_ids:
        return json({"code": 40001, "message": "客户 ID 和标签 ID 不能为空"}, status=400)

    current_user = get_current_user(request)
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    removed_count = await service.batch_remove_customer_tags(customer_ids, tag_ids)

    # 清除缓存（标签变更会影响客户列表筛选结果）
    await cache_service.invalidate_tag_cache()
    await cache_service.invalidate_customer_cache()
    # 记录批量操作审计日志
    summary = build_batch_audit_summary(
        operation="batch_remove_tags",
        total_count=len(customer_ids),
        success_count=removed_count,
        failed_count=len(customer_ids) - removed_count,
    )

    await create_audit_entry(
        db_session=db_session,
        user_id=current_user.get("user_id") if current_user else None,
        action="batch_remove_tags",
        module="customer-tags",
        record_id=None,  # 批量操作
        record_type="customer-tag",
        changes={
            "after": {"removed_count": removed_count},
        },
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
            "message": "批量移除完成",
            "data": {"removed_count": removed_count},
        }
    )


# ========== 画像标签管理 ==========

profile_tags_bp = Blueprint("profile_tags", url_prefix="/api/v1/profiles")


@profile_tags_bp.get("/<profile_id:int>/tags")
@auth_required
@require_permission("analytics:view")
async def get_profile_tags(request: Request, profile_id: int):
    """获取画像的所有标签"""
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    tags = await service.get_profile_tags(profile_id)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": [
                {
                    "id": tag.id,
                    "name": tag.name,
                    "type": tag.type,
                    "category": tag.category,
                }
                for tag in tags
            ],
        }
    )


@profile_tags_bp.post("/<profile_id:int>/tags/<tag_id:int>")
@auth_required
@require_permission("analytics:profile_tag_edit")
async def add_profile_tag(request: Request, profile_id: int, tag_id: int):
    """给画像添加标签"""
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)
    current_user = get_current_user(request)

    success = await service.add_profile_tag(profile_id, tag_id)

    if not success:
        return json(
            {"code": 40001, "message": "添加失败，请检查画像和标签是否存在"},
            status=400,
        )

    # 记录审计日志
    await create_audit_entry(
        db_session=db_session,
        user_id=current_user.get("user_id") if current_user else None,
        action="add_tag",
        module="profile-tags",
        record_id=profile_id,
        record_type="profile-tag",
        changes={"tag_id": tag_id, "profile_id": profile_id},
        operation_type="relation",
        extra_metadata={"tag_id": tag_id},
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    # 清除缓存
    await cache_service.invalidate_tag_cache()

    return json({"code": 0, "message": "添加成功"})


@profile_tags_bp.delete("/<profile_id:int>/tags/<tag_id:int>")
@auth_required
@require_permission("analytics:profile_tag_edit")
async def remove_profile_tag(request: Request, profile_id: int, tag_id: int):
    """移除画像标签"""
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)
    current_user = get_current_user(request)

    success = await service.remove_profile_tag(profile_id, tag_id)

    if not success:
        return json({"code": 40001, "message": "移除失败，标签可能不存在"}, status=400)

    # 记录审计日志
    await create_audit_entry(
        db_session=db_session,
        user_id=current_user.get("user_id") if current_user else None,
        action="remove_tag",
        module="profile-tags",
        record_id=profile_id,
        record_type="profile-tag",
        changes={"tag_id": tag_id, "profile_id": profile_id},
        operation_type="relation",
        extra_metadata={"tag_id": tag_id},
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    # 清除缓存
    await cache_service.invalidate_tag_cache()

    return json({"code": 0, "message": "移除成功"})
