<template>
  <div class="consumption-analysis-page">
    <div class="page-header">
      <div class="header-title">
        <h1>消耗分析</h1>
        <p class="header-subtitle">多维度客户消耗数据统计与趋势分析</p>
      </div>
      <div class="header-actions">
        <a-button :loading="syncLoading" :disabled="syncLoading" @click="handleSync">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path fill-rule="evenodd" d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2v1z"/>
            </svg>
          </template>
          {{ syncLoading ? '同步中...' : '数据同步' }}
        </a-button>
        <a-button :loading="loading" @click="handleRefresh">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path fill-rule="evenodd" d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2v1z"/>
            </svg>
          </template>
          刷新
        </a-button>
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
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import {
  getConsumptionTrend,
  getTopCustomers,
  getDeviceDistribution,
  manualSyncConsumption,
  type ConsumptionTrendItem,
  type TopCustomer,
  type DeviceDistributionItem,
} from '@/api/analytics'

import KeywordAutoComplete from '@/components/KeywordAutoComplete.vue'
import { formatCurrency, formatNumber } from '@/utils/formatters'

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
const syncLoading = ref(false)
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

// 同步数据
const handleSync = async () => {
  syncLoading.value = true
  try {
    const res = await manualSyncConsumption()
    if (res.code === 0) {
      Message.success(`同步成功！订单：${res.data.order_sync.success}条，费用：${res.data.cost_calc.calculated}条`)
      // 同步完成后自动刷新数据
      await loadData()
    } else {
      Message.error(res.message || '同步失败')
    }
  } catch (error: unknown) {
    const msg =
      error instanceof Error
        ? error.message
        : (error as { message?: string })?.message || '同步失败'
    Message.error(msg)
  } finally {
    syncLoading.value = false
  }
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
          color: '#999'
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
        color: '#646a73'
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
          color: '#e0e2e7',
        },
      },
      axisLabel: {
        color: '#646a73',
      },
    },
    yAxis: [
      {
        type: 'value',
        name: '结算费用',
        position: 'left',
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
      {
        type: 'value',
        name: '订单数量',
        position: 'right',
        axisLabel: {
          formatter: '{value} 单',
          color: '#646a73',
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
          color: '#0369A1',
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(3, 105, 161, 0.3)' },
            { offset: 1, color: 'rgba(3, 105, 161, 0.05)' },
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
          color: '#10B981',
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(16, 185, 129, 0.3)' },
            { offset: 1, color: 'rgba(16, 185, 129, 0.05)' },
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
          value: deviceMetric.value === 'cost' ? item.cost : item.order_count,
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
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-title h1 {
  font-size: 24px;
  font-weight: 600;
  color: #1d2330;
  margin: 0 0 8px 0;
}

.header-subtitle {
  font-size: 14px;
  color: #646a73;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.filter-section {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 24px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.stat-label {
  font-size: 14px;
  color: #646a73;
  margin-bottom: 12px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #1d2330;
  margin-bottom: 8px;
}

.stat-trend {
  display: flex;
  align-items: center;
  font-size: 13px;
}

.trend-label {
  color: #646a73;
  margin-right: 8px;
}

.trend-value {
  color: #10B981;
  font-weight: 500;
}

.trend-value.trend-down {
  color: #FF4D4F;
}

.charts-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.chart-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.chart-card.full-width {
  grid-column: span 2;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: #1d2330;
  margin: 0;
}

.chart-container {
  height: 300px;
}

.top-customers-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.top-customer-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.top-customer-item:hover {
  background: #f5f6f7;
}

.top-customer-item.is-top {
  background: linear-gradient(135deg, #FFF7E6 0%, #FFFFFF 100%);
  border-left: 3px solid #FAAD14;
}

.rank {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #f5f6f7;
  margin-right: 12px;
}

.rank-num {
  font-size: 14px;
  font-weight: 600;
  color: #646a73;
}

.top-customer-item.is-top .rank-num {
  color: #FAAD14;
  font-weight: bold;
}

.rank-rank-1 {
  background: linear-gradient(135deg, #FAAD14 0%, #FFC53D 100%);
  color: #fff;
}

.rank-rank-2 {
  background: linear-gradient(135deg, #C0C0C0 0%, #E8E8E8 100%);
  color: #fff;
}

.rank-rank-3 {
  background: linear-gradient(135deg, #CD7F32 0%, #E6A866 100%);
  color: #fff;
}

.customer-info {
  flex: 1;
}

.customer-name {
  font-size: 14px;
  font-weight: 500;
  color: #1d2330;
  margin-bottom: 4px;
}

.customer-id {
  font-size: 12px;
  color: #646a73;
}

.customer-amount {
  font-size: 14px;
  font-weight: 600;
  color: #0369A1;
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
