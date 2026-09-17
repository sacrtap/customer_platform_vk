# 运营工作台页面功能修复 — 技术设计

## 1. 总览

三层缺陷：
- 布局层：grid 子项 `min-width: auto` 被 echarts canvas 固定宽度撑破 fr 分配
- 数据层：图表/表格的数据源选择错误或键缺失（Invoice 空表 / risk_customers 键不存在）
- 交互层：前端 tab 切换未切换数据源；后端 trend 接口各 metric 分支有 bug

修复策略：最小改动、前后端各修其责，不触碰其他页面分析逻辑。

## 2. 问题 1：hero 宽度

### 根因
`.hero { grid-template-columns: 1.35fr 0.65fr }`（global.css）。第一列 ChartCard 内 echarts canvas 有固定内联宽 762px（`chart-container` 宽度 762px），加上 ChartCard padding 18px*2 + border 1px*2 = min-content 800px > 1.35fr 计算值 799.9px。grid 子项默认 `min-width: auto`，fr 轨道被 min-content 撑开，第二列被压到 250px。

浏览器隔离实验证明：
- 给 hero 两子项 `min-width: 0` → 轨道 `799.875px 385.125px` ✓
- 隐藏第一列内容 → 同样恢复 ✓

### 修复
`frontend/src/views/Home.vue` scoped style 中为 hero 子项加：

```css
.hero > * {
  min-width: 0;   /* 允许 grid 轨道按 fr 收缩，不被 echarts canvas 撑破 */
}
```

同时 `.chart-container` 的 echarts 实例在容器 resize 时已有 `handleResize` 监听，canvas 会自动适配。

## 3. 问题 2：经营趋势图表

### 根因
1. 前端 `loadChartData` 固定请求 `/dashboard/chart-data` 并取 `data.consumption_trend`（Invoice 维度，本地空）
2. `watch(activeTrendTab)` 触发 `loadChartData(true)` 但仍取 consumption_trend → tab 切换无效
3. 后端 `/dashboard/trend` 各 metric 缺陷：
   - `payment`：`get_invoice_status_stats()` 返回 list，代码 `invoice_stats.get("monthly_trend")` → AttributeError 500
   - `customer_count`：`chart_data.get("customer_growth_trend", ...)`，但 `get_dashboard_chart_data` 只返回 `{consumption_trend, payment_trend}` → 空
   - `health`：`health_stats.get("monthly_trend", [])`，但 `get_customer_health_stats` 无该键 → 空

### 修复

#### 后端（routes/analytics.py `get_dashboard_trend`）
- **consumption**：改用 DailyConsumption 真实消耗数据。新服务方法 `get_consumption_trend_daily(start, end)`（按月聚合 `DailyConsumption.total_cost`），保留 Invoice 版 `get_consumption_trend` 给其他调用方
- **payment**：改用 `get_payment_trend(start, end, months)`（已存在，返回 `{period, invoiced, paid, completion_rate}`），取 `paid` 作为 values、`period` 作为 dates
- **customer_count**：新服务方法 `get_customer_count_trend(start, end)`：按月统计 `Customer.created_at` 当月新增数，或累计活跃客户数（用 DailyConsumption 有消耗的客户去重按月计数）。采用「当月有消耗的客户数」语义（与健康度活跃定义一致）
- **health**：新服务方法或直接取 `get_customer_health_stats` 的 `active_customers` 变化——但健康度无历史表，简化为返回当月活跃客户数（同 customer_count 口径可区分：健康度用 `warning_customers + churn_risk_customers` 总量作为单点，或按月活跃/总数）。**决定**：health metric 返回每月「健康度风险客户数（余额预警 + 流失风险）」——无历史数据时按月占位 0 或当前值，前端显示合理空态不报错。为满足 AC5 结构正确即可，语义上给出当前风险客户数的单月折线。

简化决策（避免过度设计）：三个非消耗 metric 的 values 用真实可算的月度聚合：
- payment：`get_payment_trend` 的 paid（结算单维度，本地空但结构正确）
- customer_count：按月「有消耗客户数」（DailyConsumption distinct customer_id）
- health：按月「消耗客户数中的风险占比」不可行（无历史评分），改为返回 `get_customer_health_stats` 的当前风险客户计数作为单点数组 + 前端友好空态

最终统一：所有 metric 返回 `{dates: [...], values: [...], metric}`，值数组与 dates 等长；无历史数据时数组含当前单点或空数组，前端对空数组显示「暂无数据」文案而非空白。

#### 前端（Home.vue + api/analytics.ts）
- `api/analytics.ts` 新增 `getDashboardTrend(metric, months)` → `GET /analytics/dashboard/trend`
- `Home.vue`：
  - `loadChartData` 改为按 `activeTrendTab` 映射 metric（consume→consumption, payment→payment, customers→customer_count, health→health）请求 trend 接口
  - `initChart` 改造为接收 `{dates, values}` 结构（x 轴 = dates，y 轴 = values）
  - 空数据时显示「暂无数据」覆盖层（非空白）
  - tab 切换 watch 传当前 metric 重新请求

## 4. 问题 3：今日优先跟进客户

### 根因
`get_priority_customers`（routes/analytics.py）：
- 余额预警 `get_balance_warning_list(threshold=1000)`：本地 balances 无 <1000 行 → 空
- `health_stats.get("risk_customers", [])`：`get_customer_health_stats` **没有该键** → 恒空

### 修复
`services/analytics.py` 新增 `get_risk_customers(limit)`：
- 基于 DailyConsumption 找「有消耗记录」的客户（90 天活跃）
- 对活跃客户查询 CustomerBalance，筛选 `real_amount + bonus_amount < threshold`（默认 1000）
- 合并「流失风险客户」（`get_inactive_customers`：曾消耗但最近 90 天无消耗）作为补充
- 返回 `[{customer_id, customer_name, score(0-100 估算), risk_type, manager_name}]`

`routes/analytics.py get_priority_customers` 改造：
- 移除 `health_stats.get("risk_customers", [])`（不存在）
- 改为调用 `service.get_risk_customers(limit)`，与余额预警合并去重
- 保留现有 customers 构建逻辑（health/health_class/consumption/balance_days/risk/manager 字段）

本地验证预期：`get_risk_customers` 用「曾消耗但最近 90 天无消耗」的流失风险客户（DailyConsumption 有 08-01~09-16 数据，8 月有消耗的客户到 9 月中旬算 inactive？注意 90 天窗口相对当前时间），配合余额预警合并后应有非空结果（至少流失风险客户有数据）。

## 5. 影响面

| 文件 | 改动 |
|---|---|
| frontend/src/views/Home.vue | hero min-width、loadChartData 按 tab 换源、initChart 适配 dates/values、空态文案 |
| frontend/src/api/analytics.ts | 新增 getDashboardTrend |
| frontend/src/views/__tests__/Home.test.ts | mock 适配 trend 接口 |
| backend/app/routes/analytics.py | get_dashboard_trend 各 metric 修复、get_priority_customers 用真实风险源 |
| backend/app/services/analytics.py | 新增 get_consumption_trend_daily / get_customer_count_trend / get_risk_customers |

不改动：`get_consumption_trend`（Invoice）及消耗分析页、`get_dashboard_chart_data` 接口本身（保留给潜在调用方）、认证与权限装饰器。
