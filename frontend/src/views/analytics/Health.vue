<template>
  <div class="health-analysis-page">
    <AppPageHeader
      title="健康度分析"
      description="客户活跃度监控与风险预警"
      eyebrow="ANALYTICS"
    />

    <MetricGrid>
      <MetricCard label="总客户数" :value="totalCustomers" />
      <MetricCard label="活跃客户" :value="activeCustomers" :trend="'活跃率 ' + activeRate + '%'" trend-type="up" />
      <MetricCard label="余额预警" :value="warningCustomers" trend="余额 &lt; ¥1000" trend-type="warn" />
      <MetricCard label="流失风险" :value="churnRiskCustomers" trend-type="down" />
    </MetricGrid>

    <DataSection title="余额预警客户" :count="warningPagination.total">
      <CompactTableShell>
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
            <a-button type="text" size="small" @click="viewCustomer(record.customer_id)">查看</a-button>
          </template>
        </a-table>
      </CompactTableShell>
    </DataSection>

    <DataSection title="长期未消耗客户" :count="inactivePagination.total" style="margin-top: 16px">
      <CompactTableShell>
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
            <a-button type="text" size="small" @click="viewCustomer(record.customer_id)">查看</a-button>
          </template>
        </a-table>
      </CompactTableShell>
    </DataSection>
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
import { AppPageHeader, MetricGrid, MetricCard, DataSection, CompactTableShell } from '@/components/dashboard'

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
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载失败')
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
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 加载未消耗客户列表
const loadInactiveList = async () => {
  loading.value = true
  try {
    const res = await getInactiveList({ days: inactiveDays.value })
    inactiveList.value = (res.data || []).map((item: InactiveCustomer) => ({
      ...item,
      days_inactive: item.days || 0,
    }))
    inactivePagination.total = inactiveList.value.length
  } catch (error: unknown) {
    Message.error((error as Error).message || '加载失败')
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
  display: flex;
  justify-content: space-between;
  align-items: center;
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
