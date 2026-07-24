<template>
  <div class="profile-analysis-page">
    <PageHeader eyebrow="Analytics" title="画像分析" subtitle="客户画像多维度统计分析">
      <template #actions>
        <a-button :loading="loading" @click="handleRefresh">刷新</a-button>
      </template>
    </PageHeader>

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
        <div class="stat-label">画像覆盖率</div>
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
          <h3>房产客户行业分布</h3>
        </div>
        <div ref="realEstateChartRef" class="chart-container"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
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

/** ECharts 统一配色序列 */
const CHART_COLORS = ['#1D4ED8', '#0891B2', '#059669', '#D97706', '#DC2626', '#7C3AED']
const TEXT_MUTED = '#475569'
const TEXT_INK = '#0F172A'

/** 房产客户独立橙色系配色 */
const REAL_ESTATE_COLORS = ['#D97706', '#F59E0B', '#FBBF24', '#FCD34D', '#FDE68A']

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
  industryCount.value = data.filter((item: IndustryData) => item.industry !== '未分类').length
  // totalCustomers 由 loadRealEstateData 中的 getRealEstateStats 返回，
  // 这里不再从行业分布汇总计算（行业分布可能因 LEFT JOIN 导致汇总值等于总数，
  // 但语义上应使用权威的客户总数接口）
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
  // 客户总数使用后端权威值，而非行业分布汇总
  totalCustomers.value = stats.total_customers || 0
  realEstateCustomers.value = stats.real_estate_customers || 0
  realEstateRate.value = stats.real_estate_percentage || 0
  // 画像覆盖率 = 有画像的客户数 / 客户总数（由后端计算返回）
  dataCompleteRate.value = stats.profile_coverage_rate || 0

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
        color: TEXT_MUTED,
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
            color: TEXT_INK,
          },
        },
        labelLine: {
          show: false,
        },
        data: data.map((item, index) => ({
          name: item.industry || '其他',
          value: item.count,
          itemStyle: {
            color: CHART_COLORS[index % CHART_COLORS.length],
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
          data: [],
          label: {
            show: true,
            position: 'center',
            formatter: '-',
            fontSize: 24,
            color: '#94A3B8',
            fontWeight: 'lighter',
          },
        },
      ],
    }

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
        color: TEXT_MUTED,
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
            color: TEXT_INK,
          },
        },
        labelLine: {
          show: false,
        },
        data: data.map((item, index) => ({
          name: item.scale_level || '未知',
          value: item.count,
          itemStyle: {
            color: CHART_COLORS[index % CHART_COLORS.length],
          },
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
        color: TEXT_MUTED,
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
            color: TEXT_INK,
          },
        },
        labelLine: {
          show: false,
        },
        data: data.map((item, index) => ({
          name: item.consume_level || '未知',
          value: item.count,
          itemStyle: {
            color: CHART_COLORS[index % CHART_COLORS.length],
          },
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
        color: TEXT_MUTED,
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
            color: TEXT_INK,
          },
        },
        labelLine: {
          show: false,
        },
        data:
          data.length > 0
            ? data.map((item, index) => ({
                name: item.industry || '其他',
                value: item.count,
                itemStyle: {
                  color: REAL_ESTATE_COLORS[index % REAL_ESTATE_COLORS.length],
                },
              }))
            : [{ name: '暂无数据', value: 0, itemStyle: { color: '#E2E8F0' } }],
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
  loadData({ force_refresh: true })
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
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.header-info h1 {
  margin: 4px 0 2px 0;
  font-size: 26px;
  font-weight: 850;
  color: var(--ink);
  line-height: 1.2;
}

.header-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--muted);
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.stat-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: 20px;
  transition: all 200ms ease;
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.stat-label {
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 12px;
}

.stat-value {
  font-size: 26px;
  font-weight: 850;
  color: var(--ink);
}

.stat-value.success {
  color: var(--green);
}

.stat-extra {
  font-size: 12px;
  color: var(--muted);
  margin-top: 8px;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.chart-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.chart-header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--line);
}

.chart-header h3 {
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
  margin: 0;
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
