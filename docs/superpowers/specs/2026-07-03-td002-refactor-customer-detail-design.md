# TD-002 Refactor Customer Detail

**Date**: 2026-07-03  
**Author**: brainstorming session  
**Status**: Draft for Review

## Context

Frontend monolith file `frontend/src/views/customers/Detail.vue` spans **2332 lines** (template 624 + script 831 + style 874), violating SRP and causing:

- High merge conflict frequency across 5+ tab panes
- Difficulty locating code by business domain
- Poor testability: cannot unit test individual tabs in isolation

This spec defines a **component-by-tab**拆分 strategy: each `<a-tab-pane>` becomes its own component with isolated styles, while page header, tab container, and shared dialogs remain in the parent.

## Goals

- **Reduce 单文件行数** to ~150 lines in parent `Detail.vue`
- **隔离 tab 逻辑**: each tab independently testable
- **Break "上帝组件"**: no single file governing 5 disparate domains
- **保留现有 API 与 UI 路径**: no backend contract changes
- **零功能回归**: existing E2E tests continue to pass

## Non-Goals

- TD-001 (后端单文件) — deferred; requires touching db transactions, state machine
- TD-004/006/008/009 — not in scope for this ticket
- Index.vue 拆分 — will be addressed in a separate spec if desired

## Architecture

### Component Tree

```
Detail.vue (parent, ~150 lines)
├── <page-header> (保留)
├── <header-actions> (保留)
├── <a-tabs> wrapper (保留: activeKey + @change)
│   ├── CustomerBasicTab     → emits: none (read-only display)
│   ├── CustomerProfileTab   → emits: none (read-only display)
│   ├── CustomerBalanceTab   → emits: none (read-only display)
│   ├── CustomerInvoicesTab  → emits: view-invoice(record)
│   └── CustomerUsageTab     → emits: page-change(payload)
├── EditCustomerDialog       → props: visible / customer
│                             emits: submit(form) / close
└── TagSelectorDialog        → props: visible
                             emits: add(tags) / close
```

### Shared State: `useCustomerDetail` Composable

```ts
// composables/useCustomerDetail.ts
export interface UseCustomerDetailReturn {
  // === 状态 ===
  detail: Ref<Customer | null>
  loading: Ref<boolean>
  activeTab: Ref<string>

  balance: Ref<Balance>
  balanceLoading: Ref<boolean>

  profile: Ref<Profile>
  profileLoading: Ref<boolean>

  invoices: Ref<Invoice[]>

  usageData: Ref<UsageRecord[]>
  usageLoading: Ref<boolean>
  usagePagination: Ref<{ current: number; pageSize: number; total: number }>

  editModalVisible: Ref<boolean>
  tagSelectorVisible: Ref<boolean>

  // === 方法 ===
  loadDetail: () => Promise<void>
  loadBalance: () => Promise<void>
  loadProfile: () => Promise<void>
  loadInvoices: () => Promise<void>
  loadUsage: (page?: number) => Promise<void>
  handleTabChange: (key: string) => void

  // === 对话框方法 ===
  openEdit: () => void
  closeEdit: () => void
  submitEdit: (form: EditForm) => Promise<void>

  openTagSelector: () => void
  closeTagSelector: () => void
  addTags: (tags: Tag[]) => Promise<void>
}
```

### 各 Tab 组件职责

| 组件 | 文件 | 输入 props | 输出 emits | 内部状态 |
|---|---|---|---|---|
| CustomerBasicTab | `views/customers/detail/CustomerBasicTab.vue` | `detail: Customer` | none | none |
| CustomerProfileTab | `views/customers/detail/CustomerProfileTab.vue` | `profile: Profile`, `profileLoading: boolean` | none | 扩展指标列表 |
| CustomerBalanceTab | `views/customers/detail/CustomerBalanceTab.vue` | `balance: Balance`, `balanceLoading: boolean` | none | none |
| CustomerInvoicesTab | `views/customers/detail/CustomerInvoicesTab.vue` | `invoices: Invoice[]` | `view-invoice(record)` | none |
| CustomerUsageTab | `views/customers/detail/CustomerUsageTab.vue` | `usageData: UsageRecord[]`, `loading: boolean`, `pagination: Pagination` | `page-change(page)` | usageDistribution, totalUsageQuantity |

### 对话框组件

| 组件 | 文件 | Props | Emits |
|---|---|---|---|
| EditCustomerDialog | `views/customers/detail/EditCustomerDialog.vue` | `visible: boolean`, `customer: Customer` | `submit(form)` / `close` |
| TagSelectorDialog | `views/customers/detail/TagSelectorDialog.vue` | `visible: boolean` | `add(tags)` / `close` |

## Data Flow

### 1. 初始加载

```
Detail.vue (mounted)
  → useCustomerDetail.composable.loadDetail()
  → activeTab 默认 'basic'
  → 仅 basic 渲染；其他 tab 的 <component> 复用但数据未加载
```

### 2. Tab 切换（懒加载）

```
用户点击 'balance' tab
  → useCustomerDetail.handleTabChange('balance')
  → activeTab = 'balance'
  → v-if 触发 CustomerBalanceTab 挂载
  → composable 检测到 balance 数据缺失 → loadBalance()
  → 渲染 Skeleton / 真实数据

用户再次切回 'basic'
  → 组件复用，数据不重新加载（composable 缓存）
```

### 3. 编辑对话框

```
用户点击 "编辑" 按钮
  → openEdit()
  → editModalVisible = true
  → <EditCustomerDialog> 挂载，显示表单

用户点击 "确定"
  → emit → submitEdit(form)
  → composable 调用 updateCustomer API
  → success → detail = response.data
  → closeEdit()
```

## 样式策略

| 层级 | 位置 |
|---|---|
| 页面级覆盖（a-tabs 全局变量、a-modal 宽度等） | Detail.vue `<style scoped>` |
| 组件私有样式（如 .info-grid、.metrics-grid） | 各 Tab 组件 `<style scoped>` |
| 卡片/按钮/图标细节（如 .balance-card、.metric-card） | 各 Tab 组件 scoped |

原则：**组件私有样式随组件迁移**，父组件仅保留布局和全局覆盖类。

## Error Handling

| 场景 | 处理 | 实现位置 |
|---|---|---|
| loadDetail 失败 | `$notification.error` + 重试按钮 | composable |
| loadBalance 等 tab 加载失败 | tab 内 error 状态 + 重试入口 | tab 组件 template |
| submitEdit 失败 | 表单下方展示错误 | EditCustomerDialog |
| 图表加载失败 | fallback 空状态 | 各 Chart 组件 |

## Testing Strategy

| 测试类型 | 文件 | 重点 |
|---|---|---|
| 单元 | `composables/__tests__/useCustomerDetail.spec.ts` | 懒加载逻辑、对话框状态、tab 切换 |
| 单元 | `customers/detail/__tests__/CustomerBasicTab.spec.ts` | props 渲染、空值 fallback |
| 单元 | `customers/detail/__tests__/CustomerUsageTab.spec.ts` | 分页事件 emit |
| 单元 | `customers/detail/__tests__/EditCustomerDialog.spec.ts` | 表单校验、emit |
| E2E | 保持现有 `customer-detail.spec.ts` 通过（关键路径） | 无需新增用例 |

## Migration Plan

### 第一步：抽取 composable + dialogs（不动 tab 结构）
1. 新建 `composables/useCustomerDetail.ts` 并迁移所有状态/方法
2. Detail.vue 改为引用 composable，删除重复逻辑
3. 抽离 `EditCustomerDialog.vue` 和 `TagSelectorDialog.vue`
4. 验证：npm run dev 正常，E2E 通过

### 第二步：逐个抽 tab 组件（独立可回滚）
1. **CustomerBasicTab**（行数最少 ~154 行模板）— 练手
2. **CustomerBalanceTab**（数据卡片 + 趋势图）
3. **CustomerProfileTab**（指标网格 + 图表）
4. **CustomerInvoicesTab**（纯 a-table）
5. **CustomerUsageTab**（分布图 + 表格 + 分页）

每完成一个 tab → 单 PR → Code Review → 合并。

### 第三步：清理父组件
- 删除 Detail.vue 中已迁移的 template/script 代码
- 确认 final Detail.vue ≤ 150 行
- 最终 E2E 全量通过

## Acceptance Criteria

- [ ] `frontend/src/views/customers/Detail.vue` ≤ 150 行（不含空行和注释）
- [ ] 5 个 tab 组件独立存在且可独立测试
- [ ] 现有 E2E `customer-detail.spec.ts` 全量通过
- [ ] 新增 composable 单元测试覆盖率 ≥ 60%
- [ ] 样式公私分离：组件私有样式 scoped，父组件仅保留页面级覆盖
- [ ] 浏览器中视觉表现与改造前一致（回归验证）

## Risks & Mitigations

| 风险 | 减轻措施 |
|---|---|
| Tab 间隐式依赖导致数据未初始化 | composable 在 tab change 时检查空值按需加载 |
| 样式迁移遗漏导致视觉回归 | 每个 tab PR 执行截图对比 + E2E |
| 过度重构影响交付节奏 | 分多 PR 小步跑，每 PR ≤ 400 行变更 |
| 延迟加载逻辑破坏现有交互 | 保留 shouldRenderChart 机制 |
