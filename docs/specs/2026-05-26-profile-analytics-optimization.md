# 画像分析页面优化（房产行业子分类统计 + 图表替换）

> 归档来源：`.omo/drafts/profile-analytics-optimization.md`、`.omo/drafts/profile-analytics-optimization-spec.md`、`.omo/plans/profile-analytics-optimization.md`、`.omo/notepads/profile-analytics-optimization/{issues,learnings}.md`（2026-11-19 蒸馏合并，原件已删除）
> 状态：已实施 —— `backend/app/routes/analytics.py`（`/profile/real-estate-industry`）、`backend/app/services/analytics.py`（`get_real_estate_industry_stats`）、`frontend/src/api/analytics.ts`（`RealEstateIndustryItem` / `getRealEstateIndustryStats`）、`frontend/src/views/analytics/Profile.vue` 均在位
> 关联：`docs/specs/2026-06-12-scale-level-distribution-fixes.md`（规模等级 bug 的完整三次修复链，本篇仅记首修根因）
> 锚点说明：文中 `文件:行号` 为 2026-05/06 期快照，定位以符号名与路径为准

## Context

画像分析页三项需求：

1. 房产客户按行业子分类（房产经纪 / 房产ERP / 房产平台）统计
2. 规模等级分布按 S/A/B/C/D/E 分类（原有功能，本次带出 bug 修复）
3. 房产占比图由 2 分类改为 3 分类

**用户决策（2026-05-26，方案 A）**：替换第 4 个图表"房产客户占比"的数据源；顶部统计卡片口径不变（房产客户总数 + 总占比）；规模等级分布确认应按 S/A/B/C/D/E，代码已按 `scale_level` 分组，需排查分类维度为何不对。

## Approach

### 1. 后端：`AnalyticsService.get_real_estate_industry_stats()`

- JOIN 模式复用 `get_industry_distribution()`：`.outerjoin(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)`；过滤复用 `get_real_estate_stats()`：`CustomerProfile.is_real_estate` + `Customer.deleted_at IS NULL`
- `GROUP BY IndustryType.name`，NULL 显示为"未分类"；百分比 `round(count / total * 100, 2)`；`ORDER BY count DESC`
- 返回 `[{"industry": "房产经纪", "count": 15, "percentage": ...}, ...]`
- 不改 `get_industry_distribution()` / `get_real_estate_stats()`

### 2. 路由：`GET /api/v1/analytics/profile/real-estate-industry`

- `@auth_required`；完全复用 `/profile/real-estate` 模式：缓存检查 → service → 写缓存 → JSON
- 缓存 `cache_service.get/set("analytics_profile", ..., "real_estate_industry")`

### 3. 前端

- `frontend/src/api/analytics.ts` 新增 `RealEstateIndustryItem`（`{ industry, count }`）与 `getRealEstateIndustryStats()`
- `frontend/src/views/analytics/Profile.vue`：删除 2 分类饼图逻辑，第 4 图改为 3 分类环形饼图（自定义 3-5 色区别于行业分布图，tooltip `'{b}: {c} 家 ({d}%)'`，图例右侧）；统计卡片与行业分布图不动

### 4. 规模等级分类维度问题（首修根因）

`get_scale_level_stats()` 原实现两个问题：① `CustomerProfile.scale_level` 是 `String(50)` 无 CHECK 约束，直接 `GROUP BY` 会暴露 NULL、旧版遗留值（"大型/中型/小型"等）；② `ORDER BY count DESC` 顺序随数据分布漂移。修复：`CASE WHEN scale_level IN (S,A,B,C,D,E) THEN scale_level ELSE '未分类' END` 归一化 + Python 端按 `S→A→B→C→D→E→未分类` 固定顺序重排、过滤 count=0。**该 bug 后续又经历两次修复（空态 option 不全、刷新后缓存命中旧值），完整链路见 `docs/specs/2026-06-12-scale-level-distribution-fixes.md`。**

## Critical files & anchors

- `backend/app/services/analytics.py` — `get_real_estate_industry_stats()`；`get_scale_level_stats()` 归一化
- `backend/app/routes/analytics.py` — `/profile/real-estate-industry` 路由
- `frontend/src/api/analytics.ts` — `RealEstateIndustryItem` + `getRealEstateIndustryStats()`
- `frontend/src/views/analytics/Profile.vue` — 第 4 图数据源替换
- `backend/tests/test_analytics_service.py` — `TestGetRealEstateIndustryStats`

## Verification

- 单测类 `TestGetRealEstateIndustryStats` 三用例：success（3 行 dict mock：房产经纪/房产ERP/房产平台各 1，验证 count=1、percentage=33.33）、empty（空 mock → 空列表）、isolation（1 行 count=2 → percentage=100.0）
- mock 模式：dict 行 `{"name": "...", "count": N}` + 现有 `make_mock_execute_result()` + `analytics_service` fixture，全 mock 无真实库
- `pytest tests/test_analytics_service.py` → 53 passed / 1 failed（失败为预存 `test_get_industry_distribution_success` mock 问题，无关）
- 路由集成：`pytest tests/` 89 passed / 1 failed（预存集成问题，无关）；端点返回 `{"code": 0, "message": "success", "data": [...]}`
- `ruff check` / `ruff format` 通过；`npx vue-tsc --noEmit` ok；前端 build PASS
- 规模等级修复验证：`pytest tests/test_analytics_service.py` 53 passed（无 scale 专门用例）；`GET /profile/scale` 返回仅含 S/A/B/C/D/E/未分类

## Assumptions

- 房产统计继续读 `CustomerProfile`（当时 profile 尚未与 Customer 统一，见 `2026-05-29-is-real-estate-unify-and-filter-fixes.md`）。
- 图表配色自定义 3-5 色与行业分布图区分。

## 实施结果（截至 2026-11-19 核实）

- 上述四个落点均在位；规模等级分布的后续演进（空态渲染、缓存失效）已由 2026-06-12 两篇文档承接。
