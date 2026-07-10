<template>
  <div class="balance-page">
    <AppPageHeader
      title="余额管理"
      description="客户余额查询、充值与导入"
      eyebrow="BILLING"
    >
      <template #actions>
        <a-button v-if="can('balance:recharge')" type="primary" @click="openRechargeModal()">
          <template #icon><icon-plus /></template>充值
        </a-button>
        <a-button v-if="can('balance:import')" @click="importModalVisible = true">
          <template #icon><icon-upload /></template>导入
        </a-button>
      </template>
    </AppPageHeader>

    <FilterPanel>
      <BalanceFilters
        v-model:filters="filters"
        v-model:advanced-filters="advancedFilters"
        :industry-types="industryTypes"
        :tag-options="tagOptions"
        :managers="managers"
        @search="handleSearch"
        @reset="handleReset"
      />
    </FilterPanel>

    <MetricGrid>
      <MetricCard label="账户总余额" :value="formatCurrency(totalBalance)" />
      <MetricCard label="低余额客户" :value="lowBalanceCount" trend="需关注" trend-type="warn" />
      <MetricCard label="赠送余额占比" :value="bonusPercentage ? bonusPercentage.toFixed(1) + '%' : '-'" />
      <MetricCard label="充值记录数" :value="rechargeRecordCount" />
    </MetricGrid>

    <CompactTableShell>
      <a-table
        :columns="columns"
        :data="balances"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        @sorter-change="handleSortChange"
      >
        <template #balance="{ record }">
          <div class="balance-info">
            <div>总额：{{ formatCurrency(record.total_amount) }}</div>
            <div class="balance-detail">
              <span class="real">实充：{{ formatCurrency(record.real_amount) }}</span>
              <span class="bonus">赠送：{{ formatCurrency(record.bonus_amount) }}</span>
            </div>
          </div>
        </template>
        <template #used="{ record }">
          <div>
            {{ formatCurrency(record.used_total) }}
            <div class="used-detail">
              <span class="used-real">实：{{ formatCurrency(record.used_real) }}</span>
              <span class="used-bonus">赠：{{ formatCurrency(record.used_bonus) }}</span>
            </div>
          </div>
        </template>
        <template #last_recharge_at="{ record }">
          <span v-if="record.last_recharge_at" class="cell-nowrap">{{ formatDate(record.last_recharge_at) }}</span>
          <span v-else class="text-muted">-</span>
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button size="small" ghost @click="openRecordModal(record.id)">
              充值记录
            </a-button>
            <a-button v-if="can('balance:recharge')" size="small" ghost @click="openRechargeModal(record.id)">
              充值
            </a-button>
          </a-space>
        </template>
      </a-table>
    </CompactTableShell>

    <RechargeModal v-model:visible="rechargeModalVisible" @success="loadBalances" />
    <RechargeRecordModal v-model:visible="recordModalVisible" :customer-id="currentRecordCustomerId" />
    <ImportBalanceModal v-model:visible="importModalVisible" @success="loadBalances" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { useBalance } from '@/composables/useBalance'
import { IconPlus, IconUpload } from '@arco-design/web-vue/es/icon'
import BalanceFilters from './components/BalanceFilters.vue'
import RechargeModal from './components/RechargeModal.vue'
import RechargeRecordModal from './components/RechargeRecordModal.vue'
import ImportBalanceModal from './components/ImportBalanceModal.vue'
import { formatCurrency, formatDate } from '@/utils/formatters'

import {
  AppPageHeader,
  FilterPanel,
  MetricGrid,
  MetricCard,
  CompactTableShell,
} from '@/components/dashboard'

const userStore = useUserStore()
const can = (p: string) => userStore.hasPermission(p)

const {
  loading, balances, filters, advancedFilters, pagination,
  industryTypes, tagOptions, managers,
  loadBalances, handlePageChange, handlePageSizeChange, handleSortChange, handleSearch, handleReset,
  loadIndustries, loadTags, loadManagers,
} = useBalance()

const rechargeModalVisible = ref(false)
const recordModalVisible = ref(false)
const importModalVisible = ref(false)
const currentCustomerId = ref<number>()
const currentRecordCustomerId = ref<number>()

const columns = [
  { title: '客户', dataIndex: 'customer_name', width: 200, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '账号类型', dataIndex: 'account_type', width: 120 },
  { title: '行业', dataIndex: 'industry_type', width: 120 },
  { title: '余额', dataIndex: 'total_amount', slotName: 'balance', width: 200, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '已消耗', dataIndex: 'used_total', slotName: 'used', width: 200, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '最新充值时间', dataIndex: 'last_recharge_at', slotName: 'last_recharge_at', width: 160 },
  { title: '操作', slotName: 'action', width: 180, fixed: 'right' as const },
]

// Computed metrics
const totalBalance = computed(() => {
  return balances.value.reduce((sum, b) => sum + b.total_amount, 0)
})

const lowBalanceCount = computed(() => {
  return balances.value.filter(b => b.total_amount > 0 && b.total_amount < 100).length
})

const bonusPercentage = computed(() => {
  const total = balances.value.reduce((sum, b) => sum + b.total_amount, 0)
  const bonus = balances.value.reduce((sum, b) => sum + b.bonus_amount, 0)
  return total > 0 ? (bonus / total) * 100 : 0
})

const rechargeRecordCount = computed(() => {
  return balances.value.filter(b => b.last_recharge_at).length
})

const openRechargeModal = (customerId?: number) => {
  currentCustomerId.value = customerId
  rechargeModalVisible.value = true
}

const openRecordModal = (customerId: number) => {
  currentRecordCustomerId.value = customerId
  recordModalVisible.value = true
}

onMounted(() => {
  loadIndustries()
  loadTags()
  loadManagers()
  loadBalances()
})
</script>

<style scoped>
.balance-page { display: flex; flex-direction: column; gap: 16px; }
.balance-info { display: flex; flex-direction: column; gap: 4px; }
.balance-detail { display: flex; gap: 12px; font-size: 12px; color: var(--cop-muted); }
.real { color: var(--cop-success); }
.bonus { color: var(--cop-warning); }
.used-detail { display: flex; gap: 12px; font-size: 12px; color: var(--cop-muted); }
.cell-nowrap { white-space: nowrap; }
.text-muted { color: var(--cop-muted); }
</style>