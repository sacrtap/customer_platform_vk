"""customer_scope_user_id 单元测试：服务端强制可见性语义

覆盖（2026-09-29 修复后）：
- 未认证（无用户上下文）→ fail-closed 抛 401（而非放行全量）
- 有 customers:view_all → 返回 None（可查看全部）
- 无 view_all → 返回 user_id（调用方须按归属过滤）
- 权限缓存未命中 → 走数据库查询并回填缓存
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sanic.exceptions import SanicException


@pytest.mark.asyncio
async def test_scope_user_id_unauthenticated_fail_closed():
    """未认证用户：抛 401（fail-closed，防止未来未保护 route 越权）"""
    from app.middleware import auth as auth_module

    request = MagicMock()
    request.ctx.user = None
    original_gcu = auth_module.get_current_user
    auth_module.get_current_user = MagicMock(return_value=None)
    try:
        with pytest.raises(SanicException) as exc:
            await auth_module.customer_scope_user_id(request)
        assert exc.value.status_code == 401
    finally:
        auth_module.get_current_user = original_gcu


@pytest.mark.asyncio
async def test_scope_user_id_with_view_all_returns_none():
    """拥有 customers:view_all → None（查看全部）"""
    from app.cache import permissions as perm_module
    from app.middleware import auth as auth_module

    request = MagicMock()
    original_gcu = auth_module.get_current_user
    auth_module.get_current_user = MagicMock(return_value={"user_id": 7, "username": "admin"})
    original_get = perm_module.permission_cache.get_permissions
    original_set = perm_module.permission_cache.set_permissions
    perm_module.permission_cache.get_permissions = AsyncMock(
        return_value={"customers:view", "customers:view_all"}
    )
    try:
        result = await auth_module.customer_scope_user_id(request)
        assert result is None
    finally:
        auth_module.get_current_user = original_gcu
        perm_module.permission_cache.get_permissions = original_get
        perm_module.permission_cache.set_permissions = original_set


@pytest.mark.asyncio
async def test_scope_user_id_without_view_all_returns_user_id():
    """无 view_all → 返回当前用户 ID（调用方须强制归属过滤）"""
    from app.cache import permissions as perm_module
    from app.middleware import auth as auth_module

    request = MagicMock()
    original_gcu = auth_module.get_current_user
    auth_module.get_current_user = MagicMock(return_value={"user_id": 9, "username": "manager"})
    original_get = perm_module.permission_cache.get_permissions
    perm_module.permission_cache.get_permissions = AsyncMock(return_value={"customers:view"})
    try:
        result = await auth_module.customer_scope_user_id(request)
        assert result == 9
    finally:
        auth_module.get_current_user = original_gcu
        perm_module.permission_cache.get_permissions = original_get


@pytest.mark.asyncio
async def test_scope_user_id_cache_miss_falls_back_to_db():
    """权限缓存未命中 → 查数据库并回填缓存"""
    from app.cache import permissions as perm_module
    from app.middleware import auth as auth_module
    from app.services import get_user_permissions as original_gup

    request = MagicMock()
    request.ctx.db_session = MagicMock()
    original_gcu = auth_module.get_current_user
    auth_module.get_current_user = MagicMock(return_value={"user_id": 5, "username": "ops"})
    original_get = perm_module.permission_cache.get_permissions
    original_set = perm_module.permission_cache.set_permissions
    perm_module.permission_cache.get_permissions = AsyncMock(return_value=None)
    perm_module.permission_cache.set_permissions = AsyncMock()
    auth_module.get_user_permissions = AsyncMock(return_value={"customers:view"})
    try:
        result = await auth_module.customer_scope_user_id(request)
        assert result == 5
        perm_module.permission_cache.set_permissions.assert_awaited_once()
    finally:
        auth_module.get_current_user = original_gcu
        perm_module.permission_cache.get_permissions = original_get
        perm_module.permission_cache.set_permissions = original_set
        auth_module.get_user_permissions = original_gup
