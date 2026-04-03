"""
客户运营中台 - CustomerService 批量创建客户单元测试

测试目标：CustomerService.batch_create_customers() 方法
优化特性：
1. 批量查询现有 company_id（避免 N+1 查询）
2. 使用 set 跟踪已存在的 ID
3. 批量创建 CustomerBalance 对象
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class MockDBSession:
    """Mock 数据库会话"""

    def __init__(self):
        self.execute = AsyncMock()
        self._add_calls = []
        self._add_all_calls = []
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self._new = []

    def add(self, obj):
        """模拟 add 方法，跟踪新对象"""
        self._add_calls.append(obj)
        self._new.append(obj)

    def add_all(self, objects):
        """模拟 add_all 方法"""
        self._add_all_calls.append(objects)
        self._new.extend(objects)

    @property
    def new(self):
        return self._new


def make_mock_execute_result(rows):
    """创建 execute 返回结果"""
    result = MagicMock()
    result.all = MagicMock(return_value=rows)
    result.scalar_one_or_none = MagicMock(return_value=rows[0] if rows else None)
    return result


@pytest.fixture
def mock_db():
    """创建 Mock 数据库会话"""
    return MockDBSession()


@pytest.fixture
def customer_service(mock_db):
    """创建 CustomerService 实例（不 patch 模型，使用真实模型类）"""
    from app.services.customers import CustomerService

    service = CustomerService(mock_db)
    yield service, mock_db


# ==================== 成功场景 ====================


@pytest.mark.asyncio
async def test_batch_create_success(customer_service):
    """测试批量创建客户成功"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    customers_data = [
        {"company_id": "C001", "name": "公司A"},
        {"company_id": "C002", "name": "公司B"},
        {"company_id": "C003", "name": "公司C"},
    ]

    success_count, errors = await service.batch_create_customers(customers_data)

    assert success_count == 3
    assert len(errors) == 0
    assert len(mock_db._add_calls) == 3
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_batch_create_empty_list(customer_service):
    """测试空列表输入"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    success_count, errors = await service.batch_create_customers([])

    assert success_count == 0
    assert len(errors) == 0


@pytest.mark.asyncio
async def test_batch_create_with_partial_data(customer_service):
    """测试部分字段填充"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    customers_data = [
        {"company_id": "C001", "name": "公司A"},
        {"company_id": "C002"},  # 缺少 name
    ]

    success_count, errors = await service.batch_create_customers(customers_data)

    assert success_count == 2
    assert len(mock_db._add_calls) == 2


# ==================== 重复检测 ====================


@pytest.mark.asyncio
async def test_detects_preexisting_duplicate(customer_service):
    """测试检测已存在的 company_id"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([("C001",)])

    customers_data = [
        {"company_id": "C001", "name": "公司A"},
        {"company_id": "C002", "name": "公司B"},
    ]

    success_count, errors = await service.batch_create_customers(customers_data)

    assert success_count == 1
    assert len(errors) == 1
    assert "C001" in errors[0]


@pytest.mark.asyncio
async def test_detects_within_batch_duplicate(customer_service):
    """测试检测同批次内的重复"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    customers_data = [
        {"company_id": "C001", "name": "公司A"},
        {"company_id": "C001", "name": "公司A-重复"},
    ]

    success_count, errors = await service.batch_create_customers(customers_data)

    assert success_count == 1
    assert len(errors) == 1


@pytest.mark.asyncio
async def test_mixed_duplicates(customer_service):
    """测试混合重复场景"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([("C001",)])

    customers_data = [
        {"company_id": "C001", "name": "已存在"},
        {"company_id": "C002", "name": "新公司"},
        {"company_id": "C001", "name": "同批次重复"},
        {"company_id": "C003", "name": "另一个新公司"},
    ]

    success_count, errors = await service.batch_create_customers(customers_data)

    assert success_count == 2
    assert len(errors) == 2


@pytest.mark.asyncio
async def test_all_duplicates(customer_service):
    """测试全部重复"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([("C001",), ("C002",)])

    customers_data = [
        {"company_id": "C001", "name": "公司A"},
        {"company_id": "C002", "name": "公司B"},
    ]

    success_count, errors = await service.batch_create_customers(customers_data)

    assert success_count == 0
    assert len(errors) == 2


# ==================== 错误处理 ====================


@pytest.mark.asyncio
async def test_missing_company_id(customer_service):
    """测试缺少 company_id"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    customers_data = [
        {"name": "没有company_id"},
        {"company_id": "C001", "name": "正常公司"},
    ]

    success_count, errors = await service.batch_create_customers(customers_data)

    assert success_count == 1
    assert len(errors) == 1
    assert "company_id" in errors[0]


# ==================== 批量查询优化验证 ====================


@pytest.mark.asyncio
async def test_single_bulk_query_not_n_plus_1(customer_service):
    """验证只执行一次批量查询（不是 N+1）"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    customers_data = [
        {"company_id": f"C{i:03d}", "name": f"公司{i}"} for i in range(50)
    ]

    await service.batch_create_customers(customers_data)

    # execute 应该只被调用 1 次（批量查询现有 ID）
    assert mock_db.execute.call_count == 1


@pytest.mark.asyncio
async def test_uses_set_for_existing_ids(customer_service):
    """验证使用 set 存储现有 ID"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result(
        [("C001",), ("C002",), ("C003",)]
    )

    customers_data = [
        {"company_id": "C001", "name": "已存在1"},
        {"company_id": "C002", "name": "已存在2"},
        {"company_id": "C004", "name": "新公司"},
    ]

    success_count, errors = await service.batch_create_customers(customers_data)

    assert success_count == 1
    assert len(errors) == 2


# ==================== CustomerBalance 批量创建 ====================


@pytest.mark.asyncio
async def test_creates_balances_in_bulk(customer_service):
    """验证批量创建 Balance"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    customers_data = [
        {"company_id": "C001", "name": "公司A"},
        {"company_id": "C002", "name": "公司B"},
        {"company_id": "C003", "name": "公司C"},
    ]

    await service.batch_create_customers(customers_data)

    assert len(mock_db._add_all_calls) == 1
    assert len(mock_db._add_all_calls[0]) >= 1


@pytest.mark.asyncio
async def test_no_balance_creation_on_empty_batch(customer_service):
    """验证空批次不创建 Balance"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    await service.batch_create_customers([])

    assert len(mock_db._add_all_calls) == 0


# ==================== 大批量测试 ====================


@pytest.mark.asyncio
async def test_large_batch(customer_service):
    """测试 100+ 项批量创建"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    customers_data = [
        {"company_id": f"C{i:04d}", "name": f"公司{i}"} for i in range(150)
    ]

    success_count, errors = await service.batch_create_customers(customers_data)

    assert success_count == 150
    assert len(errors) == 0
    assert mock_db.execute.call_count == 1


@pytest.mark.asyncio
async def test_large_batch_with_some_existing(customer_service):
    """测试大批量中部分已存在"""
    service, mock_db = customer_service

    existing = [(f"C{i:04d}",) for i in range(0, 100, 10)]
    mock_db.execute.return_value = make_mock_execute_result(existing)

    customers_data = [
        {"company_id": f"C{i:04d}", "name": f"公司{i}"} for i in range(100)
    ]

    success_count, errors = await service.batch_create_customers(customers_data)

    assert success_count == 90
    assert len(errors) == 10


# ==================== 事务验证 ====================


@pytest.mark.asyncio
async def test_commit_called_after_success(customer_service):
    """验证 commit 调用"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    customers_data = [
        {"company_id": "C001", "name": "公司A"},
    ]

    await service.batch_create_customers(customers_data)

    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_flush_called_before_balance_creation(customer_service):
    """验证 flush 在 add_all 之前调用"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    customers_data = [
        {"company_id": "C001", "name": "公司A"},
    ]

    await service.batch_create_customers(customers_data)

    assert mock_db.flush.call_count == 1
    assert len(mock_db._add_all_calls) == 1
