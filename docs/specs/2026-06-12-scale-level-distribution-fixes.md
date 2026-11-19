# 规模等级分布 bug 三次修复全记录

> 归档来源：`.omo/drafts/规模等级分布-bug-investigation.md`、`规模等级分布-bug-root-cause.md`、`.omo/plans/规模等级分布-bug-fix-plan.md`、`-bug-fix-plan-finalized.md`、`-前端修复实施.md`、`.omo/evidence/规模等级分布-{debug-complete,debug-summary,第二次修复完成}.md`、`规模等级刷新后消失-root-cause.md`、`规模等级刷新问题-修复完成.md`（2026-11-19 蒸馏合并，原件已删除）
> 状态：已实施 —— `frontend/src/views/analytics/Profile.vue::initScaleChart` 现保留 `hasValidLevels` 判定（`item.scale_level !== '未分类'`）与 `item.scale_level || '未知'` 兜底
> 关联：`docs/specs/2026-05-26-profile-analytics-optimization.md`（分类归一化首修）、`docs/specs/2026-06-12-analytics-cache-strategy.md`（阶段四依赖的服务端缓存改造）
> 锚点说明：文中 `文件:行号` 为 2026-06 期快照，定位以符号名与路径为准

## Context

同一 bug（画像分析页"规模等级分布"饼图异常）在 2026-06-11 一天内被连改三次：数据全 NULL 导致单扇区 → 首修空态容错引入"图表完全不显示" → 二修补好 ECharts option → F5 又暴露缓存旧值。本篇按因果链四阶段讲清全过程。

## Approach

### 阶段一：现象与数据（根因）

饼图只有一个 100% 的"未分类"扇区。数据流：`Profile.vue.loadScaleData()` → `getScaleStats()` → `GET /api/v1/analytics/profile/scale` → `get_scale_level_stats()` → `CustomerProfile.scale_level`。

原始查询结果：

```sql
SELECT COALESCE(scale_level, '-'), COUNT(*) FROM customer_profiles ... GROUP BY scale_level;
-- NULL : 1234
```

`CustomerProfile.scale_level` 为 `varchar(50)`、nullable、无默认值，**全部 1324 条记录为 NULL**（对比：`consume_level` 有 147 个非 NULL 值 C1-C5，图表正常）。后端 `case` 语句把 NULL 归为"未分类" → API 返回单条记录 → 单扇区饼图。属历史数据未填充，非代码缺陷。

### 阶段二：首修引入的新故障（图表完全不显示）

按"前端容错 + 友好显示"方向修复：`initScaleChart()` 开头加 `hasValidLevels` 检查，无有效等级时清空图表并 `setOption` 占位。但首版实现有错：

```javascript
// ❌ 首修错误实现（Profile.vue 258-279 行）
scaleChart = echarts.init(scaleChartRef.value)  // 分支内重复 init
scaleChart.clear()                              // 清空渲染上下文
scaleChart.setOption({
  series: [
    {
      center: ['35%', '50%'],                   // center 位置错误
      label: { ... }                            // 缺 type/radius/name/data
    }
  ]
})
```

后果：图表区域空白。结论：**`clear()` 后必须给完整 option**——空态也要符合 ECharts schema。

### 阶段三：二修正确写法

空态分支改为一次 `setOption` 完整配置（移除分支内重复 init 与 `clear()`）：

```javascript
const option = {
  tooltip: { show: false },      // 关闭提示框
  legend: { show: false },       // 关闭图例
  series: [
    {
      name: '规模等级',
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      data: [],                  // 空数组，不渲染扇区
      label: {
        show: true,
        position: 'center',
        formatter: '-',
        fontSize: 24,
        color: '#999',
        fontWeight: 'lighter',
      },
    },
  ],
}
scaleChart.setOption(option)
```

验证：`npm run build` 通过、`vue-tsc` 通过、1855 模块转换无错误。

### 阶段四：三修（F5 刷新后消失）

业务录入 1 条 S 等级后：点"刷新"按钮图表正确显示 S 扇区；但浏览器 F5 后又变回占位符 "-"。

- 彼时数据库查询结果已是 `S: 1 / NULL: 1323`，但 Redis 固定键 `cache:analytics_profile:scale` 仍缓存着全"未分类"的旧值
- F5 → `onMounted()` → `loadData()` 不带 `force_refresh` → 后端命中旧缓存直接返回 → 前端 `hasValidLevels=false` → 占位符
- 点刷新按钮走 `force_refresh=true` 跳过缓存，故正确

修复：前端 `onMounted` 首次加载改 `loadData({ force_refresh: true })`（首屏强制刷新）；根治靠服务端版本化/失效缓存（时间戳键 + 主动清除 + TTL，见 `docs/specs/2026-06-12-analytics-cache-strategy.md`）。结论：**首屏强制刷新 + 服务端版本化/失效缓存**，二者缺一仍会复现。

### 用户业务规则决策（2026-06-11，原文照搬）

| 问题 | 用户决策 |
|-----|---------|
| 客户创建时是否自动设置 scale_level？ | ❌ **不自动设置**，允许保留 NULL |
| 后台维护时是否自动填充？ | ❌ **不自动填充**，允许保留 NULL |
| 前端图表空值如何显示？ | `"-"`（而不是"未分类"） |
| 是否需要 SQL 批量初始化？ | ❌ **取消批量初始化** |
| 后续数据来源？ | 由业务人员手动维护和更新 |

原 P0 方案"SQL 批量初始化为 E 级"与 NOT NULL 约束因此**取消**；保留项：前端图表优化（P0）、数据补全工具（P1）、数据库 CHECK 约束（P2，可选）。

## Critical files & anchors

- `frontend/src/views/analytics/Profile.vue` — `initScaleChart()`：`hasValidLevels` 检查 + 空态完整 option；`onMounted` 首屏 force_refresh
- `backend/app/routes/analytics.py` — `get_scale_stats()`：`force_refresh` 参数与固定缓存键（阶段四根因，后由缓存策略篇改造）
- `backend/app/services/analytics.py` — `get_scale_level_stats()`：`case` 归一化（S/A/B/C/D/E，否则"未分类"）
- `backend/app/models/customers.py` — `CustomerProfile.scale_level`：`varchar(50)` nullable 无默认值

## Verification

- 三场景表（最终态）：全 NULL → 中心灰色"-"；部分有值 → 只显示有值扇区；全部有效 → 正常 S/A/B/C/D/E 饼图
- `npm run build` / `vue-tsc` 通过；不影响行业分布、消费等级、房产占比三个图表
- F5 复现路径：`redis-cli DEL cache:analytics_profile:scale` 后 F5 应见 S 扇区（阶段四验收项）

## Assumptions

- 阶段一的"批量初始化 E 级"被用户明确否决，空值保留 NULL 是产品决策而非数据缺陷。
- ECharts 空态渲染必须给完整 pie option（缺 `type`/`radius`/`name`/`data` 即不渲染）——本案例两次踩中。

## 实施结果（截至 2026-11-19 核实）

- `initScaleChart` 保留 `hasValidLevels` 判定与 `item.scale_level || '未知'` 兜底；服务端缓存已演进为带 `hour_bucket`/scope 的键，阶段四根因（固定键）已消除。
