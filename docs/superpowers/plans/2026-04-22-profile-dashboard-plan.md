# 画像管理仪表盘实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建画像管理仪表盘页面 (`/profiles`)，修复侧边栏"画像管理"菜单点击后页面空白的问题，汇总展示画像统计数据、可视化图表和快捷操作。

**Architecture:** 前端单页面组件，复用现有后端画像分析 API（`getScaleStats`、`getConsumeLevelStats`、`getIndustryDistribution`、`getRealEstateStats`），使用 `Promise.allSettled` 实现部分失败降级，ECharts 渲染图表，Arco Design 构建 UI。

**Tech Stack:** Vue 3.4 + TypeScript 5.3 + Arco Design 2.54 + ECharts 5.x + Vue Router 4.x

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/views/profiles/Dashboard.vue` | 创建 | 画像管理仪表盘页面主组件 |
| `frontend/src/router/index.ts` | 修改 | 新增 `/profiles` 路由 |
| `frontend/src/views/Dashboard.vue` | 修改 | 新增 `ProfileDashboard` 标题映射 |

---

### Task 1: 创建画像管理仪表盘页面组件

**Files:**
- Create: `frontend/src/views/profiles/Dashboard.vue`

**描述**: 创建画像管理仪表盘页面，包含统计卡片、ECharts 图表、快捷操作三个区域。

**步骤**:

- [ ] **Step 1: 创建 Dashboard.vue 页面组件**

创建文件 `frontend/src/views/profiles/Dashboard.vue`，内容如下：

```vue
<template>
  <div class="profile-dashboard">
    <div class="page-header">
      <div class="header-title">
        <h1>画像管理</h1>
        <p class="header-subtitle">客户画像总览与快捷入口</p>
      </div>
      <a-button type="outline" @click="loadData" :loading="loading">
        <template #icon><icon-refresh /></template>
        刷新
      </a-button>
    </div>

    <a-spin :loading="loading" style="width: 100%">
      <!-- 空状态 -->
      <a-result v-if="isEmpty && !loading" status="404" title="暂无画像数据">
        <template #subtitle>
          请先为客户创建画像记录，或导入包含画像信息的客户数据
        </template>
        <template #extra>
          <a-space>
            <a-button type="primary" @click="$router.push('/customers')">
              前往客户列表
            </a-button>
          </a-space>
        </template>
      </a-result>

      <template v-else>
        <!-- 统计卡片区域 -->
        <div class="stats-grid">
          <a-card class="stat-card">
            <a-statistic title="客户总数" :value="totalCustomers" />
          </a-card>
          <a-card class="stat-card">
            <a-statistic title="规模等级分布">
              <template #suffix>
                <div class="mini-chart">
                  <div v-for="level in scaleLevels" :key="level.name" class="mini-bar-wrapper">
                    <div class="mini-bar" :style="{ height: level.height + '%' }"></div>
                    <div class="mini-label">{{ level.name }}</div>
                  </div>
                </div>
              </template>
            </a-statistic>
          </a-card>
          <a-card class="stat-card">
            <a-statistic title="消费等级分布">
              <template #suffix>
                <div class="mini-chart">
                  <div v-for="level in consumeLevels" :key="level.name" class="mini-bar-wrapper">
                    <div class="mini-bar consume" :style="{ height: level.height + '%' }"></div>
                    <div class="mini-label">{{ level.name }}</div>
                  </div>
                </div>
              </template>
            </a-statistic>
          </a-card>
          <a-card class="stat-card">
            <a-statistic title="房产客户占比" :value="realEstatePercentage" suffix="%" :precision="1" />
          </a-card>
        </div>

        <!-- ECharts 图表区域 -->
        <div class="charts-grid">
          <a-card class="chart-card">
            <template #title>行业分布</template>
            <div ref="industryChartRef" class="chart-container"></div>
          </a-card>
          <a-card class="chart-card">
            <template #title>规模等级分布</template>
            <div ref="scaleChartRef" class="chart-container"></div>
          </a-card>
        </div>

        <a-card class="chart-card full-width">
          <template #title>消费等级分布</template>
          <div ref="consumeLevelChartRef" class="chart-container"></div>
        </a-card>

        <!-- 快捷操作区域 -->
        <div class="quick-actions">
          <h3>快捷操作</h3>
          <div class="actions-grid">
            <a-card v-if="canViewTags" class="action-card" hoverable @click="$router.push('/tags')">
              <div class="action-icon">🏷️</div>
              <h4>标签管理</h4>
              <p>管理客户标签与画像标签</p>
            </a-card>
            <a-card v-if="canViewAnalytics" class="action-card" hoverable @click="$router.push('/analytics/profile')">
              <div class="action-icon">📊</div>
              <h4>画像分析详情</h4>
              <p>查看多维度画像统计分析</p>
            </a-card>
            <a-card class="action-card" hoverable @click="$router.push('/customers')">
              <div class="action-icon">👥</div>
              <h4>客户列表</h4>
              <p>浏览和管理所有客户</p>
            </a-card>
          </div>
        </div>
      </template>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconRefresh } from '@arco-design/web-vue/es/icon'
import * as echarts from 'echarts'
import {
  getScaleStats,
  getConsumeLevelStats,
  getIndustryDistribution,
  getRealEstateStats,
  type ScaleLevelStatsItem,
  type ConsumeLevelStatsItem,
  type IndustryDistributionItem,
  type RealEstateStats,
} from '@/api/analytics'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

// 权限检查
const canViewTags = computed(() => userStore.hasPermission('tags:view'))
const canViewAnalytics = computed(() => userStore.hasPermission('analytics:view'))

// 响应式数据
const loading = ref(false)
const scaleData = ref<ScaleLevelStatsItem[]>([])
const consumeLevelData = ref<ConsumeLevelStatsItem[]>([])
const industryData = ref<IndustryDistributionItem[]>([])
const realEstateData = ref<RealEstateStats | null>(null)

// ECharts 实例
const industryChartRef = ref<HTMLElement>()
const scaleChartRef = ref<HTMLElement>()
const consumeLevelChartRef = ref<HTMLElement>()
let industryChart: echarts.ECharts | null = null
let scaleChart: echarts.ECharts | null = null
let consumeLevelChart: echarts.ECharts | null = null

// 计算属性
const totalCustomers = computed(() => {
  return scaleData.value.reduce((sum, item) => sum + item.count, 0)
})

const realEstatePercentage = computed(() => {
  if (!realEstateData.value) return 0
  return realEstateData.value.real_estate_percentage
})

const isEmpty = computed(() => {
  return totalCustomers.value === 0 && !industryData.value.length
})

// 规模等级迷你图表数据
const scaleLevels = computed(() => {
  const maxCount = Math.max(...scaleData.value.map((i) => i.count), 1)
  const order = ['S', 'A', 'B', 'C', 'D']
  return order.map((name) => {
    const item = scaleData.value.find((i) => i.scale_level === name)
    return {
      name,
      height: item ? (item.count / maxCount) * 100 : 0,
    }
  })
})

// 消费等级迷你图表数据
const consumeLevels = computed(() => {
  const maxCount = Math.max(...consumeLevelData.value.map((i) => i.count), 1)
  const order = ['S', 'A', 'B', 'C', 'D']
  return order.map((name) => {
    const item = consumeLevelData.value.find((i) => i.consume_level === name)
    return {
      name,
      height: item ? (item.count / maxCount) * 100 : 0,
    }
  })
})

// 加载数据
async function loadData() {
  loading.value = true
  try {
    const results = await Promise.allSettled([
      getScaleStats(),
      getConsumeLevelStats(),
      getIndustryDistribution(),
      getRealEstateStats(),
    ])

    const [scaleResult, consumeResult, industryResult, realEstateResult] = results

    if (scaleResult.status === 'fulfilled') {
      scaleData.value = scaleResult.value.data || []
    } else {
      Message.error('规模等级数据加载失败')
    }

    if (consumeResult.status === 'fulfilled') {
      consumeLevelData.value = consumeResult.value.data || []
    } else {
      Message.error('消费等级数据加载失败')
    }

    if (industryResult.status === 'fulfilled') {
      industryData.value = industryResult.value.data || []
    } else {
      Message.error('行业分布数据加载失败')
    }

    if (realEstateResult.status === 'fulfilled') {
      realEstateData.value = realEstateResult.value.data || null
    } else {
      Message.error('房产客户数据加载失败')
    }

    // 渲染图表
    renderCharts()
  } catch (error) {
    Message.error('数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

// 渲染图表
function renderCharts() {
  renderIndustryChart()
  renderScaleChart()
  renderConsumeLevelChart()
}

function renderIndustryChart() {
  if (!industryChartRef.value) return
  if (!industryChart) {
    industryChart = echarts.init(industryChartRef.value)
  }

  const option = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
        label: { show: true, formatter: '{b}: {d}%' },
        data: industryData.value.map((item) => ({
          name: item.industry || '未分类',
          value: item.count,
        })),
      },
    ],
  }
  industryChart.setOption(option)
}

function renderScaleChart() {
  if (!scaleChartRef.value) return
  if (!scaleChart) {
    scaleChart = echarts.init(scaleChartRef.value)
  }

  const order = ['S', 'A', 'B', 'C', 'D']
  const data = order.map((level) => {
    const item = scaleData.value.find((i) => i.scale_level === level)
    return item ? item.count : 0
  })

  const option = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: order },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'bar',
        data,
        itemStyle: { color: '#0369A1' },
        label: { show: true, position: 'top' },
      },
    ],
  }
  scaleChart.setOption(option)
}

function renderConsumeLevelChart() {
  if (!consumeLevelChartRef.value) return
  if (!consumeLevelChart) {
    consumeLevelChart = echarts.init(consumeLevelChartRef.value)
  }

  const order = ['S', 'A', 'B', 'C', 'D']
  const data = order.map((level) => {
    const item = consumeLevelData.value.find((i) => i.consume_level === level)
    return item ? item.count : 0
  })

  const option = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: order },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'bar',
        data,
        itemStyle: { color: '#059669' },
        label: { show: true, position: 'top' },
      },
    ],
  }
  consumeLevelChart.setOption(option)
}

// 响应式调整
function handleResize() {
  industryChart?.resize()
  scaleChart?.resize()
  consumeLevelChart?.resize()
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  industryChart?.dispose()
  scaleChart?.dispose()
  consumeLevelChart?.dispose()
})
</script>

<style scoped>
.profile-dashboard {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-title h1 {
  font-size: 24px;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 4px;
}

.header-subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  border-radius: 12px;
}

.stat-card :deep(.arco-statistic-content) {
  margin-top: 8px;
}

.mini-chart {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 40px;
  margin-top: 8px;
}

.mini-bar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.mini-bar {
  width: 100%;
  min-height: 4px;
  background: #0369a1;
  border-radius: 4px 4px 0 0;
  transition: height 0.3s ease;
}

.mini-bar.consume {
  background: #059669;
}

.mini-label {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.chart-card {
  border-radius: 12px;
}

.chart-card.full-width {
  margin-bottom: 24px;
}

.chart-container {
  height: 300px;
  width: 100%;
}

.quick-actions {
  margin-top: 32px;
}

.quick-actions h3 {
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 16px;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.action-card {
  border-radius: 12px;
  cursor: pointer;
  text-align: center;
  padding: 24px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.action-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.action-icon {
  font-size: 40px;
  margin-bottom: 12px;
}

.action-card h4 {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 8px;
}

.action-card p {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .charts-grid {
    grid-template-columns: 1fr;
  }
  .actions-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
  .actions-grid {
    grid-template-columns: 1fr;
  }
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
```

- [ ] **Step 2: 创建 profiles 目录**

```bash
mkdir -p frontend/src/views/profiles
```

- [ ] **Step 3: 验证文件创建成功**

```bash
ls -la frontend/src/views/profiles/Dashboard.vue
```

---

### Task 2: 注册 `/profiles` 路由

**Files:**
- Modify: `frontend/src/router/index.ts`

**描述**: 在路由配置中新增 `/profiles` 路由，指向新创建的 Dashboard 组件。

**步骤**:

- [ ] **Step 1: 修改 router/index.ts，在 analytics 路由之后添加 profiles 路由**

在 `frontend/src/router/index.ts` 中，找到 `system` 路由块（约第 110 行），在其之前添加：

```typescript
      {
        path: 'profiles',
        name: 'ProfileDashboard',
        component: () => import('@/views/profiles/Dashboard.vue'),
        meta: { requiresPermission: 'profiles:view' },
      },
      {
        path: 'system',
```

完整的路由插入位置（在 `analytics` 块结束后，`system` 块开始前）：

```typescript
        ],  // analytics 块结束
      },
      {
        path: 'profiles',
        name: 'ProfileDashboard',
        component: () => import('@/views/profiles/Dashboard.vue'),
        meta: { requiresPermission: 'profiles:view' },
      },
      {
        path: 'system',
```

- [ ] **Step 2: 验证路由注册成功**

```bash
cd frontend && grep -n "ProfileDashboard" src/router/index.ts
```

期望输出：包含 `ProfileDashboard` 的行

---

### Task 3: 更新侧边栏标题映射

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`

**描述**: 在 `pageTitle` 计算属性的 `routeMap` 中新增 `ProfileDashboard` 映射。

**步骤**:

- [ ] **Step 1: 修改 Dashboard.vue 的 pageTitle 计算属性**

在 `frontend/src/views/Dashboard.vue` 中，找到 `pageTitle` 计算属性（约第 637-651 行），在 `routeMap` 中添加 `ProfileDashboard` 映射：

```typescript
const pageTitle = computed(() => {
  const routeMap: Record<string, string> = {
    Home: '仪表盘',
    Customers: '客户管理',
    CustomerDetail: '客户详情',
    Balance: '余额管理',
    PricingRules: '计费规则',
    Tags: '标签管理',
    Users: '用户管理',
    Roles: '角色权限',
    SyncLogs: '同步日志',
    AuditLogs: '审计日志',
    ProfileDashboard: '画像管理',
  }
  return routeMap[route.name as string] || '仪表盘'
})
```

- [ ] **Step 2: 验证修改成功**

```bash
cd frontend && grep -n "ProfileDashboard" src/views/Dashboard.vue
```

期望输出：`ProfileDashboard: '画像管理'`

---

### Task 4: 类型检查与构建验证

**Files:**
- 无新增文件

**描述**: 运行 TypeScript 类型检查和构建验证，确保没有类型错误。

**步骤**:

- [ ] **Step 1: 运行 TypeScript 类型检查**

```bash
cd frontend && npm run type-check
```

期望输出：无错误

- [ ] **Step 2: 运行构建验证**

```bash
cd frontend && npm run build
```

期望输出：构建成功，无错误

- [ ] **Step 3: 运行前端 lint**

```bash
cd frontend && npm run lint
```

如果有 lint 错误，自动修复：

```bash
cd frontend && npm run lint:fix
```

---

### Task 5: 提交所有更改

**Files:**
- 所有上述变更

**描述**: 将所有更改提交到 git。

**步骤**:

- [ ] **Step 1: 检查更改状态**

```bash
git status
```

- [ ] **Step 2: 添加并提交**

```bash
git add frontend/src/views/profiles/Dashboard.vue frontend/src/router/index.ts frontend/src/views/Dashboard.vue
git commit -m "feat: add profile dashboard page to fix empty /profiles route

Create a comprehensive profile management dashboard with:
- Stats cards (total customers, scale/consume level distribution, real estate ratio)
- ECharts visualizations (industry pie chart, scale/consume level bar charts)
- Quick action shortcuts (tags, analytics, customer list)
- Graceful error handling with Promise.allSettled
- Responsive layout for different screen sizes

Fixes: side menu '画像管理' link pointing to undefined /profiles route"
```

- [ ] **Step 3: 验证提交成功**

```bash
git log -1 --stat
```

---

## 验收标准

1. ✅ 侧边栏"画像管理"点击后正常显示仪表盘页面
2. ✅ 4个统计卡片数据正确显示
3. ✅ 3个 ECharts 图表正常渲染
4. ✅ 快捷操作卡片点击后正确跳转
5. ✅ 页面标题显示为"画像管理"
6. ✅ API 部分失败时页面降级显示，不崩溃
7. ✅ TypeScript 类型检查通过
8. ✅ 构建成功，无错误

---

## 依赖关系

- Task 1 可独立执行（创建页面组件）
- Task 2 依赖 Task 1（路由指向组件）
- Task 3 依赖 Task 2（标题映射对应路由名称）
- Task 4 依赖 Task 1-3（验证所有更改）
- Task 5 依赖 Task 1-4（提交最终结果）
