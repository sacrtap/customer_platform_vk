<!-- frontend/src/components/charts/HealthGauge.vue -->
<template>
  <div ref="chartRef" class="health-gauge"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = withDefaults(
  defineProps<{
    score: number
    level: string
  }>(),
  {}
)

const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

const getColorByScore = (score: number) => {
  if (score >= 80) return '#22c55e'
  if (score >= 60) return '#f59e0b'
  return '#ef4444'
}

const initChart = () => {
  if (!chartRef.value) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)

  const color = getColorByScore(props.score)
  const score = props.score

  const option = {
    series: [
      {
        type: 'pie',
        radius: ['70%', '85%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        hoverAnimation: false,
        label: {
          show: false,
        },
        data: [
          {
            value: score,
            itemStyle: {
              color: color,
            },
          },
          {
            value: 100 - score,
            itemStyle: {
              color: '#e5e7eb',
            },
          },
        ],
      },
    ],
    graphic: {
      elements: [
        {
          type: 'text',
          left: 'center',
          top: '40%',
          style: {
            text: `${score}`,
            fontSize: 36,
            fontWeight: 700,
            fill: '#1d2330',
          },
        },
        {
          type: 'text',
          left: 'center',
          top: '65%',
          style: {
            text: props.level,
            fontSize: 14,
            fontWeight: 500,
            fill: '#646a73',
          },
        },
      ],
    },
  }

  chartInstance.setOption(option)
}

const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize()
  }
}

watch(
  () => [props.score, props.level],
  () => {
    initChart()
  }
)

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
  }
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.health-gauge {
  width: 100%;
  height: 100%;
  min-height: 200px;
}
</style>
