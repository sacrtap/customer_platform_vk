"""
客户群组服务单元测试

测试 CustomerGroupService 的 CRUD 操作
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime


class MockDBSession:
    """Mock 数据库会话"""

    def __init__(self):
        self.execute = AsyncMock()
        self.add = MagicMock()
        self.delete = MagicMock()
        self.commit = AsyncMock()
        self.flush = AsyncMock()
        self._new = []

    @property
    def new(self):
        return self._new


def make_mock_execute_result(rows, scalar_value=None):
    """创建 execute 返回结果"""
    result = MagicMock()
    result.all = MagicMock(return_value=rows)
    result.scalar = MagicMock(return_value=scalar_value)
    result.scalar_one_or_none = MagicMock(return_value=rows[0] if rows else None)
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))
    return result


@pytest.fixture
def mock_db():
    """创建 Mock 数据库会话"""
    return MockDBSession()


@pytest.fixture
def group_service(mock_db):
    """创建 CustomerGroupService 实例"""
    from app.services.groups import CustomerGroupService

    service = CustomerGroupService(mock_db)
    yield service, mock_db


# ==================== 创建群组测试 ====================


@pytest.mark.asyncio
async def test_create_dynamic_group(group_service):
    """测试创建动态群组"""
    service, mock_db = group_service

    mock_db.execute.return_value = make_mock_execute_result([])

    group = await service.create_group(
        name="Q1 重点客户",
        description="2026 年 Q1 重点客户",
        group_type="dynamic",
        filter_conditions={"customer_level": "KA"},
        created_by=1,
    )

    assert group.name == "Q1 重点客户"
    assert group.group_type == "dynamic"
    assert group.filter_conditions == {"customer_level": "KA"}
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_create_static_group(group_service):
    """测试创建静态群组"""
    service, mock_db = group_service

    mock_db.execute.return_value = make_mock_execute_result([])

    group = await service.create_group(
        name="手动客户群",
        description="手动管理的客户群",
        group_type="static",
        filter_conditions=None,
        created_by=1,
    )

    assert group.name == "手动客户群"
    assert group.group_type == "static"
    assert group.filter_conditions is None


@pytest.mark.asyncio
async def test_create_group_without_description(group_service):
    """测试创建无描述的群组"""
    service, mock_db = group_service

    mock_db.execute.return_value = make_mock_execute_result([])

    group = await service.create_group(
        name="简单群组",
        description=None,
        group_type="dynamic",
        filter_conditions=None,
        created_by=1,
    )

    assert group.name == "简单群组"
    assert group.description is None


# ==================== 获取用户群组列表测试 ====================


@pytest.mark.asyncio
async def test_get_user_groups(group_service):
    """测试获取用户的群组列表"""
    service, mock_db = group_service

    # Mock 返回的群组数据
    mock_group_a = MagicMock()
    mock_group_a.id = 1
    mock_group_a.name = "群组 A"
    mock_group_a.description = "描述 A"
    mock_group_a.group_type = "dynamic"
    mock_group_a.created_at = datetime(2026, 4, 1, 10, 0, 0)

    mock_group_b = MagicMock()
    mock_group_b.id = 2
    mock_group_b.name = "群组 B"
    mock_group_b.description = "描述 B"
    mock_group_b.group_type = "static"
    mock_group_b.created_at = datetime(2026, 4, 2, 10, 0, 0)

    mock_groups = [mock_group_a, mock_group_b]

    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=mock_groups)
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=scalars_mock)
    mock_db.execute.return_value = result_mock

    groups = await service.get_user_groups(user_id=1)

    assert len(groups) == 2
    assert groups[0].name == "群组 A"
    assert groups[1].name == "群组 B"


@pytest.mark.asyncio
async def test_get_user_groups_empty(group_service):
    """测试用户没有群组"""
    service, mock_db = group_service

    mock_db.execute.return_value = make_mock_execute_result([])

    groups = await service.get_user_groups(user_id=999)

    assert len(groups) == 0


# ==================== 获取群组详情测试 ====================


@pytest.mark.asyncio
async def test_get_group_detail(group_service):
    """测试获取群组详情"""
    service, mock_db = group_service

    mock_group = MagicMock()
    mock_group.id = 1
    mock_group.name = "测试群组"
    mock_group.description = "测试描述"
    mock_group.group_type = "dynamic"
    mock_group.filter_conditions = {"customer_level": "KA"}

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=mock_group)
    mock_db.execute.return_value = result_mock

    group = await service.get_group_detail(group_id=1)

    assert group is not None
    assert group.id == 1
    assert group.name == "测试群组"


@pytest.mark.asyncio
async def test_get_group_detail_not_found(group_service):
    """测试获取不存在的群组"""
    service, mock_db = group_service

    mock_db.execute.return_value = make_mock_execute_result([])

    group = await service.get_group_detail(group_id=999)

    assert group is None


# ==================== 更新群组测试 ====================


@pytest.mark.asyncio
async def test_update_group(group_service):
    """测试更新群组"""
    service, mock_db = group_service

    # Mock 现有的群组
    mock_group = MagicMock(
        id=1,
        name="旧名称",
        description="旧描述",
        group_type="dynamic",
        filter_conditions={"old": "value"},
    )

    # 第一次调用返回群组（get_group_detail）
    # 第二次调用返回空（update 后的 commit）
    mock_db.execute.side_effect = [
        make_mock_execute_result([mock_group]),
        make_mock_execute_result([]),
    ]

    updated_group = await service.update_group(
        group_id=1,
        data={"name": "新名称", "description": "新描述"},
    )

    assert updated_group is not None
    assert updated_group.name == "新名称"
    assert updated_group.description == "新描述"


@pytest.mark.asyncio
async def test_update_group_not_found(group_service):
    """测试更新不存在的群组"""
    service, mock_db = group_service

    mock_db.execute.return_value = make_mock_execute_result([])

    result = await service.update_group(
        group_id=999,
        data={"name": "新名称"},
    )

    assert result is None


# ==================== 删除群组测试 ====================


@pytest.mark.asyncio
async def test_delete_group(group_service):
    """测试删除群组（软删除）"""
    service, mock_db = group_service

    mock_group = MagicMock(
        id=1,
        name="测试群组",
        deleted_at=None,
    )

    mock_db.execute.side_effect = [
        make_mock_execute_result([mock_group]),
        make_mock_execute_result([]),
    ]

    result = await service.delete_group(group_id=1)

    assert result is True
    assert mock_group.deleted_at is not None
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_delete_group_not_found(group_service):
    """测试删除不存在的群组"""
    service, mock_db = group_service

    mock_db.execute.return_value = make_mock_execute_result([])

    result = await service.delete_group(group_id=999)

    assert result is False


# ==================== 添加成员测试 ====================


@pytest.mark.asyncio
async def test_add_member(group_service):
    """测试添加成员到静态群组"""
    service, mock_db = group_service

    # 检查是否已存在 - 返回空
    mock_db.execute.return_value = make_mock_execute_result([])

    result = await service.add_member(group_id=1, customer_id=100)

    assert result is True
    assert mock_db.add.call_count == 1
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_add_member_already_exists(group_service):
    """测试添加已存在的成员"""
    service, mock_db = group_service

    # 检查是否已存在 - 返回已存在
    existing_member = MagicMock(group_id=1, customer_id=100)
    mock_db.execute.return_value = make_mock_execute_result([existing_member])

    result = await service.add_member(group_id=1, customer_id=100)

    assert result is False
    assert mock_db.add.call_count == 0


# ==================== 移除成员测试 ====================


@pytest.mark.asyncio
async def test_remove_member(group_service):
    """测试移除成员"""
    service, mock_db = group_service

    mock_member = MagicMock()
    mock_member.group_id = 1
    mock_member.customer_id = 100

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=mock_member)
    mock_db.execute.return_value = result_mock
    mock_db.delete = AsyncMock()

    result = await service.remove_member(group_id=1, customer_id=100)

    assert result is True
    assert mock_db.delete.call_count == 1
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_remove_member_not_found(group_service):
    """测试移除不存在的成员"""
    service, mock_db = group_service

    mock_db.execute.return_value = make_mock_execute_result([])

    result = await service.remove_member(group_id=1, customer_id=999)

    assert result is False


# ==================== 获取群组成员列表测试 ====================


@pytest.mark.asyncio
async def test_get_group_members(group_service):
    """测试获取群组成员列表"""
    service, mock_db = group_service

    # Mock 计数查询结果
    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=25)

    # Mock 成员查询结果
    mock_customer_a = MagicMock()
    mock_customer_a.id = 1
    mock_customer_a.name = "客户 A"
    mock_customer_a.company_id = "C001"

    mock_customer_b = MagicMock()
    mock_customer_b.id = 2
    mock_customer_b.name = "客户 B"
    mock_customer_b.company_id = "C002"

    mock_customers = [mock_customer_a, mock_customer_b]

    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=mock_customers)
    members_result = MagicMock()
    members_result.scalars = MagicMock(return_value=scalars_mock)

    mock_db.execute.side_effect = [count_result, members_result]

    customers, total = await service.get_group_members(group_id=1, page=1, page_size=20)

    assert len(customers) == 2
    assert total == 25
    assert customers[0].name == "客户 A"


@pytest.mark.asyncio
async def test_get_group_members_empty(group_service):
    """测试获取空成员列表"""
    service, mock_db = group_service

    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=0)

    members_result = MagicMock()
    members_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )

    mock_db.execute.side_effect = [count_result, members_result]

    customers, total = await service.get_group_members(group_id=1, page=1, page_size=20)

    assert len(customers) == 0
    assert total == 0


# ==================== 应用群组筛选测试 ====================


@pytest.mark.asyncio
async def test_apply_group_filter_static(group_service):
    """测试应用静态群组筛选"""
    service, mock_db = group_service

    mock_group = MagicMock(id=1, group_type="static")

    # get_group_detail 返回
    # get_group_members 返回计数和成员
    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=10)

    members_result = MagicMock()
    members_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )

    mock_db.execute.side_effect = [
        make_mock_execute_result([mock_group]),
        count_result,
        members_result,
    ]

    customers, total = await service.apply_group_filter(
        group_id=1, page=1, page_size=20
    )

    assert total == 10


@pytest.mark.asyncio
async def test_apply_group_filter_dynamic(group_service):
    """测试应用动态群组筛选"""
    service, mock_db = group_service

    mock_group = MagicMock(
        id=1,
        group_type="dynamic",
        filter_conditions={"customer_level": "KA"},
    )

    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=50)

    filter_result = MagicMock()
    filter_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )

    mock_db.execute.side_effect = [
        make_mock_execute_result([mock_group]),
        count_result,
        filter_result,
    ]

    customers, total = await service.apply_group_filter(
        group_id=1, page=1, page_size=20
    )

    assert total == 50


@pytest.mark.asyncio
async def test_apply_group_filter_not_found(group_service):
    """测试应用不存在的群组筛选"""
    service, mock_db = group_service

    mock_db.execute.return_value = make_mock_execute_result([])

    customers, total = await service.apply_group_filter(
        group_id=999, page=1, page_size=20
    )

    assert len(customers) == 0
    assert total == 0


# ==================== 获取群组统计测试 ====================


@pytest.mark.asyncio
async def test_get_group_stats_static(group_service):
    """测试获取静态群组统计"""
    service, mock_db = group_service

    mock_group = MagicMock()
    mock_group.id = 1
    mock_group.name = "测试群组"
    mock_group.group_type = "static"

    group_result = MagicMock()
    group_result.scalar_one_or_none = MagicMock(return_value=mock_group)

    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=100)

    mock_db.execute.side_effect = [group_result, count_result]

    stats = await service.get_group_stats(group_id=1)

    assert stats["id"] == 1
    assert stats["name"] == "测试群组"
    assert stats["group_type"] == "static"
    assert stats["member_count"] == 100


@pytest.mark.asyncio
async def test_get_group_stats_dynamic(group_service):
    """测试获取动态群组统计"""
    service, mock_db = group_service

    mock_group = MagicMock()
    mock_group.id = 1
    mock_group.name = "动态群组"
    mock_group.group_type = "dynamic"
    mock_group.filter_conditions = {"customer_level": "KA"}

    # get_group_detail 第一次调用 (get_group_stats)
    group_result = MagicMock()
    group_result.scalar_one_or_none = MagicMock(return_value=mock_group)

    # apply_group_filter 中的 get_group_detail 第二次调用
    group_result2 = MagicMock()
    group_result2.scalar_one_or_none = MagicMock(return_value=mock_group)

    # 计数查询
    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=75)

    # 筛选查询
    filter_scalars = MagicMock()
    filter_scalars.all = MagicMock(return_value=[])
    filter_result = MagicMock()
    filter_result.scalars = MagicMock(return_value=filter_scalars)

    mock_db.execute.side_effect = [
        group_result,
        group_result2,
        count_result,
        filter_result,
    ]

    stats = await service.get_group_stats(group_id=1)

    assert stats["id"] == 1
    assert stats["name"] == "动态群组"
    assert stats["group_type"] == "dynamic"
    assert stats["member_count"] == 75


@pytest.mark.asyncio
async def test_get_group_stats_not_found(group_service):
    """测试获取不存在群组的统计"""
    service, mock_db = group_service

    mock_db.execute.return_value = make_mock_execute_result([])

    stats = await service.get_group_stats(group_id=999)

    assert stats == {}
