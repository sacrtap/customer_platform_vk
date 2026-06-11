<template>
  <div class="profile-analysis-page">
    <div class="page-header">
      <div class="header-title">
        <h1>画像分析</h1>
        <p class="header-subtitle">客户画像多维度统计分析</p>
      </div>
      <div class="header-actions">
        <a-button :loading="loading" @click="handleRefresh">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
              <path fill-rule="evenodd" d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2v1z"/>
              <path d="M8 1a.5.5 0 0 1 .5.5v4a.5.5 0 0 1-1 0v-4A.5.5 0 0 1 8 1z"/>
              <path d="M8 5.5L5.5 3H10.5L8 5.5z"/>
            </svg>
          </template>
          刷新
        </a-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">客户总数</div>
        <div class="stat-value">{{ totalCustomers }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">行业覆盖</div>
        <div class="stat-value">{{ industryCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">房产客户</div>
        <div class="stat-value">{{ realEstateCustomers }}</div>
        <div class="stat-extra">占比 {{ realEstateRate }}%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">数据完整率</div>
        <div class="stat-value success">{{ dataCompleteRate }}%</div>
      </div>
    </div>

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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import {
  getIndustryDistribution,
  getScaleStats,
  getConsumeLevelStats,
  getRealEstateStats,
  getRealEstateIndustryStats,
} from '@/api/analytics'

interface IndustryData {
  industry: string
  count: number
}

interface ScaleData {
  scale_level: string
  count: number
}

interface ConsumeLevelData {
  consume_level: string
  count: number
}

interface RealEstateIndustryData {
  industry: string
  count: number
}

const industryChartRef = ref<HTMLElement>()
const scaleChartRef = ref<HTMLElement>()
const consumeLevelChartRef = ref<HTMLElement>()
const realEstateChartRef = ref<HTMLElement>()

let industryChart: ECharts | null = null
let scaleChart: ECharts | null = null
let consumeLevelChart: ECharts | null = null
let realEstateChart: ECharts | null = null

// 统计数据
const totalCustomers = ref(0)
const industryCount = ref(0)
const realEstateCustomers = ref(0)
const realEstateRate = ref(0)
const dataCompleteRate = ref(0)
const loading = ref(false)

// 加载数据
const loadData = async (options?: { force_refresh?: boolean }) => {
  const { force_refresh = false } = options || {}
  try {
    await Promise.all([
      loadIndustryData({ force_refresh }),
      loadScaleData({ force_refresh }),
      loadConsumeLevelData({ force_refresh }),
      loadRealEstateData({ force_refresh }),
    ])
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载失败')
  }
}

// 强制刷新
const handleRefresh = async () => {
  loading.value = true
  try {
    await loadData({ force_refresh: true })
    Message.success('已刷新')
  } catch (error: unknown) {
    Message.error((error as Error).message || '刷新失败')
  } finally {
    loading.value = false
  }
}

// 加载行业分布
const loadIndustryData = async (options?: { force_refresh?: boolean }) => {
  const res = await getIndustryDistribution(options)
  const data = res.data || []
  industryCount.value = data.length
  totalCustomers.value = data.reduce((sum: number, item: { count: number }) => sum + item.count, 0)
  initIndustryChart(data)
}

// 加载规模等级
const loadScaleData = async (options?: { force_refresh?: boolean }) => {
  const res = await getScaleStats(options)
  initScaleChart(res.data || [])
}

// 加载消费等级
const loadConsumeLevelData = async (options?: { force_refresh?: boolean }) => {
  const res = await getConsumeLevelStats(options)
  initConsumeLevelChart(res.data || [])
}

// 加载房产客户统计
const loadRealEstateData = async (options?: { force_refresh?: boolean }) => {
  // 统计卡片数据：调用 getRealEstateStats
  const statsRes = await getRealEstateStats(options)
  const stats = statsRes.data || {}
  realEstateCustomers.value = stats.real_estate_customers || 0
  realEstateRate.value = stats.real_estate_percentage || 0
  dataCompleteRate.value =
    Math.round(
      ((totalCustomers.value > 0 ? realEstateCustomers.value : 0) / totalCustomers.value) * 100
    ) || 85

  // 饼图数据：调用 getRealEstateIndustryStats
  const industryRes = await getRealEstateIndustryStats(options)
  const industryData = industryRes.data || []
  initRealEstateChart(industryData)
}

// 初始化行业分布图表
const initIndustryChart = (data: IndustryData[]) => {
  if (!industryChartRef.value) return

  if (industryChart) {
    industryChart.dispose()
  }

  industryChart = echarts.init(industryChartRef.value)

  const colors = [
    '#0369A1',
    '#0ea5e9',
    '#38bdf8',
    '#7dd3fc',
    '#bae6fd',
    '#0284c7',
    '#0369A1',
    '#075985',
  ]

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
        name: '行业',
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
        data: data.map((item, index) => ({
          name: item.industry || '其他',
          value: item.count,
          itemStyle: {
            color: colors[index % colors.length],
          },
        })),
      },
    ],
  }

  industryChart.setOption(option)
}

// 初始化规模等级图表
const initScaleChart = (data: ScaleData[]) => {
  if (!scaleChartRef.value) return

  if (scaleChart) {
    scaleChart.dispose()
  }

  scaleChart = echarts.init(scaleChartRef.value)

  // 检查数据完整性：如果只有"未分类"或无数据，显示友好提示
  const hasValidLevels = data.some((item) => item.scale_level !== '未分类')
  const totalCount = data.reduce((sum, item) => sum + item.count, 0)

  if (!hasValidLevels || totalCount === 0) {
    // 空状态：只显示中心文字，不渲染饼图
    const option = {
      tooltip: {
        show: false,
      },
      legend: {
        show: false,
      },
      series: [
        {
          name: '规模等级',
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['35%', '50%'],
          data: [],  // 空数据数组
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

    console.log('[规模等级分布] 数据尚未完善，客户规模等级字段待手动维护')
    scaleChart.setOption(option)
    return
  }

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
        name: '规模等级',
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
        data: data.map((item) => ({
          name: item.scale_level || '未知',
          value: item.count,
        })),
      },
    ],
  }

  scaleChart.setOption(option)
}

// 初始化消费等级图表
const initConsumeLevelChart = (data: ConsumeLevelData[]) => {
  if (!consumeLevelChartRef.value) return

  if (consumeLevelChart) {
    consumeLevelChart.dispose()
  }

  consumeLevelChart = echarts.init(consumeLevelChartRef.value)

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
        name: '消费等级',
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
        data: data.map((item) => ({
          name: item.consume_level || '未知',
          value: item.count,
        })),
      },
    ],
  }

  consumeLevelChart.setOption(option)
}

// 初始化房产客户行业分布图表
const initRealEstateChart = (data: RealEstateIndustryData[]) => {
  if (!realEstateChartRef.value) return

  if (realEstateChart) {
    realEstateChart.dispose()
  }

  realEstateChart = echarts.init(realEstateChartRef.value)

  // 橙色系配色，区别于行业分布图的蓝色系
  const colors = ['#f97316', '#fb923c', '#fdba74', '#fed7aa', '#ffedd5']

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} 家 ({d}%)',
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
        name: '房产行业',
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
        data: data.length > 0
          ? data.map((item, index) => ({
              name: item.industry || '其他',
              value: item.count,
              itemStyle: {
                color: colors[index % colors.length],
              },
            }))
          : [{ name: '暂无数据', value: 0, itemStyle: { color: '#e5e7eb' } }],
      },
    ],
  }

  realEstateChart.setOption(option)
}

// 窗口大小变化时重新渲染图表
const handleResize = () => {
  industryChart?.resize()
  scaleChart?.resize()
  consumeLevelChart?.resize()
  realEstateChart?.resize()
}

onMounted(() => {
  loadData({ force_refresh: true }) // 首次加载强制刷新，避免命中旧缓存
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  industryChart?.dispose()
  scaleChart?.dispose()
  consumeLevelChart?.dispose()
  realEstateChart?.dispose()
})
</script>

<style scoped>
.profile-analysis-page {
  padding: 0;
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-3: #e0e2e7;
  --neutral-5: #8f959e;
  --neutral-6: #646a73;
  --neutral-7: #4c5360;
  --neutral-10: #1d2330;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
}

.header-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--neutral-10);
  margin-bottom: 8px;
}

.header-subtitle {
  font-size: 14px;
  color: var(--neutral-6);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  margin-bottom: 24px;
}

.stat-card {
  background: white;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  transition: all 200ms ease;
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.stat-label {
  font-size: 13px;
  color: var(--neutral-6);
  margin-bottom: 12px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--neutral-10);
}

.stat-value.success {
  color: #22c55e;
}

.stat-extra {
  font-size: 12px;
  color: var(--neutral-5);
  margin-top: 8px;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
  margin-bottom: 24px;
}

.chart-card {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.chart-header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--neutral-2);
}

.chart-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--neutral-10);
}

.chart-container {
  height: 300px;
  padding: 24px;
}

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
</style>
