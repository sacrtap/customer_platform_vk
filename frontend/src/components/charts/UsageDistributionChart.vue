<!-- frontend/src/components/charts/UsageDistributionChart.vue -->
<template>
  <div class="usage-distribution-chart">
    <div v-if="loading" class="chart-loading">
      <a-spin size="large" />
    </div>
    <v-chart v-else :option="chartOption" :autoresize="true" class="chart-container" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { TitleComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import type { EChartsOption } from 'echarts'

use([CanvasRenderer, PieChart, TitleComponent, LegendComponent, TooltipComponent])

interface DistributionItem {
  device_type: string
  quantity: number
  percentage: number
}

const props = withDefaults(
  defineProps<{
    distribution: DistributionItem[]
    totalQuantity: number
    loading?: boolean
  }>(),
  {
    loading: false,
  }
)

const chartOption = computed<EChartsOption>(() => {
  const data = props.distribution.map((item) => ({
    name: item.device_type,
    value: item.quantity,
    percentage: item.percentage,
  }))

  const colors = ['#0369A1', '#0284C7', '#0EA5E9', '#38BDF8', '#7DD3FC', '#BAE6FD']

  const option = {
    color: colors,
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        return `${params.name}<br/>用量：${params.value.toLocaleString()}<br/>占比：${params.data.percentage}%`
      },
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      itemWidth: 12,
      itemHeight: 12,
      textStyle: {
        fontSize: 13,
        color: '#374151',
      },
    },
    series: [
      {
        name: '设备类型分布',
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 2,
        },
        label: {
          show: false,
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold',
            formatter: '{b}\n{d}%',
          },
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.2)',
          },
        },
        labelLine: {
          show: false,
        },
        data: data,
      },
    ],
    graphic: [
      {
        type: 'text',
        left: '35%',
        top: '45%',
        style: {
          text: '总用量',
          textAlign: 'center',
          fill: '#6B7280',
          fontSize: 14,
        },
      },
      {
        type: 'text',
        left: '35%',
        top: '55%',
        style: {
          text: props.totalQuantity.toLocaleString(),
          textAlign: 'center',
          fill: '#111827',
          fontSize: 24,
          fontWeight: 'bold',
        },
      },
    ],
  }

  return option as EChartsOption
})
</script>

<style scoped>
.usage-distribution-chart {
  width: 100%;
  height: 100%;
  min-height: 318px;
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  border: 1px solid #eef0f3;
  position: relative;
}

.chart-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 300px;
}

.chart-container {
  width: 100%;
  height: 300px;
  min-height: 300px;
}
</style>
