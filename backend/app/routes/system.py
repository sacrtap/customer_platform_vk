# -*- coding: utf-8 -*-
"""系统公告路由"""

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json

from ..cache.base import cache_service
from ..middleware.auth import auth_required
from ..services.github_updates import get_github_updates_client

system_bp = Blueprint("system", url_prefix="/api/v1/system")


@system_bp.get("/updates")
@auth_required
async def get_system_updates(request: Request):
    """获取最近 3 次部署更新摘要（仅成功部署，含两次部署间全部提交）

    只读接口，不落库。结果经 Redis 缓存 10 分钟兜底 GitHub 匿名限流；
    仅缓存非空结果（空 = GitHub 不可达/限流，下次请求可重试）。
    """
    cached = await cache_service.get("system_updates")
    if cached is not None:
        return json({"code": 0, "message": "success", "data": {"updates": cached}})

    client = get_github_updates_client()
    updates = await client.get_recent_updates(3)
    if updates:
        await cache_service.set("system_updates", updates)

    return json({"code": 0, "message": "success", "data": {"updates": updates}})
