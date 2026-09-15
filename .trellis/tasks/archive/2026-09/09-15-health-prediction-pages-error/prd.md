# 修复健康度分析与预测消费页面报错

## Goal

进入健康度分析、预测消费页面后出现 The application encountered an unexpected error 错误提示，业务页面无法正常使用。

## Background（排查结论，2026-09-16）

两个页面各有一个确定性 500 根因：

1. **健康度分析页 - 长期未消耗客户列表 500**
   - 接口：`GET /api/v1/analytics/health/inactive-list`（本地已复现 500）
   - 根因：`AnalyticsService.get_inactive_customers()`（`backend/app/services/analytics.py:992`）中
     `now = datetime.utcnow().date()`（`date` 类型）与 `row.last_consumption_date`
     （来自 `daily_consumptions.consumption_date`，迁移 `r7s8t9u0v1w2` 已改为
     `DateTime(timezone=True)`，返回 `datetime`）直接相减 →
     `TypeError: unsupported operand type(s) for -: 'datetime.date' and 'datetime.datetime'`

2. **预测消费页 - 单价配置/预测接口 500（远程按迁移部署时）**
   - 接口：`GET /api/v1/analytics/consumption/forecast`、`price-config` 等（依赖 `get_unit_prices()`）
   - 根因：`forecast_unit_prices` 表没有任何 alembic 迁移文件（模型
     `backend/app/models/forecast_config.py` 于提交 `3a9b2aa` 引入，但未附迁移；
     `backend/app/models/__init__.py` 也未 `import forecast_config`，alembic
     autogenerate 无法发现该表）。本地表为开发期手动创建，远程通过
     `alembic upgrade head` 部署时表缺失 → `select(ForecastUnitPrice)` 抛
     UndefinedTable → 接口 500。`get_unit_prices()` 仅在表存在且为空时回退
     默认单价，表缺失不兜底。

## Requirements

- 修复 `get_inactive_customers` 的类型错误，使 `/health/inactive-list` 正常返回 200 与客户列表
- 补建 `forecast_unit_prices` 表的 alembic 迁移，使远程按迁移部署后预测消费各接口正常
- 在 `models/__init__.py` 注册 `forecast_config` 模型，保证 alembic autogenerate 未来可发现

## Acceptance Criteria

- [x] `GET /api/v1/analytics/health/inactive-list?days=30&force_refresh=true` 返回 200 且包含客户列表
- [x] `GET /api/v1/analytics/consumption/forecast`、`price-config`、`data-readiness`、`forecast-trend` 返回 200
- [x] 新 alembic 迁移可执行（`alembic upgrade head` 无异常），`forecast_unit_prices` 表在全新库可创建
- [x] 单元测试覆盖：`get_inactive_customers` 日期计算、`get_unit_prices` 表缺失兜底
- [x] 现有测试集通过（覆盖率 ≥50% CI 门槛不回落）

## Notes

- 轻量 bug 修复任务，PRD-only（不需要 design.md / implement.md）
- 保持 `prd.md` 聚焦需求与验收标准
