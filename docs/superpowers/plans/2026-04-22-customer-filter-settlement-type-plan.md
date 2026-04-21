# 客户管理页面新增结算方式筛选项 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在客户管理页面第一行筛选项中新增"结算方式"筛选项，保持查询/重置按钮始终在第一行最右侧。

**Architecture:** 仅前端改动，在 `Index.vue` 中新增筛选项组件、响应式状态、API 参数传递和重置逻辑。后端已支持 `settlement_type` 筛选参数。

**Tech Stack:** Vue 3.4 + TypeScript + Arco Design

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/views/customers/Index.vue` | Modify | 新增筛选项模板、状态、参数传递、重置逻辑 |
| `docs/superpowers/specs/2026-04-22-customer-filter-settlement-type-design.md` | Already exists | 设计文档 |

---

### Task 1: 新增结算方式筛选项到模板层

**Files:**
- Modify: `frontend/src/views/customers/Index.vue:117-125`（在第 4 个筛选项后、按钮列前插入新列）

- [ ] **Step 1: 插入结算方式筛选项模板**

在现有代码第 117 行（重点客户筛选项结束 `</a-col>`）和第 118 行（按钮列开始 `<a-col>`）之间，插入以下代码：

```vue
          <a-col :xs="24" :sm="12" :md="8" :lg="4">
            <a-form-item label="结算方式">
              <a-select v-model="filters.settlement_type" placeholder="请选择" allow-clear>
                <a-option value="prepaid">预付费</a-option>
                <a-option value="postpaid">后付费</a-option>
              </a-select>
            </a-form-item>
          </a-col>
```

插入后，第一行结构变为：
- 第 1 列：关键词 (lg=4)
- 第 2 列：账号类型 (lg=4)
- 第 3 列：行业类型 (lg=4)
- 第 4 列：重点客户 (lg=4)
- **第 5 列：结算方式 (lg=4)** ← 新增
- 第 6 列：查询/重置按钮 (lg=4)

总计 6×4=24，刚好占满一行。

- [ ] **Step 2: 验证模板结构**

运行前端开发服务器检查模板编译：
```bash
cd frontend && npm run dev
```
预期：无编译错误，页面正常渲染。

---

### Task 2: 新增结算方式筛选项到脚本层 - filters 状态

**Files:**
- Modify: `frontend/src/views/customers/Index.vue:508-513`（filters reactive 对象）

- [ ] **Step 1: 在 filters 对象中新增 settlement_type 字段**

修改前（约第 508-513 行）：
```ts
const filters = reactive({
  keyword: '',
  account_type: '',
  industry: '',
  is_key_customer: null as boolean | null,
})
```

修改后：
```ts
const filters = reactive({
  keyword: '',
  account_type: '',
  industry: '',
  is_key_customer: null as boolean | null,
  settlement_type: '',
})
```

- [ ] **Step 2: 验证 TypeScript 类型检查通过**

```bash
cd frontend && npm run type-check
```
预期：无类型错误。

---

### Task 3: 新增结算方式参数到 loadCustomers() 函数

**Files:**
- Modify: `frontend/src/views/customers/Index.vue:619-624`（loadCustomers 函数中的参数构建部分）

- [ ] **Step 1: 在 loadCustomers 函数中新增 settlement_type 参数传递**

在约第 622 行（`if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer`）之后，添加：

```ts
    if (filters.settlement_type) params.settlement_type = filters.settlement_type
```

同时，params 类型定义（约第 602-612 行）也需要新增字段。修改前：
```ts
    const params: {
      page: number
      page_size: number
      keyword?: string
      account_type?: string
      industry?: string
      manager_id?: number
      sales_manager_id?: number
      is_key_customer?: boolean
      sort_by: string
      sort_order: 'asc' | 'desc'
    } = {
```

修改后：
```ts
    const params: {
      page: number
      page_size: number
      keyword?: string
      account_type?: string
      industry?: string
      manager_id?: number
      sales_manager_id?: number
      is_key_customer?: boolean
      settlement_type?: string
      sort_by: string
      sort_order: 'asc' | 'desc'
    } = {
```

- [ ] **Step 2: 验证 TypeScript 类型检查通过**

```bash
cd frontend && npm run type-check
```
预期：无类型错误。

---

### Task 4: 新增结算方式重置逻辑到 handleReset() 函数

**Files:**
- Modify: `frontend/src/views/customers/Index.vue:644-654`（handleReset 函数）

- [ ] **Step 1: 在 handleReset 函数中新增 settlement_type 重置**

修改前（约第 644-654 行）：
```ts
const handleReset = () => {
  filters.keyword = ''
  filters.account_type = ''
  filters.industry = ''
  filters.is_key_customer = null
  advancedFilters.manager_id = null
  advancedFilters.sales_manager_id = null
  advancedFilters.tag_ids = []
  pagination.current = 1
  loadCustomers()
}
```

修改后：
```ts
const handleReset = () => {
  filters.keyword = ''
  filters.account_type = ''
  filters.industry = ''
  filters.is_key_customer = null
  filters.settlement_type = ''
  advancedFilters.manager_id = null
  advancedFilters.sales_manager_id = null
  advancedFilters.tag_ids = []
  pagination.current = 1
  loadCustomers()
}
```

- [ ] **Step 2: 验证代码格式**

```bash
cd frontend && npm run lint && npm run format
```
预期：无 lint 错误。

---

### Task 5: 新增结算方式参数到 handleExport() 函数

**Files:**
- Modify: `frontend/src/views/customers/Index.vue:731-737`（handleExport 函数中的参数构建部分）

- [ ] **Step 1: 在 handleExport 函数中新增 settlement_type 参数传递**

在约第 735 行（`if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer`）之后，添加：

```ts
    if (filters.settlement_type) params.settlement_type = filters.settlement_type
```

- [ ] **Step 2: 验证代码格式和类型检查**

```bash
cd frontend && npm run type-check && npm run lint
```
预期：无错误。

---

### Task 6: 端到端验证

**Files:**
- 无需文件变更

- [ ] **Step 1: 启动前端开发服务器**

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: 手动验证功能**

1. 打开客户管理页面
2. 确认第一行显示：关键词、账号类型、行业类型、重点客户、**结算方式**、查询/重置按钮
3. 选择"结算方式"为"预付费"，点击"查询"，验证列表过滤
4. 选择"结算方式"为"后付费"，点击"查询"，验证列表过滤
5. 点击"重置"，验证结算方式筛选项清空
6. 点击"导出"，验证导出文件包含结算方式筛选结果

- [ ] **Step 3: 运行前端 lint 和类型检查**

```bash
cd frontend && npm run lint && npm run type-check
```
预期：全部通过。

---

### Task 7: 提交代码

- [ ] **Step 1: 提交更改**

```bash
git add frontend/src/views/customers/Index.vue
git commit -m "feat: 客户管理页面新增结算方式筛选项

- 在第一行筛选区域新增结算方式下拉筛选项
- 支持预付费/后付费筛选
- 更新 filters 状态、loadCustomers、handleReset、handleExport 函数
- 查询/重置按钮保持在第一行最右侧"
```

---

## 验收标准

1. ✅ 第一行显示 5 个筛选项 + 查询/重置按钮
2. ✅ 结算方式筛选项可正常选择"预付费"、"后付费"
3. ✅ 选择后点击"查询"，列表按结算方式过滤
4. ✅ 点击"重置"，结算方式筛选项清空
5. ✅ 导出功能包含结算方式筛选条件
6. ✅ TypeScript 类型检查通过
7. ✅ ESLint 检查通过
