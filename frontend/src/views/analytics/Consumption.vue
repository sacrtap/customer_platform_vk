<template>
  <div class="consumption-analysis-page">
    <AppPageHeader
      title="消耗分析"
      description="多维度客户消耗数据统计与趋势分析"
      eyebrow="ANALYTICS"
    >
      <template #actions>
        <a-button
          :disabled="isSyncing"
          @click="handleSyncButtonClick"
        >
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path fill-rule="evenodd" d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2v1z"/>
            </svg>
          </template>
          <template v-if="isSyncing">
            数据同步 {{ Math.round((syncProgress?.percentage || 0) * 100) }}%
          </template>
          <template v-else>
            数据同步
          </template>
        </a-button>
        <SyncDialog
          v-model:visible="showSyncDialog"
          v-model:minimized="syncMinimized"
          @success="handleSyncSuccess"
          @progress="handleProgressUpdate"
        />
        <a-button :loading="loading" @click="handleRefresh">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path fill-rule="evenodd" d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2v1z"/>
            </svg>
          </template>
          刷新
        </a-button>
      </template>
    </AppPageHeader>

    <FilterPanel>
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
            <a-option value="12month">最近 12 月</a-option>
            <a-option value="custom">自定义</a-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="timeRange === 'custom'" label="开始日期">
          <a-date-picker
            v-model="dateRange[0]"
            style="width: 160px"
            placeholder="开始日期"
            @change="handleDateRangeChange"
          />
        </a-form-item>
        <a-form-item v-if="timeRange === 'custom'" label="结束日期">
          <a-date-picker
            v-model="dateRange[1]"
            style="width: 160px"
            placeholder="结束日期"
            @change="handleDateRangeChange"
          />
        </a-form-item>
        <a-form-item label="关键词">
          <KeywordAutoComplete
            v-model:keywords="filters.keyword"
            placeholder="客户/设备关键词"
            style="width: 220px"
          />
        </a-form-item>
        <a-form-item label="设备类型">
          <a-select
            v-model="filters.device_type"
            placeholder="请选择"
            style="width: 160px"
            allow-clear
          >
            <a-option value="X">X</a-option>
            <a-option value="N">N</a-option>
            <a-option value="L">L</a-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-button type="primary" :loading="loading" @click="handleSearch">
            查询
          </a-button>
          <a-button @click="handleReset">重置</a-button>
        </a-form-item>
      </a-form>
    </FilterPanel>

    <MetricGrid>
      <MetricCard
        label="总消耗"
        :value="formatCurrency(totalConsumption)"
      />
      <MetricCard
        label="日均消耗"
        :value="formatCurrency(avgDailyConsumption)"
      />
      <MetricCard
        label="峰值日期"
        :value="peakDate || '-'"
      />
      <MetricCard
        label="Top10 占比"
        :value="top10Percentage ? top10Percentage.toFixed(1) + '%' : '-'"
      />
      <MetricCard
        label="同步质量"
        :value="syncQuality || '-'"
      />
    </MetricGrid>

    <div class="charts-section">
      <ChartCard title="消耗趋势">
        <div class="chart-tabs">
          <a-radio-group v-model="trendMetric" type="button" button-style="outline" size="small">
            <a-button :value="'cost'">消耗金额</a-button>
            <a-button :value="'order_count'">订单量</a-button>
          </a-radio-group>
        </div>
        <div ref="trendChartRef" class="chart-container" />
      </ChartCard>

      <div class="charts-row">
        <ChartCard title="设备类型分布">
          <div class="chart-tabs">
            <a-radio-group v-model="deviceMetric" type="button" button-style="outline" size="small">
              <a-button :value="'cost'">消耗金额</a-button>
              <a-button :value="'order_count'">订单量</a-button>
            </a-radio-group>
          </div>
          <div ref="deviceChartRef" class="chart-container" />
        </ChartCard>

        <ChartCard title="Top 10 客户排行">
          <div class="chart-tabs">
            <a-radio-group v-model="topMetric" type="button" button-style="outline" size="small">
              <a-button :value="'cost'">消耗金额</a-button>
              <a-button :value="'order_count'">订单量</a-button>
            </a-radio-group>
          </div>
          <div class="top-customers-table">
            <a-table
              :columns="topColumns"
              :data="topCustomers"
              :pagination="false"
              :bordered="false"
              row-key="customer_id"
            >
              <template #rank="{ index }">
                <span class="rank-badge" :class="index < 3 ? 'top-' + (index + 1) : ''">
                  #{{ index + 1 }}
                </span>
              </template>
              <template #metric="{ record }">
                <span class="metric-value">
                  {{ topMetric.value === 'cost' ? formatCurrency(record.cost) : formatNumber(record.order_count) }}
                </span>
              </template>
              <template #percentage="{ record }">
                <div class="percentage-bar">
                  <div
                    class="percentage-fill"
                    :style="{ width: totalMetricValue.value > 0 ? ((topMetric.value === 'cost' ? record.cost : record.order_count) / totalMetricValue.value) * 100 + '%' : '0%' }"
                  />
                </div>
                <span class="percentage-text">
                  {{ totalMetricValue.value > 0 ? (((topMetric.value === 'cost' ? record.cost : record.order_count) / totalMetricValue.value) * 100).toFixed(1) : 0 }}%
                </span>
              </template>
            </a-table>
          </div>
        </ChartCard>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
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
import type { SyncTask } from '@/api/syncTasks'
import { formatCurrency, formatNumber } from '@/utils/formatters'

import KeywordAutoComplete from '@/components/KeywordAutoComplete.vue'
import SyncDialog from './components/SyncDialog.vue'

import {
  AppPageHeader,
  FilterPanel,
  MetricGrid,
  MetricCard,
  ChartCard,
} from '@/components/dashboard'

const filters = reactive({
  start_date: '',
  end_date: '',
  keyword: '',
  device_type: '',
})

const timeRange = ref('3month')
const dateRange = ref<[Date, Date] | null>(null)

const trendMetric = ref<'cost' | 'order_count'>('cost')
const deviceMetric = ref<'cost' | 'order_count'>('cost')
const topMetric = ref<'cost' | 'order_count'>('cost')

const loading = ref(false)
const showSyncDialog = ref(false)
const syncMinimized = ref(false)
const syncProgress = ref<SyncTask | null>(null)

const isSyncing = computed(() => {
  return !!(syncProgress.value &&
         syncProgress.value.status === 'running' &&
         syncProgress.value.percentage < 1)
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
const deviceChartRef = ref<HTMLElement>()
let trendChart: ECharts | null = null
let deviceChart: ECharts | null = null

const totalConsumption = ref(0)
const avgDailyConsumption = ref(0)
const peakDate = ref<string>('')
const top10Percentage = ref(0)
const syncQuality = ref<string>('')

const trendData = ref<ConsumptionTrendItem[]>([])
const topCustomers = ref<TopCustomer[]>([])
const deviceDistribution = ref<DeviceDistributionItem[]>([])

const topColumns = [
  { title: '排名', slotName: 'rank', width: 60, align: 'center' as const },
  { title: '客户', dataIndex: 'customer_name', width: 200 },
  { title: '消耗金额', slotName: 'metric', width: 140, align: 'right' as const },
  { title: '占比', slotName: 'percentage', width: 120, align: 'right' as const },
]

const totalMetricValue = computed(() => {
  return topCustomers.value.reduce((sum, c) => sum + (topMetric.value === 'cost' ? c.cost : c.order_count), 0)
})

const handleTimeRangeChange = (value: string) => {
  timeRange.value = value
  if (value !== 'custom') {
    const end = new Date()
    const start = new Date()
    const months = value === '1month' ? 1 : value === '3month' ? 3 : value === '6month' ? 6 : 12
    start.setMonth(start.getMonth() - months)
    filters.start_date = start.toISOString().split('T')[0]
    filters.end_date = end.toISOString().split('T')[0]
    dateRange.value = null
    handleSearch()
  } else {
    dateRange.value = null
  }
}

const handleDateRangeChange = () => {
  if (dateRange.value && dateRange.value[0] && dateRange.value[1]) {
    filters.start_date = dateRange.value[0].toISOString().split('T')[0]
    filters.end_date = dateRange.value[1].toISOString().split('T')[0]
  }
}

const loadData = async () => {
  loading.value = true
  try {
    await Promise.all([
      loadTrend(),
      loadTopCustomers(),
      loadDeviceDistribution(),
    ])
  } finally {
    loading.value = false
  }
}

const loadTrend = async () => {
  const params: Record<string, string | number | undefined> = { start_date: filters.start_date, end_date: filters.end_date }
  if (filters.device_type) params.device_type = filters.device_type
  const res = await getConsumptionTrend(params)
  trendData.value = res.data
  renderTrendChart()
  computeMetrics()
}

const loadTopCustomers = async () => {
  const params: Record<string, string | number | undefined> = { start_date: filters.start_date, end_date: filters.end_date, limit: 10 }
  if (filters.device_type) params.device_type = filters.device_type
  const res = await getTopCustomers(params)
  topCustomers.value = res.data
}

const loadDeviceDistribution = async () => {
  const params: Record<string, string | number | undefined> = { start_date: filters.start_date, end_date: filters.end_date }
  if (filters.device_type) params.device_type = filters.device_type
  const res = await getDeviceDistribution(params)
  deviceDistribution.value = res.data
  renderDeviceChart?.()
}

const computeMetrics = () => {
  if (trendData.value.length > 0) {
    totalConsumption.value = trendData.value.reduce((sum, d) => sum + d.cost, 0)
    avgDailyConsumption.value = totalConsumption.value / trendData.value.length
    const peak = trendData.value.reduce((max, d) => d.cost > max.cost ? d : max, trendData.value[0])
    peakDate.value = peak.date
  }
}

const renderTrendChart = () => {
  if (!trendChartRef.value || !trendData.value.length) return
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }
  const xData = trendData.value.map(d => d.date)
  const yData = trendData.value.map(d => trendMetric.value === 'cost' ? d.cost : d.order_count)
  const option = {
    grid: { top: 10, right: 10, bottom: 40, left: 50 },
    xAxis: { type: 'category', data: xData, axisLine: { lineStyle: { color: 'var(--cop-line)' } }, axisLabel: { color: 'var(--cop-muted)' } },
    yAxis: { type: 'value', axisLine: { lineStyle: { color: 'var(--cop-line)' } }, axisLabel: { color: 'var(--cop-muted)' }, splitLine: { lineStyle: { color: 'var(--cop-line)', type: 'dashed' } } },
    series: [{ data: yData, type: 'line', smooth: true, lineStyle: { width: 2, color: 'var(--cop-primary)' }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(14, 165, 233, 0.2)' }, { offset: 1, color: 'rgba(14, 165, 233, 0)' }] } }, symbol: 'none' }],
    tooltip: { trigger: 'axis', formatter: (params: { axis: string; value: number }[]) => `${params[0].axis}<br/>${trendMetric.value === 'cost' ? formatCurrency(params[0].value) : formatNumber(params[0].value)}` },
  }
  trendChart.setOption(option)
  window.addEventListener('resize', () => trendChart?.resize())
}

const renderDeviceChart = () => {
  if (!deviceChartRef.value || !deviceDistribution.value.length) return
  if (!deviceChart) {
    deviceChart = echarts.init(deviceChartRef.value)
  }
  const data = deviceDistribution.value.map(d => ({
    name: d.device_type,
    value: deviceMetric.value === 'cost' ? d.cost : d.order_count,
  }))
  const option = {
    tooltip: { trigger: 'item', formatter: (params: { name: string; value: number; percent: number }) => `${params.name}<br/>${deviceMetric.value === 'cost' ? formatCurrency(params.value) : formatNumber(params.value)} (${params.percent}%)` },
    legend: { bottom: 0, left: 'center', textStyle: { color: 'var(--cop-ink)' } },
    series: [{ type: 'pie', radius: ['40%', '70%'], avoidLabelOverlap: false, label: { show: false }, emphasis: { label: { show: true, fontSize: 12, fontWeight: 'bold' } }, labelLine: { show: false }, data, itemStyle: { borderRadius: 4 } }],
    color: ['#0ea5e9', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'],
  }
  deviceChart.setOption(option)
  window.addEventListener('resize', () => deviceChart?.resize())
}

watch(trendMetric, () => {
  renderTrendChart()
})
watch(deviceMetric, () => {
  renderDeviceChart()
})
watch(topMetric, () => {
  // top customers table is reactive
})

const handleSearch = () => {
  loadData()
}

const handleReset = () => {
  filters.start_date = ''
  filters.end_date = ''
  filters.keyword = ''
  filters.device_type = ''
  timeRange.value = '3month'
  dateRange.value = null
  const end = new Date()
  const start = new Date()
  start.setMonth(start.getMonth() - 3)
  filters.start_date = start.toISOString().split('T')[0]
  filters.end_date = end.toISOString().split('T')[0]
  loadData()
}

const handleRefresh = () => {
  loadData()
}

const handleSyncSuccess = () => {
  showSyncDialog.value = false
  syncMinimized.value = false
  loadData()
  Message.success('同步成功')
}

onMounted(() => {
  handleReset()
  loadData()
})

onUnmounted(() => {
  trendChart?.dispose()
  deviceChart?.dispose()
})
</script>

<style scoped>
.consumption-analysis-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.charts-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.chart-tabs {
  margin-bottom: 12px;
}
.chart-container {
  width: 100%;
  height: 280px;
}
.top-customers-table :deep(.arco-table-td) {
  padding: 8px 12px;
}
.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  color: var(--cop-muted);
  background: var(--cop-bg);
}
.rank-badge.top-1 { background: linear-gradient(135deg, #fbbf24, #f59e0b); color: white; }
.rank-badge.top-2 { background: linear-gradient(135deg, #9ca3af, #6b7280); color: white; }
.rank-badge.top-3 { background: linear-gradient(135deg, #d97706, #92400e); color: white; }
.metric-value { font-weight: 600; }
.percentage-bar {
  height: 6px;
  background: var(--cop-line);
  border-radius: 3px;
  overflow: hidden;
  flex: 1;
  max-width: 100px;
}
.percentage-fill {
  height: 100%;
  background: var(--cop-primary);
  border-radius: 3px;
  transition: width 0.3s ease;
}
.percentage-text {
  margin-left: 8px;
  font-size: 12px;
  color: var(--cop-muted);
}
.device-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: var(--cop-primary-bg);
  color: var(--cop-primary);
}
.amount { font-weight: 600; color: var(--cop-ink); }
.order-count { color: var(--cop-muted); }
@media (max-width: 1024px) {
  .charts-row {
    grid-template-columns: 1fr;
  }
}
</style>