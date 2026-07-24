<template>
  <div class="balance-page">
    <!-- PageHeader -->
    <PageHeader
      eyebrow="Billing"
      title="余额管理"
      subtitle="客户余额总览、充值操作与充值记录追溯，低余额预警与批量充值支持。"
    >
      <template #actions>
        <button class="btn" :disabled="loading" @click="handleDataRefresh">
          <span v-if="loading" class="refresh-spin">⟳</span>
          <span v-else>⟳</span>
          数据刷新
        </button>
        <button v-if="can('balance:import')" class="btn" @click="importModalVisible = true">
          导入
        </button>
        <button v-if="can('billing:recharge')" class="btn primary" @click="openRechargeModal()">
          充值
        </button>
      </template>
    </PageHeader>

    <!-- KPI 卡片 -->
    <div class="grid-4">
      <KpiCard
        label="总余额"
        :value="formatBalanceAmount(stats.total_balance)"
        :trend="`共 ${stats.total_customers} 个客户`"
        trend-type="up"
        :active="activeKpi === 'all'"
        @click="applyKpiFilter('all')"
      />
      <KpiCard
        label="本月充值"
        :value="`¥${formatNumber(stats.this_month_amount)}`"
        :trend="`${stats.this_month_count} 笔（实：¥${formatNumber(stats.this_month_real_amount)}，赠：¥${formatNumber(stats.this_month_bonus_amount)}）`"
        trend-type="neutral"
        :active="activeKpi === 'thisMonth'"
        @click="applyKpiFilter('thisMonth')"
      />
      <KpiCard
        label="余额不足"
        :value="stats.low_balance_count"
        trend="需跟进"
        trend-type="warn"
        :active="activeKpi === 'low'"
        @click="applyKpiFilter('low')"
      />
      <KpiCard
        label="零余额客户"
        :value="stats.zero_balance_count"
        trend="已耗尽"
        trend-type="down"
        :active="activeKpi === 'zero'"
        @click="applyKpiFilter('zero')"
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
        @search="handleSearch"
        @reset="handleReset"
        @clear-kpi="clearKpiFilter"
      />

      <!-- 批量操作工具栏 -->
      <BalanceBatchToolbar
        v-if="hasSelected"
        :selected-count="selectedIds.length"
        @batch-action="handleBatchAction"
        @clear="clearSelection"
      />

      <!-- 表格 -->
      <BalanceTable
        :balances="balances"
        :loading="loading"
        :pagination="pagination"
        :selected-ids="selectedIds"
        :can="can"
        @select="handleSelect"
        @select-all="handleSelectAll"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        @sort-change="handleSortChange"
        @recharge="openRechargeModal"
        @view-records="viewRechargeRecords"
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
import { Message } from '@arco-design/web-vue'
import PageHeader from '@/components/PageHeader.vue'
import KpiCard from '@/components/ui/KpiCard.vue'
import BalanceFilters from './components/BalanceFilters.vue'
import BalanceBatchToolbar from './components/BalanceBatchToolbar.vue'
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
  selectedIds,
  hasSelected,
  loadBalances,
  loadStats,
  handleRefresh,
  handlePageChange,
  handlePageSizeChange,
  handleSortChange,
  handleSearch,
  handleReset,
  handleSelect,
  handleSelectAll,
  clearSelection,
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

// KPI 联动筛选
const activeKpi = ref<'all' | 'low' | 'zero' | 'thisMonth'>('all')

const kpiBadgeText = computed(() => {
  if (activeKpi.value === 'all') return ''
  const labels: Record<string, string> = {
    low: '余额不足',
    zero: '零余额客户',
    thisMonth: '本月充值',
  }
  return labels[activeKpi.value] || ''
})

const applyKpiFilter = (kpi: 'all' | 'low' | 'zero' | 'thisMonth') => {
  activeKpi.value = kpi
  // 先清除所有 KPI 联动的筛选
  filters.balance_range = ''
  filters.recharge_date = []

  if (kpi === 'low') {
    filters.balance_range = 'low'
  } else if (kpi === 'zero') {
    filters.balance_range = 'zero'
  } else if (kpi === 'thisMonth') {
    // 设置充值日期为本月
    const now = new Date()
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1)
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0)
    filters.recharge_date = [
      firstDay.toISOString().split('T')[0],
      lastDay.toISOString().split('T')[0],
    ]
  }
  handleSearch()
  loadStats()
}

const clearKpiFilter = () => {
  activeKpi.value = 'all'
  filters.balance_range = ''
  filters.recharge_date = []
  handleSearch()
  loadStats()
}

// KPI 卡片格式化
const formatBalanceAmount = (amount: number): string => {
  if (amount >= 100000000) return `¥${(amount / 100000000).toFixed(1)}亿`
  if (amount >= 10000) return `¥${(amount / 10000).toFixed(1)}万`
  return `¥${amount.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
}

const formatNumber = (num: number): string => {
  return num.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
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

const handleBatchAction = (action: string) => {
  if (action === 'recharge') {
    if (selectedIds.value.length === 0) {
      Message.warning('请先选择客户')
      return
    }
    Message.info(`已选择 ${selectedIds.value.length} 个客户，批量充值功能开发中`)
  } else if (action === 'export') {
    Message.info('批量导出功能开发中')
  }
}

// 数据刷新：强制重新加载列表 + 统计
const handleDataRefresh = async () => {
  await handleRefresh()
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
  padding: 22px 24px 44px;
  max-width: 1440px;
  margin: 0 auto;
}

/* 覆盖 PageHeader 的 margin-bottom，使用 gap 控制间距 */
.balance-page :deep(.page-header) {
  margin-bottom: 0;
}

/* KPI 卡片网格 */
.grid-4 {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

@media (max-width: 900px) {
  .grid-4 {
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
