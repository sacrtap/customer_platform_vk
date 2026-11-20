# 前端组件清单

> 本文件列出所有可复用 Vue 组件及其职责。
> 最后更新: 2026-11-20

---

## 通用组件 (`src/components/`)

| 组件 | 大小 | 职责 | 使用场景 |
|------|------|------|----------|
| [ActionButton.vue](../../frontend/src/components/ActionButton.vue) | 1.9K | 操作按钮封装，`label` + 可选 `badge` 角标，点击抛 `click` | `components/layout/AppHeader.vue` 顶部操作入口 |
| [BatchToolbar.vue](../../frontend/src/components/BatchToolbar.vue) | 0.6K | 批量操作工具栏：展示「已选择 N 项」+ 默认插槽放批量动作 | 根目录版本暂无业务引用（客户列表用的是 `views/customers/components/BatchToolbar.vue` 本地副本） |
| [ChartCard.vue](../../frontend/src/components/ChartCard.vue) | 0.8K | 图表卡片容器：标题 + `actions` 插槽 | `views/Home.vue` 经营趋势、异常与待办 |
| [ConsumeLevelProgress.vue](../../frontend/src/components/ConsumeLevelProgress.vue) | 6.2K | 消费等级（C1–C6）分段进度条，组件内按等级算游标位置 | 暂无引用；客户详情画像 Tab 用的是 `components/charts/ConsumeLevelProgress.vue` |
| [CustomerAutoComplete.vue](../../frontend/src/components/CustomerAutoComplete.vue) | 3.0K | 客户远程搜索（300ms 防抖，`v-model` 绑定 customer id） | 结算/充值/定价规则/VR 创建弹窗、结算单详情抽屉、客户新建与编辑、余额白名单（9 处） |
| [CustomerPreviewDrawer.vue](../../frontend/src/components/CustomerPreviewDrawer.vue) | 4.3K | 客户 360 右侧抽屉预览（余额、30 天消耗、健康度） | 暂无引用（客户列表用 `views/customers/components/PreviewDrawer.vue`） |
| [DataTable.vue](../../frontend/src/components/DataTable.vue) | 10.7K | 通用表格：列设置（`storageKey` 存 localStorage）、分页、行选择、横向滚动、插槽透传 | 18 处列表页/表格组件（结算、定价、套餐、客户、角色、用户、系统管理等） |
| [EmptyState.vue](../../frontend/src/components/EmptyState.vue) | 1.4K | 空状态占位（`title` + `description`） | 9 个列表页的无数据提示 |
| [FilterSection.vue](../../frontend/src/components/FilterSection.vue) | 0.4K | 筛选区白底圆角容器（纯插槽） | 仅 `components/__tests__/FilterSection.test.ts` 引用 |
| [KeywordAutoComplete.vue](../../frontend/src/components/KeywordAutoComplete.vue) | 2.3K | 通用关键词联想输入（`v-model` 为字符串，客户关键词 300ms 防抖） | `views/analytics/Forecast.vue` 客户关键词搜索 |
| [PageHeader.vue](../../frontend/src/components/PageHeader.vue) | 1.0K | 页面标题区：`eyebrow` / `title` / `subtitle` + `actions` 插槽 | 27 个页面顶部（首页、结算、客户、分析、系统管理） |
| [QuickFilterTags.vue](../../frontend/src/components/QuickFilterTags.vue) | 1.2K | 快捷筛选标签组，支持计数、再次点击取消选中 | 仅 `components/__tests__/QuickFilterTags.test.ts` 引用 |
| [SkeletonCard.vue](../../frontend/src/components/SkeletonCard.vue) | 1.4K | 加载骨架屏卡片（可配高度） | 客户详情余额 Tab、画像 Tab 的加载占位 |
| [Sparkline.vue](../../frontend/src/components/Sparkline.vue) | 0.8K | 迷你 SVG 折线（默认 50×16） | 暂无引用 |
| [StatCard.vue](../../frontend/src/components/StatCard.vue) | 3.2K | 统计卡片：标题/数值/副标题/配色变体/图标/紧凑布局 | 暂无引用 |
| [SyncStatusBar.vue](../../frontend/src/components/SyncStatusBar.vue) | 1.7K | 同步状态条（ok / warning / syncing + 最近、下次同步时间） | `views/Home.vue`、`views/analytics/Consumption.vue` |
| [TagSelector.vue](../../frontend/src/components/TagSelector.vue) | 2.2K | 标签多选（customer / profile 两类标签，远程拉取） | 暂无引用（客户列表/详情用 `views/customers/detail/TagSelectorDialog.vue`） |

## UI 基础组件 (`src/components/ui/`)

| 组件 | 大小 | 职责 | 使用场景 |
|------|------|------|----------|
| [FilterDropdown.vue](../../frontend/src/components/ui/FilterDropdown.vue) | 5.2K | 下拉筛选触发器：单选/多选、内置「全部」选项、多选需确认应用 | 结算、VR 结算、定价规则、套餐、充值、客户筛选栏（9 处） |

## VR 结算组件 (`src/components/vr/`)

| 组件 | 大小 | 职责 | 使用场景 |
|------|------|------|----------|
| [VrSettlementTimeline.vue](../../frontend/src/components/vr/VrSettlementTimeline.vue) | 6.1K | VR 结算单状态时间线（复用 `components/common/StatusTimeline.vue`，映射 8 个状态节点及驳回/取消） | `views/billing/components/VrSettlementDetailDrawer.vue` |

## 图表组件 (`src/components/charts/`)

| 组件 | 大小 | 职责 | 使用场景 |
|------|------|------|----------|
| [BalanceTrendChart.vue](../../frontend/src/components/charts/BalanceTrendChart.vue) | 3.6K | 余额趋势折线图（ECharts） | 余额管理页面 |
| [ConsumeLevelProgress.vue](../../frontend/src/components/charts/ConsumeLevelProgress.vue) | 4.1K | 消费等级进度图表 | 客户分析页面 |
| [HealthGauge.vue](../../frontend/src/components/charts/HealthGauge.vue) | 2.4K | 健康度仪表盘（仪表盘图） | 健康度分析页面 |
| [UsageDistributionChart.vue](../../frontend/src/components/charts/UsageDistributionChart.vue) | 3.4K | 用量分布图表（饼图/柱状图） | 消耗分析页面 |

## 页面组件 (`src/views/`)

| 页面 | 路由 | 职责 |
|------|------|------|
| [App.vue](../../frontend/src/App.vue) | - | 根组件 |
| [Dashboard.vue](../../frontend/src/views/Dashboard.vue) | `/` | 主布局（侧边栏 + 内容区） |
| [Home.vue](../../frontend/src/views/Home.vue) | `/home` | 首页仪表盘（统计卡片 + 趋势图） |
| [Login.vue](../../frontend/src/views/Login.vue) | `/login` | 登录页 |
| [ResetPassword.vue](../../frontend/src/views/ResetPassword.vue) | `/reset-password` | 密码重置页 |

### 客户管理 (`views/customers/`)
| 页面 | 路由 | 职责 |
|------|------|------|
| [Index.vue](../../frontend/src/views/customers/Index.vue) | `/customers` | 客户列表（多条件筛选、排序、导入/导出） |
| [Detail.vue](../../frontend/src/views/customers/Detail.vue) | `/customers/:id` | 客户详情（基本信息、画像、余额、标签） |

### 结算管理 (`views/billing/`)
| 页面 | 路由 | 职责 |
|------|------|------|
| [Balance.vue](../../frontend/src/views/billing/Balance.vue) | `/billing/balances` | 余额管理（充值、余额趋势） |
| [PricingRules.vue](../../frontend/src/views/billing/PricingRules.vue) | `/billing/pricing-rules` | 定价规则管理 |

### 客户分析 (`views/analytics/`)
| 页面 | 路由 | 职责 |
|------|------|------|
| [Consumption.vue](../../frontend/src/views/analytics/Consumption.vue) | `/analytics/consumption` | 消耗分析（趋势、排行榜、设备分布） |
| [Payment.vue](../../frontend/src/views/analytics/Payment.vue) | `/analytics/payment` | 回款分析（预测 vs 实际） |
| [Health.vue](../../frontend/src/views/analytics/Health.vue) | `/analytics/health` | 健康度分析（仪表盘、预警列表） |
| [Profile.vue](../../frontend/src/views/analytics/Profile.vue) | `/analytics/profile` | 画像分析（行业分布、等级统计） |
| [Forecast.vue](../../frontend/src/views/analytics/Forecast.vue) | `/analytics/forecast` | 预测回款（月度预测明细） |

### 系统管理 (`views/system/`, `views/users/`, `views/roles/`, `views/tags/`)
| 页面 | 路由 | 职责 |
|------|------|------|
| [Users/Index.vue](../../frontend/src/views/users/Index.vue) | `/users` | 用户管理 |
| [Roles/Index.vue](../../frontend/src/views/roles/Index.vue) | `/roles` | 角色权限管理 |
| [Tags/Index.vue](../../frontend/src/views/tags/Index.vue) | `/tags` | 标签管理 |
| [AuditLogs.vue](../../frontend/src/views/system/AuditLogs.vue) | `/system/audit-logs` | 审计日志查看 |
| [SyncLogs.vue](../../frontend/src/views/system/SyncLogs.vue) | `/system/sync-logs` | 同步任务日志查看 |

---

## 组件复用指南

### 新增组件规范
1. 通用组件放在 `src/components/`
2. 图表组件放在 `src/components/charts/`
3. 所有组件使用 TypeScript 类型定义 props 和 emits
4. 组件名称使用 `PascalCase`
5. 组件按需引入，不设 `src/components/index.ts` 统一出口（该文件不存在）

### 导入约定
- 通用组件按文件路径引入：`import DataTable from '@/components/DataTable.vue'`
- 唯一的 barrel 是 `src/components/charts/index.ts`，导出 `BalanceTrendChart`、`HealthGauge`、`UsageDistributionChart`（业务代码目前仍按文件路径直接引入图表组件）
- 子目录组件同样按路径引入：`@/components/ui/FilterDropdown.vue`、`@/components/vr/VrSettlementTimeline.vue`
