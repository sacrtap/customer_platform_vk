"""get_kpi_stats 单元测试：全量卡片可见性（visibility_user_id）与
「我的客户」（mine_user_id）语义分离的回归保护。

背景（2026-09-29）：前端无条件传 mine=true 曾使 admin（有 view_all）的
total/key_customers/incomplete_profile 被误过滤为名下客户数（≈0）。
修复后三个全量卡片只受 visibility_user_id（服务端强制 scope_user_id）约束，
mine_user_id 仅影响 my_customers 计数。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


class MockDBSession(AsyncSession):
    """Mock 数据库会话（execute 按 side_effect 依次返回各 count 结果）"""

    def __init__(self):
        super().__init__()
        self.execute = AsyncMock()


def make_count_result(scalar_value):
    result = MagicMock()
    result.scalar = MagicMock(return_value=scalar_value)
    return result


@pytest.fixture
def mock_db():
    return MockDBSession()


def run_kpi(mock_db, values, **kwargs):
    """按 get_kpi_stats 的执行顺序（total/key/incomplete/mine）喂 count 结果"""
    mock_db.execute = AsyncMock(side_effect=[make_count_result(v) for v in values])
    from app.services.customers import CustomerService

    service = CustomerService(mock_db)
    return service, mock_db


@pytest.mark.asyncio
async def test_kpi_stats_admin_visibility_none_no_scope_filter():
    """有 view_all（visibility_user_id=None）：三个全量卡片不做归属过滤"""
    service, db = run_kpi(MockDBSession(), [5, 2, 1, 0])
    stats = await service.get_kpi_stats(filters={}, mine_user_id=None, visibility_user_id=None)
    assert stats == {
        "total": 5,
        "key_customers": 2,
        "incomplete_profile": 1,
        "my_customers": 0,
    }
    # 三个全量卡片 stmt 均不含 manager_id / sales_manager_id 过滤
    for call in db.execute.call_args_list[:3]:
        sql = str(call.args[0])
        assert "manager_id" not in sql, "admin 全量卡片不应含归属过滤"


@pytest.mark.asyncio
async def test_kpi_stats_admin_mine_true_full_visible():
    """回归（2026-09-29）：admin + mine=true 时全量卡片仍显示全量，
    仅 my_customers 按 admin 名下统计（此处 0）"""
    service, db = run_kpi(MockDBSession(), [5, 2, 1, 0])
    stats = await service.get_kpi_stats(filters={}, mine_user_id=100, visibility_user_id=None)
    assert stats == {
        "total": 5,
        "key_customers": 2,
        "incomplete_profile": 1,
        "my_customers": 0,
    }
    for call in db.execute.call_args_list[:3]:
        sql = str(call.args[0])
        assert "manager_id" not in sql, "admin+mine=true 全量卡片不应被过滤"
    # 第 4 个（mine_stmt）按 mine_user_id=100 过滤
    mine_sql = str(db.execute.call_args_list[3].args[0])
    assert "manager_id" in mine_sql and "sales_manager_id" in mine_sql


@pytest.mark.asyncio
async def test_kpi_stats_scoped_visibility_filters_full_cards():
    """受限用户（visibility_user_id=42）：三个全量卡片按归属过滤"""
    service, db = run_kpi(MockDBSession(), [1, 1, 1, 1])
    stats = await service.get_kpi_stats(filters={}, mine_user_id=42, visibility_user_id=42)
    assert stats == {
        "total": 1,
        "key_customers": 1,
        "incomplete_profile": 1,
        "my_customers": 1,
    }
    # 三个全量卡片 + mine_stmt 全部含归属过滤
    for call in db.execute.call_args_list:
        sql = str(call.args[0])
        assert "manager_id" in sql and "sales_manager_id" in sql


@pytest.mark.asyncio
async def test_kpi_stats_scoped_but_no_mine_request():
    """受限用户但未显式请求 mine（mine_user_id=None）：
    全量卡片仍按 visibility 过滤，my_customers 为 0"""
    service, db = run_kpi(MockDBSession(), [3, 1, 2, 0])
    stats = await service.get_kpi_stats(filters={}, mine_user_id=None, visibility_user_id=9)
    assert stats == {
        "total": 3,
        "key_customers": 1,
        "incomplete_profile": 2,
        "my_customers": 0,
    }
    for call in db.execute.call_args_list[:3]:
        sql = str(call.args[0])
        assert "manager_id" in sql, "受限用户全量卡片必须按归属过滤"
