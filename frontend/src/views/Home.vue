<template>
  <div class="home-page">
    <AppPageHeader
      eyebrow="Home"
      title="运营工作台"
      description="首屏回答今天经营是否正常、哪些客户需要处理、同步/结算链路是否有风险。"
    >
      <template #actions>
        <a-button type="primary" :loading="loading" @click="refreshData">
          <template #icon>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              :style="{
                transform: loading ? 'rotate(360deg)' : 'none',
                transition: 'transform 0.5s linear',
              }"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </template>
          刷新数据
        </a-button>
      </template>
    </AppPageHeader>

    <a-spin :loading="statsLoading" style="width: 100%">
      <MetricGrid>
        <MetricCard
          label="活跃客户"
          :value="formatNumber(stats.totalCustomers)"
          trend="较上月变化"
          trend-type="up"
        />
        <MetricCard
          label="本月消耗"
          :value="formatCurrencyWan(stats.monthConsumption)"
          trend="完成率"
          trend-type="up"
        />
        <MetricCard
          label="待回款"
          :value="stats.pendingConfirmation"
          trend="临期提醒"
          trend-type="warn"
        />
        <MetricCard
          label="低余额客户"
          :value="formatNumber(stats.keyCustomers)"
          trend="需跟进"
          trend-type="down"
        />
      </MetricGrid>
    </a-spin>

    <!-- 内容网格 -->
    <div class="dashboard-grid">
      <!-- 月度消耗趋势 -->
      <ChartCard title="月度消耗趋势">
        <div ref="chartRef" class="chart-container" style="height: 300px;"></div>
      </ChartCard>

      <!-- 待办事项 -->
      <DataSection title="待办事项" subtitle="优先处理事项">
        <div v-if="todosLoading" class="todos-loading">
          <a-spin :size="24" />
        </div>
        <ul v-else class="todo-list">
          <li v-for="todo in todos" :key="todo.id" class="todo-item">
            <div class="todo-icon" :class="todo.type">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                fill="currentColor"
                viewBox="0 0 16 16"
              >
                <path
                  v-if="todo.type === 'warning'"
                  fill-rule="evenodd"
                  d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16zM8.5 4a.5.5 0 0 0-1 0v5.793l-2.147 2.146a.5.5 0 0 0 .708.708L8 8.707l1.793 1.793a.5.5 0 1 0 .708-.708L8.5 9.793V4z"
                />
                <path
                  v-else-if="todo.type === 'info'"
                  fill-rule="evenodd"
                  d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16zM5.5 6A.5.5 0 0 0 5 6.5v5a.5.5 0 0 0 1 0v-5A.5.5 0 0 0 5.5 6zm3.5 10a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2a.5.5 0 0 1 .5.5z"
                />
                <path
                  v-else
                  fill-rule="evenodd"
                  d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16zM5.5 6A.5.5 0 0 0 5 6.5v5a.5.5 0 0 0 1 0v-5A.5.5 0 0 0 5.5 6zm3.5 10a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2a.5.5 0 0 1 .5.5z"
                />
              </svg>
            </div>
            <div class="todo-content">
              <div class="todo-title">{{ todo.title }}</div>
              <div class="todo-meta">{{ formatDate(todo.created_at) }}</div>
            </div>
          </li>
        </ul>
      </DataSection>

      <!-- 最近结算单 -->
      <DataSection title="最近结算单" subtitle="近期结算记录">
        <a-table
          :columns="invoiceColumns"
          :data="invoices"
          :loading="invoicesLoading"
          :bordered="false"
          :row-hoverable="true"
          size="small"
          :pagination="false"
        >
          <template #invoice_number="{ record }">
            <span class="invoice-number">{{ record.invoice_number }}</span>
          </template>
          <template #customer_name="{ record }">
            <span class="customer-name">{{ record.customer_name }}</span>
          </template>
          <template #amount="{ record }">
            <span class="amount">{{ formatCurrency(record.amount) }}</span>
          </template>
          <template #status="{ record }">
            <StatusBadge :status="record.status" />
          </template>
          <template #created_at="{ record }">
            <span class="date">{{ formatDate(record.created_at) }}</span>
          </template>
        </a-table>
      </DataSection>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getDashboardStats, getDashboardChartData, getPendingTasks } from '@/api/analytics'
import { getRecentInvoices, type Invoice } from '@/api/billing'
import { formatCurrency, formatCurrencyWan, formatDate, formatNumber } from '@/utils/formatters'
import { useCachedRequest } from '@/composables/useCachedRequest'
import type { ECharts } from 'echarts'
// 简单的性能追踪函数
const trackPerformance = (label: string, startTime: number) => {
  const duration = Date.now() - startTime
  console.log(`[Dashboard] ${label}: ${duration}ms`)
}
// 懒加载 ECharts
let echartsPromise: Promise<typeof import('echarts')> | null = null
const loadEcharts = async () => {
  if (!echartsPromise) {
    echartsPromise = import('echarts')
  }
  const echarts = await echartsPromise
  return echarts
}

// 初始化缓存请求器
const statsRequest = useCachedRequest('stats', getDashboardStats, 5 * 60 * 1000) // 5分钟
const chartRequest = useCachedRequest(
  'chart',
  () => getDashboardChartData({ months: 12 }),
  15 * 60 * 1000
) // 15分钟
const todosRequest = useCachedRequest('todos', getPendingTasks, 2 * 60 * 1000) // 2分钟
const invoicesRequest = useCachedRequest(
  'invoices',
  () => getRecentInvoices(10),
  2 * 60 * 1000
) // 2分钟

// 独立的 loading 状态
const statsLoading = ref(false)
const chartLoading = ref(false)
const todosLoading = ref(false)
const invoicesLoading = ref(false)
const loading = ref(false)
const chartRef = ref<HTMLElement>()
let chartInstance: ECharts | null = null

// 统计数据
const stats = reactive({
  totalCustomers: 0,
  keyCustomers: 0,
  totalBalance: 0,
  realBalance: 0,
  bonusBalance: 0,
  monthInvoiceCount: 0,
  pendingConfirmation: 0,
  monthConsumption: 0,
})

// 待办事项
const todos = ref<
  Array<{
    id: number
    title: string
    priority: 'high' | 'medium' | 'low'
    priorityText: string
    due: string
    checked: boolean
  }>
>([])
// 结算单
const invoices = ref<Invoice[]>([])

// 结算单列定义
const invoiceColumns = [
  { title: '结算单号', dataIndex: 'invoice_number', width: 160 },
  { title: '客户', dataIndex: 'customer_name', width: 180 },
  { title: '金额', dataIndex: 'amount', width: 120, align: 'right' },
  { title: '状态', dataIndex: 'status', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', width: 160 },
] as const

// 统计数据加载
const loadStats = async (forceRefresh = false) => {
  const startTime = Date.now()
  statsLoading.value = true
  try {
    const res = await statsRequest.execute(forceRefresh)
    stats.totalCustomers = res.data.total_customers
    stats.keyCustomers = res.data.key_customers
    stats.totalBalance = res.data.total_balance
    stats.realBalance = res.data.real_balance
    stats.bonusBalance = res.data.bonus_balance
    stats.monthInvoiceCount = res.data.month_invoice_count
    stats.pendingConfirmation = res.data.pending_confirmation
    stats.monthConsumption = res.data.month_consumption
    trackPerformance('stats_load', startTime)
  } catch (error) {
    console.error('加载统计数据失败:', error)
    Message.error('加载统计数据失败')
  } finally {
    statsLoading.value = false
  }
}

// 加载图表数据
const loadChartData = async (forceRefresh = false) => {
  const startTime = Date.now()
  chartLoading.value = true
  try {
    const res = await chartRequest.execute(forceRefresh)
    await nextTick()
    await initChart(
      (res as { data: { consumption_trend: Array<{ period: string; total_amount: number }> } }).data
        .consumption_trend
    )
    trackPerformance('chart_load', startTime)
  } catch (error) {
    console.error('加载图表数据失败:', error)
    Message.error('加载图表数据失败')
  } finally {
    chartLoading.value = false
  }
}

// 初始化图表
const initChart = async (data: Array<{ period: string; total_amount: number }>) => {
  if (!chartRef.value) return

  const echarts = await loadEcharts()

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e0e2e7',
      textStyle: { color: '#2f3645' },
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
      boundaryGap: false,
      data: data.map((item) => item.period),
      axisLine: { lineStyle: { color: '#e0e2e7' } },
      axisLabel: { color: '#646a73' },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#eef0f3' } },
      axisLabel: {
        color: '#646a73',
        formatter: (value: number) => {
          if (value >= 10000) {
            return (value / 10000).toFixed(1) + '万'
          }
          return value.toString()
        },
      },
    },
    series: [
      {
        name: '消耗金额',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 3, color: '#3296f7' },
        itemStyle: { color: '#3296f7' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(50, 150, 247, 0.2)' },
              { offset: 1, color: 'rgba(3, 105, 161, 0.02)' },
            ],
          },
        },
        data: data.map((item) => item.total_amount),
      },
    ],
  }

  chartInstance.setOption(option)
}
const loadTodos = async (forceRefresh = false) => {
  const startTime = Date.now()
  todosLoading.value = true
  try {
    const res = await todosRequest.execute(forceRefresh)
    todos.value = res.tasks.map((item: { id: number; title: string; type: string; created_at: string }) => ({
      id: item.id,
      title: item.title,
      priority: item.type === 'warning' ? 'high' : 'medium',
      priorityText: item.type === 'warning' ? '警告' : '信息',
      due: item.created_at,
      checked: false,
    }))
    trackPerformance('todos_load', startTime)
  } catch (error) {
    console.error('加载待办事项失败:', error)
    Message.error('加载待办事项失败')
  } finally {
    todosLoading.value = false
  }
}
const loadRecentInvoices = async (forceRefresh = false) => {
  const startTime = Date.now()
  invoicesLoading.value = true
  try {
    const res = await invoicesRequest.execute(forceRefresh)
    invoices.value = res.data.list
    trackPerformance('invoices_load', startTime)
  } catch (error) {
    console.error('加载结算单失败:', error)
    Message.error('加载结算单失败')
  } finally {
    invoicesLoading.value = false
  }
}

// 并行加载所有数据
const loadAllData = async (forceRefresh = false) => {
  await Promise.all([
    loadStats(forceRefresh),
    loadChartData(forceRefresh),
    loadTodos(forceRefresh),
    loadRecentInvoices(forceRefresh),
  ])
}

// 刷新数据
const refreshData = async () => {
  loading.value = true
  try {
    await loadAllData(true)
    Message.success('数据已刷新')
  } finally {
    loading.value = false
  }
}



// 窗口大小变化处理
const handleResize = () => {
  chartInstance?.resize()
}

onMounted(() => {
  loadAllData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.home-page {
  --primary-1: #e8f3ff;
  --primary-5: #3296f7;
  --primary-6: #0369a1;
  --primary-7: #035a8a;
  --success-1: #e8ffea;
  --success-5: #4ade80;
  --success-6: #22c55e;
  --warning-1: #fff7e8;
  --warning-5: #fbbf24;
  --warning-6: #f59e0b;
  --danger-1: #ffe8e8;
  --danger-5: #f87171;
  --danger-6: #ef4444;
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-3: #e0e2e7;
  --neutral-5: #8f959e;
  --neutral-6: #646a73;
  --neutral-7: #4c5360;
  --neutral-9: #2f3645;
  --neutral-10: #1d2330;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 250ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* 图表容器 */
.chart-container {
  height: 300px;
  width: 100%;
}

/* 内容网格 */
.dashboard-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 24px;
}

/* 待办事项 */
.todo-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.todo-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  background: var(--neutral-1);
  transition: background var(--transition-fast);
}

.todo-item:hover {
  background: var(--neutral-2);
}

.todo-icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.todo-icon.warning {
  background: var(--danger-1);
  color: var(--danger-6);
}

.todo-icon.info {
  background: var(--primary-1);
  color: var(--primary-6);
}

.todo-icon.success {
  background: var(--success-1);
  color: var(--success-6);
}

.todo-content {
  flex: 1;
  min-width: 0;
}

.todo-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--neutral-10);
  margin-bottom: 4px;
}

.todo-meta {
  font-size: 12px;
  color: var(--neutral-6);
}

.todos-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 120px;
}

/* 结算单表格 */
.invoice-number {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 13px;
  color: var(--neutral-7);
}

.customer-name {
  font-weight: 500;
  color: var(--neutral-10);
}

.amount {
  font-weight: 600;
  color: var(--neutral-10);
}

.date {
  font-size: 12px;
  color: var(--neutral-6);
}
</style>
