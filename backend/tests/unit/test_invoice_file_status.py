"""file-status 路由单元测试

测试 /invoices/file-status 接口的参数解析和响应格式。
通过直接调用未装饰的原始函数绕过 auth_required 和 require_permission。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# 获取未装饰的原始函数
from app.routes.billing.invoices import get_invoice_file_status

# 访问装饰器链中的原始函数
# auth_required 装饰器将原始函数保存在 __wrapped__ 属性中
_raw_fn = get_invoice_file_status
while hasattr(_raw_fn, "__wrapped__"):
    _raw_fn = _raw_fn.__wrapped__


def _make_request(ids_param: str = "", db_session=None):
    """构造 mock Request 对象"""
    request = MagicMock()
    request.args = {"ids": ids_param} if ids_param else {}
    request.ctx.db_session = db_session or MagicMock()
    request.app.ctx = MagicMock()
    return request


@pytest.mark.asyncio
async def test_file_status_empty_ids():
    """ids 参数为空时返回空列表"""
    request = _make_request(ids_param="")
    response = await _raw_fn(request)
    assert response.status == 200
    import json as json_mod

    data = json_mod.loads(response.body)
    assert data["code"] == 0
    assert data["data"]["list"] == []


@pytest.mark.asyncio
async def test_file_status_no_ids_param():
    """未传 ids 参数时返回空列表"""
    request = _make_request(ids_param="")
    response = await _raw_fn(request)
    import json as json_mod

    data = json_mod.loads(response.body)
    assert data["code"] == 0
    assert data["data"]["list"] == []


@pytest.mark.asyncio
async def test_file_status_invalid_ids():
    """ids 包含非数字时返回 400 错误"""
    request = _make_request(ids_param="1,abc,3")
    response = await _raw_fn(request)
    import json as json_mod

    assert response.status == 400
    data = json_mod.loads(response.body)
    assert "ids" in data["message"]


@pytest.mark.asyncio
async def test_file_status_valid_ids():
    """有效的 ids 参数正确查询并返回结果"""
    # Mock 数据库查询结果
    mock_row1 = MagicMock()
    mock_row1.id = 1
    mock_row1.detail_file_status = "completed"
    mock_row1.detail_file_path = "invoices/2026/07/invoice_1.xlsx"

    mock_row2 = MagicMock()
    mock_row2.id = 3
    mock_row2.detail_file_status = None  # 测试 None 降级为 "pending"
    mock_row2.detail_file_path = None

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row1, mock_row2]

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    request = _make_request(ids_param="1,3", db_session=mock_db)
    response = await _raw_fn(request)

    import json as json_mod

    data = json_mod.loads(response.body)
    assert data["code"] == 0
    result_list = data["data"]["list"]
    assert len(result_list) == 2

    # 第一条 — completed
    assert result_list[0]["id"] == 1
    assert result_list[0]["detail_file_status"] == "completed"
    assert result_list[0]["detail_file_path"] == "invoices/2026/07/invoice_1.xlsx"

    # 第二条 — None 降级为 "pending"
    assert result_list[1]["id"] == 3
    assert result_list[1]["detail_file_status"] == "pending"
    assert result_list[1]["detail_file_path"] is None


@pytest.mark.asyncio
async def test_file_status_single_id():
    """单个 id 查询"""
    mock_row = MagicMock()
    mock_row.id = 42
    mock_row.detail_file_status = "generating"
    mock_row.detail_file_path = None

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    request = _make_request(ids_param="42", db_session=mock_db)
    response = await _raw_fn(request)

    import json as json_mod

    data = json_mod.loads(response.body)
    assert data["code"] == 0
    assert len(data["data"]["list"]) == 1
    assert data["data"]["list"][0]["id"] == 42
    assert data["data"]["list"][0]["detail_file_status"] == "generating"


@pytest.mark.asyncio
async def test_file_status_empty_after_parsing():
    """ids 参数为 "1,,3" 时过滤空字符串后正常查询"""
    mock_result = MagicMock()
    mock_result.all.return_value = []

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    request = _make_request(ids_param="1,,3", db_session=mock_db)
    response = await _raw_fn(request)

    import json as json_mod

    data = json_mod.loads(response.body)
    assert data["code"] == 0
    # 应该正常返回空列表（ids=[1,3] 查无结果）
    assert data["data"]["list"] == []
