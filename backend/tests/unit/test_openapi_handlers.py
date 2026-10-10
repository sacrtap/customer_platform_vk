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
    result.all.return_value = [
        (615, "北京金诚阜业房地产经纪有限公司", 100000.0, 0.0),
        (1552, "荣城地产", None, None),
    ]
    session.execute = AsyncMock(return_value=result)
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
    response = await get_all_customer_balances(_make_request())
    assert response.status == 200
    data = _response_json(response)["data"]
    assert data[0] == {
        "customer_id": "615",
        "customer_name": "北京金诚阜业房地产经纪有限公司",
        "balance": 100000.0,
    }
    assert data[1]["balance"] == 0.0
