<template>
  <div class="consumption-analysis-page">
    <div class="page-header">
      <div class="header-title">
        <h1>消耗分析</h1>
        <p class="header-subtitle">多维度客户消耗数据统计与趋势分析</p>
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
        <div class="stat-label">总消耗金额</div>
        <div class="stat-value">{{ formatCurrency(totalConsumption) }}</div>
        <div class="stat-trend">
          <span class="trend-label">环比</span>
          <span :class="['trend-value', trend >= 0 ? 'trend-up' : 'trend-down']">
            {{ trend >= 0 ? '+' : '' }}{{ trend }}%
          </span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">活跃客户数</div>
        <div class="stat-value">{{ formatNumber(activeCustomers) }}</div>
        <div class="stat-trend">
          <span class="trend-label">占比</span>
          <span class="trend-value">{{ activeRate }}%</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">日均消耗</div>
        <div class="stat-value">{{ formatCurrency(dailyAverage) }}</div>
        <div class="stat-trend">
          <span class="trend-label">较上月</span>
          <span :class="['trend-value', avgTrend >= 0 ? 'trend-up' : 'trend-down']">
            {{ avgTrend >= 0 ? '+' : '' }}{{ avgTrend }}%
          </span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Top1 客户</div>
        <div class="stat-value">{{ topCustomer?.customer_name || '-' }}</div>
        <div class="stat-trend">
          <span class="trend-label">消耗</span>
          <span class="trend-value">{{ formatCurrency(topCustomer?.total_amount || 0) }}</span>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-section">
      <!-- 消耗趋势图 -->
      <div class="chart-card full-width">
        <div class="chart-header">
          <h3>消耗趋势</h3>
        </div>
        <div ref="trendChartRef" class="chart-container"></div>
      </div>

      <!-- 设备类型分布 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>设备类型分布</h3>
        </div>
        <div ref="deviceChartRef" class="chart-container"></div>
      </div>

      <!-- Top10 客户排行榜 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>Top10 消耗客户</h3>
        </div>
        <div class="top-customers-list">
          <div
            v-for="(customer, index) in topCustomers"
            :key="customer.customer_id"
            class="top-customer-item"
          >
            <div class="rank">
              <span :class="['rank-num', `rank-${index + 1}`]">{{ index + 1 }}</span>
            </div>
            <div class="customer-info">
              <div class="customer-name">{{ customer.customer_name }}</div>
              <div class="customer-id">{{ customer.company_id }}</div>
            </div>
            <div class="customer-amount">{{ formatCurrency(customer.total_amount) }}</div>
          </div>
          <a-empty v-if="topCustomers.length === 0" description="暂无数据" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import {
  getConsumptionTrend,
  getTopCustomers,
  getDeviceDistribution,
  type ConsumptionTrendItem,
  type TopCustomer,
  type DeviceDistributionItem,
} from '@/api/analytics'
import { formatCurrency, formatNumber } from '@/utils/formatters'

const filters = reactive({
  start_date: '',
  end_date: '',
  customer_id: undefined as number | undefined,
})

const timeRange = ref('3month')
const dateRange = ref<[Date, Date] | null>(null)
const customerId = ref<number | undefined>(undefined)

const loading = ref(false)
const trendChartRef = ref<HTMLElement>()
const deviceChartRef = ref<HTMLElement>()
let trendChart: ECharts | null = null
let deviceChart: ECharts | null = null

// 统计数据
const totalConsumption = ref(0)
const activeCustomers = ref(0)
const activeRate = ref(0)
const dailyAverage = ref(0)
const trend = ref(0)
const avgTrend = ref(0)
const topCustomer = ref<TopCustomer | null>(null)

// 图表数据
const consumptionTrend = ref<ConsumptionTrendItem[]>([])
const topCustomers = ref<TopCustomer[]>([])
const deviceDistribution = ref<DeviceDistributionItem[]>([])

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
  loading.value = true
  try {
    await Promise.all([loadTrendData(), loadTopCustomersData(), loadDeviceData()])
    calculateStats()
  } catch (error: any) {
    Message.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 加载趋势数据
const loadTrendData = async () => {
  const res = await getConsumptionTrend({
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
    customer_id: filters.customer_id,
  })
  consumptionTrend.value = res.data || []
  initTrendChart()
}

// 加载 Top 客户
const loadTopCustomersData = async () => {
  const res = await getTopCustomers({
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
    limit: 10,
  })
  topCustomers.value = res.data || []
  if (topCustomers.value.length > 0) {
    topCustomer.value = topCustomers.value[0]
  }
}

// 加载设备分布
const loadDeviceData = async () => {
  const res = await getDeviceDistribution({
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
    customer_id: filters.customer_id,
  })
  deviceDistribution.value = res.data || []
  initDeviceChart()
}

// 计算统计数据
const calculateStats = () => {
  if (consumptionTrend.value.length > 0) {
    totalConsumption.value = consumptionTrend.value.reduce(
      (sum, item) => sum + item.total_amount,
      0
    )

    // 计算日均消耗
    const days = consumptionTrend.value.length
    dailyAverage.value = totalConsumption.value / days

    // 计算环比（简单估算）
    if (consumptionTrend.value.length >= 2) {
      const last = consumptionTrend.value[consumptionTrend.value.length - 1].total_amount
      const prev = consumptionTrend.value[consumptionTrend.value.length - 2].total_amount
      trend.value = prev > 0 ? Math.round(((last - prev) / prev) * 100) : 0
    }
  }

  activeCustomers.value = new Set(topCustomers.value.map((c) => c.customer_id)).size
  activeRate.value = activeCustomers.value > 0 ? Math.round((activeCustomers.value / 100) * 100) : 0
  avgTrend.value = 0 // TODO: 替换为真实 API 数据
}

// 初始化趋势图表
const initTrendChart = () => {
  if (!trendChartRef.value) return

  if (trendChart) {
    trendChart.dispose()
  }

  trendChart = echarts.init(trendChartRef.value)

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
      data: consumptionTrend.value.map((item) => item.period),
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
        name: '消耗金额',
        type: 'line',
        smooth: true,
        data: consumptionTrend.value.map((item) => item.total_amount),
        itemStyle: {
          color: '#0369A1',
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(3, 105, 161, 0.3)' },
            { offset: 1, color: 'rgba(3, 105, 161, 0.05)' },
          ]),
        },
      },
    ],
  }

  trendChart.setOption(option)
}

// 初始化设备分布图表
const initDeviceChart = () => {
  if (!deviceChartRef.value) return

  if (deviceChart) {
    deviceChart.dispose()
  }

  deviceChart = echarts.init(deviceChartRef.value)

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
        name: '设备类型',
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
            fontSize: 16,
            fontWeight: 'bold',
            color: '#1d2330',
          },
        },
        labelLine: {
          show: false,
        },
        data: deviceDistribution.value.map((item) => ({
          name: item.device_type,
          value: item.total_amount,
        })),
      },
    ],
  }

  deviceChart.setOption(option)
}

// 窗口大小变化时重新渲染图表
const handleResize = () => {
  trendChart?.resize()
  deviceChart?.resize()
}

onMounted(() => {
  handleTimeRangeChange()
  window.addEventListener('resize', handleResize)
})
</script>

<style scoped>
.consumption-analysis-page {
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
  margin-bottom: 8px;
}

.stat-trend {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.trend-label {
  color: var(--neutral-5);
}

.trend-value {
  font-weight: 600;
}

.trend-up {
  color: #ef4444;
}

.trend-down {
  color: #22c55e;
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

.top-customers-list {
  padding: 16px 24px;
  max-height: 350px;
  overflow-y: auto;
}

.top-customer-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--neutral-2);
}

.top-customer-item:last-child {
  border-bottom: none;
}

.rank {
  width: 32px;
  flex-shrink: 0;
}

.rank-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--neutral-7);
  background: var(--neutral-1);
}

.rank-1 {
  background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
  color: white;
}

.rank-2 {
  background: linear-gradient(135deg, #9ca3af 0%, #6b7280 100%);
  color: white;
}

.rank-3 {
  background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
  color: white;
}

.customer-info {
  flex: 1;
  min-width: 0;
}

.customer-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--neutral-10);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.customer-id {
  font-size: 12px;
  color: var(--neutral-5);
  margin-top: 2px;
}

.customer-amount {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary-6);
  white-space: nowrap;
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
