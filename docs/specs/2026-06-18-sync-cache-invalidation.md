# 数据同步后消费分析缓存失效修复

> 归档来源：`.omo/plans/sync-cache-invalidation.md`、`.omo/drafts/sync-cache-invalidation.md`（2026-11-19 蒸馏合并，原件已删除）
> 状态：已实施 —— `backend/app/cache/base.py` 有 `invalidate_pattern`，并按 `cache:analytics_{category}_*` 通配清理
> 锚点说明：文中 `文件:行号` 为 2026-06 期快照，定位以符号名与路径为准

## Context

**现象**：在消费分析页点"数据同步"，同步成功返回后图表仍显示旧数据。

**根因链**：`routes/analytics.py::manual_sync_consumption` 里清缓存调用 `cache_service.delete(prefix)` 不带 parts → `_build_key(prefix)` 生成 `cache:analytics_consumption_trend:`（空前缀键），而真实缓存键带日期后缀，形如 `cache:analytics_consumption_trend:2026-01-01:2026-06-18:all` → 删的键不存在，**删除是空操作** → 缓存永不失效 → 持续服务旧数据。

## Approach

**决策**：3 个 `cache_service.delete(prefix)` 调用换 1 个 `cache_service.invalidate_pattern("cache:analytics_*")`，并加 info 日志记录清除的键数量。通配符一次覆盖所有 metric / 日期 / 客户变体，比逐个构造 pattern 更简洁。前端不动（`loadData()` 在同步后本就会重取）。

**范围护栏**：不做缓存预热（invalidate 后下次请求自动重建）；不清理路由中的 debug print（独立 scope）；不改 `Consumption.vue` / `api/analytics.ts` / `AnalyticsService` / `CacheService` 类本身；不加新端点或参数。

## Critical files & anchors

- `backend/app/routes/analytics.py` — `manual_sync_consumption` 内 `invalidate_pattern("cache:analytics_*")`
- `backend/app/cache/base.py` — `invalidate_pattern` 方法定义（现按 `cache:analytics_{category}_*` 通配清理）

## Verification

- `grep -n "invalidate_pattern" backend/app/routes/analytics.py` 命中 `manual_sync_consumption` 内调用；同函数内无 `cache_service.delete`
- 完整 API 流程：取 token → 调 `GET /api/v1/analytics/consumption/trend` 生成缓存 → 调 `POST /api/v1/analytics/consumption/sync` → `redis-cli keys "cache:analytics_*"` 返回空 → 再调 trend 返回新数据
- sync API 返回 `{"code": 0, "message": "同步成功", ...}`；`ruff check` 无新增错误
- Redis 未运行时 `invalidate_pattern` 自身 try/except 已 graceful 处理，无需额外兜底

## Assumptions

- 通配 `cache:analytics_*` 会连带清掉其他分析页缓存——可接受（同步后所有分析数据都应刷新）。
- 前端无需改动的依据是 `loadData()` 的既有重取逻辑，非本次新增。
