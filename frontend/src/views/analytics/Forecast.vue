<template>
  <div class="forecast-analysis-page">
    <PageHeader eyebrow="Analytics" title="预测消费" subtitle="基于历史用量估算的未来消费预测" />

    <!-- 数据就绪度横幅 -->
    <div
      v-if="readiness && readiness.months_with_data < readiness.total_months_target"
      class="readiness-banner"
    >
      <div class="readiness-icon">📊</div>
      <div class="readiness-content">
        <span class="readiness-title">数据积累中</span>
        <span class="readiness-desc">
          已有 {{ readiness.months_with_data }}/{{ readiness.total_months_target }} 个月实盘数据
          （客户覆盖
          {{ readiness.customer_coverage_pct }}%），当前预测为估算值，建议积累数据后评估准确度。
        </span>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div class="filter-card">
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
        <a-form-item label="设备类型">
          <a-select v-model="filters.deviceType" style="width: 120px" @change="loadData">
            <a-option value="">全部</a-option>
            <a-option value="L">L</a-option>
            <a-option value="N">N</a-option>
            <a-option value="X">X</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="客户">
          <KeywordAutoComplete
            v-model="filters.keyword"
            placeholder="公司名称/公司 ID"
            width="200"
          />
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" @click="loadData">查询</a-button>
            <a-button @click="handleReset">重置</a-button>
            <a-button @click="openConfigModal">
              <template #icon><icon-settings /></template>
              预测参数
            </a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </div>

    <!-- 预测参数配置弹框 -->
    <a-modal
      v-model:visible="showConfigModal"
      title="预测参数配置"
      width="540px"
      :confirm-loading="configModalLoading"
      ok-text="保存并重新预测"
      @ok="handleSavePrices"
      @cancel="handleConfigCancel"
    >
      <div class="config-form">
        <div class="config-section">
          <h4 class="section-title">单价配置</h4>
          <p class="section-desc">修改各设备类型的单价后，系统将基于新单价重新计算预测值</p>
          <div class="price-grid">
            <div v-for="item in priceConfig" :key="item.device_type" class="price-row">
              <span class="price-label">{{ item.device_type }} 型设备</span>
              <div class="price-input-group">
                <a-input-number
                  v-model="item.unit_price"
                  :min="0"
                  :max="999"
                  :precision="2"
                  :step="1"
                  size="medium"
                  style="width: 140px"
                />
                <span class="price-unit">元/套</span>
              </div>
            </div>
          </div>
          <a-button size="small" type="text" @click="handleResetPrices">
            <template #icon><icon-refresh /></template>
            重置为默认值
          </a-button>
        </div>

        <a-divider />

        <div class="config-section">
          <h4 class="section-title">预测范围</h4>
          <div class="range-row">
            <span class="range-label">应用方式</span>
            <a-radio-group v-model="forecastParams.applyTo" type="button" size="medium">
              <a-radio value="all">更新历史及后续月份</a-radio>
              <a-radio value="future_only">仅后续月份</a-radio>
            </a-radio-group>
          </div>
          <div class="range-row">
            <span class="range-label">预测月数</span>
            <a-select v-model="forecastParams.forecastMonths" style="width: 140px" size="medium">
              <a-option :value="3">3 个月</a-option>
              <a-option :value="6">6 个月</a-option>
              <a-option :value="12">12 个月</a-option>
              <a-option :value="24">24 个月</a-option>
            </a-select>
          </div>
        </div>

        <a-divider />

        <div class="config-section hint-section">
          <icon-info-circle />
          <span>修改预测参数后，预测数据将重新计算，耗时取决于客户量级</span>
        </div>
      </div>
    </a-modal>

    <!-- 重新预测进度弹框 -->
    <a-modal
      v-model:visible="showProgressModal"
      title="正在重新预测"
      :footer="false"
      :mask-closable="false"
      :closable="false"
      width="400px"
    >
      <div class="progress-body">
        <div class="progress-spinner">
          <a-spin :size="48" />
        </div>
        <p class="progress-text">正在基于新参数重新计算预测值...</p>
        <div class="progress-bar">
          <a-progress :percent="progressPercent" :status="progressStatus" :animation="true" />
        </div>
        <p class="progress-hint">
          <template v-if="progressPercent < 30">正在加载单价配置...</template>
          <template v-else-if="progressPercent < 60">正在计算客户预测值...</template>
          <template v-else-if="progressPercent < 90">正在生成趋势数据...</template>
          <template v-else>即将完成</template>
        </p>
      </div>
    </a-modal>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">预测消费总额</div>
        <div class="stat-value">{{ formatCurrency(summary.total_forecast) }}</div>
        <div class="stat-trend">
          <span class="confidence-tag" :class="'confidence-' + summary.confidence">
            {{ confidenceLabel(summary.confidence) }}置信度
          </span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">本月实盘</div>
        <div class="stat-value success">{{ formatCurrency(summary.actual_this_month) }}</div>
        <div class="stat-trend">
          <span class="trend-label">环比</span>
          <span class="trend-value" :class="momClass">{{
            formatMom(summary.month_over_month_change)
          }}</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">覆盖客户</div>
        <div class="stat-value">
          {{ summary.active_customer_count
          }}<span class="stat-sub">/{{ summary.total_customer_count }}</span>
        </div>
        <div class="stat-trend">
          <span class="trend-label">活跃客户预测数</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">数据就绪度</div>
        <div class="stat-value">
          {{ readiness ? readiness.months_with_data : 0 }}<span class="stat-sub">/12 月</span>
        </div>
        <div class="stat-trend">
          <span class="trend-label">已积累实盘数据</span>
        </div>
      </div>
    </div>

    <!-- 预测趋势图 -->
    <div class="chart-section">
      <div class="chart-card full-width">
        <div class="chart-header">
          <h3>月度消费预测</h3>
        </div>
        <div ref="forecastChartRef" class="chart-container"></div>
      </div>
    </div>

    <!-- 设备类型拆解图 -->
    <div class="chart-section">
      <div class="chart-card full-width">
        <div class="chart-header">
          <h3>按设备类型拆解</h3>
        </div>
        <div ref="deviceChartRef" class="chart-container device-chart"></div>
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
        :data="forecastList"
        :loading="loading"
        row-key="customer_id"
        :pagination="pagination"
        @page-change="handlePageChange"
      >
        <template #amount="{ record }">
          <span class="forecast-amount">{{ formatCurrency(record.forecast_amount) }}</span>
        </template>
        <template #method="{ record }">
          <span class="method-tag" :class="'method-' + record.forecast_method">
            {{ methodLabel(record.forecast_method) }}
          </span>
        </template>
        <template #active="{ record }">
          <span v-if="record.is_active" class="active-tag active">活跃</span>
          <span v-else class="active-tag inactive">已休眠</span>
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
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconSettings, IconRefresh, IconInfoCircle } from '@arco-design/web-vue/es/icon'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import {
  getConsumptionForecast,
  getConsumptionForecastTrend,
  getDataReadiness,
  getPriceConfig,
  updatePriceConfig,
  type ConsumptionForecast,
  type ForecastSummary,
  type ForecastTrendItem,
  type DataReadiness,
  type UnitPriceItem,
} from '@/api/analytics'

import KeywordAutoComplete from '@/components/KeywordAutoComplete.vue'
import { formatCurrency } from '@/utils/formatters'

/** ECharts 统一配色 */
const TEXT_MUTED = '#475569'
const AXIS_LINE = '#DBE3EF'
const SPLIT_LINE = '#F1F5F9'

const router = useRouter()

const filters = reactive({
  year: new Date().getFullYear(),
  month: undefined as number | undefined,
  keyword: '',
  deviceType: '',
})

const selectedYear = ref(new Date())
const selectedMonth = ref<number | undefined>(undefined)

const forecastChartRef = ref<HTMLElement>()
const deviceChartRef = ref<HTMLElement>()
let forecastChart: ECharts | null = null
let deviceChart: ECharts | null = null

const loading = ref(false)
const forecastList = ref<ConsumptionForecast[]>([])
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

// 统计数据
const summary = reactive<ForecastSummary>({
  total_forecast: 0,
  actual_this_month: 0,
  month_over_month_change: 0,
  active_customer_count: 0,
  total_customer_count: 0,
  confidence: 'low',
})

// 数据就绪度
const readiness = ref<DataReadiness | null>(null)

// 弹框状态
const showConfigModal = ref(false)
const showProgressModal = ref(false)
const configModalLoading = ref(false)
const progressPercent = ref(0)
const progressStatus = ref<'active' | 'success'>('active')

// 价格配置（深拷贝备份用于取消还原）
const priceConfig = ref<UnitPriceItem[]>([])
const priceConfigBackup = ref<UnitPriceItem[]>([])
const defaultPrices: Record<string, number> = { L: 14.5, N: 30, X: 30 }

const forecastParams = reactive({
  applyTo: 'all' as 'all' | 'future_only',
  forecastMonths: 12,
})

// 加载价格配置
const loadPriceConfig = async () => {
  try {
    const res = await getPriceConfig()
    priceConfig.value = res.data || []
  } catch {
    // 默认值
    priceConfig.value = [
      { device_type: 'L', unit_price: 14.5 },
      { device_type: 'N', unit_price: 30 },
      { device_type: 'X', unit_price: 30 },
    ]
  }
}

// 打开配置弹框前备份当前价格
const openConfigModal = () => {
  backupPriceConfig()
  showConfigModal.value = true
}

// 备份当前价格（用于取消还原）
const backupPriceConfig = () => {
  priceConfigBackup.value = priceConfig.value.map((item) => ({ ...item }))
}

// 取消配置修改
const handleConfigCancel = () => {
  priceConfig.value = priceConfigBackup.value.map((item) => ({ ...item }))
  showConfigModal.value = false
}

// 模拟进度动画
const runProgressSimulation = async () => {
  progressPercent.value = 0
  progressStatus.value = 'active'
  const stages = [
    { to: 25, duration: 600 },
    { to: 50, duration: 1000 },
    { to: 75, duration: 1200 },
    { to: 90, duration: 800 },
  ]
  for (const stage of stages) {
    const start = progressPercent.value
    const steps = 10
    for (let i = 0; i < steps; i++) {
      await new Promise((r) => setTimeout(r, stage.duration / steps))
      progressPercent.value = start + ((stage.to - start) * (i + 1)) / steps
    }
  }
}

// 保存价格配置并重新预测
const handleSavePrices = async () => {
  configModalLoading.value = true
  try {
    const prices: Record<string, number> = {}
    priceConfig.value.forEach((item) => {
      prices[item.device_type] = item.unit_price
    })
    // 关闭配置弹框，打开进度弹框
    showConfigModal.value = false
    showProgressModal.value = true
    progressPercent.value = 0
    progressStatus.value = 'active'

    // 并行执行：更新价格 + 进度模拟
    await Promise.all([updatePriceConfig(prices), runProgressSimulation()])

    // 实际完成时进度跳到 100
    progressPercent.value = 100
    progressStatus.value = 'success'

    // 短暂展示完成状态后关闭并刷新
    await new Promise((r) => setTimeout(r, 500))
    showProgressModal.value = false
    await loadData()
    Message.success('预测已更新')
  } catch (error: unknown) {
    showProgressModal.value = false
    Message.error((error as Error).message || '重新预测失败')
  } finally {
    configModalLoading.value = false
    progressPercent.value = 0
  }
}

// 重置为默认值
const handleResetPrices = () => {
  priceConfig.value.forEach((item) => {
    if (defaultPrices[item.device_type] !== undefined) {
      item.unit_price = defaultPrices[item.device_type]
    }
  })
}

const columns = [
  { title: '公司 ID', dataIndex: 'company_id', width: 120 },
  { title: '客户名称', dataIndex: 'customer_name', width: 200 },
  { title: '设备类型', dataIndex: 'device_type', width: 90 },
  { title: '估算用量', dataIndex: 'estimated_usage', width: 100 },
  {
    title: '单价',
    dataIndex: 'unit_price',
    width: 90,
    render: ({ record }: { record: ConsumptionForecast }) => `¥${record.unit_price}/套`,
  },
  {
    title: '预测金额',
    slotName: 'amount',
    width: 120,
    sorter: (a: ConsumptionForecast, b: ConsumptionForecast) =>
      a.forecast_amount - b.forecast_amount,
  },
  { title: '方法', slotName: 'method', width: 100 },
  { title: '状态', slotName: 'active', width: 90 },
  { title: '操作', slotName: 'action', width: 80, fixed: 'right' as const },
]

const momClass = computed(() => {
  const v = summary.month_over_month_change
  if (v > 0) return 'mom-up'
  if (v < 0) return 'mom-down'
  return ''
})

const formatMom = (v: number) => {
  if (!v) return '—'
  return `${v > 0 ? '+' : ''}${v}%`
}

const confidenceLabel = (c: string) => {
  const map: Record<string, string> = { low: '低', medium: '中', high: '高' }
  return map[c] || '低'
}

const methodLabel = (m: string) => {
  const map: Record<string, string> = {
    historical_hold: '历史保持',
    cold_start: '冷启动',
    trimmed: '截断修正',
  }
  return map[m] || m
}

// 重置
const handleReset = () => {
  selectedYear.value = new Date()
  selectedMonth.value = undefined
  filters.keyword = ''
  filters.deviceType = ''
  filters.year = new Date().getFullYear()
  filters.month = undefined
  loadData()
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    filters.year = selectedYear.value?.getFullYear() || new Date().getFullYear()
    filters.month = selectedMonth.value

    await loadForecastData()
    await loadReadiness()
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 加载预测数据
const loadForecastData = async () => {
  const res = await getConsumptionForecast({
    year: filters.year,
    month: filters.month,
    keyword: filters.keyword || undefined,
    device_type: filters.deviceType || undefined,
    force_refresh: true,
    apply_to: forecastParams.applyTo,
    forecast_months: forecastParams.forecastMonths,
  })

  const responseData = res.data || { forecasts: [], summary: null }
  forecastList.value = responseData.forecasts || []
  pagination.total = forecastList.value.length

  const s = responseData.summary
  if (s) {
    summary.total_forecast = s.total_forecast || 0
    summary.actual_this_month = s.actual_this_month || 0
    summary.month_over_month_change = s.month_over_month_change || 0
    summary.active_customer_count = s.active_customer_count || 0
    summary.total_customer_count = s.total_customer_count || 0
    summary.confidence = s.confidence || 'low'
  }

  // 加载图表趋势数据
  await loadTrendData()
  initDeviceChart()
}

// 加载数据就绪度
const loadReadiness = async () => {
  try {
    const res = await getDataReadiness()
    readiness.value = res.data || null
  } catch {
    readiness.value = null
  }
}

// 加载趋势数据（全年 12 个月预测 vs 实际）
const trendData = ref<ForecastTrendItem[]>([])

const loadTrendData = async () => {
  try {
    const res = await getConsumptionForecastTrend({
      year: filters.year,
      force_refresh: true,
      apply_to: forecastParams.applyTo,
      forecast_months: forecastParams.forecastMonths,
    })
    trendData.value = res.data || []
  } catch {
    trendData.value = []
  }
  initForecastChart()
}

// 初始化预测图表
const initForecastChart = () => {
  if (!forecastChartRef.value) return

  if (forecastChart) {
    forecastChart.dispose()
  }

  forecastChart = echarts.init(forecastChartRef.value)

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

  const forecastData = months.map((_, index) => {
    const item = trendData.value[index]
    return item ? item.forecast : 0
  })
  const actualData = months.map((_, index) => {
    const item = trendData.value[index]
    return item && item.is_actual && item.actual !== null ? item.actual : null
  })

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
      formatter: (params: Array<{ seriesName: string; name: string; value: number }>) => {
        let html = `<div style="font-weight:600;margin-bottom:4px">${params[0].name}</div>`
        for (const p of params) {
          if (p.value !== null && p.value !== undefined) {
            html += `<div>${p.seriesName}：¥${Number(p.value).toLocaleString()}</div>`
          }
        }
        return html
      },
    },
    legend: {
      data: ['预测消费', '实际消费'],
      textStyle: {
        color: TEXT_MUTED,
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
          color: AXIS_LINE,
        },
      },
      axisLabel: {
        color: TEXT_MUTED,
      },
    },
    yAxis: {
      type: 'value',
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
    series: [
      {
        name: '预测消费',
        type: 'bar',
        data: forecastData,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#1D4ED8' },
            { offset: 1, color: '#1E40AF' },
          ]),
        },
      },
      {
        name: '实际消费',
        type: 'line',
        smooth: true,
        data: actualData,
        connectNulls: false,
        itemStyle: {
          color: '#059669',
        },
        lineStyle: {
          width: 3,
        },
        symbol: 'circle',
        symbolSize: 8,
      },
    ],
  }

  forecastChart.setOption(option)
}

// 初始化设备类型拆解图
const initDeviceChart = () => {
  if (!deviceChartRef.value) return

  if (deviceChart) {
    deviceChart.dispose()
  }

  deviceChart = echarts.init(deviceChartRef.value)

  // 按设备类型聚合预测金额
  const deviceAgg: Record<string, number> = {}
  forecastList.value.forEach((item) => {
    deviceAgg[item.device_type] = (deviceAgg[item.device_type] || 0) + item.forecast_amount
  })

  const colors: Record<string, string> = {
    L: '#1D4ED8',
    N: '#059669',
    X: '#D97706',
  }

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}：¥{c}（{d}%）',
    },
    legend: {
      bottom: 0,
      textStyle: {
        color: TEXT_MUTED,
      },
    },
    series: [
      {
        name: '预测消费',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        itemStyle: {
          borderRadius: 6,
          borderColor: '#fff',
          borderWidth: 2,
        },
        label: {
          color: TEXT_MUTED,
          formatter: '{b}\n¥{c}',
        },
        data: Object.entries(deviceAgg).map(([name, value]) => ({
          name: `${name} 系列`,
          value: Math.round(value),
          itemStyle: {
            color: colors[name] || '#64748B',
          },
        })),
      },
    ],
  }

  deviceChart.setOption(option)
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
  deviceChart?.resize()
}

onMounted(() => {
  loadPriceConfig()
  loadData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  forecastChart?.dispose()
  deviceChart?.dispose()
})
</script>

<style scoped>
.forecast-analysis-page {
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

/* 数据就绪度横幅 */
.readiness-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  background: linear-gradient(135deg, #eff6ff 0%, #f0fdfa 100%);
  border: 1px solid #bfdbfe;
  border-radius: var(--radius-lg);
  padding: 14px 20px;
}

.readiness-icon {
  font-size: 22px;
}

.readiness-content {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.readiness-title {
  font-weight: 700;
  color: #1e40af;
}

.readiness-desc {
  font-size: 13px;
  color: #475569;
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
}

.stat-value.success {
  color: var(--green);
}

.stat-value.warning {
  color: var(--amber);
}

.stat-sub {
  font-size: 14px;
  color: var(--muted);
  font-weight: 500;
}

.stat-trend {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  margin-top: 8px;
}

.trend-label {
  color: var(--muted);
}

.trend-value {
  font-weight: 600;
  color: var(--primary);
}

.trend-value.mom-up {
  color: var(--green);
}

.trend-value.mom-down {
  color: var(--red, #dc2626);
}

.confidence-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 100px;
  font-size: 12px;
  font-weight: 600;
}

.confidence-low {
  background: #fef3c7;
  color: #92400e;
}

.confidence-medium {
  background: #dbeafe;
  color: #1e40af;
}

.confidence-high {
  background: #d1fae5;
  color: #065f46;
}

.chart-section {
  margin-bottom: 0;
}

.chart-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.chart-card.full-width {
  grid-column: 1 / -1;
}

.chart-header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--line);
}

.chart-header h3 {
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
  margin: 0;
}

.chart-container {
  height: 400px;
  padding: 24px;
}

.chart-container.device-chart {
  height: 320px;
}

.table-section {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--line);
}

.table-header h3 {
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
  margin: 0;
}

/* 表头样式 */
.table-section :deep(.arco-table-th) {
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}

.forecast-amount {
  font-weight: 700;
  color: var(--primary);
}

/* 方法标注 */
.method-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.method-historical_hold {
  background: #dbeafe;
  color: #1e40af;
}

.method-cold_start {
  background: #fef3c7;
  color: #92400e;
}

.method-trimmed {
  background: #fce7f3;
  color: #9d174d;
}

/* 活跃标记 */
.active-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.active-tag.active {
  background: #d1fae5;
  color: #065f46;
}

.active-tag.inactive {
  background: #f1f5f9;
  color: #64748b;
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

/* 预测参数弹框样式 */
.config-form {
  padding: 4px 0;
}

.config-section {
  margin-bottom: 4px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 4px 0;
}

.section-desc {
  font-size: 12px;
  color: var(--muted);
  margin: 0 0 16px 0;
}

.price-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
}

.price-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--bg);
  border-radius: var(--radius);
  border: 1px solid var(--line);
}

.price-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--ink);
}

.price-input-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.price-unit {
  font-size: 13px;
  color: var(--muted);
}

.range-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
}

.range-label {
  font-size: 14px;
  color: var(--ink);
  min-width: 80px;
}

.hint-section {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--muted);
}

.hint-section .arco-icon {
  font-size: 15px;
  color: var(--primary);
  flex-shrink: 0;
}

/* 进度弹框样式 */
.progress-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 0 8px;
  gap: 16px;
}

.progress-spinner {
  display: flex;
  justify-content: center;
}

.progress-text {
  font-size: 15px;
  color: var(--ink);
  font-weight: 500;
  margin: 0;
}

.progress-bar {
  width: 100%;
  padding: 0 8px;
}

.progress-hint {
  font-size: 12px;
  color: var(--muted);
  margin: 0;
}
</style>
