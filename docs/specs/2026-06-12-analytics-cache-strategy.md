# 画像分析缓存策略优化与强制刷新

> 归档来源：`.omo/plans/画像分析缓存优化-长期方案.md`（提案版）、`.omo/plans/analytics-cache-optimization.md`（已完成版）、`.omo/plans/画像分析页面缓存刷新功能.md`、`.omo/evidence/analytics-cache-optimization-complete.md`（2026-11-19 蒸馏合并，原件已删除）
> 状态：已实施 —— `backend/app/routes/analytics.py` 各统计端点均以 `cache_service.get/set(namespace, cache_key)` 带 key 调用（如 `analytics.py` 的 `real_estate_industry:{hour_bucket}:scope:{...}`）；`force_refresh` 生效
> 关联：`docs/specs/2026-06-12-scale-level-distribution-fixes.md`（"刷新后消失"与本篇共用同一根因：固定缓存键 + 首屏无 force_refresh）
> 锚点说明：文中 `文件:行号` 为 2026-06 期快照，定位以符号名与路径为准

## Context

**问题**：画像分析页 Redis 固定缓存键（`cache:analytics_profile:*`）无法区分新旧数据、无失效机制——F5 刷新后首次加载仍命中旧缓存，用户改完 `scale_level` 看不到变化。

## Approach

三方案叠加，构成"时间戳过期 + TTL 过期 + 主动清除"三重保险。实施优先级与实测：方案 1（P0，预估 15min，实测 ~20min）→ 方案 3（P1，预估 20min，实测含在方案 1 内）→ 方案 2（P2，预估 45min，实测 ~10min），总计 ~45min。

### 方案 1：时间戳/版本化缓存键（每小时自动失效）

```python
hour_bucket = int(time.time() // 3600)
cached_key = f"analytics_profile:{key}:{hour_bucket}"
cached = await cache_service.get("analytics_profile", cached_key) if not force_refresh else None
```

覆盖 `routes/analytics.py` 全部 5 个 `/analytics/profile/*` 端点（industry / scale / consume-level / real-estate / real-estate-industry）。hour_bucket 跨小时即换键，旧键自然废弃。

### 方案 2：数据变更主动清缓存

`services/customers.py` 新增 `clear_analytics_cache()`，删除 5 个画像缓存键（industry / scale / consume_level / real_estate / real_estate_industry），调用点两处：`update_customer()` 返回前、`batch_update_customers()` 提交事务后。

### 方案 3：统一 TTL 5 分钟

```python
if not force_refresh:
    await cache_service.set("analytics_profile", result, f"{key}:{hour_bucket}", ttl=300)
```

即使 hour_bucket 未变，缓存 5 分钟后自动过期重取。监控指标（命中率 / 过期次数 / 平均响应时间）列为后续项，本次未实现。

### 附带：`force_refresh` 强制刷新机制

- 后端：读 `request.args.get("force_refresh")`；为 true 时跳过 get；且**强制刷新时不写缓存**（避免把强制结果固化回同一键）
- 前端 `Profile.vue`：header 加"刷新"按钮（loading 态），`handleRefresh` → `loadData({ force_refresh: true })` → 成功 toast"已刷新"
- `api/analytics.ts`：4 个画像接口（`getScaleStats` / `getConsumeLevelStats` / `getRealEstateStats` / `getRealEstateIndustryStats`）增加可选 params 透传

## Critical files & anchors

- `backend/app/routes/analytics.py` — 5 个端点：时间戳键 + `force_refresh` + `ttl=300`
- `backend/app/services/customers.py` — `clear_analytics_cache()` 及 2 个调用点
- `frontend/src/api/analytics.ts` — 4 个接口可选参数
- `frontend/src/views/analytics/Profile.vue` — 刷新按钮与 `handleRefresh`

## Verification

- 验收（方案 1）：F5 后看到最新数据（配合前端强制刷新）；缓存键形如 `analytics_profile:scale:{hour_bucket}`；一小时后自动失效
- 验收（方案 2）：改 `scale_level` 后 `clear_analytics_cache()` 被调用（2 个调用点）；不影响其他功能
- 验收（方案 3）：Redis 项 TTL=300s；频繁更新不堆积
- 构建：`npm run build` / `vue-tsc` / `ruff check` 均通过；`python -m py_compile` 两个后端文件通过
- 改动量：后端 `routes/analytics.py` +38/-0（另一份记录为 +47/-12，含前端提交前的中间态）、`services/customers.py` +29/-0；前端 `api/analytics.ts` +8/-10、`Profile.vue` +59/-13；合计约 +134/-22

## Assumptions

- 监控中间件（`cache_monitor.py`）与专用 `DELETE /analytics/profile/cache` 端点当时列为可选项，未实现。
- 首屏（onMounted）不带 `force_refresh`，跨小时前仍可能命中旧值——该残留问题次日由规模等级三修解决，见 Step 7 文档。

## 实施结果（截至 2026-11-19 核实）

- 时间戳键 + TTL + 主动清除 + `force_refresh` 均在线；现存键带 `:{hour_bucket}:scope:{...}` 后缀，方案已演进为按 scope 细化。
