# 健康度评估排除规则优化

## Goal

客户详情页健康度评分（`get_customer_health_score`）排除以下客户，不进行评估：

1. **不结算**：`is_settlement_enabled = False`
2. **客户测试账号**：`account_type = '客户测试账号'`
3. **内部账号**：`account_type = '内部账号'`（用户口述「内容账号」，经确认即「内部账号」，不新增类型）

## Background（调研结论）

- **健康度是否有具体字段**：否。`Customer` 表无 `health_score` 字段，健康度为实时计算（`get_customer_health_score`，权重：用量达标率 50% + 余额充足率 30% + 回款及时率 20%）。
- **与健康度分析页的关联**：分析页（`Health.vue` / `get_customer_health_stats`）基于 90 天消耗活跃度 + 余额预警，与详情页评分是**两套独立逻辑**，无共享字段。本次不改动分析页。
- 当前 `get_customer_health_score` 对所有客户无差别计算，未排除任何账号。

## Requirements

- `get_customer_health_score` 开头查询客户信息；命中排除条件时直接返回 `score: null`、`level: '不适用'`（或等价语义），跳过评分计算。
- 前端 `CustomerProfileTab.vue` / `HealthGauge.vue` 对 `score == null` 展示「不参与评估」提示（替代仪表盘）。
- 前端类型 `CustomerHealthScore`（`api/analytics.ts`）的 `score` / `level` 允许 null。

## Constraints

- 仅改详情页评分链路；健康度分析页（`get_customer_health_stats`、预警/未消耗列表）行为不变。
- 不新增数据库字段，不做数据迁移。

## Acceptance Criteria

- [ ] 不结算客户：详情页不显示分数，展示「不参与评估」。
- [ ] 客户测试账号、内部账号：详情页不显示分数，展示「不参与评估」。
- [ ] 正常客户（结算且为正式账号）：评分计算与展示与现状一致。
- [ ] 后端测试：`test_analytics_service.py` 增加排除规则用例（三种排除对象 + 正常客户对照）。
- [ ] 健康度分析页统计数字不受影响。
