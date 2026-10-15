# 实施计划：运营工作台优化实现

分支：`optimize/workbench-optimization`（基于 main）

## Phase A — 后端数据层（先于前端，接口先行）

- [ ] A1 `get_dashboard_stats` 扩展字段（analytics.py）：按 design §1 新增 9 个字段，沿用 scope_conds 模式、独立轻查询
- [ ] A2 新增 `get_dashboard_todos(mine_user_id, include_ops_pending, include_sales_pending)`（design §2）
- [ ] A3 路由：`/dashboard/stats` 缓存键 v2；新增 `/dashboard/todos`；删除 `/dashboard/chart-data` + service `get_dashboard_chart_data`；清理 performance 测试 URL
- [ ] A4 后端测试：service 层 stats 新字段 + todos（test_analytics_service.py）；integration todos 接口（test_analytics_api.py）；删除 chart-data 相关测试
- [ ] A5 验证：`cd backend && .venv/bin/python -m pytest tests/test_analytics_service.py tests/integration/test_analytics_api.py -q`；ruff、pyright（后端 make check 全量见总验证）

## Phase B — 前端角色画像 + 数据层

- [ ] B1 `useWorkbenchRole.ts`（新建，design §4）+ 单测
- [ ] B2 `analytics.ts`：DashboardStats 扩展、getDashboardTodos 新接口、删 getPendingTasks/getDashboardChartData
- [ ] B3 验证：`cd frontend && pnpm test -- useWorkbenchRole && pnpm type-check`

## Phase C — Home.vue 改造（角色差异 + KPI + 待办 + 同步条 + 快捷操作 + 趋势默认值）

- [ ] C1 KPI 4 项接真数据 + 环比副标签；同步条接 last/next/success_rate/abnormal；待办行动中心（可点击、删 sortByAmount）；快捷操作显隐 + CSV 导出 + 删保存视图；趋势默认 tab 按角色；health tab"当月快照"
- [ ] C2 验证：`cd frontend && pnpm type-check`；`grep -rn "Math.random\|1.36M\|98.6\|保存视图" frontend/src/views/Home.vue frontend/src/api/analytics.ts` 无命中

## Phase D — 端到端验证 + 收尾

- [ ] D1 启动后端+前端，三账号冒烟（超管/运营经理/销售经理登录 `/`）：角色差异、KPI 真实值、待办跳转、趋势默认指标
- [ ] D2 后端全量：`cd backend && .venv/bin/python -m pytest tests/ -q`（覆盖率 CI 口径 ≥50% 不因删除测试下降）；ruff check、pyright
- [ ] D3 前端全量：`pnpm test`（全量 vitest）+ `pnpm type-check`
- [ ] D4 更新 spec 指南（trellis-update-spec）：
  - `backend` → 无新增，但可在 analytics 相关记录 dashboard stats/todos 字段契约（如无对应文档则记入 journal，避免重复沉淀）
  - 若发现可复用经验（如"plan 与实际权限码映射差异"）→ 沉淀到 `.trellis/spec/guides/` 或 learn
- [ ] D5 提交：按逻辑分 2-3 个 commit（后端数据层 / 前端角色+API / Home.vue 改造），写 PR 描述含验收边界；归档任务

## 验证命令速查

```bash
# 后端单测
cd backend && .venv/bin/python -m pytest tests/test_analytics_service.py tests/integration/test_analytics_api.py -q
# 后端全量 + 静态检查
cd backend && .venv/bin/python -m pytest tests/ -q && .venv/bin/ruff check app/ && .venv/bin/pyright
# 前端
cd frontend && pnpm test -- useWorkbenchRole && pnpm type-check && pnpm test
# mock 残留检查
grep -rn "Math.random\|1.36M\|98.6\|保存视图" frontend/src/views/Home.vue frontend/src/api/analytics.ts
```

## 风险与预案

- Redis 旧 stats 缓存：缓存键 v2 + 开发环境 flushdb
- 生产数据量大时 sync 聚合：限定最近 30 条（ORDER BY id DESC LIMIT 30），无全表扫描
- `SyncTaskLog` 为空：所有 sync 字段 null → 前端显示"暂无同步记录"（Plan 假设条 1）
