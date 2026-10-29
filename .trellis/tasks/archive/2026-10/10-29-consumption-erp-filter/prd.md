# 消耗分析页新增「ERP 系统」筛选项

## 需求

在「消耗分析」页（`frontend/src/views/analytics/Consumption.vue`）的筛选器中新增「ERP系统」下拉筛选项，
选项来源于客户管理页同一字典（`ErpSystem`：`label=name`、`value=value`），筛选值与客户管理中设定的
ERP 归属一致，并确保筛选在页面上**真实生效**（含缓存不被旧结果污染）。

## 背景 / 现状

- 该页筛选器注释明确为「统一筛选（趋势图 + 设备分布 + 客户排行共用）」，现有筛选项：
  时间范围、关键词、账号类型、行业、规模等级、消费等级、运营经理、销售经理。
- ERP 归属字段为 `Customer.erp_system`（`String(100)`），存的是 `ErpSystem.value`（如 `yonyou`/`kingdee`），
  字典接口 `GET /api/v1/erp-systems` 返回 `{id, name, value, sort_order}`。
- 仓库已有三处贯通先例，语义统一为 `Customer.erp_system == value` 精确匹配：
  客户列表（`services/customers.py:313-315`）、余额管理（`billing/balances.py:469`）、
  结算单（`services/billing.py:1484-1486`）。本次沿用同一口径，不新建第二套语义。
- 消耗分析三个后端端点均**已 join `Customer`**（`DailyConsumption.customer_id == Customer.id`），
  因此只需追加 where 条件，无需新增 join。

## 用户口径决策（已确认）

- 筛选范围：**三者共用，全部生效**（趋势图 / 客户排行 / 设备分布），与页内既有筛选行为一致。

## 验收标准

### AC1 前端筛选项
- 筛选栏出现「ERP系统」下拉，选项来自 `getErpSystemsList()`（`label=name`、`value=value`），
  加载失败不阻塞页面其他功能。
- 默认值为空（不筛选），与「账号类型」等不同——不引入默认过滤，避免数据被意外收窄。

### AC2 前端请求参数
- `filters` 新增 `erp_system: ''`；`handleReset` 一并重置为空。
- `getConsumptionTrend` / `getTopCustomers` / `getDeviceDistribution` 三个 API 签名新增
  `erp_system?: string`，仅在非空时拼参。

### AC3 后端筛选贯通（三端点）
- `/api/v1/analytics/consumption/trend`、`/consumption/top`、`/consumption/device-distribution`
  均接收 `erp_system` 查询参数并透传到 service。
- `get_consumption_trend_with_metric` / `get_top_customers_with_metric` /
  `get_device_type_distribution_with_metric` 新增 `erp_system` 参数，非空时
  `stmt.where(Customer.erp_system == erp_system)`。

### AC4 缓存正确性（关键）
- 三个端点的 Redis cache_key 必须包含 `erp_system`，否则切换 ERP 会命中旧缓存，
  表现为「筛选似生效但数据不变」。缓存 namespace 分别为
  `analytics_consumption_trend` / `analytics_top_customers` / `analytics_device_distribution`。

### AC5 数据可见性不受影响
- `mine_user_id` scope 约束逻辑保持原样；ERP 筛选只是在其上追加条件。

### AC6 空值与不存在值
- 空串 / 缺失 → 不加 where，返回全量（与现有筛选一致）。
- 传入不存在的 ERP value → 结果为空（数据/统计为空），非报错。

## 非目标

- 不改 `Customer.erp_system` 存储结构（保持字符串，不外键化）。
- 不做回款分析等其他分析页的 ERP 筛选。
- 不改导出逻辑（该页当前无导出）。

## 验证命令

```bash
cd backend && .venv/bin/python -m ruff check app/
cd backend && .venv/bin/python -m pyright app/routes/analytics.py app/services/analytics.py
cd frontend && pnpm type-check
cd frontend && npx eslint src/views/analytics/Consumption.vue src/api/analytics.ts
```
