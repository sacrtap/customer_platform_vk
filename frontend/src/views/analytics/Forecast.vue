<template>
  <div class="forecast-analysis-page">
    <PageHeader eyebrow="Analytics" title="预测回款" subtitle="基于历史数据的智能回款预测" />

    <!-- 筛选区域 -->
    <div class="filter-card">
      <a-form layout="inline" :model="filters">
        <a-form-item label="年份">
          <a-year-picker v-model="selectedYear" style="width: 150px" @change="loadData" />
        </a-form-item>
        <a-form-item label="月份">
          <a-select
            v-model="selectedMonth"
            placeholder="全年"
            style="width: 120px"
            @change="loadData"
          >
            <a-option :value="undefined">全年</a-option>
            <a-option :value="1">1 月</a-option>
            <a-option :value="2">2 月</a-option>
            <a-option :value="3">3 月</a-option>
            <a-option :value="4">4 月</a-option>
            <a-option :value="5">5 月</a-option>
            <a-option :value="6">6 月</a-option>
            <a-option :value="7">7 月</a-option>
            <a-option :value="8">8 月</a-option>
            <a-option :value="9">9 月</a-option>
            <a-option :value="10">10 月</a-option>
            <a-option :value="11">11 月</a-option>
            <a-option :value="12">12 月</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="客户">
          <KeywordAutoComplete
            v-model="filters.keyword"
            placeholder="公司名称/公司 ID"
            width="200"
          />
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" @click="loadData">查询</a-button>
            <a-button @click="handleReset">重置</a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">预测回款总额</div>
        <div class="stat-value">{{ formatCurrency(totalPredicted) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已确认回款</div>
        <div class="stat-value success">{{ formatCurrency(confirmedAmount) }}</div>
        <div class="stat-trend">
          <span class="trend-label">完成率</span>
          <span class="trend-value">{{ completionRate }}%</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">待确认回款</div>
        <div class="stat-value warning">{{ formatCurrency(pendingAmount) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">预测客户数</div>
        <div class="stat-value">{{ predictedCustomers }}</div>
      </div>
    </div>

    <!-- 预测趋势图 -->
    <div class="chart-section">
      <div class="chart-card full-width">
        <div class="chart-header">
          <h3>月度回款预测</h3>
        </div>
        <div ref="forecastChartRef" class="chart-container"></div>
      </div>
    </div>

    <!-- 预测明细表 -->
    <div class="table-section">
      <div class="table-header">
        <h3>预测明细</h3>
        <a-button type="text" size="small" @click="loadData">
          <template #icon>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path d="M8 3a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z" />
              <path
                d="m5.93 6.704-.847 6.783a1 1 0 0 0 1.094 1.12l1.13-1.13a1 1 0 0 1 1.394 0l1.13 1.13a1 1 0 0 0 1.094-1.12l-.847-6.783a1 1 0 0 0-.996-.876H6.926a1 1 0 0 0-.996.876zM6.002 1.5a2.5 2.5 0 0 1 4.996 0 2.5 2.5 0 0 1-4.996 0z"
              />
            </svg>
          </template>
          刷新
        </a-button>
      </div>
      <a-table
        :columns="columns"
        :data="predictionList"
        :loading="loading"
        row-key="customer_id"
        :pagination="pagination"
        @page-change="handlePageChange"
      >
        <template #amount="{ record }">
          <span class="predicted-amount">{{ formatCurrency(record.predicted_amount) }}</span>
        </template>
        <template #action="{ record }">
          <a-button type="text" size="small" @click="viewCustomer(record.customer_id)"
            >查看</a-button
          >
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import {
  getMonthlyPrediction,
  getPredictionTrend,
  type PaymentPrediction,
  type PredictionTrendItem,
} from '@/api/analytics'

import KeywordAutoComplete from '@/components/KeywordAutoComplete.vue'
import { formatCurrency } from '@/utils/formatters'

/** ECharts 统一配色 */
const TEXT_MUTED = '#475569'
const AXIS_LINE = '#DBE3EF'
const SPLIT_LINE = '#F1F5F9'

const router = useRouter()

const filters = reactive({
  year: new Date().getFullYear(),
  month: undefined as number | undefined,
  keyword: '',
})

const selectedYear = ref(new Date())
const selectedMonth = ref<number | undefined>(undefined)

const forecastChartRef = ref<HTMLElement>()
let forecastChart: ECharts | null = null

const loading = ref(false)
const predictionList = ref<PaymentPrediction[]>([])
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

// 统计数据
const totalPredicted = ref(0)
const confirmedAmount = ref(0)
const pendingAmount = ref(0)
const completionRate = ref(0)
const predictedCustomers = ref(0)

const columns = [
  { title: '公司 ID', dataIndex: 'company_id', width: 120 },
  { title: '客户名称', dataIndex: 'customer_name', width: 200 },
  { title: '设备类型', dataIndex: 'device_type', width: 100 },
  { title: '用量', dataIndex: 'quantity', width: 100 },
  { title: '计费类型', dataIndex: 'pricing_type', width: 100 },
  {
    title: '预测金额',
    slotName: 'amount',
    width: 120,
    sorter: (a: PaymentPrediction, b: PaymentPrediction) => a.predicted_amount - b.predicted_amount,
  },
  { title: '操作', slotName: 'action', width: 80, fixed: 'right' as const },
]

// 重置
const handleReset = () => {
  selectedYear.value = new Date()
  selectedMonth.value = undefined
  filters.keyword = ''
  filters.year = new Date().getFullYear()
  filters.month = undefined
  loadData()
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    filters.year = selectedYear.value?.getFullYear() || new Date().getFullYear()
    filters.month = selectedMonth.value

    await loadPredictionData()
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 加载预测数据
const loadPredictionData = async () => {
  const res = await getMonthlyPrediction({
    year: filters.year,
    month: filters.month,
    keyword: filters.keyword || undefined,
    force_refresh: true,
  })

  const responseData = res.data || { predictions: [], summary: null }
  predictionList.value = responseData.predictions || []
  pagination.total = predictionList.value.length

  // 使用后端返回的汇总统计（而非前端硬编码）
  const summary = responseData.summary
  if (summary) {
    totalPredicted.value = summary.total_predicted || 0
    confirmedAmount.value = summary.confirmed_amount || 0
    pendingAmount.value = summary.pending_amount || 0
    completionRate.value = summary.completion_rate || 0
    predictedCustomers.value = summary.predicted_customers || 0
  }

  // 加载图表趋势数据
  await loadTrendData()
}

// 加载趋势数据（全年 12 个月预测 vs 实际）
const trendData = ref<PredictionTrendItem[]>([])

const loadTrendData = async () => {
  try {
    const res = await getPredictionTrend({
      year: filters.year,
      force_refresh: true,
    })
    trendData.value = res.data || []
  } catch {
    trendData.value = []
  }
  initForecastChart()
}

// 初始化预测图表
const initForecastChart = () => {
  if (!forecastChartRef.value) return

  if (forecastChart) {
    forecastChart.dispose()
  }

  forecastChart = echarts.init(forecastChartRef.value)

  const months = [
    '1 月',
    '2 月',
    '3 月',
    '4 月',
    '5 月',
    '6 月',
    '7 月',
    '8 月',
    '9 月',
    '10 月',
    '11 月',
    '12 月',
  ]
  const currentMonth = new Date().getMonth()

  // 使用后端趋势数据
  const predictedData = months.map((_, index) => {
    const item = trendData.value[index]
    return item ? item.predicted : 0
  })
  const actualData = months.map((_, index) => {
    const item = trendData.value[index]
    return item ? item.actual : 0
  })

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
      formatter: (params: Array<{ seriesName: string; name: string; value: number }>) => {
        let html = `<div style="font-weight:600;margin-bottom:4px">${params[0].name}</div>`
        for (const p of params) {
          if (p.value !== null && p.value !== undefined) {
            html += `<div>${p.seriesName}：¥${Number(p.value).toLocaleString()}</div>`
          }
        }
        return html
      },
    },
    legend: {
      data: ['预测回款', '实际回款'],
      textStyle: {
        color: TEXT_MUTED,
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: months,
      axisLine: {
        lineStyle: {
          color: AXIS_LINE,
        },
      },
      axisLabel: {
        color: TEXT_MUTED,
      },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: '¥{value}',
        color: TEXT_MUTED,
      },
      splitLine: {
        lineStyle: {
          color: SPLIT_LINE,
        },
      },
    },
    series: [
      {
        name: '预测回款',
        type: 'bar',
        data: predictedData,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#1D4ED8' },
            { offset: 1, color: '#1E40AF' },
          ]),
        },
      },
      {
        name: '实际回款',
        type: 'line',
        smooth: true,
        data: actualData.map((val, index) => (index <= currentMonth ? val : null)),
        connectNulls: false,
        itemStyle: {
          color: '#059669',
        },
        lineStyle: {
          width: 3,
        },
        symbol: 'circle',
        symbolSize: 8,
      },
    ],
  }

  forecastChart.setOption(option)
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
}

// 查看客户详情
const viewCustomer = (customerId: number) => {
  router.push(`/customers/${customerId}`)
}

// 窗口大小变化时重新渲染图表
const handleResize = () => {
  forecastChart?.resize()
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  forecastChart?.dispose()
})
</script>

<style scoped>
.forecast-analysis-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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

.filter-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: 20px 24px;
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

.stat-value.warning {
  color: var(--amber);
}

.stat-trend {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  margin-top: 8px;
}

.trend-label {
  color: var(--muted);
}

.trend-value {
  font-weight: 600;
  color: var(--primary);
}

.chart-section {
  margin-bottom: 0;
}

.chart-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.chart-card.full-width {
  grid-column: 1 / -1;
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
  height: 400px;
  padding: 24px;
}

.table-section {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--line);
}

.table-header h3 {
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
  margin: 0;
}

/* 表头样式 */
.table-section :deep(.arco-table-th) {
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}

.predicted-amount {
  font-weight: 700;
  color: var(--primary);
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
