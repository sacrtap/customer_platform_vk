# 运营工作台优化方案

> 状态：已完成（产品经理视角，角色场景驱动，5 步方案）

## Context

用户要求以资深产品经理视角，结合各角色使用场景，对"运营工作台"（`frontend/src/views/Home.vue`）提出界面功能优化建议。当前工作台展示层完整但数据层 6/10 关键指标为假，且**零角色差异化**——所有角色看到同一界面，与系统已有的 RBAC + 数据可见性（`customers:view_all` 仅超管持有，运营/销售经理仅看自己负责客户）能力脱节。目标：给出按角色场景分层的界面优化建议，使工作台成为各角色的决策首屏。

## 现状深度分析（已调研确认）

### 数据真伪盘点

| 模块 | 数据来源 | 真实性 | 问题 |
|------|---------|--------|------|
| KPI「活跃客户」数 | 后端 `get_dashboard_stats` → `total_customers` | ✅ 真实 | 副标签"较上月 +8.4%"硬编码 |
| KPI「本月消耗」 | 后端 → `month_consumption` | ✅ 真实 | 副标签"完成 73%"硬编码 |
| KPI「待回款」金额 `¥1.36M` | 模板硬编码 | ❌ 假 | 后端有 `pending_confirmation`(单数) 无金额 |
| KPI「低余额客户 42」 | 模板硬编码 | ❌ 假 | 后端 `priority-customers` 可算但未聚合到 stats |
| KPI「同步成功率 98.6%」「异常任务 7」 | 模板硬编码 | ❌ 假 | 后端无对应聚合 |
| SyncStatusBar `ok/10:00/11:00` | 模板硬编码 | ❌ 假 | 后端无同步状态聚合 |
| 经营趋势图 | 后端 `get_dashboard_trend` | ✅ 真实 | "健康度"指标仅返回当月单点（无历史评分表） |
| 异常与待办列表 | 前端 `getPendingTasks()` mock 3 条 | ❌ 全假 | count/amount/urgency 用 `Math.random()` |
| 今日优先跟进客户 | 后端 `get_priority_customers` | ✅ 真实 | — |
| 快捷操作 4 项 | 3 项 `Message.info('...开发中')` | ❌ 占位 | |

### 结论

工作台**展示层完整、数据层 6/10 关键指标为假**。核心缺陷不是样式，而是**数据可信度**：
1. KPI 条 6 项中 3 项数字、全部副标签为硬编码假数据
2. "异常与待办"完全假（mock + 随机数），却是运营决策核心
3. 同步状态条硬编码，无法反映真实链路健康
4. 3 个快捷操作是占位


### 角色体系事实（已调研确认）

- **实际预置角色**（`backend/scripts/seed.py:144`）：超级管理员 + 运营经理 + 销售经理。README 的"数据分析师/高层管理者"是概念角色，无预置实现。
- **`customers:view_all`**（`backend/scripts/fix_add_view_all_permission.py:24`）：仅超级管理员持有，运营/销售经理默认**不授**，受数据可见性约束（仅看 `manager_id` 或 `sales_manager_id` 匹配的客户，见 `backend/app/middleware/auth.py:176` 的 `customer_scope_user_id`）。
- **工作台路由 `/` 无 `requiresPermission`**（`frontend/src/router/index.ts`）：所有角色可进，但 `Home.vue` 不读取 `userStore.roles` / 不做 `can()` 判断，**界面零差异化**。
- **后端已有 scope 支持**：`get_dashboard_stats(mine_user_id=scope)`、`get_priority_customers`、`get_dashboard_trend` 均按 scope 过滤数据，但前端工作台未据此做信息分层。
- **权限码体系**：`customers:view`/`view_all`、`billing:view`、`billing:confirm`(运营经理独有，结算单第一步确认)、`billing:sales_approve`(销售经理独有，第二步)、`billing:ops_approve`(运营经理)、`analytics:view`、`system:view`。
### 项目可复用能力（支撑真实化）

- `AnalyticsService.get_balance_warning_list` — 低余额客户（priority-customers 已用）
- `get_health_stats` — 健康度风险/流失客户计数
- `get_payment_analysis` / `get_invoice_status_stats` — 回款金额
- SyncLogs — 同步日志（可聚合成功率/异常任务）
- `get_prediction_trend` — 预测回款（已有预测能力，工作台未利用）

## Approach

已确认方向：**数据真实化 + 信息架构重构**；待办用**聚合现有领域状态**（不新建表）。本方案以产品经理视角，按"各角色首屏场景差异 → 通用信息真实化 → 信息架构重组"组织，每步可独立验证。

### Step 1 — 角色差异化首屏（产品核心建议）

当前工作台零角色差异，与系统 RBAC + 数据可见性能力脱节。在 `Home.vue` 引入角色感知，让不同角色看到与其职责匹配的首屏：

**前端角色判断**（复用现有能力，无新接口）：
- `Home.vue` script 顶部加 `const userStore = useUserStore()` + `const roleProfile = computed(() => deriveRoleProfile(userStore.roles, userStore.permissions))`。
- `deriveRoleProfile(roles: string[], perms: Set<string>)` 返回 `{ tier: 'admin'|'ops'|'sales', canViewAll: boolean, canConfirm: boolean, canSalesApprove: boolean, canManageSystem: boolean }`。判定：`perms.has('customers:view_all')`→admin/全局；`perms.has('billing:confirm')||'billing:ops_approve'`→ops；`perms.has('billing:sales_approve')`→sales。三者互斥按 admin>ops>sales 优先。纯前端函数，放 `Home.vue` 内或 `composables/useWorkbenchRole.ts`（无等价工具存在，新建）。

**差异化展示规则**：
- **超管/全局角色**：KPI 显示全局口径（活跃客户总数、全量本月消耗、全量待回款、全量低余额客户数）；趋势图默认"消耗"全量；待办含"全量同步异常""全量逾期结算单"。PageHeader subtitle 显示"全局经营视图"。
- **运营经理**：KPI 标注"我负责的客户"口径（后端 scope 已自动过滤，前端只需改文案：副标签"我负责 N 家"而非"较上月+8.4%"）；待办聚焦"待我确认的结算单"（`billing:confirm` 独有，调 `/billing/invoices?status=pending_confirmation&approver=me`）；快捷操作突出"批量分配""提醒充值"。
- **销售经理**：KPI 标注"我跟进的客户"；待办聚焦"待我销售审批的结算单"（`billing:sales_approve` 独有）；趋势图默认"回款"（销售关注回款而非消耗）；隐藏"数据同步""批量分配"（无 `system:view` / 无 `customers:edit`），保留"新建客户""生成结算单"。
- 用 `v-if="roleProfile.tier === 'admin'"` / `can('billing:confirm')` 控制模块显隐，复用 `useAppLayout` 已有的 `can()`。

### Step 2 — 后端：dashboard stats 扩展真实字段（支撑 Step 1 数据）

扩展 `AnalyticsService.get_dashboard_stats`（`backend/app/services/analytics.py:2740`）返回值，新增字段使 KPI 全部真实（scope 已支持，无需改签名）：
- `low_balance_count`：直接 `SELECT count(*) FROM customer_balances WHERE real_amount + bonus_amount < 1000 AND deleted_at IS NULL`（加 scope_conds），不调 `get_balance_warning_list` 全量（避免重查询）。
- `pending_payment_amount`：`SELECT SUM(total_amount) FROM invoices WHERE status='pending_customer' AND deleted_at IS NULL`（加 scope_conds via Customer join），与已有 `pending_confirmation` 同上下文。
- `sync_success_rate` + `abnormal_task_count` + `last_sync_time` + `next_sync_time`：聚合 `SyncTaskLog` 表（`backend/app/models/billing.py:250`，字段 `status`/`executed_at`/`success_count`/`failed_count`）。`sync_success_rate = success_count / (success+failed+skipped)` 最近 N 条；`abnormal_task_count = status IN ('partial','failed')` 计数；`last_sync_time` = 最近 `executed_at`。
- 环比：`total_customers`/`month_consumption` 各加 `*_mom_pct`（上月同期查询，scope 同）。
返回值新增键：`low_balance_count`, `pending_payment_amount`, `sync_success_rate`, `abnormal_task_count`, `last_sync_time`, `next_sync_time`, `total_customers_mom_pct`, `month_consumption_mom_pct`。无新表、无迁移。

### Step 3 — 后端：待办真实化聚合接口（支撑 Step 1 待办）

新增 `get_dashboard_todos` 方法于 `AnalyticsService` + `/analytics/dashboard/todos` 路由（`backend/app/routes/analytics.py`，紧邻 L1001 的 `/dashboard/stats`）。聚合现有领域状态为待办项，每项含 `id`(字符串稳定键), `title`, `count`, `amount`, `urgency`(1-10), `priority`, `action_url`(点击跳转路径), `due`：
- 低余额客户：复用 Step2 查询，`urgency=9, action_url='/billing/balances?warning=1'`
- 逾期结算单：`SELECT count(*), SUM(total_amount) FROM invoices WHERE status IN overdue-states AND due_date < today`（payment 模块同口径），`urgency=8, action_url='/billing/invoices?status=overdue'`
- 临期回款：`SELECT count(*) FROM invoices WHERE status='pending_customer' AND due_date BETWEEN today AND today+7`，`urgency=6, action_url='/billing/invoices?status=pending'`
- 流失风险客户：复用 `get_risk_customers` 流失风险子集计数，`urgency=5, action_url='/analytics/health?tab=churn'`
- 待确认结算单（仅 ops 角色返回此项，后端按 scope 用户的 `billing:confirm` 权限判断是否聚合）：`SELECT count(*) FROM invoices WHERE status='pending_customer' AND approver=scope_user`，`urgency=7, action_url='/billing/invoices?status=pending_confirmation'`
替换前端 `getPendingTasks` mock（`frontend/src/api/analytics.ts:449`）为 `api.get('/analytics/dashboard/todos')`，删 mock 数组 + `Promise.resolve` + `loadTodos` 中的 `Math.random()`。

### Step 4 — 前端：KPI 条 + SyncStatusBar 接真数据

改 `Home.vue` KPI 模板（L22-56）：
- 删硬编码：`¥1.36M`→`{{ formatCurrency(stats.pendingPaymentAmount) }}`；`42`→`{{ stats.lowBalanceCount }}`；`98.6%`→`{{ stats.syncSuccessRate?.toFixed(1) ?? '—' }}%`；`7`→`{{ stats.abnormalTaskCount }}`。
- 副标签接真实环比：`stats.totalCustomersMomPct`/`monthConsumptionMomPct`；同步成功率副标签 `abnormalTaskCount > 0 ? `${abnormalTaskCount} 异常` : '稳定'`。
- `stats` reactive（L209）新增字段并从 `res.data` 映射。
- `SyncStatusBar`（L16）改 `:status="syncStatus" :last-sync="stats.lastSyncTime" :next-sync="stats.nextSyncTime"`，删硬编码。`syncStatus` computed：`abnormalTaskCount > 0 ? 'warning' : 'ok'`。

### Step 5 — 前端：信息架构重组（按决策流 + 角色场景）

重组 `Home.vue` 首屏，按"经营健康 → 行动引导 → 趋势洞察"决策流排列，并落 Step 1 的角色差异：
- **KPI 条精简为 4 项核心**（活跃客户+环比 / 本月消耗+完成度 / 待回款金额+临期单数 / 低余额客户数），同步成功率移入 SyncStatusBar 旁侧，异常任务移入待办。副标签文案按 Step 1 角色口径（"我负责 N 家" vs "全局 N 家"）。
- **异常与待办升级为行动中心**：每条可点击 → `todo.action_url`（Step 3 返回）。删 `sortByAmount` toggle（真实 urgency 排序），保留 urgency 默认排序。待办列表按角色过滤（Step 1 + Step 3 后端配合）。
- **快捷操作按角色显隐 + 补齐**：`exportReport` 实现为前端生成 CSV（KPI+待办快照）；`batchAssign` 仅 ops/admin 可见（`can('customers:edit')`），跳转 `/customers?priority=1`；`saveView` 移除（删按钮）；"数据同步"仅 `can('system:view')` 可见。
- **趋势图保留**，"健康度"tab 标注"当月快照"（后端无历史评分，诚实标注）；默认指标按角色（ops=消耗，sales=回款，admin=消耗）。

### Step 6 — 前端：dashboard chart-data 旧接口清理

`Home.vue` 现用 `getDashboardTrend`（多指标），但 `getDashboardChartData`（`analytics.ts:429`，旧单指标接口）及后端路由 `/dashboard/chart-data`（`analytics.py:1022`）已无调用方。确认无其他引用后删前端导出函数 + 后端路由（默认 clean cutover）。

## Critical files & anchors

- `frontend/src/views/Home.vue` — 工作台主页，Step 1/4/5 全在此；KPI 模板 L22-56，stats reactive L209，loadStats L283，loadTodos L435，roleProfile 接入点 L196 附近
- `frontend/src/composables/useWorkbenchRole.ts` — 新建；`deriveRoleProfile(roles, perms)` 角色分层逻辑，Step 1 核心
- `frontend/src/stores/user.ts` — 复用 `roles`/`permissions`/`hasPermission`（L7, L19, L44），Step 1 数据源
- `frontend/src/api/analytics.ts` — `getPendingTasks` mock L449 改真接口，`getDashboardStats` 返回类型 L412 扩展
- `backend/app/services/analytics.py` — `get_dashboard_stats` L2740 扩展字段，新增 `get_dashboard_todos` 方法
- `backend/app/routes/analytics.py` — 新增 `/dashboard/todos` 路由（紧邻 L1001）；可能删 `/dashboard/chart-data` L1022

## Verification

每步独立验证，全部在 `backend/` 或 `frontend/` 目录执行：

1. **角色分层正确性**：`deriveRoleProfile` 单测——输入 `Set(['customers:view_all'])` 断言 `tier==='admin'`；输入 `Set(['customers:view','billing:confirm'])` 断言 `tier==='ops'`；输入 `Set(['customers:view','billing:sales_approve'])` 断言 `tier==='sales'`。`cd frontend && pnpm test -- useWorkbenchRole`
2. **后端聚合正确性**：`cd backend && .venv/bin/python -c "..."` 调用扩展后 `get_dashboard_stats` + `get_dashboard_todos`，断言新字段非 None 且数值合理（low_balance_count≥0，sync_success_rate 0-1 之间）。
3. **后端路由**：启动后端，`curl -H "Authorization: Bearer <token>" localhost:8000/analytics/dashboard/stats` 和 `/dashboard/todos`，断言 JSON 含新字段。
4. **前端无 mock 残留**：`grep -rn "Math.random\|Promise.resolve.*tasks\|1.36M\|98.6" frontend/src/views/Home.vue frontend/src/api/analytics.ts` 应无命中。
5. **类型检查**：`cd frontend && pnpm type-check` 通过（stats 新字段 + roleProfile 类型对齐）。
6. **角色场景 UI 冒烟**：分别用超管/运营经理/销售经理账号登录访问 `/`——超管看全局口径+全量待办+默认消耗趋势；运营经理看"我负责"口径+待确认结算单待办+批量分配按钮；销售经理看"我跟进"口径+待审批待办+默认回款趋势+无数据同步/批量分配按钮。
7. **数据可见性回归**：非 view_all 账号的 stats/todos 仅含其负责客户数据（后端 scope 已强制，验证未破坏）。

## Assumptions & contingencies

- **假设**：`SyncTaskLog` 有定期写入数据（同步任务实际运行过）。若表为空：`sync_success_rate` 返回 `null`，前端显示"暂无同步记录"而非 98.6% 假值。Step1 查询对空表安全。
- **假设**：无独立"月预算"表（README 未提）。消耗完成度用上月消耗为基准，若上月无数据则副标签显示"—"。
- **假设**：`exportReport` 前端 CSV 足够（用户选"数据真实化+IA"非"含后端导出"）。若需后端导出则降级为跳转分析页，不在本轮建导出接口。
- **假设**：实际用户只有超管/运营经理/销售经理三种预置角色（seed.py 确认）。若企业自定义了新角色（如"数据分析师"只读），`deriveRoleProfile` 对未知角色降级为 `tier='sales'`（最小权限视角），并在副标签显示"自定义角色"提示。
