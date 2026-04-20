# 客户管理列表排序功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在客户管理列表中添加多列点击排序功能，默认按客户ID递增排序，支持按公司ID等字段排序。

**Architecture:** 前后端协同实现。后端在 `get_all_customers` 服务方法中添加动态排序支持，通过白名单验证防止注入；前端在 Arco Design 表格组件中启用 `sortable` 属性，通过 `@sort` 事件传递排序参数到 API。

**Tech Stack:** Python 3.12 + Sanic + SQLAlchemy 2.0, Vue 3.4 + TypeScript + Arco Design 2.54

---

### Task 1: 后端服务层 - 添加动态排序支持

**Files:**
- Modify: `backend/app/services/customers.py:164-248`

- [ ] **Step 1: 修改 `get_all_customers` 方法签名，添加排序参数**

在 `backend/app/services/customers.py` 第 164-169 行，修改方法签名：

```python
    async def get_all_customers(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[dict] = None,
        sort_by: str = "id",
        sort_order: str = "asc",
    ) -> Tuple[List[Customer], int]:
```

- [ ] **Step 2: 添加排序字段白名单常量**

在文件顶部（第 14 行附近，`CustomerService` 类定义之前）添加：

```python
# 允许排序的字段白名单
ALLOWED_SORT_FIELDS = {"id", "company_id", "name", "created_at", "updated_at"}
VALID_SORT_ORDERS = {"asc", "desc"}
```

- [ ] **Step 3: 添加排序参数验证和动态排序逻辑**

在 `get_all_customers` 方法中，替换第 235-236 行的硬编码排序：

原代码：
```python
        # 分页排序
        stmt = stmt.order_by(Customer.created_at.desc())
```

替换为：
```python
        # 验证排序参数
        if sort_by not in ALLOWED_SORT_FIELDS:
            raise ValueError(f"Invalid sort field: {sort_by}")
        if sort_order not in VALID_SORT_ORDERS:
            raise ValueError(f"Invalid sort order: {sort_order}")

        # 动态排序
        sort_column = getattr(Customer, sort_by)
        if sort_order == "desc":
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())
```

- [ ] **Step 4: 更新方法文档字符串**

更新 `get_all_customers` 的 docstring（第 170-186 行），添加排序参数说明：

```python
        """
        获取客户列表（支持筛选和分页）

        Args:
            page: 页码
            page_size: 每页数量
            filters: 筛选条件字典
                - keyword: 公司名称/公司 ID 关键词
                - account_type: 账号类型
                - industry: 行业类型（筛选 customer_profiles.industry）
                - manager_id: 运营经理 ID
                - settlement_type: 结算方式
                - is_key_customer: 是否重点客户
            sort_by: 排序字段，可选值：id, company_id, name, created_at, updated_at（默认 id）
            sort_order: 排序方向，asc 或 desc（默认 asc）

        Returns:
            (customers, total)
        """
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/customers.py
git commit -m "feat(customers): 添加动态排序支持到 get_all_customers 方法

- 新增 sort_by 和 sort_order 参数
- 添加排序字段白名单验证
- 默认按 id ASC 排序"
```

---

### Task 2: 后端路由层 - 解析并传递排序参数

**Files:**
- Modify: `backend/app/routes/customers.py:23-106`

- [ ] **Step 1: 在 `list_customers` 路由中解析排序参数**

在 `backend/app/routes/customers.py` 第 41-42 行（`page_size = min(...)` 之后）添加：

```python
    # 排序参数
    sort_by = request.args.get("sort_by", "id")
    sort_order = request.args.get("sort_order", "asc")
```

- [ ] **Step 2: 更新缓存 key 以包含排序信息**

修改第 64 行的缓存 key 生成逻辑：

原代码：
```python
    cache_key = f"p{page}_ps{page_size}_{hashlib.md5(str(sorted(filters.items())).encode()).hexdigest()[:8]}"
```

替换为：
```python
    cache_key = f"p{page}_ps{page_size}_sb{sort_by}_so{sort_order}_{hashlib.md5(str(sorted(filters.items())).encode()).hexdigest()[:8]}"
```

- [ ] **Step 3: 传递排序参数到服务方法并处理验证错误**

修改第 72-74 行的服务调用：

原代码：
```python
    customers, total = await service.get_all_customers(
        page=page, page_size=page_size, filters=filters
    )
```

替换为：
```python
    try:
        customers, total = await service.get_all_customers(
            page=page, page_size=page_size, filters=filters,
            sort_by=sort_by, sort_order=sort_order
        )
    except ValueError as e:
        return json({"code": 40001, "message": str(e)}, status=400)
```

- [ ] **Step 4: 更新路由文档字符串**

修改第 27-39 行的 docstring，添加排序参数说明：

```python
    """
    获取客户列表（支持筛选和排序）

    Query:
    - page: 页码 (默认 1)
    - page_size: 每页数量 (默认 20)
    - keyword: 关键词（公司名称/公司 ID）
    - account_type: 账号类型
    - industry: 行业类型
    - manager_id: 运营经理 ID
    - settlement_type: 结算方式
    - is_key_customer: 是否重点客户 (true/false)
    - sort_by: 排序字段 (id, company_id, name, created_at, updated_at，默认 id)
    - sort_order: 排序方向 (asc 或 desc，默认 asc)
    """
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/routes/customers.py
git commit -m "feat(customers): 路由层支持排序参数并更新缓存策略

- 解析 sort_by 和 sort_order 查询参数
- 缓存 key 包含排序维度
- 添加 ValueError 错误处理返回 400"
```

---

### Task 3: 后端测试 - 验证排序功能

**Files:**
- Create: `backend/tests/test_customers_sorting.py`
- Reference: 查看现有测试文件 `backend/tests/test_customers.py` 了解测试模式

- [ ] **Step 1: 创建测试文件并编写测试用例**

创建 `backend/tests/test_customers_sorting.py`：

```python
"""客户列表排序功能测试"""

import pytest
from app.services.customers import CustomerService, ALLOWED_SORT_FIELDS, VALID_SORT_ORDERS


class TestSortValidation:
    """排序参数验证测试"""

    def test_allowed_sort_fields_constant(self):
        """验证排序字段白名单包含预期字段"""
        expected_fields = {"id", "company_id", "name", "created_at", "updated_at"}
        assert ALLOWED_SORT_FIELDS == expected_fields

    def test_valid_sort_orders_constant(self):
        """验证排序方向白名单"""
        assert VALID_SORT_ORDERS == {"asc", "desc"}

    def test_invalid_sort_field_raises_value_error(self):
        """无效排序字段应抛出 ValueError"""
        assert "invalid_field" not in ALLOWED_SORT_FIELDS
        assert "password" not in ALLOWED_SORT_FIELDS
        assert "deleted_at" not in ALLOWED_SORT_FIELDS

    def test_invalid_sort_order_raises_value_error(self):
        """无效排序方向应抛出 ValueError"""
        assert "ASC" not in VALID_SORT_ORDERS  # 区分大小写
        assert "DESC" not in VALID_SORT_ORDERS
        assert "random" not in VALID_SORT_ORDERS


class TestSortServiceIntegration:
    """服务层排序集成测试（需要数据库 fixture）"""

    @pytest.mark.asyncio
    async def test_default_sort_is_id_asc(self, async_session, test_customers):
        """默认应按 id 递增排序"""
        service = CustomerService(async_session)
        customers, total = await service.get_all_customers(page=1, page_size=100)
        assert total >= 2
        # 验证 id 递增
        for i in range(len(customers) - 1):
            assert customers[i].id <= customers[i + 1].id

    @pytest.mark.asyncio
    async def test_sort_by_company_id_asc(self, async_session, test_customers):
        """按 company_id 升序排序"""
        service = CustomerService(async_session)
        customers, total = await service.get_all_customers(
            page=1, page_size=100, sort_by="company_id", sort_order="asc"
        )
        for i in range(len(customers) - 1):
            assert customers[i].company_id <= customers[i + 1].company_id

    @pytest.mark.asyncio
    async def test_sort_by_company_id_desc(self, async_session, test_customers):
        """按 company_id 降序排序"""
        service = CustomerService(async_session)
        customers, total = await service.get_all_customers(
            page=1, page_size=100, sort_by="company_id", sort_order="desc"
        )
        for i in range(len(customers) - 1):
            assert customers[i].company_id >= customers[i + 1].company_id

    @pytest.mark.asyncio
    async def test_invalid_sort_field_raises(self, async_session):
        """无效排序字段应抛出 ValueError"""
        service = CustomerService(async_session)
        with pytest.raises(ValueError, match="Invalid sort field"):
            await service.get_all_customers(sort_by="invalid_field")

    @pytest.mark.asyncio
    async def test_invalid_sort_order_raises(self, async_session):
        """无效排序方向应抛出 ValueError"""
        service = CustomerService(async_session)
        with pytest.raises(ValueError, match="Invalid sort order"):
            await service.get_all_customers(sort_order="DESC")
```

- [ ] **Step 2: 运行测试验证失败（此时测试应失败，因为服务层尚未实现）**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_customers_sorting.py -v
```

预期：部分测试失败（服务层未实现排序功能）

- [ ] **Step 3: 实现完成后再次运行测试**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_customers_sorting.py -v
```

预期：所有测试通过

- [ ] **Step 4: 提交**

```bash
git add backend/tests/test_customers_sorting.py
git commit -m "test(customers): 添加排序功能测试用例

- 测试排序字段白名单验证
- 测试默认排序 id ASC
- 测试 company_id 升序/降序
- 测试无效参数错误处理"
```

---

### Task 4: 前端 API 层 - 添加排序参数类型定义

**Files:**
- Modify: `frontend/src/api/customers.ts:5-16`

- [ ] **Step 1: 更新 `getCustomers` 函数签名**

修改 `frontend/src/api/customers.ts` 第 5-16 行：

```typescript
// 获取客户列表
export function getCustomers(params?: {
  page?: number
  page_size?: number
  keyword?: string
  account_type?: string
  industry?: string
  manager_id?: number
  settlement_type?: string
  is_key_customer?: boolean
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}) {
  return api.get('/customers', { params })
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/customers.ts
git commit -m "feat(customers): API 层添加排序参数类型定义

- getCustomers 支持 sort_by 和 sort_order 参数"
```

---

### Task 5: 前端页面组件 - 启用表格排序功能

**Files:**
- Modify: `frontend/src/views/customers/Index.vue`

- [ ] **Step 1: 添加排序状态管理**

在 `frontend/src/views/customers/Index.vue` 第 493 行（`const customers = ref<Customer[]>([])` 之后）添加：

```typescript
// 排序状态
const sortState = reactive({
  sort_by: 'id',
  sort_order: 'asc' as 'asc' | 'desc',
})
```

- [ ] **Step 2: 修改列定义，启用排序**

修改第 503-512 行的 `columns` 数组：

```typescript
const columns = [
  { title: '公司 ID', dataIndex: 'company_id', width: 140, sortable: true, ellipsis: true, tooltip: true },
  { title: '客户名称', dataIndex: 'name', width: 250, ellipsis: true, tooltip: true },
  { title: '行业类型', dataIndex: 'industry', width: 100 },
  { title: '结算方式', slotName: 'settlementType', width: 100 },
  { title: '运营经理', slotName: 'manager', width: 150, ellipsis: true, tooltip: true },
  { title: '重点客户', slotName: 'isKeyCustomer', width: 100 },
  { title: '创建时间', slotName: 'createdAt', width: 180 },
  { title: '操作', slotName: 'action', width: 320, fixed: 'right' as const },
]
```

- [ ] **Step 3: 添加排序事件处理函数**

在 `loadCustomers` 函数之前（约第 533 行）添加：

```typescript
// 处理排序
const handleSort = (dataIndex: string, direction: 'asc' | 'desc' | '') => {
  if (!direction) {
    // 取消排序时恢复默认
    sortState.sort_by = 'id'
    sortState.sort_order = 'asc'
  } else {
    sortState.sort_by = dataIndex
    sortState.sort_order = direction
  }
  pagination.current = 1 // 重置到第一页
  loadCustomers()
}
```

- [ ] **Step 4: 修改 `loadCustomers` 函数，传递排序参数**

修改第 534-564 行的 `loadCustomers` 函数：

```typescript
// 加载客户列表
const loadCustomers = async () => {
  loading.value = true
  try {
    const params: {
      page: number
      page_size: number
      keyword?: string
      account_type?: string
      industry?: string
      manager_id?: number
      is_key_customer?: boolean
      sort_by: string
      sort_order: 'asc' | 'desc'
    } = {
      page: pagination.current,
      page_size: pagination.pageSize,
      sort_by: sortState.sort_by,
      sort_order: sortState.sort_order,
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.account_type) params.account_type = filters.account_type
    if (filters.industry) params.industry = filters.industry
    if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer
    if (advancedFilters.manager_id) params.manager_id = advancedFilters.manager_id

    const res = await getCustomers(params)
    customers.value = res.data.list || []
    pagination.total = res.data.total || 0
    pagination.current = res.data.page || 1
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 5: 绑定排序事件到表格组件**

修改第 193-200 行的表格组件：

```vue
      <a-table
        :columns="columns"
        :data="customers"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        @page-change="handlePageChange"
        @sort="handleSort"
      >
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/views/customers/Index.vue
git commit -m "feat(customers): 前端表格启用排序功能

- 添加 sortState 状态管理
- 公司ID列启用 sortable
- 实现 handleSort 事件处理
- loadCustomers 传递排序参数
- 默认按 id ASC 排序"
```

---

### Task 6: 运行完整测试验证

- [ ] **Step 1: 运行后端测试**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -v -k "customer" --tb=short
```

- [ ] **Step 2: 运行前端类型检查**

```bash
cd frontend && npm run type-check
```

- [ ] **Step 3: 运行前端 lint**

```bash
cd frontend && npm run lint
```

- [ ] **Step 4: 启动后端服务手动验证**

```bash
cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 `http://localhost:8000/api/v1/customers?sort_by=company_id&sort_order=asc` 验证排序生效

- [ ] **Step 5: 启动前端服务手动验证**

```bash
cd frontend && npm run dev
```

打开 `http://localhost:5173/customers`，验证：
1. 列表默认按客户ID递增排序
2. 点击"公司ID"列标题可切换升序/降序
3. 排序图标显示正确

- [ ] **Step 6: 提交（如有必要）**

```bash
git status
# 如有未提交的文件，按需提交
```

---

## 验收检查清单

- [ ] 后端 `get_all_customers` 支持 `sort_by` 和 `sort_order` 参数
- [ ] 默认排序为 `id ASC`
- [ ] 排序字段白名单验证生效（非法字段返回 400）
- [ ] 缓存 key 包含排序维度
- [ ] 前端 API 类型定义包含排序参数
- [ ] 前端表格"公司ID"列可点击排序
- [ ] 排序事件正确传递参数到后端
- [ ] 所有测试通过
- [ ] TypeScript 类型检查通过
- [ ] ESLint 检查通过
