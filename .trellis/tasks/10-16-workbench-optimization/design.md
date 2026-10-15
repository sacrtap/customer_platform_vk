# 设计文档：运营工作台优化实现

## 0. 与基线 Plan 的事实差异（调研修正，实现以此为准）

| # | Plan 描述 | 实际代码事实 | 修正 |
|---|-----------|-------------|------|
| D1 | `billing:confirm`=运营经理独有，第一步确认 | `billing:ops_approve`=运营经理(第一步 pending_ops→pending_sales)；`billing:sales_approve`=销售经理(第二步)；`billing:confirm`=客户确认(第三步)，运营经理也持有（seed.py:157-159） | 角色判定用 `billing:ops_approve` 判 ops、`billing:sales_approve` 判 sales；待办"待我处理"按该状态聚合 |
| D2 | 逾期/临期按 `due_date` | Invoice 模型**无 `due_date` 字段** | 用 `period_end` 口径：逾期=周期已结束未结清；临期=本月应收未结清 |
| D3 | `sync_success_rate` 用 status IN (success/partial/failed) | SyncTaskLog.status 实际终值 `success`/`partial`/`failed`（sync_task_service._update_audit_log 由 audit_status 传入；SyncTask 任务表才是 completed/running） | 聚合 SQL 排除 `pending`，与模型注释一致 |
| D4 | 低余额 `real_amount+bonus_amount<1000` | 现有 `get_balance_warning_list` 用 `CustomerBalance.total_amount < 1000`（total_amount 为维护的总余额字段，充值/扣款同步） | 统一用 `total_amount < 1000`，与余额预警页口径一致 |
| D5 | 删 chart-data 仅前端函数+后端路由 | 后端还有 service 方法 `get_dashboard_chart_data` + 3 处测试引用（integration/service/performance） | 一并删除 service 方法及相关测试；`get_consumption_trend`/`get_payment_trend` 有其他调用方，保留 |
| D6 | `next_sync_time` 无数据源 | 存在 `SyncScheduleConfig`（daily_sync，enabled + sync_time HH:MM） | next_sync_time 由排程配置推算当天/次日 HH:MM，未启用则 null |
| D7 | 待确认结算单 status=`pending_customer`+approver=me | 无 approver 概念；`approver_id` 未在流程中使用；确认人记 `ops_confirmed_by`/`sales_confirmed_by`，且 `confirm_ops` 校验 `customer.manager_id==me` | 待办按角色权限聚合：ops→`pending_ops`、sales→`pending_sales`，scope 内（customer 的 manager/sales_manager=me）

## 1. 后端：`get_dashboard_stats` 扩展字段

位置：`backend/app/services/analytics.py` `get_dashboard_stats(mine_user_id)`。

新增字段（`mine_user_id` scope 全部沿用，返回值不破坏既有字段）：

| 字段 | SQL 口径 |
|------|---------|
| `low_balance_count` | `COUNT(*) FROM customer_balances cb JOIN customers c ON c.id=cb.customer_id WHERE cb.total_amount < 1000 AND cb.deleted_at IS NULL AND c.deleted_at IS NULL`（+scope） |
| `pending_payment_amount` | `SUM(Invoice.total_amount - COALESCE(discount_amount,0))` WHERE `status NOT IN ('draft','cancelled','paid','completed')` AND Customer.deleted_at IS NULL（+scope，与 payment 模块"待回款=应收净额-已回款"同口径；单独查询，不并入 invoice_stmt 以免改变现计数） |
| `pending_payment_count` | 同范围 COUNT |
| `sync_success_rate` | 最近 30 条 `SyncTaskLog`（status IN success/partial/failed，按 id desc）：`SUM(success_count)/SUM(success_count+failed_count+skipped_count)`；无记录→`null` |
| `abnormal_task_count` | 近 7 天 `SyncTaskLog.status IN ('partial','failed')` 行数（executed_at >= 7 天前） |
| `last_sync_time` | `MAX(executed_at)`（字符串 `%Y-%m-%d %H:%M:%S`，比较安全）；无→`null` |
| `next_sync_time` | `SyncScheduleConfig(task_name='daily_sync')` 若 enabled：今天 `sync_time` 未过→今天 HH:MM，已过→次日 HH:MM；未启用→`null` |
| `total_customers_mom_pct` | `(本月客户总数 - 上月客户总数)/上月总数×100`，上月总数=`COUNT(Customer WHERE created_at <= 上月最后一天)`；上月为 0→`null`；四舍五入 1 位 |
| `month_consumption_mom_pct` | 上月结算周期消耗（period 落入上月、非 cancelled）×100 同理；上月为 0→`null` |

实现要点：
- 全部新加独立轻查询，不重构现有两个主查询（避免回归）；每个查询按现有 `scope_conds` 模式叠加。
- 返回 dict 按现有风格 `float(... or 0)` 归一。

## 2. 后端：`get_dashboard_todos`（新增）

位置：`AnalyticsService.get_dashboard_todos(mine_user_id, include_ops_pending=False, include_sales_pending=False) -> List[Dict]`。

返回 list，每项：

```json
{ "id": "low_balance", "title": "低余额客户", "count": 3, "amount": 0,
  "urgency": 9, "priority": "high", "action_url": "/billing/balances?warning=1", "due": null }
```

| id | title | 口径（全部 scope 过滤） | urgency/priority | action_url |
|----|-------|------------------------|------------------|-----------|
| `low_balance` | 低余额客户 | total_amount<1000 客户数 | 9/high | `/billing/balances?warning=1` |
| `overdue_invoices` | 逾期结算单 | `Invoice.period_end < 本月1日` AND status NOT IN (draft,cancelled,paid,completed)；count + SUM(total_amount) | 8/high | `/billing/invoices?status=overdue` |
| `due_soon` | 临期回款 | `period_end` 在本月内 AND 同上状态；count | 6/medium | `/billing/invoices?status=pending` |
| `churn_risk` | 流失风险客户 | 复用 `get_inactive_customers(days=90)` 的查询子句做 COUNT（不改该查询） | 5/medium | `/analytics/health?tab=churn` |
| `pending_ops`（仅 include_ops_pending） | 待运营确认 | `Invoice.status='pending_ops'` AND customer scope；count | 7/high | `/billing/invoices?status=pending_ops` |
| `pending_sales`（仅 include_sales_pending） | 待销售审批 | `Invoice.status='pending_sales'` AND customer scope；count | 7/high | `/billing/invoices?status=pending_sales` |

- urgency 排序在前端做；后端按 urgency 降序返回。
- `due`：当前无到期日概念，统一 `null`；amount 对无金额项为 0。
- priority 映射：urgency≥7→high，5-6→medium，<5→low（预留）。
- 空表安全：所有 COUNT/SUM 对空集返回 0/None→0。

## 3. 后端路由

位置：`backend/app/routes/analytics.py`。

1. `/dashboard/stats`（现有）：不改签名，传参与 scope 同现状；**缓存键升级 `stats:v2:scope:{scope}`**（旧缓存无新字段，防污染）。
2. 新增 `/dashboard/todos`（GET，`@auth_required`）：
   - `scope_user_id = await customer_scope_user_id(request)`；
   - 权限标志：`permission_cache.get_permissions(user_id)`（复用现有模式，路由内判断）→ `include_ops_pending = 'billing:ops_approve' in perms`、`include_sales_pending = 'billing:sales_approve' in perms`；超管默认全权限命中两者；
   - 缓存 60s，key `todos:v1:scope:{scope}:ops:{int}:sales:{int}`；
   - 返回 `{"code":0,"message":"success","data":[...]}`（data 直接为数组，对齐现有 priority-customers 风格）。
3. 删除 `/dashboard/chart-data`（GET）+ `AnalyticsService.get_dashboard_chart_data`。

## 4. 前端：角色画像 `useWorkbenchRole.ts`（新建）

`frontend/src/composables/useWorkbenchRole.ts`：

```ts
export interface WorkbenchRoleProfile {
  tier: 'admin' | 'ops' | 'sales'
  canViewAll: boolean
  canOpsConfirm: boolean   // billing:ops_approve
  canSalesApprove: boolean // billing:sales_approve
  canManageSystem: boolean // system:view
}
export function deriveRoleProfile(perms: Set<string>, roles: string[]): WorkbenchRoleProfile
```

判定：`customers:view_all`→admin；否则 `billing:ops_approve`→ops；否则 `billing:sales_approve`→sales；三者皆无→`tier='sales'`（最小权限视角，Plan 假设条 3）。`hasPermission` 语义对齐 `userStore.hasPermission`（超管角色名列表含"超级管理员"→全权限）。

## 5. 前端：Home.vue 改造

- **角色接入**：`useUserStore()` + `useWorkbenchRole()`；`pageSubtitle` computed 按 tier：admin→"全局经营视图"、ops→"我负责的客户"、sales→"我跟进的客户"（其余副标题文案同规则）。
- **KPI 条 4 项**：活跃客户（`totalCustomers`+`<span>{{ momPctText(totalCustomersMomPct) }}</span>`）、本月消耗（`monthConsumption`+环比）、待回款（`formatCurrency(pendingPaymentAmount)`，副标签 `pendingConfirmation 单待客户确认`）、低余额客户数（`lowBalanceCount`）。同步成功率与异常任务移出 KPI 条。
- **同步状态条**：`:status="syncStatus" :last-sync="stats.lastSyncTime || '—'" :next-sync="stats.nextSyncTime || undefined"`；`syncStatus = abnormalTaskCount>0 ? 'warning' : 'ok'`；旁侧加小标签：`同步成功率 {{ syncSuccessRate 或 '暂无记录' }}`、`{{ abnormalTaskCount }} 个异常`。
- **待办行动中心**：`getDashboardTodos` 真接口；每行渲染 title/count/amount(有值时)；整行可点击 `router.push(todo.action_url)`；删除 `sortByAmount` 开关与 `sortedTodos` 金额分支（保留按 urgency 排序）；后端已按角色返回项，前端不再过滤。
- **快捷操作**：新建客户 / 生成结算单 / 数据同步（`can('system:view')`）/ 导出报告（实现前端 CSV：KPI 4 项+待办快照，`Blob` 下载 `workbench-YYYYMMDD.csv`）；删除"保存视图"按钮与 `saveView`；"批量分配"按钮（今日优先跟进区标题旁）`v-if="can('customers:edit')"` 并跳转 `/customers?priority=1`（替换 `Message.info` 占位）。
- **趋势图**：`activeTrendTab` 初始值按 tier（ops/admin→'consume'、sales→'payment'）；健康度 tab label 加"（当月快照）"。
- **stats reactive**：新增 `lowBalanceCount/pendingPaymentAmount/pendingPaymentCount/syncSuccessRate/abnormalTaskCount/lastSyncTime/nextSyncTime/totalCustomersMomPct/monthConsumptionMomPct` 并映射。
- **formatCurrency**：新增金额格式化（万→万单位）工具或复用 `formatCurrencyWan`（待回款金额展示用 `¥x.x万` 或整数元，随 KPI 现有风格）。

## 6. 前端 API 层 `analytics.ts`

- `DashboardStats` 接口按新字段扩展。
- 删除 `getPendingTasks` + `PendingTask`/`PendingTasksResponse` mock；新增：

```ts
export interface DashboardTodo { id: string; title: string; count: number; amount: number; urgency: number; priority: 'high'|'medium'|'low'; action_url: string; due: string | null }
export function getDashboardTodos() { return api.get<DashboardTodo[]>('/analytics/dashboard/todos') }
```

- 删除 `getDashboardChartData` + `ChartTrendItem`/`DashboardChartData`（无调用方，含测试内引用清理）。

## 7. 测试

- 前端 `frontend/src/composables/__tests__/useWorkbenchRole.test.ts`：
  - `{customers:view_all}` + `['超级管理员']`→admin
  - `{customers:view, billing:ops_approve}`→ops
  - `{customers:view, billing:sales_approve}`→sales
  - 无权限→sales（降级）
- 后端 `backend/tests/test_analytics_service.py`：扩展现有 dashboard 测试组——`get_dashboard_stats` 新字段存在性与取值（low_balance_count≥0、sync_success_rate 0-1 或 None、mom 字段 None 或数字）；`get_dashboard_todos` 返回项 id 集合与 include 标志行为、空库安全。
- 后端 `backend/tests/integration/test_analytics_api.py`：`/dashboard/todos` 鉴权与返回结构；删除 chart-data 集成测试。
- 删除 `backend/tests/performance/test_api_load.py` 中对 chart-data 的 URL（模拟负载目标无意义）。
- 删除 `backend/tests/test_analytics_service.py` 中 `get_dashboard_chart_data` 测试。

## 8. 兼容性与回滚

- stats 接口是**加字段**，前端新字段读取对旧后端为 undefined：前端显示降级（`?? 0` / '—'），不报错。
- todos 为新接口，删除 chart-data 无消费者（已核实前端仅定义不调用；后端仅测试引用）。`git revert` 单提交即可回滚。
- 缓存：stats 缓存键 v2 升级避免旧缓存无字段；todos 60s TTL。

## 9. 明确不做（与 Plan/范围对齐）

- 不建新表/迁移；不改 `get_dashboard_trend` 后端（只改前端默认 tab 与 health 文案）；不动 priority-customers；不后移导出到后端。
