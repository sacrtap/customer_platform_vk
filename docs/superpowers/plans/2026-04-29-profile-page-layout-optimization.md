# 画像分析页面布局优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将房产客户占比模块改为标准 chart-card 样式，与规模等级分布一致，形成 2x2 网格布局。

**Architecture:** 单文件修改，Profile.vue 的模板结构、图表配置、CSS 样式三处改动，无新文件创建。

**Tech Stack:** Vue 3 + TypeScript + ECharts + Arco Design

---

### Task 1: 修改模板结构 - 房产客户占比融入 charts-grid

**Files:**
- Modify: `frontend/src/views/analytics/Profile.vue:32-86`

- [ ] **Step 1: 修改 charts-grid 区域，添加房产客户占比 chart-card**

将第 32-56 行的 `charts-grid` 替换为：

```vue
    <!-- 图表区域 -->
    <div class="charts-grid">
      <!-- 行业分布 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>行业分布</h3>
        </div>
        <div ref="industryChartRef" class="chart-container"></div>
      </div>

      <!-- 规模等级分布 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>规模等级分布</h3>
        </div>
        <div ref="scaleChartRef" class="chart-container"></div>
      </div>

      <!-- 消费等级分布 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>消费等级分布</h3>
        </div>
        <div ref="consumeLevelChartRef" class="chart-container"></div>
      </div>

      <!-- 房产客户占比 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>房产客户占比</h3>
        </div>
        <div ref="realEstateChartRef" class="chart-container"></div>
      </div>
    </div>
```

- [ ] **Step 2: 删除独立的 real-estate-section 区域**

删除第 58-86 行的整个 `<div class="real-estate-section">` 区块（包含其内部的 chart-card full-width、real-estate-content、统计列表等所有 HTML）。

删除后，模板中不再有 `real-estate-section`、`real-estate-content`、`real-estate-stats`、`stat-item`、`stat-dot`、`stat-info` 等自定义 class。

- [ ] **Step 3: 验证模板结构**

最终模板结构应为：
```
.profile-analysis-page
  ├── .page-header
  ├── .stats-grid (4个 stat-card)
  └── .charts-grid (4个 chart-card: 行业分布、规模等级分布、消费等级分布、房产客户占比)
```

---

### Task 2: 修改房产客户图表配置 - 与规模等级分布一致

**Files:**
- Modify: `frontend/src/views/analytics/Profile.vue:388-437` (initRealEstateChart 函数)

- [ ] **Step 1: 替换 initRealEstateChart 函数**

将第 388-437 行的 `initRealEstateChart` 函数替换为：

```typescript
// 初始化房产客户图表
const initRealEstateChart = (data: RealEstateData) => {
  if (!realEstateChartRef.value) return

  if (realEstateChart) {
    realEstateChart.dispose()
  }

  realEstateChart = echarts.init(realEstateChartRef.value)

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      textStyle: {
        color: '#646a73',
      },
    },
    series: [
      {
        name: '房产客户',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 2,
        },
        label: {
          show: false,
          position: 'center',
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold',
            color: '#1d2330',
          },
        },
        labelLine: {
          show: false,
        },
        data: [
          {
            name: '房产客户',
            value: data.real_estate_customers || 0,
            itemStyle: { color: '#f97316' },
          },
          {
            name: '非房产客户',
            value: data.non_real_estate_customers || 0,
            itemStyle: { color: '#9ca3af' },
          },
        ],
      },
    ],
  }

  realEstateChart.setOption(option)
}
```

**关键变更说明：**
- 添加 `legend` 配置：右侧垂直图例，与规模等级分布一致
- `radius` 从 `['50%', '70%']` 改为 `['40%', '70%']`
- 添加 `center: ['35%', '50%']`：饼图偏左，为右侧图例留空间
- 添加 `itemStyle`：`borderRadius: 8, borderColor: '#fff', borderWidth: 2`
- `label.show` 从 `true` 改为 `false`（默认不显示中心文字）
- `emphasis.label` 保持 hover 时显示中心百分比

---

### Task 3: 清理冗余 CSS 样式

**Files:**
- Modify: `frontend/src/views/analytics/Profile.vue:553-645` (style 部分)

- [ ] **Step 1: 删除不再需要的 CSS 类**

删除以下 CSS 类（第 557-619 行）：

```css
/* 删除这些类 */
.real-estate-section { ... }
.chart-card.full-width { ... }
.real-estate-content { ... }
.real-estate-chart { ... }
.real-estate-stats { ... }
.stat-item { ... }
.stat-dot { ... }
.stat-info { ... }
.stat-info .stat-label { ... }
.stat-info .stat-value { ... }
.stat-info .stat-percent { ... }
```

- [ ] **Step 2: 清理媒体查询中的冗余样式**

删除 `@media (max-width: 768px)` 中不再需要的样式（第 636-644 行）：

```css
/* 删除这些 */
.real-estate-content {
  flex-direction: column;
  align-items: stretch;
}

.real-estate-chart {
  width: 100%;
  height: 250px;
}
```

保留的媒体查询：
```css
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .charts-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
```

---

### Task 4: 验证与提交

**Files:**
- `frontend/src/views/analytics/Profile.vue`

- [ ] **Step 1: 运行前端类型检查**

```bash
cd frontend && npx vue-tsc --noEmit
```

预期：无类型错误

- [ ] **Step 2: 启动前端开发服务器，手动验证页面**

```bash
cd frontend && npm run dev
```

访问画像分析页面 (`/analytics/profile`)，验证：
1. 4 个图表卡片形成 2x2 网格布局
2. 房产客户占比卡片样式与规模等级分布一致
3. 房产客户占比饼图有右侧垂直图例
4. hover 饼图时中心显示百分比
5. 窗口缩放到 1200px 以下时，charts-grid 变为单列

- [ ] **Step 3: 提交更改**

```bash
git add frontend/src/views/analytics/Profile.vue
git commit -m "style(analytics): 统一房产客户占比与规模等级分布样式，优化页面布局为 2x2 网格"
```

---

## 自审检查

### 1. 规范覆盖检查

| 规范要求 | 对应 Task |
|----------|-----------|
| 房产客户占比改为标准 chart-card | Task 1 |
| 放入 charts-grid 形成 2x2 网格 | Task 1 |
| 饼图配置与规模等级一致 | Task 2 |
| 移除自定义 CSS 类 | Task 3 |
| 响应式布局正常 | Task 4 (验证) |

### 2. 占位符扫描

- ✅ 无 TBD/TODO
- ✅ 无 "类似 Task N" 的引用
- ✅ 所有代码步骤包含完整代码
- ✅ 所有测试步骤包含具体命令

### 3. 类型一致性

- `RealEstateData` 接口保持不变（第 117-120 行）
- `initRealEstateChart` 函数签名不变，仅修改内部配置
- 所有 ref 引用保持不变

### 4. 风险评估

- **低风险**：仅修改单文件的样式和图表配置，不影响业务逻辑
- **回滚简单**：git revert 即可恢复
