<template>
  <div class="balance-page">
    <!-- PageHeader -->
    <PageHeader
      eyebrow="Billing"
      title="余额管理"
      subtitle="预付费与后付费余额总览、充值操作与充值记录追溯，低余额与即将耗尽预警。"
    >
      <template #actions>
        <button class="btn" :disabled="loading" @click="handleDataRefresh">
          <span v-if="loading" class="refresh-spin">⟳</span>
          <span v-else>⟳</span>
          数据刷新
        </button>
        <button v-if="can('billing:balance_import')" class="btn" @click="importModalVisible = true">
          导入
        </button>
        <button
          v-if="can('billing:balance_export')"
          class="btn"
          :disabled="exporting"
          @click="handleExport"
        >
          {{ exporting ? '导出中...' : '导出' }}
        </button>
        <button v-if="can('billing:recharge')" class="btn primary" @click="openRechargeModal()">
          充值
        </button>
      </template>
    </PageHeader>

    <!-- KPI 卡片 -->
    <div class="grid-5">
      <KpiCard
        label="总余额（预付费）"
        :value="formatMoney(stats.total_balance_prepaid)"
        :hint="`预付费客户（含未设置结算类型）余额合计：${formatExactMoney(stats.total_balance_prepaid)}`"
        :trend="`${stats.prepaid_customers} 个预付费客户`"
        trend-type="neutral"
        :active="activeKpi === 'prepaid'"
        @click="applyKpiFilter('prepaid')"
      />
      <KpiCard
        label="总余额（后付费）"
        :value="formatMoney(stats.postpaid_receivable)"
        :hint="`应收款（净）= 后付费客户欠款合计：${formatExactMoney(stats.postpaid_receivable)}；后付费余额合计 ${formatExactMoney(stats.total_balance_postpaid)}`"
        :trend="`应收款 · ${stats.postpaid_customers} 个后付费客户`"
        trend-type="neutral"
        :active="activeKpi === 'postpaid'"
        @click="applyKpiFilter('postpaid')"
      />
      <KpiCard
        label="本月充值"
        :value="formatMoney(stats.this_month_amount)"
        :hint="`本月充值合计：${formatExactMoney(stats.this_month_amount)}（实充 ${formatExactMoney(stats.this_month_real_amount)} + 赠送 ${formatExactMoney(stats.this_month_bonus_amount)}）`"
        :trend="`${stats.this_month_count} 笔（实 ${formatMoney(stats.this_month_real_amount)} + 赠 ${formatMoney(stats.this_month_bonus_amount)}）`"
        trend-type="neutral"
        :active="activeKpi === 'thisMonth'"
        @click="applyKpiFilter('thisMonth')"
      />
      <KpiCard
        label="即将耗尽"
        :value="stats.burning_soon_count"
        :hint="'按近 30 天日均消耗预计 7 天内耗尽的预付费客户数'"
        :trend="burningTrend.text"
        :trend-type="burningTrend.type"
        :active="activeKpi === 'burning'"
        @click="applyKpiFilter('burning')"
      />
      <KpiCard
        label="余额不足"
        :value="stats.low_balance_count"
        :hint="'余额低于 ¥10,000 的预付费客户数（含欠费）'"
        :trend="lowBalanceTrend.text"
        :trend-type="lowBalanceTrend.type"
        :active="activeKpi === 'low'"
        @click="applyKpiFilter('low')"
      />
    </div>

    <!-- 筛选 + 批量操作 + 表格 在同一卡片内 -->
    <div class="card pad main-card">
      <!-- 筛选器 -->
      <BalanceFilters
        v-model:filters="filters"
        v-model:advanced-filters="advancedFilters"
        :industry-types="industryTypes"
        :tag-options="tagOptions"
        :managers="managers"
        :active-kpi-badge="kpiBadgeText"
        :empty="balances.length === 0 && !loading"
        @search="handleFilterSearch"
        @reset="handleFilterReset"
        @clear-kpi="clearKpiFilter"
      />

      <!-- 表格 -->
      <BalanceTable
        :balances="balances"
        :loading="loading"
        :pagination="pagination"
        :can="can"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        @sort-change="handleSortChange"
        @recharge="openRechargeModal"
        @view-records="viewRechargeRecords"
        @recalculate="handleRecalculate"
      />
    </div>

    <!-- 充值弹窗 -->
    <RechargeModal
      v-model:visible="rechargeModalVisible"
      :customer-id="currentCustomerId"
      :customer-name="currentCustomerName"
      @success="handleRechargeSuccess"
    />

    <!-- 充值记录抽屉 -->
    <RechargeRecordModal
      v-model:visible="recordModalVisible"
      :customer-id="currentRecordCustomerId"
    />

    <!-- 导入弹窗 -->
    <ImportBalanceModal v-model:visible="importModalVisible" @success="loadBalances" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useUserStore } from '@/stores/user'
import { useBalance } from '@/composables/useBalance'
import { Message, Modal } from '@arco-design/web-vue'
import { exportBalances, recalculateBalance } from '@/api/billing'
import { formatCurrency } from '@/utils/formatters'
import PageHeader from '@/components/PageHeader.vue'
import KpiCard from '@/components/ui/KpiCard.vue'
import BalanceFilters from './components/BalanceFilters.vue'
import BalanceTable from './components/BalanceTable.vue'
import RechargeModal from './components/RechargeModal.vue'
import RechargeRecordModal from './components/RechargeRecordModal.vue'
import ImportBalanceModal from './components/ImportBalanceModal.vue'
import type { Balance } from '@/api/billing'

const userStore = useUserStore()
const can = (p: string) => userStore.hasPermission(p)

const {
  loading,
  balances,
  filters,
  advancedFilters,
  pagination,
  industryTypes,
  tagOptions,
  managers,
  stats,
  loadBalances,
  loadStats,
  buildExportParams,
  handleRefresh,
  handlePageChange,
  handlePageSizeChange,
  handleSortChange,
  handleSearch,
  handleReset,
  loadIndustries,
  loadTags,
  loadManagers,
} = useBalance()

const rechargeModalVisible = ref(false)
const recordModalVisible = ref(false)
const importModalVisible = ref(false)
const currentCustomerId = ref<number>()
const currentCustomerName = ref<string>()
const currentRecordCustomerId = ref<number>()

// KPI 联动筛选（'all' = 无 KPI 筛选）
type KpiKey = 'all' | 'prepaid' | 'postpaid' | 'low' | 'thisMonth' | 'burning'

const activeKpi = ref<KpiKey>('all')

const kpiBadgeText = computed(() => {
  if (activeKpi.value === 'all') return ''
  const labels: Record<string, string> = {
    prepaid: '总余额（预付费）',
    postpaid: '总余额（后付费）',
    low: '余额不足',
    thisMonth: '本月充值',
    burning: '即将耗尽',
  }
  return labels[activeKpi.value] || ''
})

const burningTrend = computed<{ text: string; type: 'warn' | 'neutral' }>(() =>
  stats.burning_soon_count > 0
    ? { text: '需立即充值', type: 'warn' }
    : { text: '暂无预警', type: 'neutral' }
)

const lowBalanceTrend = computed<{ text: string; type: 'warn' | 'neutral' }>(() =>
  stats.low_balance_count > 0 ? { text: '需跟进', type: 'warn' } : { text: '暂无', type: 'neutral' }
)

const applyKpiFilter = (kpi: KpiKey) => {
  activeKpi.value = kpi
  // 先清除所有 KPI 联动的筛选
  filters.balance_range = ''
  filters.recharge_date = []
  filters.settlement_group = ''

  if (kpi === 'prepaid' || kpi === 'postpaid') {
    // 结算类型分组口径（prepaid 含未设置结算类型的客户），与统计卡片一致
    filters.settlement_group = kpi
    filters.settlement_type = ''
  } else if (kpi === 'low') {
    // 后端「余额不足」口径仅统计预付费（后付费欠款属于应收款），
    // 列表需同步限定 settlement_group=prepaid，保证卡片数字与列表条数一致
    filters.balance_range = 'low'
    filters.settlement_group = 'prepaid'
    filters.settlement_type = ''
  } else if (kpi === 'thisMonth') {
    // 设置充值日期为本月
    const now = new Date()
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1)
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0)
    filters.recharge_date = [
      firstDay.toISOString().split('T')[0],
      lastDay.toISOString().split('T')[0],
    ]
  } else if (kpi === 'burning') {
    // 即将耗尽：按 days_remaining 升序排列，最紧急的排最前
    handleSortChange('days_remaining', 'asc')
    return
  }
  // handleSearch 内部已调用 loadStats()，无需重复调用
  handleSearch()
}

// 手动调整筛选条件后清除 KPI 徽章，避免徽章与列表口径不一致
const handleFilterSearch = () => {
  activeKpi.value = 'all'
  filters.settlement_group = ''
  handleSearch()
}

const handleFilterReset = () => {
  activeKpi.value = 'all'
  handleReset()
}

const clearKpiFilter = () => {
  activeKpi.value = 'all'
  filters.balance_range = ''
  filters.recharge_date = []
  filters.settlement_group = ''
  // handleSearch 内部已调用 loadStats()，无需重复调用
  handleSearch()
}

// KPI 卡片金额格式化：≥1 万用「万/亿」缩写，精确金额见卡片 tooltip
const formatMoney = (amount: number): string => {
  const sign = amount < 0 ? '-' : ''
  const abs = Math.abs(amount)
  if (abs >= 100000000) return `${sign}¥${(abs / 100000000).toFixed(1)}亿`
  if (abs >= 10000) return `${sign}¥${(abs / 10000).toFixed(1)}万`
  return `${sign}¥${abs.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`
}

const formatExactMoney = (amount: number): string => {
  return `¥${amount.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

const openRechargeModal = (record?: Balance) => {
  currentCustomerId.value = record?.customer_id
  currentCustomerName.value = record?.customer_name
  rechargeModalVisible.value = true
}

const viewRechargeRecords = (record: Balance) => {
  currentRecordCustomerId.value = record.customer_id
  recordModalVisible.value = true
}

const handleRechargeSuccess = () => {
  loadBalances()
  loadStats()
}

const handleRecalculate = async (record: Balance) => {
  const confirmed = await new Promise<boolean>((resolve) => {
    Modal.confirm({
      title: '确认重算余额',
      content: `将重算客户「${record.customer_name}」的余额 total_amount = real_amount + bonus_amount，是否确认？`,
      okText: '确认重算',
      cancelText: '取消',
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    })
  })
  if (!confirmed) return

  try {
    const res = await recalculateBalance(record.customer_id)
    const data = res.data
    if (data.changed) {
      Message.success(
        `重算完成：total_amount 从 ${formatCurrency(data.old_total)} 修正为 ${formatCurrency(data.total_amount)}`
      )
    } else {
      Message.info('重算完成：余额数据一致，无需修正')
    }
    loadBalances()
    loadStats()
  } catch (error: unknown) {
    Message.error((error as Error).message || '重算失败')
  }
}

// 数据刷新：强制重新加载列表 + 统计
const handleDataRefresh = async () => {
  await handleRefresh()
}

// 导出余额：按当前筛选条件导出全部匹配数据
const exporting = ref(false)
const handleExport = async () => {
  exporting.value = true
  try {
    const res = await exportBalances(buildExportParams())
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `balances_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    const truncated = res.headers?.['x-truncated'] === 'true'
    if (truncated) {
      Message.warning('数据超过 5 万条，仅导出了前 5 万条，请缩小筛选范围后再导出')
    } else {
      Message.success('导出成功')
    }
  } catch (error: unknown) {
    Message.error((error as Error).message || '导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  loadBalances()
  loadStats()
  loadIndustries()
  loadTags()
  loadManagers()
})
</script>

<style scoped>
.balance-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 1440px;
  margin: 0 auto;
}

/* 覆盖 PageHeader 的 margin-bottom，使用 gap 控制间距 */
.balance-page :deep(.page-header) {
  margin-bottom: 0;
}

/* KPI 卡片网格 */
.grid-5 {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
}

@media (max-width: 1200px) {
  .grid-5 {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 700px) {
  .grid-5 {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* 主卡片 */
.main-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg, 16px);
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0, 0, 0, 0.06));
  padding: 20px 24px;
  overflow: hidden;
}

/* 按钮样式 */
.btn {
  border: 1px solid var(--line);
  background: white;
  color: var(--ink);
  border-radius: 12px;
  padding: 9px 12px;
  cursor: pointer;
  font-weight: 700;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
}
.btn:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}
.btn.primary {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}
.btn.primary:hover {
  background: #1e40af;
}

/* 数据刷新按钮 */
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.refresh-spin {
  display: inline-block;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
