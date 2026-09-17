# 运营工作台页面功能修复 — 实施计划

## 执行顺序（依赖序）

### Step 1 后端服务方法（services/analytics.py）
- [ ] 1.1 `get_consumption_trend_daily(start_date, end_date)`：按月聚合 DailyConsumption.total_cost，返回 `[{period, total_amount}]`（复用 `get_consumption_trend_with_metric` 的按日数据按月归并，或直接 SQL 按月 group by）
- [ ] 1.2 `get_customer_count_trend(start_date, end_date)`：按月统计当月有消耗的 distinct customer_id 数，返回 `[{period, customer_count}]`
- [ ] 1.3 `get_risk_customers(limit=20)`：流失风险客户（曾消耗但 90 天无消耗，`get_inactive_customers` 口径）+ 余额预警合并，返回 `[{customer_id, customer_name, score, risk_type, manager_name}]`
- [ ] 1.4 回归：新增方法不破坏既有（现有测试全绿）

### Step 2 后端路由修复（routes/analytics.py）
- [ ] 2.1 `get_dashboard_trend`：
  - consumption → `get_consumption_trend_daily`（period/total_amount）
  - payment → `get_payment_trend` 的 period/paid（修复 list.get 500）
  - customer_count → `get_customer_count_trend`（period/customer_count）
  - health → 当前风险客户计数单点（dates/values 等长），无历史则空数组
  - 统一返回 `{dates, values, metric}`
- [ ] 2.2 `get_priority_customers`：`health_stats.get("risk_customers")` → `service.get_risk_customers(limit)`，合并去重逻辑保留

### Step 3 前端 API 与页面（Home.vue + api/analytics.ts）
- [ ] 3.1 `api/analytics.ts`：新增 `getDashboardTrend(metric, months)`、`TrendResponse` 类型
- [ ] 3.2 `Home.vue`：
  - `.hero > * { min-width: 0 }`（问题 1）
  - `loadChartData` 按 activeTrendTab 映射 metric 请求 trend，`initChart` 适配 `{dates, values}`
  - 空数据显示「暂无数据」文案
  - watch 切 tab 时换 metric 重新加载
- [ ] 3.3 `Home.test.ts`：mock 适配 getDashboardTrend（consumption 数据），既有断言更新

### Step 4 验证（对照 prd.md AC1-AC8）
- [ ] 4.1 后端接口：trend 四 metric 结构正确无 500；priority-customers 非空
- [ ] 4.2 浏览器：hero 800/385、图表默认消耗折线、tab 切换、表格有行
- [ ] 4.3 回归：`pnpm type-check` + `pnpm build`、后端相关测试、全量测试失败数不增

## 验证命令
- 后端：`.venv/bin/python -m pytest tests/test_analytics_service.py tests/unit/services/test_analytics_service.py -q`
- 前端：`pnpm type-check && pnpm build && pnpm vitest run src/views/__tests__/Home.test.ts`
- 接口：curl trend 四 metric + priority-customers

## 回滚点
- 每个 Step 独立提交（Step1 后端服务 → Step2 路由 → Step3 前端 → Step4 测试/验证）
- 前端样式 min-width 改动独立小提交，可单独 revert

## 评审门
- Step 2 完成后：接口评审（对照 design.md 第 3/4 节）
- Step 3 完成后：前端交互评审（对照 prd AC1-AC4）
