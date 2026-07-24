<template>
  <div class="payment-page">
    <!-- PageHeader -->
    <PageHeader
      eyebrow="Analytics"
      title="回款分析"
      subtitle="结算单回款进度与完成率分析，多维度筛选洞察回款全貌。"
    >
      <template #actions>
        <button class="btn" :disabled="loading" @click="handleRefresh">
          <span v-if="loading" class="refresh-spin">⟳</span>
          <span v-else>⟳</span>
          刷新
        </button>
      </template>
    </PageHeader>

    <!-- KPI 卡片 -->
    <div class="grid-4">
      <KpiCard label="应收总额" :value="formatCurrency(totalInvoiced)" trend-type="neutral" />
      <KpiCard label="减免总额" :value="formatCurrency(totalDiscount)" trend-type="warn" />
      <KpiCard
        label="已回款"
        :value="formatCurrency(totalPaid)"
        :trend="`回款率 ${completionRate}%`"
        trend-type="up"
      />
      <KpiCard label="待回款" :value="formatCurrency(difference)" trend-type="down" />
    </div>

    <!-- 趋势图卡片 -->
    <div class="card pad main-card">
      <!-- 统一筛选器 -->
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

      <!-- 回款对比分析图 -->
      <div class="chart-section">
        <div class="section-title">
          <h3>回款对比分析</h3>
        </div>
        <div ref="comparisonChartRef" class="chart-container"></div>
      </div>
    </div>

    <!-- 状态分布 + 回款趋势 -->
    <div class="grid-2">
      <div class="card pad main-card">
        <div class="section-title">
          <h3>结算单状态分布</h3>
        </div>
        <div ref="statusChartRef" class="chart-container"></div>
      </div>
      <div class="card pad main-card">
        <div class="section-title">
          <h3>回款趋势</h3>
        </div>
        <div ref="trendChartRef" class="chart-container"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import * as echarts from 'echarts'
import PageHeader from '@/components/PageHeader.vue'
import KpiCard from '@/components/ui/KpiCard.vue'
import FilterDropdown from '@/components/ui/FilterDropdown.vue'
import type { ECharts } from 'echarts'
import {
  getPaymentAnalysis,
  getInvoiceStatusStats,
  getPaymentTrend,
  type PaymentTrendItem,
  type InvoiceStatusStats,
} from '@/api/analytics'
import { formatCurrency } from '@/utils/formatters'
import { getIndustryTypes } from '@/api/customers'
import { getManagers } from '@/api/users'
import type { IndustryType } from '@/types'

import CustomerSearchInput from '@/views/customers/components/CustomerSearchInput.vue'

/** ECharts 统一配色序列 */
const CHART_COLORS = ['#1D4ED8', '#0891B2', '#059669', '#D97706', '#DC2626', '#7C3AED']
const TEXT_MUTED = '#475569'
const TEXT_INK = '#0F172A'
const AXIS_LINE = '#DBE3EF'
const SPLIT_LINE = '#F1F5F9'

// --- 统一筛选 ---
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

// 月度趋势数据
const paymentTrend = ref<PaymentTrendItem[]>([])

// 状态统计
const statusStats = ref<InvoiceStatusStats[]>([])

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

// 重置
const handleReset = () => {
  timeRange.value = '3month'
  Object.assign(filters, createDefaultFilters())
  handleTimeRangeChange()
}

// 构建筛选参数
const buildFilterParams = () => ({
  start_date: filters.start_date || undefined,
  end_date: filters.end_date || undefined,
  keyword: filters.keyword || undefined,
  account_type: filters.account_type || undefined,
  industry: filters.industry.length > 0 ? filters.industry.join(',') : undefined,
  scale_level: filters.scale_level || undefined,
  consume_level: filters.consume_level || undefined,
  manager_id: filters.manager_id || undefined,
  sales_manager_id: filters.sales_manager_id || undefined,
})

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    await Promise.all([loadPaymentData(), loadStatusData(), loadTrendData()])
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 刷新
const handleRefresh = async () => {
  await loadData()
}

// 加载回款分析数据
const loadPaymentData = async () => {
  const res = await getPaymentAnalysis({
    ...buildFilterParams(),
    force_refresh: true,
  })
  const data = res.data || {}
  totalInvoiced.value = data.total_invoiced || 0
  totalDiscount.value = data.total_discount || 0
  totalPaid.value = data.total_paid || 0
  completionRate.value = data.completion_rate || 0
  difference.value = data.difference || 0
}

// 加载状态统计
const loadStatusData = async () => {
  const res = await getInvoiceStatusStats({
    ...buildFilterParams(),
    force_refresh: true,
  })
  statusStats.value = res.data || []
  initStatusChart()
}

// 加载月度趋势数据
const loadTrendData = async () => {
  const res = await getPaymentTrend({
    ...buildFilterParams(),
    months: 6,
    force_refresh: true,
  })
  paymentTrend.value = res.data || []
  initComparisonChart()
  initTrendChart()
}

// --- 图表初始化 ---
// 初始化对比图表（使用真实月度数据）
const initComparisonChart = () => {
  if (!comparisonChartRef.value) return

  if (comparisonChart) comparisonChart.dispose()
  comparisonChart = echarts.init(comparisonChartRef.value)

  const periodLabels = paymentTrend.value.map((item) => item.period)
  const invoicedData = paymentTrend.value.map((item) => item.invoiced)
  const paidData = paymentTrend.value.map((item) => item.paid)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      formatter: (params: any[]) => {
        let html = `${params[0].axisValue}<br/>`
        for (const p of params) {
          html += `${p.marker} ${p.seriesName}: ¥${Number(p.value).toLocaleString()}<br/>`
        }
        return html
      },
    },
    legend: {
      data: ['应收金额', '已回款'],
      textStyle: { color: TEXT_MUTED },
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: periodLabels,
      axisLine: { lineStyle: { color: AXIS_LINE } },
      axisLabel: { color: TEXT_MUTED },
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: '¥{value}', color: TEXT_MUTED },
      splitLine: { lineStyle: { color: SPLIT_LINE } },
    },
    series: [
      {
        name: '应收金额',
        type: 'bar',
        data: invoicedData,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#1D4ED8' },
            { offset: 1, color: '#1E40AF' },
          ]),
        },
      },
      {
        name: '已回款',
        type: 'bar',
        data: paidData,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#059669' },
            { offset: 1, color: '#047857' },
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

  if (statusChart) statusChart.dispose()
  statusChart = echarts.init(statusChartRef.value)

  const statusColors: Record<string, string> = {
    draft: '#94A3B8',
    pending_ops: '#F59E0B',
    pending_sales: '#FBBF24',
    pending_customer: '#D97706',
    customer_confirmed: '#1D4ED8',
    paid: '#059669',
    completed: '#0891B2',
    cancelled: '#DC2626',
  }

  const statusNames: Record<string, string> = {
    draft: '草稿',
    pending_ops: '待运营确认',
    pending_sales: '待销售确认',
    pending_customer: '待客户确认',
    customer_confirmed: '客户已确认',
    paid: '已付款',
    completed: '已完成',
    cancelled: '已取消',
  }

  const option = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      textStyle: { color: TEXT_MUTED, fontSize: 12 },
    },
    series: [
      {
        name: '结算单状态',
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
        data: statusStats.value.map((item) => ({
          name: statusNames[item.name] || item.name,
          value: item.count,
          itemStyle: { color: statusColors[item.name] || '#94A3B8' },
        })),
      },
    ],
  }

  statusChart.setOption(option)
}

// 初始化趋势图表（使用真实月度数据）
const initTrendChart = () => {
  if (!trendChartRef.value) return

  if (trendChart) trendChart.dispose()
  trendChart = echarts.init(trendChartRef.value)

  const periodLabels = paymentTrend.value.map((item) => item.period)
  const paidData = paymentTrend.value.map((item) => item.paid)

  const option = {
    tooltip: {
      trigger: 'axis',
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      formatter: (params: any[]) => {
        const p = params[0]
        return `${p.axisValue}<br/>${p.marker} ${p.seriesName}: ¥${Number(p.value).toLocaleString()}`
      },
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: periodLabels,
      axisLine: { lineStyle: { color: AXIS_LINE } },
      axisLabel: { color: TEXT_MUTED },
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: '¥{value}', color: TEXT_MUTED },
      splitLine: { lineStyle: { color: SPLIT_LINE } },
    },
    series: [
      {
        name: '回款金额',
        type: 'line',
        smooth: true,
        data: paidData,
        itemStyle: { color: CHART_COLORS[2] },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(5, 150, 105, 0.3)' },
            { offset: 1, color: 'rgba(5, 150, 105, 0.05)' },
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
  comparisonChart?.dispose()
  statusChart?.dispose()
  trendChart?.dispose()
})
</script>

<style scoped>
.payment-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px 24px 44px;
  max-width: 1440px;
  margin: 0 auto;
}

.payment-page :deep(.page-header) {
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

@media (max-width: 1100px) {
  .grid-4 {
    grid-template-columns: repeat(2, 1fr);
  }
  .grid-2 {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .grid-4 {
    grid-template-columns: 1fr;
  }
  .filters {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
