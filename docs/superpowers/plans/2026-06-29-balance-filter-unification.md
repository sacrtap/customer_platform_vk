# 余额管理筛选项统一实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将客户管理页面的筛选项（房产客户、结算方式）同步到余额管理页面，同时保留余额管理特有的充值时间筛选。

**Architecture:** 后端在余额 API 路由中添加 `is_real_estate` 和 `settlement_type` 参数支持，前端在余额管理页面添加对应的筛选组件，调整筛选项顺序使其与客户管理页面一致。

**Tech Stack:** Python (Sanic), TypeScript (Vue 3 + Arco Design), PostgreSQL

## Global Constraints

- 数据库事务：所有修改操作必须在 `async with db_session.begin():` 块内执行
- 权限校验：所有 API 端点必须添加 `@auth_required` 装饰器
- 测试覆盖率：CI 要求测试覆盖率 ≥50%
- Python 版本：必须使用 Python 3.12.x

---

## File Structure

**后端改动:**
- `backend/app/routes/billing.py` — 添加 `is_real_estate` 和 `settlement_type` 筛选参数支持

**前端改动:**
- `frontend/src/views/billing/Balance.vue` — 添加筛选组件、调整筛选顺序、更新数据结构和 API 调用

**测试文件:**
- `backend/tests/integration/test_billing_api.py` — 添加新筛选参数的集成测试

---

### Task 1: 后端 - 添加筛选参数解析

**Files:**
- Modify: `backend/app/routes/billing.py:61-68`

**Interfaces:**
- Consumes: `request.args.get()` — Sanic 请求参数获取
- Produces: `is_real_estate: bool | None`, `settlement_type: str | None` — 解析后的筛选参数

- [ ] **Step 1: 在 billing.py 第 61 行后添加新筛选参数解析**

在 `is_key_customer` 参数解析后（第 68 行后），添加以下代码：

```python
is_real_estate = request.args.get("is_real_estate")
if is_real_estate is not None and is_real_estate.strip() != "":
    if is_real_estate.lower() not in ("true", "false"):
        return json(
            {"code": 40001, "message": "is_real_estate 参数必须为 'true' 或 'false'"},
            status=400,
        )
    is_real_estate = is_real_estate.lower() == "true"
else:
    is_real_estate = None

settlement_type = request.args.get("settlement_type")
if settlement_type is not None and settlement_type.strip() == "":
    settlement_type = None
```

- [ ] **Step 2: 验证代码语法正确**

Run: `cd backend && python -m py_compile app/routes/billing.py`
Expected: 无错误输出

- [ ] **Step 3: 提交后端参数解析改动**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk
git add backend/app/routes/billing.py
git commit -m "feat(billing): 添加 is_real_estate 和 settlement_type 参数解析"
```

---

### Task 2: 后端 - 添加数据查询筛选条件

**Files:**
- Modify: `backend/app/routes/billing.py:114`

**Interfaces:**
- Consumes: `is_real_estate: bool | None`, `settlement_type: str | None` — Task 1 解析的参数
- Produces: 过滤后的 SQLAlchemy 查询语句

- [ ] **Step 1: 在 billing.py 第 114 行后添加数据查询筛选条件**

在 `if is_key_customer is not None:` 条件后（第 114 行后），添加以下代码：

```python
if is_real_estate is not None:
    base_stmt = base_stmt.where(Customer.is_real_estate == is_real_estate)

if settlement_type:
    base_stmt = base_stmt.where(Customer.settlement_type == settlement_type)
```

- [ ] **Step 2: 验证代码语法正确**

Run: `cd backend && python -m py_compile app/routes/billing.py`
Expected: 无错误输出

- [ ] **Step 3: 提交数据查询筛选条件改动**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk
git add backend/app/routes/billing.py
git commit -m "feat(billing): 在数据查询中添加 is_real_estate 和 settlement_type 筛选条件"
```

---

### Task 3: 后端 - 添加计数查询筛选条件

**Files:**
- Modify: `backend/app/routes/billing.py:188`

**Interfaces:**
- Consumes: `is_real_estate: bool | None`, `settlement_type: str | None` — Task 1 解析的参数
- Produces: 过滤后的计数查询语句，确保分页总数正确

- [ ] **Step 1: 在 billing.py 第 188 行后添加计数查询筛选条件**

在计数查询的 `if is_key_customer is not None:` 条件后（第 188 行后），添加以下代码：

```python
if is_real_estate is not None:
    count_stmt = count_stmt.where(Customer.is_real_estate == is_real_estate)

if settlement_type:
    count_stmt = count_stmt.where(Customer.settlement_type == settlement_type)
```

- [ ] **Step 2: 验证代码语法正确**

Run: `cd backend && python -m py_compile app/routes/billing.py`
Expected: 无错误输出

- [ ] **Step 3: 提交计数查询筛选条件改动**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk
git add backend/app/routes/billing.py
git commit -m "feat(billing): 在计数查询中添加 is_real_estate 和 settlement_type 筛选条件"
```

---

### Task 4: 后端 - 编写集成测试

**Files:**
- Test: `backend/tests/integration/test_billing_api.py`

**Interfaces:**
- Consumes: 后端 API `GET /api/v1/billing/balances` 及其新筛选参数
- Produces: 5 个测试用例验证筛选功能

- [ ] **Step 1: 在 test_billing_api.py 文件末尾添加测试用例**

在文件末尾添加以下测试代码：

```python
@pytest.mark.asyncio
async def test_get_balances_filter_is_real_estate_true(test_client, auth_headers, db_session):
    """测试 is_real_estate=true 筛选"""
    from sqlalchemy import text
    
    # 清理已有数据
    await db_session.execute(text("DELETE FROM customer_balances"))
    await db_session.execute(text("DELETE FROM customers"))
    
    # 创建测试数据：房产客户
    await db_session.execute(text("""
        INSERT INTO customers (id, company_id, name, account_type, is_real_estate, created_at)
        VALUES (1, 'C001', '房产客户A', '正式账号', true, NOW())
    """))
    await db_session.execute(text("""
        INSERT INTO customer_balances (id, customer_id, total_amount, used_total, created_at)
        VALUES (1, 1, 1000.0, 200.0, NOW())
    """))
    
    # 创建测试数据：非房产客户
    await db_session.execute(text("""
        INSERT INTO customers (id, company_id, name, account_type, is_real_estate, created_at)
        VALUES (2, 'C002', '非房产客户B', '正式账号', false, NOW())
    """))
    await db_session.execute(text("""
        INSERT INTO customer_balances (id, customer_id, total_amount, used_total, created_at)
        VALUES (2, 2, 2000.0, 400.0, NOW())
    """))
    
    await db_session.commit()
    
    # 测试筛选 is_real_estate=true
    response = await test_client.get(
        "/api/v1/billing/balances?is_real_estate=true",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["list"][0]["customer_name"] == "房产客户A"


@pytest.mark.asyncio
async def test_get_balances_filter_is_real_estate_false(test_client, auth_headers, db_session):
    """测试 is_real_estate=false 筛选"""
    from sqlalchemy import text
    
    # 使用上一个测试的数据
    response = await test_client.get(
        "/api/v1/billing/balances?is_real_estate=false",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["list"][0]["customer_name"] == "非房产客户B"


@pytest.mark.asyncio
async def test_get_balances_filter_settlement_type_prepaid(test_client, auth_headers, db_session):
    """测试 settlement_type=prepaid 筛选"""
    from sqlalchemy import text
    
    # 清理已有数据
    await db_session.execute(text("DELETE FROM customer_balances"))
    await db_session.execute(text("DELETE FROM customers"))
    
    # 创建测试数据：预付费客户
    await db_session.execute(text("""
        INSERT INTO customers (id, company_id, name, account_type, settlement_type, created_at)
        VALUES (1, 'C001', '预付费客户A', '正式账号', 'prepaid', NOW())
    """))
    await db_session.execute(text("""
        INSERT INTO customer_balances (id, customer_id, total_amount, used_total, created_at)
        VALUES (1, 1, 1000.0, 200.0, NOW())
    """))
    
    # 创建测试数据：后付费客户
    await db_session.execute(text("""
        INSERT INTO customers (id, company_id, name, account_type, settlement_type, created_at)
        VALUES (2, 'C002', '后付费客户B', '正式账号', 'postpaid', NOW())
    """))
    await db_session.execute(text("""
        INSERT INTO customer_balances (id, customer_id, total_amount, used_total, created_at)
        VALUES (2, 2, 2000.0, 400.0, NOW())
    """))
    
    await db_session.commit()
    
    # 测试筛选 settlement_type=prepaid
    response = await test_client.get(
        "/api/v1/billing/balances?settlement_type=prepaid",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["list"][0]["customer_name"] == "预付费客户A"


@pytest.mark.asyncio
async def test_get_balances_filter_settlement_type_postpaid(test_client, auth_headers, db_session):
    """测试 settlement_type=postpaid 筛选"""
    # 使用上一个测试的数据
    response = await test_client.get(
        "/api/v1/billing/balances?settlement_type=postpaid",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["list"][0]["customer_name"] == "后付费客户B"


@pytest.mark.asyncio
async def test_get_balances_filter_combined(test_client, auth_headers, db_session):
    """测试组合筛选 is_real_estate=true&settlement_type=prepaid"""
    from sqlalchemy import text
    
    # 清理已有数据
    await db_session.execute(text("DELETE FROM customer_balances"))
    await db_session.execute(text("DELETE FROM customers"))
    
    # 创建测试数据：房产+预付费
    await db_session.execute(text("""
        INSERT INTO customers (id, company_id, name, account_type, is_real_estate, settlement_type, created_at)
        VALUES (1, 'C001', '房产预付费A', '正式账号', true, 'prepaid', NOW())
    """))
    await db_session.execute(text("""
        INSERT INTO customer_balances (id, customer_id, total_amount, used_total, created_at)
        VALUES (1, 1, 1000.0, 200.0, NOW())
    """))
    
    # 创建测试数据：房产+后付费
    await db_session.execute(text("""
        INSERT INTO customers (id, company_id, name, account_type, is_real_estate, settlement_type, created_at)
        VALUES (2, 'C002', '房产后付费B', '正式账号', true, 'postpaid', NOW())
    """))
    await db_session.execute(text("""
        INSERT INTO customer_balances (id, customer_id, total_amount, used_total, created_at)
        VALUES (2, 2, 2000.0, 400.0, NOW())
    """))
    
    await db_session.commit()
    
    # 测试组合筛选
    response = await test_client.get(
        "/api/v1/billing/balances?is_real_estate=true&settlement_type=prepaid",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["list"][0]["customer_name"] == "房产预付费A"
```

- [ ] **Step 2: 运行测试验证**

Run: `cd backend && pytest tests/integration/test_billing_api.py::test_get_balances_filter_is_real_estate_true -v`
Expected: PASS

Run: `cd backend && pytest tests/integration/test_billing_api.py::test_get_balances_filter_is_real_estate_false -v`
Expected: PASS

Run: `cd backend && pytest tests/integration/test_billing_api.py::test_get_balances_filter_settlement_type_prepaid -v`
Expected: PASS

Run: `cd backend && pytest tests/integration/test_billing_api.py::test_get_balances_filter_settlement_type_postpaid -v`
Expected: PASS

Run: `cd backend && pytest tests/integration/test_billing_api.py::test_get_balances_filter_combined -v`
Expected: PASS

- [ ] **Step 3: 提交测试代码**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk
git add backend/tests/integration/test_billing_api.py
git commit -m "test(billing): 添加 is_real_estate 和 settlement_type 筛选集成测试"
```

---

### Task 5: 前端 - 修改 filters 数据结构

**Files:**
- Modify: `frontend/src/views/billing/Balance.vue:509-515`

**Interfaces:**
- Consumes: Vue 3 `reactive()` 函数
- Produces: 包含 `is_real_estate` 和 `settlement_type` 字段的 filters 对象

- [ ] **Step 1: 修改 Balance.vue 第 509-515 行的 createDefaultFilters 函数**

将现有的 `createDefaultFilters` 函数修改为：

```typescript
const createDefaultFilters = () => ({
  keyword: '',
  recharge_date: [] as string[],
  industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
  account_type: '正式账号',
  is_key_customer: null as boolean | null,
  is_real_estate: null as boolean | null,
  settlement_type: '',
})
```

- [ ] **Step 2: 验证 TypeScript 语法正确**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无错误输出（或仅有与本次改动无关的警告）

- [ ] **Step 3: 提交 filters 数据结构改动**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk
git add frontend/src/views/billing/Balance.vue
git commit -m "feat(balance): 在 filters 中添加 is_real_estate 和 settlement_type 字段"
```

---

### Task 6: 前端 - 修改模板筛选区域

**Files:**
- Modify: `frontend/src/views/billing/Balance.vue:38-96`

**Interfaces:**
- Consumes: `filters.is_real_estate`, `filters.settlement_type` — Task 5 定义的字段
- Produces: 调整后的筛选区域 UI，顺序：关键词 → 账号类型 → 行业类型 → 重点客户 → 房产客户 → 结算方式 → 充值时间 → 查询/重置

- [ ] **Step 1: 修改 Balance.vue 第 38-96 行的筛选区域模板**

将整个筛选区域替换为以下代码（调整顺序并添加新筛选项）：

```vue
<a-row :gutter="16">
  <a-col :xs="24" :sm="12" :md="8" :lg="4">
    <a-form-item label="关键词">
      <KeywordAutoComplete
        v-model="filters.keyword"
        placeholder="公司名称/公司 ID"
        width="100%"
      />
    </a-form-item>
  </a-col>
  <a-col :xs="24" :sm="12" :md="8" :lg="4">
    <a-form-item label="账号类型">
      <a-select v-model="filters.account_type" placeholder="请选择" allow-clear>
        <a-option value="正式账号">正式账号</a-option>
        <a-option value="测试账号">测试账号</a-option>
      </a-select>
    </a-form-item>
  </a-col>
  <a-col :xs="24" :sm="12" :md="8" :lg="4">
    <a-form-item label="行业类型">
      <a-select
        v-model="filters.industry"
        placeholder="请选择行业类型"
        allow-clear
        multiple
        :max-tag-count="1"
        :max-tag-placeholder="(count: number) => `+${count}`"
      >
        <a-option v-for="item in industryTypes" :key="item.id" :value="item.name">
          {{ item.name }}
        </a-option>
      </a-select>
    </a-form-item>
  </a-col>
  <a-col :xs="24" :sm="12" :md="8" :lg="4">
    <a-form-item label="重点客户">
      <a-select v-model="filters.is_key_customer" placeholder="请选择" allow-clear>
        <a-option :value="true">是</a-option>
        <a-option :value="false">否</a-option>
      </a-select>
    </a-form-item>
  </a-col>
  <a-col :xs="24" :sm="12" :md="8" :lg="4">
    <a-form-item label="房产客户">
      <a-select v-model="filters.is_real_estate" placeholder="请选择" allow-clear>
        <a-option :value="true">是</a-option>
        <a-option :value="false">否</a-option>
      </a-select>
    </a-form-item>
  </a-col>
  <a-col :xs="24" :sm="12" :md="8" :lg="4">
    <a-form-item label="结算方式">
      <a-select v-model="filters.settlement_type" placeholder="请选择" allow-clear>
        <a-option value="prepaid">预付费</a-option>
        <a-option value="postpaid">后付费</a-option>
      </a-select>
    </a-form-item>
  </a-col>
  <a-col :xs="24" :sm="12" :md="8" :lg="6">
    <a-form-item label="充值时间">
      <a-range-picker
        v-model="filters.recharge_date"
        :placeholder="['开始日期', '结束日期']"
        style="width: 100%"
        format="YYYY-MM-DD"
      />
    </a-form-item>
  </a-col>
  <a-col :xs="24" :sm="12" :md="8" :lg="4">
    <a-form-item label="&nbsp;">
      <a-space>
        <a-button type="primary" @click="handleSearch">查询</a-button>
        <a-button @click="handleReset">重置</a-button>
      </a-space>
    </a-form-item>
  </a-col>
</a-row>
```

- [ ] **Step 2: 验证 Vue 模板语法正确**

Run: `cd frontend && npm run build`
Expected: 构建成功（或仅有与本次改动无关的警告）

- [ ] **Step 3: 提交模板改动**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk
git add frontend/src/views/billing/Balance.vue
git commit -m "feat(balance): 调整筛选区域顺序并添加房产客户和结算方式筛选项"
```

---

### Task 7: 前端 - 修改 loadBalances 函数

**Files:**
- Modify: `frontend/src/views/billing/Balance.vue:748-781`

**Interfaces:**
- Consumes: `filters.is_real_estate`, `filters.settlement_type` — Task 5 定义的字段
- Produces: 包含新筛选参数的 API 请求

- [ ] **Step 1: 修改 Balance.vue 第 748-781 行的 loadBalances 函数**

将 `params` 类型定义和条件判断修改为：

```typescript
const params: {
  page: number
  page_size: number
  keyword?: string
  account_type?: string
  industry?: string
  manager_id?: number
  sales_manager_id?: number
  recharge_date_from?: string
  recharge_date_to?: string
  tag_ids?: string
  is_key_customer?: boolean
  is_real_estate?: boolean
  settlement_type?: string
  sort_by: string
  sort_order: 'asc' | 'desc'
} = {
  page: pagination.current,
  page_size: pagination.pageSize,
  sort_by: sortState.sort_by,
  sort_order: backendSortOrder,
}
if (filters.keyword) params.keyword = filters.keyword
if (filters.account_type) params.account_type = filters.account_type
if (filters.industry && filters.industry.length > 0)
  params.industry = filters.industry.join(',')
if (filters.recharge_date && filters.recharge_date.length === 2) {
  params.recharge_date_from = filters.recharge_date[0]
  params.recharge_date_to = filters.recharge_date[1]
}
if (advancedFilters.manager_id) params.manager_id = advancedFilters.manager_id
if (advancedFilters.sales_manager_id) params.sales_manager_id = advancedFilters.sales_manager_id
if (advancedFilters.tag_ids && advancedFilters.tag_ids.length > 0) {
  params.tag_ids = advancedFilters.tag_ids.join(',')
}
if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer
if (filters.is_real_estate !== null) params.is_real_estate = filters.is_real_estate
if (filters.settlement_type) params.settlement_type = filters.settlement_type
```

- [ ] **Step 2: 验证 TypeScript 语法正确**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无错误输出（或仅有与本次改动无关的警告）

- [ ] **Step 3: 提交 loadBalances 函数改动**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk
git add frontend/src/views/billing/Balance.vue
git commit -m "feat(balance): 在 loadBalances 中添加新筛选参数传递"
```

---

### Task 8: 前端 - 验证 handleReset 函数

**Files:**
- Modify: `frontend/src/views/billing/Balance.vue:815-822`

**Interfaces:**
- Consumes: `createDefaultFilters()` — Task 5 修改的函数
- Produces: 重置功能自动支持新字段（无需额外改动）

- [ ] **Step 1: 确认 handleReset 函数无需修改**

查看 Balance.vue 第 815-822 行的 `handleReset` 函数：

```typescript
const handleReset = () => {
  Object.assign(filters, createDefaultFilters())
  advancedFilters.manager_id = null
  advancedFilters.sales_manager_id = null
  advancedFilters.tag_ids = []
  pagination.current = 1
  loadBalances()
}
```

由于 `handleReset` 使用 `Object.assign(filters, createDefaultFilters())` 重置所有筛选字段，而 `createDefaultFilters()` 已在 Task 5 中添加了 `is_real_estate` 和 `settlement_type` 字段，因此重置功能自动支持新字段，无需额外修改。

- [ ] **Step 2: 无需提交（无代码改动）**

---

### Task 9: 集成测试 - 前端功能验收

**Files:**
- 无代码改动，仅功能验证

**Interfaces:**
- Consumes: 完整的前后端实现
- Produces: 功能验收报告

- [ ] **Step 1: 启动后端服务**

```bash
cd backend && make run
```

- [ ] **Step 2: 启动前端服务**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: 手动验证前端功能**

打开浏览器访问前端页面，进入余额管理页面，验证：

1. 筛选项顺序：关键词 → 账号类型 → 行业类型 → 重点客户 → 房产客户 → 结算方式 → 充值时间 → 查询/重置
2. "房产客户"下拉框正常工作（是/否/清空）
3. "结算方式"下拉框正常工作（预付费/后付费/清空）
4. 查询按钮点击后，新筛选参数正确传递给后端 API（通过浏览器开发者工具 Network 面板查看）
5. 重置按钮点击后，新筛选字段恢复默认值
6. 高级筛选（运营经理/商务经理/标签）不受影响

- [ ] **Step 4: 运行后端完整测试**

```bash
cd backend && pytest tests/integration/test_billing_api.py -v
```

Expected: 所有测试通过

- [ ] **Step 5: 提交最终验证（如有必要）**

如果验证过程中发现问题并修复，提交修复代码：

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk
git add .
git commit -m "fix: 修复集成测试中发现的问题"
```

---

## 实施顺序

1. **Task 1-3**: 后端改动（参数解析 + 数据查询 + 计数查询）
2. **Task 4**: 后端集成测试
3. **Task 5-7**: 前端改动（数据结构 + 模板 + API 调用）
4. **Task 8**: 验证 handleReset（无需改动）
5. **Task 9**: 集成测试和功能验收

---

## 回滚方案

如果实施过程中出现问题，可以通过以下方式回滚：

```bash
# 回滚到实施前的状态
git revert <commit-hash>

# 或者回滚多个提交
git reset --hard HEAD~<N>
```

由于本次改动仅涉及筛选功能，不影响核心业务逻辑，回滚风险较低。
