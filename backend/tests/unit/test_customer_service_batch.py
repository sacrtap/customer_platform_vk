"""
客户运营中台 - CustomerService 批量创建客户单元测试

测试目标：CustomerService.batch_create_customers() 方法
优化特性：
1. 批量查询现有 company_id（避免 N+1 查询）
2. 使用 set 跟踪已存在的 ID
3. 批量创建 CustomerBalance 对象
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession


class MockDBSession(AsyncSession):
    """Mock 数据库会话"""

    def __init__(self):
        super().__init__()
        self.execute = AsyncMock()
        self._add_calls = []
        self._add_all_calls = []
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.refresh = AsyncMock()
        self._new = []
        self.add = MagicMock(side_effect=self._add_mock)
        self.add_all = MagicMock(side_effect=self._add_all_mock)

    def _add_mock(self, obj):
        """模拟 add 方法，跟踪新对象"""
        self._add_calls.append(obj)
        self._new.append(obj)

    def _add_all_mock(self, objects):
        """模拟 add_all 方法"""
        self._add_all_calls.append(objects)
        self._new.extend(objects)

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
    """测试部分字段填充 - 缺少 name 应被拒绝"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    customers_data = [
        {"company_id": "C001", "name": "公司A"},
        {"company_id": "C002"},  # 缺少 name - 应被拒绝
    ]

    success_count, errors = await service.batch_create_customers(customers_data)

    assert success_count == 1
    assert len(errors) == 1
    assert "缺少 name" in errors[0]
    assert len(mock_db._add_calls) == 1


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


# ==================== get_customer_by_id 测试 ====================


@pytest.mark.asyncio
async def test_get_customer_by_id_success(customer_service):
    """测试成功获取客户"""
    service, mock_db = customer_service

    mock_customer = MagicMock()
    mock_customer.id = 1
    mock_customer.name = "测试客户"
    mock_customer.company_id = "C001"

    mock_db.execute.return_value = make_mock_execute_result([mock_customer])

    customer = await service.get_customer_by_id(customer_id=1)

    assert customer is not None
    assert customer.id == 1
    assert customer.name == "测试客户"


@pytest.mark.asyncio
async def test_get_customer_by_id_not_found(customer_service):
    """测试获取不存在的客户"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    customer = await service.get_customer_by_id(customer_id=999)

    assert customer is None


# ==================== get_all_customers 测试 ====================


@pytest.mark.asyncio
async def test_get_all_customers_default(customer_service):
    """测试获取所有客户（默认分页）"""
    service, mock_db = customer_service

    mock_customer_a = MagicMock()
    mock_customer_a.id = 1
    mock_customer_a.name = "客户 A"

    mock_customer_b = MagicMock()
    mock_customer_b.id = 2
    mock_customer_b.name = "客户 B"

    mock_customers = [mock_customer_a, mock_customer_b]

    # Mock 计数查询
    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=2)

    # Mock 客户列表查询
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=mock_customers)
    customers_result = MagicMock()
    customers_result.scalars = MagicMock(return_value=scalars_mock)

    mock_db.execute.side_effect = [count_result, customers_result]

    customers, total = await service.get_all_customers()

    assert len(customers) == 2
    assert total == 2
    assert customers[0].name == "客户 A"


@pytest.mark.asyncio
async def test_get_all_customers_with_pagination(customer_service):
    """测试带分页的查询"""
    service, mock_db = customer_service

    mock_customer = MagicMock()
    mock_customer.id = 1
    mock_customer.name = "客户 A"

    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=50)

    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=[mock_customer])
    customers_result = MagicMock()
    customers_result.scalars = MagicMock(return_value=scalars_mock)

    mock_db.execute.side_effect = [count_result, customers_result]

    customers, total = await service.get_all_customers(page=2, page_size=10)

    assert total == 50
    assert len(customers) == 1


@pytest.mark.asyncio
async def test_get_all_customers_with_keyword_filter(customer_service):
    """测试关键词筛选"""
    service, mock_db = customer_service

    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=3)

    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=[])
    customers_result = MagicMock()
    customers_result.scalars = MagicMock(return_value=scalars_mock)

    mock_db.execute.side_effect = [count_result, customers_result]

    filters = {"keyword": "科技"}
    customers, total = await service.get_all_customers(filters=filters)

    assert total == 3


@pytest.mark.asyncio
async def test_get_all_customers_with_multiple_filters(customer_service):
    """测试多个筛选条件"""
    service, mock_db = customer_service

    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=5)

    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=[])
    customers_result = MagicMock()
    customers_result.scalars = MagicMock(return_value=scalars_mock)

    mock_db.execute.side_effect = [count_result, customers_result]

    filters = {
        "account_type": "企业",
        "customer_level": "KA",
        "is_key_customer": True,
    }
    customers, total = await service.get_all_customers(filters=filters)

    assert total == 5


@pytest.mark.asyncio
async def test_get_all_customers_empty(customer_service):
    """测试空结果"""
    service, mock_db = customer_service

    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=0)

    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=[])
    customers_result = MagicMock()
    customers_result.scalars = MagicMock(return_value=scalars_mock)

    mock_db.execute.side_effect = [count_result, customers_result]

    customers, total = await service.get_all_customers()

    assert len(customers) == 0
    assert total == 0


# ==================== create_customer 测试 ====================


@pytest.mark.asyncio
async def test_create_customer_success(customer_service):
    """测试成功创建客户"""
    service, mock_db = customer_service

    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    data = {
        "company_id": "C001",
        "name": "测试公司",
        "account_type": "企业",
        "customer_level": "KA",
    }

    customer = await service.create_customer(data)

    assert customer.company_id == "C001"
    assert customer.name == "测试公司"
    assert mock_db.flush.call_count == 1
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_create_customer_with_all_fields(customer_service):
    """测试创建完整字段客户"""
    service, mock_db = customer_service

    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    data = {
        "company_id": "C001",
        "name": "测试公司",
        "account_type": "企业",
        "customer_level": "KA",
        "price_policy": "VIP",
        "manager_id": 1,
        "settlement_cycle": "月结",
        "settlement_type": "银行转账",
        "is_key_customer": True,
        "email": "test@example.com",
    }

    customer = await service.create_customer(data)

    assert customer.company_id == "C001"
    assert customer.is_key_customer is True
    assert customer.email == "test@example.com"


# ==================== update_customer 测试 ====================


@pytest.mark.asyncio
async def test_update_customer_success(customer_service):
    """测试成功更新客户"""
    service, mock_db = customer_service

    mock_customer = MagicMock()
    mock_customer.id = 1
    mock_customer.name = "旧名称"

    # get_customer_by_id 返回
    mock_db.execute.return_value = make_mock_execute_result([mock_customer])

    data = {"name": "新名称", "customer_level": "KA"}

    customer = await service.update_customer(customer_id=1, data=data)

    assert customer is not None
    assert customer.name == "新名称"
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_update_customer_partial_fields(customer_service):
    """测试部分字段更新"""
    service, mock_db = customer_service

    mock_customer = MagicMock()
    mock_customer.id = 1
    mock_customer.name = "旧名称"
    mock_customer.customer_level = "A"

    mock_db.execute.return_value = make_mock_execute_result([mock_customer])

    data = {"name": "新名称"}

    customer = await service.update_customer(customer_id=1, data=data)

    assert customer.name == "新名称"
    # customer_level 应该保持不变


@pytest.mark.asyncio
async def test_update_customer_not_found(customer_service):
    """测试更新不存在的客户"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    data = {"name": "新名称"}

    customer = await service.update_customer(customer_id=999, data=data)

    assert customer is None


# ==================== delete_customer 测试 ====================


@pytest.mark.asyncio
async def test_delete_customer_success(customer_service):
    """测试成功删除客户（软删除）"""
    service, mock_db = customer_service

    mock_customer = MagicMock()
    mock_customer.id = 1
    mock_customer.deleted_at = None

    mock_db.execute.return_value = make_mock_execute_result([mock_customer])

    result = await service.delete_customer(customer_id=1)

    assert result is True
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_delete_customer_not_found(customer_service):
    """测试删除不存在的客户"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    result = await service.delete_customer(customer_id=999)

    assert result is False


# ==================== get_customer_profile 测试 ====================


@pytest.mark.asyncio
async def test_get_customer_profile_success(customer_service):
    """测试成功获取客户画像"""
    service, mock_db = customer_service

    mock_profile = MagicMock()
    mock_profile.id = 1
    mock_profile.customer_id = 1
    mock_profile.scale_level = "大"

    mock_db.execute.return_value = make_mock_execute_result([mock_profile])

    profile = await service.get_customer_profile(customer_id=1)

    assert profile is not None
    assert profile.customer_id == 1
    assert profile.scale_level == "大"


@pytest.mark.asyncio
async def test_get_customer_profile_not_found(customer_service):
    """测试获取不存在的客户画像"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    profile = await service.get_customer_profile(customer_id=999)

    assert profile is None


# ==================== create_or_update_profile 测试 ====================


@pytest.mark.asyncio
async def test_create_profile(customer_service):
    """测试创建新画像"""
    service, mock_db = customer_service

    # get_customer_profile 返回空
    mock_db.execute.return_value = make_mock_execute_result([])

    data = {
        "scale_level": "大",
        "consume_level": "高",
        "industry": "互联网",
        "is_real_estate": False,
        "description": "测试描述",
    }

    profile = await service.create_or_update_profile(customer_id=1, data=data)

    assert profile.customer_id == 1
    assert profile.scale_level == "大"
    assert mock_db.add.call_count == 1
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_update_existing_profile(customer_service):
    """测试更新现有画像"""
    service, mock_db = customer_service

    mock_profile = MagicMock()
    mock_profile.id = 1
    mock_profile.customer_id = 1
    mock_profile.scale_level = "小"

    # get_customer_profile 返回现有画像
    mock_db.execute.return_value = make_mock_execute_result([mock_profile])

    data = {"scale_level": "大", "consume_level": "高"}

    profile = await service.create_or_update_profile(customer_id=1, data=data)

    assert profile.scale_level == "大"
    # 不应该调用 add，因为已存在
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
async def test_create_profile_partial_fields(customer_service):
    """测试创建画像（部分字段）"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    data = {"scale_level": "中"}

    profile = await service.create_or_update_profile(customer_id=1, data=data)

    assert profile.scale_level == "中"
    assert profile.consume_level is None  # 未提供字段应为 None


# ==================== 边界条件测试 ====================


@pytest.mark.asyncio
async def test_get_all_customers_with_manager_filter(customer_service):
    """测试按运营经理筛选"""
    service, mock_db = customer_service

    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=3)

    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=[])
    customers_result = MagicMock()
    customers_result.scalars = MagicMock(return_value=scalars_mock)

    mock_db.execute.side_effect = [count_result, customers_result]

    filters = {"manager_id": 1}
    customers, total = await service.get_all_customers(filters=filters)

    assert total == 3


@pytest.mark.asyncio
async def test_get_all_customers_with_settlement_type_filter(customer_service):
    """测试按结算方式筛选"""
    service, mock_db = customer_service

    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=510)

    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=[])
    customers_result = MagicMock()
    customers_result.scalars = MagicMock(return_value=scalars_mock)

    mock_db.execute.side_effect = [count_result, customers_result]

    filters = {"settlement_type": "银行转账"}
    customers, total = await service.get_all_customers(filters=filters)

    assert total == 510


@pytest.mark.asyncio
async def test_get_all_customers_with_all_filter_types(customer_service):
    """测试所有筛选条件"""
    service, mock_db = customer_service

    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=1)

    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=[])
    customers_result = MagicMock()
    customers_result.scalars = MagicMock(return_value=scalars_mock)

    mock_db.execute.side_effect = [count_result, customers_result]

    filters = {
        "keyword": "科技",
        "account_type": "企业",
        "business_type": "互联网",
        "customer_level": "KA",
        "manager_id": 1,
        "settlement_type": "银行转账",
        "is_key_customer": True,
    }
    customers, total = await service.get_all_customers(filters=filters)

    assert total == 1


@pytest.mark.asyncio
async def test_batch_create_with_exception(customer_service):
    """测试批量创建时的异常处理"""
    service, mock_db = customer_service

    mock_db.execute.return_value = make_mock_execute_result([])

    # 使用无效数据触发异常
    customers_data = [{"company_id": "C001", "name": "正常公司"}]

    # 让 add 方法抛出异常
    original_add = service.db.add
    service.db.add = MagicMock(side_effect=Exception("数据库错误"))

    success_count, errors = await service.batch_create_customers(customers_data)

    assert success_count == 0
    assert len(errors) == 1
    assert "数据库错误" in errors[0]

    # 恢复原始方法
    service.db.add = original_add
