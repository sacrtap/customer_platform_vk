# 运营工作台页面功能修复

## Goal

运营工作台（Dashboard/Home）页面存在 3 个显示问题，需修复：
1. 「异常与待办」卡片宽度不正确（过窄，与「经营趋势」卡片比例失调）
2. 「经营趋势」图表未正确显示（空白，无折线/数据）
3. 「今日优先跟进客户」表格未正确显示（无数据行）

## 背景（根因调研结论）

**问题 1 根因**：`.hero` grid 布局 `1.35fr 0.65fr`，但第一列内容（echarts canvas 固定宽 762px + ChartCard padding 36px + border 2px = min-content 800px）超过 1.35fr 应得宽度（799.9px），grid 子项默认 `min-width: auto` 导致 fr 分配被内容撑破：第一列 800px、第二列被压缩至 250px（理论 385px）。**已验证修复**：给 hero 子项 `min-width: 0` 后轨道恢复 799.875px/385.125px。

**问题 2 根因**（前后端双层缺陷）：
- 前端 `loadChartData` 固定调用 `/dashboard/chart-data` 且只取 `data.consumption_trend`；后端该字段基于 **Invoice 表**（本地 0 行）→ 恒空数组 → 图表空白
- 前端 4 个 tab（消耗/回款/客户数/健康度）切换时 `watch(activeTrendTab)` 仍只请求 consumption_trend，**未按 tab 切换数据源**
- 后端已有 `/dashboard/trend?metric=xxx` 多指标接口但存在缺陷：payment 分支 `get_invoice_status_stats()` 返回 **list** 却调用 `.get("monthly_trend")` → 500；customer_count 分支读取不存在的 `customer_growth_trend` 键 → 空；health 分支读取不存在的 `monthly_trend` 键 → 空

**问题 3 根因**：`/priority-customers` 两个数据源均为空：
- 余额预警 `get_balance_warning_list(threshold=1000)`：本地 `customer_balances` 表仅 1 行且 total_amount ≥ 1000 → 空
- 健康度风险 `health_stats.get("risk_customers", [])`：**`get_customer_health_stats` 返回值根本没有 `risk_customers` 键**（只有计数）→ 恒空列表
- 结果 customers 恒为 [] → 表格 0 行

## Requirements

### R1 修复「异常与待办」卡片宽度
- hero 两卡片按 1.35fr / 0.65fr 正确分配，第二列恢复到理论宽度（385px 量级），不被第一列内容撑破
- 图表容器不被压缩后仍正常渲染（canvas 自适应容器宽度）

### R2 修复「经营趋势」图表显示
- 页面加载后图表默认显示「消耗」趋势数据（基于真实消耗数据源 DailyConsumption，本地有 3168 行真实数据）
- 4 个 tab（消耗/回款/客户数/健康度）点击后图表切换为对应指标数据
- 后端 `/dashboard/trend` 各 metric 返回正确结构 `{dates, values, metric}`，无 500 错误

### R3 修复「今日优先跟进客户」表格
- 表格展示实际客户数据行（含客户、健康度、本月消耗、余额可用、风险、负责人、下一步）
- 数据来源：余额预警 + 健康度风险客户合并去重（风险客户来源需真实可查）
- 本地数据可用时表格应有数据；无数据时显示友好空态而非空白

## Acceptance Criteria

- [ ] AC1 浏览器实测：hero 两卡片宽度约为 800px / 385px（1.35fr / 0.65fr），「异常与待办」内容完整显示不被截断
- [ ] AC2 浏览器实测：「经营趋势」图表默认显示消耗折线（有数据点/坐标轴），非空白
- [ ] AC3 浏览器实测：点击「回款」「客户数」「健康度」tab，图表切换为对应数据（或显示合理空态，不报错）
- [ ] AC4 浏览器实测：「今日优先跟进客户」表格显示数据行（≥1 行，含各字段）
- [ ] AC5 接口验证：`GET /api/v1/analytics/dashboard/trend?metric=consumption|payment|customer_count|health` 均返回 code=0 且 data 含 dates/values
- [ ] AC6 接口验证：`GET /api/v1/analytics/priority-customers` 返回非空 customers 列表（本地数据下）
- [ ] AC7 回归：前端 `pnpm type-check` + `pnpm build` 通过；Home.vue 既有单元测试适配后通过；后端相关测试通过
- [ ] AC8 无新增回归：全量后端测试中既有失败数量不增加（基线 28 failed + 3 errors）

## Notes

- 涉及文件：`frontend/src/views/Home.vue`、`frontend/src/api/analytics.ts`、`backend/app/routes/analytics.py`、`backend/app/services/analytics.py`、`frontend/src/views/__tests__/Home.test.ts`
- 不修改其他页面的分析逻辑；`get_consumption_trend`（Invoice 维度）保留给其他调用方
- 项目硬规则：中文回复/注释、文件修改前先读、`@auth_required` 不改动
