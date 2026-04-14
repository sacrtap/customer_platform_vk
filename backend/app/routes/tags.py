"""标签管理路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from ..services.tags import TagService
from ..middleware.auth import auth_required, require_permission, get_current_user
from ..cache.base import cache_service

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
                    "created_at": tag.created_at.isoformat()
                    if tag.created_at
                    else None,
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
        tag = await service.create_tag(data, created_by=current_user["user_id"])
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

    success = await service.add_customer_tag(customer_id, tag_id)

    if not success:
        return json(
            {"code": 40001, "message": "添加失败，请检查客户和标签是否存在"},
            status=400,
        )

    return json({"code": 0, "message": "添加成功"})


@customer_tags_bp.delete("/<customer_id:int>/tags/<tag_id:int>")
@auth_required
@require_permission("customers:edit")
async def remove_customer_tag(request: Request, customer_id: int, tag_id: int):
    """移除客户标签"""
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    success = await service.remove_customer_tag(customer_id, tag_id)

    if not success:
        return json({"code": 40001, "message": "移除失败，标签可能不存在"}, status=400)

    # 清除缓存
    await cache_service.invalidate_tag_cache()

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
        return json(
            {"code": 40001, "message": "客户 ID 和标签 ID 不能为空"}, status=400
        )

    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    success_count, error_count = await service.batch_add_customer_tags(
        customer_ids, tag_ids
    )

    # 清除缓存
    await cache_service.invalidate_tag_cache()

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
        return json(
            {"code": 40001, "message": "客户 ID 和标签 ID 不能为空"}, status=400
        )

    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    removed_count = await service.batch_remove_customer_tags(customer_ids, tag_ids)

    # 清除缓存
    await cache_service.invalidate_tag_cache()

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
@require_permission("profiles:view")
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
@require_permission("profiles:edit")
async def add_profile_tag(request: Request, profile_id: int, tag_id: int):
    """给画像添加标签"""
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    success = await service.add_profile_tag(profile_id, tag_id)

    if not success:
        return json(
            {"code": 40001, "message": "添加失败，请检查画像和标签是否存在"},
            status=400,
        )

    # 清除缓存
    await cache_service.invalidate_tag_cache()

    return json({"code": 0, "message": "添加成功"})


@profile_tags_bp.delete("/<profile_id:int>/tags/<tag_id:int>")
@auth_required
@require_permission("profiles:edit")
async def remove_profile_tag(request: Request, profile_id: int, tag_id: int):
    """移除画像标签"""
    db_session: AsyncSession = request.ctx.db_session
    service = TagService(db_session)

    success = await service.remove_profile_tag(profile_id, tag_id)

    if not success:
        return json({"code": 40001, "message": "移除失败，标签可能不存在"}, status=400)

    # 清除缓存
    await cache_service.invalidate_tag_cache()

    return json({"code": 0, "message": "移除成功"})
