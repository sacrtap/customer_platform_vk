<!-- frontend/src/components/charts/BalanceTrendChart.vue -->
<template>
  <div class="balance-trend-chart">
    <div v-if="loading" class="chart-loading">
      <a-spin size="large" />
    </div>
    <div v-else ref="chartRef" class="chart-container"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import type { CallbackDataParams } from 'echarts/types/dist/shared'

interface TrendItem {
  month: string
  total_amount: number
  real_amount: number
  bonus_amount: number
}

const props = withDefaults(
  defineProps<{
    trend: TrendItem[]
    loading?: boolean
  }>(),
  {
    loading: false,
  }
)

const chartRef = ref<HTMLElement>()
let chart: ECharts | null = null

const initChart = () => {
  if (!chartRef.value) return

  if (chart) {
    chart.dispose()
  }

  chart = echarts.init(chartRef.value)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: CallbackDataParams | CallbackDataParams[]) => {
        const arr = Array.isArray(params) ? params : [params]
        if (arr.length === 0) return ''
        let result = `${(arr[0] as any).axisValue}<br/>`
        arr.forEach((param: CallbackDataParams) => {
          result += `${param.marker} ${param.seriesName}: ¥${(param.value as number).toLocaleString()}<br/>`
        })
        return result
      },
    },
    legend: {
      data: ['总余额', '实充余额', '赠送余额'],
      top: 0,
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
      data: props.trend.map((item) => item.month),
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
        name: '总余额',
        type: 'line',
        smooth: true,
        data: props.trend.map((item) => item.total_amount),
        itemStyle: {
          color: '#0369A1',
        },
        lineStyle: {
          width: 3,
        },
      },
      {
        name: '实充余额',
        type: 'line',
        smooth: true,
        data: props.trend.map((item) => item.real_amount),
        itemStyle: {
          color: '#22C55E',
        },
        lineStyle: {
          width: 2,
        },
      },
      {
        name: '赠送余额',
        type: 'line',
        smooth: true,
        data: props.trend.map((item) => item.bonus_amount),
        itemStyle: {
          color: '#F59E0B',
        },
        lineStyle: {
          width: 2,
          type: 'dashed',
        },
      },
    ],
  }

  chart.setOption(option)
}

const handleResize = () => {
  chart?.resize()
}

watch(
  () => props.trend,
  () => {
    initChart()
  },
  { deep: true }
)

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  chart?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.balance-trend-chart {
  width: 100%;
  height: 100%;
  position: relative;
}

.chart-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 350px;
}

.chart-container {
  width: 100%;
  height: 350px;
}
</style>
