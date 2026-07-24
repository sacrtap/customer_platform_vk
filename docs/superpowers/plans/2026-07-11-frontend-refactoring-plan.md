# 前端原型设计规范重构执行方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 依据 `prototype/design.md` 设计规范和 `prototype/index.html`、`prototype/login.html` 原型文件，对前端全部 22 个页面进行渐进式样式重构，统一设计令牌、布局框架和组件规范，不修改后端接口。

**Architecture:** 前端保持 Vue 3 + Composition API + Arco Design Vue 技术栈不变，通过映射原型设计令牌到 CSS 自定义属性和 Arco 主题变量，逐阶段重构布局框架、页面组件和图表配色，最终实现原型设计规范的全面落地。

**Tech Stack:** Vue 3.4 + TypeScript + Arco Design Vue 2.54 + Vite 7 + ECharts 5 + Pinia 2 + Vue Router 4

---

## 确认事项

| 序号 | 确认内容 | 决策 |
|------|----------|------|
| 1 | 设计总览页是否开发 | ❌ 不开发，但遵守其设计规范 |
| 2 | 首页"优先跟进客户"数据来源 | ✅ 方案 A：前端组合调用现有 API 模拟（已记录为 TD-010 技术债务） |
| 3 | 企业 SSO 登录 | ✅ 仅 UI 占位（点击提示"功能开发中"） |
| 4 | 行业类型 & 数据清空页面 | ✅ 保持现有功能，样式随新设计方案统一重构 |

---

## Global Constraints

- **不修改后端接口**：所有 API 调用保持现有路径和参数不变
- **不遗漏任何前端页面**：22 个页面全部覆盖
- **渐进式重构**：每个阶段独立可验证，可阶段提交
- **根因分析**：验证中发现的问题使用根因分析法追溯解决
- **最终 PR**：所有阶段完成且验证全部通过后才提交 PR
- **文件修改前必须先读取**：避免基于过时快照编辑
- **TypeScript 类型完整**：`npm run type-check` 必须 0 errors
- **单文件 ≤ 500 行**（测试文件除外）

---

## 页面清单（22 页）

| # | 页面 | 路由 | 文件 | 阶段 |
|---|------|------|------|------|
| 1 | 登录页 | `/login` | `views/Login.vue` | Phase 2 |
| 2 | 重置密码 | `/reset-password` | `views/ResetPassword.vue` | Phase 2 |
| 3 | 运营工作台（首页） | `/` | `views/Home.vue` | Phase 3 |
| 4 | 客户列表 | `/customers` | `views/customers/Index.vue` | Phase 4 |
| 5 | 客户详情 | `/customers/:id` | `views/customers/Detail.vue` | Phase 4 |
| 6 | 标签管理 | `/tags` | `views/tags/Index.vue` | Phase 7 |
| 7 | 余额管理 | `/billing/balances` | `views/billing/Balance.vue` | Phase 5 |
| 8 | 计费规则 | `/billing/pricing-rules` | `views/billing/PricingRules.vue` | Phase 5 |
| 9 | 结算单 | `/billing/invoices` | `views/billing/Invoices.vue` | Phase 5 |
| 10 | 消耗分析 | `/analytics/consumption` | `views/analytics/Consumption.vue` | Phase 6 |
| 11 | 回款分析 | `/analytics/payment` | `views/analytics/Payment.vue` | Phase 6 |
| 12 | 健康度分析 | `/analytics/health` | `views/analytics/Health.vue` | Phase 6 |
| 13 | 画像分析 | `/analytics/profile` | `views/analytics/Profile.vue` | Phase 6 |
| 14 | 预测回款 | `/analytics/forecast` | `views/analytics/Forecast.vue` | Phase 6 |
| 15 | 用户管理 | `/users` | `views/users/Index.vue` | Phase 7 |
| 16 | 角色管理 | `/roles` | `views/roles/Index.vue` | Phase 7 |
| 17 | 同步日志 | `/system/sync-logs` | `views/system/SyncLogs.vue` | Phase 7 |
| 18 | 审计日志 | `/system/audit-logs` | `views/system/AuditLogs.vue` | Phase 7 |
| 19 | 行业类型 | `/system/industry-types` | `views/system/IndustryTypes.vue` | Phase 7 |
| 20 | 数据清空 | `/system/database-management` | `views/system/DatabaseManagement.vue` | Phase 7 |
| 21 | 个人信息 | `/profile` | `views/Profile.vue` | Phase 8 |
| 22 | 仪表盘布局 | `/` (Layout) | `views/Dashboard.vue` | Phase 1 |

---

## 核心差异摘要

### 设计令牌差异

| 令牌 | 原型值 | 当前值 | 差异 |
|------|--------|--------|------|
| 主色 `--primary` | `#1D4ED8` | `#0f172a` | 🔴 完全不同 |
| 主色渐变 | `#1D4ED8 → #2563EB` | `#0369a1 → #0284c7` | 🔴 完全不同 |
| 品牌标识渐变 | `#3B82F6 → #06B6D4` | `#0369a1 → #0284c7` | 🔴 完全不同 |
| 字体栈 | `Inter, "PingFang SC", ...` | `Plus Jakarta Sans, ...` | 🔴 完全不同 |
| 圆角 | `18px / 12px / 16px` | `16px / 12px / 8px` | 🟡 接近 |

### 布局差异

| 维度 | 原型 | 当前 | 差异 |
|------|------|------|------|
| 布局方式 | CSS Grid (`252px 1fr`) | Flexbox (`margin-left`) | 🔴 需改为 Grid |
| 内容区最大宽度 | `max-width: 1440px` | 无限制 | 🔴 需添加 |
| 顶栏效果 | `backdrop-filter: blur(14px)` | 纯白背景 | 🔴 需添加毛玻璃 |
| 顶栏搜索框 | 有 | 无 | 🔴 需添加 |
| 侧边栏品牌标识 | `.mark` "VK" 渐变方块 | SVG 图标 + 文字 | 🔴 完全不同 |
| 侧边栏折叠按钮 | 浮动圆形药丸 | 底部方形小按钮 | 🔴 完全不同 |

---

## 实施阶段总览

| 阶段 | 名称 | 优先级 | 涉及文件数 | 预估工作量 |
|------|------|--------|-----------|-----------|
| Phase 0 | 设计令牌与基础层 | P0 | ~3 | 小 |
| Phase 1 | 布局框架（侧边栏 + 顶栏） | P0 | ~4 | 中 |
| Phase 2 | 登录认证页面 | P0 | ~2 | 中 |
| Phase 3 | 首页（运营工作台） | P0 | ~2 | 中 |
| Phase 4 | 客户管理（列表 + 详情） | P0 | ~12 | 大 |
| Phase 5 | 结算管理（余额 + 计费 + 发票） | P1 | ~12 | 大 |
| Phase 6 | 运营分析（5 个分析页） | P1 | ~8 | 大 |
| Phase 7 | 系统管理（7 个页面） | P2 | ~8 | 中 |
| Phase 8 | 个人信息与重置密码 | P2 | ~1 | 小 |
| Phase 9 | 响应式适配与无障碍 | P1 | 全局 | 中 |
| Phase 10 | 最终验证与 PR 提交 | — | — | 小 |

### 阶段提交策略

- **第一次阶段提交**：Phase 0-3 完成（设计令牌 + 布局 + 登录 + 首页）
- **第二次阶段提交**：Phase 4-6 完成（客户 + 结算 + 分析）
- **第三次阶段提交**：Phase 7-9 完成（系统管理 + 个人信息 + 响应式）
- **最终 PR**：Phase 10 验证全通过后提交

---

## Phase 0：设计令牌与基础层

**目标**: 将原型 `design.md` 中的设计令牌映射为全局 CSS 变量和 Arco Design 主题变量。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `frontend/src/styles/global.css` | 重写 CSS 变量 |
| `frontend/src/styles/arco-theme.css` | 重写 Arco 主题覆盖 |
| `frontend/src/main.ts` | 确认字体引入（如需 Inter 字体） |

### 任务清单

- [x] **0.1** 重写 `global.css` `:root` 变量
  - 中性色：`--bg: #F6F8FB`、`--panel: #FFFFFF`、`--ink: #0F172A`、`--muted: #475569`、`--soft: #E2E8F0`、`--line: #DBE3EF`
  - 主色/语义色：`--primary: #1D4ED8`、`--primary-2: #2563EB`、`--cyan: #0891B2`、`--green: #059669`、`--amber: #D97706`、`--red: #DC2626`、`--violet: #7C3AED`
  - 阴影：`--shadow: 0 14px 40px rgba(15,23,42,.08)`、`--shadow-sm: 0 1px 2px rgba(0,0,0,.04)`、`--shadow-md: 0 4px 12px rgba(0,0,0,.08)`
  - 圆角：`--radius: 18px`、`--radius-sm: 12px`
  - 字体栈：`Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif`
  - 保留旧变量别名（兼容期）：`--neutral-1` → `--bg`、`--neutral-10` → `--ink` 等映射

- [x] **0.2** 重写 `arco-theme.css` Arco 主题覆盖
  - Arco 主色从 `#0f172a` 改为 `#1D4ED8`
  - 按钮 primary 渐变：`linear-gradient(135deg, #1D4ED8, #2563EB)`
  - 输入框 focus：`border-color: #1D4ED8; box-shadow: 0 0 0 3px rgba(29,78,216,.1)`
  - 链接色：`#1D4ED8`
  - 分页 active：`background: #1D4ED8`
  - 标签 primary：`background: #DBEAFE; color: #1D4ED8`

- [x] **0.3** 添加全局工具类
  - 状态标签：`.tag.green/.amber/.red/.blue/.violet/.gray`（药丸样式，`border-radius: 999px`）
  - 网格布局：`.grid-4`(`repeat(4,1fr)`)、`.grid-3`(`repeat(3,1fr)`)、`.grid-2`(`repeat(2,1fr)`)
  - KPI 条：`.kpi-strip`(`repeat(6,1fr)`)
  - Hero 区：`.hero`(`1.35fr .65fr`)
  - 区块标题：`.section-title`
  - 空状态：`.empty-state`

### 验证

```bash
cd frontend && npm run type-check && npm run lint
```

**验证标准**: 编译无错误，已有页面不出现样式破坏性变化
**根因分析预案**: 若 Arco 组件颜色异常 → 检查 `!important` 覆盖优先级；若字体不生效 → 检查 `@import` 或 `<link>` 引入

---

## Phase 1：布局框架重构（侧边栏 + 顶栏）

**目标**: 将 `Dashboard.vue` 布局从 Flexbox 改为 CSS Grid，重构 `AppSidebar.vue` 和 `AppHeader.vue` 匹配原型设计。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `frontend/src/views/Dashboard.vue` | 改为 Grid 布局 |
| `frontend/src/components/layout/AppSidebar.vue` | 全面重构 |
| `frontend/src/components/layout/AppHeader.vue` | 添加毛玻璃 + 搜索框 |
| `frontend/src/composables/useAppLayout.ts` | 侧边栏状态适配 |

### 任务清单

- [x] **1.1** 重构 `Dashboard.vue` 布局
  - `.shell` 改为 `display: grid; grid-template-columns: 252px 1fr; transition: grid-template-columns .25s ease`
  - 折叠态 `.shell.collapsed` → `grid-template-columns: 72px 1fr`
  - 侧边栏 `position: sticky; top: 0; height: 100vh`
  - 内容区 `max-width: 1440px; margin: 0 auto; padding: 22px 24px 44px`
  - 移除 `margin-left` 方案，改用 Grid 自然布局
  - 保留修改密码弹窗功能

- [x] **1.2** 重构 `AppSidebar.vue` 侧边栏
  - 背景：`radial-gradient(circle at 20% 0%, rgba(37,99,235,.28), transparent 32%), linear-gradient(180deg, #111C33 0%, #0B1220 100%)`
  - 品牌标识：`.mark` 36×36px，`linear-gradient(135deg, #3B82F6, #06B6D4)`，`border-radius: 13px`，文字 "VK"，`font-weight: 900`
  - 品牌标题：`font-size: 16px; font-weight: 850; color: white`
  - 导航组：`background: rgba(15,23,42,.20); border-radius: 16px; padding: 6px`
  - 分组标题：`font-size: 10px; font-weight: 850; letter-spacing: .08em; text-transform: uppercase; color: #93A4B8`
  - 一级菜单按钮：`padding: 8px 10px; border-radius: 12px; color: #CBD5E1`
  - 一级菜单 hover：`background: rgba(255,255,255,.09); color: white`
  - 一级菜单 active：`background: linear-gradient(90deg, rgba(59,130,246,.24), rgba(6,182,212,.12)); color: white; box-shadow: inset 0 0 0 1px rgba(125,211,252,.12)`
  - active 图标颜色：`#67E8F9`
  - 二级菜单：`margin-left: 17px; padding-left: 8px; border-left: 1px solid rgba(148,163,184,.22)`
  - 二级菜单标签 `.nav-hint`：短标签提示任务属性
  - 折叠按钮：浮动圆形药丸 `position: absolute; right: -17px; width: 34px; height: 34px; border-radius: 999px; background: linear-gradient(135deg, #1D4ED8, #0891B2)`
  - 折叠态：宽度 `72px`，隐藏品牌文字/分组标题/二级菜单/说明卡片（`!important`）
  - 持久化：`localStorage` 保存 `prototype-sidebar-collapsed`
  - 侧边栏滚动：`.nav` 设置 `overflow-y: auto; overflow-x: visible`，`.nav-group` 设置 `overflow: visible`

- [x] **1.3** 重构 `AppHeader.vue` 顶栏
  - 添加 `backdrop-filter: blur(14px)` + `background: rgba(246,248,251,.86)`
  - 添加搜索框：`border-radius: 14px; border: 1px solid var(--line); padding: 10px 12px; box-shadow: 0 4px 14px rgba(15,23,42,.04)`
  - 搜索框 `role="search"` + `aria-label`
  - 键盘快捷键 `/` 聚焦搜索框
  - 保留现有面包屑、通知按钮、用户头像下拉

- [x] **1.4** 适配 `useAppLayout.ts`
  - 侧边栏折叠状态 `localStorage` key 改为 `prototype-sidebar-collapsed`
  - 保留导航菜单数据结构和权限过滤逻辑
  - 确保 `isParentMenuActive` / `isSubmenuActive` 路由匹配逻辑正确

### 验证

1. 启动 `npm run dev`，逐页面路由跳转，确认侧边栏导航正常
2. 测试折叠/展开：动画流畅、状态持久化、二级菜单隐藏/展开正确
3. 测试移动端响应式（≤1100px 侧边栏切顶部相对定位）
4. 搜索框 `/` 快捷键聚焦正常
5. 根因分析：若折叠后导航溢出 → 检查 `overflow-x: visible`；若毛玻璃不生效 → 检查浏览器兼容性

---

## Phase 2：登录认证页面重构

**目标**: 重构 `Login.vue` 和 `ResetPassword.vue` 匹配原型 `login.html`。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `frontend/src/views/Login.vue` | 全面重构样式 |
| `frontend/src/views/ResetPassword.vue` | 全面重构样式 |

### 任务清单

- [x] **2.1** 重构 `Login.vue`
  - 登录外壳：`grid-template-columns: 480px 520px; max-width: 1000px; min-height: 600px; border-radius: 18px; box-shadow: var(--shadow)`
  - 品牌侧背景：`radial-gradient(circle at 20% 0%, rgba(37,99,235,.28), transparent 32%), linear-gradient(180deg, #111C33 0%, #0B1220 100%)`
  - 品牌侧 padding：`48px 40px`
  - 脉冲光晕动画：`@keyframes pulse { 0%,100%{transform:scale(1);opacity:.5} 50%{transform:scale(1.1);opacity:.8} }`，`animation: pulse 8s ease-in-out infinite`
  - 品牌标识 `.mark`：`48×48px; border-radius: 16px; background: linear-gradient(135deg, #3B82F6, #06B6D4); color: white; font-weight: 900; font-size: 20px; box-shadow: 0 10px 28px rgba(37,99,235,.34)`
  - 品牌标题：`font-size: 24px; font-weight: 850; color: white`
  - 特性展示项（3 项）：图标容器 `40×40px; border-radius: 10px; background: rgba(59,130,246,.15)`，SVG `stroke: #3B82F6`，标题 `color: white; font-size: 15px; font-weight: 700`，描述 `color: #94A3B8; font-size: 13px`
  - 版权信息：`color: #64748B; font-size: 12px; text-align: center`
  - 表单侧：`padding: 48px 56px; background: var(--panel)`
  - 表单标题：`font-size: 28px; font-weight: 800; color: var(--ink)`
  - 表单标签：`font-size: 13px; font-weight: 600; color: var(--ink)`
  - 输入框：`padding: 12px 14px; border: 1px solid var(--line); border-radius: 12px; font-size: 14px`
  - 输入框 focus：`border-color: var(--primary); box-shadow: 0 0 0 3px rgba(29,78,216,.1)`
  - 主按钮：`width: 100%; padding: 13px 20px; background: linear-gradient(135deg, var(--primary), var(--primary-2)); color: white; border-radius: 12px; box-shadow: 0 8px 20px rgba(29,78,216,.25)`
  - 主按钮 hover：`transform: translateY(-1px); box-shadow: 0 12px 28px rgba(29,78,216,.35)`
  - 分隔线："或"，`::before/::after` 生成线条
  - SSO 按钮（UI 占位）：`width: 100%; background: var(--bg); color: var(--ink); border: 1px solid var(--line); border-radius: 12px`
  - 保留现有登录逻辑（`api.post('/auth/login')`）、记住我、忘记密码弹窗
  - 响应式：≤960px 切单列，≤640px 全屏无圆角

- [x] **2.2** 重构 `ResetPassword.vue`
  - 居中卡片：`max-width: 480px; border-radius: 18px; box-shadow: var(--shadow)`
  - 图标容器：`56×56px; border-radius: 14px; background: rgba(29,78,216,.10)`
  - 标题：`font-size: 22px; font-weight: 700`
  - 描述：`color: var(--muted); margin-bottom: 24px`
  - 按钮：`width: 100%; padding: 13px 20px` + 主色渐变
  - 保留现有重置逻辑（`api.post('/auth/reset-password')`）

### 验证

1. 登录功能正常：账号密码登录 → `api.post('/auth/login')` 返回 token/用户信息/权限
2. 记住我：勾选后 `localStorage` 保存用户名，刷新页面自动填充；取消勾选则清除
3. 忘记密码完整流程：弹窗输入用户名+注册邮箱 → `api.post('/auth/forgot-password')` → 提示发送成功
4. SSO 按钮点击提示"功能开发中"
5. 响应式：≤960px 切单列，≤640px 全屏无圆角
6. 重置密码功能正常：URL 携带 `?token=xxx` → 输入新密码+确认密码 → `api.post('/auth/reset-password')` → 成功后 2s 跳转登录页
7. 重置密码：无 token 时提示"重置链接无效"
8. 根因分析：若表单验证异常 → 检查 Arco Form 组件 `:rules` 兼容性

---

## Phase 3：首页（运营工作台）重构

**目标**: 重构 `Home.vue` 匹配原型首页布局。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `frontend/src/views/Home.vue` | 全面重构布局 |
| `frontend/src/components/StatCard.vue` | KPI 卡片样式调整 |

### 任务清单

- [x] **3.1** 添加 PageHeader
  - eyebrow（小标题）：`color: var(--primary); font-weight: 800; font-size: 12px; letter-spacing: .08em; text-transform: uppercase`
  - 大标题：`font-size: 26px; font-weight: 850`
  - 副标题：`color: var(--muted)`
  - 操作按钮组：刷新数据按钮

- [x] **3.2** 重构 Hero 区
  - `display: grid; grid-template-columns: 1.35fr .65fr; gap: 18px; margin-bottom: 18px`
  - 左侧：经营趋势图（ECharts 折线图，颜色 `#1D4ED8`）
  - 右侧：异常与待办区块（调用 `getPendingTasks()` + `getDashboardStats()` 组合展示）

- [x] **3.3** 重构 KPI 条
  - `display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px`
  - 紧凑 KPI 卡片：`padding: 11px; border-radius: 16px; border: 1px solid var(--line); box-shadow: 0 1px 2px rgba(0,0,0,.04)`
  - 标题：`font-size: 13px; color: var(--muted)`
  - 数值：`font-size: 22-28px; font-weight: 850`

- [x] **3.4** 优先跟进客户表格（TD-010 方案 A）
  - 调用 `getCustomers()`（带筛选+排序参数）模拟优先跟进客户
  - 表格卡片：`background: white; border-radius: 16px; border: 1px solid var(--line); box-shadow: 0 1px 2px rgba(0,0,0,.04)`
  - 表头：`background: #F8FAFC; color: #334155; font-size: 12px; font-weight: 600`
  - 行 hover：`background: #F8FBFF`
  - 客户信息列：客户 Logo（30×30px，`border-radius: 9px`）+ 名称组合

- [x] **3.5** 统一图表配色
  - ECharts 颜色序列：`['#1D4ED8', '#0891B2', '#059669', '#D97706', '#DC2626', '#7C3AED']`
  - 网格线：`var(--line)` 或更浅
  - 文字：`var(--muted)`
  - 保留现有数据加载逻辑（`useCachedRequest`）和性能优化

### 验证

1. 数据加载正常：stats（`getDashboardStats`）、chart（`getDashboardChartData`）、todos（`getPendingTasks`）、invoices（`getRecentInvoices`）、priority-customers
2. 刷新功能正常：点击刷新 → 强制跳过缓存（`forceRefresh=true`）→ 各模块独立 loading → 成功提示
3. 缓存机制正常：`useCachedRequest` 各自独立 TTL（stats 5min、chart 15min、todos 2min、invoices 2min）
4. 待办事项交互：checkbox 可勾选/取消
5. 占位按钮行为：导出/查看详情/查看全部 → 提示"功能开发中"
6. ECharts 懒加载正常：`import('echarts')` 动态导入不影响首屏
7. 最近结算单表格：状态徽章正确映射（draft/pending_customer/paid/completed/cancelled）
8. 响应式：≤1100px KPI 条切 2 列，Hero 区切 1 列
9. 根因分析：若 ECharts 图表颜色不更新 → 检查 `option` 对象引用；若优先跟进客户数据为空 → 检查 `getCustomers()` 参数

---

## Phase 4：客户管理重构（列表 + 详情）

**目标**: 重构客户列表和客户详情页面匹配原型设计。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `frontend/src/views/customers/Index.vue` | 重构布局和表格样式 |
| `frontend/src/views/customers/Detail.vue` | 重构布局和 Tab 样式 |
| `frontend/src/views/customers/components/CustomerFilters.vue` | 重构筛选区样式 |
| `frontend/src/views/customers/components/CustomerTable.vue` | 重构表格单元格 |
| `frontend/src/views/customers/components/CustomerFormModal.vue` | 统一弹窗样式 |
| `frontend/src/views/customers/components/CustomerImportModal.vue` | 统一弹窗样式 |
| `frontend/src/views/customers/components/CustomerBatchEditModal.vue` | 统一弹窗样式 |
| `frontend/src/views/customers/detail/CustomerBasicTab.vue` | 样式统一 |
| `frontend/src/views/customers/detail/CustomerProfileTab.vue` | 画像键值对卡片 |
| `frontend/src/views/customers/detail/CustomerBalanceTab.vue` | 样式统一 |
| `frontend/src/views/customers/detail/CustomerInvoicesTab.vue` | 样式统一 |
| `frontend/src/views/customers/detail/CustomerUsageTab.vue` | 热力图样式 |
| `frontend/src/components/CustomerAutoComplete.vue` | 样式统一 |

### 任务清单

- [x] **4.1** 客户列表 `Index.vue` 重构
  - PageHeader：eyebrow + 大标题 + 副标题 + 操作按钮组（新建/导入/导出）
  - 4 KPI 卡片区（客户总数/重点客户/本月消耗/异常客户）
  - 筛选区：白色卡片 `border-radius: 16px; border: 1px solid var(--line); box-shadow: 0 1px 2px rgba(0,0,0,.04); padding: 24px`
  - 表格客户信息列：客户 Logo（30×30px，`border-radius: 9px; background: #E0F2FE; color: #0369A1`）+ 名称组合
  - 消耗进度条：`height: 8px; background: #E2E8F0; border-radius: 999px`，填充 `linear-gradient(90deg, #2563EB, #06B6D4)`
  - 健康度标签：`.tag.green/.amber/.red`
  - 批量操作工具栏：`background: rgba(29,78,216,.06); border: 1px solid rgba(29,78,216,.15); border-radius: 12px`
  - 保留现有筛选/分页/CRUD 逻辑

- [x] **4.2** 客户详情 `Detail.vue` 重构
  - 4 KPI 头部（余额/本月消耗/结算单数/健康度）
  - Tab 切换改为原型药丸标签样式（`border-radius: 999px; padding: 7px 10px; font-weight: 700`）
  - Tab active：`background: #DBEAFE; border-color: #BFDBFE; color: #1D4ED8`
  - 画像信息卡片：键值对网格 `display: grid; gap: 9px`，每行 `display: flex; justify-content: space-between; border-bottom: 1px solid #EDF2F7`
  - 30 天消耗热力图（`CustomerUsageTab.vue`）：7 列网格，`height: 26px; border-radius: 7px`，颜色深度按倍数变化
  - 结算时间线（`CustomerInvoicesTab.vue`）：`grid-template-columns: 82px 1fr auto`，圆点 `8×8px; border-radius: 50%; background: var(--primary)`
  - 保留现有 Tab 功能和编辑弹窗

- [x] **4.3** 统一弹窗样式
  - 所有 Modal 圆角 `16px`
  - 主按钮渐变 `linear-gradient(135deg, #1D4ED8, #2563EB)`
  - 表单标签 `font-size: 13px; font-weight: 600`

### 验证

1. 客户列表 CRUD 全流程：新建（`CustomerFormModal`）、编辑、删除（确认弹窗）、导入（`CustomerImportModal`）、导出
2. 基础筛选 + 高级筛选联动正常（行业类型/运营经理/客户标签分别加载）
3. 表格排序正常（`@sort-change`）
4. 分页正常（页码切换 + 每页条数切换）
5. 查看客户跳转 → `/customers/:id`
6. 批量操作：多选 → 批量编辑弹窗（`CustomerBatchEditModal`）→ 取消选择
7. 客户详情 5 个 Tab 切换正常：基础信息、画像信息、余额信息、结算单、用量分析
8. 客户详情编辑弹窗（`EditCustomerDialog`）三列布局正常
9. 设为重点/取消重点（`toggleKeyCustomer`）正常
10. 标签管理：`TagSelectorDialog` 添加标签 + `removeTag` 删除标签
11. 余额信息 Tab：余额数据 + `BalanceTrendChart` 趋势图
12. 画像信息 Tab：画像数据 + `HealthGauge` 健康度仪表盘
13. 用量分析 Tab：用量数据 + 分页
14. 结算单 Tab：结算单列表 + `viewInvoice` 查看详情
15. 根因分析：若热力图数据异常 → 检查 API 返回的 daily usage 数据格式；若标签加载失败 → 检查 `allTags` API

---

## Phase 5：结算管理重构

**目标**: 重构余额管理、计费规则、结算单三个页面。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `frontend/src/views/billing/Balance.vue` | 重构布局样式 |
| `frontend/src/views/billing/PricingRules.vue` | 重构布局样式 |
| `frontend/src/views/billing/Invoices.vue` | 重构布局样式 |
| `frontend/src/views/billing/components/BalanceFilters.vue` | 样式统一 |
| `frontend/src/views/billing/components/DiscountModal.vue` | 样式统一 |
| `frontend/src/views/billing/components/GenerateInvoiceModal.vue` | 样式统一 |
| `frontend/src/views/billing/components/ImportBalanceModal.vue` | 样式统一 |
| `frontend/src/views/billing/components/InvoiceDetailDrawer.vue` | 样式统一 |
| `frontend/src/views/billing/components/InvoiceFilters.vue` | 样式统一 |
| `frontend/src/views/billing/components/PayModal.vue` | 样式统一 |
| `frontend/src/views/billing/components/RechargeModal.vue` | 样式统一 |
| `frontend/src/views/billing/components/RechargeRecordModal.vue` | 样式统一 |
| `frontend/src/components/invoice/InvoiceStatusBadge.vue` | 状态标签映射 |
| `frontend/src/components/invoice/InvoiceTimeline.vue` | 时间线样式 |

### 任务清单

- [x] **5.1** 余额管理 `Balance.vue` 重构
  - PageHeader + 4 KPI（总余额/实充余额/赠送余额/本月消耗）
  - 筛选区白色卡片
  - 余额表格统一样式
  - 保留充值/导入功能

- [x] **5.2** 计费规则 `PricingRules.vue` 重构
  - PageHeader + 筛选区
  - 规则表格：定价/阶梯/包年标签区分（`.tag.blue/.violet/.gray`）
  - 保留 CRUD 功能

- [x] **5.3** 结算单 `Invoices.vue` 重构
  - PageHeader + 4 KPI（草稿/待确认/已付款/已完成）
  - 筛选区白色卡片
  - 结算单表格统一样式
  - InvoiceDetailDrawer 样式重构
  - InvoiceTimeline 样式重构

- [x] **5.4** InvoiceStatusBadge 状态映射
  - draft → gray（`#F1F5F9` / `#475569`）
  - pending_customer → amber（`rgba(217,119,6,.10)` / `#D97706`）
  - customer_confirmed → blue（`#DBEAFE` / `#1D4ED8`）
  - paid → green（`rgba(5,150,105,.10)` / `#059669`）
  - completed → arcoblue
  - cancelled → red（`rgba(220,38,38,.10)` / `#DC2626`）

- [x] **5.5** 统一弹窗样式
  - 所有 Modal 圆角 `16px`
  - 主按钮渐变
  - 表单标签统一样式

### 验证

1. 余额管理：列表加载 + 筛选（行业/标签/运营经理）+ 排序（客户名/余额/已消耗/最新充值时间）
2. 余额明细展示：总额/实充/赠送 + 已消耗实/已消耗赠
3. 充值流程：`RechargeModal` 充值 → 成功后刷新列表
4. 充值记录查看：`RechargeRecordModal` 展示历史充值记录
5. 余额导入：`ImportBalanceModal` 导入 → 成功后刷新
6. 计费规则 CRUD：创建/编辑/删除
7. 计费规则动态表单：fixed（单价）/ tiered（JSON 阶梯配置 + 格式校验）/ package（套餐选择）三种类型切换
8. 计费规则冲突检测：`checkPricingRuleConflict` → 冲突时显示已有规则详情
9. 计费规则筛选：关键词/设备类型/计费类型
10. 结算单全流程：生成（`GenerateInvoiceModal`）→ 提交 → 确认 → 付款（`PayModal`）→ 完成 / 取消 / 删除草稿
11. 结算单折扣：`DiscountModal` 设置折扣
12. 结算单详情：`InvoiceDetailDrawer` 抽屉展示 + 状态操作按钮
13. 结算单跳转客户：`@go-customer` → `/customers/:id`
14. 结算单导出（当前占位 `console.log`，验证不报错即可）
15. `InvoiceStatusBadge` 状态标签正确映射 6 种状态
16. 根因分析：若金额计算异常 → 追溯 `calculate-items` API 调用；若阶梯 JSON 解析失败 → 检查 `JSON.parse` 错误提示

---

## Phase 6：运营分析重构

**目标**: 重构 5 个分析页面，统一图表配色和卡片样式。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `frontend/src/views/analytics/Consumption.vue` | 重构布局+图表配色 |
| `frontend/src/views/analytics/Payment.vue` | 重构布局+图表配色 |
| `frontend/src/views/analytics/Health.vue` | 重构布局+图表配色 |
| `frontend/src/views/analytics/Profile.vue` | 重构布局+图表配色 |
| `frontend/src/views/analytics/Forecast.vue` | 重构布局+图表配色 |
| `frontend/src/views/analytics/components/ProgressView.vue` | 样式统一 |
| `frontend/src/views/analytics/components/SyncDialog.vue` | 样式统一 |
| `frontend/src/components/charts/BalanceTrendChart.vue` | 图表配色 |
| `frontend/src/components/charts/UsageDistributionChart.vue` | 图表配色 |
| `frontend/src/components/charts/HealthGauge.vue` | 图表配色 |
| `frontend/src/components/charts/ConsumeLevelProgress.vue` | 样式统一 |
| `frontend/src/components/charts/index.ts` | 无需修改 |

### 任务清单

- [x] **6.1** 统一分析页布局
  - 所有分析页统一 PageHeader + 筛选区 + KPI 条 + 图表卡片布局
  - 图表卡片：`background: white; border-radius: 16px; border: 1px solid var(--line); box-shadow: 0 1px 2px rgba(0,0,0,.04); padding: 20px`
  - 区块标题：`font-size: 17px; font-weight: 600`

- [x] **6.2** 统一 ECharts 配色
  - 颜色序列：`['#1D4ED8', '#0891B2', '#059669', '#D97706', '#DC2626', '#7C3AED']`
  - 背景透明，文字 `var(--muted)`，网格线 `var(--line)` 或更浅
  - 更新所有图表组件（`BalanceTrendChart`、`UsageDistributionChart`、`HealthGauge`、`ConsumeLevelProgress`）

- [x] **6.3** 消耗分析 `Consumption.vue`
  - 6 KPI 条 + 趋势折线图 + 环形分布图 + Top 排行表
  - 保留消耗同步功能（SyncDialog）

- [x] **6.4** 回款分析 `Payment.vue`
  - 4 KPI + 柱状对比图 + 饼图 + 趋势图

- [x] **6.5** 健康度分析 `Health.vue`
  - 4 KPI + 预警客户表 + 长期未消耗客户表

- [x] **6.6** 画像分析 `Profile.vue`
  - 4 KPI + 行业分布饼图 + 规模等级柱图 + 消费等级环形图 + 房产占比

- [x] **6.7** 预测回款 `Forecast.vue`
  - 4 KPI + 趋势图 + 明细表

### 验证

1. 各分析页数据加载正常
2. 筛选条件联动正确
3. 图表渲染正确（无空白、无数据溢出）
4. **消耗分析特有**：
   - 时间范围筛选（1月/3月/6月/自定义）+ 日期范围选择器
   - 指标切换（cost ↔ order_count）三处联动：趋势图、设备分布、Top10
   - 数据同步（`SyncDialog`）：启动同步 → 进度显示 → 最小化 → 完成后自动刷新
   - 强制刷新（`force_refresh=true`）跳过缓存
   - Top10 客户排行：点击客户项切换 topCustomer 展示
   - 同步中按钮显示百分比进度
5. **回款分析特有**：
   - 4 KPI 正确（应收/减免/已回款+回款率/待回款）
   - 三图表渲染（对比柱图/状态饼图/趋势折线图）
6. **健康度分析特有**：
   - 4 KPI 正确（总客户/活跃/余额预警/流失风险）
   - 预警客户表：余额列排序 + 分页 + 查看跳转客户详情
   - 未消耗客户表：天数选择器（30/60/90/180天）+ 排序 + 分页 + 查看跳转
   - 两个列表独立刷新按钮
7. **画像分析特有**：
   - 强制刷新（`force_refresh=true`）+ 成功提示
   - 4 KPI 正确（总数/行业覆盖/房产客户+占比/数据完整率）
   - 4 饼图渲染（行业/规模等级/消费等级/房产行业分布）
   - 规模等级空状态处理（无有效数据时显示"-"）
   - 房产客户独立行业分布饼图（橙色系配色）
8. **预测回款特有**：
   - 年份选择器 + 月份选择器（全年/1-12月）联动
   - 4 KPI 正确（预测总额/已确认+完成率/待确认/预测客户数）
   - 月度预测图表（柱图预测 + 折线实际）
   - 预测明细表：金额列排序 + 分页 + 查看跳转客户详情
9. 根因分析：若图表空白 → 检查 ECharts 容器 `offsetWidth/Height`；若数据不匹配 → 检查 API 参数

---

## Phase 7：系统管理重构

**目标**: 重构用户管理、角色管理、标签管理、同步日志、审计日志、行业类型、数据清空 7 个页面。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `frontend/src/views/users/Index.vue` | 重构布局样式 |
| `frontend/src/views/roles/Index.vue` | 重构布局样式 |
| `frontend/src/views/tags/Index.vue` | 重构布局样式 |
| `frontend/src/views/system/SyncLogs.vue` | 重构布局样式 |
| `frontend/src/views/system/AuditLogs.vue` | 重构布局样式 |
| `frontend/src/views/system/IndustryTypes.vue` | 样式统一 |
| `frontend/src/views/system/DatabaseManagement.vue` | 样式统一 |
| `frontend/src/views/roles/permissionGroups.ts` | 无需修改 |

### 任务清单

- [x] **7.1** 用户管理 `users/Index.vue` 重构
  - PageHeader + 搜索 + 用户表格
  - 统一表格卡片样式

- [x] **7.2** 角色管理 `roles/Index.vue` 重构
  - PageHeader + 搜索 + 角色表格 + 权限分配弹窗
  - 统一表格卡片样式

- [x] **7.3** 标签管理 `tags/Index.vue` 重构
  - PageHeader + 分组 Tab（药丸样式 `border-radius: 999px`）
  - 标签云展示（`.tag` 药丸样式）
  - 保留 CRUD 功能

- [x] **7.4** 同步日志 `system/SyncLogs.vue` 重构
  - PageHeader + 4 KPI + 筛选 + 任务记录表格

- [x] **7.5** 审计日志 `system/AuditLogs.vue` 重构
  - PageHeader + 筛选 + 操作记录表格

- [x] **7.6** 行业类型 `system/IndustryTypes.vue` 样式统一
  - 跟随新设计令牌统一

- [x] **7.7** 数据清空 `system/DatabaseManagement.vue` 样式统一
  - 跟随新设计令牌统一

### 验证

1. **用户管理**：
   - 用户列表搜索（关键词）+ 分页
   - 创建用户（用户名/密码/邮箱/真实姓名/角色多选）
   - 编辑用户（用户名不可改、状态开关 `is_active`、角色多选）
   - 重置密码弹窗（新密码 + 确认密码 + 一致性校验）
   - 删除用户（确认弹窗）
   - 角色显示：多角色 tooltip 展示完整列表
   - 邮箱格式校验
2. **角色管理**：
   - 角色列表搜索 + 分页
   - 创建/编辑角色（名称 + 描述）
   - 系统角色保护（不可编辑、不可删除）
   - 权限配置弹窗：分组展示 + 全选/取消全选（全局 + 分组级）+ 权限计数
   - 删除角色（确认弹窗，系统角色禁用）
3. **标签管理**：
   - 客户标签/画像标签 Tab 切换
   - 标签 CRUD：新建（名称+类型+分类）、编辑（点击标签）、删除（关闭标签）
   - 分页
4. **同步日志**：
   - 4 KPI 统计卡片（总任务/成功率/24h执行/24h失败）
   - 状态筛选 + 分页
   - 任务进度条（运行中）+ 同步模式显示（仅补充缺失/强制覆盖）
   - 取消任务（pending/running 状态）+ 确认弹窗
   - 自动刷新（2s 轮询运行中任务）
   - 错误信息 tooltip
5. **审计日志**：
   - 筛选（用户ID/操作类型/模块/时间范围）+ 分页
   - 操作类型/模块下拉从 API 动态加载
   - 变更详情 popover（before/after JSON）
   - 批量操作摘要显示（`operation_type === 'batch'`）
   - created_at 排序
6. **行业类型**：CRUD（名称 + 排序号）
7. **数据清空**：权限校验（`system:database_clear`）+ 确认弹窗 + 结果展示
8. 根因分析：若权限分配失败 → 检查 `permissionGroups.ts` 数据结构

---

## Phase 8：个人信息与重置密码

**目标**: 重构个人信息页（重置密码已在 Phase 2 处理）。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `frontend/src/views/Profile.vue` | 重构布局样式 |

### 任务清单

- [x] **8.1** 个人信息 `Profile.vue` 重构
  - 左右分栏：`grid-template-columns: 1fr 1fr`
  - 左侧头像区：头像 `80×80px; border-radius: 50%; background: #DBEAFE; color: #1D4ED8`
  - 姓名 `font-size: 18px; font-weight: 700`
  - 辅助信息 `color: #94A3B8`
  - 右侧基本信息区：字段网格 `display: grid; gap: 14px`
  - 标签 `display: block; font-size: 12px; margin-bottom: 4px; color: var(--muted)`
  - 值 `<b>` 标签加粗
  - 保留头像上传、密码修改功能

### 验证

1. 信息加载正常：`getProfile()` → 用户名/邮箱/手机号/头像/真实姓名/最后登录时间
2. 信息保存正常：`updateProfile()` → 邮箱/手机号/头像/真实姓名 + Store 同步更新
3. 头像上传：JPG/PNG 格式校验 + 2MB 大小限制 → `uploadAvatar()` → Store 同步
4. 头像移除：`updateProfile({ avatar_url: '' })` → Store 同步
5. 修改密码弹窗：当前密码 + 新密码（≥6位）+ 确认密码（一致性校验）→ `changePassword()` API
6. 最后登录时间格式化展示
7. 手机号校验（11位数字）
8. 邮箱格式校验
9. 取消按钮 → `router.back()`
10. 根因分析：若头像上传失败 → 检查文件大小/类型限制；若 Store 未同步 → 检查 `userStore.setUserInfo` 调用

---

## Phase 9：响应式适配与无障碍

**目标**: 全局响应式断点适配和无障碍优化。

### 涉及文件

- 全局 CSS 文件
- 各页面组件的 `@media` 查询

### 任务清单

- [x] **9.1** 响应式断点规范
  - `> 1100px`：正常多栏布局
  - `≤ 1100px`：侧边栏切顶部相对定位；`.grid-4/.grid-3/.grid-2/.hero` 切 `1fr`；`.kpi-strip` 切 `repeat(2, 1fr)`；`desktop-only` 隐藏
  - `≤ 960px`：登录页切单列（品牌区 + 表单区垂直堆叠，隐藏第 3+ 特性项）
  - `≤ 640px`：登录页全屏无圆角；页面 padding 缩小至 `16px`；搜索框换行全宽；KPI 条单列；`.metric .value` 字号 `22px`；`.nav-hint` 隐藏

- [x] **9.2** 无障碍优化
  - 侧边栏折叠状态：`aria-expanded` + `aria-label` 同步更新
  - 导航当前状态：`aria-expanded="true/false"`
  - 搜索框：`role="search"` + `aria-label`
  - 键盘快捷键：`/` 聚焦搜索框，`Enter` 触发表单提交
  - 色彩对比：正文文字与背景对比度 ≥ 4.5:1，大文字 ≥ 3:1
  - 焦点可见性：`focus` 态有明显 outline/ring 提示

### 验证

1. Chrome DevTools 各断点视觉检查
2. 键盘导航测试（Tab/Enter/Space/`/`）
3. Lighthouse 无障碍评分 ≥ 90
4. 根因分析：若布局错位 → 检查 CSS Grid `minmax` / `auto-fit` 配置

---

## Phase 10：最终验证与 PR 提交

**目标**: 全量功能验证，确认无回归后提交 PR。

### 验证清单

- [x] **10.1** 编译验证
  - `npm run type-check` — 0 errors
  - `npm run lint` — 0 errors
  - `npm run build` — 构建成功

- [x] **10.2** 单元测试
  - `npm run test` — 全部通过
  - 覆盖率 ≥ 50%

- [x] **10.3** 全页面功能走查（22 个页面逐页验证）
  - **登录页**：登录/记住我（localStorage 持久化+恢复）/忘记密码（用户名+邮箱→发送重置链接）/SSO 占位
  - **重置密码**：token 参数校验/新密码+确认/成功后 2s 跳转登录/无 token 报错
  - **首页**：4 KPI/月度趋势图/待办勾选/最近结算单表格/刷新（强制跳过缓存）/占位按钮提示/ECharts 懒加载
  - **客户列表**：基础+高级筛选/排序/分页/CRUD/导入导出/批量编辑/查看跳转
  - **客户详情**：5 Tab 切换/编辑弹窗/设为重点/标签管理（添加+删除）/余额趋势图/健康度/用量分页/结算单查看
  - **标签管理**：客户/画像 Tab 切换/CRUD/分页
  - **余额管理**：筛选/排序/余额明细/充值/充值记录/导入
  - **计费规则**：CRUD/三种计费类型表单/阶梯 JSON 校验/冲突检测
  - **结算单**：全流程（生成→提交→确认→付款→完成/取消/删除）/折扣/详情 Drawer/跳转客户/状态徽章
  - **消耗分析**：时间范围/指标切换三联动/数据同步（进度+最小化）/强制刷新/Top10 交互
  - **回款分析**：时间范围/4 KPI/三图表（对比/状态/趋势）
  - **健康度分析**：4 KPI/预警表（排序+跳转）/未消耗表（天数选择+排序+跳转）
  - **画像分析**：强制刷新/4 KPI/四饼图/规模等级空状态/房产独立分布
  - **预测回款**：年月筛选/4 KPI/趋势图/明细表（排序+跳转）
  - **用户管理**：搜索/CRUD/重置密码/状态切换/角色多选+tooltip/邮箱校验
  - **角色管理**：搜索/CRUD/系统角色保护/权限配置（分组+全选+计数）
  - **同步日志**：4 KPI/状态筛选/进度条/同步模式/取消任务/自动刷新/错误 tooltip
  - **审计日志**：筛选（用户/操作/模块/时间）/动态下拉/变更详情 popover/批量摘要/排序
  - **行业类型**：CRUD（名称+排序号）
  - **数据清空**：权限校验/确认弹窗/结果展示
  - **个人信息**：加载/保存/头像上传校验/头像移除/修改密码/最后登录时间/Store 同步
  - **仪表盘布局**：侧边栏导航/折叠持久化/顶栏搜索/修改密码弹窗

- [x] **10.4** 响应式走查
  - 1100px 断点
  - 960px 断点
  - 640px 断点

- [x] **10.5** 无障碍走查
  - 键盘导航
  - 焦点可见性
  - aria 属性正确

### 根因分析流程

遇到问题时按以下流程处理：

```
1. 问题描述 → 明确现象和复现步骤
2. 根因定位 → 逐层排查（组件 → API → 数据 → 样式）
3. 修复方案 → 最小化变更
4. 验证修复 → 覆盖原问题 + 回归测试
5. 记录归档 → 防止同类问题
```

### 提交策略

- **第一次阶段提交**：Phase 0-3 完成
- **第二次阶段提交**：Phase 4-6 完成
- **第三次阶段提交**：Phase 7-9 完成
- **最终 PR**：Phase 10 验证全通过后提交

---

## 风险与回退

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Arco Design 主题覆盖不完整 | 中 | 部分 Arco 组件颜色不一致 | 逐组件检查，必要时增加 `!important` 覆盖 |
| CSS Grid 兼容性问题 | 低 | 旧浏览器布局错位 | 目标浏览器均为现代浏览器（Chrome 100+） |
| ECharts 图表配色遗漏 | 中 | 部分图表仍使用旧颜色 | 全局搜索 `#0369a1` 等旧色值 |
| 侧边栏折叠状态丢失 | 低 | 用户需重新折叠 | 确保 `localStorage` key 正确迁移 |
| 响应式断点冲突 | 中 | 部分 `@media` 查询冲突 | 统一断点值，删除冗余查询 |

---

## 附录：设计令牌速查表

```css
:root {
  /* 中性色 */
  --bg: #F6F8FB;
  --panel: #FFFFFF;
  --ink: #0F172A;
  --muted: #475569;
  --soft: #E2E8F0;
  --line: #DBE3EF;

  /* 主色/语义色 */
  --primary: #1D4ED8;
  --primary-2: #2563EB;
  --cyan: #0891B2;
  --green: #059669;
  --amber: #D97706;
  --red: #DC2626;
  --violet: #7C3AED;

  /* 阴影 */
  --shadow: 0 14px 40px rgba(15, 23, 42, .08);
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, .04);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, .08);

  /* 圆角 */
  --radius: 18px;
  --radius-sm: 12px;
}
```

## 附录：侧边栏导航结构

| 分组 | 一级菜单 | 二级菜单 |
|------|----------|----------|
| **总览** | 运营工作台 | — |
| **核心功能** | 客户管理、结算管理 | 客户列表、客户详情、标签管理；余额管理、计费规则、结算单 |
| **运营分析** | 客户分析 | 消耗分析、回款分析、健康度、画像分析、预测回款 |
| **系统管理** | 系统设置 | 用户管理、角色权限、行业类型、数据清空 |
| **系统工具** | 同步日志、审计日志 | — |
| **个人** | 个人信息 | — |
