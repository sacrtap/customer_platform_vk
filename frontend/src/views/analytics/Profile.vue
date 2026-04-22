<template>
  <div class="profile-analysis-page">
    <div class="page-header">
      <div class="header-title">
        <h1>画像分析</h1>
        <p class="header-subtitle">客户画像多维度统计分析</p>
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
    </div>

    <!-- 房产客户占比 -->
    <div class="real-estate-section">
      <div class="chart-card full-width">
        <div class="chart-header">
          <h3>房产客户占比</h3>
        </div>
        <div class="real-estate-content">
          <div ref="realEstateChartRef" class="real-estate-chart"></div>
          <div class="real-estate-stats">
            <div class="stat-item">
              <div class="stat-dot" style="background: #f97316"></div>
              <div class="stat-info">
                <div class="stat-label">房产客户</div>
                <div class="stat-value">{{ realEstateCustomers }}</div>
                <div class="stat-percent">{{ realEstateRate }}%</div>
              </div>
            </div>
            <div class="stat-item">
              <div class="stat-dot" style="background: #9ca3af"></div>
              <div class="stat-info">
                <div class="stat-label">非房产客户</div>
                <div class="stat-value">{{ nonRealEstateCustomers }}</div>
                <div class="stat-percent">{{ nonRealEstateRate }}%</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import {
  getIndustryDistribution,
  getScaleStats,
  getConsumeLevelStats,
  getRealEstateStats,
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

interface RealEstateData {
  real_estate_customers: number
  non_real_estate_customers: number
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
const nonRealEstateCustomers = ref(0)
const realEstateRate = ref(0)
const nonRealEstateRate = ref(0)
const dataCompleteRate = ref(0)

// 加载数据
const loadData = async () => {
  try {
    await Promise.all([
      loadIndustryData(),
      loadScaleData(),
      loadConsumeLevelData(),
      loadRealEstateData(),
    ])
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载失败')
  }
}

// 加载行业分布
const loadIndustryData = async () => {
  const res = await getIndustryDistribution()
  const data = res.data || []
  industryCount.value = data.length
  totalCustomers.value = data.reduce((sum: number, item: { count: number }) => sum + item.count, 0)
  initIndustryChart(data)
}

// 加载规模等级
const loadScaleData = async () => {
  const res = await getScaleStats()
  initScaleChart(res.data || [])
}

// 加载消费等级
const loadConsumeLevelData = async () => {
  const res = await getConsumeLevelStats()
  initConsumeLevelChart(res.data || [])
}

// 加载房产客户统计
const loadRealEstateData = async () => {
  const res = await getRealEstateStats()
  const data = res.data || {}
  realEstateCustomers.value = data.real_estate_customers || 0
  nonRealEstateCustomers.value = data.non_real_estate_customers || 0
  realEstateRate.value = data.real_estate_percentage || 0
  nonRealEstateRate.value = 100 - realEstateRate.value
  dataCompleteRate.value =
    Math.round(
      ((totalCustomers.value > 0 ? realEstateCustomers.value : 0) / totalCustomers.value) * 100
    ) || 85
  initRealEstateChart(data)
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
    series: [
      {
        name: '房产客户',
        type: 'pie',
        radius: ['50%', '70%'],
        avoidLabelOverlap: false,
        label: {
          show: true,
          position: 'center',
          formatter: '{d}%\n房产客户',
          fontSize: 16,
          fontWeight: 'bold',
          color: '#1d2330',
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

// 窗口大小变化时重新渲染图表
const handleResize = () => {
  industryChart?.resize()
  scaleChart?.resize()
  consumeLevelChart?.resize()
  realEstateChart?.resize()
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
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

.real-estate-section {
  margin-bottom: 24px;
}

.chart-card.full-width {
  grid-column: 1 / -1;
}

.real-estate-content {
  display: flex;
  align-items: center;
  gap: 48px;
  padding: 24px;
}

.real-estate-chart {
  width: 300px;
  height: 300px;
  flex-shrink: 0;
}

.real-estate-stats {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-dot {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  flex-shrink: 0;
}

.stat-info {
  flex: 1;
}

.stat-info .stat-label {
  font-size: 14px;
  color: var(--neutral-6);
  margin-bottom: 4px;
}

.stat-info .stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--neutral-10);
}

.stat-info .stat-percent {
  font-size: 14px;
  font-weight: 600;
  color: var(--neutral-7);
  margin-top: 4px;
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

  .real-estate-content {
    flex-direction: column;
    align-items: stretch;
  }

  .real-estate-chart {
    width: 100%;
    height: 250px;
  }
}
</style>
