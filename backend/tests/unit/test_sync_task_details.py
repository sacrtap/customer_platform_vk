"""同步任务执行明细接口单元测试"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routes.sync_tasks import get_sync_task_details


def parse_response_body(response):
    """解析 Sanic JSON 响应体为 dict"""
    body = response.body
    if isinstance(body, bytes):
        return json.loads(body)
    return body


@pytest.fixture
def mock_request():
    """模拟请求上下文"""
    request = MagicMock()
    request.ctx = MagicMock()
    request.ctx.db_session = AsyncMock()
    request.ctx.user = {"user_id": 1}
    request.args = {}
    return request


def make_detail(detail_id, level, category="order_save", customer_id=None, customer_name=None):
    """构造明细 mock 对象"""
    d = MagicMock()
    d.id = detail_id
    d.sync_date = MagicMock()
    d.sync_date.isoformat.return_value = "2026-09-16"
    d.level = level
    d.category = category
    d.message = f"detail-{detail_id}"
    d.customer_id = customer_id
    d.customer_name = customer_name
    d.external_customer_id = "10086" if level == "warning" else None
    d.company_name = "XX公司" if level == "warning" else None
    d.order_code = "NEST-001" if level == "warning" else None
    d.record_count = 1
    d.created_at = MagicMock()
    d.created_at.isoformat.return_value = "2026-09-17T00:00:00"
    return d


class TestGetSyncTaskDetails:
    """执行明细接口测试"""

    async def test_get_details_full(self, mock_request):
        """测试明细查询（无 level 过滤）"""
        task_id = "123e4567-e89b-12d3-a456-426614174000"

        # summary 结果: (info, warning, error, total)
        summary_result = MagicMock()
        summary_result.one.return_value = (2, 1, 1, 4)

        # 过滤后 count
        count_result = MagicMock()
        count_result.scalar.return_value = 4

        # 明细列表（查询左连客户表，返回 (detail, is_settlement_enabled, account_type, company_id) 元组）
        list_result = MagicMock()
        list_result.all.return_value = [
            (make_detail(1, "info", customer_id=1, customer_name="客户A"), True, "正式账号", 10086),
            (make_detail(2, "warning"), False, "客户测试账号", 10087),
            (make_detail(3, "error"), None, None, None),
            (make_detail(4, "info", customer_id=2, customer_name="客户B"), True, "正式账号", 10088),
        ]

        mock_request.ctx.db_session.execute = AsyncMock(
            side_effect=[summary_result, count_result, list_result]
        )

        response = await get_sync_task_details(mock_request, task_id)

        assert response.status == 200
        body = parse_response_body(response)
        assert body["code"] == 0

        data = body["data"]
        # summary 全量计数
        assert data["summary"] == {
            "info_count": 2,
            "warning_count": 1,
            "error_count": 1,
            "total_count": 4,
        }
        # 列表
        assert len(data["list"]) == 4
        first = data["list"][0]
        assert first["level"] == "info"
        assert first["customer_id"] == 1
        assert first["customer_name"] == "客户A"
        assert first["is_settlement_enabled"] is True
        assert first["account_type"] == "正式账号"
        assert first["company_id"] == 10086
        # warning 明细含外部标识
        warning = data["list"][1]
        assert warning["external_customer_id"] == "10086"
        assert warning["company_name"] == "XX公司"
        assert warning["order_code"] == "NEST-001"
        # 分页
        assert data["pagination"] == {"page": 1, "page_size": 20, "total": 4}

    async def test_get_details_with_level_filter(self, mock_request):
        """测试按 level 过滤"""
        task_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_request.args = {"level": "warning"}

        summary_result = MagicMock()
        summary_result.one.return_value = (0, 1, 0, 1)

        count_result = MagicMock()
        count_result.scalar.return_value = 1

        list_result = MagicMock()
        list_result.all.return_value = [(make_detail(2, "warning"), False, "客户测试账号", 10087)]

        mock_request.ctx.db_session.execute = AsyncMock(
            side_effect=[summary_result, count_result, list_result]
        )

        response = await get_sync_task_details(mock_request, task_id)

        body = parse_response_body(response)
        data = body["data"]
        assert data["summary"]["total_count"] == 1
        assert len(data["list"]) == 1
        assert data["list"][0]["level"] == "warning"
        assert data["pagination"]["total"] == 1

    async def test_get_details_no_records(self, mock_request):
        """测试无明细记录（历史任务）"""
        task_id = "123e4567-e89b-12d3-a456-426614174000"

        summary_result = MagicMock()
        summary_result.one.return_value = (0, 0, 0, 0)

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        list_result = MagicMock()
        list_result.all.return_value = []

        mock_request.ctx.db_session.execute = AsyncMock(
            side_effect=[summary_result, count_result, list_result]
        )

        response = await get_sync_task_details(mock_request, task_id)

        body = parse_response_body(response)
        data = body["data"]
        assert data["summary"]["total_count"] == 0
        assert data["list"] == []
        assert data["pagination"]["total"] == 0

    async def test_get_details_error(self, mock_request):
        """测试异常返回 500"""
        task_id = "123e4567-e89b-12d3-a456-426614174000"
        mock_request.ctx.db_session.execute = AsyncMock(side_effect=Exception("db error"))

        with patch("app.routes.sync_tasks.logger"):
            response = await get_sync_task_details(mock_request, task_id)

        assert response.status == 500
        body = parse_response_body(response)
        assert body["code"] == 500
