# TD-002 前端组件拆续拆设计文档

**创建日期**: 2026-07-04
**状态**: 待审核
**范围**: Dashboard.vue(1689行)、Balance.vue(1373行)、Invoices.vue(1037行)
**模式对齐**: customers/components 已验证模式

---

## 一、背景与目标

TD-002 前端单文件过大已通过 customers/Detail.vue 和 customers/Index.vue 拆分部分缓解，但仍有 3 个视图文件超 1000 行。本轮按方案 A（与 customers/components 对齐）继续拆分：

- `Dashboard.vue` → 1689 行 → 拆出 AppSidebar、AppHeader + useAppLayout composable
- `Balance.vue` → 1373 行 → 拆出 BalanceFilters、RechargeModal、RechargeRecordModal、ImportBalanceModal + useBalance composable
- `Invoices.vue` → 1037 行 → 拆出 InvoiceFilters、InvoiceDetailDrawer、GenerateInvoiceModal、DiscountModal、PayModal + useInvoice composable

**目标**：
1. 每个视图文件 ≤ 300 行（模板 + 脚本 + 样式）
2. 每个子组件 ≤ 300 行
3. 子组件通过 defineModel/defineEmits 与父组件通信
4. API 调用和状态管理集中到 composable，便于复用和测试

---

## 二、组件拆分方案

### 2.1 Dashboard.vue 拆分（1689 → ~250 行）

**现状分析**：
- 模板(1-685行)：侧边栏(4-465) + 主内容区(467-685)
- 脚本(687-854)：侧边栏导航、用户信息、折叠状态
- 样式(857-1689)：全部页面样式

**拆出组件**：

| 组件名 | 位置 | 职责 |
|--------|------|------|
| `AppSidebar.vue` | `frontend/src/components/layout/AppSidebar.vue` | 侧边栏整体，包含 logo、导航、用户信息 |
| `AppHeader.vue` | `frontend/src/components/layout/AppHeader.vue` | 顶部栏，包含菜单按钮、标题、面包屑、通知、用户菜单 |
| `useAppLayout` | `frontend/src/composables/useAppLayout.ts` | 侧边栏折叠状态、移动端菜单、用户信息、导航菜单数据 |

**父组件保留**：整体布局容器、router-view

**接口约定**：
```ts
// AppSidebar props/emits
interface Props {
  collapsed?: boolean
  mobileOpen?: boolean
}
interface Emits {
  'toggle-collapse': []
  'close-mobile': []
}

// AppHeader props/emits
interface Props {
  pageTitle?: string
  breadcrumb?: Array<{ label: string; to?: string }>
}
interface Emits {
  'toggle-mobile': []
  'menu-click': [menu: NavItem]
}
```

---

### 2.2 Balance.vue 拆分（1373 → ~280 行）

**现状分析**：
- 模板：筛选(35-190) + 表格(193-246) + 4 个弹窗(292-479)
- 脚本：列表加载、充值、导入、导出、记录弹窗等逻辑
- 样式：独立 section 样式

**拆出组件**：

| 组件名 | 位置 | 职责 |
|--------|------|------|
| `BalanceFilters.vue` | `frontend/src/views/billing/components/BalanceFilters.vue` | 筛选表单（关键词、客户、金额范围）+ 高级筛选 |
| `RechargeModal.vue` | `frontend/src/views/billing/components/RechargeModal.vue` | 充值表单弹窗 |
| `RechargeRecordModal.vue` | `frontend/src/views/billing/components/RechargeRecordModal.vue` | 充值记录弹窗 |
| `ImportBalanceModal.vue` | `frontend/src/views/billing/components/ImportBalanceModal.vue` | 余额导入弹窗 |
| `useBalance` | `frontend/src/composables/useBalance.ts` | 余额列表加载、筛选、排序状态、分页 |

**父组件保留**：表格主体、弹窗状态管理、事件处理

---

### 2.3 Invoices.vue 拆分（1037 → ~280 行）

**现状分析**：
- 模板：筛选(49-88) + 表格(90-188) + 详情抽屉(191-332) + 4 个弹窗(335-405)
- 脚本：列表、详情、提交/确认/付款/取消、折扣、生成、额度计算等
- 样式：弹窗和抽屉样式

**拆出组件**：

| 组件名 | 位置 | 职责 |
|--------|------|------|
| `InvoiceFilters.vue` | `frontend/src/views/billing/components/InvoiceFilters.vue` | 筛选表单（关键词、状态）+ 下拉搜索 |
| `InvoiceDetailDrawer.vue` | `frontend/src/views/billing/components/InvoiceDetailDrawer.vue` | 结算单详情抽屉（使用 InvoiceTimeline） |
| `GenerateInvoiceModal.vue` | `frontend/src/views/billing/components/GenerateInvoiceModal.vue` | 生成结算单表单 |
| `DiscountModal.vue` | `frontend/src/views/billing/components/DiscountModal.vue` | 折扣申请表单 |
| `PayModal.vue` | `frontend/src/views/billing/components/PayModal.vue` | 付款确认表单 |
| `useInvoice` | `frontend/src/composables/useInvoice.ts` | 发票列表加载、筛选、排序、分页 |

**父组件保留**：表格主体、抽屉/弹窗状态管理、业务事件处理

---

## 三、Composable 设计

### 3.1 `useAppLayout.ts`

```ts
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
  const sidebarCollapsed = ref(false)
  const mobileMenuOpen = ref(false)
  const userStore = useUserStore()
  const router = useRouter()

  // 导航菜单数据
  const navMenus = computed<NavItem[]>(() => [
    // 核心功能、运营功能、结算管理、系统管理：根据 userStore.permissions 过滤
  ])

  // 当前页面标题和面包屑
  const pageTitle = computed(() => {
    // 从当前路由 meta 获取
  })

  const breadcrumb = computed(() => {
    // 从当前路由 matched 获取
  })

  function toggleSidebar() { ... }
  function toggleMobileMenu() { ... }

  // 用户信息
  const currentUser = computed(() => userStore.user)
  const userPermissions = computed(() => userStore.permissions)

  return {
    sidebarCollapsed,
    mobileMenuOpen,
    navMenus,
    pageTitle,
    breadcrumb,
    currentUser,
    userPermissions,
    toggleSidebar,
    toggleMobileMenu,
  }
}
```

---

### 3.2 `useBalance.ts`

```ts
export function useBalance() {
  const balances = ref<Balance[]>([])
  const loading = ref(false)
  const pagination = reactive({ current: 1, pageSize: 20, total: 0 })
  const sortState = reactive({ sort_by: 'id', sort_order: 'ascend' })

  const filters = reactive({
    keyword: '',
    customer_id: undefined as number | undefined,
    min_amount: undefined as number | undefined,
    max_amount: undefined as number | undefined,
  })

  async function loadBalances() {
    loading.value = true
    try {
      const res = await getBalances({ ...filters, ...sortState, ...pagination })
      balances.value = res.data.items
      pagination.total = res.data.total
    } finally {
      loading.value = false
    }
  }

  function handleSearch() { ... }
  function handleReset() { ... }

  return {
    balances,
    loading,
    pagination,
    sortState,
    filters,
    loadBalances,
    handleSearch,
    handleReset,
  }
}
```

---

### 3.3 `useInvoice.ts`

```ts
export function useInvoice() {
  const invoices = ref<Invoice[]>([])
  const loading = ref(false)
  const selectedInvoice = ref<Invoice | null>(null)
  const pagination = reactive({ current: 1, pageSize: 20, total: 0 })
  const sortState = reactive({ sort_by: 'id', sort_order: 'ascend' })

  const filters = reactive({
    keyword: '',
    status: undefined as string | undefined,
  })

  async function loadInvoices() { ... }
  async function loadInvoiceDetail(id: number) { ... }

  return {
    invoices,
    loading,
    selectedInvoice,
    pagination,
    sortState,
    filters,
    loadInvoices,
    loadInvoiceDetail,
    // 业务操作通过 emit 暴露给父组件
  }
}
```

---

## 四、文件变更清单

### 4.1 新增文件（14 个）

```
frontend/src/components/layout/
├── AppSidebar.vue
└── AppHeader.vue

frontend/src/composables/
├── useAppLayout.ts
├── useBalance.ts
└── useInvoice.ts

frontend/src/views/billing/components/
├── BalanceFilters.vue
├── RechargeModal.vue
├── RechargeRecordModal.vue
├── ImportBalanceModal.vue
├── InvoiceFilters.vue
├── InvoiceDetailDrawer.vue
├── GenerateInvoiceModal.vue
├── DiscountModal.vue
└── PayModal.vue
```

### 4.2 修改文件（3 个）

```
frontend/src/views/Dashboard.vue        1689行 → ~250行
frontend/src/views/billing/Balance.vue  1373行 → ~280行
frontend/src/views/billing/Invoices.vue 1037行 → ~280行
```

### 4.3 迁移策略

遵循**提取 + 适度优化**：
1. 模板/脚本/样式原样搬运（机械提取，确保行为不变）
2. 重复出现的 API 调用抽到 composable
3. 弹窗内部状态保留在弹窗组件内，避免过度拆分

---

## 五、验证策略

### 5.1 自动化测试

| 验证项 | 命令 | 通过条件 |
|--------|------|---------|
| 类型检查 | `npm run type-check`（或 vue-tsc） | 0 错误 |
| 单元测试 | `npm run test` | 全部 composable 测试通过 |
| E2E 关键流程 | 登录→Dashboard→余额查看→充值 | 核心路径可用 |
| 构建测试 | `npm run build` | 构建成功 |

### 5.2 手动验收清单

- [ ] 侧边栏折叠/展开正常，移动端菜单正常
- [ ] 页面标题和面包屑随路由变化
- [ ] 余额筛选、充值、记录、导入流程正常
- [ ] 发票筛选、详情抽屉、生成、折扣、付款正常
- [ ] 弹窗状态互不干扰，关闭后数据重置正确

### 5.3 组件单元测试（可选，当前测试覆盖率要求 ≥50%）

```ts
// __tests__/useBalance.spec.ts
describe('useBalance', () => {
  it('loads balances on mount', async () => { ... })
  it('handles filter changes', async () => { ... })
  it('handles pagination changes', async () => { ... })
})
```

---

## 六、风险点

| 风险 | 影响 | 缓解 |
|------|------|------|
| 侧边栏组件化后路由跳转失效 | 高 | 保留 router-link，emit 事件留作备用 |
| 弹窗之间状态冲突 | 中 | 弹窗内部独立 reactive，关闭时重置 |
| composable 改动影响其他视图 | 低 | composable 仅被当前页面使用 |
| 样式隔离问题 | 低 | 保持 scoped 或 deep 选择器 |

---

## 七、实施顺序

1. **第一步**：拆 Dashboard（布局组件相对独立，先验证模式）
2. **第二步**：拆 Balance（复用 composable 模式）
3. **第三步**：拆 Invoices（最复杂，积累经验后处理）

每步完成后执行验证策略，通过后进入下一步。

---

## 八、参考

- `frontend/src/views/customers/components/`：已验证的拆分模板
- `frontend/src/components/layout/`：待创建
- `docs/technical_debt/debt.md`：TD-002 原始记录
- `docs/technical_debt/priority-report.md`：优先级依据
