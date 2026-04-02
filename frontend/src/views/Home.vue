<template>
  <div class="home">
    <!-- 统计卡片 -->
    <a-row :gutter="16" class="stats-row">
      <a-col :span="6">
        <a-card>
          <a-statistic title="客户总数" :value="dashboardStats.total_customers">
            <template #suffix>
              <a-tag v-if="dashboardStats.customer_growth > 0" color="green">+{{ dashboardStats.customer_growth }}%</a-tag>
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="本月消耗" :value="dashboardStats.monthly_consumption" :precision="2">
            <template #suffix>万元</template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="待确认结算单" :value="dashboardStats.pending_invoices">
            <template #suffix>
              <a-tag v-if="dashboardStats.pending_invoices > 0" color="orange">待处理</a-tag>
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic title="余额预警客户" :value="dashboardStats.warning_customers">
            <template #suffix>
              <a-tag v-if="dashboardStats.warning_customers > 0" color="red">预警</a-tag>
            </template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <!-- 图表区域 -->
    <a-row :gutter="16" class="chart-row">
      <a-col :span="12">
        <a-card title="月度消耗趋势">
          <div ref="consumptionChartRef" class="chart"></div>
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card title="客户分级分布">
          <div ref="customerLevelChartRef" class="chart"></div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 待办事项 -->
    <a-row :gutter="16" class="todo-row">
      <a-col :span="24">
        <a-card title="待办事项">
          <a-list :loading="todosLoading">
            <a-list-item v-for="todo in todos" :key="todo.id">
              <a-space>
                <a-tag :color="todo.type === 'invoice' ? 'orange' : 'red'">
                  {{ todo.type === 'invoice' ? '结算单' : '余额预警' }}
                </a-tag>
                <span>{{ todo.content }}</span>
                <a-tag color="gray">{{ todo.date }}</a-tag>
              </a-space>
            </a-list-item>
            <template #no-data>
              <a-empty description="暂无待办事项" />
            </template>
          </a-list>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import * as analyticsApi from '@/api/analytics'

const dashboardStats = reactive({
  total_customers: 0,
  customer_growth: 0,
  monthly_consumption: 0,
  pending_invoices: 0,
  warning_customers: 0,
})

const todos = ref<any[]>([])
const todosLoading = ref(false)

const consumptionChartRef = ref<HTMLElement>()
const customerLevelChartRef = ref<HTMLElement>()
let consumptionChart: ECharts | null = null
let customerLevelChart: ECharts | null = null

const loadDashboardStats = async () => {
  try {
    const res = await analyticsApi.getDashboardStats()
    Object.assign(dashboardStats, res.data)
  } catch (err: any) {
    console.error('加载仪表盘数据失败:', err)
  }
}

const loadTodos = async () => {
  todosLoading.value = true
  try {
    // TODO: 实现待办事项 API
    todos.value = [
      { id: 1, type: 'invoice', content: '3 月结算单待商务确认 (5 笔)', date: '今天' },
      { id: 2, type: 'warning', content: 'XX 公司余额不足 (剩余 ¥1,200)', date: '今天' },
      { id: 3, type: 'invoice', content: '2 月结算单待客户确认 (3 笔)', date: '昨天' },
    ]
  } catch (err: any) {
    console.error('加载待办事项失败:', err)
  } finally {
    todosLoading.value = false
  }
}

const initCharts = async () => {
  await nextTick()

  // 消耗趋势图
  if (consumptionChartRef.value) {
    consumptionChart = echarts.init(consumptionChartRef.value)
    try {
      const res = await analyticsApi.getDashboardChartData({ chart_type: 'consumption_trend' })
      consumptionChart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: {
          type: 'category',
          data: res.data.months || ['1 月', '2 月', '3 月', '4 月', '5 月', '6 月'],
        },
        yAxis: {
          type: 'value',
          name: '万元',
        },
        series: [
          {
            name: '消耗金额',
            type: 'line',
            data: res.data.values || [],
            smooth: true,
            areaStyle: {
              color: 'rgba(22, 93, 255, 0.1)',
            },
            itemStyle: {
              color: '#165dff',
            },
          },
        ],
      })
    } catch (err: any) {
      console.error('加载消耗趋势图失败:', err)
    }
  }

  // 客户分级饼图
  if (customerLevelChartRef.value) {
    customerLevelChart = echarts.init(customerLevelChartRef.value)
    try {
      const res = await analyticsApi.getDashboardChartData({ chart_type: 'customer_level' })
      customerLevelChart.setOption({
        tooltip: { trigger: 'item' },
        legend: {
          orient: 'vertical',
          left: 'left',
        },
        series: [
          {
            name: '客户等级',
            type: 'pie',
            radius: '50%',
            data: res.data.levels || [
              { value: 120, name: 'KA' },
              { value: 200, name: 'SKA' },
              { value: 150, name: '普通' },
            ],
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0, 0, 0, 0.5)',
              },
            },
          },
        ],
      })
    } catch (err: any) {
      console.error('加载客户分级图失败:', err)
    }
  }
}

onMounted(() => {
  loadDashboardStats()
  loadTodos()
  initCharts()

  window.addEventListener('resize', () => {
    consumptionChart?.resize()
    customerLevelChart?.resize()
  })
})
</script>

<style scoped>
.home {
  padding: 20px;
}

.stats-row {
  margin-bottom: 16px;
}

.chart-row {
  margin-bottom: 16px;
}

.chart {
  height: 300px;
  width: 100%;
}

.todo-row {
  margin-bottom: 16px;
}
</style>
