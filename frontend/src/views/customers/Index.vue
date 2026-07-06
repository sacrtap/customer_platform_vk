<template>
  <div class="customer-list-page">
    <div class="page-header">
      <div class="header-title">
        <h1>客户管理</h1>
        <p class="header-subtitle">统一客户基础信息与画像数据管理</p>
      </div>
      <div class="header-actions">
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
    <div v-if="hasSelectedCustomers" class="batch-toolbar">
      <a-space>
        <a-tag color="arcoblue" size="large">
          已选择 {{ selectedCustomerIds.length }} 条
        </a-tag>
        <a-button type="primary" @click="openBatchEditDialog">批量编辑</a-button>
        <a-button @click="clearBatchSelection">取消选择</a-button>
      </a-space>
    </div>

    <!-- 表格 -->
    <CustomerTable
      :customers="customers"
      :loading="loading"
      :pagination="pagination"
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
import { useCustomerList } from '@/composables/useCustomerList'

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
</script>

<style scoped>
.customer-list-page {
  padding: 24px;
  background: var(--color-bg-1);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
}

.header-title h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.header-subtitle {
  margin: 4px 0 0 0;
  font-size: 13px;
  color: var(--color-text-3);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.batch-toolbar {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--color-fill-1);
  border-radius: 4px;
  border: 1px solid var(--color-border);
}
</style>
