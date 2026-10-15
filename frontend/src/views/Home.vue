<template>
  <div class="home-page">
    <!-- PageHeader -->
    <PageHeader eyebrow="Home" title="运营工作台" :subtitle="pageSubtitle">
      <template #actions>
        <a-button type="primary" :loading="loading" @click="refreshData">刷新数据</a-button>
      </template>
    </PageHeader>

    <!-- 同步状态条（真实同步健康数据） -->
    <SyncStatusBar
      :status="syncStatus"
      :last-sync="stats.lastSyncTime || '暂无同步记录'"
      :next-sync="stats.nextSyncTime || undefined"
    >
      <template #action>
        <span class="sync-meta">
          <template v-if="stats.syncSuccessRate != null">
            同步成功率 {{ (stats.syncSuccessRate * 100).toFixed(1) }}%
          </template>
          <template v-else>暂无成功率数据</template>
          <span v-if="stats.abnormalTaskCount > 0" class="sync-abnormal">
            {{ stats.abnormalTaskCount }} 个异常
          </span>
        </span>
        <a-button size="mini" @click="$router.push('/system/sync-logs')">查看日志</a-button>
      </template>
    </SyncStatusBar>

    <!-- KPI 条（4 项核心指标，全量真实数据） -->
    <a-spin :loading="statsLoading" style="width: 100%">
      <div class="kpi-strip" style="margin-bottom: 18px">
        <div class="mini kpi-clickable" @click="$router.push('/customers')">
          <span>活跃客户</span>
          <b>{{ formatNumber(stats.totalCustomers) }}</b>
          <span class="up">较上月 {{ momText(stats.totalCustomersMomPct) }}</span>
        </div>
        <div class="mini kpi-clickable" @click="$router.push('/analytics/consumption')">
          <span>本月消耗</span>
          <b>{{ formatCurrencyWan(stats.monthConsumption) }}</b>
          <span class="up">较上月 {{ momText(stats.monthConsumptionMomPct) }}</span>
        </div>
        <div class="mini kpi-clickable" @click="$router.push('/analytics/payment')">
          <span>待回款</span>
          <b>{{ formatCurrencyWan(stats.pendingPaymentAmount) }}</b>
          <span class="warn">{{ stats.pendingPaymentCount }} 单未结</span>
        </div>
        <div class="mini kpi-clickable" @click="$router.push('/billing/balances')">
          <span>低余额客户</span>
          <b>{{ stats.lowBalanceCount }}</b>
          <span class="down">需跟进</span>
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

      <!-- 右侧：待办行动中心（真实聚合，可点击跳转） -->
      <ChartCard title="异常与待办">
        <template #actions>
          <span class="tag amber">{{ todos.length }} 项</span>
          <span class="sort-hint">按紧急度排序</span>
        </template>
        <a-spin :loading="todosLoading" style="width: 100%">
          <div class="compact-list">
            <div
              v-for="todo in todos"
              :key="todo.id"
              class="row todo-row"
              @click="$router.push(todo.action_url)"
            >
              <div class="todo-main">
                <span>{{ todo.title }}</span>
                <b>{{ todo.count }}</b>
                <span v-if="todo.amount > 0" class="todo-amount">{{
                  formatCurrency(todo.amount)
                }}</span>
              </div>
              <span class="todo-urgency" :class="`urgency-${todo.priority}`">{{
                todo.urgency
              }}</span>
            </div>
          </div>
        </a-spin>
        <!-- 快捷操作面板（按角色显隐） -->
        <div class="quick-actions">
          <button class="quick-action-btn" @click="$router.push('/customers')">
            <span class="qa-icon">+</span>新建客户
          </button>
          <button class="quick-action-btn" @click="$router.push('/billing/invoices')">
            <span class="qa-icon">¥</span>生成结算单
          </button>
          <button
            v-if="roleProfile.canManageSystem"
            class="quick-action-btn"
            @click="$router.push('/system/sync-logs')"
          >
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
        <a-button v-if="roleProfile.canOpsConfirm" @click="batchAssign">批量分配</a-button>
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
  getDashboardTrend,
  getDashboardTodos,
  getPriorityCustomers,
  type DashboardTodo,
  type DashboardTrendMetric,
} from '@/api/analytics'
import { formatCurrency, formatCurrencyWan, formatNumber } from '@/utils/formatters'
import { useCachedRequest } from '@/composables/useCachedRequest'
import { useWorkbenchRole } from '@/composables/useWorkbenchRole'
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
const { roleProfile } = useWorkbenchRole()

const pageSubtitle = computed(() => {
  switch (roleProfile.value.tier) {
    case 'admin':
      return '全局经营视图 · 同步 / 结算链路全量健康监测'
    case 'ops':
      return '我负责的客户经营视图'
    default:
      return '我跟进的客户经营视图'
  }
})

/** 环比文案：null 表示上月无基准数据 */
const momText = (pct: number | null): string => {
  if (pct == null) return '暂无上月数据'
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(1)}%`
}

const syncStatus = computed<'ok' | 'warning' | 'syncing'>(() =>
  stats.abnormalTaskCount > 0 ? 'warning' : 'ok'
)

const statsRequest = useCachedRequest('stats', getDashboardStats, 5 * 60 * 1000)
const todosRequest = useCachedRequest('todos', getDashboardTodos, 2 * 60 * 1000)

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
  lowBalanceCount: 0,
  pendingPaymentAmount: 0,
  pendingPaymentCount: 0,
  syncSuccessRate: null as number | null,
  abnormalTaskCount: 0,
  lastSyncTime: null as string | null,
  nextSyncTime: null as string | null,
  totalCustomersMomPct: null as number | null,
  monthConsumptionMomPct: null as number | null,
})

const trendTabs = [
  { key: 'consume', label: '消耗' },
  { key: 'payment', label: '回款' },
  { key: 'customers', label: '客户数' },
  { key: 'health', label: '健康度（当月快照）' },
]
// 默认指标按角色：销售经理关注回款，其余默认消耗
const activeTrendTab = ref(roleProfile.value.tier === 'sales' ? 'payment' : 'consume')

const todos = ref<DashboardTodo[]>([])

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
    stats.lowBalanceCount = res.data.low_balance_count ?? 0
    stats.pendingPaymentAmount = res.data.pending_payment_amount ?? 0
    stats.pendingPaymentCount = res.data.pending_payment_count ?? 0
    stats.syncSuccessRate = res.data.sync_success_rate ?? null
    stats.abnormalTaskCount = res.data.abnormal_task_count ?? 0
    stats.lastSyncTime = res.data.last_sync_time ?? null
    stats.nextSyncTime = res.data.next_sync_time ?? null
    stats.totalCustomersMomPct = res.data.total_customers_mom_pct ?? null
    stats.monthConsumptionMomPct = res.data.month_consumption_mom_pct ?? null
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
    // tab → 后端 metric 映射
    const metricMap: Record<string, DashboardTrendMetric> = {
      consume: 'consumption',
      payment: 'payment',
      customers: 'customer_count',
      health: 'health',
    }
    const metric = metricMap[activeTrendTab.value] || 'consumption'
    const res = await getDashboardTrend({ metric, months: 12, force_refresh: forceRefresh })
    await nextTick()
    await initChart({
      dates: (res.data?.dates as string[]) || [],
      values: (res.data?.values as number[]) || [],
    })
  } catch (error) {
    console.error('加载图表数据失败:', error)
    Message.error('加载图表数据失败')
  } finally {
    chartLoading.value = false
  }
}

const initChart = async (data: { dates: string[]; values: number[] }) => {
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

  const isEmpty = data.dates.length === 0 || data.values.length === 0
  // 计数型指标（客户数/健康风险数）不适用货币格式化
  const isMoneyMetric = activeTrendTab.value === 'consume' || activeTrendTab.value === 'payment'
  const formatAxisValue = (value: number) =>
    isMoneyMetric ? `¥${(value / 10000).toFixed(0)}万` : String(Math.round(value))

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#DBE3EF',
      textStyle: { color: '#0F172A' },
      valueFormatter: (value: number) =>
        isMoneyMetric ? `¥${value.toLocaleString()}` : String(value),
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
      data: data.dates,
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
        formatter: formatAxisValue,
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
        data: data.values,
      },
    ],
    // 空数据时显示提示
    graphic: isEmpty
      ? [
          {
            type: 'text',
            left: 'center',
            top: 'middle',
            style: {
              text: '暂无数据',
              fill: '#94A3B8',
              fontSize: 14,
            },
          },
        ]
      : [],
  }

  chartInstance.setOption(option)
}

const loadTodos = async (forceRefresh = false) => {
  todosLoading.value = true
  try {
    const res = await todosRequest.execute(forceRefresh)
    // 后端已按 urgency 降序返回；直接使用真实聚合数据
    todos.value = res.data.map((item: DashboardTodo) => ({ ...item }))
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

/**
 * 导出运营工作台快照（前端生成 CSV：KPI 4 项 + 待办列表）
 */
const exportReport = () => {
  const dateStr = new Date().toISOString().slice(0, 10)
  const rows: Array<Array<string | number>> = [
    [`运营工作台快照 ${dateStr}`],
    [],
    ['指标', '数值'],
    ['活跃客户', formatNumber(stats.totalCustomers)],
    ['本月消耗', formatCurrencyWan(stats.monthConsumption)],
    ['待回款金额', formatCurrency(stats.pendingPaymentAmount)],
    ['低余额客户', stats.lowBalanceCount],
    [
      '同步成功率',
      stats.syncSuccessRate != null
        ? `${(stats.syncSuccessRate * 100).toFixed(1)}%`
        : '暂无同步记录',
    ],
    ['异常任务', stats.abnormalTaskCount],
    [],
    ['待办', '数量', '金额'],
    ...todos.value.map((todo) => [
      todo.title,
      todo.count,
      todo.amount > 0 ? formatCurrency(todo.amount) : '',
    ]),
  ]
  const csv = rows
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n')
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `workbench-${dateStr}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

/** 批量分配：跳转客户列表优先跟进筛选（原为占位提示） */
const batchAssign = () => router.push('/customers?priority=1')

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
/* hero 两卡片按 1.35fr/0.65fr 分配：允许轨道收缩，
   避免 echarts canvas 固定宽度撑破 fr 比例（第二列被压缩） */
.hero > * {
  min-width: 0;
}

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

/* 同步状态条旁侧健康标签 */
.sync-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  margin-right: 4px;
}
.sync-abnormal {
  color: #dc2626;
  font-weight: 700;
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

/* 待办行动中心：可点击跳转 + 紧急度标识 */
.todo-row {
  cursor: pointer;
  transition: all 0.18s ease;
  border-radius: 8px;
  padding: 8px 6px;
}
.todo-row:hover {
  background: #f8fbff;
}
.todo-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.todo-main > span:first-child {
  color: var(--ink);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.todo-main b {
  color: var(--ink);
  font-size: 14px;
}
.todo-amount {
  color: var(--muted);
  font-size: 12px;
}
.todo-urgency {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 999px;
  flex-shrink: 0;
}
.urgency-high {
  background: #fee2e2;
  color: #dc2626;
}
.urgency-medium {
  background: #fef3c7;
  color: #d97706;
}
.urgency-low {
  background: #e0f2fe;
  color: #0284c7;
}
.sort-hint {
  font-size: 12px;
  color: var(--muted);
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
