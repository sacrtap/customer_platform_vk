# 前端原型风格全页面重构设计

## 1. 背景

当前项目是客户运营中台，前端技术栈为 Vue 3、Arco Design Vue、Pinia、Vue Router、ECharts、TypeScript 与 Vite。`prototype/` 目录已经交付新的 UI/UX 方向：紧凑型企业数据驾驶舱。

本设计基于：

- `prototype/index.html`
- `prototype/README.md`
- 当前前端路由与页面结构

目标是在不污染 `main` 的前提下，从新分支推进所有前端页面的视觉与组件结构重构。

当前开发分支：

```text
feat/frontend-prototype-redesign
```

## 2. 已批准方向

用户已批准采用：

**方案 B：视觉 + 组件结构重构**

该方案保留现有业务逻辑、API、路由与 Arco Design 组件体系，同时抽取统一设计系统和通用业务组件，让所有页面逐步落地 prototype 风格。

## 3. 设计目标

1. **统一视觉风格**
   - 全站采用 `prototype/index.html` 的紧凑型企业数据驾驶舱风格。
   - 使用深色渐变侧边栏、浅灰页面背景、白色卡片、蓝青主视觉。

2. **提升信息密度**
   - 关键页面首屏优先展示 KPI、风险、待办、趋势。
   - 表格、筛选、图表集中在一个工作面，减少跳转。

3. **提高维护性**
   - 抽取页面标题、指标卡、筛选面板、状态标签、表格容器等通用组件。
   - 避免每个页面重复实现相同布局与样式。

4. **控制风险**
   - 不改变后端 API。
   - 不重写核心业务逻辑。
   - 不引入新 UI 依赖。
   - 保留 Arco Design 作为基础组件库。

## 4. 非目标

本阶段不做以下事项：

- 不替换 Arco Design。
- 不改后端接口。
- 不重构权限模型、结算规则、客户数据结构。
- 不新增复杂动画框架。
- 不重新设计登录鉴权流程。
- 不在 `main` 上直接开发页面改造。

## 5. 原型设计基准

### 5.1 页面覆盖

`prototype/index.html` 已覆盖 7 个关键原型页面：

1. 设计总览
2. 运营工作台
3. 客户管理
4. 客户详情
5. 消耗分析
6. 结算管理
7. 系统治理

### 5.2 视觉基准

- 主色：`#1D4ED8`
- 辅助色：`#0891B2`
- 成功色：`#059669`
- 预警色：`#D97706`
- 风险色：`#DC2626`
- 页面背景：`#F6F8FB`
- 主文本：`#0F172A`
- 辅助文本：`#475569`

### 5.3 交互基准

- 侧边栏支持展开/收起。
- 展开态约 `252px`，折叠态约 `72px`。
- 折叠态仅显示一级菜单图标。
- 折叠态强制隐藏二级菜单，避免已展开二级菜单占位。
- 折叠态保留当前业务域父级高亮。
- 侧边栏状态通过 `localStorage` 持久化。
- 父级菜单展开态单展开，折叠态点击直接导航业务域。

## 6. 信息架构

以 prototype 的业务域分组为目标，同时映射当前路由：

### 6.1 总览

- 运营工作台：首页 / Dashboard

### 6.2 核心功能

- 客户管理
  - 客户列表
  - 客户详情
  - 标签与画像
- 结算管理
  - 余额管理
  - 计费规则
  - 结算单 / 发票 / 回款相关入口

### 6.3 运营分析

- 消耗分析
- 回款分析
- 健康度分析
- 画像分析
- 预测回款

### 6.4 系统管理

- 用户管理
- 角色管理
- 同步日志
- 审计日志
- 数据库管理
- 个人信息

## 7. 架构设计

### 7.1 分支策略

从干净 `main` 创建开发分支：

```bash
git checkout -b feat/frontend-prototype-redesign
```

所有页面重构工作只在该分支进行。完成后再通过 PR 或显式合并回 `main`。

### 7.2 样式系统

新增或重构全局样式入口，集中管理：

- 颜色 token
- 间距 token
- 卡片样式
- 状态色
- 表格密度
- 页面背景
- 侧边栏变量
- 图表容器样式

建议文件：

```text
frontend/src/styles/design-tokens.css
frontend/src/styles/dashboard-theme.css
```

若现有项目已有全局样式文件，应优先复用现有入口，避免重复引入。

### 7.3 布局层

重点重构：

```text
frontend/src/views/Dashboard.vue
frontend/src/components/layout/AppSidebar.vue
frontend/src/components/layout/AppHeader.vue
```

目标：

- AppSidebar 对齐 prototype 的深色渐变、图标菜单、二级菜单、折叠态。
- AppHeader 对齐 prototype 的全局搜索、状态提示、用户入口。
- Dashboard 统一页面内容容器宽度、padding、背景和响应式行为。

### 7.4 通用业务组件层

建议新增目录：

```text
frontend/src/components/dashboard/
```

建议组件：

| 组件 | 职责 |
|---|---|
| `AppPageHeader` | 页面标题、副标题、主操作按钮 |
| `MetricCard` | 单个 KPI 指标卡 |
| `MetricGrid` | KPI 指标栅格 |
| `FilterPanel` | 统一筛选区域容器 |
| `DataSection` | 图表/表格/列表区域标题与容器 |
| `StatusBadge` | 成功、预警、风险、普通状态 |
| `RiskTag` | 风险等级标签 |
| `ActionToolbar` | 批量操作、导出、新建等工具栏 |
| `CompactTableShell` | 表格外层滚动、边框、密度控制 |
| `ChartCard` | 图表卡片容器与图例/说明区 |

原则：

- 组件只负责展示结构，不直接耦合 API。
- 页面继续负责数据获取和业务动作。
- 组件 props 保持简单，避免为未来需求过度抽象。

## 8. 页面迁移设计

### 8.1 P0 页面

优先迁移最高频和最能体现 prototype 价值的页面：

1. `Home.vue`
   - 改为运营工作台。
   - 首屏展示 KPI、趋势、异常待办、优先客户。

2. `customers/Index.vue`
   - 改为客户资产工作台。
   - 强化筛选、健康度、余额风险、批量操作。

3. `customers/Detail.vue`
   - 改为客户 360。
   - 聚合基础信息、画像、余额、消耗、结算、操作记录。

4. `analytics/Consumption.vue`
   - 改为消耗分析驾驶舱。
   - 统一同步状态、趋势、设备分布、Top 客户、明细表。

5. 结算相关页面
   - `billing/Balance.vue`
   - `billing/Invoices.vue`
   - `billing/PricingRules.vue`
   - 强化余额风险、生成前检查、失败原因、金额影响排序。

### 8.2 P1 页面

- `analytics/Payment.vue`
- `analytics/Health.vue`
- `analytics/Profile.vue`
- `analytics/Forecast.vue`
- `tags/Index.vue`

目标：统一分析页结构和图表容器。

### 8.3 P2 页面

- `users/Index.vue`
- `roles/Index.vue`
- `system/SyncLogs.vue`
- `system/AuditLogs.vue`
- `system/DatabaseManagement.vue`
- `Profile.vue`
- `Login.vue`
- `ResetPassword.vue`

目标：统一系统管理、个人中心和认证页面风格。

## 9. 数据流设计

保持现有页面数据流：

- API 层不变。
- Pinia store 不变。
- 路由守卫不变。
- 页面继续调用现有接口。
- 通用展示组件通过 props 接收数据。

示例：

```text
页面 API 调用 → 页面状态整理 → 通用组件展示 → 用户操作回调 → 页面业务函数处理
```

## 10. 错误处理与空状态

统一页面反馈规则：

- API 加载中：使用 skeleton 或卡片内 loading。
- 空数据：给出原因和下一步动作，而不是只显示“暂无数据”。
- 风险数据：使用黄色/红色标签并提供操作按钮。
- 同步失败：展示失败原因、重试入口和最近同步时间。
- 表格异常：保留当前筛选条件，避免刷新后丢失上下文。

## 11. 响应式设计

- 桌面端：侧边栏 + 顶部栏 + 主内容。
- 中等屏幕：侧边栏可折叠，主内容保持单列优先。
- 移动端：菜单纵向堆叠或抽屉化，表格允许横向滚动。
- 不要求移动端达到完整桌面操作效率，但不能出现内容不可访问。

## 12. 验证策略

每个阶段至少执行：

```bash
npm run type-check
npm run lint
npm run build
```

针对视觉和交互：

- 用浏览器打开关键页面。
- 检查侧边栏展开/收起。
- 检查一级/二级菜单 active 状态。
- 检查 KPI、筛选、图表、表格在 1440px、1024px、768px、375px 下不出现横向溢出。

## 13. 风险与应对

### 13.1 风险：全页面一次性改动过大

应对：按 P0/P1/P2 迁移，每阶段都可独立验证。

### 13.2 风险：通用组件过度抽象

应对：先抽 prototype 已经稳定出现的模式；单页特例留在页面内，不提前泛化。

### 13.3 风险：Arco 组件样式覆盖冲突

应对：优先用外层容器和 CSS token 控制视觉；避免深层覆盖 Arco 内部 DOM。

### 13.4 风险：现有类型检查配置较宽松

应对：本次重构新增代码应保持类型明确，避免继续引入 `any` 和隐式不安全数据结构。

## 14. 成功标准

1. 所有前端页面视觉风格与 prototype 保持一致。
2. 侧边栏具备图标、二级菜单、折叠和持久化能力。
3. P0 页面具备 KPI + 筛选 + 图表/表格 + 风险提示的统一结构。
4. 主要通用组件被复用，而不是每页复制样式。
5. `npm run type-check`、`npm run lint`、`npm run build` 通过。
6. 所有工作在 `feat/frontend-prototype-redesign` 分支完成，不直接污染 `main`。

## 15. 后续实施入口

用户审阅并批准本设计后，进入实施计划阶段。实施计划应明确：

- 组件创建顺序
- 页面迁移批次
- 每批验证命令
- 每批可回退点
- 是否需要并行子代理处理不同页面域
