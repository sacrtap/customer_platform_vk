<template>
  <div class="customer-list-page">
    <AppPageHeader
      eyebrow="Customers"
      title="客户管理"
      description="统一客户基础信息与画像数据管理"
    >
      <template #actions>
        <a-button v-if="can('customers:create')" type="primary" @click="openCreateModal">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z" />
            </svg>
          </template>
          新建客户
        </a-button>
        <a-button v-if="can('customers:import')" @click="openImportModal">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z" />
              <path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z" />
            </svg>
          </template>
          导入
        </a-button>
        <a-button v-if="can('customers:export')" @click="handleExport">
          <template #icon>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z" />
              <path d="M7.646 1.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1-.708.708L8.5 2.707V11.5a.5.5 0 0 1-1 0V2.707L5.354 4.854a.5.5 0 1 1-.708-.708l3-3z" />
            </svg>
          </template>
          导出
        </a-button>
        <a-button v-if="can('customers:batch-edit')" :disabled="!hasSelectedCustomers" @click="openBatchEditDialog">
          批量编辑
        </a-button>
      </template>
    </AppPageHeader>

    <MetricGrid>
      <MetricCard label="客户总数" :value="pagination.total" trend="总计" trend-type="neutral" />
      <MetricCard label="重点客户" :value="customers.filter(c => c.is_key_customer).length" trend="高价值" trend-type="up" />
      <MetricCard label="待完善画像" :value="customers.filter(c => !c.profile_completed).length" trend="需跟进" trend-type="warn" />
      <MetricCard label="高风险客户" :value="customers.filter(c => c.risk_level === 'high').length" trend="预警中" trend-type="down" />
    </MetricGrid>

    <FilterPanel>
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
    </FilterPanel>

    <CompactTableShell>
      <CustomerTable
        :customers="customers"
        :loading="loading"
        :pagination="pagination"
        :managers="managers"
        :managers-loading="managersLoading"
        :selected-customer-ids="selectedCustomerIds"
        :can="can"
        @select="handleBatchSelect"
        @select-all="handleBatchSelectAll"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        @sort="handleSort"
        @view="viewCustomer"
        @edit="openEditModal"
        @delete="handleDelete"
      />
    </CompactTableShell>

    <CustomerFormModal
      v-model:visible="customerModalVisible"
      :is-edit-mode="isEditMode"
      :editing-customer="editingCustomerData"
      :managers="managers"
      :managers-loading="managersLoading"
      :customer-tags="customerTags"
      :tags-loading="tagsLoading"
      :industry-types="industryTypes"
      @submit="submitEdit"
    />

    <CustomerImportModal
      v-model:visible="importModalVisible"
      @imported="handleSearch"
    />

    <CustomerBatchEditModal
      v-model:visible="batchEditDialogVisible"
      :selected-customer-ids="selectedCustomerIds"
      :managers="managers"
      :customer-tags="customerTags"
      :industry-types="industryTypes"
      @updated="handleSearch"
    />
  </div>
</template>

<script setup lang="ts">
import { useCustomerList } from '@/composables/useCustomerList'

import CustomerFilters from './components/CustomerFilters.vue'
import CustomerTable from './components/CustomerTable.vue'
import CustomerFormModal from './components/CustomerFormModal.vue'
import CustomerImportModal from './components/CustomerImportModal.vue'
import CustomerBatchEditModal from './components/CustomerBatchEditModal.vue'

// 新组件导入
import AppPageHeader from '@/components/dashboard/AppPageHeader.vue'
import MetricGrid from '@/components/dashboard/MetricGrid.vue'
import MetricCard from '@/components/dashboard/MetricCard.vue'
import FilterPanel from '@/components/dashboard/FilterPanel.vue'
import CompactTableShell from '@/components/dashboard/CompactTableShell.vue'

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
  handleBatchSelect, handleBatchSelectAll, openBatchEditDialog,
  handleExport,
  openCreateModal, openEditModal, viewCustomer, openImportModal,
} = useCustomerList()
</script>

<style scoped>
.customer-list-page {
  padding: 24px;
  background: var(--cop-bg);
  min-height: 100vh;
}
</style>
