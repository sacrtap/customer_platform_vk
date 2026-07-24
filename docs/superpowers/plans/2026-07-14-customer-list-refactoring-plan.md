# 客户列表页面重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `http://localhost:5173/customers` 页面按 `prototype/customers.html` 设计重构对齐，包括共享 UI 组件提取、业务组件重构、页面组装和样式对齐。

**Architecture:** 分层重构 — 先提取共享 UI 组件（Tag/FilterDropdown/KpiCard/ProgressBar/Drawer/ModalLayout/CheckboxArray），再重构业务组件（CustomerKpi/CustomerFilters/CustomerTable/PreviewDrawer/BatchToolbar/CustomerModals），最后组装页面并对齐样式。后端仅做序列化扩展（返回已有字段 scale_level/consume_level/balance）。

**Tech Stack:** Vue 3 + TypeScript + Arco Design Vue + CSS Scoped

## Global Constraints

- 不修改前端技术架构（保持 Vue 3 + Arco Design）
- 保持现有 composables（useCustomerList）状态管理逻辑
- 新增字段后端暂不实现计算逻辑（usage_30d/health 显示占位符）
- 组件需有清晰的 Props/Events 接口定义
- 样式使用 CSS 变量对齐 prototype 设计令牌
- 所有新组件放在 `src/components/ui/` 目录

---

## Phase 1: 共享 UI 组件

### Task 1: Tag 标签组件

**Files:**
- Create: `frontend/src/components/ui/Tag.vue`
- Test: `frontend/tests/unit/components/ui/Tag.spec.ts`

**Interfaces:**
- Consumes: variant, size props
- Produces: `<Tag variant="blue">文字</Tag>`

- [ ] **Step 1: 创建 Tag.vue 组件**

```vue
<!-- frontend/src/components/ui/Tag.vue -->
<template>
  <span class="tag" :class="[variant, size]">
    <slot />
  </span>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'blue' | 'green' | 'amber' | 'red' | 'violet' | 'gray'
  size?: 'sm' | 'md'
}>(), {
  variant: 'gray',
  size: 'md',
})
</script>

<style scoped>
.tag {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-weight: 700;
  white-space: nowrap;
}
.tag.sm { padding: 2px 6px; font-size: 11px; }
.tag.md { padding: 4px 8px; font-size: 12px; }
.tag.blue { background: #DBEAFE; color: #1D4ED8; }
.tag.green { background: #DCFCE7; color: #047857; }
.tag.amber { background: #FEF3C7; color: #B45309; }
.tag.red { background: #FEE2E2; color: #B91C1C; }
.tag.violet { background: #EDE9FE; color: #6D28D9; }
.tag.gray { background: #F1F5F9; color: #475569; }
</style>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/ui/Tag.vue
git commit -m "feat(ui): add Tag component with semantic variants"
```

---

### Task 2: ProgressBar 进度条组件

**Files:**
- Create: `frontend/src/components/ui/ProgressBar.vue`

**Interfaces:**
- Consumes: value (0-100), color
- Produces: `<ProgressBar :value="75" />`

- [ ] **Step 1: 创建 ProgressBar.vue**

```vue
<!-- frontend/src/components/ui/ProgressBar.vue -->
<template>
  <div class="progress-bar">
    <div class="progress-fill" :style="{ width: `${Math.min(100, Math.max(0, value))}%`, background: color }" />
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  value: number
  color?: string
}>(), {
  color: 'var(--primary)',
})
</script>

<style scoped>
.progress-bar {
  width: 100%;
  height: 6px;
  background: #E2E8F0;
  border-radius: 3px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 3px;
  transition: width .3s ease;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/ui/ProgressBar.vue
git commit -m "feat(ui): add ProgressBar component"
```

---

### Task 3: KpiCard 指标卡片组件

**Files:**
- Create: `frontend/src/components/ui/KpiCard.vue`

**Interfaces:**
- Consumes: label, value, trend, trendType, active
- Produces: `<KpiCard label="客户总数" :value="3286" trend="本月新增 126" trend-type="up" />`
- Emits: click

- [ ] **Step 1: 创建 KpiCard.vue**

```vue
<!-- frontend/src/components/ui/KpiCard.vue -->
<template>
  <div class="kpi-card" :class="{ active }" @click="$emit('click')">
    <div class="kpi-label">{{ label }}</div>
    <div class="kpi-value">{{ value }}</div>
    <div v-if="trend" class="kpi-trend" :class="trendType">{{ trend }}</div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  label: string
  value: string | number
  trend?: string
  trendType?: 'up' | 'down' | 'warn' | 'neutral'
  active?: boolean
}>(), {
  trendType: 'neutral',
  active: false,
})

defineEmits<{ click: [] }>()
</script>

<style scoped>
.kpi-card {
  background: #f8fafc;
  border: 1px solid #edf2f7;
  border-radius: 14px;
  padding: 14px;
  cursor: pointer;
  transition: all .18s ease;
}
.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,.08);
}
.kpi-card.active {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(29, 78, 216, .15), 0 6px 20px rgba(29, 78, 216, .12);
}
.kpi-label { font-size: 12px; color: var(--muted); }
.kpi-value { font-size: 22px; font-weight: 850; color: var(--ink); margin: 4px 0; }
.kpi-trend { font-size: 12px; }
.kpi-trend.up { color: #059669; }
.kpi-trend.down { color: #DC2626; }
.kpi-trend.warn { color: #D97706; }
.kpi-trend.neutral { color: var(--muted); }
</style>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/ui/KpiCard.vue
git commit -m "feat(ui): add KpiCard component with active state"
```

---

### Task 4: FilterDropdown 筛选下拉组件

**Files:**
- Create: `frontend/src/components/ui/FilterDropdown.vue`

**Interfaces:**
- Consumes: label, modelValue, options, multiple
- Produces: `<FilterDropdown label="行业" v-model="val" :options="industryOpts" />`
- Emits: update:modelValue, apply

- [ ] **Step 1: 创建 FilterDropdown.vue**

```vue
<!-- frontend/src/components/ui/FilterDropdown.vue -->
<template>
  <div class="filter-dropdown" ref="dropdownRef">
    <button class="filter-trigger" @click="toggle">
      <span class="filter-label">{{ label }}</span>
      <span class="filter-value">{{ displayValue }}</span>
      <span class="filter-arrow" :class="{ open: isOpen }">▾</span>
    </button>
    <div v-if="isOpen" class="filter-panel">
      <div
        v-for="opt in options"
        :key="opt.value"
        class="filter-option"
        :class="{ active: isSelected(opt.value) }"
        @click="selectOption(opt.value)"
      >
        {{ opt.label }}
      </div>
      <div v-if="multiple" class="filter-actions">
        <button class="btn-confirm" @click="confirmApply">确认</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

interface Option { label: string; value: string }

const props = withDefaults(defineProps<{
  label: string
  modelValue: string | string[]
  options: Option[]
  multiple?: boolean
}>(), {
  multiple: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string | string[]]
  apply: []
}>()

const isOpen = ref(false)
const dropdownRef = ref<HTMLElement>()

const displayValue = computed(() => {
  if (props.multiple) {
    const arr = props.modelValue as string[]
    if (!arr.length) return '全部'
    if (arr.length === 1) {
      return props.options.find(o => o.value === arr[0])?.label ?? '全部'
    }
    return `已选 ${arr.length} 项`
  }
  if (!props.modelValue) return '全部'
  return props.options.find(o => o.value === props.modelValue)?.label ?? '全部'
})

const isSelected = (val: string) => {
  if (props.multiple) return (props.modelValue as string[]).includes(val)
  return props.modelValue === val
}

const toggle = () => { isOpen.value = !isOpen.value }

const selectOption = (val: string) => {
  if (props.multiple) {
    const arr = [...(props.modelValue as string[])]
    const idx = arr.indexOf(val)
    if (idx >= 0) arr.splice(idx, 1)
    else arr.push(val)
    emit('update:modelValue', arr)
  } else {
    emit('update:modelValue', val)
    isOpen.value = false
    emit('apply')
  }
}

const confirmApply = () => {
  isOpen.value = false
  emit('apply')
}

const handleClickOutside = (e: MouseEvent) => {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target as Node)) {
    isOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<style scoped>
.filter-dropdown { position: relative; display: inline-block; }
.filter-trigger {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 12px; border: 1px solid var(--line);
  border-radius: 8px; background: white; cursor: pointer;
  font-size: 13px; transition: border-color .2s;
}
.filter-trigger:hover { border-color: var(--primary); }
.filter-label { color: var(--muted); }
.filter-value { color: var(--ink); font-weight: 500; }
.filter-arrow { transition: transform .2s; font-size: 10px; }
.filter-arrow.open { transform: rotate(180deg); }
.filter-panel {
  position: absolute; top: 100%; left: 0; margin-top: 4px;
  min-width: 180px; background: white; border: 1px solid var(--line);
  border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,.1);
  z-index: 100; padding: 4px;
}
.filter-option {
  padding: 8px 12px; border-radius: 6px; cursor: pointer;
  font-size: 13px; transition: background .15s;
}
.filter-option:hover { background: var(--bg); }
.filter-option.active { background: #EFF6FF; color: var(--primary); font-weight: 600; }
.filter-actions { padding: 8px 12px; border-top: 1px solid var(--line); margin-top: 4px; }
.btn-confirm {
  width: 100%; padding: 6px; border: none; border-radius: 6px;
  background: var(--primary); color: white; font-size: 13px; cursor: pointer;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/ui/FilterDropdown.vue
git commit -m "feat(ui): add FilterDropdown component with single/multiple select"
```

---

### Task 5: CheckboxArray 复选框组组件

**Files:**
- Create: `frontend/src/components/ui/CheckboxArray.vue`

**Interfaces:**
- Consumes: modelValue, options, columns
- Produces: `<CheckboxArray v-model="selected" :options="colOpts" :columns="4" />`

- [ ] **Step 1: 创建 CheckboxArray.vue**

```vue
<!-- frontend/src/components/ui/CheckboxArray.vue -->
<template>
  <div class="checkbox-grid" :style="{ gridTemplateColumns: `repeat(${columns}, 1fr)` }">
    <label v-for="opt in options" :key="opt.value" class="checkbox-item">
      <input
        type="checkbox"
        :checked="modelValue.includes(opt.value)"
        @change="toggle(opt.value)"
      />
      {{ opt.label }}
    </label>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  modelValue: string[]
  options: Array<{ label: string; value: string }>
  columns?: number
}>(), {
  columns: 4,
})

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const toggle = (val: string) => {
  const arr = [...props.modelValue]
  const idx = arr.indexOf(val)
  if (idx >= 0) arr.splice(idx, 1)
  else arr.push(val)
  emit('update:modelValue', arr)
}
</script>

<style scoped>
.checkbox-grid {
  display: grid; gap: 8px;
}
.checkbox-item {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; cursor: pointer; padding: 4px 0;
}
.checkbox-item input[type="checkbox"] {
  width: 14px; height: 14px; cursor: pointer;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/ui/CheckboxArray.vue
git commit -m "feat(ui): add CheckboxArray component for grid checkboxes"
```

---

## Phase 2: 业务组件重构

### Task 6: CustomerKpi 指标卡片组

**Files:**
- Create: `frontend/src/views/customers/components/CustomerKpi.vue`

**Interfaces:**
- Consumes: kpi data (total, key, incomplete, mine)
- Produces: `<CustomerKpi :data="kpiData" @kpi-change="onKpiChange" />`

- [ ] **Step 1: 创建 CustomerKpi.vue**

```vue
<!-- frontend/src/views/customers/components/CustomerKpi.vue -->
<template>
  <div class="grid-4">
    <KpiCard
      label="客户总数" :value="data.total" :trend="`本月新增 ${data.newThisMonth}`"
      trend-type="up" :active="active === 'all'" @click="emit('kpiChange', 'all')"
    />
    <KpiCard
      label="重点客户" :value="data.keyCustomers" :trend="`消耗贡献 ${data.keyContribution}%`"
      trend-type="neutral" :active="active === 'key'" @click="emit('kpiChange', 'key')"
    />
    <KpiCard
      label="待完善画像" :value="data.incompleteProfile" trend="影响分析准确性"
      trend-type="warn" :active="active === 'incomplete'" @click="emit('kpiChange', 'incomplete')"
    />
    <KpiCard
      label="我的客户" :value="data.myCustomers" trend="需运营跟进"
      trend-type="down" :active="active === 'mine'" @click="emit('kpiChange', 'mine')"
    />
  </div>
</template>

<script setup lang="ts">
import KpiCard from '@/components/ui/KpiCard.vue'

defineProps<{
  data: {
    total: string
    newThisMonth: number
    keyCustomers: number
    keyContribution: number
    incompleteProfile: number
    myCustomers: number
  }
  active: 'all' | 'key' | 'incomplete' | 'mine'
}>()

const emit = defineEmits<{ kpiChange: [type: 'all' | 'key' | 'incomplete' | 'mine'] }>()
</script>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/customers/components/CustomerKpi.vue
git commit -m "feat(customers): add CustomerKpi component using shared KpiCard"
```

---

### Task 7: CustomerFilters 筛选器重构

**Files:**
- Modify: `frontend/src/views/customers/components/CustomerFilters.vue`

**Interfaces:** 保持现有 Props/Events 接口不变

- [ ] **Step 1: 重构 CustomerFilters.vue 使用 FilterDropdown**

保留现有 props/events 接口，将 a-select 替换为 FilterDropdown 组件。高级筛选折叠区保留。

```vue
<!-- 关键变更：筛选区域使用 FilterDropdown -->
<div class="filters">
  <div class="search-input-wrap">
    <svg .../><input v-model="filters.keyword" placeholder="搜索客户名称 / 公司 ID" />
  </div>
  <FilterDropdown
    label="行业" v-model="filters.industry" :options="industryOptions" multiple
    @apply="handleSearch"
FilterDropdown label="规模等级" v-model="filters.scale_level" :options="scaleOptions" @apply="handleSearch" />
  <FilterDropdown label="消费等级" v-model="filters.consume_level" :options="consumeOptions" @apply="handleSearch" />
  <FilterDropdown label="运营经理" v-model="filters.manager_id" :options="managerOptions" @apply="handleSearch" />
  <FilterDropdown label="销售经理" v-model="filters.sales_manager_id" :options="salesOptions" @apply="handleSearch" />
  <button class="btn primary" @click="handleSearch">筛选</button>
</div>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/customers/components/CustomerFilters.vue
git commit -m "feat(customers): refactor filters to use FilterDropdown component"
```

---

### Task 8: CustomerTable 表格重构

**Files:**
- Modify: `frontend/src/views/customers/components/CustomerTable.vue`

**Interfaces:** 保持现有 props/events 接口，扩展列定义

- [ ] **Step 1: 扩展列定义 + 新增列设置功能**

新增列:
- `scale_level` — 显示规模等级 (S/A/B/C/D)
- `consume_level` — 显示消费等级 (C1-C6)
- `balance` — 显示余额 (¥格式)
- `usage_30d` — ProgressBar 显示消耗占比
- `health` — Tag 显示健康度

列设置: 右上角齿轮图标 → CheckboxArray → localStorage 持久化

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/customers/components/CustomerTable.vue
git commit -m "feat(customers): extend table columns with scale/consume/balance/usage/health"
```

---

### Task 9: PreviewDrawer 预览抽屉重建

**Files:**
- Modify: `frontend/src/components/CustomerPreviewDrawer.vue`

**Interfaces:**
- Consumes: visible, customerId
- Internal: 加载客户摘要数据

- [ ] **Step 1: 按原型重建抽屉内容**

结构:
- 头部: Logo + 名称 + 行业/等级
- KPI 4宫格: 当前余额 / 30天消耗 / 健康度 / 预计耗尽
- 底部操作: 查看详情 / 生成结算单 / 提醒充值

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/CustomerPreviewDrawer.vue
git commit -m "feat(customers): rebuild preview drawer with KPI grid layout"
```

---

### Task 10: BatchToolbar 批量工具栏扩展

**Files:**
- Modify: `frontend/src/components/BatchToolbar.vue`

**Interfaces:**
- Consumes: count
- Emits: batch-edit, assign-manager, batch-export, batch-tag, clear

- [ ] **Step 1: 扩展按钮为4个操作**

```vue
<div class="batch-toolbar">
  <span class="batch-count">已选择 <b>{{ count }}</b> 项</span>
  <button class="btn" @click="$emit('batchEdit')">批量编辑</button>
  <button class="btn" @click="$emit('assignManager')">分配负责人</button>
  <button class="btn" @click="$emit('batchExport')">批量导出</button>
  <button class="btn" @click="$emit('batchTag')">设标签</button>
  <button class="btn" @click="$emit('clear')">取消</button>
</div>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/BatchToolbar.vue
git commit -m "feat(customers): extend batch toolbar with assign/export/tag actions"
```

---

### Task 11: 新增弹窗实现

**Files:**
- Create: `frontend/src/views/customers/components/AssignManagerModal.vue`
- Create: `frontend/src/views/customers/components/BatchExportModal.vue`
- Create: `frontend/src/views/customers/components/BatchTagModal.vue`
- Create: `frontend/src/views/customers/components/ColumnSettingModal.vue`
- Modify: `frontend/src/views/customers/components/CustomerFormModal.vue` (调整字段对齐原型)
- Modify: `frontend/src/views/customers/components/CustomerImportModal.vue` (样式对齐)

**Interfaces:** 各弹窗 visible prop + submitted/cancel events

- [ ] **Step 1: 创建 AssignManagerModal**

运营经理/销售经理选择 + 备注

- [ ] **Step 2: 创建 BatchExportModal**

导出范围 + 格式 + 字段勾选

- [ ] **Step 3: 创建 BatchTagModal**

添加/移除 + 标签多选

- [ ] **Step 4: 创建 ColumnSettingModal**

CheckboxArray 勾选显隐列

- [ ] **Step 5: 调整 CustomerFormModal 字段布局**

按 prototype form-grid 布局: 基础信息 / 结算与业务 / 等级与消费 / 状态控制 / 备注

- [ ] **Step 6: 提交**

```bash
git add frontend/src/views/customers/components/
git commit -m "feat(customers): add batch operation modals and column settings"
```

---

## Phase 3: 页面组装

### Task 12: Index.vue 页面重写

**Files:**
- Modify: `frontend/src/views/customers/Index.vue`

**Interfaces:** 保持 useCustomerList composable 接口

- [ ] **Step 1: 重写 Index.vue 模板**

```vue
<template>
  <div class="customer-page">
    <PageHeader eyebrow="Customers" title="客户管理" subtitle="...">
      <template #actions>
        <a-button @click="openImportModal">导入客户</a-button>
        <a-button @click="handleExport">导出</a-button>
        <a-button type="primary" @click="openCreateModal">新增客户</a-button>
      </template>
    </PageHeader>

    <CustomerKpi :data="kpiData" :active="activeKpi" @kpi-change="onKpiChange" />

    <div class="card pad" style="margin-top: 14px">
      <CustomerFilters ... />
      <BatchToolbar v-if="hasSelected" :count="..." @batchEdit="..." @assignManager="..." ... />
      <CustomerTable ... @view="openPreview" />
    </div>

    <CustomerPreviewDrawer v-model:visible="previewVisible" :customer-id="previewId" />
    <!-- 所有弹窗 -->
  </div>
</template>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/customers/Index.vue
git commit -m "feat(customers): rewrite Index.vue with new component structure"
```

---

## Phase 4: 样式对齐 + 后端序列化

### Task 13: 全局样式变量对齐

**Files:**
- Modify: `frontend/src/styles/global.css`
- Modify: `frontend/src/styles/arco-theme.css`

- [ ] **Step 1: 确保 CSS 变量与 prototype 一致**

```css
:root {
  --bg: #F6F8FB;
  --panel: #FFFFFF;
  --ink: #0F172A;
  --muted: #475569;
  --line: #DBE3EF;
  --primary: #1D4ED8;
  --primary-hover: #2563EB;
  --shadow: 0 14px 40px rgba(15,23,42,.08), 0 2px 6px rgba(15,23,42,.04);
  --radius: 18px;
  --radius-sm: 12px;
}
```

- [ ] **Step 2: 提交**

```bash/src/styles/global.css frontend/src/styles/arco-theme.css
git commit -m "style: align CSS variables with prototype design tokens"
```

---

### Task 14: 后端 API 序列化扩展

**Files:**
- Modify: `backend/app/routes/customers.py` (list_customers 函数)

- [ ] **Step 1: 在 list API 返回中新增 scale_level, consume_level, balance**

```python
# 在 result["data"]["list"] 的 dict 中新增:
"scale_level": c.profile.scale_level if c.profile else None,
"consume_level": c.profile.consume_level if c.profile else None,
"balance": float(c.balance.total_amount) if c.balance else 0,
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/routes/customers.py
git commit -m "feat(api): add scale_level, consume_level, balance to customer list response"
```

---

## 验收检查清单

- [ ] 页面整体观感与 prototype/customers.html 一致
- [ ] 筛选器 FilterDropdown 单选/多选正常
- [ ] 表格列完整（含新增列），排序正常
- [ ] 行点击打开预览抽屉
- [ ] 批量操作工具栏 + 弹窗正常
- [ ] 列设置可保存到 localStorage
- [ ] 响应式布局在 960px/640px 正常
- [ ] 后端 API 返回新字段
