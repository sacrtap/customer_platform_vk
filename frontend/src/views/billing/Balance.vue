<template>
  <div class="balance-page">
    <div class="page-header">
      <div class="header-title">
        <h1>余额管理</h1>
        <p class="header-subtitle">客户余额查询、充值与导入</p>
      </div>
      <div class="header-actions">
        <a-button v-if="can('balance:recharge')" type="primary" @click="openRechargeModal()">
          <template #icon><icon-plus /></template>充值
        </a-button>
        <a-button v-if="can('balance:import')" @click="importModalVisible = true">
          <template #icon><icon-upload /></template>导入
        </a-button>
      </div>
    </div>

    <BalanceFilters
      v-model:filters="filters"
      v-model:advanced-filters="advancedFilters"
      :industry-types="industryTypes"
      :tag-options="tagOptions"
      :managers="managers"
      @search="handleSearch"
      @reset="handleReset"
    />

    <div class="table-section">
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
          {{ record.last_recharge_at ? formatDate(record.last_recharge_at) : '-' }}
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button v-if="can('billing:recharge')" type="primary" size="small" @click="openRechargeModal(record)">充值</a-button>
            <a-button type="text" size="small" @click="viewRechargeRecords(record)">记录</a-button>
          </a-space>
        </template>
        <template #empty>
          <EmptyState title="暂无余额数据" description="点击「充值」为客户充值">
            <template #action><a-button v-if="can('balance:recharge')" type="primary" @click="openRechargeModal()">前往充值</a-button></template>
          </EmptyState>
        </template>
      </a-table>
    </div>

    <RechargeModal v-model:visible="rechargeModalVisible" @success="loadBalances" />
    <RechargeRecordModal v-model:visible="recordModalVisible" :customer-id="currentRecordCustomerId" />
    <ImportBalanceModal v-model:visible="importModalVisible" @success="loadBalances" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { useBalance } from '@/composables/useBalance'
import { IconPlus, IconUpload } from '@arco-design/web-vue/es/icon'
import BalanceFilters from './components/BalanceFilters.vue'
import RechargeModal from './components/RechargeModal.vue'
import RechargeRecordModal from './components/RechargeRecordModal.vue'
import ImportBalanceModal from './components/ImportBalanceModal.vue'
import EmptyState from '@/components/EmptyState.vue'
import { formatCurrency, formatDate } from '@/utils/formatters'
import type { Balance } from '@/api/billing'

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
  { title: '最新充值时间', dataIndex: 'last_recharge_at', slotName: 'last_recharge_at', width: 180, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '操作', slotName: 'action', width: 200, fixed: 'right' as const },
]

const openRechargeModal = (record?: Balance) => { currentCustomerId.value = record?.customer_id; rechargeModalVisible.value = true }
const viewRechargeRecords = (record: Balance) => { currentRecordCustomerId.value = record.customer_id; recordModalVisible.value = true }

onMounted(() => {
  loadBalances()
  loadIndustries()
  loadTags()
  loadManagers()
})
</script>

<style scoped>
.balance-page { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.header-title h1 { font-size: 24px; font-weight: 700; color: #2f3645; margin-bottom: 8px; }
.header-subtitle { font-size: 14px; color: #8f959e; margin-top: 4px; }
.header-actions { display: flex; gap: 12px; }
.table-section { background: #fff; border-radius: 12px; padding: 20px 24px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.balance-info .balance-detail { font-size: 12px; color: #8f959e; margin-top: 2px; display: flex; gap: 12px; }
.balance-info .real { color: #0369a1; }
.balance-info .bonus { color: #22c55e; }
.used-detail { font-size: 12px; color: #8f959e; margin-top: 2px; display: flex; gap: 12px; }
.used-detail .used-real { color: #ef4444; }
.used-detail .used-bonus { color: #8f959e; }
</style>
