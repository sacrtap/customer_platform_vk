<template>
  <div class="customer-list-page">
    <!-- PageHeader -->
    <PageHeader eyebrow="Customers" title="客户列表"
      subtitle="将客户筛选、标签、画像、余额风险与批量操作放在同一工作面，避免运营在多个页面来回跳转。">
      <template #actions>
        <a-button v-if="can('customers:export')" @click="handleExport">导出</a-button>
        <a-button v-if="can('customers:import')" @click="openImportModal">导入</a-button>
        <a-button v-if="can('customers:create')" type="primary" @click="openCreateModal">新增客户</a-button>
      </template>
    </PageHeader>

    <!-- KPI 联动筛选 -->
    <div class="grid-4">
      <div class="metric card kpi-clickable" :class="{ 'kpi-active': activeKpi === 'all' }" @click="applyKpiFilter('all')">
        <div class="label">客户总数</div>
        <div class="value">{{ kpiData.total }}</div>
        <div class="trend up">本月新增 {{ kpiData.newThisMonth }}</div>
      </div>
      <div class="metric card kpi-clickable" :class="{ 'kpi-active': activeKpi === 'key' }" @click="applyKpiFilter('key')">
        <div class="label">重点客户</div>
        <div class="value">{{ kpiData.keyCustomers }}</div>
        <div class="trend">消耗贡献 {{ kpiData.keyContribution }}%</div>
      </div>
      <div class="metric card kpi-clickable" :class="{ 'kpi-active': activeKpi === 'incomplete' }" @click="applyKpiFilter('incomplete')">
        <div class="label">待完善画像</div>
        <div class="value">{{ kpiData.incompleteProfile }}</div>
        <div class="trend warn">影响分析准确性</div>
      </div>
      <div class="metric card kpi-clickable" :class="{ 'kpi-active': activeKpi === 'mine' }" @click="applyKpiFilter('mine')">
        <div class="label">我的客户</div>
        <div class="value">{{ kpiData.myCustomers }}</div>
        <div class="trend down">需运营跟进</div>
      </div>
    </div>

    <CustomerFilters
      v-model:filters="filters"
      v-model:advanced-filters="advancedFilters"
      :industry-types="industryTypes"
      :managers="managers"
      :customer-tags="customerTags"
      :managers-loading="managersLoading"
      :tags-loading="tagsLoading"
      @search="handleSearch"
      @reset="handleReset"
      @advanced-search="handleAdvancedSearch"
    />

    <!-- 批量操作工具栏 -->
    <BatchToolbar v-if="hasSelectedCustomers" :count="selectedCustomerIds.length">
      <a-button type="primary" @click="openBatchEditDialog">批量编辑</a-button>
      <a-button @click="clearBatchSelection">取消选择</a-button>
    </BatchToolbar>

    <!-- 表格 -->
    <TableSection>
    <CustomerTable
      :customers="customers"
      :loading="loading"
      :pagination="pagination"
      :managers="managers as Array<{ id: number; real_name: string | null }>"
      :managers-loading="managersLoading as boolean"
      :selected-customer-ids="selectedCustomerIds"
      :can="can"
      @select="handleBatchSelect"
      @select-all="handleBatchSelectAll"
      @page-change="handlePageChange"
      @page-size-change="handlePageSizeChange"
      @sort-change="handleSort"
      @view="viewCustomer"
      @edit="openEditModal"
      @delete="handleDelete"
    />
    </TableSection>

    <!-- 客户预览抽屉 -->
    <CustomerPreviewDrawer
      v-model:visible="previewDrawerVisible"
      :customer-id="previewCustomerId"
    />

    <CustomerFormModal
      :visible="customerModalVisible as boolean"
      :is-edit-mode="isEditMode as boolean"
      :customer-record="editingCustomerData as any"
      :industry-types="industryTypes as any"
      :managers="managers as any"
      :managers-loading="managersLoading as boolean"
      @saved="handleSearch"
      @update:visible="customerModalVisible = $event"
    />

    <!-- 导入对话框 -->
    <CustomerImportModal
      :visible="importModalVisible"
      @saved="handleSearch"
      @update:visible="importModalVisible = $event"
    />

    <!-- 批量编辑对话框 -->
    <CustomerBatchEditModal
      :visible="batchEditDialogVisible"
      :selected-customer-ids="selectedCustomerIds"
      :managers="managers"
      @submitted="handleSearch"
      @update:visible="batchEditDialogVisible = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useCustomerList } from '@/composables/useCustomerList'

import PageHeader from '@/components/PageHeader.vue'
import BatchToolbar from '@/components/BatchToolbar.vue'
import TableSection from '@/components/TableSection.vue'
import CustomerPreviewDrawer from '@/components/CustomerPreviewDrawer.vue'
import CustomerFilters from './components/CustomerFilters.vue'
import CustomerTable from './components/CustomerTable.vue'
import CustomerFormModal from './components/CustomerFormModal.vue'
import CustomerImportModal from './components/CustomerImportModal.vue'
import CustomerBatchEditModal from './components/CustomerBatchEditModal.vue'

// 使用 composable 管理列表页所有状态和逻辑
const {
  can,
  filters, advancedFilters,
  managers, managersLoading, customerTags, tagsLoading, industryTypes,
  loading, customers, pagination,
  selectedCustomerIds, hasSelectedCustomers,
  customerModalVisible, isEditMode, editingCustomerData,
  batchEditDialogVisible, importModalVisible,
  handleSearch, handleReset, handleAdvancedSearch,
  handlePageChange, handlePageSizeChange, handleSort,
  handleDelete,
  handleBatchSelect, handleBatchSelectAll, openBatchEditDialog, clearBatchSelection,
  handleExport,
  openCreateModal, openEditModal, viewCustomer, openImportModal,
} = useCustomerList()

// KPI 联动筛选
const activeKpi = ref('all')
const kpiData = reactive({
  total: '3,286',
  newThisMonth: 126,
  keyCustomers: 348,
  keyContribution: 72,
  incompleteProfile: 214,
  myCustomers: 58,
})
const applyKpiFilter = (kpi: string) => {
  activeKpi.value = kpi
  // 根据 KPI 设置筛选条件
  if (kpi === 'key') {
    filters.is_key_customer = true
  } else if (kpi === 'mine') {
    // 设置当前用户的客户
  } else {
    ;(filters as any).is_key_customer = undefined
  }
  handleSearch()
}

// 预览抽屉
const previewDrawerVisible = ref(false)
const previewCustomerId = ref<number | null>(null)
const openPreview = (id: number) => {
  previewCustomerId.value = id
  previewDrawerVisible.value = true
}
</script>

<style scoped>
.customer-list-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* KPI 联动筛选 */
.kpi-clickable {
  cursor: pointer;
  transition: all .18s ease;
}
.kpi-clickable:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.kpi-active {
  border-color: #93C5FD;
  background: #EFF6FF;
}

.metric .label { font-size: 13px; color: var(--muted); }
.metric .value { font-size: 24px; font-weight: 850; color: var(--ink); margin: 4px 0; }
.metric .trend { font-size: 12px; }
.trend.up { color: #059669; }
.trend.warn { color: #D97706; }
.trend.down { color: #DC2626; }
</style>
