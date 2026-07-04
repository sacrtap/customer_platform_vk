# TD-002 前端组件拆分实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Dashboard.vue(1689行)、Balance.vue(1373行)、Invoices.vue(1037行) 拆分为 ≤300 行的视图文件 + 独立子组件 + composable，与 customers/components 模式对齐。

**Architecture:** 按视图拆分，每个视图独立拆出筛选组件、弹窗组件和 composable。子组件通过 defineModel/defineEmits 与父组件通信，API 调用和列表状态集中到 composable。

**Tech Stack:** Vue 3 Composition API + TypeScript + Arco Design Vue + Vite + Vitest

## Global Constraints

- 每个视图文件拆分后 ≤ 300 行（模板 + 脚本 + 样式）
- 每个子组件 ≤ 300 行
- 子组件通信：defineModel + defineEmits（对齐 customers/components 模式）
- Composable 命名：useXxx（对齐 useCustomerDetail.ts 模式）
- 测试覆盖率要求：≥50%（`--cov-fail-under=50`）
- 文件修改前必须先读取
- 每步完成后执行验证，通过后进入下一步

---

## 文件结构

### 新增文件（14 个）

```
frontend/src/components/layout/
├── AppSidebar.vue              # 侧边栏（logo + 导航 + 用户信息）
└── AppHeader.vue               # 顶部栏（菜单按钮 + 标题 + 面包屑 + 通知）

frontend/src/composables/
├── useAppLayout.ts             # 侧边栏折叠、移动端菜单、导航数据
├── useBalance.ts               # 余额列表加载、筛选、排序、分页
└── useInvoice.ts               # 发票列表加载、筛选、排序、分页

frontend/src/views/billing/components/
├── BalanceFilters.vue          # 余额筛选表单
├── RechargeModal.vue           # 充值弹窗
├── RechargeRecordModal.vue     # 充值记录弹窗
├── ImportBalanceModal.vue      # 余额导入弹窗
├── InvoiceFilters.vue          # 发票筛选表单
├── InvoiceDetailDrawer.vue     # 结算单详情抽屉
├── GenerateInvoiceModal.vue    # 生成结算单弹窗
├── DiscountModal.vue           # 折扣申请弹窗
└── PayModal.vue                # 付款确认弹窗
```

### 修改文件（3 个）

```
frontend/src/views/Dashboard.vue        1689行 → ~200行
frontend/src/views/billing/Balance.vue  1373行 → ~250行
frontend/src/views/billing/Invoices.vue 1037行 → ~250行
```

---

## 实施顺序

按依赖关系和复杂度排序：
1. **Dashboard.vue**（布局独立，先验证模式）
2. **Balance.vue**（复用 composable 模式）
3. **Invoices.vue**（最复杂，积累经验后处理）

每个视图拆分 = 一个独立阶段，阶段内可并行处理无依赖的子任务。

---

## 阶段 1：Dashboard.vue 拆分

### Task 1.1: 创建 useAppLayout composable

**Files:**
- Create: `frontend/src/composables/useAppLayout.ts`

**Interfaces:**
- Consumes: `useUserStore`, `useRouter`, `useRoute`
- Produces: `useAppLayout()` 返回 `{ sidebarCollapsed, mobileMenuOpen, navMenus, pageTitle, breadcrumb, currentUser, userPermissions, toggleSidebar, toggleMobileMenu }`

- [ ] **Step 1: 读取 Dashboard.vue 脚本区**

读取 `frontend/src/views/Dashboard.vue:687-855`，提取侧边栏折叠、移动端菜单、导航菜单、用户信息、面包屑等逻辑。

- [ ] **Step 2: 创建 useAppLayout.ts**

```typescript
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'

export interface NavItem {
  key: string
  label: string
  icon?: string
  to?: string
  children?: NavItem[]
  badge?: number
  permission?: string
}

export function useAppLayout() {
  const router = useRouter()
  const route = useRoute()
  const userStore = useUserStore()

  const sidebarCollapsed = ref(false)
  const mobileMenuOpen = ref(false)
  const expandedSubmenu = ref<string | null>(null)

  // 导航菜单数据（根据权限过滤）
  const navMenus = computed<NavItem[]>(() => {
    const allMenus: NavItem[] = [
      { key: 'dashboard', label: '工作台', to: '/dashboard' },
      { key: 'customers', label: '客户管理', to: '/customers' },
      {
        key: 'billing',
        label: '结算管理',
        children: [
          { key: 'balance', label: '余额管理', to: '/billing/balance' },
          { key: 'invoices', label: '结算单', to: '/billing/invoices' },
        ],
      },
      {
        key: 'system',
        label: '系统管理',
        children: [
          { key: 'users', label: '用户管理', to: '/system/users' },
          { key: 'roles', label: '角色管理', to: '/system/roles' },
        ],
      },
    ]
    return allMenus.filter(menu => {
      if (menu.permission && !userStore.hasPermission(menu.permission)) return false
      if (menu.children) {
        menu.children = menu.children.filter(child => 
          !child.permission || userStore.hasPermission(child.permission)
        )
      }
      return true
    })
  })

  // 当前页面标题
  const pageTitle = computed(() => route.meta?.title as string || '首页')

  // 面包屑
  const breadcrumb = computed(() => {
    const matched = route.matched.filter(r => r.meta?.title)
    return matched.map(r => ({ label: r.meta.title as string, to: r.path }))
  })

  // 用户信息
  const currentUser = computed(() => userStore.user)
  const userPermissions = computed(() => userStore.permissions)

  // 方法
  const toggleSidebar = () => { sidebarCollapsed.value = !sidebarCollapsed.value }
  const toggleMobileMenu = () => { mobileMenuOpen.value = !mobileMenuOpen.value }
  const closeMobileMenu = () => { mobileMenuOpen.value = false }

  // 监听路由变化，自动展开子菜单
  watch(() => route.path, (newPath) => {
    if (newPath.startsWith('/billing')) expandedSubmenu.value = 'billing'
    else if (newPath.startsWith('/system')) expandedSubmenu.value = 'system'
    else expandedSubmenu.value = null
    mobileMenuOpen.value = false
  }, { immediate: true })

  return {
    sidebarCollapsed,
    mobileMenuOpen,
    expandedSubmenu,
    navMenus,
    pageTitle,
    breadcrumb,
    currentUser,
    userPermissions,
    toggleSidebar,
    toggleMobileMenu,
    closeMobileMenu,
  }
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/composables/useAppLayout.ts
git commit -m "feat: 添加 useAppLayout composable"
```

---

### Task 1.2: 创建 AppSidebar.vue 组件

**Files:**
- Create: `frontend/src/components/layout/AppSidebar.vue`

**Interfaces:**
- Consumes: `useAppLayout` composable
- Produces: `AppSidebar.vue` 组件，通过 `defineEmits` 暴露 `toggle-collapse` 和 `close-mobile` 事件

- [ ] **Step 1: 读取 Dashboard.vue 侧边栏模板**

读取 `frontend/src/views/Dashboard.vue:4-465`，提取侧边栏模板结构。

- [ ] **Step 2: 创建 AppSidebar.vue**

```vue
<template>
  <aside :class="['sidebar', { collapsed: sidebarCollapsed, 'mobile-open': mobileMenuOpen }]">
    <!-- Logo -->
    <div class="sidebar-logo">
      <div class="logo-icon">
        <!-- SVG logo -->
      </div>
      <span v-if="!sidebarCollapsed" class="logo-text">Customer Platform VK</span>
    </div>

    <!-- 导航菜单 -->
    <nav class="sidebar-nav">
      <div v-for="section in navSections" :key="section.key" class="nav-section">
        <!-- 一级菜单 -->
        <template v-if="section.children">
          <div
            :class="['nav-item', 'nav-parent', { active: isParentActive(section.key), expanded: expandedSubmenu === section.key }]"
            @click="toggleSubmenu(section.key)"
          >
            <!-- 图标 + 标签 -->
          </div>
          <!-- 二级菜单 -->
          <div v-if="expandedSubmenu === section.key || sidebarCollapsed" class="nav-submenu">
            <router-link
              v-for="child in section.children"
              :key="child.key"
              :to="child.to!"
              class="nav-item nav-child"
            >
              {{ child.label }}
            </router-link>
          </div>
        </template>
        <router-link v-else :to="section.to!" class="nav-item" active-class="active">
          {{ section.label }}
        </router-link>
      </div>
    </nav>

    <!-- 用户信息 -->
    <div class="sidebar-user">
      <div class="sidebar-user-info">
        <!-- 用户头像 + 名称 -->
      </div>
      <div class="sidebar-toggle" @click="emit('toggle-collapse')">
        <!-- 折叠按钮 -->
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAppLayout } from '@/composables/useAppLayout'

const emit = defineEmits<{
  'toggle-collapse': []
  'close-mobile': []
}>()

const {
  sidebarCollapsed,
  mobileMenuOpen,
  expandedSubmenu,
  navMenus,
  currentUser,
  toggleSidebar,
  toggleMobileMenu,
} = useAppLayout()

const navSections = computed(() => navMenus.value)

const isParentActive = (key: string) => {
  // 判断父菜单是否应该高亮
}

const toggleSubmenu = (key: string) => {
  expandedSubmenu.value = expandedSubmenu.value === key ? null : key
}
</script>

<style scoped>
/* 从 Dashboard.vue 提取侧边栏样式 */
.sidebar { /* ... */ }
.sidebar.collapsed { /* ... */ }
.sidebar-nav { /* ... */ }
/* ... 约 200 行样式 ... */
</style>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/layout/AppSidebar.vue
git commit -m "feat: 添加 AppSidebar 布局组件"
```

---

### Task 1.3: 创建 AppHeader.vue 组件

**Files:**
- Create: `frontend/src/components/layout/AppHeader.vue`

**Interfaces:**
- Consumes: `useAppLayout` composable
- Produces: `AppHeader.vue` 组件，通过 `defineEmits` 暴露 `toggle-mobile` 事件

- [ ] **Step 1: 读取 Dashboard.vue 顶部栏模板**

读取 `frontend/src/views/Dashboard.vue:471-677`，提取顶部栏模板结构。

- [ ] **Step 2: 创建 AppHeader.vue**

```vue
<template>
  <header class="header">
    <div class="header-left">
      <button class="mobile-menu-btn" aria-label="打开菜单" @click="emit('toggle-mobile')">
        <!-- 菜单图标 -->
      </button>
      <h1 class="header-title">{{ pageTitle }}</h1>
      <div class="header-breadcrumb">
        <router-link to="/">首页</router-link>
        <span>/</span>
        <span class="current">{{ pageTitle }}</span>
      </div>
    </div>

    <div class="header-right">
      <!-- 通知按钮 -->
      <ActionButton label="消息通知" :badge="3" @click="handleNotification">
        <!-- 通知图标 -->
      </ActionButton>

      <!-- 用户菜单 -->
      <a-dropdown>
        <div class="user-menu-trigger">
          <!-- 用户头像 + 名称 -->
        </div>
        <template #content>
          <a-doption @click="handleChangePassword">修改密码</a-doption>
          <a-doption @click="handleLogout">退出登录</a-doption>
        </template>
      </a-dropdown>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useAppLayout } from '@/composables/useAppLayout'
import ActionButton from '@/components/ActionButton.vue'

const emit = defineEmits<{
  'toggle-mobile': []
}>()

const { pageTitle, breadcrumb, currentUser } = useAppLayout()

const handleNotification = () => {
  // 通知功能开发中
}

const handleChangePassword = () => {
  // 修改密码逻辑（从 Dashboard.vue 迁移）
}

const handleLogout = () => {
  // 退出登录逻辑（从 Dashboard.vue 迁移）
}
</script>

<style scoped>
/* 从 Dashboard.vue 提取顶部栏样式 */
.header { /* ... */ }
/* ... 约 100 行样式 ... */
</style>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/layout/AppHeader.vue
git commit -m "feat: 添加 AppHeader 布局组件"
```

---

### Task 1.4: 精简 Dashboard.vue

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`

**Interfaces:**
- Consumes: `AppSidebar.vue`, `AppHeader.vue`, `useAppLayout.ts`
- Produces: 精简后的 Dashboard.vue（~200 行）

- [ ] **Step 1: 读取 Dashboard.vue 完整内容**

读取 `frontend/src/views/Dashboard.vue:1-1689`，确认所有需要迁移的部分。

- [ ] **Step 2: 替换模板区**

将侧边栏和顶部栏替换为组件引用：

```vue
<template>
  <div class="dashboard-layout">
    <AppSidebar
      @toggle-collapse="toggleSidebar"
      @close-mobile="closeMobileMenu"
    />

    <div v-if="mobileMenuOpen" class="mobile-overlay" @click="closeMobileMenu" />

    <main :class="['main-content', { 'sidebar-collapsed': sidebarCollapsed }]">
      <AppHeader @toggle-mobile="toggleMobileMenu" />

      <div class="page-content">
        <router-view />
      </div>
    </main>
  </div>
</template>
```

- [ ] **Step 3: 替换脚本区**

```typescript
<script setup lang="ts">
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import { useAppLayout } from '@/composables/useAppLayout'

const {
  sidebarCollapsed,
  mobileMenuOpen,
  toggleSidebar,
  toggleMobileMenu,
  closeMobileMenu,
} = useAppLayout()
</script>
```

- [ ] **Step 4: 精简样式区**

删除侧边栏和顶部栏样式，仅保留 `.dashboard-layout`、`.main-content`、`.page-content`、`.mobile-overlay` 等容器样式。

- [ ] **Step 5: 验证**

```bash
cd frontend && npm run type-check
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/views/Dashboard.vue
git commit -m "refactor: 精简 Dashboard.vue，拆出 AppSidebar 和 AppHeader"
```

---

## 阶段 2：Balance.vue 拆分

### Task 2.1: 创建 useBalance composable

**Files:**
- Create: `frontend/src/composables/useBalance.ts`

**Interfaces:**
- Consumes: `getBalances`, `recharge`, `getRechargeRecords`, `importBalances`, `downloadBalanceImportTemplate` from `@/api/billing`
- Produces: `useBalance()` 返回 `{ balances, loading, pagination, sortState, filters, loadBalances, handleSearch, handleReset }`

- [ ] **Step 1: 读取 Balance.vue 脚本区**

读取 `frontend/src/views/billing/Balance.vue:483-1028`，提取列表加载、筛选、排序、分页逻辑。

- [ ] **Step 2: 创建 useBalance.ts**

```typescript
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  getBalances,
  recharge,
  getRechargeRecords,
  importBalances,
  downloadBalanceImportTemplate,
  type Balance,
  type RechargeRecord,
} from '@/api/billing'

export function useBalance() {
  const balances = ref<Balance[]>([])
  const loading = ref(false)
  const pagination = reactive({
    current: 1,
    pageSize: 20,
    total: 0,
    showTotal: true,
    showPageSize: true,
  })
  const sortState = reactive({
    sort_by: 'id',
    sort_order: 'ascend' as 'ascend' | 'descend' | '',
  })

  const filters = reactive({
    keyword: '',
    customer_id: undefined as number | undefined,
    min_amount: undefined as number | undefined,
    max_amount: undefined as number | undefined,
  })

  async function loadBalances() {
    loading.value = true
    try {
      const res = await getBalances({
        ...filters,
        sort_by: sortState.sort_by,
        sort_order: sortState.sort_order === 'ascend' ? 'asc' : 'desc',
        page: pagination.current,
        page_size: pagination.pageSize,
      })
      balances.value = res.data.items
      pagination.total = res.data.total
    } finally {
      loading.value = false
    }
  }

  function handleSearch() {
    pagination.current = 1
    loadBalances()
  }

  function handleReset() {
    filters.keyword = ''
    filters.customer_id = undefined
    filters.min_amount = undefined
    filters.max_amount = undefined
    pagination.current = 1
    loadBalances()
  }

  function handlePageChange(page: number) {
    pagination.current = page
    loadBalances()
  }

  function handlePageSizeChange(pageSize: number) {
    pagination.pageSize = pageSize
    pagination.current = 1
    loadBalances()
  }

  function handleSortChange(sortBy: string, sortOrder: string) {
    sortState.sort_by = sortBy
    sortState.sort_order = sortOrder as 'ascend' | 'descend' | ''
    loadBalances()
  }

  onMounted(() => {
    loadBalances()
  })

  return {
    balances,
    loading,
    pagination,
    sortState,
    filters,
    loadBalances,
    handleSearch,
    handleReset,
    handlePageChange,
    handlePageSizeChange,
    handleSortChange,
  }
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/composables/useBalance.ts
git commit -m "feat: 添加 useBalance composable"
```

---

### Task 2.2: 创建 BalanceFilters.vue 组件

**Files:**
- Create: `frontend/src/views/billing/components/BalanceFilters.vue`

**Interfaces:**
- Consumes: `filters` 对象（defineModel）
- Produces: `BalanceFilters.vue` 组件，通过 `defineEmits` 暴露 `search` 和 `reset` 事件

- [ ] **Step 1: 读取 Balance.vue 筛选模板**

读取 `frontend/src/views/billing/Balance.vue:35-190`，提取筛选表单结构。

- [ ] **Step 2: 创建 BalanceFilters.vue**

```vue
<template>
  <div class="filter-section">
    <a-form layout="vertical" :model="filters">
      <a-row :gutter="16">
        <a-col :span="6">
          <a-form-item field="keyword" label="关键词">
            <a-input v-model="filters.keyword" placeholder="客户名称/公司ID" allow-clear @search="emit('search')" />
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="customer_id" label="客户">
            <CustomerAutoComplete v-model="filters.customer_id" placeholder="选择客户" />
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="min_amount" label="最小金额">
            <a-input-number v-model="filters.min_amount" placeholder="最小金额" :min="0" />
          </a-form-item>
        </a-col>
        <a-col :span="6">
          <a-form-item field="max_amount" label="最大金额">
            <a-input-number v-model="filters.max_amount" placeholder="最大金额" :min="0" />
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>

    <a-collapse class="advanced-filter-collapse">
      <a-collapse-item key="advanced" header="高级筛选">
        <!-- 高级筛选内容 -->
      </a-collapse-item>
    </a-collapse>

    <div class="filter-actions">
      <a-button type="primary" @click="emit('search')">
        <template #icon><icon-search /></template>
        搜索
      </a-button>
      <a-button @click="emit('reset')">
        <template #icon><icon-refresh /></template>
        重置
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'

interface Filters {
  keyword: string
  customer_id: number | undefined
  min_amount: number | undefined
  max_amount: number | undefined
}

const filters = defineModel<Filters>('filters', { required: true })

const emit = defineEmits<{
  search: []
  reset: []
}>()
</script>

<style scoped>
.filter-section { /* ... */ }
/* ... 约 80 行样式 ... */
</style>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/billing/components/BalanceFilters.vue
git commit -m "feat: 添加 BalanceFilters 筛选组件"
```

---

### Task 2.3: 创建 RechargeModal.vue 组件

**Files:**
- Create: `frontend/src/views/billing/components/RechargeModal.vue`

**Interfaces:**
- Consumes: `recharge` API
- Produces: `RechargeModal.vue` 组件，通过 `defineModel` 控制显示状态，`defineEmits` 暴露 `success` 事件

- [ ] **Step 1: 读取 Balance.vue 充值弹窗模板**

读取 `frontend/src/views/billing/Balance.vue:249-292`，提取充值弹窗结构。

- [ ] **Step 2: 创建 RechargeModal.vue**

```vue
<template>
  <a-modal
    v-model:visible="isVisible"
    title="客户充值"
    :confirm-loading="loading"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item field="customer_id" label="客户" required>
        <CustomerAutoComplete v-model="form.customer_id" placeholder="选择客户" />
      </a-form-item>
      <a-form-item field="amount" label="充值金额" required>
        <a-input-number v-model="form.amount" placeholder="充值金额" :min="0.01" :precision="2" />
      </a-form-item>
      <a-form-item field="remark" label="备注">
        <a-textarea v-model="form.remark" placeholder="备注" :max-length="200" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { recharge } from '@/api/billing'
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  customer_id: undefined as number | undefined,
  amount: undefined as number | undefined,
  remark: '',
})

const rules = {
  customer_id: [{ required: true, message: '请选择客户' }],
  amount: [{ required: true, message: '请输入充值金额' }],
}

async function handleSubmit() {
  const valid = await formRef.value?.validate()
  if (valid) return false

  loading.value = true
  try {
    await recharge({
      customer_id: form.customer_id!,
      amount: form.amount!,
      remark: form.remark,
    })
    Message.success('充值成功')
    emit('success')
    return true
  } catch (error: unknown) {
    Message.error((error as Error).message || '充值失败')
    return false
  } finally {
    loading.value = false
  }
}

function handleCancel() {
  formRef.value?.resetFields()
  emit('update:visible', false)
}
</script>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/billing/components/RechargeModal.vue
git commit -m "feat: 添加 RechargeModal 充值弹窗组件"
```

---

### Task 2.4: 创建 RechargeRecordModal.vue 组件

**Files:**
- Create: `frontend/src/views/billing/components/RechargeRecordModal.vue`

**Interfaces:**
- Consumes: `getRechargeRecords` API
- Produces: `RechargeRecordModal.vue` 组件

- [ ] **Step 1: 读取 Balance.vue 充值记录弹窗模板**

读取 `frontend/src/views/billing/Balance.vue:295-324`，提取充值记录弹窗结构。

- [ ] **Step 2: 创建 RechargeRecordModal.vue**

```vue
<template>
  <a-modal
    v-model:visible="isVisible"
    title="充值记录"
    :footer="false"
    width="800px"
    @cancel="handleCancel"
  >
    <a-table :data="records" :loading="loading" :pagination="pagination">
      <template #columns>
        <a-table-column title="充值时间" dataIndex="created_at" :width="180" />
        <a-table-column title="金额" dataIndex="amount" :width="200" />
        <a-table-column title="备注" dataIndex="remark" />
      </template>
    </a-table>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { getRechargeRecords, type RechargeRecord } from '@/api/billing'

const props = defineProps<{
  visible: boolean
  customerId?: number
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const records = ref<RechargeRecord[]>([])
const loading = ref(false)
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

async function loadRecords() {
  if (!props.customerId) return
  loading.value = true
  try {
    const res = await getRechargeRecords({
      customer_id: props.customerId,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    records.value = res.data.items
    pagination.total = res.data.total
  } finally {
    loading.value = false
  }
}

watch(() => props.visible, (val) => {
  if (val) {
    pagination.current = 1
    loadRecords()
  }
})

function handleCancel() {
  emit('update:visible', false)
}
</script>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/billing/components/RechargeRecordModal.vue
git commit -m "feat: 添加 RechargeRecordModal 充值记录弹窗组件"
```

---

### Task 2.5: 创建 ImportBalanceModal.vue 组件

**Files:**
- Create: `frontend/src/views/billing/components/ImportBalanceModal.vue`

**Interfaces:**
- Consumes: `importBalances`, `downloadBalanceImportTemplate` API
- Produces: `ImportBalanceModal.vue` 组件

- [ ] **Step 1: 读取 Balance.vue 导入弹窗模板**

读取 `frontend/src/views/billing/Balance.vue:327-479`，提取导入弹窗结构。

- [ ] **Step 2: 创建 ImportBalanceModal.vue**

```vue
<template>
  <a-modal
    v-model:visible="isVisible"
    title="余额导入"
    :confirm-loading="loading"
    @before-ok="handleImport"
    @cancel="handleCancel"
  >
    <div class="import-modal-content">
      <a-upload
        ref="uploadRef"
        accept=".xlsx,.xls"
        :limit="1"
        :custom-request="handleUpload"
      >
        <template #upload-button>
          <div class="upload-area">
            <icon-upload />
            <span>点击或拖拽文件到此处上传</span>
          </div>
        </template>
      </a-upload>

      <div class="import-tips">
        <div class="tips-title">
          <icon-info-circle />
          导入须知
        </div>
        <ul class="tips-list">
          <li>请使用下载的模板文件填写充值数据</li>
          <li>确保必填字段（公司 ID、充值金额等）已填写</li>
          <li>单次导入建议不超过 1000 条数据</li>
        </ul>
      </div>

      <div v-if="importResult" class="import-result">
        <a-alert :type="importResult.error_count > 0 ? 'warning' : 'success'">
          导入完成：成功 {{ importResult.success_count }} 条，失败 {{ importResult.error_count }} 条
        </a-alert>
        <div v-if="importResult.errors && importResult.errors.length > 0" class="import-errors">
          <div class="errors-title">失败详情：</div>
          <ul class="errors-list">
            <li v-for="(error, index) in importResult.errors" :key="index">{{ error }}</li>
          </ul>
        </div>
      </div>
    </div>

    <template #footer>
      <a-button @click="downloadTemplate">下载模板</a-button>
      <a-button @click="handleCancel">取消</a-button>
      <a-button type="primary" :loading="loading" @click="handleImport">导入</a-button>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import { importBalances, downloadBalanceImportTemplate } from '@/api/billing'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const loading = ref(false)
const file = ref<File | null>(null)
const importResult = ref<{
  success_count: number
  error_count: number
  errors: string[]
} | null>(null)

function handleUpload(options: any) {
  file.value = options.file
  return {
    status: 'done',
    response: { message: '上传成功' },
  }
}

async function handleImport() {
  if (!file.value) {
    Message.warning('请选择文件')
    return false
  }

  loading.value = true
  try {
    const res = await importBalances(file.value)
    importResult.value = res.data
    if (res.data.error_count === 0) {
      Message.success('导入成功')
      emit('success')
      return true
    } else {
      Message.warning(`导入完成：成功 ${res.data.success_count} 条，失败 ${res.data.error_count} 条`)
      return false
    }
  } catch (error: unknown) {
    Message.error((error as Error).message || '导入失败')
    return false
  } finally {
    loading.value = false
  }
}

async function downloadTemplate() {
  try {
    const response = await downloadBalanceImportTemplate()
    const blob = new Blob([response.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '余额导入模板.xlsx'
    link.click()
    window.URL.revokeObjectURL(url)
    Message.success('模板下载成功')
  } catch (error: unknown) {
    Message.error((error as Error).message || '下载模板失败')
  }
}

function handleCancel() {
  file.value = null
  importResult.value = null
  emit('update:visible', false)
}
</script>

<style scoped>
.import-modal-content { /* ... */ }
.upload-area { /* ... */ }
.import-tips { /* ... */ }
.import-result { /* ... */ }
/* ... 约 100 行样式 ... */
</style>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/billing/components/ImportBalanceModal.vue
git commit -m "feat: 添加 ImportBalanceModal 导入弹窗组件"
```

---

### Task 2.6: 精简 Balance.vue

**Files:**
- Modify: `frontend/src/views/billing/Balance.vue`

**Interfaces:**
- Consumes: `BalanceFilters.vue`, `RechargeModal.vue`, `RechargeRecordModal.vue`, `ImportBalanceModal.vue`, `useBalance.ts`
- Produces: 精简后的 Balance.vue（~250 行）

- [ ] **Step 1: 读取 Balance.vue 完整内容**

读取 `frontend/src/views/billing/Balance.vue:1-1373`，确认所有需要迁移的部分。

- [ ] **Step 2: 替换模板区**

```vue
<template>
  <div class="balance-management-page">
    <div class="page-header">
      <div class="header-title">
        <h1>余额管理</h1>
        <p class="header-subtitle">客户余额查询、充值与导入</p>
      </div>
      <div class="header-actions">
        <a-button v-if="can('balance:recharge')" type="primary" @click="openRechargeModal">
          <template #icon><icon-plus /></template>
          充值
        </a-button>
        <a-button v-if="can('balance:import')" @click="openImportModal">
          <template #icon><icon-upload /></template>
          导入
        </a-button>
      </div>
    </div>

    <BalanceFilters
      v-model="filters"
      @search="handleSearch"
      @reset="handleReset"
    />

    <div class="table-section">
      <a-table
        :data="balances"
        :loading="loading"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        @sort-change="handleSortChange"
      >
        <!-- 表格列定义 -->
      </a-table>
    </div>

    <RechargeModal
      v-model:visible="rechargeModalVisible"
      @success="loadBalances"
    />

    <RechargeRecordModal
      v-model:visible="recordModalVisible"
      :customer-id="currentRecordCustomerId"
    />

    <ImportBalanceModal
      v-model:visible="importModalVisible"
      @success="loadBalances"
    />
  </div>
</template>
```

- [ ] **Step 3: 替换脚本区**

```typescript
<script setup lang="ts">
import { reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import { useBalance } from '@/composables/useBalance'
import BalanceFilters from './components/BalanceFilters.vue'
import RechargeModal from './components/RechargeModal.vue'
import RechargeRecordModal from './components/RechargeRecordModal.vue'
import ImportBalanceModal from './components/ImportBalanceModal.vue'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

const {
  balances,
  loading,
  pagination,
  sortState,
  filters,
  loadBalances,
  handleSearch,
  handleReset,
  handlePageChange,
  handlePageSizeChange,
  handleSortChange,
} = useBalance()

const rechargeModalVisible = ref(false)
const importModalVisible = ref(false)
const recordModalVisible = ref(false)
const currentRecordCustomerId = ref<number | null>(null)

function openRechargeModal() {
  rechargeModalVisible.value = true
}

function openImportModal() {
  importModalVisible.value = true
}

function openRecordModal(customerId: number) {
  currentRecordCustomerId.value = customerId
  recordModalVisible.value = true
}
</script>
```

- [ ] **Step 4: 精简样式区**

删除筛选、弹窗相关样式，仅保留页面容器、表格、页头样式。

- [ ] **Step 5: 验证**

```bash
cd frontend && npm run type-check
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/views/billing/Balance.vue
git commit -m "refactor: 精简 Balance.vue，拆出筛选和弹窗组件"
```

---

## 阶段 3：Invoices.vue 拆分

### Task 3.1: 创建 useInvoice composable

**Files:**
- Create: `frontend/src/composables/useInvoice.ts`

**Interfaces:**
- Consumes: `getInvoices`, `getInvoice` from `@/api/billing`
- Produces: `useInvoice()` 返回 `{ invoices, loading, selectedInvoice, pagination, sortState, filters, loadInvoices, loadInvoiceDetail, handleSearch, handleReset }`

- [ ] **Step 1: 读取 Invoices.vue 脚本区**

读取 `frontend/src/views/billing/Invoices.vue:408-879`，提取列表加载、筛选、排序、分页、详情加载逻辑。

- [ ] **Step 2: 创建 useInvoice.ts**

```typescript
import { ref, reactive, onMounted } from 'vue'
import { getInvoices, getInvoice, type Invoice } from '@/api/billing'

export function useInvoice() {
  const invoices = ref<Invoice[]>([])
  const loading = ref(false)
  const selectedInvoice = ref<Invoice | null>(null)
  const pagination = reactive({
    current: 1,
    pageSize: 20,
    total: 0,
    showTotal: true,
    showPageSize: true,
  })
  const sortState = reactive({
    sort_by: 'id',
    sort_order: 'ascend' as 'ascend' | 'descend' | '',
  })

  const filters = reactive({
    keyword: '',
    status: undefined as string | undefined,
  })

  async function loadInvoices() {
    loading.value = true
    try {
      const res = await getInvoices({
        ...filters,
        sort_by: sortState.sort_by,
        sort_order: sortState.sort_order === 'ascend' ? 'asc' : 'desc',
        page: pagination.current,
        page_size: pagination.pageSize,
      })
      invoices.value = res.data.items
      pagination.total = res.data.total
    } finally {
      loading.value = false
    }
  }

  async function loadInvoiceDetail(id: number) {
    const res = await getInvoice(id)
    selectedInvoice.value = res.data
  }

  function handleSearch() {
    pagination.current = 1
    loadInvoices()
  }

  function handleReset() {
    filters.keyword = ''
    filters.status = undefined
    pagination.current = 1
    loadInvoices()
  }

  function handlePageChange(page: number) {
    pagination.current = page
    loadInvoices()
  }

  function handlePageSizeChange(pageSize: number) {
    pagination.pageSize = pageSize
    pagination.current = 1
    loadInvoices()
  }

  function handleSortChange(sortBy: string, sortOrder: string) {
    sortState.sort_by = sortBy
    sortState.sort_order = sortOrder as 'ascend' | 'descend' | ''
    loadInvoices()
  }

  onMounted(() => {
    loadInvoices()
  })

  return {
    invoices,
    loading,
    selectedInvoice,
    pagination,
    sortState,
    filters,
    loadInvoices,
    loadInvoiceDetail,
    handleSearch,
    handleReset,
    handlePageChange,
    handlePageSizeChange,
    handleSortChange,
  }
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/composables/useInvoice.ts
git commit -m "feat: 添加 useInvoice composable"
```

---

### Task 3.2: 创建 InvoiceFilters.vue 组件

**Files:**
- Create: `frontend/src/views/billing/components/InvoiceFilters.vue`

**Interfaces:**
- Consumes: `filters` 对象（defineModel）
- Produces: `InvoiceFilters.vue` 组件

- [ ] **Step 1: 读取 Invoices.vue 筛选模板**

读取 `frontend/src/views/billing/Invoices.vue:49-88`，提取筛选表单结构。

- [ ] **Step 2: 创建 InvoiceFilters.vue**

```vue
<template>
  <div class="filter-section">
    <a-form layout="vertical" :model="filters">
      <a-row :gutter="16">
        <a-col :span="8">
          <a-form-item field="keyword" label="关键词">
            <KeywordAutoComplete v-model="filters.keyword" placeholder="结算单号/客户名称" @search="emit('search')" />
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item field="status" label="状态">
            <a-select v-model="filters.status" placeholder="选择状态" allow-clear>
              <a-option value="draft">草稿</a-option>
              <a-option value="pending_customer">待客户确认</a-option>
              <a-option value="pending_payment">待付款</a-option>
              <a-option value="paid">已付款</a-option>
              <a-option value="completed">已完成</a-option>
              <a-option value="cancelled">已取消</a-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="8">
          <a-form-item>
            <a-button type="primary" @click="emit('search')">
              <template #icon><icon-search /></template>
              搜索
            </a-button>
            <a-button @click="emit('reset')">
              <template #icon><icon-refresh /></template>
              重置
            </a-button>
          </a-form-item>
        </a-col>
      </a-row>
    </a-form>
  </div>
</template>

<script setup lang="ts">
import KeywordAutoComplete from '@/components/KeywordAutoComplete.vue'

interface Filters {
  keyword: string
  status: string | undefined
}

const filters = defineModel<Filters>('filters', { required: true })

const emit = defineEmits<{
  search: []
  reset: []
}>()
</script>

<style scoped>
.filter-section { /* ... */ }
/* ... 约 50 行样式 ... */
</style>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/billing/components/InvoiceFilters.vue
git commit -m "feat: 添加 InvoiceFilters 筛选组件"
```

---

### Task 3.3: 创建 InvoiceDetailDrawer.vue 组件

**Files:**
- Create: `frontend/src/views/billing/components/InvoiceDetailDrawer.vue`

**Interfaces:**
- Consumes: `InvoiceStatusBadge`, `InvoiceTimeline` from `@/components/invoice/`
- Produces: `InvoiceDetailDrawer.vue` 组件

- [ ] **Step 1: 读取 Invoices.vue 详情抽屉模板**

读取 `frontend/src/views/billing/Invoices.vue:191-332`，提取详情抽屉结构。

- [ ] **Step 2: 创建 InvoiceDetailDrawer.vue**

```vue
<template>
  <a-drawer v-model:visible="isVisible" title="结算单详情" width="720px" unmount-on-close>
    <template v-if="invoice">
      <div class="invoice-detail">
        <div class="detail-header">
          <h2>{{ invoice.invoice_no }}</h2>
          <InvoiceStatusBadge :status="invoice.status" />
        </div>

        <a-descriptions :data="detailItems" :column="2" bordered />

        <div class="detail-section">
          <h3>状态时间线</h3>
          <InvoiceTimeline :invoice="invoice" />
        </div>

        <div class="detail-section">
          <h3>结算明细</h3>
          <a-table :data="invoice.items" :pagination="false">
            <!-- 明细列 -->
          </a-table>
        </div>
      </div>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Invoice } from '@/api/billing'
import InvoiceStatusBadge from '@/components/invoice/InvoiceStatusBadge.vue'
import InvoiceTimeline from '@/components/invoice/InvoiceTimeline.vue'

const props = defineProps<{
  visible: boolean
  invoice: Invoice | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const detailItems = computed(() => {
  if (!props.invoice) return []
  return [
    { label: '客户名称', value: props.invoice.customer_name },
    { label: '结算金额', value: props.invoice.amount },
    { label: '创建时间', value: props.invoice.created_at },
    // ... 更多字段
  ]
})
</script>

<style scoped>
.invoice-detail { /* ... */ }
.detail-header { /* ... */ }
.detail-section { /* ... */ }
/* ... 约 80 行样式 ... */
</style>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/billing/components/InvoiceDetailDrawer.vue
git commit -m "feat: 添加 InvoiceDetailDrawer 详情抽屉组件"
```

---

### Task 3.4: 创建 GenerateInvoiceModal.vue 组件

**Files:**
- Create: `frontend/src/views/billing/components/GenerateInvoiceModal.vue`

**Interfaces:**
- Consumes: `generateInvoice`, `calculateInvoiceItems` API
- Produces: `GenerateInvoiceModal.vue` 组件

- [ ] **Step 1: 读取 Invoices.vue 生成结算单弹窗模板**

读取 `frontend/src/views/billing/Invoices.vue:335-357`，提取生成结算单弹窗结构。

- [ ] **Step 2: 创建 GenerateInvoiceModal.vue**

```vue
<template>
  <a-modal
    v-model:visible="isVisible"
    title="生成结算单"
    :confirm-loading="loading"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item field="customer_id" label="客户" required>
        <CustomerAutoComplete v-model="form.customer_id" placeholder="选择客户" @change="handleCustomerChange" />
      </a-form-item>
      <a-form-item field="billing_period" label="结算周期" required>
        <a-range-picker v-model="form.billing_period" />
      </a-form-item>
      <a-form-item field="remark" label="备注">
        <a-textarea v-model="form.remark" placeholder="备注" :max-length="200" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { generateInvoice, calculateInvoiceItems } from '@/api/billing'
import CustomerAutoComplete from '@/components/CustomerAutoComplete.vue'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  customer_id: undefined as number | undefined,
  billing_period: [] as string[],
  remark: '',
})

const rules = {
  customer_id: [{ required: true, message: '请选择客户' }],
  billing_period: [{ required: true, message: '请选择结算周期' }],
}

async function handleCustomerChange(customerId: number) {
  // 计算结算项预览
  if (customerId && form.billing_period.length === 2) {
    const res = await calculateInvoiceItems({
      customer_id: customerId,
      start_date: form.billing_period[0],
      end_date: form.billing_period[1],
    })
    // 更新预览
  }
}

async function handleSubmit() {
  const valid = await formRef.value?.validate()
  if (valid) return false

  loading.value = true
  try {
    await generateInvoice({
      customer_id: form.customer_id!,
      start_date: form.billing_period[0],
      end_date: form.billing_period[1],
      remark: form.remark,
    })
    Message.success('结算单生成成功')
    emit('success')
    return true
  } catch (error: unknown) {
    Message.error((error as Error).message || '生成失败')
    return false
  } finally {
    loading.value = false
  }
}

function handleCancel() {
  formRef.value?.resetFields()
  emit('update:visible', false)
}
</script>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/billing/components/GenerateInvoiceModal.vue
git commit -m "feat: 添加 GenerateInvoiceModal 生成结算单弹窗组件"
```

---

### Task 3.5: 创建 DiscountModal.vue 组件

**Files:**
- Create: `frontend/src/views/billing/components/DiscountModal.vue`

**Interfaces:**
- Consumes: `applyDiscount` API
- Produces: `DiscountModal.vue` 组件

- [ ] **Step 1: 读取 Invoices.vue 折扣弹窗模板**

读取 `frontend/src/views/billing/Invoices.vue:360-387`，提取折扣弹窗结构。

- [ ] **Step 2: 创建 DiscountModal.vue**

```vue
<template>
  <a-modal
    v-model:visible="isVisible"
    title="折扣申请"
    :confirm-loading="loading"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item field="discount_amount" label="折扣金额" required>
        <a-input-number v-model="form.discount_amount" placeholder="折扣金额" :min="0" :precision="2" />
      </a-form-item>
      <a-form-item field="reason" label="申请原因" required>
        <a-textarea v-model="form.reason" placeholder="申请原因" :max-length="200" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { applyDiscount } from '@/api/billing'

const props = defineProps<{
  visible: boolean
  invoiceId?: number
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  discount_amount: undefined as number | undefined,
  reason: '',
})

const rules = {
  discount_amount: [{ required: true, message: '请输入折扣金额' }],
  reason: [{ required: true, message: '请输入申请原因' }],
}

async function handleSubmit() {
  if (!props.invoiceId) return false

  const valid = await formRef.value?.validate()
  if (valid) return false

  loading.value = true
  try {
    await applyDiscount({
      invoice_id: props.invoiceId,
      discount_amount: form.discount_amount!,
      reason: form.reason,
    })
    Message.success('折扣申请提交成功')
    emit('success')
    return true
  } catch (error: unknown) {
    Message.error((error as Error).message || '申请失败')
    return false
  } finally {
    loading.value = false
  }
}

function handleCancel() {
  formRef.value?.resetFields()
  emit('update:visible', false)
}
</script>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/billing/components/DiscountModal.vue
git commit -m "feat: 添加 DiscountModal 折扣申请弹窗组件"
```

---

### Task 3.6: 创建 PayModal.vue 组件

**Files:**
- Create: `frontend/src/views/billing/components/PayModal.vue`

**Interfaces:**
- Consumes: `payInvoice` API
- Produces: `PayModal.vue` 组件

- [ ] **Step 1: 读取 Invoices.vue 付款弹窗模板**

读取 `frontend/src/views/billing/Invoices.vue:390-405`，提取付款弹窗结构。

- [ ] **Step 2: 创建 PayModal.vue**

```vue
<template>
  <a-modal
    v-model:visible="isVisible"
    title="确认付款"
    :confirm-loading="loading"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form ref="formRef" :model="form" :rules="rules" layout="vertical">
      <a-form-item field="payment_method" label="付款方式" required>
        <a-select v-model="form.payment_method" placeholder="选择付款方式">
          <a-option value="bank_transfer">银行转账</a-option>
          <a-option value="cash">现金</a-option>
          <a-option value="check">支票</a-option>
        </a-select>
      </a-form-item>
      <a-form-item field="payment_date" label="付款日期" required>
        <a-date-picker v-model="form.payment_date" />
      </a-form-item>
      <a-form-item field="remark" label="备注">
        <a-textarea v-model="form.remark" placeholder="备注" :max-length="200" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { payInvoice } from '@/api/billing'

const props = defineProps<{
  visible: boolean
  invoiceId?: number
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  payment_method: '',
  payment_date: '',
  remark: '',
})

const rules = {
  payment_method: [{ required: true, message: '请选择付款方式' }],
  payment_date: [{ required: true, message: '请选择付款日期' }],
}

async function handleSubmit() {
  if (!props.invoiceId) return false

  const valid = await formRef.value?.validate()
  if (valid) return false

  loading.value = true
  try {
    await payInvoice({
      invoice_id: props.invoiceId,
      payment_method: form.payment_method,
      payment_date: form.payment_date,
      remark: form.remark,
    })
    Message.success('付款确认成功')
    emit('success')
    return true
  } catch (error: unknown) {
    Message.error((error as Error).message || '付款确认失败')
    return false
  } finally {
    loading.value = false
  }
}

function handleCancel() {
  formRef.value?.resetFields()
  emit('update:visible', false)
}
</script>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/billing/components/PayModal.vue
git commit -m "feat: 添加 PayModal 付款确认弹窗组件"
```

---

### Task 3.7: 精简 Invoices.vue

**Files:**
- Modify: `frontend/src/views/billing/Invoices.vue`

**Interfaces:**
- Consumes: `InvoiceFilters.vue`, `InvoiceDetailDrawer.vue`, `GenerateInvoiceModal.vue`, `DiscountModal.vue`, `PayModal.vue`, `useInvoice.ts`
- Produces: 精简后的 Invoices.vue（~250 行）

- [ ] **Step 1: 读取 Invoices.vue 完整内容**

读取 `frontend/src/views/billing/Invoices.vue:1-1037`，确认所有需要迁移的部分。

- [ ] **Step 2: 替换模板区**

```vue
<template>
  <div class="invoice-management-page">
    <div class="page-header">
      <div class="header-title">
        <h1>结算单管理</h1>
        <p class="header-subtitle">结算单查询、生成与付款</p>
      </div>
      <div class="header-actions">
        <a-button v-if="can('invoice:generate')" type="primary" @click="openGenerateModal">
          <template #icon><icon-plus /></template>
          生成结算单
        </a-button>
      </div>
    </div>

    <InvoiceFilters
      v-model="filters"
      @search="handleSearch"
      @reset="handleReset"
    />

    <div class="table-section">
      <a-table
        :data="invoices"
        :loading="loading"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        @sort-change="handleSortChange"
      >
        <!-- 表格列定义 -->
      </a-table>
    </div>

    <InvoiceDetailDrawer
      v-model:visible="drawerVisible"
      :invoice="selectedInvoice"
    />

    <GenerateInvoiceModal
      v-model:visible="generateModalVisible"
      @success="loadInvoices"
    />

    <DiscountModal
      v-model:visible="discountModalVisible"
      :invoice-id="selectedInvoice?.id"
      @success="loadInvoices"
    />

    <PayModal
      v-model:visible="payModalVisible"
      :invoice-id="selectedInvoice?.id"
      @success="loadInvoices"
    />
  </div>
</template>
```

- [ ] **Step 3: 替换脚本区**

```typescript
<script setup lang="ts">
import { ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { useInvoice } from '@/composables/useInvoice'
import InvoiceFilters from './components/InvoiceFilters.vue'
import InvoiceDetailDrawer from './components/InvoiceDetailDrawer.vue'
import GenerateInvoiceModal from './components/GenerateInvoiceModal.vue'
import DiscountModal from './components/DiscountModal.vue'
import PayModal from './components/PayModal.vue'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

const {
  invoices,
  loading,
  selectedInvoice,
  pagination,
  sortState,
  filters,
  loadInvoices,
  loadInvoiceDetail,
  handleSearch,
  handleReset,
  handlePageChange,
  handlePageSizeChange,
  handleSortChange,
} = useInvoice()

const drawerVisible = ref(false)
const generateModalVisible = ref(false)
const discountModalVisible = ref(false)
const payModalVisible = ref(false)

function openDrawer(invoiceId: number) {
  loadInvoiceDetail(invoiceId)
  drawerVisible.value = true
}

function openGenerateModal() {
  generateModalVisible.value = true
}

function openDiscountModal() {
  discountModalVisible.value = true
}

function openPayModal() {
  payModalVisible.value = true
}
</script>
```

- [ ] **Step 4: 精简样式区**

删除筛选、弹窗、抽屉相关样式，仅保留页面容器、表格、页头样式。

- [ ] **Step 5: 验证**

```bash
cd frontend && npm run type-check
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/views/billing/Invoices.vue
git commit -m "refactor: 精简 Invoices.vue，拆出筛选、详情抽屉和弹窗组件"
```

---

## 最终验证

完成所有阶段后执行：

```bash
cd frontend
npm run type-check   # 类型检查
npm run test        # 单元测试
npm run build       # 构建验证
```

手动验收清单：
- [ ] 侧边栏折叠/展开正常，移动端菜单正常
- [ ] 页面标题和面包屑随路由变化
- [ ] 余额筛选、充值、记录、导入流程正常
- [ ] 发票筛选、详情抽屉、生成、折扣、付款正常
- [ ] 弹窗状态互不干扰，关闭后数据重置正确
