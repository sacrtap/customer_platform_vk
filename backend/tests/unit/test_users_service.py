"""UserService.get_all_users active_only 单元测试

覆盖 /users/options 仅返回启用用户的过滤分支（2026-09-29 可见性改造）。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


class MockDBSession(AsyncSession):
    def __init__(self):
        super().__init__()
        self.execute = AsyncMock()


def make_count_result(value):
    r = MagicMock()
    r.scalar = MagicMock(return_value=value)
    return r


def make_users_result(rows):
    r = MagicMock()
    r.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))
    return r


@pytest.fixture
def mock_db():
    return MockDBSession()


@pytest.mark.asyncio
async def test_get_all_users_active_only_adds_is_active_filter():
    """active_only=True：count 与列表查询的 WHERE 均追加 is_active 过滤"""
    from app.services.users import UserService

    db = MockDBSession()
    db.execute = AsyncMock(side_effect=[make_count_result(5), make_users_result([MagicMock()])])
    service = UserService(db)
    users, total = await service.get_all_users(page=1, page_size=2000, active_only=True)
    assert total == 5
    assert len(users) == 1
    for call in db.execute.call_args_list:
        sql = str(call.args[0])
        assert "WHERE" in sql, "查询应含 WHERE 子句"
        where_part = sql.split("WHERE", 1)[1]
        assert "is_active" in where_part, f"WHERE 必须过滤 is_active: {where_part}"


@pytest.mark.asyncio
async def test_get_all_users_without_active_only():
    """active_only=False（默认）：WHERE 不追加 is_active 过滤"""
    from app.services.users import UserService

    db = MockDBSession()
    db.execute = AsyncMock(side_effect=[make_count_result(3), make_users_result([MagicMock()])])
    service = UserService(db)
    users, total = await service.get_all_users(page=1, page_size=20)
    assert total == 3
    for call in db.execute.call_args_list:
        sql = str(call.args[0])
        where_part = sql.split("WHERE", 1)[1]
        assert "is_active" not in where_part, f"默认查询 WHERE 不应过滤 is_active: {where_part}"


@pytest.mark.asyncio
async def test_get_all_users_keyword_filter():
    """keyword：count 与列表查询均追加 username/real_name/email 模糊匹配"""
    from app.services.users import UserService

    db = MockDBSession()
    db.execute = AsyncMock(side_effect=[make_count_result(2), make_users_result([MagicMock()])])
    service = UserService(db)
    users, total = await service.get_all_users(keyword="张", active_only=True)
    assert total == 2
    for call in db.execute.call_args_list:
        sql = str(call.args[0])
        assert "username" in sql and "real_name" in sql and "email" in sql
