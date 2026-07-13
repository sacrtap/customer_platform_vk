# 原型驱动全栈重构设计规格

> **创建日期**: 2026-07-14
> **状态**: 已确认，待编写实现计划
> **范围**: 前端 22+ 页面 + 后端 API，视觉统一 + 交互增强

---

## 1. 背景与目标

### 1.1 项目现状

客户运营中台已有一套完整的原型设计体系（`prototype/design.md` 1829 行设计规范 + 24 个独立 HTML 原型页面 + `prototype/index.html` 单文件原型）和已存在的重构优化计划（`docs/superpowers/plans/2026-07-13-prototype-refactoring-optimization-plan.md`）。

前端基于 Vue 3 + Arco Design + TypeScript 已实现全部页面路由和基础功能，设计令牌（`global.css`）和 Arco 主题覆盖（`arco-theme.css`）已初步对齐原型。但存在以下问题：

1. **样式冲突**：`td002-component-styles.css`（153 行）使用旧色彩体系（`#0369a1` / `#2f3645` / `#8f959e`），与原型的 `#1D4ED8` / `#0F172A` / `#475569` 冲突
2. **页面状态不一**：部分页面已开始对齐原型风格，部分仍使用旧 td002 样式
3. **功能差距**：重构优化计划中的交互增强（KPI 下钻、快速预览抽屉、图表联动等）尚未实现

### 1.2 目标

按照原型设计方案重构前端全部 22+ 页面及对应后端 API，实现：
- **视觉统一**：消除旧 td002 样式，所有页面对齐原型的色彩、布局、组件规范
- **交互增强**：实现重构优化计划中定义的全部交互功能
- **前后端同步**：前端新功能需要的后端 API 在同一阶段内完成

### 1.3 约束

- 不破坏现有功能：每阶段完成后应用可用，不引入回归
- 原型为唯一视觉基准：`prototype/design.md` + 24 个独立 HTML 页面
- 后端硬规则：所有修改操作在 `async with db_session.begin():` 块内，API 端点添加 `@auth_required`，余额扣款使用行级锁（`FOR UPDATE`），Python 3.12.x
- 测试覆盖率：CI 要求 ≥ 50%（`--cov-fail-under=50`）
- 文件修改前必须先读取

---

## 2. 架构总览与分阶段路线图

### 2.1 分阶段策略

```
Phase 0: 基础层统一（全局基础，无页面级改动）
    ↓
Phase 1: P0 核心页面（Home / 客户列表 / 客户详情 / 消耗分析 / 结算管理×3）
    ↓
Phase 2: P1 分析页面（画像分析 / 健康度 / 回款分析 / 预测回款）
    ↓
Phase 3: P2 系统页面（用户 / 角色 / 标签 / 同步日志 / 审计日志 / 行业类型 / 数据清空）
    ↓
Phase 4: 认证/个人域（Login / ResetPassword / Profile）
```

### 2.2 每阶段内部流程

```
1. 前端视觉统一 → 对齐原型色彩/布局/组件规范
2. 前端交互增强 → 实现重构优化计划中的交互功能
3. 后端 API 调整 → 新增/修改端点支持新功能
4. 测试验证 → E2E + 视觉回归 + 单元测试
```

### 2.3 页面分组与优先级

| 阶段 | 页面 | 优先级理由 |
|------|------|-----------|
| Phase 0 | 全局基础层（令牌/样式/组件/布局） | 基础不稳定后续都会出问题 |
| Phase 1 | Home、客户列表、客户详情、消耗分析、余额/计费/结算单 | 最高频使用 + 最高风险路径 |
| Phase 2 | 画像分析、健康度、回款分析、预测回款 | 次高频，依赖 Phase 1 基础组件 |
| Phase 3 | 用户、角色、标签、同步/审计日志、行业类型、数据清空 | 低频但必要，系统治理 |
| Phase 4 | Login、ResetPassword、Profile | 独立性强，最后收尾 |

---

## 3. Phase 0 — 基础层统一

### 3.1 设计令牌验证与补全

**现状**：`frontend/src/styles/global.css` 已有原型令牌。

**工作内容**：
- 对比 `prototype/design.md` 第 2 节令牌表，逐项核对 `:root` 变量
- 补充缺失令牌（如有）
- 验证 `arco-theme.css` 中硬编码 hex 值与 design.md 一致（`#1D4ED8` / `#2563EB` / `#1E40AF`）
- 删除 backward-compat 别名（`--primary-1` / `--neutral-*` 等），确认无页面引用后清理

**涉及文件**：
- `frontend/src/styles/global.css`
- `frontend/src/styles/arco-theme.css`

### 3.2 td002 旧样式处理

**现状**：`frontend/src/styles/td002-component-styles.css`（153 行）使用旧色彩体系。

**工作内容**：
- 将整个文件内容用注释包裹（`/* td002 旧样式，迁移中 */`）
- 从 `main.ts` 或 `vite.config.ts` 中移除对该文件的导入
- 逐页迁移后确认无引用，Phase 4 结束时删除文件

**涉及文件**：
- `frontend/src/styles/td002-component-styles.css`
- `frontend/src/main.ts`

### 3.3 全局工具类对齐

**需补充的工具类**（来自 `design.md`）：

| 工具类 | 来源 | 用途 |
|--------|------|------|
| `.mini` | design.md 3.12 | KPI 条紧凑卡片内边距 `11px` |
| `.ia` | design.md 3.26 | 信息架构 5 列网格 |
| `.prototype-note` | design.md 3.27 | 原型覆盖框（3 列） |
| `.chart-placeholder` | design.md 3.21.5 | 图表占位符 |

**涉及文件**：
- `frontend/src/styles/global.css`

### 3.4 布局组件对齐原型

**AppSidebar.vue**：
- 对齐项：导航组圆角 `16px` + 背景色 `rgba(15,23,42,.20)`、折叠按钮样式（`design.md` 6.2.6）、品牌标识 `.mark` 尺寸/渐变/阴影（`design.md` 3.8）
- 验证折叠态行为：二级菜单强制隐藏、手风琴交互
- 验证侧边栏滚动：`.nav` 的 `overflow-y: auto` + `overflow-x: visible`

**AppHeader.vue**：
- 对齐项：毛玻璃效果 `backdrop-filter: blur(14px)` + 背景 `rgba(246,248,251,.86)`、搜索框样式（`design.md` 3.5）、状态药丸标签 `.pill`

**Dashboard.vue**：
- 验证 Shell 布局：`grid-template-columns: 252px 1fr` → `72px 1fr`，切换动画 `0.25s ease`

**涉及文件**：
- `frontend/src/components/layout/AppSidebar.vue`
- `frontend/src/components/layout/AppHeader.vue`
- `frontend/src/views/Dashboard.vue`

### 3.5 通用页面组件创建/规范化

从原型 `design.md` 第 4 节提取的页面级通用组件：

| 组件名 | 文件路径 | 来源 | 说明 |
|--------|----------|------|------|
| `PageHeader` | `components/PageHeader.vue` | design.md 4.1 | 页面标题 + 副标题 + 操作按钮组 |
| `FilterSection` | `components/FilterSection.vue` | design.md 4.2 | 白色卡片筛选区，统一 `a-form layout="inline"` |
| `TableSection` | `components/TableSection.vue` | design.md 4.3 | 表格容器，表头/行 hover 样式 |
| `ChartCard` | `components/ChartCard.vue` | design.md 4.4 | 图表卡片，标题 + 内容区 |
| `BatchToolbar` | `components/BatchToolbar.vue` | design.md 4.6 | 批量操作工具栏 |
| `QuickFilterTags` | `components/QuickFilterTags.vue` | 重构计划 | 快速筛选标签（如"待确认(8)"） |

现有组件对齐：
- `StatCard.vue` — 对齐 design.md 3.12 KPI 卡片规范
- `EmptyState.vue` — 对齐 design.md 3.15 空状态规范
- `SkeletonCard.vue` — 对齐 design.md 4.11 骨架屏规范
- `ActionButton.vue` — 对齐 design.md 3.16 操作按钮规范

**涉及文件**：
- 新建：`frontend/src/components/PageHeader.vue`、`FilterSection.vue`、`TableSection.vue`、`ChartCard.vue`、`BatchToolbar.vue`、`QuickFilterTags.vue`
- 修改：`frontend/src/components/StatCard.vue`、`EmptyState.vue`、`SkeletonCard.vue`、`ActionButton.vue`

### 3.6 Phase 0 验证标准

- 前端开发服务器正常启动，无控制台错误
- 侧边栏折叠/展开、手风琴交互、localStorage 持久化正常
- 顶栏毛玻璃效果、搜索框 `/` 快捷键正常
- 所有通用组件可独立渲染，样式与原型一致
- `td002-component-styles.css` 已注释，无页面样式断裂

---

## 4. Phase 1 — P0 核心页面全栈重构

### 4.1 运营工作台（Home.vue）

**原型参考**：`prototype/home.html` + `design.md` 10.2

**视觉重构**：
- 使用 `PageHeader` 组件替换当前 `.headline`
- KPI 条从 `.grid-4` 改为 `.kpi-strip`（6 列），对齐原型 6 指标布局
- Hero 区验证 `.hero`（1.35fr + .65fr）布局
- 待办列表样式对齐原型 `.event` 时间线样式

**交互增强**（重构计划 3.2）：

| 功能 | 前端 | 后端 |
|------|------|------|
| KPI 卡片点击下钻 | `@click` 路由跳转 + 筛选参数 | 无 |
| 快捷操作面板 | 4 宫格按钮卡片 | 无 |
| 异常排序开关 | Toggle 切换 + 列表重排 | 无 |
| 实时同步状态条 | 脉冲动画指示条 | `GET /api/sync/status`（新增） |
| 趋势图指标切换 | Tab 切换图表数据 | `GET /api/analytics/trend?metric=xxx`（扩展） |
| 行内下拉操作 | 行内下拉菜单 | 无 |

**后端变更**：
- `backend/app/routes/analytics.py` — `GET /api/analytics/trend` 增加 `metric` 参数（consumption/payment/customer_count/health）
- `backend/app/routes/sync_tasks.py` — 新增 `GET /api/sync/status` 端点返回同步状态

**涉及文件**：
- `frontend/src/views/Home.vue`
- `backend/app/routes/analytics.py`
- `backend/app/routes/sync_tasks.py`

### 4.2 客户列表（customers/Index.vue）

**原型参考**：`prototype/customers.html` + `design.md` 10.3

**视觉重构**：
- 使用 `PageHeader` + `FilterSection` + `TableSection` 组件
- KPI 卡片对齐 `.mini` 紧凑样式
- `CustomerTable.vue` — 客户 Logo 样式（`.customer .logo`）、进度条（design.md 3.20）、状态标签对齐
- 批量操作工具栏使用 `BatchToolbar` 组件

**交互增强**（重构计划 3.3）：

| 功能 | 前端 | 后端 |
|------|------|------|
| 保存筛选视图 | 弹窗保存 + 下拉切换 | `POST /api/customers/saved-views`（新增） |
| 列自定义 | 列设置面板 + localStorage | 无 |
| 异常优先排序 | Toggle 开关 + 排序 | `GET /api/customers?sort=risk`（扩展） |
| 卡片/表格视图切换 | 视图切换按钮 | 无 |
| 快速预览抽屉 | hover Drawer 滑出 | `GET /api/customers/:id/summary`（新增） |
| KPI 联动筛选 | KPI 点击筛选表格 | 无 |
| 批量操作增强 | 批量编辑/分配/导出/设标签 | `POST /api/customers/batch`（扩展） |

**后端变更**：
- `backend/app/routes/customers.py` — 新增 `GET /api/customers/:id/summary`（客户 360 预览数据）
- `backend/app/routes/customers.py` — 新增 `POST /api/customers/saved-views` + `GET /api/customers/saved-views`
- `backend/app/routes/customers.py` — 扩展列表接口支持 `sort=risk` 参数

**涉及文件**：
- `frontend/src/views/customers/Index.vue`
- `frontend/src/views/customers/components/CustomerTable.vue`
- `frontend/src/views/customers/components/CustomerFilters.vue`
- `backend/app/routes/customers.py`

### 4.3 客户详情（customers/Detail.vue）

**原型参考**：`prototype/detail.html` + `design.md` 10.3

**视觉重构**：
- Tab 导航对齐原型药丸标签样式（design.md 4.5）
- 6 个 Tab 布局：基础信息 / 画像 / 余额 / 消耗 / 结算 / 操作记录
- KPI 卡片对齐 `.grid-4` + `.mini` 样式
- 画像卡片对齐 `.callout` / Compact List 样式（design.md 3.25）
- 热力图对齐 design.md 3.22 样式
- 时间线对齐 design.md 3.23 样式

**交互增强**（重构计划 3.4）：

| 功能 | 前端 | 后端 |
|------|------|------|
| Tab 分区导航 | 6 个药丸 Tab + URL hash 同步 | 无 |
| 余额耗尽预测 | 预测天数 + mini chart | `GET /api/customers/:id/balance-forecast`（新增） |
| 健康度仪表盘 | HealthGauge 组件 | 已有 `GET /api/customers/:id/health` |
| 消耗趋势 mini 图 | 30 天折线 mini chart | 已有 `GET /api/customers/:id/usage` |
| 快捷操作栏 | 充值/结算/编辑/提醒按钮 | 无 |
| 关联客户推荐 | 同行业客户卡片 | `GET /api/customers/:id/related`（新增） |
| 操作记录筛选 | Tab 筛选时间线 | 已有 `GET /api/customers/:id/timeline` |

**后端变更**：
- `backend/app/routes/customers.py` — 新增 `GET /api/customers/:id/balance-forecast`（余额耗尽预测）
- `backend/app/routes/customers.py` — 新增 `GET /api/customers/:id/related`（关联客户推荐）

**涉及文件**：
- `frontend/src/views/customers/Detail.vue`
- `frontend/src/views/customers/detail/CustomerBasicTab.vue`
- `frontend/src/views/customers/detail/CustomerProfileTab.vue`
- `frontend/src/views/customers/detail/CustomerBalanceTab.vue`
- `frontend/src/views/customers/detail/CustomerUsageTab.vue`
- `frontend/src/views/customers/detail/CustomerInvoicesTab.vue`
- `backend/app/routes/customers.py`

### 4.4 消耗分析（analytics/Consumption.vue）

**原型参考**：`prototype/consumption.html` + `design.md` 10.5

**视觉重构**：
- `FilterSection` + `.kpi-strip`（6 列）+ `ChartCard` + 表格
- SVG 原型图表替换为 ECharts 组件
- 环形图对齐 design.md 3.21.3 样式
- Top 排行表格对齐 TableSection 样式

**交互增强**（重构计划 3.5）：

| 功能 | 前端 | 后端 |
|------|------|------|
| 同步质量提示 | 同步状态提示条 + 手动同步按钮 | 复用 `/api/sync/status` |
| 图表解释 tooltip | `?` 图标 + hover 说明 | 无 |
| 点击联动明细 | 环形图扇区点击筛选表格 | 无 |
| 同比/环比对比 | 双线模式开关 | `GET /api/analytics/consumption?compare=period`（扩展） |
| 异常检测高亮 | 峰值/谷值红色标注 | 后端返回异常标记 |
| 导出报告 | 导出 PDF/Excel | `GET /api/analytics/consumption/export`（新增） |
| Top 客户深度钻取 | 行点击跳转客户详情 | 无 |

**后端变更**：
- `backend/app/routes/analytics.py` — 扩展消耗分析接口支持 `compare` 参数
- `backend/app/routes/analytics.py` — 新增 `GET /api/analytics/consumption/export`
- `backend/app/routes/analytics.py` — 返回数据中包含异常标记字段

**涉及文件**：
- `frontend/src/views/analytics/Consumption.vue`
- `backend/app/routes/analytics.py`

### 4.5 结算管理（billing/Balance.vue + PricingRules.vue + Invoices.vue）

**原型参考**：`prototype/balance.html` + `prototype/pricing.html` + `prototype/invoices.html` + `design.md` 10.4

**视觉重构**：
- 3 个页面统一使用 `PageHeader` + `FilterSection` + `TableSection`
- 结算单状态标签使用 `InvoiceStatusBadge`（已有，验证对齐 design.md 4.9）
- 结算单时间线使用 `InvoiceTimeline`（已有，验证对齐 design.md 4.12）
- 分页组件对齐 design.md 3.18 样式

**余额管理交互增强**（重构计划 3.7）：

| 功能 | 前端 | 后端 |
|------|------|------|
| 余额趋势 mini chart | Sparkline 迷你折线 | `GET /api/billing/balances/:id/trend`（新增） |
| 余额预警阈值配置 | 预警设置弹窗 | `POST /api/billing/balance-thresholds`（新增） |
| 批量充值 | 批量充值弹窗 | `POST /api/billing/balances/batch-recharge`（新增） |
| 余额耗尽预测列 | "5 天"/"安全" 标签 | 复用 balance-forecast |
| 低余额自动高亮 | 行背景高亮 | 无 |
| 充值记录抽屉 | Drawer 时间线 | 已有 `GET /api/billing/recharge-records` |

**计费规则交互增强**（重构计划 3.8）：

| 功能 | 前端 | 后端 |
|------|------|------|
| 规则生效预览 | 实时计算费用 | `POST /api/billing/pricing-rules/preview`（新增） |
| 冲突检测可视化 | 冲突标记列 | `GET /api/billing/pricing-rules?check_conflicts=true`（扩展） |
| 定价对比视图 | 阶梯对比图弹窗 | 无 |
| 规则版本历史 | Drawer 变更时间线 | `GET /api/billing/pricing-rules/:id/history`（新增） |
| 批量导入 | Excel 导入 | `POST /api/billing/pricing-rules/import`（新增） |
| 即将到期高亮 | 琥珀色背景 + 标签 | 后端返回 `expires_at` 字段 |

**结算单交互增强**（重构计划 3.9）：

| 功能 | 前端 | 后端 |
|------|------|------|
| 生命周期可视化 | 状态流程图 | 无 |
| 批量操作 | 批量确认/导出 | `POST /api/billing/invoices/batch`（扩展） |
| 逾期自动高亮 | 红色背景 + 倒计时 | 后端返回 `overdue_days` 字段 |
| 金额汇总页脚 | 汇总行 | 后端返回 `summary` 字段 |
| 快速筛选标签 | `QuickFilterTags` 组件 | 无 |

**后端变更**：
- `backend/app/routes/billing.py` 或 `backend/app/routes/billing/` — 上述新增端点
- 所有新增端点添加 `@auth_required` 装饰器
- 余额相关修改操作使用 `FOR UPDATE` 行级锁

**涉及文件**：
- `frontend/src/views/billing/Balance.vue`
- `frontend/src/views/billing/PricingRules.vue`
- `frontend/src/views/billing/Invoices.vue`
- `frontend/src/views/billing/components/`（各子组件）
- `backend/app/routes/billing.py` 或 `backend/app/routes/billing/`

### 4.6 Phase 1 验证标准

- 所有 P0 页面视觉与原型一致（色彩、布局、组件样式）
- 交互功能可用：KPI 下钻、保存筛选、Tab 导航、图表联动等
- 后端新增 API 端点均添加 `@auth_required` 装饰器
- E2E 测试覆盖新增交互流程
- 无回归：现有功能全部正常

---

## 5. Phase 2 — P1 分析页面

### 5.1 画像分析（analytics/Profile.vue）

**原型参考**：`prototype/profile-analysis.html` + `design.md` 10.5

**视觉重构**：
- `PageHeader` + `.grid-4` KPI + `ChartCard` × 4（2×2 图表网格）
- 图表组件统一使用 ECharts，颜色序列 `[#1D4ED8, #0891B2, #059669, #D97706, #DC2626, #7C3AED]`

**交互增强**（重构计划 3.12）：

| 功能 | 前端 | 后端 |
|------|------|------|
| 行业分布饼图 | 点击扇区联动客户列表 | 无 |
| 规模等级柱图 | 柱子可点击筛选 | 无 |
| 消费等级环形图 | 中心显示总数 | 无 |
| 房产占比环形图 | 双色环形图 | 后端返回 `is_real_estate` 统计 |
| 交叉维度热力图 | 行业×规模热力图矩阵 | `GET /api/analytics/profile/cross-dimension`（新增） |
| 标签关联分析 | Top 10 标签排行 | `GET /api/analytics/profile/tag-usage`（新增） |
| 画像完整率 KPI | 完整率 < 80% 标橙色 | 后端返回 `profile_completeness` 字段 |

**后端变更**：
- `backend/app/routes/analytics.py` — 新增 `GET /api/analytics/profile/cross-dimension`
- `backend/app/routes/analytics.py` — 新增 `GET /api/analytics/profile/tag-usage`

### 5.2 健康度分析（analytics/Health.vue）

**原型参考**：`prototype/health.html` + `design.md` 10.5

**视觉重构**：
- `PageHeader` + `.grid-4` KPI + 双表格布局
- `HealthGauge` 组件用于客户健康度评分展示

**交互增强**（重构计划 3.11）：

| 功能 | 前端 | 后端 |
|------|------|------|
| 健康度分布环形图 | 三色环形图（健康/预警/高风险） | 后端返回分布数据 |
| 风险趋势折线图 | 30 天风险客户数变化 | `GET /api/analytics/health/risk-trend`（新增） |
| 一键跟进按钮 | 弹窗选择跟进方式 | `POST /api/customers/:id/follow-up`（新增） |
| 天数选择器 | 30/60/90/180 天切换 | `GET /api/analytics/health?days=30`（扩展） |
| 健康度评分卡片 | 网格卡片视图 | 无 |
| 导出预警清单 | 导出 Excel | `GET /api/analytics/health/export`（新增） |

**后端变更**：
- `backend/app/routes/analytics.py` — 新增 `GET /api/analytics/health/risk-trend`、`GET /api/analytics/health/export`
- `backend/app/routes/customers.py` — 新增 `POST /api/customers/:id/follow-up`

### 5.3 回款分析（analytics/Payment.vue）

**原型参考**：`prototype/payment.html` + `design.md` 10.5

**视觉重构**：
- `PageHeader` + `.grid-4` KPI + `ChartCard` × 3
- 从占位符替换为真实 ECharts 图表

**交互增强**（重构计划 3.10）：

| 功能 | 前端 | 后端 |
|------|------|------|
| 预测 vs 实际对比柱图 | 双色柱图 | `GET /api/analytics/payment/forecast-vs-actual`（新增） |
| 结算单状态饼图 | 点击扇区联动 | 无 |
| 回款趋势双 Y 轴 | 金额(柱) + 回款率(线) | `GET /api/analytics/payment/trend`（扩展） |
| 回款周期 KPI | 平均回款天数 + 趋势 | 后端返回 `avg_payment_days` |
| 客户回款排行 | Top 客户排行表 | `GET /api/analytics/payment/top-customers`（新增） |
| 导出报告 | 导出按钮 | `GET /api/analytics/payment/export`（新增） |

**后端变更**：
- `backend/app/routes/analytics.py` — 新增上述端点

### 5.4 预测回款（analytics/Forecast.vue）

**原型参考**：`prototype/forecast.html` + `design.md` 10.5

**视觉重构**：
- `FilterSection` + `.grid-4` KPI + `ChartCard` 趋势图 + `TableSection` 明细表

**交互增强**（重构计划 3.13）：

| 功能 | 前端 | 后端 |
|------|------|------|
| 置信区间阴影 | 浅色阴影区域 | 后端返回 `confidence_interval` |
| 风险评估标签 | 低/中/高 三色标签 | 后端返回 `risk_level` |
| 预测准确度 KPI | 近 3 月偏差均值 | 后端返回 `forecast_accuracy` |
| 月度对比柱图 | 本月 vs 上月 vs 去年同期 | `GET /api/analytics/forecast/monthly-compare`（新增） |
| 客户深度钻取 | 行点击跳转客户详情 | 无 |
| 高风险客户高亮 | 红色背景 + 风险标签 | 无 |

**后端变更**：
- `backend/app/routes/analytics.py` — 新增 `GET /api/analytics/forecast/monthly-compare`，扩展返回字段

### 5.5 Phase 2 验证标准

- 所有 P1 页面视觉与原型一致
- 分析页面图表组件正常渲染，交互联动有效
- 后端新增 API 均添加 `@auth_required` 装饰器
- E2E + 单元测试覆盖新增功能

---

## 6. Phase 3 — P2 系统页面

### 6.1 用户管理（users/Index.vue）

**原型参考**：`prototype/users.html`

**视觉重构**：`PageHeader` + `FilterSection`（角色筛选）+ `TableSection`

**交互增强**（重构计划 3.14）：
- 角色筛选下拉
- 活跃度 mini 热力图（7 格）
- 批量启用/禁用/分配角色
- 最后登录时间排序
- 卡片/表格视图切换
- 在线状态指示（绿/灰圆点）

**后端变更**：
- `backend/app/routes/users.py` — 扩展列表接口返回 `last_active_days`、`is_online` 字段

### 6.2 角色管理（roles/Index.vue）

**原型参考**：`prototype/roles.html`

**视觉重构**：`PageHeader` + `FilterSection` + `TableSection`

**交互增强**（重构计划 3.15）：
- 权限矩阵可视化弹窗（行=功能模块，列=操作）
- 用户数列可点击弹窗展示该角色下所有用户
- 角色对比按钮
- 权限变更审计预览
- 系统内置角色锁定标记

**后端变更**：
- `backend/app/routes/roles.py` — 新增 `GET /api/roles/:id/users`、`GET /api/roles/compare?id1=&id2=`

### 6.3 标签管理（tags/Index.vue）

**原型参考**：`prototype/tags.html`

**视觉重构**：`PageHeader` + Tab 分组 + 标签云 + `BatchToolbar`

**交互增强**（重构计划 3.16）：
- 使用次数和客户数显示
- 分类 Tab（全部/业务标签/风险标签/自定义）
- 颜色自定义（6 色选择器）
- 标签合并功能
- 批量删除
- 搜索框模糊匹配

**后端变更**：
- `backend/app/routes/tags.py` — 扩展返回 `usage_count`、`customer_count`；新增 `POST /api/tags/merge`

### 6.4 同步日志（system/SyncLogs.vue）

**原型参考**：`prototype/sync-logs.html`

**视觉重构**：`PageHeader` + `.grid-4` KPI + `FilterSection` + `TableSection`

**交互增强**（重构计划 3.17）：
- 实时同步监控面板（运行中任务 + 进度条）
- 失败任务重试按钮
- 同步模式标识列（增量/全量）
- 平均耗时 KPI
- 7 天同步趋势折线图
- 错误详情展开

**后端变更**：
- `backend/app/routes/sync_tasks.py` — 新增 `POST /api/sync/tasks/:id/retry`、`GET /api/sync/trend`

### 6.5 审计日志（system/AuditLogs.vue）

**原型参考**：`prototype/audit-logs.html`

**视觉重构**：`PageHeader` + `FilterSection` + `TableSection` + `QuickFilterTags`

**交互增强**（重构计划 3.18）：
- 风险级别筛选（高/中/低）
- before/after 对比视图（双列 JSON，差异高亮）
- 操作频率热力图
- 批量操作摘要
- 快速筛选标签
- 导出审计报告

**后端变更**：
- `backend/app/routes/audit_logs.py` — 扩展返回 `risk_level`、`before`、`after` 字段；新增 `GET /api/audit-logs/export`

### 6.6 行业类型（system/IndustryTypes.vue）

**原型参考**：`prototype/industry-types.html`

**视觉重构**：`PageHeader` + `TableSection`

**交互增强**（重构计划 3.19）：
- 关联客户数显示
- 批量删除/合并
- 拖拽排序
- 颜色标识

**后端变更**：
- `backend/app/routes/industry_type_routes.py` — 扩展返回 `customer_count`；新增 `PUT /api/industry-types/reorder`

### 6.7 数据清空（system/DatabaseManagement.vue）

**原型参考**：`prototype/database-management.html`

**视觉重构**：`PageHeader` + 居中危险操作卡片

**交互增强**（重构计划 3.20）：
- 清空前显示影响范围摘要
- 备份提醒
- 操作日志记录
- 分模块勾选清空（客户数据/结算数据/日志数据）

**后端变更**：
- `backend/app/routes/database_management.py` — 扩展返回影响范围统计；新增分模块清空参数

### 6.8 Phase 3 验证标准

- 所有 P2 页面视觉与原型一致
- 系统管理页面 CRUD 功能完整
- 后端新增 API 均添加 `@auth_required` 装饰器
- 数据库修改操作均在 `async with db_session.begin():` 块内
- E2E + 单元测试覆盖新增功能

---

## 7. Phase 4 — 认证/个人域

### 7.1 登录页（Login.vue）

**原型参考**：`prototype/login.html` + `design.md` 3.2 + 5.2

**视觉重构**：
- 登录外壳：`grid-template-columns: 480px 520px`，`max-width: 1000px`，`border-radius: 18px`
- 品牌侧：深色渐变背景 + 脉冲光晕动画 + 特性展示项
- 表单侧：`padding: 48px 56px`，表单标题 `28px/800`
- 使用原生 `<button type="submit" class="btn btn-primary">` 而非 Arco `a-button`（design.md 3.3.2）
- 登录按钮箭头图标 + loading 状态切换
- 复选框对齐 design.md 3.2.5 样式
- 分隔线对齐 design.md 3.2.6 样式

**交互验证**：
- 账号密码登录 → 已有，验证样式对齐
- 忘记密码弹窗 → 已有，验证样式
- 企业 SSO 按钮 → 已有，验证样式
- 响应式：`≤960px` 切单列，`≤640px` 全屏无圆角

**后端**：无变更，复用现有 `POST /api/auth/login`

### 7.2 重置密码（ResetPassword.vue）

**原型参考**：`prototype/reset-password.html` + `design.md` 4.8

**视觉重构**：
- 居中卡片容器 `max-width: 480px`
- 图标容器 `56×56px`，`border-radius: 14px`，`background: rgba(29,78,216,.10)`
- 标题 `22px/700`，描述 `var(--muted)`
- 按钮 `width: 100%; margin-top: 8px`

**交互增强**（重构计划 3.22）：

| 功能 | 前端 | 后端 |
|------|------|------|
| 密码强度指示器 | 弱/中/强 三级进度条 | 无 |
| 密码要求清单 | 实时校验打勾 | 无 |
| 显示/隐藏密码 | 眼睛图标切换 | 无 |
| 返回登录链接 | 底部链接 | 无 |

**后端**：无变更，复用现有 `POST /api/auth/reset-password`

### 7.3 个人信息（Profile.vue）

**原型参考**：`prototype/profile.html` + `design.md` 4.7

**视觉重构**：
- 左右分栏 `grid-template-columns: 1fr 1fr`
- 左侧头像区：`80×80px` 头像 + 姓名 `18px/700` + 辅助信息
- 右侧信息区：字段网格 + 标签 `12px` + 值 `<b>` 加粗

**交互增强**（重构计划 3.21）：

| 功能 | 前端 | 后端 |
|------|------|------|
| 最近活动卡片 | 最近 10 条操作记录 | `GET /api/audit-logs?user_id=me&limit=10`（扩展） |
| 密码安全强度 | 弱/中/强 进度条 | 无 |
| 头像裁剪 | 上传 + 裁剪弹窗 | `POST /api/users/me/avatar`（新增） |
| 偏好设置 Tab | 主题/语言/通知偏好 | `GET/PUT /api/users/me/preferences`（新增） |
| 快捷键说明 | 快捷键卡片 | 无 |

**后端变更**：
- `backend/app/routes/users.py` — 新增 `POST /api/users/me/avatar`（头像上传）
- `backend/app/routes/users.py` — 新增 `GET/PUT /api/users/me/preferences`（偏好设置）

### 7.4 Phase 4 最终清理

- 删除 `td002-component-styles.css` 文件
- 验证所有页面无残留旧样式引用
- 全量 E2E 测试通过
- 全量视觉回归快照更新

---

## 8. 测试策略

### 8.1 测试分层

| 层级 | 框架 | 覆盖范围 |
|------|------|----------|
| 单元测试 | Vitest（前端）+ pytest（后端） | 新增组件、composables、API 端点 |
| E2E 测试 | Playwright | 新增交互流程（KPI 下钻、保存筛选、Tab 导航等） |
| 视觉回归 | Playwright 快照 | 每页重构后更新快照基线 |
| API 测试 | pytest | 后端新增端点的输入验证、权限校验、事务完整性 |

### 8.2 每阶段测试要求

| 阶段 | 测试要求 |
|------|----------|
| Phase 0 | 通用组件单元测试 + 布局组件 E2E（侧边栏折叠/搜索快捷键） |
| Phase 1 | P0 页面 E2E（含新增交互）+ 后端新端点 pytest + 视觉回归快照更新 |
| Phase 2 | P1 页面 E2E（图表联动、天数切换）+ 后端新端点 pytest |
| Phase 3 | P2 页面 E2E（CRUD、批量操作）+ 后端新端点 pytest |
| Phase 4 | 认证页 E2E（登录流程、密码强度校验）+ 后端新端点 pytest |

### 8.3 CI 覆盖率要求

- 后端测试覆盖率 ≥ 50%（`--cov-fail-under=50`）
- 前端无硬性覆盖率要求，但新增组件/composables 必须有单元测试

---

## 9. 项目硬规则遵守清单

以下规则在整个重构过程中必须始终遵守：

| 规则 | 说明 |
|------|------|
| 数据库事务 | 所有修改操作必须在 `async with db_session.begin():` 块内执行 |
| 权限校验 | 所有 API 端点必须添加 `@auth_required` 装饰器 |
| 测试覆盖率 | CI 要求测试覆盖率 ≥ 50%（`--cov-fail-under=50`） |
| Python 版本 | 必须使用 Python 3.12.x，不支持 3.13+ |
| 并发安全 | 余额扣款使用行级锁（`FOR UPDATE`）防止冲突 |
| 文件修改前读取 | 避免基于过时快照编辑 |
| 中文回复 | 思考过程及会话内回复必须使用中文 |
| pre-commit 环境 | 脚本必须使用 `$BACKEND_DIR/.venv/bin/python` |

---

## 10. 全局验证标准

- ✅ 前端开发服务器正常启动，无控制台错误
- ✅ 所有 22+ 页面视觉与原型一致
- ✅ 重构优化计划中的交互功能全部实现
- ✅ `td002-component-styles.css` 已删除，无残留旧样式
- ✅ 后端新增 API 均有 `@auth_required` + 测试覆盖
- ✅ E2E 测试全部通过
- ✅ 视觉回归快照全部更新
- ✅ CI 通过（覆盖率 ≥ 50%）

---

## 11. 参考文件索引

| 文件 | 说明 |
|------|------|
| `prototype/design.md` | 完整设计规范（1829 行） |
| `prototype/index.html` | 单文件高保真原型 |
| `prototype/home.html` | 运营工作台原型 |
| `prototype/customers.html` | 客户列表原型 |
| `prototype/detail.html` | 客户详情原型 |
| `prototype/consumption.html` | 消耗分析原型 |
| `prototype/balance.html` | 余额管理原型 |
| `prototype/pricing.html` | 计费规则原型 |
| `prototype/invoices.html` | 结算单原型 |
| `prototype/profile-analysis.html` | 画像分析原型 |
| `prototype/health.html` | 健康度分析原型 |
| `prototype/payment.html` | 回款分析原型 |
| `prototype/forecast.html` | 预测回款原型 |
| `prototype/login.html` | 登录页原型 |
| `prototype/reset-password.html` | 重置密码原型 |
| `prototype/profile.html` | 个人信息原型 |
| `docs/superpowers/plans/2026-07-13-prototype-refactoring-optimization-plan.md` | 重构优化计划（22 页面详细方案） |
| `frontend/src/styles/global.css` | 设计令牌 + 全局工具类 |
| `frontend/src/styles/arco-theme.css` | Arco Design 主题覆盖 |
| `frontend/src/styles/td002-component-styles.css` | 旧样式文件（待迁移后删除） |
