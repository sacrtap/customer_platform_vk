<template>
  <div class="home-page">
    <!-- PageHeader -->
    <PageHeader
      eyebrow="Home"
      title="运营工作台"
      subtitle="首屏回答三个问题：今天经营是否正常、哪些客户需要处理、同步/结算链路是否有风险。"
    >
      <template #actions>
        <a-button @click="saveView">保存视图</a-button>
        <a-button type="primary" :loading="loading" @click="refreshData">刷新数据</a-button>
      </template>
    </PageHeader>

    <!-- 同步状态条 -->
    <SyncStatusBar status="ok" last-sync="10:00" next-sync="11:00">
      <template #action>
        <a-button size="mini" @click="$router.push('/system/sync-logs')">查看日志</a-button>
      </template>
    </SyncStatusBar>

    <!-- KPI 条（可点击下钻） -->
    <a-spin :loading="statsLoading" style="width: 100%">
      <div class="kpi-strip" style="margin-bottom: 18px">
        <div class="mini kpi-clickable" @click="$router.push('/customers')">
          <span>活跃客户</span>
          <b>{{ formatNumber(stats.totalCustomers) }}</b>
          <span class="up">较上月 +8.4%</span>
        </div>
        <div class="mini kpi-clickable" @click="$router.push('/analytics/consumption')">
          <span>本月消耗</span>
          <b>{{ formatCurrencyWan(stats.monthConsumption) }}</b>
          <span class="up">完成 73%</span>
        </div>
        <div class="mini kpi-clickable" @click="$router.push('/analytics/payment')">
          <span>待回款</span>
          <b>¥1.36M</b>
          <span class="warn">{{ stats.pendingConfirmation }} 单临期</span>
        </div>
        <div class="mini kpi-clickable" @click="$router.push('/billing/balances')">
          <span>低余额客户</span>
          <b>42</b>
          <span class="down">需跟进</span>
        </div>
        <div class="mini kpi-clickable" @click="$router.push('/system/sync-logs')">
          <span>同步成功率</span>
          <b>98.6%</b>
          <span class="up">稳定</span>
        </div>
        <div class="mini kpi-clickable" @click="$router.push('/system/sync-logs')">
          <span>异常任务</span>
          <b>7</b>
          <span class="warn">待重试</span>
        </div>
      </div>
    </a-spin>

    <!-- Hero 区：趋势图 + 待办 -->
    <div class="hero">
      <!-- 左侧：经营趋势图 -->
      <ChartCard title="经营趋势">
        <template #actions>
          <div class="tabs">
            <span
              v-for="tab in trendTabs"
              :key="tab.key"
              class="tab"
              :class="{ active: activeTrendTab === tab.key }"
              @click="activeTrendTab = tab.key"
              >{{ tab.label }}</span
            >
          </div>
        </template>
        <a-spin :loading="chartLoading" style="width: 100%">
          <div ref="chartRef" class="chart-container"></div>
        </a-spin>
      </ChartCard>

      <!-- 右侧：异常与待办 -->
      <ChartCard title="异常与待办">
        <template #actions>
          <span class="tag amber">{{ todos.length }} 项</span>
          <label class="toggle-switch">
            <input v-model="sortByAmount" type="checkbox" />
            <span class="toggle-label-text">按金额排序</span>
          </label>
        </template>
        <a-spin :loading="todosLoading" style="width: 100%">
          <div class="compact-list">
            <div v-for="todo in sortedTodos" :key="todo.id" class="row">
              <span>{{ todo.title }}</span>
              <b>{{ todo.count }}</b>
            </div>
          </div>
        </a-spin>
        <!-- 快捷操作面板 -->
        <div class="quick-actions">
          <button class="quick-action-btn" @click="$router.push('/customers')">
            <span class="qa-icon">+</span>新建客户
          </button>
          <button class="quick-action-btn" @click="$router.push('/billing/invoices')">
            <span class="qa-icon">¥</span>生成结算单
          </button>
          <button class="quick-action-btn" @click="$router.push('/system/sync-logs')">
            <span class="qa-icon">⟳</span>数据同步
          </button>
          <button class="quick-action-btn" @click="exportReport">
            <span class="qa-icon">↓</span>导出报告
          </button>
        </div>
      </ChartCard>
    </div>

    <!-- 今日优先跟进客户 -->
    <div class="card pad" style="margin-top: 14px">
      <div class="section-title">
        <h2>今日优先跟进客户</h2>
        <a-button @click="batchAssign">批量分配</a-button>
      </div>
      <a-spin :loading="invoicesLoading" style="width: 100%">
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>客户</th>
                <th>健康度</th>
                <th>本月消耗</th>
                <th>余额可用</th>
                <th>风险</th>
                <th>负责人</th>
                <th>下一步</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="customer in priorityCustomers" :key="customer.id">
                <td>
                  <div class="customer">
                    <span class="logo">{{ customer.name.charAt(0) }}</span>
                    <b>{{ customer.name }}</b>
                  </div>
                </td>
                <td>
                  <span class="tag" :class="customer.healthClass">{{ customer.health }}</span>
                </td>
                <td>{{ customer.consumption }}</td>
                <td>{{ customer.balanceDays }}</td>
                <td>{{ customer.risk }}</td>
                <td>{{ customer.manager }}</td>
                <td>
                  <a-dropdown @select="(val: string) => handleAction(val, customer)">
                    <a-button size="mini">操作 ▾</a-button>
                    <template #content>
                      <a-doption value="detail">查看详情</a-doption>
                      <a-doption value="recharge">提醒充值</a-doption>
                      <a-doption value="invoice">生成结算单</a-doption>
                      <a-doption value="assign">分配负责人</a-doption>
                    </template>
                  </a-dropdown>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </a-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import {
  getDashboardStats,
  getDashboardChartData,
  getPendingTasks,
  getPriorityCustomers,
} from '@/api/analytics'
import { formatCurrencyWan, formatNumber } from '@/utils/formatters'
import { useCachedRequest } from '@/composables/useCachedRequest'
import PageHeader from '@/components/PageHeader.vue'
import ChartCard from '@/components/ChartCard.vue'
import SyncStatusBar from '@/components/SyncStatusBar.vue'

import type { ECharts } from 'echarts'

let echartsPromise: Promise<typeof import('echarts')> | null = null
const loadEcharts = async () => {
  if (!echartsPromise) {
    echartsPromise = import('echarts')
  }
  return echartsPromise
}

const router = useRouter()

const statsRequest = useCachedRequest('stats', getDashboardStats, 5 * 60 * 1000)
const chartRequest = useCachedRequest(
  'chart',
  () => getDashboardChartData({ months: 12 }),
  15 * 60 * 1000
)
const todosRequest = useCachedRequest('todos', getPendingTasks, 2 * 60 * 1000)

const statsLoading = ref(false)
const chartLoading = ref(false)
const todosLoading = ref(false)
const invoicesLoading = ref(false)
const loading = ref(false)
const chartRef = ref<HTMLElement>()
let chartInstance: ECharts | null = null

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

const trendTabs = [
  { key: 'consume', label: '消耗' },
  { key: 'payment', label: '回款' },
  { key: 'customers', label: '客户数' },
  { key: 'health', label: '健康度' },
]
const activeTrendTab = ref('consume')

const todos = ref<
  Array<{
    id: number
    title: string
    count: number
    amount: number
    urgency: number
    priority: 'high' | 'medium' | 'low'
    priorityText: string
    due: string
  }>
>([])

const sortByAmount = ref(false)
const sortedTodos = computed(() => {
  const list = [...todos.value]
  return sortByAmount.value
    ? list.sort((a, b) => b.amount - a.amount)
    : list.sort((a, b) => b.urgency - a.urgency)
})

const priorityCustomers = ref<
  Array<{
    id: number
    name: string
    health: string
    healthClass: string
    consumption: string
    balanceDays: string
    risk: string
    manager: string
  }>
>([])

const loadPriorityCustomers = async () => {
  invoicesLoading.value = true
  try {
    const res = await getPriorityCustomers(20)
    priorityCustomers.value = (res.data.customers || []).map((c: Record<string, unknown>) => ({
      id: c.id as number,
      name: c.name as string,
      health: c.health as string,
      healthClass: c.health_class as string,
      consumption: c.consumption as string,
      balanceDays: c.balance_days as string,
      risk: c.risk as string,
      manager: c.manager as string,
    }))
  } catch (error) {
    console.error('加载优先跟进客户失败:', error)
  } finally {
    invoicesLoading.value = false
  }
}

const loadStats = async (forceRefresh = false) => {
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
  } catch (error) {
    console.error('加载统计数据失败:', error)
    Message.error('加载统计数据失败')
  } finally {
    statsLoading.value = false
  }
}

const loadChartData = async (forceRefresh = false) => {
  chartLoading.value = true
  try {
    const res = await chartRequest.execute(forceRefresh)
    await nextTick()
    await initChart(
      (res as { data: { consumption_trend: Array<{ period: string; total_amount: number }> } }).data
        .consumption_trend
    )
  } catch (error) {
    console.error('加载图表数据失败:', error)
    Message.error('加载图表数据失败')
  } finally {
    chartLoading.value = false
  }
}

const initChart = async (data: Array<{ period: string; total_amount: number }>) => {
  if (!chartRef.value) return

  const echarts = await loadEcharts()

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)

  const seriesColors: Record<string, string> = {
    consume: '#1D4ED8',
    payment: '#059669',
    customers: '#0891B2',
    health: '#D97706',
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#DBE3EF',
      textStyle: { color: '#0F172A' },
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
      axisLine: { lineStyle: { color: '#DBE3EF' } },
      axisLabel: { color: '#475569' },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#EDF2F7' } },
      axisLabel: {
        color: '#475569',
        formatter: (value: number) => `¥${(value / 10000).toFixed(0)}万`,
      },
    },
    series: [
      {
        name: trendTabs.find((t) => t.key === activeTrendTab.value)?.label || '消耗',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: {
          color: seriesColors[activeTrendTab.value] || '#1D4ED8',
          width: 3,
        },
        itemStyle: {
          color: seriesColors[activeTrendTab.value] || '#1D4ED8',
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(29, 78, 216, 0.2)' },
              { offset: 1, color: 'rgba(29, 78, 216, 0.02)' },
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
  todosLoading.value = true
  try {
    const res = await todosRequest.execute(forceRefresh)
    todos.value = res.tasks.map(
      (item: { id: number; title: string; type: string; created_at: string }) => ({
        id: item.id,
        title: item.title,
        count: Math.floor(Math.random() * 50) + 1,
        amount: Math.floor(Math.random() * 1000000),
        urgency: Math.floor(Math.random() * 10) + 1,
        priority: item.type === 'warning' ? 'high' : 'medium',
        priorityText: item.type === 'warning' ? '警告' : '信息',
        due: item.created_at,
      })
    )
  } catch (error) {
    console.error('加载待办事项失败:', error)
    Message.error('加载待办事项失败')
  } finally {
    todosLoading.value = false
  }
}

const loadAllData = async (forceRefresh = false) => {
  await Promise.all([
    loadStats(forceRefresh),
    loadChartData(forceRefresh),
    loadTodos(forceRefresh),
    loadPriorityCustomers(),
  ])
}

const refreshData = async () => {
  loading.value = true
  try {
    await loadAllData(true)
    Message.success('数据已刷新')
  } finally {
    loading.value = false
  }
}

const saveView = () => Message.info('保存视图功能开发中')
const exportReport = () => Message.info('导出报告功能开发中')
const batchAssign = () => Message.info('批量分配功能开发中')

const handleAction = (val: string, customer: { id: number; name: string }) => {
  if (val === 'detail') router.push(`/customers/${customer.id}`)
  else Message.info(`${val} - ${customer.name}`)
}

watch(activeTrendTab, () => {
  if (chartRef.value && chartInstance) {
    // 重新渲染图表（Tab 切换时）
    loadChartData(true)
  }
})

const handleResize = () => {
  chartInstance?.resize()
}

onMounted(() => {
  loadAllData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
</script>

<style scoped>
/* KPI 可点击下钻 */
.kpi-clickable {
  cursor: pointer;
  transition: all 0.18s ease;
}
.kpi-clickable:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

/* 趋势图 Tab */
.tabs {
  display: flex;
  gap: 6px;
}
.tab {
  padding: 7px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  cursor: pointer;
  border: 1px solid var(--line);
  background: white;
  transition: all 0.18s ease;
}
.tab.active {
  background: #dbeafe;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

/* 紧凑列表 */
.compact-list {
  display: grid;
  gap: 9px;
}
.compact-list .row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid #edf2f7;
  font-size: 13px;
}
.compact-list .row:last-child {
  border-bottom: 0;
}

/* 快捷操作面板 */
.quick-actions {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 14px;
}
.quick-action-btn {
  border: 1px solid var(--line);
  background: white;
  border-radius: 12px;
  padding: 14px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  transition: all 0.18s ease;
}
.quick-action-btn:hover {
  border-color: #93c5fd;
  color: #1d4ed8;
  background: #eff6ff;
  transform: translateY(-1px);
}
.qa-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  font-size: 16px;
  font-weight: 700;
  background: #dbeafe;
  color: #1d4ed8;
}

/* 排序开关 */
.toggle-switch {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 12px;
  color: var(--muted);
}
.toggle-switch input[type='checkbox'] {
  accent-color: #1d4ed8;
}

/* 标签 */
.tag {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 999px;
  font-weight: 700;
}
.tag.amber {
  background: #fef3c7;
  color: #d97706;
}
.tag.red {
  background: #fee2e2;
  color: #dc2626;
}
.tag.green {
  background: #dcfce7;
  color: #059669;
}

/* 客户 Logo */
.customer {
  display: flex;
  align-items: center;
  gap: 10px;
}
.customer .logo {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: #dbeafe;
  color: #1d4ed8;
  font-weight: 850;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.customer b {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
}

/* 图表容器 */
.chart-container {
  height: 260px;
  width: 100%;
}

/* 表格 */
.table-wrap {
  overflow: auto;
}
.table {
  width: 100%;
  border-collapse: collapse;
  min-width: 860px;
}
.table th,
.table td {
  padding: 12px;
  border-bottom: 1px solid #edf2f7;
  text-align: left;
  white-space: nowrap;
}
.table th {
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}
.table tr:hover td {
  background: #f8fbff;
}

/* 趋势指示 */
.up {
  color: #059669;
}
.warn {
  color: #d97706;
}
.down {
  color: #dc2626;
}

/* 响应式 */
@media (max-width: 1100px) {
  .hero {
    grid-template-columns: 1fr;
  }
  .quick-actions {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
