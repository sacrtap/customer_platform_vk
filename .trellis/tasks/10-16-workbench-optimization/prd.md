# 运营工作台优化方案实现

## Goal

将运营工作台（`frontend/src/views/Home.vue`）从"展示层完整、数据层 6/10 指标为假、零角色差异化"改造为**各角色可信任的决策首屏**：数据真实化（KPI/同步状态/待办接真数据）、角色差异化（超管/运营经理/销售经理三档场景）、信息架构重组（经营健康 → 行动引导 → 趋势洞察）。

## Background（现状调研结论）

- KPI 条 6 项中「待回款 ¥1.36M」「低余额 42」「同步成功率 98.6%」「异常任务 7」为模板硬编码假数据；「活跃客户」「本月消耗」数字为真但副标签（+8.4%、73%）硬编码。
- 同步状态条 `ok/10:00/11:00` 硬编码；「异常与待办」3 条为 mock + `Math.random()` 造数（count/amount/urgency 全假）；3 个快捷操作为占位。
- 工作台对超管/运营经理/销售经理显示完全一致，未利用已有 RBAC（`customers:view_all`、`billing:ops_approve`、`billing:sales_approve`）与后端 scope 数据可见性。
- 后端 `get_dashboard_stats` / `get_priority_customers` / `get_dashboard_trend` 均已支持 scope 过滤，前端未据此分层。

## Requirements

1. **角色差异化首屏**：前端按用户权限派生角色画像（admin/ops/sales），首屏按角色展示对应口径与模块：
   - 超管：全局口径（副标签"全局 N 家"）、全量待办、PageHeader 副标题"全局经营视图"。
   - 运营经理："我负责的客户"口径、待办含「待我运营确认的结算单」（第一步）、快捷操作含"批量分配"。
   - 销售经理："我跟进的客户"口径、待办含「待我销售审批的结算单」（第二步）、趋势图默认"回款"、隐藏"数据同步""批量分配"。
2. **数据真实化**：KPI 条 4 项核心（活跃客户+环比 / 本月消耗+环比 / 待回款金额 / 低余额客户数）全部后端真实数据；同步成功率/最近同步/下次同步接真实同步日志与排程；「异常与待办」改为真实待办聚合接口，可点击跳转，按 urgency 排序。
3. **信息架构重组**：按"经营健康 → 行动引导 → 趋势洞察"排列；同步成功率移入同步状态条旁侧、异常任务并入待办；快捷操作按角色显隐并实现"导出报告"（前端 CSV）；删除"保存视图"占位按钮。
4. **清理旧接口**：删除无调用方的 `getDashboardChartData` / `/dashboard/chart-data`（前端导出函数、后端路由与 service 方法、相关测试）。
5. **诚实标注能力边界**：健康度趋势 tab 标注"当月快照"（后端无历史评分表）。

## Non-Goals

- 不新建数据库表、不做迁移（待办全部聚合现有领域状态）。
- 不做后端导出接口（导出报告用前端 CSV）。
- 不改"今日优先跟进客户"功能本身（已真实）。

## Acceptance Criteria

1. `deriveRoleProfile` 单测通过：`view_all`→admin、`billing:ops_approve`→ops、`billing:sales_approve`→sales（`cd frontend && pnpm test -- useWorkbenchRole`）。
2. 后端扩展 `get_dashboard_stats` + 新增 `get_dashboard_todos` 验证：新字段非 None 且数值合理（low_balance_count≥0、sync_success_rate 0-1 或 null、todos 项含 id/title/count/urgency/action_url）。
3. `/analytics/dashboard/stats`、`/analytics/dashboard/todos` 接口返回新字段；无 view_all 账号的数按 scope 过滤（回归不破坏）。
4. `grep -rn "Math.random\|1.36M\|98.6\|保存视图" frontend/src/views/Home.vue frontend/src/api/analytics.ts` 无命中（mock/硬编码清除）。
5. `cd frontend && pnpm type-check` 通过。
6. 角色 UI 冒烟（三种账号登录 `/`）：超管看全局口径+全量待办+默认消耗趋势；运营经理看"我负责"口径+待运营确认待办+批量分配；销售经理看"我跟进"口径+待销售审批待办+默认回款趋势+无数据同步/批量分配。
7. 后端全量测试通过：`cd backend && .venv/bin/python -m pytest tests/ -x -q`（含新增 stats/todos 测试），ruff/pyright 通过。

## Notes

- 待办口径修正（因无 `due_date` 字段）：逾期=按结算周期 `period_end` 判定，与 payment 模块"应收"口径一致。
- 角色判定权限码修正：`billing:ops_approve` 才是一步确认（运营经理独有）；`billing:confirm` 是第三步客户确认，不作为角色判定依据。
