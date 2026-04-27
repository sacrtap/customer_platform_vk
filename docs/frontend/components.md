# 前端组件清单

> 本文件列出所有可复用 Vue 组件及其职责。
> 最后更新: 2026-04-27

---

## 通用组件 (`src/components/`)

| 组件 | 大小 | 职责 | 使用场景 |
|------|------|------|----------|
| [ActionButton.vue](../../frontend/src/components/ActionButton.vue) | 2.0K | 统一操作按钮，支持权限控制和加载状态 | 表格操作列、表单提交按钮 |
| [ConsumeLevelProgress.vue](../../frontend/src/components/ConsumeLevelProgress.vue) | 4.8K | 消费等级进度条可视化 | 客户列表、客户详情页 |
| [CustomerAutoComplete.vue](../../frontend/src/components/CustomerAutoComplete.vue) | 2.7K | 客户输入检索组件（AutoComplete），支持远程搜索、300ms 防抖 | 余额管理、计费规则、消耗分析、回款分析、预测回款页面的客户筛选 |
| [EmptyState.vue](../../frontend/src/components/EmptyState.vue) | 1.4K | 空状态占位组件 | 数据列表为空时展示 |
| [SkeletonCard.vue](../../frontend/src/components/SkeletonCard.vue) | 1.4K | 加载骨架屏卡片 | 数据加载中的占位 |
| [StatCard.vue](../../frontend/src/components/StatCard.vue) | 3.5K | 统计卡片组件，支持图标、标题、数值、趋势 | 仪表盘、各分析页面顶部统计 |
| [TagSelector.vue](../../frontend/src/components/TagSelector.vue) | 2.2K | 标签选择器，支持搜索和分类 | 客户打标、高级筛选 |

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
5. 可复用组件应在 `components/index.ts` 中统一导出

### 当前导出配置
`src/components/index.ts` 导出：
- `ActionButton`
- `CustomerAutoComplete`
- `EmptyState`
- `SkeletonCard`
- `StatCard`
- `TagSelector`
- 图表组件：`BalanceTrendChart`, `HealthGauge`, `UsageDistributionChart`