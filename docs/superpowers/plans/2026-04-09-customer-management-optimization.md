# 客户管理页面体验优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化客户管理页面的 15 个体验问题，重点解决高优先级的 5 个问题（筛选布局、时间格式、重点客户样式、运营经理选择、Detail 编辑字段缺失）

**Architecture:** 
- 前端采用 Vue 3 + TypeScript + Arco Design
- 使用模板插槽 (slot) 格式化表格列显示
- 使用 `a-select` 组件实现运营经理下拉选择
- 复用已有的 `getManagers()` API 获取用户列表
- 统一使用 `manager_id` 作为数据模型字段

**Tech Stack:** Vue 3.4, TypeScript 5.3, Arco Design 2.54, Vite 5.0

---

## 文件结构

**修改的文件:**
- `frontend/src/views/customers/Index.vue` - 客户列表页（主要修改）
- `frontend/src/views/customers/Detail.vue` - 客户详情页（补充编辑字段）

**涉及的后端文件（无需修改，仅确认接口）:**
- `backend/app/routes/customers.py` - 已支持 `manager_id` 参数
- `backend/app/models/customers.py` - `manager_id` 字段已定义

---

## Task 1: 修复创建时间格式问题

**Files:**
- Modify: `frontend/src/views/customers/Index.vue:455`
- Test: 手动验证浏览器中时间显示格式

**目标:** 将 `created_at` 列从直接显示 ISO 字符串改为格式化后的 `YYYY-MM-DD HH:mm:ss` 格式

- [ ] **Step 1: 修改表格列定义，添加 slotName**

在 `Index.vue` 第 455 行，将：
```typescript
{ title: '创建时间', dataIndex: 'created_at', width: 180 },
```
改为：
```typescript
{ title: '创建时间', slotName: 'createdAt', width: 180 },
```

- [ ] **Step 2: 添加时间格式化模板插槽**

在 `Index.vue` 第 214 行（`<template #action>` 之前）添加：
```vue
<template #createdAt="{ record }">
  {{ formatDateTime(record.created_at) }}
</template>
```

- [ ] **Step 3: 导入 formatDateTime 函数**

在 `Index.vue` 第 400 行（import 语句区域）添加：
```typescript
import { formatDateTime } from '@/utils/formatters'
```

- [ ] **Step 4: 验证时间格式**

启动前端开发服务器，访问客户管理页面，确认时间显示格式为 `2026-04-07 10:30:00` 格式

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/customers/Index.vue
git commit -m "fix: 格式化客户列表创建时间显示"
```

---

## Task 2: 优化重点客户样式显示

**Files:**
- Modify: `frontend/src/views/customers/Index.vue:454`
- Test: 手动验证浏览器中重点客户列显示

**目标:** 将 `is_key_customer` 列从显示 `true/false` 改为显示 `是/否` + Tag 颜色标识

- [ ] **Step 1: 修改表格列定义，添加 slotName**

在 `Index.vue` 第 454 行，将：
```typescript
{ title: '重点客户', dataIndex: 'is_key_customer', width: 90 },
```
改为：
```typescript
{ title: '重点客户', slotName: 'isKeyCustomer', width: 90 },
```

- [ ] **Step 2: 添加重点客户格式化模板插槽**

在 `Index.vue` 第 214 行（`<template #createdAt>` 之前）添加：
```vue
<template #isKeyCustomer="{ record }">
  <a-tag :color="record.is_key_customer ? 'red' : 'gray'">
    {{ record.is_key_customer ? '是' : '否' }}
  </a-tag>
</template>
```

- [ ] **Step 3: 验证重点客户样式**

启动前端开发服务器，访问客户管理页面，确认：
- 重点客户显示红色"是"Tag
- 非重点客户显示灰色"否"Tag

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/customers/Index.vue
git commit -m "feat: 重点客户列使用 Tag 显示是/否"
```

---

## Task 3: 优化运营经理字段为下拉选择（编辑表单）

**Files:**
- Modify: `frontend/src/views/customers/Index.vue:341-343,608,670`
- Test: 手动验证编辑表单中运营经理下拉选择功能

**目标:** 将编辑表单中的运营经理从文本输入改为下拉选择，支持选择所有平台用户

- [ ] **Step 1: 修改编辑表单中的运营经理字段**

在 `Index.vue` 第 341-343 行，将：
```vue
<a-form-item field="manager" label="运营经理">
  <a-input v-model="customerForm.manager" placeholder="请输入运营经理姓名" />
</a-form-item>
```
改为：
```vue
<a-form-item field="manager_id" label="运营经理">
  <a-select
    v-model="customerForm.manager_id"
    placeholder="请选择运营经理"
    allow-clear
    :loading="managersLoading"
  >
    <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
      {{ manager.real_name || manager.username }}
    </a-option>
  </a-select>
</a-form-item>
```

- [ ] **Step 2: 更新 customerForm 数据结构**

在 `Index.vue` 第 608 行，将：
```typescript
const customerForm = reactive({
  // ... 其他字段
  manager: '',
})
```
改为：
```typescript
const customerForm = reactive({
  // ... 其他字段
  manager_id: null as number | null,
})
```

- [ ] **Step 3: 更新 openCreateModal 函数中的表单重置**

在 `Index.vue` 第 630 行，将：
```typescript
manager: '',
```
改为：
```typescript
manager_id: null,
```

- [ ] **Step 4: 更新 openEditModal 函数中的数据回显**

在 `Index.vue` 第 650 行，将：
```typescript
manager: record.manager || '',
```
改为：
```typescript
manager_id: record.manager_id || null,
```

- [ ] **Step 5: 更新 handleCustomerSubmit 函数中的提交数据**

在 `Index.vue` 第 670 行，将：
```typescript
manager: customerForm.manager || undefined,
```
改为：
```typescript
manager_id: customerForm.manager_id || undefined,
```

- [ ] **Step 6: 验证运营经理选择功能**

启动前端开发服务器，打开新建/编辑客户对话框，确认：
- 运营经理字段显示为下拉选择框
- 下拉列表显示所有平台用户（real_name 或 username）
- 支持清空选择
- 保存后 `manager_id` 正确提交到后端

- [ ] **Step 7: 提交**

```bash
git add frontend/src/views/customers/Index.vue
git commit -m "feat: 运营经理字段改为下拉选择支持选择平台用户"
```

---

## Task 4: 优化筛选区域布局

**Files:**
- Modify: `frontend/src/views/customers/Index.vue:66-195`
- Test: 手动验证筛选区域在不同屏幕尺寸下的显示效果

**目标:** 将单行排列的筛选表单改为多行栅格布局，提升操作体验

- [ ] **Step 1: 修改筛选区域 HTML 结构**

在 `Index.vue` 第 66-158 行，将：
```vue
<!-- 筛选区域 -->
<div class="filter-section">
  <a-form layout="inline" :model="filters">
    <a-form-item label="关键词">
      <a-input v-model="filters.keyword" placeholder="公司名称/公司 ID" style="width: 200px">
        <!-- ... -->
      </a-input>
    </a-form-item>
    <!-- 其他筛选项... -->
  </a-form>
  <!-- 高级筛选区域... -->
</div>
```
改为：
```vue
<!-- 筛选区域 -->
<div class="filter-section">
  <a-form :model="filters" layout="vertical">
    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :sm="12" :md="8" :lg="6">
        <a-form-item label="关键词">
          <a-input v-model="filters.keyword" placeholder="公司名称/公司 ID">
            <template #prefix>
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                <path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z"/>
              </svg>
            </template>
          </a-input>
        </a-form-item>
      </a-col>
      <a-col :xs="24" :sm="12" :md="8" :lg="6">
        <a-form-item label="账号类型">
          <a-select v-model="filters.account_type" placeholder="请选择" allow-clear>
            <a-option value="正式账号">正式账号</a-option>
            <a-option value="测试账号">测试账号</a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :xs="24" :sm="12" :md="8" :lg="6">
        <a-form-item label="业务类型">
          <a-select v-model="filters.business_type" placeholder="请选择" allow-clear>
            <a-option value="A">A 类业务</a-option>
            <a-option value="B">B 类业务</a-option>
            <a-option value="C">C 类业务</a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :xs="24" :sm="12" :md="8" :lg="6">
        <a-form-item label="客户等级">
          <a-select v-model="filters.customer_level" placeholder="请选择" allow-clear>
            <a-option value="KA">KA</a-option>
            <a-option value="SKA">SKA</a-option>
            <a-option value="普通">普通</a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :xs="24" :sm="12" :md="8" :lg="6">
        <a-form-item label="重点客户">
          <a-select v-model="filters.is_key_customer" placeholder="请选择" allow-clear>
            <a-option :value="true">是</a-option>
            <a-option :value="false">否</a-option>
          </a-select>
        </a-form-item>
      </a-col>
      <a-col :xs="24" :sm="12" :md="8" :lg="6">
        <a-form-item label=" ">
          <a-space>
            <a-button type="primary" @click="handleSearch">查询</a-button>
            <a-button @click="handleReset">重置</a-button>
          </a-space>
        </a-form-item>
      </a-col>
    </a-row>
  </a-form>

  <a-divider style="margin: 16px 0" />
  
  <div class="advanced-filter-toggle">
    <a-button type="text" @click="showAdvancedFilter = !showAdvancedFilter">
      高级筛选
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"
           :style="{ transform: showAdvancedFilter ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }">
        <path fill-rule="evenodd" d="M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708z"/>
      </svg>
    </a-button>
  </div>

  <!-- 高级筛选区域 -->
  <a-collapse v-model:activeKey="showAdvancedFilter ? ['1'] : []" :bordered="false" style="margin-top: 16px">
    <a-collapse-item key="1" title="">
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :sm="12" :md="8" :lg="6">
          <a-form-item label="运营经理">
            <a-select v-model="advancedFilters.manager_id" placeholder="请选择运营经理" allow-clear :loading="managersLoading">
              <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
                {{ manager.real_name || manager.username }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :xs="24" :sm="12" :md="8" :lg="6">
          <a-form-item label="标签筛选">
            <a-select v-model="advancedFilters.tag_ids" placeholder="选择标签" multiple allow-clear :loading="tagsLoading">
              <a-option v-for="tag in customerTags" :key="tag.id" :value="tag.id">
                {{ tag.name }}
              </a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :xs="24" :sm="12" :md="8" :lg="6">
          <a-form-item label=" ">
            <a-button type="primary" @click="handleAdvancedSearch">应用高级筛选</a-button>
          </a-form-item>
        </a-col>
      </a-row>
    </a-collapse-item>
  </a-collapse>
</div>
```

- [ ] **Step 2: 更新筛选区域 CSS 样式**

在 `Index.vue` 第 770 行之后，添加：
```css
.filter-section {
  background: white;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  margin-bottom: 24px;
}

.filter-section .arco-form-item {
  margin-bottom: 0;
}

.filter-section .arco-select,
.filter-section .arco-input {
  width: 100%;
}

.advanced-filter-toggle {
  margin-top: 16px;
}
```

- [ ] **Step 3: 验证筛选区域布局**

启动前端开发服务器，访问客户管理页面，确认：
- 筛选项按栅格排列，响应式适配不同屏幕
- 查询/重置按钮在同一行
- 高级筛选区域使用折叠面板，展开/收起动画流畅
- 在小屏幕（<768px）下筛选项自动换行

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/customers/Index.vue
git commit -m "feat: 优化筛选区域为多行栅格布局"
```

---

## Task 5: 在 Detail.vue 中添加缺失的编辑字段

**Files:**
- Modify: `frontend/src/views/customers/Detail.vue:193-243`
- Test: 手动验证详情页编辑对话框功能

**目标:** 在详情页编辑对话框中添加"重点客户"和"运营经理"字段

- [ ] **Step 1: 在 EditForm 接口中添加字段**

在 `Detail.vue` 第 274 行，将：
```typescript
interface EditForm {
  name: string
  email: string
  account_type?: string
  business_type?: string
  customer_level?: string
  settlement_type?: string
  settlement_cycle?: string
}
```
改为：
```typescript
interface EditForm {
  name: string
  email: string
  account_type?: string
  business_type?: string
  customer_level?: string
  settlement_type?: string
  settlement_cycle?: string
  is_key_customer?: boolean
  manager_id?: number
}
```

- [ ] **Step 2: 在编辑对话框中添加重点客户字段**

在 `Detail.vue` 第 239 行（`settlement_cycle` 字段之后）添加：
```vue
<a-form-item field="is_key_customer" label="重点客户">
  <a-switch v-model="editForm.is_key_customer" />
</a-form-item>
```

- [ ] **Step 3: 在编辑对话框中添加运营经理字段**

在 `Detail.vue` 第 243 行（重点客户字段之后）添加：
```vue
<a-form-item field="manager_id" label="运营经理">
  <a-select
    v-model="editForm.manager_id"
    placeholder="请选择运营经理"
    allow-clear
    :loading="managersLoading"
  >
    <a-option v-for="manager in managers" :key="manager.id" :value="manager.id">
      {{ manager.real_name || manager.username }}
    </a-option>
  </a-select>
</a-form-item>
```

- [ ] **Step 4: 添加运营经理数据加载逻辑**

在 `Detail.vue` 第 274 行（script setup 区域）添加：
```typescript
import { getManagers } from '@/api/users'

const managersLoading = ref(false)
const managers = ref<any[]>([])

const loadManagers = async () => {
  managersLoading.value = true
  try {
    const res = await getManagers()
    managers.value = res.data?.list || res.data || []
  } catch (error: any) {
    console.error('加载运营经理失败:', error)
  } finally {
    managersLoading.value = false
  }
}
```

- [ ] **Step 5: 更新 editForm 初始化数据**

在 `Detail.vue` 第 399 行，将：
```typescript
const editForm = ref<EditForm>({
  name: '',
  email: '',
  account_type: undefined,
  business_type: undefined,
  customer_level: undefined,
  settlement_type: undefined,
  settlement_cycle: undefined,
})
```
改为：
```typescript
const editForm = ref<EditForm>({
  name: '',
  email: '',
  account_type: undefined,
  business_type: undefined,
  customer_level: undefined,
  settlement_type: undefined,
  settlement_cycle: undefined,
  is_key_customer: false,
  manager_id: undefined,
})
```

- [ ] **Step 6: 更新 openEditModal 函数中的数据回显**

在 `Detail.vue` 第 463 行，将：
```typescript
const openEditModal = () => {
  editForm.value = {
    name: customer.value.name || '',
    email: customer.value.email || '',
    account_type: customer.value.account_type || undefined,
    business_type: customer.value.business_type || undefined,
    customer_level: customer.value.customer_level || undefined,
    settlement_type: customer.value.settlement_type || undefined,
    settlement_cycle: customer.value.settlement_cycle || undefined,
  }
  editModalVisible.value = true
}
```
改为：
```typescript
const openEditModal = () => {
  editForm.value = {
    name: customer.value.name || '',
    email: customer.value.email || '',
    account_type: customer.value.account_type || undefined,
    business_type: customer.value.business_type || undefined,
    customer_level: customer.value.customer_level || undefined,
    settlement_type: customer.value.settlement_type || undefined,
    settlement_cycle: customer.value.settlement_cycle || undefined,
    is_key_customer: customer.value.is_key_customer || false,
    manager_id: customer.value.manager_id || undefined,
  }
  editModalVisible.value = true
}
```

- [ ] **Step 7: 更新 handleEditSubmit 函数中的提交数据**

在 `Detail.vue` 第 468 行，将：
```typescript
await updateCustomer(customerId.value, {
  name: editForm.value.name,
  email: editForm.value.email || undefined,
  account_type: editForm.value.account_type || undefined,
  business_type: editForm.value.business_type || undefined,
  customer_level: editForm.value.customer_level || undefined,
  settlement_type: editForm.value.settlement_type,
  settlement_cycle: editForm.value.settlement_cycle || undefined,
})
```
改为：
```typescript
await updateCustomer(customerId.value, {
  name: editForm.value.name,
  email: editForm.value.email || undefined,
  account_type: editForm.value.account_type || undefined,
  business_type: editForm.value.business_type || undefined,
  customer_level: editForm.value.customer_level || undefined,
  settlement_type: editForm.value.settlement_type,
  settlement_cycle: editForm.value.settlement_cycle || undefined,
  is_key_customer: editForm.value.is_key_customer,
  manager_id: editForm.value.manager_id || undefined,
})
```

- [ ] **Step 8: 在 onMounted 中调用 loadManagers**

在 `Detail.vue` 第 606 行，将：
```typescript
onMounted(() => {
  loadCustomerData()
  loadCustomerTags()
  loadUsageData()
})
```
改为：
```typescript
onMounted(() => {
  loadCustomerData()
  loadCustomerTags()
  loadUsageData()
  loadManagers()
})
```

- [ ] **Step 9: 验证详情页编辑功能**

启动前端开发服务器，访问客户详情页，点击编辑按钮，确认：
- 编辑对话框显示"重点客户"开关
- 编辑对话框显示"运营经理"下拉选择
- 数据回显正确
- 保存后数据更新成功

- [ ] **Step 10: 提交**

```bash
git add frontend/src/views/customers/Detail.vue
git commit -m "feat: Detail 编辑对话框添加重点客户和运营经理字段"
```

---

## Task 6: 优化表格列宽和操作按钮布局

**Files:**
- Modify: `frontend/src/views/customers/Index.vue:447-457,207-214`
- Test: 手动验证表格显示效果

**目标:** 调整表格列宽，优化操作按钮布局

- [ ] **Step 1: 调整表格列宽**

在 `Index.vue` 第 447-457 行，将 columns 定义改为：
```typescript
const columns = [
  { title: '公司 ID', dataIndex: 'company_id', width: 140, ellipsis: true, tooltip: true },
  { title: '客户名称', dataIndex: 'name', width: 250, ellipsis: true, tooltip: true },
  { title: '业务类型', dataIndex: 'business_type', width: 100 },
  { title: '客户等级', dataIndex: 'customer_level', width: 100 },
  { title: '结算方式', dataIndex: 'settlement_type', width: 100 },
  { title: '运营经理', dataIndex: 'manager', width: 150, ellipsis: true, tooltip: true },
  { title: '重点客户', slotName: 'isKeyCustomer', width: 100 },
  { title: '创建时间', slotName: 'createdAt', width: 180 },
  { title: '操作', slotName: 'action', width: 320, fixed: 'right' as const },
]
```

- [ ] **Step 2: 优化操作按钮布局**

在 `Index.vue` 第 207-214 行，将：
```vue
<template #action="{ record }">
  <a-space>
    <a-button type="primary" size="small" @click="viewCustomer(record.id)">查看</a-button>
    <a-button type="text" size="small" @click="openEditModal(record)">编辑</a-button>
    <a-button type="text" size="small" @click="viewProfile(record.id)">画像</a-button>
    <a-popconfirm content="确认删除？" @ok="() => handleDelete(record.id)">
      <a-button type="text" size="small" status="danger">删除</a-button>
    </a-popconfirm>
  </a-space>
</template>
```
改为：
```vue
<template #action="{ record }">
  <a-space>
    <a-button type="primary" size="small" @click="viewCustomer(record.id)">查看</a-button>
    <a-button type="text" size="small" @click="openEditModal(record)">编辑</a-button>
    <a-dropdown>
      <a-button type="text" size="small">更多</a-button>
      <template #content>
        <a-doption @click="viewProfile(record.id)">画像</a-doption>
        <a-doption style="color: #ff4d4f" @click="() => handleDelete(record.id)">删除</a-doption>
      </template>
    </a-dropdown>
  </a-space>
</template>
```

- [ ] **Step 3: 验证表格显示**

启动前端开发服务器，访问客户管理页面，确认：
- 各列宽度合适，内容不被截断
- 操作按钮使用"更多"下拉菜单，界面更简洁
- 删除操作在下拉菜单中显示为红色

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/customers/Index.vue
git commit -m "feat: 优化表格列宽和操作按钮布局"
```

---

## Task 7: 添加表单验证触发器和必填项标识

**Files:**
- Modify: `frontend/src/views/customers/Index.vue:240-344,611-616`
- Test: 手动验证表单验证行为

**目标:** 添加实时表单验证和必填项星号标识

- [ ] **Step 1: 更新表单验证规则**

在 `Index.vue` 第 611-616 行，将：
```typescript
const customerFormRules = {
  company_id: [{ required: true, message: '请输入公司 ID' }],
  name: [{ required: true, message: '请输入客户名称' }],
  email: [{ type: 'email', message: '请输入有效的邮箱地址' }],
}
```
改为：
```typescript
const customerFormRules = {
  company_id: [
    { required: true, message: '请输入公司 ID', trigger: ['blur', 'change'] }
  ],
  name: [
    { required: true, message: '请输入客户名称', trigger: ['blur', 'change'] }
  ],
  email: [
    { type: 'email', message: '请输入有效的邮箱地址', trigger: ['blur', 'change'] }
  ],
}
```

- [ ] **Step 2: 在 a-form 上添加 validate-trigger 属性**

在 `Index.vue` 第 240 行，将：
```vue
<a-form
  ref="customerFormRef"
  :model="customerForm"
  :rules="customerFormRules"
  layout="vertical"
>
```
改为：
```vue
<a-form
  ref="customerFormRef"
  :model="customerForm"
  :rules="customerFormRules"
  layout="vertical"
  validate-trigger="['blur', 'change']"
>
```

- [ ] **Step 3: 添加必填项星号标识样式**

在 `Index.vue` 第 843 行（CSS 区域末尾）添加：
```css
:deep(.arco-form-item-required) .arco-form-item-label::before {
  content: '*';
  color: #ff4d4f;
  margin-right: 4px;
}
```

- [ ] **Step 4: 验证表单验证行为**

启动前端开发服务器，打开新建客户对话框，确认：
- 必填项标签显示红色星号
- 输入框失焦或输入时实时验证
- 错误信息及时显示

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/customers/Index.vue
git commit -m "feat: 添加表单实时验证和必填项星号标识"
```

---

## 测试计划

### 手动测试清单

1. **时间格式测试**
   - [ ] 客户列表创建时间列显示 `YYYY-MM-DD HH:mm:ss` 格式
   - [ ] 时间值包含时分秒

2. **重点客户样式测试**
   - [ ] 重点客户显示红色"是"Tag
   - [ ] 非重点客户显示灰色"否"Tag

3. **运营经理选择测试**
   - [ ] 新建客户对话框中运营经理为下拉选择
   - [ ] 下拉列表显示所有平台用户
   - [ ] 支持清空选择
   - [ ] 编辑客户时正确回显运营经理
   - [ ] 详情页编辑对话框支持选择运营经理

4. **筛选布局测试**
   - [ ] 筛选项按栅格排列
   - [ ] 响应式适配不同屏幕尺寸
   - [ ] 高级筛选区域使用折叠面板

5. **表格布局测试**
   - [ ] 各列宽度合适，内容不截断
   - [ ] 操作按钮使用下拉菜单

6. **表单验证测试**
   - [ ] 必填项显示红色星号
   - [ ] 实时验证触发

### 回归测试

- [ ] 客户列表加载正常
- [ ] 新建客户功能正常
- [ ] 编辑客户功能正常
- [ ] 删除客户功能正常
- [ ] 导入/导出功能正常
- [ ] 高级筛选功能正常
- [ ] 分页功能正常

---

## 执行选择

**计划完成并保存到** `docs/superpowers/plans/2026-04-09-customer-management-optimization.md`

**两种执行方式:**

**1. Subagent-Driven（推荐）** - 每个任务派遣独立的 subagent 执行，任务间进行 review，快速迭代

**2. Inline Execution** - 在当前 session 中使用 executing-plans 批量执行，设置检查点

**选择哪种方式？**
