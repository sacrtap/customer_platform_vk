<template>
  <div class="health-analysis-page">
    <div class="page-header">
      <div class="header-title">
        <h1>健康度分析</h1>
        <p class="header-subtitle">客户活跃度监控与风险预警</p>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-header">
          <div
            class="stat-icon"
            style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path d="M8 3a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z" />
              <path
                d="m5.93 6.704-.847 6.783a1 1 0 0 0 1.094 1.12l1.13-1.13a1 1 0 0 1 1.394 0l1.13 1.13a1 1 0 0 0 1.094-1.12l-.847-6.783a1 1 0 0 0-.996-.876H6.926a1 1 0 0 0-.996.876zM6.002 1.5a2.5 2.5 0 0 1 4.996 0 2.5 2.5 0 0 1-4.996 0z"
              />
            </svg>
          </div>
          <div class="stat-label">总客户数</div>
        </div>
        <div class="stat-value">{{ totalCustomers }}</div>
      </div>

      <div class="stat-card">
        <div class="stat-header">
          <div
            class="stat-icon"
            style="background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%)"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z" />
              <path
                d="M10.97 4.97a.235.235 0 0 0-.02.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-1.071-1.05z"
              />
            </svg>
          </div>
          <div class="stat-label">活跃客户</div>
        </div>
        <div class="stat-value success">{{ activeCustomers }}</div>
        <div class="stat-extra">占比 {{ activeRate }}%</div>
      </div>

      <div class="stat-card">
        <div class="stat-header">
          <div
            class="stat-icon"
            style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%)"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"
              />
            </svg>
          </div>
          <div class="stat-label">余额预警</div>
        </div>
        <div class="stat-value warning">{{ warningCustomers }}</div>
        <div class="stat-extra">余额 &lt; ¥1000</div>
      </div>

      <div class="stat-card">
        <div class="stat-header">
          <div
            class="stat-icon"
            style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%)"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z" />
              <path
                d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"
              />
            </svg>
          </div>
          <div class="stat-label">流失风险</div>
        </div>
        <div class="stat-value danger">{{ churnRiskCustomers }}</div>
        <div class="stat-extra">90 天未消耗</div>
      </div>
    </div>

    <!-- 预警客户列表 -->
    <div class="table-section">
      <div class="table-header">
        <h3>余额预警客户</h3>
        <a-button type="text" size="small" @click="loadWarningList">
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
        :columns="warningColumns"
        :data="warningList"
        :loading="loading"
        row-key="customer_id"
        :pagination="warningPagination"
        @page-change="handleWarningPageChange"
      >
        <template #balance="{ record }">
          <span :class="['balance-value', record.total_amount < 500 ? 'danger' : 'warning']">
            ¥{{ record.total_amount.toFixed(2) }}
          </span>
        </template>
        <template #action="{ record }">
          <a-button type="text" size="small" @click="viewCustomer(record.customer_id)"
            >查看</a-button
          >
        </template>
      </a-table>
    </div>

    <!-- 长期未消耗客户列表 -->
    <div class="table-section">
      <div class="table-header">
        <h3>长期未消耗客户</h3>
        <a-space>
          <a-select
            v-model="inactiveDays"
            style="width: 120px"
            size="small"
            @change="loadInactiveList"
          >
            <a-option :value="30">30 天</a-option>
            <a-option :value="60">60 天</a-option>
            <a-option :value="90">90 天</a-option>
            <a-option :value="180">180 天</a-option>
          </a-select>
          <a-button type="text" size="small" @click="loadInactiveList">
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
        </a-space>
      </div>
      <a-table
        :columns="inactiveColumns"
        :data="inactiveList"
        :loading="loading"
        row-key="customer_id"
        :pagination="inactivePagination"
        @page-change="handleInactivePageChange"
      >
        <template #lastConsumption="{ record }">
          <span class="inactive-days">{{ record.days_inactive }} 天</span>
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
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import {
  getHealthStats,
  getWarningList,
  getInactiveList,
  type WarningCustomer,
  type InactiveCustomer,
} from '@/api/analytics'

const router = useRouter()

const loading = ref(false)

// 统计数据
const totalCustomers = ref(0)
const activeCustomers = ref(0)
const inactiveCustomers = ref(0)
const warningCustomers = ref(0)
const churnRiskCustomers = ref(0)
const activeRate = ref(0)

// 预警客户列表
const warningList = ref<WarningCustomer[]>([])
const warningPagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

// 未消耗客户列表
const inactiveList = ref<InactiveCustomer[]>([])
const inactiveDays = ref(90)
const inactivePagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const warningColumns = [
  { title: '公司 ID', dataIndex: 'company_id', width: 120 },
  { title: '客户名称', dataIndex: 'customer_name', width: 200 },
  {
    title: '总余额',
    slotName: 'balance',
    width: 120,
    sorter: (a: WarningCustomer, b: WarningCustomer) => a.total_amount - b.total_amount,
  },
  { title: '实充余额', dataIndex: 'real_amount', width: 100 },
  { title: '赠送余额', dataIndex: 'bonus_amount', width: 100 },
  { title: '操作', slotName: 'action', width: 80, fixed: 'right' as const },
]

const inactiveColumns = [
  { title: '公司 ID', dataIndex: 'company_id', width: 120 },
  { title: '客户名称', dataIndex: 'customer_name', width: 200 },
  { title: '运营经理', dataIndex: 'manager_name', width: 100 },
  {
    title: '未消耗天数',
    slotName: 'lastConsumption',
    width: 120,
    sorter: (a: InactiveCustomer, b: InactiveCustomer) =>
      (a.days_inactive || 0) - (b.days_inactive || 0),
  },
  { title: '操作', slotName: 'action', width: 80, fixed: 'right' as const },
]

// 加载健康度统计
const loadHealthStats = async () => {
  loading.value = true
  try {
    const res = await getHealthStats()
    const data = res.data || {}
    totalCustomers.value = data.total_customers || 0
    activeCustomers.value = data.active_customers || 0
    inactiveCustomers.value = data.inactive_customers || 0
    warningCustomers.value = data.warning_customers || 0
    churnRiskCustomers.value = data.churn_risk_customers || 0
    activeRate.value = data.active_rate || 0
  } catch (error: any) {
    Message.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 加载预警客户列表
const loadWarningList = async () => {
  loading.value = true
  try {
    const res = await getWarningList({ threshold: 1000 })
    warningList.value = res.data || []
    warningPagination.total = warningList.value.length
  } catch (error: any) {
    Message.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 加载未消耗客户列表
const loadInactiveList = async () => {
  loading.value = true
  try {
    const res = await getInactiveList({ days: inactiveDays.value })
    inactiveList.value = (res.data || []).map((item: any) => ({
      ...item,
      days_inactive: item.days || 0,
    }))
    inactivePagination.total = inactiveList.value.length
  } catch (error: any) {
    Message.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 分页变化
const handleWarningPageChange = (page: number) => {
  warningPagination.current = page
}

const handleInactivePageChange = (page: number) => {
  inactivePagination.current = page
}

// 查看客户详情
const viewCustomer = (customerId: number) => {
  router.push(`/customers/${customerId}`)
}

onMounted(() => {
  loadHealthStats()
  loadWarningList()
  loadInactiveList()
})
</script>

<style scoped>
.health-analysis-page {
  padding: 0;
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-3: #e0e2e7;
  --neutral-5: #8f959e;
  --neutral-6: #646a73;
  --neutral-7: #4c5360;
  --neutral-10: #1d2330;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.page-header {
  margin-bottom: 24px;
}

.header-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--neutral-10);
  margin-bottom: 8px;
}

.header-subtitle {
  font-size: 14px;
  color: var(--neutral-6);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  margin-bottom: 24px;
}

.stat-card {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  padding: 24px;
  transition: all 200ms ease;
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.stat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 12px;
  color: white;
}

.stat-label {
  font-size: 13px;
  color: var(--neutral-6);
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--neutral-10);
}

.stat-value.success {
  color: #22c55e;
}

.stat-value.warning {
  color: #f59e0b;
}

.stat-value.danger {
  color: #ef4444;
}

.stat-extra {
  font-size: 12px;
  color: var(--neutral-5);
  margin-top: 8px;
}

.table-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  margin-bottom: 24px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--neutral-2);
}

.table-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--neutral-10);
}

.balance-value {
  font-weight: 600;
}

.balance-value.warning {
  color: #f59e0b;
}

.balance-value.danger {
  color: #ef4444;
}

.inactive-days {
  font-weight: 600;
  color: #ef4444;
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
</style>
