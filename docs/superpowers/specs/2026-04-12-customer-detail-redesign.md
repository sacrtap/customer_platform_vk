# 客户详情页面重构设计文档

**文档 ID**: SPEC-2026-04-12-001  
**创建日期**: 2026-04-12  
**状态**: 待审批  
**负责人**: @frontend-dev  

---

## 1. 概述

### 1.1 重构目标

重构客户管理模块下的客户详情页面，提升视觉美观度、信息展示效率和用户体验，打造现代化企业级 SaaS 产品体验。

### 1.2 设计原则

- **现代企业风** - 清爽专业，增强卡片层次，引入数据可视化面板
- **信息层次清晰** - 通过视觉权重区分信息优先级
- **数据驱动** - 增加图表可视化，让数据更直观
- **交互流畅** - 适度的动效提升使用愉悦感

### 1.3 重构范围

| 模块 | 变更类型 | 说明 |
|------|----------|------|
| 基础信息 Tab | 视觉优化 | 表格改卡片式布局 |
| 画像信息 Tab | 新增组件 | 消费等级进度条、健康度指标卡 |
| 余额信息 Tab | 新增组件 | 余额趋势图（折线图） |
| 结算单 Tab | 视觉优化 | 表格样式优化 |
| 用量数据 Tab | 新增组件 | 用量分布图（环形图） |

---

## 2. 视觉设计规范

### 2.1 色彩体系

保持现有主色调，确保品牌一致性：

```css
/* 主色调 */
--primary-6: #0369A1;      /* 深蓝 - 主按钮、强调色 */
--primary-1: #E8F3FF;      /* 浅蓝 - 背景、hover 状态 */

/* 中性色 */
--neutral-10: #1D2330;     /* 深灰 - 主标题 */
--neutral-6: #646A73;      /* 中灰 - 次要文字、标签 */
--neutral-2: #EEF0F3;      /* 浅灰 - 边框、分割线 */
--neutral-1: #F7F8FA;      /* 极浅灰 - 背景色 */

/* 功能色 */
--success-color: #22C55E;  /* 成功、健康 */
--success-bg: #E8FFEA;
--warning-color: #F59E0B;  /* 警告、预警 */
--warning-bg: #FFF7E8;
--danger-color: #EF4444;   /* 危险、欠费 */
--danger-bg: #FFE8E8;
```

### 2.2 卡片风格

**轻微阴影 + 白色背景** - 清爽专业风格：

```css
.card-base {
  background: #FFFFFF;
  border: 1px solid var(--neutral-2);
  border-radius: 10px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
  transition: all 250ms cubic-bezier(0.4, 0, 0.2, 1);
}

.card-base:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  border-color: var(--primary-1);
}
```

### 2.3 动效规范

**适中程度** - 卡片入场动画 + 数据刷新动效：

| 动效类型 | 时长 | 缓动函数 | 应用场景 |
|----------|------|----------|----------|
| 入场动画 | 300ms | cubic-bezier(0.4, 0, 0.2, 1) | 卡片加载、Tab 切换 |
| Hover 反馈 | 150ms | cubic-bezier(0.4, 0, 0.2, 1) | 卡片、按钮悬停 |
| 数据刷新 | 400ms | cubic-bezier(0.4, 0, 0.6, 1) | 数字变化、进度条 |
| 加载骨架 | 1.5s | ease-in-out infinite | 数据加载占位 |

---

## 3. 详细设计

### 3.1 基础信息 Tab

#### 3.1.1 布局变更

**原设计**：传统两列表格  
**新设计**：卡片式网格布局

```
┌─────────────────────────────────────────────────────────┐
│  🏢 客户名称卡片（突出显示，带重点标识）                  │
├─────────────┬─────────────┬─────────────┬──────────────┤
│  公司 ID    │  账号类型   │  业务类型   │  客户等级    │
│  [值]       │  [值 +Tag]  │  [值 +Tag]  │  [值 +Tag]   │
├─────────────┼─────────────┼─────────────┼──────────────┤
│  结算方式   │  结算周期   │  邮箱       │  创建时间    │
│  [值 +Tag]  │  [值]       │  [值]       │  [值]        │
├─────────────────────────────────────────────────────────┤
│  🏷️ 客户标签区域（标签云样式）                           │
└─────────────────────────────────────────────────────────┘
```

#### 3.1.2 组件规格

**客户名称卡片**：
- 尺寸： fullWidth × 80px
- 样式：渐变背景 `linear-gradient(135deg, var(--primary-1), #FFFFFF)`
- 内容：客户名称 + 重点客户徽章（红色）+ 运营经理头像
- 操作：右侧固定"编辑"和"设为重点"按钮

**信息卡片单元**：
- 尺寸：4 列网格，最小宽度 200px
- 样式：白色背景 + 轻微阴影
- 标签：12px / 600 / --neutral-6 / uppercase
- 值：14px / 500 / --neutral-10
- 交互：hover 时轻微上浮 + 阴影加深

**标签云区域**：
- 布局：flex wrap，gap 8px
- 标签样式：Arcoblue 主题色，可关闭
- 添加按钮：虚线边框，hover 变实线

---

### 3.2 画像信息 Tab

#### 3.2.1 布局结构

```
┌─────────────────────────────────────────────────────────┐
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ 规模等级    │  │ 消费等级    │  │ 健康度指标卡    │  │
│  │ [徽章展示]  │  │ [进度条]    │  │ [圆形进度环]    │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐                        │
│  │ 所属行业    │  │ 房地产行业  │                        │
│  │ [值]        │  │ [Tag]       │                        │
│  └─────────────┘  └─────────────┘                        │
└─────────────────────────────────────────────────────────┘
```

#### 3.2.2 新增组件规格

**消费等级进度条**：
- 数据结构：`{ level: 'A', progress: 0.6, nextLevel: 'KA' }`
- 视觉：分段式进度条，显示当前等级和下一级
- 颜色：根据等级使用不同颜色（C→B→A→KA：橙→蓝→绿→紫）
- 尺寸：高度 8px，圆角 4px

**健康度指标卡**：
- 类型：圆形进度环（Donut Chart）
- 尺寸：直径 120px
- 数据：综合评分（0-100）
- 颜色映射：
  - 80-100：绿色（健康）
  - 60-79：黄色（亚健康）
  - 0-59：红色（不健康）
- 中心文字：显示分数 + 等级描述

**计算公式**：
```
健康度 = 用量达标率 × 50% + 余额充足率 × 30% + 回款及时率 × 20%

用量达标率 = min(实际用量 / 预期用量, 1.0) × 100
余额充足率 = min(当前余额 / 月均消耗, 1.0) × 100
回款及时率 = 按时付款结算单数 / 总结算单数 × 100
```

---

### 3.3 余额信息 Tab

#### 3.3.1 布局结构

```
┌─────────────────────────────────────────────────────────┐
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │
│  │总余额  │ │实充余额│ │赠送余额│ │已消耗  │           │
│  │[金额]  │ │[金额]  │ │[金额]  │ │[金额]  │           │
│  └────────┘ └────────┘ └────────┘ └────────┘           │
├─────────────────────────────────────────────────────────┤
│  📈 余额趋势图（近 6 个月）                               │
│  ┌─────────────────────────────────────────────────────┐│
│  │ [折线图：X 轴月份，Y 轴金额，三条线（总余额/实充/赠送）]││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

#### 3.3.2 新增组件规格

**余额趋势图**：
- 类型：多系列折线图
- 数据范围：近 6 个月（按月聚合）
- 系列：
  - 总余额（蓝色实线）
  - 实充余额（绿色实线）
  - 赠送余额（橙色虚线）
- 交互：hover 显示具体数值 tooltip
- 尺寸：高度 300px

---

### 3.4 结算单 Tab

#### 3.4.1 优化内容

- 表格行高增加至 56px
- 状态列使用徽章 + 颜色编码
- 金额列右对齐，使用等宽字体
- 添加金额汇总行（显示选中结算单总额）

---

### 3.5 用量数据 Tab

#### 3.5.1 布局结构

```
┌─────────────────────────────────────────────────────────┐
│  ┌─────────────────┐  ┌─────────────────────────────┐   │
│  │ 用量分布图      │  │ 用量统计卡片                 │   │
│  │ [环形图]        │  │ - 总用量                     │   │
│  │                 │  │ - 日均用量                   │   │
│  │                 │  │ - 峰值日期                   │   │
│  └─────────────────┘  └─────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  [用量数据表格（分页）]                                  │
└─────────────────────────────────────────────────────────┘
```

#### 3.5.2 新增组件规格

**用量分布图**：
- 类型：环形图（Donut Chart）
- 数据：按设备类型聚合用量
- 中心：显示总用量
- 图例：右侧显示，带颜色标识
- 交互：hover 高亮扇区 + 显示百分比

**用量统计卡片**：
- 数量：3 张（总用量、日均用量、峰值日期）
- 样式：与余额卡片一致
- 数字：使用等宽字体（tabular-nums）

---

## 4. 后端 API 需求

### 4.1 需要新增的 API

#### 4.1.1 余额趋势 API

```
GET /api/v1/billing/customers/<customer_id>/balance/trend

Query Parameters:
  - months: number (默认 6，最大 12)

Response:
{
  "code": 0,
  "message": "success",
  "data": {
    "customer_id": 1,
    "trend": [
      {
        "month": "2025-10",
        "total_amount": 50000.00,
        "real_amount": 40000.00,
        "bonus_amount": 10000.00
      },
      ...
    ]
  }
}
```

**实现说明**：
- 基于 `RechargeRecord` 和 `ConsumptionRecord` 按月聚合
- 计算每月末余额快照

#### 4.1.2 客户健康度评分 API

```
GET /api/v1/analytics/health/customers/<customer_id>/score

Response:
{
  "code": 0,
  "message": "success",
  "data": {
    "customer_id": 1,
    "health_score": 85.5,
    "health_level": "健康",
    "components": {
      "usage_rate": 92.0,      // 用量达标率
      "balance_rate": 75.0,    // 余额充足率
      "payment_rate": 90.0     // 回款及时率
    },
    "weights": {
      "usage_rate": 0.5,
      "balance_rate": 0.3,
      "payment_rate": 0.2
    }
  }
}
```

**实现说明**：
- 用量达标率：近 3 个月实际用量 / 预期用量（预期用量基于历史平均）
- 余额充足率：当前余额 / 近 3 个月月均消耗
- 回款及时率：近 6 个月按时付款结算单数 / 总结算单数

### 4.2 现有 API 复用

| 组件 | 使用 API | 说明 |
|------|----------|------|
| 用量分布图 | `GET /api/v1/usage/daily?customer_id=X` | 按设备类型聚合 |
| 消费等级 | `GET /api/v1/customers/<id>/profile` | 直接读取 consume_level |
| 余额卡片 | `GET /api/v1/billing/customers/<id>/balance` | 直接读取 |

---

## 5. 前端实现方案

### 5.1 技术选型

**图表库**：ECharts + vue-echarts

```bash
npm install echarts vue-echarts
```

**选择理由**：
- Vue 3 官方推荐
- 中文文档完善
- 交互能力强
- 性能优秀

### 5.2 组件结构

```
src/views/customers/Detail.vue
├── PageHeader (页面头部)
├── ATabs (标签页容器)
│   ├── BasicInfoTab (基础信息)
│   │   ├── CustomerNameCard (客户名称卡片)
│   │   ├── InfoGrid (信息网格)
│   │   └── TagCloud (标签云)
│   ├── ProfileInfoTab (画像信息)
│   │   ├── ScaleLevelBadge (规模等级徽章)
│   │   ├── ConsumeLevelProgress (消费等级进度条)
│   │   └── HealthGauge (健康度仪表)
│   ├── BalanceInfoTab (余额信息)
│   │   ├── BalanceCards (余额卡片组)
│   │   └── BalanceTrendChart (余额趋势图)
│   ├── InvoiceTab (结算单)
│   │   └── InvoiceTable (结算单表格)
│   └── UsageTab (用量数据)
│       ├── UsageDistributionChart (用量分布图)
│       └── UsageTable (用量表格)
```

### 5.3 核心组件代码示例

#### 5.3.1 健康度仪表组件

```vue
<!-- HealthGauge.vue -->
<template>
  <div class="health-gauge">
    <v-chart :option="chartOption" :auto-resize="true" />
    <div class="health-label">{{ healthLevel }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([PieChart, TitleComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{
  score: number
  level: string
}>()

const chartOption = computed(() => ({
  series: [{
    type: 'pie',
    radius: ['75%', '100%'],
    data: [{
      value: props.score,
      itemStyle: { color: getHealthColor(props.score) }
    }, {
      value: 100 - props.score,
      itemStyle: { color: '#f0f0f0' }
    }],
    label: {
      formatter: '{c}%',
      fontSize: 24,
      fontWeight: 'bold'
    }
  }]
}))

function getHealthColor(score: number): string {
  if (score >= 80) return '#22C55E'
  if (score >= 60) return '#F59E0B'
  return '#EF4444'
}
</script>
```

#### 5.3.2 消费等级进度条组件

```vue
<!-- ConsumeLevelProgress.vue -->
<template>
  <div class="consume-level-progress">
    <div class="level-info">
      <span class="current-level">当前：{{ currentLevel }}</span>
      <span class="next-level">下一级：{{ nextLevel }}</span>
    </div>
    <div class="progress-track">
      <div class="progress-bar" :style="{ width: progress + '%' }" />
      <div class="segments">
        <div v-for="seg in segments" :key="seg.level" 
             class="segment" 
             :class="{ active: isActive(seg.level) }" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const LEVELS = ['C', 'B', 'A', 'KA']
const COLORS = ['#F97316', '#3B82F6', '#22C55E', '#A855F7']

defineProps<{
  currentLevel: string
  progress: number
}>()

const segments = LEVELS.map((level, i) => ({
  level,
  color: COLORS[i]
}))

function isActive(level: string): boolean {
  const currentIndex = LEVELS.indexOf(props.currentLevel)
  const levelIndex = LEVELS.indexOf(level)
  return levelIndex <= currentIndex
}
</script>
```

---

## 6. 实施计划

### 6.1 阶段划分

| 阶段 | 任务 | 预计工时 | 依赖 |
|------|------|----------|------|
| Phase 1 | 安装 ECharts 依赖 | 0.5h | - |
| Phase 2 | 后端 API：余额趋势 | 2h | - |
| Phase 3 | 后端 API：健康度评分 | 3h | - |
| Phase 4 | 前端：基础信息 Tab 重构 | 3h | - |
| Phase 5 | 前端：画像信息 Tab 新增组件 | 4h | Phase 3 |
| Phase 6 | 前端：余额信息 Tab 新增图表 | 3h | Phase 2 |
| Phase 7 | 前端：用量数据 Tab 新增图表 | 3h | - |
| Phase 8 | 视觉细节打磨 + 响应式适配 | 2h | - |
| Phase 9 | 测试 + 修复 | 2h | - |

**总计**：约 22.5 小时

### 6.2 验收标准

1. ✅ 视觉还原度 ≥ 95%（与设计稿对比）
2. ✅ 所有图表交互正常（hover、点击）
3. ✅ 响应式布局正常（Mobile/Tablet/Desktop）
4. ✅ 加载状态骨架屏显示正常
5. ✅ 动效流畅，无卡顿
6. ✅ 后端 API 响应时间 < 500ms
7. ✅ 前端首屏加载时间 < 2s

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| ECharts 包体积过大 | 中等 | 按需引入，使用 tree-shaking |
| 健康度计算逻辑复杂 | 低 | 先实现基础版本，后续迭代优化 |
| 历史余额数据缺失 | 中等 | 趋势图从当前月份开始，逐步积累 |
| 响应式适配工作量大 | 低 | 使用 CSS Grid + 媒体查询 |

---

## 8. 附录

### 8.1 设计参考

- Arco Design Pro - 客户管理模板
- Ant Design Pro - 客户详情页
- Salesforce Lightning - 客户 360 视图

### 8.2 相关文件

- 现有代码：`frontend/src/views/customers/Detail.vue`
- 设计规范：`docs/design/DESIGN-SPEC.md`
- API 文档：`backend/app/routes/`

---

**文档结束**
