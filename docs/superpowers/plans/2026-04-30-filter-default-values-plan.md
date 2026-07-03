# 筛选项默认值优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为客户管理页面和余额管理页面的筛选项设置默认值，并在余额管理页面新增重点客户筛选项。

**Architecture:** 采用硬编码默认值方案，在两个 Vue 组件的 `filters` 响应式对象中设置初始值，并同步更新 `handleReset` 函数。余额管理页面新增 `is_key_customer` 筛选项，需要后端 API 同步支持该参数。

**Tech Stack:** Vue 3 + TypeScript + Arco Design (前端), Sanic + SQLAlchemy (后端)

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/app/routes/billing.py` | 余额管理 API，新增 `is_key_customer` 筛选支持 |
| `frontend/src/views/customers/Index.vue` | 客户管理页面，设置筛选项默认值 |
| `frontend/src/views/billing/Balance.vue` | 余额管理页面，设置筛选项默认值 + 新增重点客户筛选项 |

---

### Task 1: 后端 API 支持 is_key_customer 筛选

**Files:**
- Modify: `backend/app/routes/billing.py:44-54, 81-96, 143-166`

- [ ] **Step 1: 修改后端路由文件**

在 `backend/app/routes/billing.py` 的 `get_balances` 函数中进行以下修改：

**1.1 新增参数解析**（在第 54 行 `tag_ids` 之后添加）：

```python
# 在 recharge_date_to 和 tag_ids 之间添加
is_key_customer = request.args.get("is_key_customer")
if is_key_customer is not None:
    is_key_customer = is_key_customer.lower() == "true"
```

**1.2 添加主查询筛选条件**（在第 96 行 `sales_manager_id` 筛选之后添加）：

```python
# 在 sales_manager_id 筛选之后添加
if is_key_customer is not None:
    base_stmt = base_stmt.where(Customer.is_key_customer == is_key_customer)
```

**1.3 添加 count 查询筛选条件**（在第 166 行 `sales_manager_id` count 筛选之后添加）：

```python
# 在 sales_manager_id count 筛选之后添加
if is_key_customer is not None:
    count_stmt = count_stmt.where(Customer.is_key_customer == is_key_customer)
```

- [ ] **Step 2: 运行后端代码检查**

Run: `cd backend && flake8 app/routes/billing.py --max-line-length=120 --extend-ignore=E203`
Expected: PASS (no errors)

- [ ] **Step 3: 运行后端格式化**

Run: `cd backend && black app/routes/billing.py --exclude migrations`
Expected: PASS (file formatted)

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/billing.py
git commit -m "feat(billing): add is_key_customer filter to balances API"
```

---

### Task 2: 客户管理页面设置筛选项默认值

**Files:**
- Modify: `frontend/src/views/customers/Index.vue:516-522, 655-666`

- [ ] **Step 1: 修改 filters 初始化**

将第 516-522 行的 `filters` 初始化修改为：

```typescript
const filters = reactive({
  keyword: '',
  account_type: '正式账号',
  industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
  is_key_customer: null as boolean | null,
  settlement_type: '',
})
```

- [ ] **Step 2: 修改 handleReset 函数**

将第 655-666 行的 `handleReset` 函数修改为：

```typescript
const handleReset = () => {
  filters.keyword = ''
  filters.account_type = '正式账号'
  filters.industry = ['房产经纪', '房产ERP', '房产平台']
  filters.is_key_customer = null
  filters.settlement_type = ''
  advancedFilters.manager_id = null
  advancedFilters.sales_manager_id = null
  advancedFilters.tag_ids = []
  pagination.current = 1
  loadCustomers()
}
```

- [ ] **Step 3: 运行前端代码检查**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: PASS (no type errors)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/customers/Index.vue
git commit -m "feat(customers): set default filter values for account_type and industry"
```

---

### Task 3: 余额管理页面设置筛选项默认值并新增重点客户筛选项

**Files:**
- Modify: `frontend/src/views/billing/Balance.vue:29-86, 336-341, 488-498, 418-455`

- [ ] **Step 1: 修改 filters 初始化**

将第 336-341 行的 `filters` 初始化修改为：

```typescript
const filters = reactive({
  customer_id: undefined as number | undefined,
  recharge_date: [] as string[],
  industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
  account_type: '正式账号',
  is_key_customer: null as boolean | null,
})
```

- [ ] **Step 2: 修改 handleReset 函数**

将第 488-498 行的 `handleReset` 函数修改为：

```typescript
const handleReset = () => {
  filters.customer_id = undefined
  filters.recharge_date = []
  filters.industry = ['房产经纪', '房产ERP', '房产平台']
  filters.account_type = '正式账号'
  filters.is_key_customer = null
  advancedFilters.manager_id = null
  advancedFilters.sales_manager_id = null
  advancedFilters.tag_ids = []
  pagination.current = 1
  loadBalances()
}
```

- [ ] **Step 3: 新增重点客户筛选项（模板部分）**

在第 76 行（账号类型筛选项 `</a-col>` 之后）添加：

```vue
<a-col :xs="24" :sm="12" :md="8" :lg="4">
  <a-form-item label="重点客户">
    <a-select v-model="filters.is_key_customer" placeholder="请选择" allow-clear>
      <a-option :value="true">是</a-option>
      <a-option :value="false">否</a-option>
    </a-select>
  </a-form-item>
</a-col>
```

- [ ] **Step 4: 更新 loadBalances 参数构建**

在第 455 行（`tag_ids` 参数构建之后）添加：

```typescript
if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer
```

同时需要在 `params` 类型定义中添加 `is_key_customer` 字段（第 424-436 行）：

```typescript
const params: {
  page: number
  page_size: number
  customer_id?: number
  account_type?: string
  industry?: string
  manager_id?: number
  sales_manager_id?: number
  recharge_date_from?: string
  recharge_date_to?: string
  tag_ids?: string
  is_key_customer?: boolean  // 新增
  sort_by: string
  sort_order: 'asc' | 'desc'
} = {
```

- [ ] **Step 5: 运行前端代码检查**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: PASS (no type errors)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/billing/Balance.vue
git commit -m "feat(balance): set default filters and add is_key_customer filter"
```

---

### Task 4: 运行测试验证

- [ ] **Step 1: 运行后端测试**

Run: `cd backend && pytest tests/ -v --tb=short -x`
Expected: PASS (all tests pass)

- [ ] **Step 2: 运行前端构建**

Run: `cd frontend && npm run build`
Expected: PASS (build succeeds)

- [ ] **Step 3: 最终 Commit**

```bash
git add .
git commit -m "chore: verify filter default values implementation"
```

---

## 验收标准

1. ✅ 进入客户管理页面，账号类型默认显示"正式账号"，行业类型默认显示"房产经纪"、"房产ERP"、"房产平台"
2. ✅ 客户列表按默认筛选项加载
3. ✅ 点击"重置"按钮后，筛选项恢复到默认值（非清空）
4. ✅ 余额管理页面同样行为
5. ✅ 余额管理页面新增"重点客户"筛选项，功能与客户管理页面一致
6. ✅ 后端 API 支持 `is_key_customer` 参数筛选
