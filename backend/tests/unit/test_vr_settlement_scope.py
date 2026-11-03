"""_ensure_settlement_scope 单元测试：VR 结算单数据可见性（服务端强制）

集成测试的 mock 权限缓存对所有用户返回全量权限（含 customers:view_all），
无法构造「无 view_all 用户」的 HTTP 场景，故按计划在此以假 request 对象
直接验证路由层 scope 助手语义：

- 无 customers:view_all 且非本人负责客户 → 403 响应对象
- 无 customers:view_all 且为运营经理/销售本人 → None（放行）
- 有 customers:view_all → None（放行）
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sanic.response import HTTPResponse

from app.routes.billing import vr_settlements


def _fake_settlement(manager_id=None, sales_manager_id=None):
    """假结算单：customer 关系携带 manager_id / sales_manager_id"""
    return SimpleNamespace(
        id=1,
        customer=SimpleNamespace(manager_id=manager_id, sales_manager_id=sales_manager_id),
    )


def _patch_scope(monkeypatch, scope_user_id):
    """patch customer_scope_user_id 返回指定 scope_user_id"""

    async def fake_scope(_request):
        return scope_user_id

    monkeypatch.setattr(vr_settlements, "customer_scope_user_id", fake_scope)


@pytest.mark.asyncio
async def test_scope_denies_non_owned_customer(monkeypatch):
    """无 view_all（scope=uid）且客户由他人负责 → 403"""
    _patch_scope(monkeypatch, 42)
    # 客户归属：manager=1, sales=2；当前用户 42 两者皆非
    settlement = _fake_settlement(manager_id=1, sales_manager_id=2)

    result = await vr_settlements._ensure_settlement_scope(MagicMock(), settlement)

    assert isinstance(result, HTTPResponse)
    assert result.status == 403


@pytest.mark.asyncio
async def test_scope_allows_manager_and_sales(monkeypatch):
    """无 view_all 但当前用户是客户的运营经理或销售 → 放行（None）"""
    settlement = _fake_settlement(manager_id=42, sales_manager_id=7)

    _patch_scope(monkeypatch, 42)  # 运营经理本人
    assert await vr_settlements._ensure_settlement_scope(MagicMock(), settlement) is None

    _patch_scope(monkeypatch, 7)  # 销售本人
    assert await vr_settlements._ensure_settlement_scope(MagicMock(), settlement) is None


@pytest.mark.asyncio
async def test_scope_allows_view_all(monkeypatch):
    """有 customers:view_all（scope_user_id=None）→ 放行"""
    _patch_scope(monkeypatch, None)
    settlement = _fake_settlement(manager_id=1, sales_manager_id=2)

    assert await vr_settlements._ensure_settlement_scope(MagicMock(), settlement) is None


@pytest.mark.asyncio
async def test_customer_scope_denies_non_owned_customer(monkeypatch):
    """创建前客户可见性校验：非本人负责客户 → 403"""
    _patch_scope(monkeypatch, 42)
    customer = SimpleNamespace(manager_id=1, sales_manager_id=2)

    result = await vr_settlements._ensure_customer_scope(MagicMock(), customer)

    assert isinstance(result, HTTPResponse)
    assert result.status == 403


@pytest.mark.asyncio
async def test_customer_scope_allows_owned(monkeypatch):
    """创建前客户可见性校验：本人负责客户或 view_all → 放行"""
    _patch_scope(monkeypatch, None)
    customer = SimpleNamespace(manager_id=1, sales_manager_id=2)
    assert await vr_settlements._ensure_customer_scope(MagicMock(), customer) is None

    _patch_scope(monkeypatch, 1)
    assert await vr_settlements._ensure_customer_scope(MagicMock(), customer) is None
