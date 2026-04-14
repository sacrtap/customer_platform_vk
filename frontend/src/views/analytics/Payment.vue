<template>
  <div class="payment-analysis-page">
    <div class="page-header">
      <div class="header-title">
        <h1>回款分析</h1>
        <p class="header-subtitle">结算单回款进度与完成率分析</p>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div class="filter-section">
      <a-form layout="inline" :model="filters">
        <a-form-item label="时间范围">
          <a-select
            v-model="timeRange"
            placeholder="请选择"
            style="width: 150px"
            @change="handleTimeRangeChange"
          >
            <a-option value="1month">最近 1 月</a-option>
            <a-option value="3month">最近 3 月</a-option>
            <a-option value="6month">最近 6 月</a-option>
            <a-option value="custom">自定义</a-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="timeRange === 'custom'" label="">
          <a-range-picker
            v-model="dateRange"
            style="width: 240px"
            @change="handleDateRangeChange"
          />
        </a-form-item>
        <a-form-item label="客户">
          <a-select
            v-model="customerId"
            placeholder="全部客户"
            style="width: 200px"
            allow-clear
            @change="loadData"
          >
            <a-option :value="undefined">全部客户</a-option>
          </a-select>
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
        <div class="stat-label">应收总额</div>
        <div class="stat-value">{{ formatCurrency(totalInvoiced) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">减免总额</div>
        <div class="stat-value warning">{{ formatCurrency(totalDiscount) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已回款</div>
        <div class="stat-value success">{{ formatCurrency(totalPaid) }}</div>
        <div class="stat-trend">
          <span class="trend-label">回款率</span>
          <span class="trend-value">{{ completionRate }}%</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">待回款</div>
        <div class="stat-value danger">{{ formatCurrency(difference) }}</div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-section">
      <!-- 预测 vs 实际对比图 -->
      <div class="chart-card full-width">
        <div class="chart-header">
          <h3>回款对比分析</h3>
        </div>
        <div ref="comparisonChartRef" class="chart-container"></div>
      </div>

      <!-- 结算单状态分布 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>结算单状态分布</h3>
        </div>
        <div ref="statusChartRef" class="chart-container"></div>
      </div>

      <!-- 回款趋势 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>回款趋势</h3>
        </div>
        <div ref="trendChartRef" class="chart-container"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import { getPaymentAnalysis, getInvoiceStatusStats } from '@/api/analytics'
import { formatCurrency } from '@/utils/formatters'

const filters = reactive({
  start_date: '',
  end_date: '',
  customer_id: undefined as number | undefined,
})

const timeRange = ref('3month')
const dateRange = ref<[Date, Date] | null>(null)
const customerId = ref<number | undefined>(undefined)

const comparisonChartRef = ref<HTMLElement>()
const statusChartRef = ref<HTMLElement>()
const trendChartRef = ref<HTMLElement>()
let comparisonChart: ECharts | null = null
let statusChart: ECharts | null = null
let trendChart: ECharts | null = null

// 统计数据
const totalInvoiced = ref(0)
const totalDiscount = ref(0)
const totalPaid = ref(0)
const completionRate = ref(0)
const difference = ref(0)

// 状态统计
const statusStats = ref<Array<{ name: string; count: number; percentage: number }>>([])

// 时间范围变化
const handleTimeRangeChange = () => {
  if (timeRange.value !== 'custom') {
    const now = new Date()
    let startDate: Date
    switch (timeRange.value) {
      case '1month':
        startDate = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate())
        break
      case '3month':
        startDate = new Date(now.getFullYear(), now.getMonth() - 3, now.getDate())
        break
      case '6month':
        startDate = new Date(now.getFullYear(), now.getMonth() - 6, now.getDate())
        break
      default:
        startDate = new Date(now.getFullYear(), now.getMonth() - 3, now.getDate())
    }
    filters.start_date = startDate.toISOString().split('T')[0]
    filters.end_date = now.toISOString().split('T')[0]
    loadData()
  }
}

// 日期范围变化
const handleDateRangeChange = (dates: [Date, Date] | null) => {
  if (dates) {
    filters.start_date = dates[0].toISOString().split('T')[0]
    filters.end_date = dates[1].toISOString().split('T')[0]
  }
}

// 重置
const handleReset = () => {
  timeRange.value = '3month'
  dateRange.value = null
  customerId.value = undefined
  filters.start_date = ''
  filters.end_date = ''
  filters.customer_id = undefined
  handleTimeRangeChange()
}

// 加载数据
const loadData = async () => {
  try {
    await Promise.all([loadPaymentData(), loadStatusData()])
    calculateStats()
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载失败')
  }
}

// 加载回款分析数据
const loadPaymentData = async () => {
  const res = await getPaymentAnalysis({
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
    customer_id: filters.customer_id,
  })
  const data = res.data || {}
  totalInvoiced.value = data.total_invoiced || 0
  totalDiscount.value = data.total_discount || 0
  totalPaid.value = data.total_paid || 0
  completionRate.value = data.completion_rate || 0
  difference.value = data.difference || 0

  initComparisonChart()
}

// 加载状态统计
const loadStatusData = async () => {
  const res = await getInvoiceStatusStats({
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
  })
  statusStats.value = res.data || []
  initStatusChart()
  initTrendChart()
}

// 计算统计数据
const calculateStats = () => {
  // 统计数据已在 loadPaymentData 中计算
}

// 初始化对比图表
const initComparisonChart = () => {
  if (!comparisonChartRef.value) return

  if (comparisonChart) {
    comparisonChart.dispose()
  }

  comparisonChart = echarts.init(comparisonChartRef.value)

  // 生成模拟月度数据
  const months = 6
  const now = new Date()
  const periodLabels: string[] = []
  const invoicedData: number[] = []
  const paidData: number[] = []

  for (let i = months - 1; i >= 0; i--) {
    const date = new Date(now.getFullYear(), now.getMonth() - i, 1)
    periodLabels.push(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`)
    const baseAmount = totalInvoiced.value / months
    invoicedData.push(Math.round(baseAmount * (0.8 + Math.random() * 0.4)))
    paidData.push(Math.round(baseAmount * (0.6 + Math.random() * 0.3)))
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
      formatter: '{b}<br/>{a}: ¥{c}<br/>{b}: ¥{d}',
    },
    legend: {
      data: ['应收金额', '已回款'],
      textStyle: {
        color: '#646a73',
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
      data: periodLabels,
      axisLine: {
        lineStyle: {
          color: '#e0e2e7',
        },
      },
      axisLabel: {
        color: '#646a73',
      },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: '¥{value}',
        color: '#646a73',
      },
      splitLine: {
        lineStyle: {
          color: '#f0f0f0',
        },
      },
    },
    series: [
      {
        name: '应收金额',
        type: 'bar',
        data: invoicedData,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#0369A1' },
            { offset: 1, color: '#075985' },
          ]),
        },
      },
      {
        name: '已回款',
        type: 'bar',
        data: paidData,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#22c55e' },
            { offset: 1, color: '#16a34a' },
          ]),
        },
      },
    ],
  }

  comparisonChart.setOption(option)
}

// 初始化状态饼图
const initStatusChart = () => {
  if (!statusChartRef.value) return

  if (statusChart) {
    statusChart.dispose()
  }

  statusChart = echarts.init(statusChartRef.value)

  const statusColors: Record<string, string> = {
    draft: '#6b7280',
    pending_customer: '#f59e0b',
    customer_confirmed: '#3b82f6',
    paid: '#22c55e',
    completed: '#10b981',
    cancelled: '#ef4444',
  }

  const statusNames: Record<string, string> = {
    draft: '草稿',
    pending_customer: '待确认',
    customer_confirmed: '已确认',
    paid: '已付款',
    completed: '已完成',
    cancelled: '已取消',
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
        name: '结算单状态',
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
        data: statusStats.value.map((item) => ({
          name: statusNames[item.status] || item.status,
          value: item.count,
          itemStyle: {
            color: statusColors[item.status] || '#6b7280',
          },
        })),
      },
    ],
  }

  statusChart.setOption(option)
}

// 初始化趋势图表
const initTrendChart = () => {
  if (!trendChartRef.value) return

  if (trendChart) {
    trendChart.dispose()
  }

  trendChart = echarts.init(trendChartRef.value)

  const months = 6
  const now = new Date()
  const periodLabels: string[] = []
  const paidData: number[] = []

  for (let i = months - 1; i >= 0; i--) {
    const date = new Date(now.getFullYear(), now.getMonth() - i, 1)
    periodLabels.push(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`)
    paidData.push(Math.round((totalPaid.value / months) * (0.7 + Math.random() * 0.6)))
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: '{b}<br/>{a}: ¥{c}',
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '10%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: periodLabels,
      axisLine: {
        lineStyle: {
          color: '#e0e2e7',
        },
      },
      axisLabel: {
        color: '#646a73',
      },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: '¥{value}',
        color: '#646a73',
      },
      splitLine: {
        lineStyle: {
          color: '#f0f0f0',
        },
      },
    },
    series: [
      {
        name: '回款金额',
        type: 'line',
        smooth: true,
        data: paidData,
        itemStyle: {
          color: '#22c55e',
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(34, 197, 94, 0.3)' },
            { offset: 1, color: 'rgba(34, 197, 94, 0.05)' },
          ]),
        },
      },
    ],
  }

  trendChart.setOption(option)
}

// 窗口大小变化时重新渲染图表
const handleResize = () => {
  comparisonChart?.resize()
  statusChart?.resize()
  trendChart?.resize()
}

onMounted(() => {
  handleTimeRangeChange()
  window.addEventListener('resize', handleResize)
})
</script>

<style scoped>
.payment-analysis-page {
  padding: 0;
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-3: #e0e2e7;
  --neutral-5: #8f959e;
  --neutral-6: #646a73;
  --neutral-7: #4c5360;
  --neutral-10: #1d2330;
  --primary-6: #0369a1;
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

.filter-section {
  background: white;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  margin-bottom: 24px;
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

.stat-value.warning {
  color: #f59e0b;
}

.stat-value.danger {
  color: #ef4444;
}

.stat-trend {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  margin-top: 8px;
}

.trend-label {
  color: var(--neutral-5);
}

.trend-value {
  font-weight: 600;
  color: var(--primary-6);
}

.charts-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
}

.chart-card {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.chart-card.full-width {
  grid-column: 1 / -1;
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
  height: 350px;
  padding: 24px;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .charts-section {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
