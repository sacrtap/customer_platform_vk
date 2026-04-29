# 画像分析页面布局优化设计

**日期**: 2026-04-29
**状态**: 已批准

---

## 背景

画像分析页面 (`frontend/src/views/analytics/Profile.vue`) 中，房产客户占比模块使用了独立的 `real-estate-section` 样式，与规模等级分布等图表卡片的样式不一致，导致整体页面布局不够规整。

## 目标

将房产客户占比模块改为标准 `chart-card` 样式，与规模等级分布保持一致，使 4 个图表形成统一的 2x2 网格布局。

---

## 设计方案

### 布局变更

**变更前**:
```
stats-grid (4列统计卡片)
charts-grid
  ├── 行业分布 (chart-card)
  ├── 规模等级分布 (chart-card)
  └── 消费等级分布 (chart-card，单独占一行)
real-estate-section (独立区域，自定义样式)
  └── 房产客户占比 (饼图 + 统计列表)
```

**变更后**:
```
stats-grid (4列统计卡片)
charts-grid (2x2 网格)
  ├── 行业分布 (chart-card)
  ├── 规模等级分布 (chart-card)
  ├── 消费等级分布 (chart-card)
  └── 房产客户占比 (chart-card)
```

### 模板改动

1. 移除 `<div class="real-estate-section">` 外层包裹
2. 将房产客户占比改为标准 `<div class="chart-card">` 结构：
   ```vue
   <div class="chart-card">
     <div class="chart-header">
       <h3>房产客户占比</h3>
     </div>
     <div ref="realEstateChartRef" class="chart-container"></div>
   </div>
   ```
3. 移除自定义的 `real-estate-content` 和统计列表 HTML

### 图表配置改动

`initRealEstateChart` 函数更新为与 `initScaleChart` 一致的配置：

| 配置项 | 修改前 | 修改后 |
|--------|--------|--------|
| `radius` | `['50%', '70%']` | `['40%', '70%']` |
| `center` | 未设置 (默认居中) | `['35%', '50%']` |
| `legend` | 无 | 右侧垂直图例 |
| `itemStyle` | 无 | `borderRadius: 8, borderColor: '#fff', borderWidth: 2` |

### 样式移除

以下 CSS 类将被移除（不再需要）：
- `.real-estate-section`
- `.real-estate-content`
- `.real-estate-chart`
- `.real-estate-stats`
- `.stat-item`
- `.stat-dot`
- `.stat-info`
- `.stat-info .stat-label`
- `.stat-info .stat-value`
- `.stat-info .stat-percent`

---

## 影响范围

- **仅影响**: `frontend/src/views/analytics/Profile.vue`
- **不影响**: 后端 API、其他页面、组件库

---

## 验收标准

1. 房产客户占比模块使用标准 `chart-card` 样式
2. 4 个图表形成 2x2 网格布局
3. 房产客户占比饼图与规模等级分布样式一致（环形图 + 右侧图例）
4. 页面在 1200px 以下响应式正常（charts-grid 变为单列）
