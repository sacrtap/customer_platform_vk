# 设计文档：筛选项默认值优化

**日期**: 2026-04-30
**状态**: 已批准
**方案**: 方案 A - 硬编码默认值

---

## 背景

客户管理页面和余额管理页面的筛选项初始为空，用户每次进入页面都需要手动设置常用筛选条件。为提升操作效率，需要为常用筛选项设置合理的默认值。

---

## 需求

1. **账号类型**：默认选中"正式账号"
2. **行业类型**：默认选中"房产经纪"、"房产ERP"、"房产平台"
3. **客户管理页面**：进入时列表自动按默认筛选项显示
4. **余额管理页面**：新增"重点客户"筛选项（与客户管理页面一致）
5. **重置按钮**：点击后恢复到默认值（而非清空）

---

## 设计方案

### 方案选择

采用**方案 A：硬编码默认值**。

**理由**：
- 需求明确且简单，改动量小
- 不需要额外的抽象层
- 两个页面改动独立，风险可控
- 未来如需集中管理，重构成本低

---

## 改动详情

### 1. 客户管理页面 (`frontend/src/views/customers/Index.vue`)

#### 1.1 filters 初始化

```typescript
// 修改前
const filters = reactive({
  keyword: '',
  account_type: '',
  industry: [] as string[],
  is_key_customer: null as boolean | null,
  settlement_type: '',
})

// 修改后
const filters = reactive({
  keyword: '',
  account_type: '正式账号',
  industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
  is_key_customer: null as boolean | null,
  settlement_type: '',
})
```

#### 1.2 handleReset 恢复默认值

```typescript
// 修改前
filters.account_type = ''
filters.industry = []

// 修改后
filters.account_type = '正式账号'
filters.industry = ['房产经纪', '房产ERP', '房产平台']
```

#### 1.3 自动加载行为

页面 `onMounted()` 调用 `loadCustomers()` 时，`filters` 已包含默认值，列表自动按默认条件加载。无需额外改动。

---

### 2. 余额管理页面 (`frontend/src/views/billing/Balance.vue`)

#### 2.1 filters 初始化

```typescript
// 修改前
const filters = reactive({
  customer_id: undefined as number | undefined,
  recharge_date: [] as string[],
  industry: [] as string[],
  account_type: '',
})

// 修改后
const filters = reactive({
  customer_id: undefined as number | undefined,
  recharge_date: [] as string[],
  industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
  account_type: '正式账号',
  is_key_customer: null as boolean | null,  // 新增
})
```

#### 2.2 handleReset 恢复默认值

```typescript
// 修改前
filters.industry = []
filters.account_type = ''

// 修改后
filters.industry = ['房产经纪', '房产ERP', '房产平台']
filters.account_type = '正式账号'
filters.is_key_customer = null  // 新增
```

#### 2.3 新增重点客户筛选项（模板）

在账号类型筛选项之后添加：

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

#### 2.4 loadBalances 参数构建

添加 `is_key_customer` 参数传递：

```typescript
if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer
```

---

## 影响范围

| 文件 | 改动类型 | 风险等级 |
|------|----------|----------|
| `backend/app/routes/billing.py` | 新增 `is_key_customer` 筛选参数支持 | 低 |
| `frontend/src/views/customers/Index.vue` | 修改 filters 初始值和 reset 逻辑 | 低 |
| `frontend/src/views/billing/Balance.vue` | 修改 filters 初始值、reset 逻辑、新增筛选项 | 低-中 |

---

## 后端改动详情

### 3. 余额管理 API (`backend/app/routes/billing.py`)

#### 3.1 新增 `is_key_customer` 参数解析

在 `get_balances` 函数中（约第 54 行后）添加：

```python
is_key_customer = request.args.get("is_key_customer")
if is_key_customer is not None:
    is_key_customer = is_key_customer.lower() == "true"
```

#### 3.2 添加筛选条件

在 `industry` 筛选之后（约第 96 行后）添加：

```python
if is_key_customer is not None:
    base_stmt = base_stmt.where(Customer.is_key_customer == is_key_customer)
```

#### 3.3 更新 count_stmt

在 `sales_manager_id` 筛选之后（约第 166 行后）添加：

```python
if is_key_customer is not None:
    count_stmt = count_stmt.where(Customer.is_key_customer == is_key_customer)
```

---

## 后端依赖确认

✅ **已确认**：后端 `GET /balances` API 需要新增 `is_key_customer` 参数支持，已在设计文档中补充。

---

## 验收标准

1. 进入客户管理页面，账号类型默认显示"正式账号"，行业类型默认显示"房产经纪"、"房产ERP"、"房产平台"
2. 客户列表按默认筛选项加载
3. 点击"重置"按钮后，筛选项恢复到默认值（非清空）
4. 余额管理页面同样行为
5. 余额管理页面新增"重点客户"筛选项，功能与客户管理页面一致
