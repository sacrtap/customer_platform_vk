# Analytics Dashboard 契约（stats / todos / trend）

> 运营工作台（`frontend/src/views/Home.vue`）数据契约。改动 stats/todos 字段或口径必须同步本文件与
> `frontend/src/api/analytics.ts` 的 `DashboardStats` / `DashboardTodo` 类型。

## 1. Scope / Trigger

- 2026-10-16：工作台数据真实化（KPI/同步健康/待办接真数据）+ 角色差异化首屏。
- 变更面：`AnalyticsService.get_dashboard_stats` 返回值扩展；新增 `get_dashboard_todos` + `/analytics/dashboard/todos`；删除 `/dashboard/chart-data`。

## 2. Signatures

```python
# backend/app/services/analytics.py
async def get_dashboard_stats(self, mine_user_id: Optional[int] = None) -> Dict[str, Any]
async def get_dashboard_todos(
    self,
    mine_user_id: Optional[int] = None,
    include_ops_pending: bool = False,
    include_sales_pending: bool = False,
) -> List[Dict[str, Any]]
async def _get_sync_health_stats(self) -> Dict[str, Any]   # 私有：sync 成功率/异常/最近·下次同步
```

```text
GET /api/v1/analytics/dashboard/stats   (@auth_required, 无权限码要求)
GET /api/v1/analytics/dashboard/todos   (@auth_required, 无权限码要求)
GET /api/v1/analytics/dashboard/trend   (@auth_required)   # 既有，未改动
```

## 3. Contracts

### `/dashboard/stats` 响应 `data`

| 字段 | 类型 | 口径 |
|------|------|------|
| total_customers | int | 客户总数（scope） |
| key_customers / total_balance / real_balance / bonus_balance | int/float | 既有 |
| month_invoice_count / pending_confirmation / month_consumption | int/int/float | 既有（month=当月结算周期） |
| **low_balance_count** | int | `CustomerBalance.total_amount < 1000`（与余额预警口径一致，非 real+bonus） |
| **pending_payment_amount** | float | 应收净额累计：`status NOT IN (draft,cancelled,paid,completed)` 的 `total_amount - discount_amount` |
| **pending_payment_count** | int | 同上范围 COUNT |
| **sync_success_rate** | number\|null | 最近 30 条已终态任务（status∈success/partial/failed）**任务级**成功率 `(Σsuccess + 0.5×Σpartial)/Σ任务数`；无任务 null。**禁止**按 `success_count/failed_count` 跨任务汇总（单位不一致，见 Common Mistakes） |
| **abnormal_task_count** | int | 近 7 天 status∈(partial,failed) 行数 |
| **last_sync_time** | string\|null | `MAX(executed_at)`；executed_at 固定 `%Y-%m-%d %H:%M:%S` 字符串且**统一本地时间**（与 func.now()/排程同时区），可安全 max/比较 |
| **next_sync_time** | string\|null | `SyncScheduleConfig(daily_sync, enabled)` 推算当天/次日 HH:MM；未启用 null |
| **total_customers_mom_pct / month_consumption_mom_pct** | number\|null | 环比 %；上月基准为 0/None → null |

- 缓存：`stats:v2:scope:{scope}`（v2 版本前缀，字段扩展时必须递增，防旧缓存无新字段）；todos 缓存 60s `todos:v1:scope:..:ops:..:sales:..`。

### `/dashboard/todos` 响应 `data`（数组）

每项：`{id, title, count, amount, urgency(1-10), priority(high|medium|low), action_url, due(null)}`，按 urgency 降序。

| id | title | 口径（scope 强制） | urgency |
|----|-------|--------------------|---------|
| low_balance | 低余额客户 | total_amount<1000 | 9 |
| overdue_invoices | 逾期结算单 | `period_end < 本月1日` 且状态未结清（同 outstanding 口径）；count+SUM 金额 | 8 |
| due_soon | 临期回款 | `period_end` 在本月内且未结清 | 6 |
| churn_risk | 流失风险客户 | 90 天无消耗（与 `get_inactive_customers` 同口径） | 5 |
| pending_ops | 待运营确认 | `status='pending_ops'`；**仅当** possess `billing:ops_approve` | 7 |
| pending_sales | 待销售审批 | `status='pending_sales'`；**仅当** possess `billing:sales_approve` | 7 |

路由内权限判断：`permission_cache.get_permissions(user_id)`（与 `customer_scope_user_id` 同缓存）；超管默认命中全部权限 → 返回两种审批项。

### 数据可见性（scope）

所有统计 JOIN `Customer` 并叠加 `or_(Customer.manager_id==me, Customer.sales_manager_id==me)`；
`customers:view_all` 用户 scope=None 全量。sync 健康度是**全局系统指标**，不随 scope 变化（与客户数据无关）。

## 4. Validation & Error Matrix

| 场景 | 行为 |
|------|------|
| SyncTaskLog 空表 | sync_success_rate=null、last_sync_time=null、abnormal=0（前端"暂无同步记录"） |
| 上月无基准 | mom_pct=null（前端"暂无上月数据"） |
| 排程未启用 / 无 daily_sync 行 | next_sync_time=null（前端不显示"下次同步"） |
| 待办各表为空 | count=0 仍返回条目（不抛错） |
| 非 view_all 用户 | stats/todos 仅含其负责客户数据（服务端强制，前端不可绕过） |

## 5. Good / Base / Bad Cases

- Good：运营经理 guofuqian → total_customers=24（scope）、todos 含 pending_ops 无 pending_sales、无"数据同步"按钮。
- Base：超管 → 全量 1274、todos 含 pending_ops+pending_sales、默认趋势 tab=消耗。
- Bad：把角色判定写成 `billing:confirm`（该码是**第三步客户确认**，运营经理也持有；`billing:ops_approve` 才是一步确认且运营经理独有）。

## 6. Tests Required

- 单元：`tests/test_analytics_service.py::TestGetDashboardStats`（新字段值 + 空库 None/0）、`TestGetDashboardTodos`（基础 4 项 + include 标志 + urgency 降序）。
- 集成：`tests/integration/test_analytics_api.py::test_dashboard_todos_success`（4 基础项 id 存在 + urgency/action_url 键）。
- 前端：`useWorkbenchRole.test.ts`（tier 三档 + 降级）；`Home.test.ts`（mount 加载路径）。

## 7. Wrong vs Correct

- Wrong：`SELECT SUM(total_amount) FROM invoices WHERE status='pending_customer'` → 只算待客户确认、且漏应收净额（discount）。
- Correct：排除 draft/cancelled/paid/completed 的全链路未结 + `total_amount - discount_amount`，与回款分析「待回款=应收-已回款」同口径。
- Wrong：`due_date` 判定逾期/临期（Invoice 无此字段）→ 改用 `period_end`。
- Correct：逾期 = `period_end < 本月1日` 且未结清；临期 = `period_end ∈ 本月` 且未结清。

## Common Mistakes（经验）

- **Plan/需求中的权限码语义必须对照 seed.py 核实**：`billing:confirm`（第三步，商务/运营经理）、`billing:ops_approve`（第一步，运营经理独有）、`billing:sales_approve`（第二步，销售经理独有）。seed.py `PRESET_ROLES` 与 `ALL_PERMISSIONS` 注释是唯一权威。
- invoice 状态机：draft →(submit)→ pending_ops →(ops_approve)→ pending_sales →(sales_approve)→ pending_customer →(confirm 扣款)→ completed；paid/completed=已回款。
- 低余额统一用 `total_amount < 1000`（total_amount 为维护字段，与 real+bonus 同步）；不要混用 `real_amount+bonus_amount` 口径。
- **`SyncTaskLog` 的 count 字段跨任务单位不一致，禁止跨任务混合汇总**：`consumption_sync` 的 success_count=成功同步天数（可上万）、`check_balance_warning` 的 success_count=正常客户数、failed_count=**严重预警客户数**（不是失败！）、skipped_count=普通预警客户数、`email/invoice` 的 count=条数。唯一跨任务通用口径是 **status 任务级**（success/failed/partial 终值，partial 按 0.5 计）。
- **`SyncTaskLog.executed_at` 必须写本地时间**（naive `datetime.now()`）：2026-10-16 修复前 consumption_sync 用 `datetime.now()`（本地）而 check_balance_warning/email/invoice 用 `datetime.utcnow()`（UTC），导致 `MAX()` 字符串排序受 8h 时差误导、工作台展示时间差 8 小时。统一与 `func.now()`（DB 本地）、排程 `sync_time`（本地业务时间）同基准；历史 UTC 数据需 `to_char(executed_at::timestamp + interval '8 hours', ...)` 修正。
