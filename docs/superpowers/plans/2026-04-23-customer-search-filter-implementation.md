# 客户筛选器输入检索功能优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将5个页面（余额管理、计费规则、消耗分析、回款分析、预测回款）的客户筛选项从 a-select 改为 a-auto-complete 输入框+下拉组合形式

**Architecture:** 新建一个可复用的 `CustomerAutoComplete` 组件封装客户搜索逻辑（防抖搜索、name→id反查），5个页面替换筛选器模板并清理旧代码。每个页面改动独立可验证。

**Tech Stack:** Vue 3 + TypeScript + Arco Design (a-auto-complete) + axios

---

## 文件结构

| 操作   | 文件路径                                  | 说明                               |
| ------ | ----------------------------------------- | ---------------------------------- |
| 新建   | `frontend/src/components/CustomerAutoComplete.vue` | 可复用的客户自动补全组件           |
| 修改   | `frontend/src/views/billing/Balance.vue` | 替换筛选器中的客户选择器           |
| 修改   | `frontend/src/views/billing/PricingRules.vue` | 替换筛选器中的客户选择器           |
| 修改   | `frontend/src/views/analytics/Consumption.vue` | 替换筛选器中的客户选择器           |
| 修改   | `frontend/src/views/analytics/Payment.vue` | 替换筛选器中的客户选择器           |
| 修改   | `frontend/src/views/analytics/Forecast.vue` | 替换筛选器中的客户选择器           |

## 实现细节

### Task 1: 创建 CustomerAutoComplete 组件

**Files:**
- Create: `frontend/src/components/CustomerAutoComplete.vue`

- [ ] **Step 1: 编写组件代码**

```vue
<template>
  <a-auto-complete
    :model-value="displayText"
    :placeholder="placeholder"
    :data="autocompleteOptions"
    :filter-option="false"
    allow-clear
    :style="{ width: typeof width === 'number' ? width + 'px' : width }"
    @input="handleInput"
    @search="handleSearch"
    @select="handleSelect"
    @clear="handleClear"
  />
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { getCustomers } from '@/api/customers'

interface CustomerOption {
  value: string
  label: string
  id: number
}

const props = withDefaults(
  defineProps<{
    modelValue?: number
    placeholder?: string
    width?: number | string
  }>(),
  {
    modelValue: undefined,
    placeholder: '请输入客户名称搜索',
    width: 250,
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: number | undefined]
}>()

const displayText = ref('')
const autocompleteOptions = ref<CustomerOption[]>([])
const idByName = ref<Map<string, number>>(new Map())
let searchTimer: ReturnType<typeof setTimeout> | null = null

// 当外部通过 v-model 传入 id 时，显示对应的名称（仅首次加载）
// 注意：组件不预加载数据，displayText 初始为空

const handleInput = (value: string) => {
  displayText.value = value
}

const handleSearch = (value: string) => {
  // 清除之前的定时器
  if (searchTimer) {
    clearTimeout(searchTimer)
  }

  // 300ms 防抖
  searchTimer = setTimeout(async () => {
    if (!value || value.trim() === '') {
      autocompleteOptions.value = []
      idByName.value = new Map()
      return
    }

    try {
      const res = await getCustomers({ keyword: value.trim(), page: 1, page_size: 50 })
      const list = res.data?.list || []
      const options: CustomerOption[] = []
      const nameToId = new Map<string, number>()

      for (const customer of list) {
        options.push({
          value: customer.name,
          label: customer.name,
          id: customer.id,
        })
        nameToId.set(customer.name, customer.id)
      }

      autocompleteOptions.value = options
      idByName.value = nameToId
    } catch (error) {
      console.error('客户搜索失败:', error)
      autocompleteOptions.value = []
      idByName.value = new Map()
    }
  }, 300)
}

const handleSelect = (value: string) => {
  displayText.value = value
  const customerId = idByName.value.get(value)
  emit('update:modelValue', customerId)
}

const handleClear = () => {
  displayText.value = ''
  autocompleteOptions.value = []
  idByName.value = new Map()
  emit('update:modelValue', undefined)
}
</script>
```

- [ ] **Step 2: 验证 TypeScript 类型**

运行: `cd frontend && npm run type-check`
预期: 无类型错误

### Task 2: 修改 Balance.vue（余额管理）

**Files:**
- Modify: `frontend/src/views/billing/Balance.vue`

- [ ] **Step 1: 修改模板 - 替换筛选区域的 a-select 为 CustomerAutoComplete**

找到模板中的筛选区域客户选择器（第 31-45 行附近）：

```vue
<!-- 替换前 -->
<a-form-item label="客户">
  <a-select
    v-model="filters.customer_id"
    placeholder="请选择客户"
    style="width: 250px"
    allow-clear
    filterable
    :remote="true"
    @search="handleCustomerSearch"
  >
    <a-option v-for="customer in customerOptions" :key="customer.id" :value="customer.id">
      {{ customer.name }}
    </a-option>
  </a-select>
</a-form-item>

<!-- 替换后 -->
<a-form-item label="客户">
  <CustomerAutoComplete
    v-model="filters.customer_id"
    placeholder="请输入客户名称搜索"
    width="250"
  />
</a-form-item>
```

- [ ] **Step 2: 修改脚本部分**

在 `<script setup>` 中：

1. 添加组件导入：
```typescript
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'
```

2. 移除以下代码：
```typescript
// 删除
import { getCustomers } from '@/api/customers'

// 删除
const customerOptions = ref<
  Array<{ id: number; name: string; label: string; value: number; company_id?: string }>
>([])

// 删除
const handleCustomerSearch = async (keyword?: string) => {
  try {
    const res = await getCustomers({ keyword: keyword || undefined, page: 1, page_size: 50 })
    customerOptions.value = res.data.list || []
  } catch (error) {
    console.error('加载客户列表失败', error)
  }
}
```

3. 修改 `onMounted`，移除 `handleCustomerSearch()` 调用：
```typescript
// 修改前
onMounted(() => {
  loadBalances()
  handleCustomerSearch() // 预加载客户选项
})

// 修改后
onMounted(() => {
  loadBalances()
})
```

- [ ] **Step 3: 验证构建**

运行: `cd frontend && npm run type-check`
预期: 无类型错误

### Task 3: 修改 PricingRules.vue（计费规则）

**Files:**
- Modify: `frontend/src/views/billing/PricingRules.vue`

- [ ] **Step 1: 修改模板 - 替换筛选区域的 a-select 为 CustomerAutoComplete**

找到筛选区域的客户选择器（第 16-36 行附近）：

```vue
<!-- 替换前 -->
<a-form-item label="客户">
  <a-select
    v-model="filters.customer_id"
    placeholder="请选择客户"
    style="width: 200px"
    allow-clear
    filterable
    :remote="true"
    :loading="customersLoading"
    @search="handleCustomerSearch"
  >
    <a-option
      v-for="customer in customers"
      :key="customer.id"
      :value="customer.id"
      :label="customer.name"
    >
      {{ customer.name }}
    </a-option>
  </a-select>
</a-form-item>

<!-- 替换后 -->
<a-form-item label="客户">
  <CustomerAutoComplete
    v-model="filters.customer_id"
    placeholder="请输入客户名称搜索"
    width="200"
  />
</a-form-item>
```

**注意**：弹窗中的客户选择器（第 149-166 行）**保持不变**，仅替换筛选区域的。

- [ ] **Step 2: 修改脚本部分**

1. 添加组件导入：
```typescript
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'
```

2. 移除以下代码：
```typescript
// 删除 getCustomers import（如果不再有其他使用）
// 保留 getCustomers 如果弹窗中仍然使用，只删除筛选相关的函数

// 删除
const handleCustomerSearch = async (keyword?: string) => {
  await loadCustomers(keyword)
}
```

注意：`loadCustomers` 函数仍然被弹窗使用，**不要删除**。只删除 `handleCustomerSearch`。

3. 修改 `onMounted`：
```typescript
// 修改前
onMounted(() => {
  fetchData()
  loadCustomers() // 预加载客户选项
})

// 修改后
onMounted(() => {
  fetchData()
})
```

- [ ] **Step 3: 验证构建**

运行: `cd frontend && npm run type-check`
预期: 无类型错误

### Task 4: 修改 Consumption.vue（消耗分析）

**Files:**
- Modify: `frontend/src/views/analytics/Consumption.vue`

- [ ] **Step 1: 修改模板 - 替换筛选区域的 a-select 为 CustomerAutoComplete**

找到筛选区域的客户选择器（第 33-48 行附近）：

```vue
<!-- 替换前 -->
<a-form-item label="客户">
  <a-select
    v-model="customerId"
    placeholder="全部客户"
    style="width: 200px"
    allow-clear
    filterable
    :remote="true"
    @search="handleCustomerSearch"
    @change="loadData"
  >
    <a-option :value="undefined">全部客户</a-option>
    <a-option v-for="customer in customerOptions" :key="customer.id" :value="customer.id">
      {{ customer.name }}
    </a-option>
  </a-select>
</a-form-item>

<!-- 替换后 -->
<a-form-item label="客户">
  <CustomerAutoComplete
    v-model="customerId"
    placeholder="请输入客户名称搜索"
    width="200"
  />
</a-form-item>
```

- [ ] **Step 2: 修改脚本部分**

1. 添加组件导入：
```typescript
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'
```

2. 移除以下代码：
```typescript
// 删除
import { getCustomers } from '@/api/customers'

// 删除
const customerOptions = ref<Array<{ id: number; name: string }>>([])

// 删除
const handleCustomerSearch = async (keyword?: string) => {
  try {
    const res = await getCustomers({ keyword: keyword || undefined, page: 1, page_size: 50 })
    customerOptions.value = res.data.list || []
  } catch (error) {
    console.error('加载客户列表失败', error)
  }
}
```

3. 修改 `onMounted`：
```typescript
// 修改前
onMounted(() => {
  handleTimeRangeChange()
  handleCustomerSearch() // 预加载客户选项
  window.addEventListener('resize', handleResize)
})

// 修改后
onMounted(() => {
  handleTimeRangeChange()
  window.addEventListener('resize', handleResize)
})
```

- [ ] **Step 3: 验证构建**

运行: `cd frontend && npm run type-check`
预期: 无类型错误

### Task 5: 修改 Payment.vue（回款分析）

**Files:**
- Modify: `frontend/src/views/analytics/Payment.vue`

- [ ] **Step 1: 修改模板 - 替换筛选区域的 a-select 为 CustomerAutoComplete**

找到筛选区域的客户选择器（第 33-48 行附近）：

```vue
<!-- 替换前 -->
<a-form-item label="客户">
  <a-select
    v-model="customerId"
    placeholder="全部客户"
    style="width: 200px"
    allow-clear
    filterable
    :remote="true"
    @search="handleCustomerSearch"
    @change="loadData"
  >
    <a-option :value="undefined">全部客户</a-option>
    <a-option v-for="customer in customerOptions" :key="customer.id" :value="customer.id">
      {{ customer.name }}
    </a-option>
  </a-select>
</a-form-item>

<!-- 替换后 -->
<a-form-item label="客户">
  <CustomerAutoComplete
    v-model="customerId"
    placeholder="请输入客户名称搜索"
    width="200"
  />
</a-form-item>
```

- [ ] **Step 2: 修改脚本部分**

1. 添加组件导入：
```typescript
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'
```

2. 移除以下代码：
```typescript
// 删除
import { getCustomers } from '@/api/customers'

// 删除
const customerOptions = ref<Array<{ id: number; name: string }>>([])

// 删除
const handleCustomerSearch = async (keyword?: string) => {
  try {
    const res = await getCustomers({ keyword: keyword || undefined, page: 1, page_size: 50 })
    customerOptions.value = res.data.list || []
  } catch (error) {
    console.error('加载客户列表失败', error)
  }
}
```

3. 修改 `onMounted`：
```typescript
// 修改前
onMounted(() => {
  handleTimeRangeChange()
  handleCustomerSearch() // 预加载客户选项
  window.addEventListener('resize', handleResize)
})

// 修改后
onMounted(() => {
  handleTimeRangeChange()
  window.addEventListener('resize', handleResize)
})
```

- [ ] **Step 3: 验证构建**

运行: `cd frontend && npm run type-check`
预期: 无类型错误

### Task 6: 修改 Forecast.vue（预测回款）

**Files:**
- Modify: `frontend/src/views/analytics/Forecast.vue`

- [ ] **Step 1: 修改模板 - 替换筛选区域的 a-select 为 CustomerAutoComplete**

找到筛选区域的客户选择器（第 38-53 行附近）：

```vue
<!-- 替换前 -->
<a-form-item label="客户">
  <a-select
    v-model="customerId"
    placeholder="全部客户"
    style="width: 200px"
    allow-clear
    filterable
    :remote="true"
    @search="handleCustomerSearch"
    @change="loadData"
  >
    <a-option :value="undefined">全部客户</a-option>
    <a-option v-for="customer in customerOptions" :key="customer.id" :value="customer.id">
      {{ customer.name }}
    </a-option>
  </a-select>
</a-form-item>

<!-- 替换后 -->
<a-form-item label="客户">
  <CustomerAutoComplete
    v-model="customerId"
    placeholder="请输入客户名称搜索"
    width="200"
  />
</a-form-item>
```

- [ ] **Step 2: 修改脚本部分**

1. 添加组件导入：
```typescript
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'
```

2. 移除以下代码：
```typescript
// 删除
import { getCustomers } from '@/api/customers'

// 删除
const customerOptions = ref<Array<{ id: number; name: string }>>([])

// 删除
const handleCustomerSearch = async (keyword?: string) => {
  try {
    const res = await getCustomers({ keyword: keyword || undefined, page: 1, page_size: 50 })
    customerOptions.value = res.data.list || []
  } catch (error) {
    console.error('加载客户列表失败', error)
  }
}
```

3. 修改 `onMounted`：
```typescript
// 修改前
onMounted(() => {
  loadData()
  handleCustomerSearch() // 预加载客户选项
  window.addEventListener('resize', handleResize)
})

// 修改后
onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})
```

- [ ] **Step 3: 验证构建**

运行: `cd frontend && npm run type-check`
预期: 无类型错误

### Task 7: 最终验证与提交

**Files:** 所有修改过的文件

- [ ] **Step 1: 运行前端类型检查**

```bash
cd frontend && npm run type-check
```

预期: 无类型错误

- [ ] **Step 2: 运行前端 lint**

```bash
cd frontend && npm run lint
```

预期: 无 lint 错误

- [ ] **Step 3: 提交所有更改**

```bash
git add frontend/src/components/CustomerAutoComplete.vue
git add frontend/src/views/billing/Balance.vue
git add frontend/src/views/billing/PricingRules.vue
git add frontend/src/views/analytics/Consumption.vue
git add frontend/src/views/analytics/Payment.vue
git add frontend/src/views/analytics/Forecast.vue
git commit -m "feat: replace customer filter select with auto-complete on 5 pages

- Create CustomerAutoComplete reusable component with debounce search
- Replace a-select filter with CustomerAutoComplete on:
  - Balance.vue (余额管理)
  - PricingRules.vue (计费规则)
  - Consumption.vue (消耗分析)
  - Payment.vue (回款分析)
  - Forecast.vue (预测回款)
- Remove unused getCustomers import and handleCustomerSearch functions
- Remove pre-load customer options on mount"
```

---

## 自审检查

1. **规格覆盖**: 设计文档中所有要求均已映射到任务
   - ✅ 新建 CustomerAutoComplete 组件 → Task 1
   - ✅ 5个页面替换筛选器 → Task 2-6
   - ✅ 防抖300ms → Task 1 中实现
   - ✅ 清除操作 → Task 1 中 handleClear
   - ✅ 错误处理 → Task 1 中 catch 块
   - ✅ 移除预加载 → 各 Task 的 onMounted 修改

2. **无占位符**: 所有步骤都包含完整代码和命令

3. **类型一致性**: 所有页面使用相同的 CustomerAutoComplete 组件 API，modelValue 均为 `number | undefined`
