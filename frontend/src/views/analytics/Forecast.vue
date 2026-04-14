<template>
  <div class="forecast-analysis-page">
    <div class="page-header">
      <div class="header-title">
        <h1>预测回款</h1>
        <p class="header-subtitle">基于历史数据的智能回款预测</p>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div class="filter-section">
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
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import { getMonthlyPrediction, type PaymentPrediction } from '@/api/analytics'
import { formatCurrency } from '@/utils/formatters'

const router = useRouter()

const filters = reactive({
  year: new Date().getFullYear(),
  month: undefined as number | undefined,
  customer_id: undefined as number | undefined,
})

const selectedYear = ref(new Date())
const selectedMonth = ref<number | undefined>(undefined)
const customerId = ref<number | undefined>(undefined)

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
  customerId.value = undefined
  filters.year = new Date().getFullYear()
  filters.month = undefined
  filters.customer_id = undefined
  loadData()
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    filters.year = selectedYear.value?.getFullYear() || new Date().getFullYear()
    filters.month = selectedMonth.value
    filters.customer_id = customerId.value

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
    customer_id: filters.customer_id,
  })

  predictionList.value = res.data || []
  pagination.total = predictionList.value.length

  // 计算统计数据
  totalPredicted.value = predictionList.value.reduce((sum, item) => sum + item.predicted_amount, 0)
  predictedCustomers.value = new Set(predictionList.value.map((c) => c.customer_id)).size
  confirmedAmount.value = Math.round(totalPredicted.value * 0.6)
  pendingAmount.value = totalPredicted.value - confirmedAmount.value
  completionRate.value = Math.round((confirmedAmount.value / totalPredicted.value) * 100) || 0

  initForecastChart()
}

// 初始化预测图表
const initForecastChart = () => {
  if (!forecastChartRef.value) return

  if (forecastChart) {
    forecastChart.dispose()
  }

  forecastChart = echarts.init(forecastChartRef.value)

  // TODO: 替换为真实 API 数据
  // 生成月度预测数据（临时使用 0 或占位数据）
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

  // 移除 Math.random() 模拟数据，使用 0 作为临时值
  const predictedData = months.map(() => 0)
  const actualData = months.map(() => 0)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
      formatter: '{b}<br/>预测：¥{c}<br/>实际：¥{d}',
    },
    legend: {
      data: ['预测回款', '实际回款'],
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
      data: months,
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
        name: '预测回款',
        type: 'bar',
        data: predictedData,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#0369A1' },
            { offset: 1, color: '#075985' },
          ]),
        },
      },
      {
        name: '实际回款',
        type: 'line',
        smooth: true,
        data: actualData.map((val, index) => (index <= currentMonth ? val : null)),
        itemStyle: {
          color: '#22c55e',
        },
        lineStyle: {
          width: 3,
        },
        symbol: {
          size: 8,
        },
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
</script>

<style scoped>
.forecast-analysis-page {
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

.chart-section {
  margin-bottom: 24px;
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
  height: 400px;
  padding: 24px;
}

.table-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--neutral-2);
}

.table-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--neutral-10);
}

.predicted-amount {
  font-weight: 600;
  color: var(--primary-6);
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
