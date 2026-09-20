# Implement — 健康度评估排除规则

## 步骤

1. **后端 `services/analytics.py`** `get_customer_health_score`：
   - 方法开头查询 Customer（确认 Customer 已 import，缺失则补 `from ..models.customers import Customer`）。
   - 排除判断（is_settlement_enabled is False OR account_type in ('客户测试账号','内部账号')）命中则提前返回
     `{score: None, usage_rate: None, balance_rate: None, payment_rate: None, health_level: 'not_applicable'}`。
2. **前端 `api/analytics.ts`**：`CustomerHealthScore.score` 改为 `number | null`；`level`/`health_level` 字段修正（对齐后端实际返回 `health_level`）。
3. **前端 `CustomerProfileTab.vue`**：
   - `score === null` 分支显示「该客户不参与健康度评估」文案。
   - HealthGauge 的 `level` 传 `health_score.health_level`（修正现存 undefined 问题）。
4. **后端测试** `backend/tests/test_analytics_service.py`：新增 4 个用例——不结算 / 客户测试账号 / 内部账号 / 正常客户对照。

## 验证

- 后端：`cd backend && $BACKEND_DIR/.venv/bin/python -m pytest tests/test_analytics_service.py -q`
- 前端：类型检查 + dev server 实际操作：编辑一个测试账号客户的详情页，确认显示「不参与评估」；正常客户评分正常
- 确认健康度分析页统计不受影响（`get_health_stats` 无改动）

## 回滚点

- 后端排除分支可独立 revert；前端 null 分支不影响正常客户展示。
