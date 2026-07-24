<template>
  <div class="consumption-page">
    <!-- PageHeader -->
    <PageHeader
      eyebrow="Analytics"
      title="消耗分析"
      subtitle="同步状态 + 关键指标 + 趋势/排行 + 设备分布，多维度洞察客户消耗全貌。"
    >
      <template #actions>
        <button class="btn" :disabled="isSyncing" @click="handleSyncButtonClick">
          <span v-if="isSyncing" class="refresh-spin">⟳</span>
          <span v-else>⟳</span>
          <template v-if="isSyncing">
            数据同步 {{ Math.round((syncProgress?.percentage || 0) * 100) }}%
          </template>
          <template v-else>数据同步</template>
        </button>
        <SyncDialog
          v-model:visible="showSyncDialog"
          v-model:minimized="syncMinimized"
          @success="handleSyncSuccess"
          @progress="handleProgressUpdate"
        />
        <button class="btn" :disabled="loading" @click="handleRefresh">
          <span v-if="loading" class="refresh-spin">⟳</span>
          <span v-else>⟳</span>
          刷新
        </button>
      </template>
    </PageHeader>

    <!-- 同步状态提示 -->
    <SyncStatusBar status="ok" last-sync="10:00">
      <template #action>
        <button class="btn-mini" @click="handleSyncButtonClick">手动同步</button>
      </template>
    </SyncStatusBar>

    <!-- KPI 卡片 -->
    <div class="grid-5">
      <KpiCard
        label="总消耗金额"
        :value="formatCurrency(totalConsumption)"
        :trend="`环比 ${trend >= 0 ? '+' : ''}${trend}%`"
        :trend-type="trend >= 0 ? 'up' : 'down'"
      />
      <KpiCard
        label="订单总量"
        :value="formatNumber(totalOrderCount)"
        :trend="`环比 ${orderTrend >= 0 ? '+' : ''}${orderTrend}%`"
        :trend-type="orderTrend >= 0 ? 'up' : 'down'"
      />
      <KpiCard
        label="活跃客户数"
        :value="formatNumber(activeCustomers)"
        :trend="`占比 ${activeRate}%`"
        trend-type="neutral"
      />
      <KpiCard
        label="日均消耗"
        :value="formatCurrency(dailyAverage)"
        :trend="`较上月 ${avgTrend >= 0 ? '+' : ''}${avgTrend}%`"
        :trend-type="avgTrend >= 0 ? 'up' : 'down'"
      />
      <KpiCard
        label="消耗最高客户"
        :value="topCustomer?.customer_name || '-'"
        :trend="`消耗 ${formatCurrency(topCustomer?.cost || 0)}`"
        trend-type="neutral"
      />
    </div>

    <!-- 趋势图卡片 -->
    <div class="card pad main-card">
      <!-- 统一筛选器（趋势图 + 设备分布 + 客户排行共用） -->
      <div class="filters">
        <div class="time-range-group">
          <FilterDropdown
            v-model="timeRange"
            label="时间范围"
            :options="timeRangeOptions"
            hide-all
            @apply="handleTimeRangeChange"
          />
          <template v-if="timeRange === 'custom'">
            <input
              v-model="filters.start_date"
              type="date"
              class="filter-date"
              @change="() => loadData()"
            />
            <span class="date-sep">至</span>
            <input
              v-model="filters.end_date"
              type="date"
              class="filter-date"
              @change="() => loadData()"
            />
          </template>
        </div>
        <CustomerSearchInput v-model="filters.keyword" @search="() => loadData()" />
        <FilterDropdown
          v-model="filters.account_type"
          label="账号类型"
          :options="accountTypeOptions"
          @apply="() => loadData()"
        />
        <FilterDropdown
          v-model="industryValue"
          label="行业"
          :options="industryOptions"
          multiple
          @apply="() => loadData()"
        />
        <FilterDropdown
          v-model="filters.scale_level"
          label="规模等级"
          :options="scaleOptions"
          @apply="() => loadData()"
        />
        <FilterDropdown
          v-model="filters.consume_level"
          label="消费等级"
          :options="consumeOptions"
          @apply="() => loadData()"
        />
        <FilterDropdown
          v-model="managerValue"
          label="运营经理"
          :options="managerOptions"
          @apply="() => loadData()"
        />
        <FilterDropdown
          v-model="salesValue"
          label="销售经理"
          :options="managerOptions"
          @apply="() => loadData()"
        />
        <button class="btn primary" @click="() => loadData()">筛选</button>
        <button class="btn" @click="handleReset">重置</button>
      </div>

      <!-- 消耗趋势图 -->
      <div class="chart-section">
        <div class="section-title">
          <h3>消耗趋势</h3>
        </div>
        <div ref="trendChartRef" class="chart-container"></div>
      </div>
    </div>

    <!-- 客户排行表格 -->
    <div class="card pad main-card">
      <!-- 表格标题 -->
      <div class="section-title">
        <h3>客户排行</h3>
      </div>

      <!-- 表格 -->
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th style="width: 50px">排名</th>
              <th
                class="th-sortable"
                :class="getSortClass('company_id')"
                @click="toggleSort('company_id')"
              >
                <span>客户ID</span>
                <span class="th-sort-indicator"></span>
              </th>
              <th
                class="th-sortable"
                :class="getSortClass('customer_name')"
                @click="toggleSort('customer_name')"
              >
                <span>客户名称</span>
                <span class="th-sort-indicator"></span>
              </th>
              <th
                class="th-sortable th-right"
                :class="getSortClass('cost')"
                @click="toggleSort('cost')"
              >
                <span>结算费用</span>
                <span class="th-sort-indicator"></span>
              </th>
              <th
                class="th-sortable th-right"
                :class="getSortClass('order_count')"
                @click="toggleSort('order_count')"
              >
                <span>订单数量</span>
                <span class="th-sort-indicator"></span>
              </th>
              <th
                class="th-sortable th-right"
                :class="getSortClass('avg_cost')"
                @click="toggleSort('avg_cost')"
              >
                <span>客单价</span>
                <span class="th-sort-indicator"></span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(customer, index) in pagedTopCustomers"
              :key="customer.customer_id"
              :class="{ 'row-top': getOverallRank(index) <= 3 }"
            >
              <td>
                <span :class="['rank-badge', getRankBadgeClass(getOverallRank(index))]">
                  {{ getOverallRank(index) }}
                </span>
              </td>
              <td>
                <span class="cust-id">{{ customer.company_id || '-' }}</span>
              </td>
              <td>
                <b class="name-text">{{ customer.customer_name }}</b>
              </td>
              <td class="td-right">{{ formatCurrency(customer.cost) }}</td>
              <td class="td-right">{{ formatNumber(customer.order_count) }}</td>
              <td class="td-right">
                {{
                  formatCurrency(
                    customer.order_count > 0 ? customer.cost / customer.order_count : 0
                  )
                }}
              </td>
            </tr>
            <tr v-if="pagedTopCustomers.length === 0 && !loading">
              <td colspan="6" class="empty-state">暂无数据</td>
            </tr>
            <tr v-if="loading">
              <td colspan="6" class="loading-state">加载中...</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div class="pagination">
        <span class="page-total">共 {{ sortedTopCustomers.length.toLocaleString() }} 条</span>
        <div class="pagination-right">
          <span class="page-size">
            每页
            <select
              class="page-size-select"
              :value="pagination.pageSize"
              @change="onPageSizeChange"
            >
              <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }}</option>
            </select>
            条
          </span>
          <div class="page-controls">
            <button
              class="page-btn"
              :disabled="pagination.current <= 1"
              @click="onPageChange(pagination.current - 1)"
            >
              ‹
            </button>
            <button
              v-for="p in displayPages"
              :key="p"
              class="page-btn"
              :class="{ active: p === pagination.current, ellipsis: p === -1 }"
              :disabled="p === -1"
              @click="p > 0 && onPageChange(p)"
            >
              {{ p === -1 ? '…' : p }}
            </button>
            <button
              class="page-btn"
              :disabled="pagination.current >= totalPages"
              @click="onPageChange(pagination.current + 1)"
            >
              ›
            </button>
          </div>
          <span class="page-jump">
            跳至
            <input
              type="number"
              class="page-jump-input"
              :value="pagination.current"
              :min="1"
              :max="totalPages"
              @keydown.enter="onJumpPage(($event.target as HTMLInputElement).value)"
            />
            页
          </span>
        </div>
      </div>
    </div>

    <!-- 设备类型分布（拆分为结算费用 + 订单数量两个图表） -->
    <div class="grid-2">
      <div class="card pad main-card">
        <div class="section-title">
          <h3>设备类型分布 — 结算费用占比</h3>
        </div>
        <div ref="deviceCostChartRef" class="chart-container"></div>
      </div>
      <div class="card pad main-card">
        <div class="section-title">
          <h3>设备类型分布 — 订单数量占比</h3>
        </div>
        <div ref="deviceOrderChartRef" class="chart-container"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Message } from '@arco-design/web-vue'
import * as echarts from 'echarts'
import PageHeader from '@/components/PageHeader.vue'
import SyncStatusBar from '@/components/SyncStatusBar.vue'
import KpiCard from '@/components/ui/KpiCard.vue'
import FilterDropdown from '@/components/ui/FilterDropdown.vue'
import type { ECharts } from 'echarts'
import {
  getConsumptionTrend,
  getTopCustomers,
  getDeviceDistribution,
  type ConsumptionTrendItem,
  type TopCustomer,
  type DeviceDistributionItem,
} from '@/api/analytics'
import type { SyncTask } from '@/api/syncTasks'
import { formatCurrency, formatNumber } from '@/utils/formatters'
import { getIndustryTypes } from '@/api/customers'
import { getManagers } from '@/api/users'
import type { IndustryType } from '@/types'

import CustomerSearchInput from '@/views/customers/components/CustomerSearchInput.vue'
import SyncDialog from './components/SyncDialog.vue'

/** ECharts 统一配色序列 */
const CHART_COLORS = ['#1D4ED8', '#0891B2', '#059669', '#D97706', '#DC2626', '#7C3AED']
const TEXT_MUTED = '#475569'
const TEXT_INK = '#0F172A'
const AXIS_LINE = '#DBE3EF'
const SPLIT_LINE = '#F1F5F9'

// --- 统一筛选（趋势图 + 设备分布 + 客户排行共用） ---
const createDefaultFilters = () => ({
  start_date: '',
  end_date: '',
  keyword: '',
  account_type: '正式账号',
  industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
  scale_level: '',
  consume_level: '',
  manager_id: null as number | null,
  sales_manager_id: null as number | null,
})
const filters = reactive(createDefaultFilters())
const timeRange = ref('3month')

// 行业多选 computed
const industryValue = computed({
  get: () => filters.industry,
  set: (val: string[]) => {
    filters.industry = val
  },
})
// 运营经理 computed (string <-> number)
const managerValue = computed({
  get: () => (filters.manager_id ? String(filters.manager_id) : ''),
  set: (val: string) => {
    filters.manager_id = val ? Number(val) : null
  },
})
// 销售经理 computed
const salesValue = computed({
  get: () => (filters.sales_manager_id ? String(filters.sales_manager_id) : ''),
  set: (val: string) => {
    filters.sales_manager_id = val ? Number(val) : null
  },
})

// 字典数据
const industryTypes = ref<IndustryType[]>([])
const managers = ref<Array<{ id: number; real_name: string | null }>>([])
// 筛选选项
const accountTypeOptions = [
  { label: '正式账号', value: '正式账号' },
  { label: '测试账号', value: '测试账号' },
]
const industryOptions = computed(() =>
  industryTypes.value.map((it) => ({ label: it.name, value: it.name }))
)
const scaleOptions = [
  { label: 'S（超大型）', value: 'S' },
  { label: 'A（大型）', value: 'A' },
  { label: 'B（中型）', value: 'B' },
  { label: 'C（小型）', value: 'C' },
  { label: 'D（微型）', value: 'D' },
  { label: 'E（极小型）', value: 'E' },
]
const consumeOptions = [
  { label: 'C1 - 100万', value: 'C1' },
  { label: 'C2 - 50万', value: 'C2' },
  { label: 'C3 - 25万', value: 'C3' },
  { label: 'C4 - 12万', value: 'C4' },
  { label: 'C5 - 6万', value: 'C5' },
  { label: 'C6 - 6万以下', value: 'C6' },
]
const timeRangeOptions = [
  { label: '最近 1 月', value: '1month' },
  { label: '最近 3 月', value: '3month' },
  { label: '最近 6 月', value: '6month' },
  { label: '自定义', value: 'custom' },
]
const managerOptions = computed(() =>
  managers.value.map((m) => ({
    label: m.real_name || `#${m.id}`,
    value: String(m.id),
  }))
)

const loading = ref(false)
const showSyncDialog = ref(false)
const syncMinimized = ref(false)
const syncProgress = ref<SyncTask | null>(null)

const isSyncing = computed(() => {
  return !!(
    syncProgress.value &&
    syncProgress.value.status === 'running' &&
    syncProgress.value.percentage < 1
  )
})

const handleProgressUpdate = (progress: SyncTask) => {
  syncProgress.value = progress
}

const handleSyncButtonClick = () => {
  if (isSyncing.value) {
    syncMinimized.value = false
  }
  showSyncDialog.value = true
}

const trendChartRef = ref<HTMLElement>()
const deviceCostChartRef = ref<HTMLElement>()
const deviceOrderChartRef = ref<HTMLElement>()
let trendChart: ECharts | null = null
let deviceCostChart: ECharts | null = null
let deviceOrderChart: ECharts | null = null

// 统计数据
const totalConsumption = ref(0)
const totalOrderCount = ref(0)
const orderTrend = ref(0)
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

// 排名辅助：根据分页计算全局排名，前3名使用金/银/铜徽章
const getOverallRank = (pageIndex: number) => {
  return (pagination.current - 1) * pagination.pageSize + pageIndex + 1
}

const getRankBadgeClass = (rank: number) => {
  if (rank === 1) return 'rank-1'
  if (rank === 2) return 'rank-2'
  if (rank === 3) return 'rank-3'
  return ''
}

// --- 客户排行表格排序 ---
const sortKey = ref<'customer_name' | 'company_id' | 'cost' | 'order_count' | 'avg_cost'>('cost')
const sortDir = ref<'asc' | 'desc'>('desc')

const getSortClass = (key: string) => {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? 'sort-asc' : 'sort-desc'
}

const toggleSort = (key: typeof sortKey.value) => {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = key === 'customer_name' || key === 'company_id' ? 'asc' : 'desc'
  }
}

const sortedTopCustomers = computed(() => {
  const list = [...topCustomers.value]
  const dir = sortDir.value === 'asc' ? 1 : -1
  list.sort((a, b) => {
    let valA: number | string
    let valB: number | string
    if (sortKey.value === 'avg_cost') {
      valA = a.order_count > 0 ? a.cost / a.order_count : 0
      valB = b.order_count > 0 ? b.cost / b.order_count : 0
    } else if (sortKey.value === 'customer_name') {
      valA = a.customer_name || ''
      valB = b.customer_name || ''
      return (valA as string).localeCompare(valB as string) * dir
    } else if (sortKey.value === 'company_id') {
      valA = a.company_id || ''
      valB = b.company_id || ''
      return (valA as string).localeCompare(valB as string) * dir
    } else {
      valA = a[sortKey.value] || 0
      valB = b[sortKey.value] || 0
    }
    return ((valA as number) - (valB as number)) * dir
  })
  return list
})

// --- 分页 ---
const pagination = reactive({
  current: 1,
  pageSize: 20,
})
const pageSizeOptions = [10, 20, 50, 100]

const totalPages = computed(
  () => Math.ceil(sortedTopCustomers.value.length / pagination.pageSize) || 1
)

const pagedTopCustomers = computed(() => {
  const start = (pagination.current - 1) * pagination.pageSize
  return sortedTopCustomers.value.slice(start, start + pagination.pageSize)
})

const displayPages = computed(() => {
  const current = pagination.current
  const total = totalPages.value
  const pages: number[] = []
  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i)
  } else {
    pages.push(1)
    if (current > 3) pages.push(-1)
    const start = Math.max(2, current - 1)
    const end = Math.min(total - 1, current + 1)
    for (let i = start; i <= end; i++) pages.push(i)
    if (current < total - 2) pages.push(-1)
    pages.push(total)
  }
  return pages
})

const onPageChange = (page: number) => {
  if (page < 1 || page > totalPages.value) return
  pagination.current = page
}

const onPageSizeChange = (e: Event) => {
  pagination.pageSize = Number((e.target as HTMLSelectElement).value)
  pagination.current = 1
}

const onJumpPage = (val: string) => {
  const page = parseInt(val)
  if (page >= 1 && page <= totalPages.value) {
    onPageChange(page)
  }
}

// --- 数据加载 ---
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

const handleReset = () => {
  timeRange.value = '3month'
  filters.keyword = ''
  filters.start_date = ''
  filters.end_date = ''
  filters.account_type = '正式账号'
  filters.industry = ['房产经纪', '房产ERP', '房产平台']
  filters.scale_level = ''
  filters.consume_level = ''
  filters.manager_id = null
  filters.sales_manager_id = null
  pagination.current = 1
  handleTimeRangeChange()
}

const loadData = async (forceRefresh = false) => {
  loading.value = true
  try {
    await Promise.all([
      loadTrendData(forceRefresh),
      loadTopCustomersData(forceRefresh),
      loadDeviceData(forceRefresh),
    ])
    calculateStats()
  } catch (error: unknown) {
    Message.error(error instanceof Error ? error.message : '加载失败')
  } finally {
    loading.value = false
  }
}

const handleRefresh = async () => {
  loading.value = true
  try {
    await loadData(true)
    Message.success('数据已刷新')
  } catch (error: unknown) {
    Message.error(error instanceof Error ? error.message : '刷新失败')
  } finally {
    loading.value = false
  }
}

const handleSyncSuccess = async () => {
  Message.success('数据同步完成，正在刷新...')
  await loadData()
}

const loadTrendData = async (forceRefresh = false) => {
  const res = await getConsumptionTrend({
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
    keyword: filters.keyword || undefined,
    metric: 'cost',
    account_type: filters.account_type || undefined,
    manager_id: filters.manager_id || undefined,
    sales_manager_id: filters.sales_manager_id || undefined,
    force_refresh: forceRefresh || undefined,
  })
  consumptionTrend.value = res.data || []
  initTrendChart()
}

const loadTopCustomersData = async (forceRefresh = false) => {
  const res = await getTopCustomers({
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
    limit: 500,
    metric: 'cost',
    keyword: filters.keyword || undefined,
    account_type: filters.account_type || undefined,
    industry: filters.industry.length > 0 ? filters.industry.join(',') : undefined,
    scale_level: filters.scale_level || undefined,
    consume_level: filters.consume_level || undefined,
    manager_id: filters.manager_id || undefined,
    sales_manager_id: filters.sales_manager_id || undefined,
    force_refresh: forceRefresh || undefined,
  })
  topCustomers.value = res.data || []
  if (topCustomers.value.length > 0) {
    topCustomer.value = topCustomers.value[0]
  }
}

const loadDeviceData = async (forceRefresh = false) => {
  const res = await getDeviceDistribution({
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
    keyword: filters.keyword || undefined,
    metric: 'cost',
    account_type: filters.account_type || undefined,
    manager_id: filters.manager_id || undefined,
    sales_manager_id: filters.sales_manager_id || undefined,
    force_refresh: forceRefresh || undefined,
  })
  deviceDistribution.value = res.data || []
  initDeviceCharts()
}

const calculateStats = () => {
  if (consumptionTrend.value.length > 0) {
    totalConsumption.value = consumptionTrend.value.reduce((sum, item) => sum + (item.cost || 0), 0)
    totalOrderCount.value = consumptionTrend.value.reduce(
      (sum, item) => sum + (item.order_count || 0),
      0
    )
    const days = consumptionTrend.value.length
    dailyAverage.value = totalConsumption.value / days
    if (consumptionTrend.value.length >= 2) {
      const last = consumptionTrend.value[consumptionTrend.value.length - 1].cost || 0
      const prev = consumptionTrend.value[consumptionTrend.value.length - 2].cost || 0
      trend.value = prev > 0 ? Math.round(((last - prev) / prev) * 100) : 0
      const lastOrders = consumptionTrend.value[consumptionTrend.value.length - 1].order_count || 0
      const prevOrders = consumptionTrend.value[consumptionTrend.value.length - 2].order_count || 0
      orderTrend.value =
        prevOrders > 0 ? Math.round(((lastOrders - prevOrders) / prevOrders) * 100) : 0
    }
  }
  activeCustomers.value = new Set(topCustomers.value.map((c) => c.customer_id)).size
  activeRate.value = activeCustomers.value > 0 ? Math.round((activeCustomers.value / 100) * 100) : 0
  avgTrend.value = 0
}

// --- 图表初始化 ---
const initTrendChart = () => {
  if (!trendChartRef.value) return
  if (trendChart) trendChart.dispose()
  trendChart = echarts.init(trendChartRef.value)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', crossStyle: { color: '#94A3B8' } },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      formatter: function (params: any[]) {
        let result = params[0].axisValue + '<br/>'
        params.forEach((param) => {
          if (param.seriesName === '结算费用') {
            result +=
              param.marker + param.seriesName + ': ¥' + param.value.toLocaleString() + '<br/>'
          } else {
            result +=
              param.marker + param.seriesName + ': ' + param.value.toLocaleString() + ' 单<br/>'
          }
        })
        return result
      },
    },
    legend: {
      data: ['结算费用', '订单数量'],
      top: '0%',
      textStyle: { color: TEXT_MUTED },
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: consumptionTrend.value.map((item) => item.date || item.period),
      axisLine: { lineStyle: { color: AXIS_LINE } },
      axisLabel: { color: TEXT_MUTED },
    },
    yAxis: [
      {
        type: 'value',
        name: '结算费用',
        position: 'left',
        axisLabel: { formatter: '¥{value}', color: TEXT_MUTED },
        splitLine: { lineStyle: { color: SPLIT_LINE } },
      },
      {
        type: 'value',
        name: '订单数量',
        position: 'right',
        axisLabel: { formatter: '{value} 单', color: TEXT_MUTED },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '结算费用',
        type: 'line',
        smooth: true,
        yAxisIndex: 0,
        data: consumptionTrend.value.map((item) => item.cost),
        itemStyle: { color: CHART_COLORS[0] },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(29, 78, 216, 0.3)' },
            { offset: 1, color: 'rgba(29, 78, 216, 0.05)' },
          ]),
        },
      },
      {
        name: '订单数量',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: consumptionTrend.value.map((item) => item.order_count),
        itemStyle: { color: CHART_COLORS[1] },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(8, 145, 178, 0.3)' },
            { offset: 1, color: 'rgba(8, 145, 178, 0.05)' },
          ]),
        },
      },
    ],
  }
  trendChart.setOption(option)
}

const initDeviceCharts = () => {
  if (deviceCostChartRef.value) {
    if (deviceCostChart) deviceCostChart.dispose()
    deviceCostChart = echarts.init(deviceCostChartRef.value)
    deviceCostChart.setOption(buildPieOption('结算费用', 'cost'))
  }
  if (deviceOrderChartRef.value) {
    if (deviceOrderChart) deviceOrderChart.dispose()
    deviceOrderChart = echarts.init(deviceOrderChartRef.value)
    deviceOrderChart.setOption(buildPieOption('订单数量', 'order_count'))
  }
}

const buildPieOption = (name: string, metric: 'cost' | 'order_count') => {
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      textStyle: { color: TEXT_MUTED, fontSize: 12 },
    },
    series: [
      {
        name,
        type: 'pie',
        radius: ['45%', '72%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
        label: { show: false, position: 'center' },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold',
            color: TEXT_INK,
            formatter: `{b}\n{d}%`,
          },
        },
        labelLine: { show: false },
        data: deviceDistribution.value.map((item, index) => ({
          name: item.device_type,
          value: metric === 'cost' ? item.cost : item.order_count,
          itemStyle: { color: CHART_COLORS[index % CHART_COLORS.length] },
        })),
      },
    ],
  }
}

const handleResize = () => {
  trendChart?.resize()
  deviceCostChart?.resize()
  deviceOrderChart?.resize()
}

watch(deviceDistribution, () => {
  nextTick(() => initDeviceCharts())
})

// --- 字典加载 ---
const loadIndustryTypesData = async () => {
  try {
    const res = await getIndustryTypes()
    industryTypes.value = (res.data?.data || res.data || []) as IndustryType[]
  } catch (error) {
    console.error('加载行业类型失败:', error)
  }
}

const loadManagersData = async () => {
  try {
    const res = await getManagers()
    managers.value = (res.data?.list || res.data || []) as Array<{
      id: number
      real_name: string | null
    }>
  } catch (error) {
    console.error('加载运营经理失败:', error)
  }
}

onMounted(() => {
  handleTimeRangeChange()
  loadIndustryTypesData()
  loadManagersData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  deviceCostChart?.dispose()
  deviceOrderChart?.dispose()
})
</script>

<style scoped>
.consumption-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px 24px 44px;
  max-width: 1440px;
  margin: 0 auto;
}

.consumption-page :deep(.page-header) {
  margin-bottom: 0;
}

/* 按钮样式 */
.btn {
  border: 1px solid var(--line);
  background: white;
  color: var(--ink);
  border-radius: 12px;
  padding: 9px 12px;
  cursor: pointer;
  font-weight: 700;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
}
.btn:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}
.btn.primary {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}
.btn.primary:hover {
  background: #1e40af;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-mini {
  border: 1px solid var(--line);
  background: white;
  color: var(--ink);
  border-radius: 8px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
}
.btn-mini:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}

.refresh-spin {
  display: inline-block;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* KPI 卡片网格 */
.grid-4 {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.grid-5 {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
}
.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

/* 主卡片 */
.main-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg, 16px);
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0, 0, 0, 0.06));
  padding: 20px 24px;
  overflow: hidden;
}

/* 筛选器 */
.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid #edf2f7;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-label {
  font-size: 12px;
  color: var(--muted);
  font-weight: 600;
  white-space: nowrap;
}

.time-range-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-date {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 700;
  color: var(--ink);
  background: #fff;
  cursor: pointer;
  outline: none;
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
}
.filter-date:hover,
.filter-date:focus {
  border-color: #93c5fd;
}
.filter-date:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.1);
}

.date-sep {
  font-size: 13px;
  color: var(--muted);
}

/* 区块标题 */
.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.section-title h3 {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
  margin: 0;
}

/* 图表容器 */
.chart-section {
  margin-bottom: 0;
}
.chart-container {
  height: 320px;
}

/* 表格 */
.table-wrap {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 12px;
}
.table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  table-layout: auto;
}
.table th,
.table td {
  padding: 10px 12px;
  border-bottom: 1px solid #edf2f7;
  text-align: left;
  white-space: nowrap;
}
.table th {
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  position: sticky;
  top: 0;
  z-index: 1;
}
.table tbody tr {
  transition: background 0.15s;
}
.table tbody tr:hover td {
  background: #f8fbff;
}
.table tbody tr.row-top td {
  background: linear-gradient(90deg, rgba(254, 243, 199, 0.4) 0%, transparent 100%);
}
.table tbody tr.row-top:hover td {
  background: linear-gradient(90deg, rgba(254, 243, 199, 0.6) 0%, #f8fbff 100%);
}

/* 排序表头 */
.th-sortable {
  cursor: pointer;
  user-select: none;
  position: relative;
  padding-right: 20px !important;
}
.th-sortable:hover {
  color: var(--primary);
}
.th-right {
  text-align: right;
}
.th-sort-indicator {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 10px;
  color: var(--muted);
  line-height: 1;
}
.th-sortable.sort-asc .th-sort-indicator,
.th-sortable.sort-desc .th-sort-indicator {
  color: var(--primary);
}
.th-sortable.sort-asc .th-sort-indicator::after {
  content: '▲';
}
.th-sortable.sort-desc .th-sort-indicator::after {
  content: '▼';
}
.th-sortable:not(.sort-asc):not(.sort-desc) .th-sort-indicator::after {
  content: '⇅';
  opacity: 0.4;
}

.td-right {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* 排名徽章 */
.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  font-size: 13px;
  font-weight: 700;
  color: var(--muted);
  background: #f1f5f9;
}
.rank-1 {
  background: linear-gradient(135deg, #d97706 0%, #fbbf24 100%);
  color: #fff;
}
.rank-2 {
  background: linear-gradient(135deg, #94a3b8 0%, #cbd5e1 100%);
  color: #fff;
}
.rank-3 {
  background: linear-gradient(135deg, #b45309 0%, #d97706 100%);
  color: #fff;
}

.name-text {
  font-weight: 600;
  color: var(--ink);
}
.cust-id {
  font-variant-numeric: tabular-nums;
  color: var(--muted);
  font-size: 13px;
}

/* 空状态 / 加载状态 */
.empty-state,
.loading-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--muted);
  font-size: 14px;
}

/* 分页 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #edf2f7;
}
.page-total {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.pagination-right {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-left: auto;
}
.page-size {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
}
.page-size-select {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 3px 6px;
  font: inherit;
  font-size: 12px;
  color: var(--ink);
  background: #fff;
  cursor: pointer;
}
.page-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}
.page-btn {
  min-width: 32px;
  height: 32px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  border-radius: 8px;
  padding: 0 8px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.page-btn:hover:not(:disabled):not(.active) {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}
.page-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
  cursor: default;
}
.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.page-btn.ellipsis {
  border: none;
  background: transparent;
  cursor: default;
  opacity: 1;
}
.page-jump {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
}
.page-jump-input {
  width: 48px;
  height: 30px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0 6px;
  font: inherit;
  font-size: 12px;
  text-align: center;
  color: var(--ink);
  background: #fff;
}
.page-jump-input:focus {
  outline: none;
  border-color: #93c5fd;
  box-shadow: 0 0 0 2px rgba(147, 197, 253, 0.2);
}

@media (max-width: 1100px) {
  .grid-4,
  .grid-5 {
    grid-template-columns: repeat(2, 1fr);
  }
  .grid-2 {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .grid-4,
  .grid-5 {
    grid-template-columns: 1fr;
  }
  .filters {
    flex-direction: column;
    align-items: stretch;
  }
  .filter-group {
    width: 100%;
  }
  .pagination {
    justify-content: center;
  }
  .page-size,
  .page-jump {
    display: none;
  }
}
</style>
