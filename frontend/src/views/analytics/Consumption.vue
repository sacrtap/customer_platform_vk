<template>
  <div class="consumption-analysis-page">
    <PageHeader eyebrow="Analytics" title="消耗分析"
      subtitle="重构为“同步状态 + 关键指标 + 趋势/排行 + 明细钻取”四层，图表旁保留解释和异常入口。">
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
    </PageHeader>

    <!-- 同步状态提示 -->
    <SyncStatusBar status="ok" last-sync="10:00">
      <template #action>
        <a-button size="mini" @click="handleSyncButtonClick">手动同步</a-button>
      </template>
    </SyncStatusBar>

    <!-- 筛选区域 -->
    <div class="filter-card">
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
          <KeywordAutoComplete v-model="filters.keyword" placeholder="公司名称/公司 ID" width="200" />
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" @click="() => loadData()">查询</a-button>
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
        <div class="stat-value stat-value-sm">{{ topCustomer?.customer_name || '-' }}</div>
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
          <a-radio-group v-model="trendMetric" type="button" size="small" @change="() => loadData()">
            <a-radio value="cost">结算费用</a-radio>
            <a-radio value="order_count">订单数量</a-radio>
          </a-radio-group>
        </div>
        <div ref="trendChartRef" class="chart-container"></div>
      </div>

      <!-- 设备类型分布 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>设备类型分布</h3>
          <a-radio-group v-model="deviceMetric" type="button" size="small" @change="() => loadDeviceData()">
            <a-radio value="cost">结算费用</a-radio>
            <a-radio value="order_count">订单数量</a-radio>
          </a-radio-group>
        </div>
        <div ref="deviceChartRef" class="chart-container"></div>
      </div>

      <!-- Top10 客户排行榜 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>Top10 客户排行</h3>
          <a-radio-group v-model="topMetric" type="button" size="small" @change="() => loadTopCustomersData()">
            <a-radio value="cost">消耗金额</a-radio>
            <a-radio value="order_count">订单数量</a-radio>
          </a-radio-group>
        </div>
        <div class="top-customers-list">
          <div
            v-for="(customer, index) in topCustomers"
            :key="customer.customer_id"
            class="top-customer-item"
            :class="{ 'is-top': index < 3 }"
            @click="topCustomer = customer"
          >
            <div class="rank">
              <span :class="['rank-num', `rank-${index + 1}`]">{{ index + 1 }}</span>
            </div>
            <div class="customer-info">
              <div class="customer-name">{{ customer.customer_name }}</div>
              <div class="customer-id">{{ customer.company_id }}</div>
            </div>
            <div class="customer-amount">
              {{ topMetric === 'cost' ? formatCurrency(customer.cost) : formatNumber(customer.order_count) + ' 单' }}
            </div>
          </div>
          <a-empty v-if="topCustomers.length === 0" description="暂无数据" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import * as echarts from 'echarts'
import PageHeader from '@/components/PageHeader.vue'
import SyncStatusBar from '@/components/SyncStatusBar.vue'
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

/** ECharts 统一配色序列 */
const CHART_COLORS = ['#1D4ED8', '#0891B2', '#059669', '#D97706', '#DC2626', '#7C3AED']
const TEXT_MUTED = '#475569'
const TEXT_INK = '#0F172A'
const AXIS_LINE = '#DBE3EF'
const SPLIT_LINE = '#F1F5F9'

const filters = reactive({
  start_date: '',
  end_date: '',
  keyword: '',
})

const timeRange = ref('3month')
const dateRange = ref<[Date, Date] | null>(null)

// Metric 切换
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
    // 任务进行中，重新打开进度框
    syncMinimized.value = false
  }
  showSyncDialog.value = true
}

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
  filters.keyword = ''
  filters.start_date = ''
  filters.end_date = ''
  handleTimeRangeChange()
}

// 加载数据
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

// 刷新（强制跳过缓存）
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

// 同步成功回调
const handleSyncSuccess = async () => {
  Message.success('数据同步完成，正在刷新...')
  await loadData()
}
// 加载趋势数据
const loadTrendData = async (forceRefresh = false) => {
  const res = await getConsumptionTrend({
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
    keyword: filters.keyword || undefined,
    metric: trendMetric.value,
    force_refresh: forceRefresh || undefined,
  })
  consumptionTrend.value = res.data || []
  initTrendChart()
}

// 加载 Top 客户
const loadTopCustomersData = async (forceRefresh = false) => {
  const res = await getTopCustomers({
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
    limit: 10,
    metric: topMetric.value,
    force_refresh: forceRefresh || undefined,
  })
  topCustomers.value = res.data || []
  if (topCustomers.value.length > 0) {
    topCustomer.value = topCustomers.value[0]
  }
}

// 加载设备分布
const loadDeviceData = async (forceRefresh = false) => {
  const res = await getDeviceDistribution({
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
    keyword: filters.keyword || undefined,
    metric: deviceMetric.value,
    force_refresh: forceRefresh || undefined,
  })
  deviceDistribution.value = res.data || []
  initDeviceChart()
}

// 计算统计数据
const calculateStats = () => {
  if (consumptionTrend.value.length > 0) {
    totalConsumption.value = consumptionTrend.value.reduce(
      (sum, item) => sum + (item.cost || 0),
      0
    )

    // 计算日均消耗
    const days = consumptionTrend.value.length
    dailyAverage.value = totalConsumption.value / days

    // 计算环比（简单估算）
    if (consumptionTrend.value.length >= 2) {
      const last = consumptionTrend.value[consumptionTrend.value.length - 1].cost || 0
      const prev = consumptionTrend.value[consumptionTrend.value.length - 2].cost || 0
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
      axisPointer: {
        type: 'cross',
        crossStyle: {
          color: '#94A3B8'
        }
      },
      formatter: function(params: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
        let result = params[0].axisValue + '<br/>'
        params.forEach((param: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
          if (param.seriesName === '结算费用') {
            result += param.marker + param.seriesName + ': ¥' + param.value.toLocaleString() + '<br/>'
          } else {
            result += param.marker + param.seriesName + ': ' + param.value.toLocaleString() + ' 单<br/>'
          }
        })
        return result
      }
    },
    legend: {
      data: ['结算费用', '订单数量'],
      top: '0%',
      textStyle: {
        color: TEXT_MUTED
      }
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
      data: consumptionTrend.value.map((item) => item.date || item.period),
      axisLine: {
        lineStyle: {
          color: AXIS_LINE,
        },
      },
      axisLabel: {
        color: TEXT_MUTED,
      },
    },
    yAxis: [
      {
        type: 'value',
        name: '结算费用',
        position: 'left',
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
      {
        type: 'value',
        name: '订单数量',
        position: 'right',
        axisLabel: {
          formatter: '{value} 单',
          color: TEXT_MUTED,
        },
        splitLine: {
          show: false
        },
      }
    ],
    series: [
      {
        name: '结算费用',
        type: 'line',
        smooth: true,
        yAxisIndex: 0,
        data: consumptionTrend.value.map((item) => item.cost),
        itemStyle: {
          color: CHART_COLORS[0],
        },
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
        itemStyle: {
          color: CHART_COLORS[1],
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(8, 145, 178, 0.3)' },
            { offset: 1, color: 'rgba(8, 145, 178, 0.05)' },
          ]),
        },
      }
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
        color: TEXT_MUTED,
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
            color: TEXT_INK,
          },
        },
        labelLine: {
          show: false,
        },
        data: deviceDistribution.value.map((item, index) => ({
          name: item.device_type,
          value: deviceMetric.value === 'cost' ? item.cost : item.order_count,
          itemStyle: {
            color: CHART_COLORS[index % CHART_COLORS.length],
          },
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

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  deviceChart?.dispose()
})
</script>

<style scoped>
.consumption-analysis-page {
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

.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
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
  margin-bottom: 8px;
}

.stat-value-sm {
  font-size: 18px;
}

.stat-trend {
  display: flex;
  align-items: center;
  font-size: 13px;
}

.trend-label {
  color: var(--muted);
  margin-right: 8px;
}

.trend-value {
  color: var(--green);
  font-weight: 600;
}

.trend-value.trend-down {
  color: var(--red);
}

.charts-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.chart-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: 20px;
  overflow: hidden;
}

.chart-card.full-width {
  grid-column: 1 / -1;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-header h3 {
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
  margin: 0;
}

.chart-container {
  height: 300px;
}

/* Top customers list */
.top-customers-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.top-customer-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s;
}

.top-customer-item:hover {
  background: #F8FAFC;
}

.top-customer-item.is-top {
  background: linear-gradient(135deg, #FEF3C7 0%, #FFFFFF 100%);
  border-left: 3px solid var(--amber);
}

.rank {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #F1F5F9;
  margin-right: 12px;
  flex-shrink: 0;
}

.rank-num {
  font-size: 14px;
  font-weight: 700;
  color: var(--muted);
}

.top-customer-item.is-top .rank-num {
  color: var(--amber);
  font-weight: bold;
}

.rank-rank-1 {
  background: linear-gradient(135deg, #D97706 0%, #FBBF24 100%);
  color: #fff;
}

.rank-rank-2 {
  background: linear-gradient(135deg, #94A3B8 0%, #CBD5E1 100%);
  color: #fff;
}

.rank-rank-3 {
  background: linear-gradient(135deg, #B45309 0%, #D97706 100%);
  color: #fff;
}

.customer-info {
  flex: 1;
  min-width: 0;
}

.customer-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 4px;
}

.customer-id {
  font-size: 12px;
  color: var(--muted);
}

.customer-amount {
  font-size: 14px;
  font-weight: 700;
  color: var(--primary);
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .charts-section {
    grid-template-columns: 1fr;
  }

  .chart-card.full-width {
    grid-column: span 1;
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .header-actions {
    width: 100%;
  }

  .header-actions .arco-btn {
    flex: 1;
  }
}
</style>
