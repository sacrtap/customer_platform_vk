# PRD: 余额燃尽列 — 趋势列重新设计为 burn-down 可视化

## Goal

将余额管理页面的「趋势」+「预计耗尽」两列合并为一个「余额燃尽」列，基于 `daily_consumptions` 表真实数据计算日均消耗率，以"油表"进度条直观显示客户余额还能支撑多少天。

## Background

### 当前问题

1. **计算数据源错误**：前端 `getDailyAvg = used_total / 30` 假设所有历史消耗发生在 30 天内。实际后端有 `daily_consumptions` 表按天记录真实消费数据未被利用。
2. **余额字段误用**：前端 `getDaysLeft` 使用 `record.total_amount` 作为"剩余余额"，但 `total_amount` 是累计充值额（充值时累加，扣款时不扣减），正确剩余余额应为 `real_amount + bonus_amount`。
3. **列功能冗余**：「趋势」和「预计耗尽」两列用同一套错误公式，信息重复。
4. **Home 页 bug**：`getPriorityCustomers` 中 `balance_days = total / (total/30)` 恒等于 30，计算无意义。
5. **颜色映射不反映紧迫度**：进度条颜色基于利用率百分比（50%/80%），而非剩余天数。

### 数据源

- `daily_consumptions` 表：`customer_id` + `consumption_date` + `total_cost`（按设备类型拆分）
- `customer_balances` 表：`real_amount`（当前实充余额）、`bonus_amount`（当前赠送余额），扣款时正确扣减
- `customers` 表：`settlement_type`（prepaid/postpaid）

## Requirements

### R1: 后端 — 余额列表 API 扩展

- `GET /billing/balances` 响应每条记录增加三个字段：
  - `daily_avg_cost: float | null` — 近 30 天日均消耗（无记录时 null）
  - `consumption_days: int` — 近 30 天有消费的天数
  - `days_remaining: int | null` — 预计剩余天数（null = 无消耗或后付费）
- 计算公式：`daily_avg = SUM(total_cost in 30d) / MAX(consumption_days, 7)`
- 剩余天数：`days_remaining = floor((real_amount + bonus_amount) / daily_avg)`
- 后付费客户（`settlement_type = 'postpaid'`）的三个字段均为 null

### R2: 后端 — 排序支持

- `sort_by=days_remaining` 时，SQL 层面 `ORDER BY days_remaining ASC NULLS LAST`
- 使用 CTE 批量聚合当前页客户的消费数据，避免 N+1

### R3: 后端 — Redis 缓存

- L1: `cache:billing_consumption:{customer_id}:{YYYY-MM-DD}`，TTL 300s
  - 存储该客户当天视角的 30 天消费聚合（total_cost_30d, consumption_days）
  - 使用 MGET 批量读取当前页客户的缓存
  - 同步任务完成时 `invalidate_pattern("cache:billing_consumption:*")`
- `_ttl_config` 新增 `"billing_consumption": 300`
- 充值/扣款时 `invalidate_pattern("cache:billing_balances:*")`（如果实现 L2）

### R4: 前端 — 燃尽进度条组件

- 合并「趋势」和「预计耗尽」两列为「余额燃尽」一列
- 进度条：满格 = 安全（剩余天数多），空 = 紧急（即将耗尽）
- 满刻度 60 天，超过显示 ">60天"
- 颜色阈值：≤7 天红 / 8-30 天橙 / >30 天绿 / 无消耗灰
- 核心数字显示：剩余 X天 / 已耗尽 / 无消耗 / >60天 / 今日耗尽（<1天）
- 后付费客户显示"后付费"标签
- tooltip：日均消耗、30天消费天数、距上次充值天数 + "预测基于近30天日均消耗，实际扣款以结算单为准"
- 数据覆盖率 <50% 时颜色降级（绿→橙）+ ⚠️图标

### R5: 前端 — 行高亮与排序

- 行高亮改为基于 `days_remaining`：≤7 天红色背景、≤30 天浅黄色背景
- 「余额燃尽」列支持点击排序（升序时 NULL 排最后）

### R6: 前端 — KPI 卡片

- 新增「即将耗尽」KPI 卡片，统计 `days_remaining ≤ 7` 的客户数
- 保留原「余额不足」卡片（固定金额阈值）
- 新增卡片支持点击筛选

### R7: 后端 — Home 页修复

- 修复 `getPriorityCustomers` 中 `balance_days` 的计算逻辑
- 使用相同的 30 天日均消耗公式
- 使用 `real_amount + bonus_amount` 作为剩余余额

## Acceptance Criteria

- [ ] AC1: `GET /billing/balances` 响应包含 `daily_avg_cost`、`consumption_days`、`days_remaining` 三个字段
- [ ] AC2: `sort_by=days_remaining` 排序正确，NULL 值排最后
- [ ] AC3: 后付费客户三个字段均为 null，前端显示"后付费"标签
- [ ] AC4: 余额燃尽进度条颜色与剩余天数阈值匹配（≤7红/8-30橙/>30绿/无消耗灰）
- [ ] AC5: 进度条满格表示安全（剩余天数多），空表示紧急
- [ ] AC6: 新客户（有余额无消费）显示灰色满格 + "无消耗"
- [ ] AC7: 零余额客户显示红色空格 + "已耗尽"
- [ ] AC8: tooltip 显示日均消耗、消费天数、预测说明
- [ ] AC9: 行高亮基于 days_remaining（≤7红/≤30黄）
- [ ] AC10: KPI「即将耗尽」卡片显示正确计数，点击可筛选
- [ ] AC11: Home 页 `balance_days` 不再恒等于 30
- [ ] AC12: Redis 缓存 key 格式正确，同步任务完成时 L1 失效
- [ ] AC13: 前端 `Balance` 接口类型扩展三个新字段
- [ ] AC14: 后端 `ruff check` 通过
- [ ] AC15: 前端 `pnpm type-check` 通过

## Constraints

- 不修改数据库 schema（不需要 migration）
- 不修改 `daily_consumptions` 表的写入逻辑
- 保持现有筛选条件与 KPI 卡片的一致性
- 充值后余额变化必须立即可见（不能被 L2 列表缓存阻挡）
