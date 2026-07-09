# Frontend Prototype Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前所有前端页面按 `prototype/index.html` 的紧凑型企业数据驾驶舱风格重构，同时保留现有 Vue 3、Arco Design、API、路由和业务逻辑。

**Architecture:** 先建立设计 token、主布局和可复用业务展示组件，再按 P0/P1/P2 页面批次迁移。页面继续负责数据获取和业务行为，通用组件只负责展示结构与交互容器，降低全页面重写风险。

**Tech Stack:** Vue 3、TypeScript、Arco Design Vue、Pinia、Vue Router、ECharts、Vite、CSS variables。

## Global Constraints

- 必须在 `feat/frontend-prototype-redesign` 分支开发，不直接污染 `main`。
- 保留现有 Vue 3 + Arco Design + API + 路由。
- 不替换 Arco Design。
- 不改后端 API、权限模型、结算规则或客户数据结构。
- 不新增 UI 依赖，优先使用 CSS、Arco 和现有 ECharts。
- 每阶段至少运行：`npm run type-check`、`npm run lint`、`npm run build`。
- 新增代码避免 `any` 和隐式不安全数据结构。
- 侧边栏必须支持图标、二级菜单、折叠、localStorage 持久化、折叠态仅显示一级菜单图标。

---

## File Structure

### Create

- `frontend/src/styles/design-tokens.css`：全局颜色、间距、圆角、阴影、状态色 token。
- `frontend/src/styles/dashboard-theme.css`：驾驶舱页面、卡片、筛选、表格、标签、图表容器主题。
- `frontend/src/components/dashboard/AppPageHeader.vue`：统一页面标题、副标题、操作区。
- `frontend/src/components/dashboard/MetricCard.vue`：单个 KPI 指标卡。
- `frontend/src/components/dashboard/MetricGrid.vue`：KPI 指标栅格。
- `frontend/src/components/dashboard/FilterPanel.vue`：统一筛选面板容器。
- `frontend/src/components/dashboard/DataSection.vue`：图表、表格、列表区域容器。
- `frontend/src/components/dashboard/StatusBadge.vue`：统一状态标签。
- `frontend/src/components/dashboard/RiskTag.vue`：风险等级标签。
- `frontend/src/components/dashboard/ActionToolbar.vue`：页面和表格操作工具栏。
- `frontend/src/components/dashboard/CompactTableShell.vue`：紧凑表格外壳。
- `frontend/src/components/dashboard/ChartCard.vue`：图表卡片容器。
- `frontend/src/components/dashboard/index.ts`：统一导出 dashboard 组件。

### Modify

- `frontend/src/main.ts`：引入新增主题 CSS。
- `frontend/src/views/Dashboard.vue`：统一主布局背景、内容容器与响应式。
- `frontend/src/components/layout/AppSidebar.vue`：按 prototype 重构侧边栏。
- `frontend/src/components/layout/AppHeader.vue`：按 prototype 重构顶部栏。
- P0 页面：`Home.vue`、`customers/Index.vue`、`customers/Detail.vue`、`analytics/Consumption.vue`、`billing/Balance.vue`、`billing/Invoices.vue`、`billing/PricingRules.vue`。
- P1 页面：`analytics/Payment.vue`、`analytics/Health.vue`、`analytics/Profile.vue`、`analytics/Forecast.vue`、`tags/Index.vue`。
- P2 页面：`users/Index.vue`、`roles/Index.vue`、`system/SyncLogs.vue`、`system/AuditLogs.vue`、`system/DatabaseManagement.vue`、`Profile.vue`、`Login.vue`、`ResetPassword.vue`。

---

### Task 1: Establish dashboard design tokens

**Files:**
- Create: `frontend/src/styles/design-tokens.css`
- Create: `frontend/src/styles/dashboard-theme.css`
- Modify: `frontend/src/main.ts`

**Interfaces:**
- Consumes: existing app bootstrap in `frontend/src/main.ts`.
- Produces: CSS variables and utility classes used by all later tasks.

- [ ] **Step 1: Create design token stylesheet**

Create `frontend/src/styles/design-tokens.css`:

```css
:root {
  --cop-bg: #f6f8fb;
  --cop-panel: #ffffff;
  --cop-ink: #0f172a;
  --cop-muted: #475569;
  --cop-line: #dbe3ef;
  --cop-primary: #1d4ed8;
  --cop-primary-hover: #1e40af;
  --cop-cyan: #0891b2;
  --cop-success: #059669;
  --cop-warning: #d97706;
  --cop-danger: #dc2626;
  --cop-violet: #7c3aed;
  --cop-radius: 18px;
  --cop-radius-sm: 12px;
  --cop-shadow: 0 14px 40px rgba(15, 23, 42, 0.08);
  --cop-sidebar-width: 252px;
  --cop-sidebar-collapsed-width: 72px;
  --cop-header-height: 64px;
}
```

- [ ] **Step 2: Create dashboard theme stylesheet**

Create `frontend/src/styles/dashboard-theme.css`:

```css
.cop-page {
  min-height: 100%;
  background: var(--cop-bg);
  color: var(--cop-ink);
}

.cop-card {
  background: var(--cop-panel);
  border: 1px solid var(--cop-line);
  border-radius: var(--cop-radius);
  box-shadow: var(--cop-shadow);
}

.cop-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.cop-muted {
  color: var(--cop-muted);
}

.cop-table-shell {
  overflow: auto;
  border: 1px solid var(--cop-line);
  border-radius: 15px;
  background: var(--cop-panel);
}

.cop-status-success { color: var(--cop-success); }
.cop-status-warning { color: var(--cop-warning); }
.cop-status-danger { color: var(--cop-danger); }
```

- [ ] **Step 3: Import styles in app entry**

Modify `frontend/src/main.ts` to include:

```ts
import '@/styles/design-tokens.css'
import '@/styles/dashboard-theme.css'
```

Place these after existing global CSS imports.

- [ ] **Step 4: Verify app compiles styles**

Run:

```bash
cd frontend && npm run type-check
```

Expected: command exits 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/styles/design-tokens.css frontend/src/styles/dashboard-theme.css frontend/src/main.ts
git commit -m "style(frontend): add dashboard design tokens"
```

---

### Task 2: Build reusable dashboard UI components

**Files:**
- Create: `frontend/src/components/dashboard/AppPageHeader.vue`
- Create: `frontend/src/components/dashboard/MetricCard.vue`
- Create: `frontend/src/components/dashboard/MetricGrid.vue`
- Create: `frontend/src/components/dashboard/FilterPanel.vue`
- Create: `frontend/src/components/dashboard/DataSection.vue`
- Create: `frontend/src/components/dashboard/StatusBadge.vue`
- Create: `frontend/src/components/dashboard/RiskTag.vue`
- Create: `frontend/src/components/dashboard/ActionToolbar.vue`
- Create: `frontend/src/components/dashboard/CompactTableShell.vue`
- Create: `frontend/src/components/dashboard/ChartCard.vue`
- Create: `frontend/src/components/dashboard/index.ts`

**Interfaces:**
- Consumes: CSS variables from Task 1.
- Produces: reusable components imported by layout and page migration tasks.

- [ ] **Step 1: Create AppPageHeader**

`frontend/src/components/dashboard/AppPageHeader.vue`:

```vue
<template>
  <header class="app-page-header">
    <div>
      <p v-if="eyebrow" class="app-page-header__eyebrow">{{ eyebrow }}</p>
      <h1 class="app-page-header__title">{{ title }}</h1>
      <p v-if="description" class="app-page-header__description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="app-page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  eyebrow?: string
  description?: string
}>()
</script>

<style scoped>
.app-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.app-page-header__eyebrow {
  margin: 0 0 4px;
  color: var(--cop-primary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.app-page-header__title {
  margin: 0;
  color: var(--cop-ink);
  font-size: 26px;
  font-weight: 850;
  line-height: 1.2;
}
.app-page-header__description {
  margin: 6px 0 0;
  color: var(--cop-muted);
  max-width: 760px;
}
.app-page-header__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
@media (max-width: 768px) {
  .app-page-header { flex-direction: column; }
  .app-page-header__actions { width: 100%; }
}
</style>
```

- [ ] **Step 2: Create MetricCard and MetricGrid**

`MetricCard.vue`:

```vue
<template>
  <article class="metric-card cop-card">
    <div class="metric-card__label">{{ label }}</div>
    <div class="metric-card__value">{{ value }}</div>
    <div v-if="trend" :class="['metric-card__trend', trendTypeClass]">{{ trend }}</div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  value: string | number
  trend?: string
  trendType?: 'up' | 'down' | 'warn' | 'neutral'
}>()

const trendTypeClass = computed(() => `metric-card__trend--${props.trendType || 'neutral'}`)
</script>

<style scoped>
.metric-card { padding: 16px; }
.metric-card__label { color: var(--cop-muted); font-size: 12px; }
.metric-card__value { margin-top: 5px; font-size: 25px; font-weight: 850; }
.metric-card__trend { margin-top: 8px; font-size: 12px; }
.metric-card__trend--up { color: var(--cop-success); }
.metric-card__trend--down { color: var(--cop-danger); }
.metric-card__trend--warn { color: var(--cop-warning); }
.metric-card__trend--neutral { color: var(--cop-muted); }
</style>
```

`MetricGrid.vue`:

```vue
<template>
  <div class="metric-grid">
    <slot />
  </div>
</template>

<style scoped>
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}
</style>
```

- [ ] **Step 3: Create container and badge components**

Create:

```vue
<!-- FilterPanel.vue -->
<template><section class="filter-panel cop-card"><slot /></section></template>
<style scoped>.filter-panel{padding:14px;margin-bottom:14px;}</style>
```

```vue
<!-- DataSection.vue -->
<template>
  <section class="data-section cop-card">
    <div class="cop-section-title"><h2>{{ title }}</h2><slot name="actions" /></div>
    <slot />
  </section>
</template>
<script setup lang="ts">defineProps<{ title: string }>()</script>
<style scoped>.data-section{padding:18px}.data-section h2{margin:0;font-size:17px}</style>
```

```vue
<!-- CompactTableShell.vue -->
<template><div class="compact-table-shell cop-table-shell"><slot /></div></template>
<style scoped>.compact-table-shell :deep(.arco-table-th){background:#f8fafc;color:#334155;font-size:12px}</style>
```

```vue
<!-- ChartCard.vue -->
<template>
  <section class="chart-card cop-card">
    <div class="cop-section-title"><h2>{{ title }}</h2><slot name="meta" /></div>
    <slot />
  </section>
</template>
<script setup lang="ts">defineProps<{ title: string }>()</script>
<style scoped>.chart-card{padding:18px}.chart-card h2{margin:0;font-size:17px}</style>
```

- [ ] **Step 4: Create status components**

`StatusBadge.vue`:

```vue
<template><span :class="['status-badge', `status-badge--${type}`]"><slot>{{ label }}</slot></span></template>
<script setup lang="ts">defineProps<{ label?: string; type: 'success' | 'warning' | 'danger' | 'info' | 'neutral' }>()</script>
<style scoped>
.status-badge{display:inline-flex;border-radius:999px;padding:4px 8px;font-size:12px;font-weight:700}
.status-badge--success{background:#dcfce7;color:#047857}.status-badge--warning{background:#fef3c7;color:#b45309}.status-badge--danger{background:#fee2e2;color:#b91c1c}.status-badge--info{background:#dbeafe;color:#1d4ed8}.status-badge--neutral{background:#f1f5f9;color:#475569}
</style>
```

`RiskTag.vue`:

```vue
<template><StatusBadge :type="mappedType" :label="label" /></template>
<script setup lang="ts">
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'
const props = defineProps<{ level: 'low' | 'medium' | 'high'; label: string }>()
const mappedType = computed(() => props.level === 'high' ? 'danger' : props.level === 'medium' ? 'warning' : 'success')
</script>
```

- [ ] **Step 5: Create ActionToolbar and exports**

`ActionToolbar.vue`:

```vue
<template><div class="action-toolbar"><slot /></div></template>
<style scoped>.action-toolbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:flex-end;gap:8px}</style>
```

`index.ts`:

```ts
export { default as AppPageHeader } from './AppPageHeader.vue'
export { default as MetricCard } from './MetricCard.vue'
export { default as MetricGrid } from './MetricGrid.vue'
export { default as FilterPanel } from './FilterPanel.vue'
export { default as DataSection } from './DataSection.vue'
export { default as StatusBadge } from './StatusBadge.vue'
export { default as RiskTag } from './RiskTag.vue'
export { default as ActionToolbar } from './ActionToolbar.vue'
export { default as CompactTableShell } from './CompactTableShell.vue'
export { default as ChartCard } from './ChartCard.vue'
```

- [ ] **Step 6: Verify components type-check**

```bash
cd frontend && npm run type-check
```

Expected: exits 0.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/dashboard
git commit -m "feat(frontend): add dashboard UI components"
```

---

### Task 3: Redesign application layout and sidebar

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`
- Modify: `frontend/src/components/layout/AppSidebar.vue`
- Modify: `frontend/src/components/layout/AppHeader.vue`

**Interfaces:**
- Consumes: design tokens from Task 1.
- Produces: app shell used by every page migration task.

- [ ] **Step 1: Port prototype sidebar behavior**

In `AppSidebar.vue`, implement these state rules:

```ts
const SIDEBAR_STORAGE_KEY = 'customer-platform-sidebar-collapsed'
const collapsed = ref(localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true')

const setCollapsed = (value: boolean) => {
  collapsed.value = value
  localStorage.setItem(SIDEBAR_STORAGE_KEY, String(value))
}
```

- [ ] **Step 2: Define navigation model**

Use a typed navigation array:

```ts
interface SidebarItem {
  key: string
  label: string
  route: string
  icon: string
  children?: Array<{ key: string; label: string; route: string; hint?: string; icon: string }>
}
```

Represent groups:

- 总览：运营工作台
- 核心功能：客户管理、结算管理
- 运营分析：客户分析
- 系统管理：系统治理

- [ ] **Step 3: Implement collapsed state rules**

CSS requirements:

```css
.app-sidebar {
  width: var(--cop-sidebar-width);
  overflow: visible;
  z-index: 30;
}
.app-sidebar.is-collapsed {
  width: var(--cop-sidebar-collapsed-width);
}
.app-sidebar.is-collapsed .sidebar-subnav,
.app-sidebar.is-collapsed .sidebar-parent[aria-expanded='true'] + .sidebar-subnav {
  display: none !important;
}
.app-sidebar.is-collapsed .sidebar-label,
.app-sidebar.is-collapsed .sidebar-group-title,
.app-sidebar.is-collapsed .sidebar-hint,
.app-sidebar.is-collapsed .sidebar-chev {
  display: none;
}
```

- [ ] **Step 4: Update app header**

`AppHeader.vue` should contain:

- global search placeholder
- sync status pill
- warning count pill
- profile entry

Use existing user/profile actions and do not change auth behavior.

- [ ] **Step 5: Update Dashboard content shell**

`Dashboard.vue` content area should use:

```css
.page-content {
  flex: 1;
  padding: 22px 24px 44px;
  background: var(--cop-bg);
}
```

- [ ] **Step 6: Browser-check layout**

Run dev server if needed:

```bash
cd frontend && npm run dev
```

Expected checks:

- sidebar expanded shows labels and submenus
- sidebar collapsed shows only first-level icons
- collapsed state persists after refresh
- current child route highlights parent group

- [ ] **Step 7: Verify and commit**

```bash
cd frontend && npm run type-check && npm run lint && npm run build
git add frontend/src/views/Dashboard.vue frontend/src/components/layout/AppSidebar.vue frontend/src/components/layout/AppHeader.vue
git commit -m "feat(frontend): redesign application shell"
```

---

### Task 4: Migrate P0 operations and customer pages

**Files:**
- Modify: `frontend/src/views/Home.vue`
- Modify: `frontend/src/views/customers/Index.vue`
- Modify: `frontend/src/views/customers/Detail.vue`

**Interfaces:**
- Consumes: dashboard components from Task 2 and layout from Task 3.
- Produces: first working page examples for later page migrations.

- [ ] **Step 1: Migrate Home.vue**

Use structure:

```vue
<AppPageHeader
  eyebrow="Home"
  title="运营工作台"
  description="首屏回答今天经营是否正常、哪些客户需要处理、同步/结算链路是否有风险。"
/>
<MetricGrid>
  <MetricCard label="活跃客户" :value="totalCustomers" trend="较上月变化" trend-type="up" />
  <MetricCard label="本月消耗" :value="monthlyConsumption" trend="完成率" trend-type="up" />
  <MetricCard label="待回款" :value="pendingPayment" trend="临期提醒" trend-type="warn" />
  <MetricCard label="低余额客户" :value="lowBalanceCount" trend="需跟进" trend-type="down" />
</MetricGrid>
```

Keep existing API calls and computed values. Rename display labels only.

- [ ] **Step 2: Migrate customers/Index.vue**

Wrap existing filters in `FilterPanel`, existing table in `CompactTableShell`, and add KPI cards:

- 客户总数
- 重点客户
- 待完善画像
- 高风险客户

Do not change customer API request parameters.

- [ ] **Step 3: Migrate customers/Detail.vue**

Use `AppPageHeader`, `MetricGrid`, and `DataSection` to organize:

- 基础信息
- 画像信息
- 余额信息
- 结算单
- 用量分析
- 操作记录

Keep existing tabs if that is lower risk; style the tabs inside the new shell.

- [ ] **Step 4: Browser-check P0 customer flow**

Expected flow:

- open customer list
- apply filters
- open customer detail
- return to list
- sidebar active state remains correct

- [ ] **Step 5: Verify and commit**

```bash
cd frontend && npm run type-check && npm run lint && npm run build
git add frontend/src/views/Home.vue frontend/src/views/customers/Index.vue frontend/src/views/customers/Detail.vue
git commit -m "feat(frontend): migrate operations and customer pages"
```

---

### Task 5: Migrate P0 analytics and billing pages

**Files:**
- Modify: `frontend/src/views/analytics/Consumption.vue`
- Modify: `frontend/src/views/billing/Balance.vue`
- Modify: `frontend/src/views/billing/Invoices.vue`
- Modify: `frontend/src/views/billing/PricingRules.vue`

**Interfaces:**
- Consumes: dashboard components and P0 page patterns from Task 4.
- Produces: migrated high-value analytics and billing pages.

- [ ] **Step 1: Migrate Consumption.vue**

Use structure:

- `AppPageHeader`: 消耗分析
- `FilterPanel`: time range, customer, device type, sync mode
- `MetricGrid`: 总消耗、日均消耗、峰值日期、Top10 占比、同步质量
- `ChartCard`: 消耗趋势、设备类型分布
- `CompactTableShell`: Top 客户排行 / 明细表

Keep existing chart initialization and API calls.

- [ ] **Step 2: Migrate Balance.vue**

Use structure:

- `AppPageHeader`: 余额管理
- `MetricGrid`: 账户总余额、低余额客户、赠送余额占比、充值记录数
- `FilterPanel`: existing filters
- `CompactTableShell`: existing balance table

- [ ] **Step 3: Migrate Invoices.vue**

Use structure:

- `AppPageHeader`: 结算单队列
- `MetricGrid`: 本月应收、待确认、生成失败、临期回款
- `FilterPanel`: existing invoice filters
- `CompactTableShell`: existing invoice table
- Preserve invoice drawer and pay modal behavior.

- [ ] **Step 4: Migrate PricingRules.vue**

Use `DataSection` and `CompactTableShell`. Keep current create/edit/delete behavior.

- [ ] **Step 5: Verify and commit**

```bash
cd frontend && npm run type-check && npm run lint && npm run build
git add frontend/src/views/analytics/Consumption.vue frontend/src/views/billing/Balance.vue frontend/src/views/billing/Invoices.vue frontend/src/views/billing/PricingRules.vue
git commit -m "feat(frontend): migrate analytics and billing P0 pages"
```

---

### Task 6: Migrate P1 analysis and tag pages

**Files:**
- Modify: `frontend/src/views/analytics/Payment.vue`
- Modify: `frontend/src/views/analytics/Health.vue`
- Modify: `frontend/src/views/analytics/Profile.vue`
- Modify: `frontend/src/views/analytics/Forecast.vue`
- Modify: `frontend/src/views/tags/Index.vue`

**Interfaces:**
- Consumes: chart and table page patterns from Task 5.
- Produces: unified analytics section.

- [ ] **Step 1: Apply analysis page template**

For each analytics page, use:

```vue
<AppPageHeader />
<FilterPanel />
<MetricGrid />
<ChartCard />
<DataSection />
```

Keep existing ECharts options and API calls.

- [ ] **Step 2: Migrate tags page**

Use:

- `AppPageHeader`: 标签管理
- `DataSection`: 标签列表
- `StatusBadge`: tag status or category indicators
- Existing create/edit/delete modals remain unchanged.

- [ ] **Step 3: Verify and commit**

```bash
cd frontend && npm run type-check && npm run lint && npm run build
git add frontend/src/views/analytics/Payment.vue frontend/src/views/analytics/Health.vue frontend/src/views/analytics/Profile.vue frontend/src/views/analytics/Forecast.vue frontend/src/views/tags/Index.vue
git commit -m "feat(frontend): migrate analysis and tag pages"
```

---

### Task 7: Migrate P2 system, profile, and auth pages

**Files:**
- Modify: `frontend/src/views/users/Index.vue`
- Modify: `frontend/src/views/roles/Index.vue`
- Modify: `frontend/src/views/system/SyncLogs.vue`
- Modify: `frontend/src/views/system/AuditLogs.vue`
- Modify: `frontend/src/views/system/DatabaseManagement.vue`
- Modify: `frontend/src/views/Profile.vue`
- Modify: `frontend/src/views/Login.vue`
- Modify: `frontend/src/views/ResetPassword.vue`

**Interfaces:**
- Consumes: dashboard components and app shell.
- Produces: fully migrated frontend surface.

- [ ] **Step 1: Migrate management pages**

For users, roles, sync logs, audit logs, and database management:

- Use `AppPageHeader`.
- Use `FilterPanel` where filters exist.
- Use `DataSection` and `CompactTableShell` for tables.
- Use `StatusBadge` for states.
- Keep existing modals and permission behavior.

- [ ] **Step 2: Migrate Profile.vue**

Use card-based layout:

- profile summary card
- editable contact info card
- security actions card

Keep avatar upload and password change behavior unchanged.

- [ ] **Step 3: Migrate Login.vue and ResetPassword.vue**

Apply prototype color system and card styling. Do not alter auth API calls, token storage, remember-me behavior, or reset-password token handling.

- [ ] **Step 4: Verify and commit**

```bash
cd frontend && npm run type-check && npm run lint && npm run build
git add frontend/src/views/users/Index.vue frontend/src/views/roles/Index.vue frontend/src/views/system/SyncLogs.vue frontend/src/views/system/AuditLogs.vue frontend/src/views/system/DatabaseManagement.vue frontend/src/views/Profile.vue frontend/src/views/Login.vue frontend/src/views/ResetPassword.vue
git commit -m "feat(frontend): migrate system and auth pages"
```

---

### Task 8: Final visual regression and documentation update

**Files:**
- Modify: `prototype/README.md` if implementation differs from prototype decisions.
- Modify: `docs/superpowers/specs/2026-07-10-frontend-prototype-redesign-design.md` only if approved design changes occurred.

**Interfaces:**
- Consumes: all migrated pages.
- Produces: final verified branch ready for review/PR.

- [ ] **Step 1: Run final verification**

```bash
cd frontend && npm run type-check && npm run lint && npm run build
```

Expected: all commands exit 0.

- [ ] **Step 2: Browser visual checklist**

Check at 1440px, 1024px, 768px, and 375px:

- sidebar expanded and collapsed
- Home
- Customers
- Customer Detail
- Consumption
- Balance
- Invoices
- Users
- Login

Expected:

- no horizontal scroll on mobile except tables
- collapsed sidebar shows only first-level icons
- active parent remains visible when child page selected
- KPI cards, filters, charts, and tables align consistently

- [ ] **Step 3: Update docs if needed**

If implementation changed from design, update the relevant doc section with exact final behavior.

- [ ] **Step 4: Commit final docs**

```bash
git add prototype/README.md docs/superpowers/specs/2026-07-10-frontend-prototype-redesign-design.md
git commit -m "docs(frontend): update redesign implementation notes"
```

If no docs changed, skip this commit.

- [ ] **Step 5: Push branch**

```bash
git push -u origin feat/frontend-prototype-redesign
```

Expected: branch exists on remote and is ready for review.

---

## Self-Review

- Spec coverage: all approved requirements are covered by Tasks 1-8.
- Branch isolation: Task 8 pushes `feat/frontend-prototype-redesign`, and Global Constraints prohibit direct `main` work.
- Prototype visual system: Tasks 1-3 establish tokens, shell, sidebar, and header from prototype.
- All-page migration: Tasks 4-7 cover P0/P1/P2 pages listed in the design spec.
- Verification: every implementation task includes type-check, lint, build; Task 8 adds browser visual checks.
- Placeholder scan: no unresolved placeholders remain.
- Type consistency: component names and file paths are defined before page migration tasks consume them.
