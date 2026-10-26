"""开放平台 handler 直接调用单元测试（无 DB）

背景: Sanic asgi_client 环境下 coverage tracer 在 await 恢复点丢失,
handler 成功路径的行无法被集成测试度量。此处直接调用 handler,
用 Mock session 覆盖响应组装逻辑（balance 计算、无余额=0.0、str(company_id)）,
与集成测试（真实 DB 验证 SQL/过滤/认证）互补。

注意: 筛选条件（WHERE）必须在集成测试中验证, 本文件不防御 SQL 片段。
"""

import json as jsonlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.routes.openapi import get_all_customer_balances, get_erp_balances


def _make_request(erp_channel=None):
    """构造最小 Request 形态: args.get + ctx.db_session"""
    request = MagicMock()
    request.args.get.return_value = erp_channel
    session = AsyncMock()
    result = MagicMock()
    # 行结构: (Customer.id, company_id, name, total_amount, used_total, package_remaining)
    result.all.return_value = [
        (615, 615, "北京金诚阜业房地产经纪有限公司", 100000.0, 0.0, None),
        (1552, 1552, "荣城地产", None, None, None),
    ]
    session.execute = AsyncMock(return_value=result)
    request.ctx.db_session = session
    return request


def _make_request_all():
    """构造全量版 Request: 白名单 map 查询为空 + 客户余额行（6 列）"""
    request = MagicMock()
    request.args.get.return_value = None
    session = AsyncMock()
    whitelist_result = MagicMock()
    whitelist_result.all.return_value = []
    customer_result = MagicMock()
    customer_result.all.return_value = [
        (615, 615, "北京金诚阜业房地产经纪有限公司", 100000.0, 0.0, None),
        (1552, 1552, "荣城地产", None, None, None),
    ]
    # 第一次 execute 查白名单 map（空），第二次查客户余额
    session.execute = AsyncMock(side_effect=[whitelist_result, customer_result])
    request.ctx.db_session = session
    return request


def _make_request_package():
    """构造含包年客户的 Request（第 6 列 = 套餐剩余额度，非包年为 None）"""
    request = MagicMock()
    request.args.get.return_value = None
    session = AsyncMock()
    whitelist_result = MagicMock()
    whitelist_result.all.return_value = []
    customer_result = MagicMock()
    customer_result.all.return_value = [
        # 包年客户: 现金池为 0，但套餐剩余额度 2880.68 → 应返回 2880.68
        (100, 1625, "新乡暴风雨地产", 0.0, 0.0, 2880.68),
        # 非包年客户: 无包年列 → 走 total_amount（used_total 不参与计算）
        (101, 200, "预付费客户", 5000.0, 1500.0, None),
        # 包年且无余额行 → 仍取套餐剩余额度
        (102, 300, "包年无余额行客户", None, None, 1000.0),
    ]
    session.execute = AsyncMock(side_effect=[whitelist_result, customer_result])
    request.ctx.db_session = session
    return request


def _response_json(response) -> dict:
    return jsonlib.loads(response.body)


@pytest.mark.asyncio
async def test_erp_balances_success_direct():
    """渠道版: 有效渠道 → 200 + 余额组装正确（含无余额=0.0）"""
    response = await get_erp_balances(_make_request("qiaofang"))
    assert response.status == 200
    data = _response_json(response)["data"]
    assert data[0] == {
        "customer_id": "615",
        "customer_name": "北京金诚阜业房地产经纪有限公司",
        "balance": 100000.0,
    }
    assert data[1] == {"customer_id": "1552", "customer_name": "荣城地产", "balance": 0.0}


@pytest.mark.asyncio
async def test_erp_balances_missing_channel_direct():
    """渠道版: 缺少 erp_channel → 400 + 40004"""
    response = await get_erp_balances(_make_request(None))
    assert response.status == 400
    assert _response_json(response)["code"] == 40004


@pytest.mark.asyncio
async def test_all_balances_success_direct():
    """全量版: 无渠道参数 → 200 + 余额组装正确"""
    response = await get_all_customer_balances(_make_request_all())
    assert response.status == 200
    data = _response_json(response)["data"]
    assert data[0] == {
        "customer_id": "615",
        "customer_name": "北京金诚阜业房地产经纪有限公司",
        "balance": 100000.0,
    }
    assert data[1]["balance"] == 0.0


@pytest.mark.asyncio
async def test_all_balances_package_uses_remaining_not_cash_pool():
    """全量版: 包年客户取套餐剩余额度（现金池为 0 也返回剩余额度），非包年取 total_amount"""
    response = await get_all_customer_balances(_make_request_package())
    assert response.status == 200
    by_id = {i["customer_id"]: i["balance"] for i in _response_json(response)["data"]}
    assert by_id["1625"] == 2880.68  # 包年：现金池 0 但套餐剩 2880.68
    assert by_id["200"] == 5000.0  # 非包年：total_amount（used_total 1500 不二次扣减）
    assert by_id["300"] == 1000.0  # 包年无余额行：仍取套餐剩余额度


@pytest.mark.asyncio
async def test_all_balances_no_double_deduction_direct():
    """回归：used_total 不参与余额计算（2026-10-26 双重扣减修复）

    `total_amount = real_amount + bonus_amount` 是扣款后的当前可用余额，
    `used_total` 仅是累计消耗统计量；相减等于把同一笔消耗扣两遍。
    客户 1322 实测：total=-83.50 / used=150.30 → 应返回 -83.50，旧口径 -233.80。
    """
    request = MagicMock()
    request.args.get.return_value = None
    session = AsyncMock()
    whitelist_result = MagicMock()
    whitelist_result.all.return_value = []
    customer_result = MagicMock()
    customer_result.all.return_value = [
        (27398, 1322, "德阳齐家天下", -83.50, 150.30, None),
        (27533, 1528, "沧州瑞德信地产", 3010.00, 0.00, None),
    ]
    session.execute = AsyncMock(side_effect=[whitelist_result, customer_result])
    request.ctx.db_session = session

    response = await get_all_customer_balances(request)
    assert response.status == 200
    by_id = {i["customer_id"]: i["balance"] for i in _response_json(response)["data"]}
    assert by_id["1322"] == -83.50
    assert by_id["1528"] == 3010.0
