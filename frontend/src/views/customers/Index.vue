<template>
  <div class="customer-list-page">
    <!-- PageHeader -->
    <PageHeader
      eyebrow="Customers"
      title="客户列表"
      subtitle="将客户筛选、标签、画像、余额风险与批量操作放在同一工作面，避免运营在多个页面来回跳转。"
    >
      <template #actions>
        <a-button v-if="can('customers:export')" @click="handleExport">导出</a-button>
        <a-button v-if="can('customers:import')" @click="openImportModal">导入</a-button>
        <a-button v-if="can('customers:create')" type="primary" @click="openCreateModal">
          新增客户
        </a-button>
      </template>
    </PageHeader>

    <!-- KPI 联动筛选 -->
    <CustomerKpi :data="kpiData" :active="activeKpi" @kpi-change="applyKpiFilter" />

    <!-- 筛选器 -->
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
    <transition name="slide-down">
      <BatchToolbar
        v-if="hasSelectedCustomers"
        :selected-count="selectedCustomerIds.length"
        @batch-action="handleBatchAction"
        @add-tag="openTagModal"
      />
    </transition>

    <!-- 表格 -->
    <CustomerTable
      :customers="customers"
      :loading="loading"
      :pagination="pagination"
      :managers="managers as Array<{ id: number; real_name: string | null }>"
      :managers-loading="managersLoading"
      :selected-customer-ids="selectedCustomerIds"
      :can="can"
      @select="handleBatchSelect"
      @select-all="handleBatchSelectAll"
      @page-change="handlePageChange"
      @page-size-change="handlePageSizeChange"
      @sort-change="handleSort"
      @view="openPreview"
      @edit="openEditModal"
      @delete="handleDelete"
    />

    <!-- 客户预览抽屉 -->
    <PreviewDrawer
      :visible="previewDrawerVisible"
      :customer="previewCustomer"
      @close="previewDrawerVisible = false"
      @view-detail="viewCustomer"
      @edit="openEditModal"
      @add-tag="openTagModal"
    />

    <!-- 新增客户弹窗 -->
    <AddCustomerModal
      :visible="customerModalVisible"
      :industry-types="industryTypes"
      :managers="managers"
      @submit="handleSearch"
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

    <!-- 批量操作弹窗 -->
    <BatchLevelModal
      :visible="batchLevelVisible"
      :loading="batchLoading"
      :selected-count="selectedCustomerIds.length"
      @confirm="handleBatchLevelConfirm"
      @update:visible="batchLevelVisible = $event"
    />
    <SendEmailModal
      :visible="sendEmailVisible"
      :loading="batchLoading"
      :selected-count="selectedCustomerIds.length"
      @confirm="handleSendEmailConfirm"
      @update:visible="sendEmailVisible = $event"
    />
    <AssignManagerModal
      :visible="assignManagerVisible"
      :loading="batchLoading"
      :selected-count="selectedCustomerIds.length"
      :managers="managers"
      @confirm="handleAssignManagerConfirm"
      @update:visible="assignManagerVisible = $event"
    />

    <!-- 打标签弹窗（批量操作） -->
    <TagSelectorDialog
      :visible="tagModalVisible"
      :loading="batchLoading"
      :all-tags="customerTags as unknown as Tag[]"
      :all-tags-loading="tagsLoading"
      :customer-tags="[]"
      @add="handleBatchAddTags"
      @close="tagModalVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useCustomerList } from '@/composables/useCustomerList'
import type { Customer, Tag } from '@/types'
import { batchAddCustomerTags } from '@/api/tags'

import PageHeader from '@/components/PageHeader.vue'
import CustomerKpi from './components/CustomerKpi.vue'
import CustomerFilters from './components/CustomerFilters.vue'
import BatchToolbar from './components/BatchToolbar.vue'
import CustomerTable from './components/CustomerTable.vue'
import PreviewDrawer from './components/PreviewDrawer.vue'
import AddCustomerModal from './components/AddCustomerModal.vue'
import CustomerImportModal from './components/CustomerImportModal.vue'
import CustomerBatchEditModal from './components/CustomerBatchEditModal.vue'
import BatchLevelModal from './components/BatchLevelModal.vue'
import SendEmailModal from './components/SendEmailModal.vue'
import AssignManagerModal from './components/AssignManagerModal.vue'
import TagSelectorDialog from './detail/TagSelectorDialog.vue'

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
const activeKpi = ref<'all' | 'key' | 'incomplete' | 'mine'>('all')
const kpiData = reactive({
  total: '3,286',
  newThisMonth: 126,
  keyCustomers: 348,
  keyContribution: 72,
  incompleteProfile: 214,
  myCustomers: 58,
})

const applyKpiFilter = (kpi: 'all' | 'key' | 'incomplete' | 'mine') => {
  activeKpi.value = kpi
  if (kpi === 'key') {
    filters.is_key_customer = true
  } else {
    filters.is_key_customer = null
  }
  handleSearch()
}

// 预览抽屉
const previewDrawerVisible = ref(false)
const previewCustomer = ref<Customer | null>(null)
const openPreview = (id: number) => {
  previewCustomer.value = customers.value.find((c) => c.id === id) || null
  previewDrawerVisible.value = true
}

// 批量操作弹窗状态
const batchLoading = ref(false)
const batchLevelVisible = ref(false)
const sendEmailVisible = ref(false)
const assignManagerVisible = ref(false)
const tagModalVisible = ref(false)

const openTagModal = () => {
  tagModalVisible.value = true
}

const handleBatchAction = (action: string) => {
  if (action === 'assign') assignManagerVisible.value = true
  else if (action === 'setLevel') batchLevelVisible.value = true
  else if (action === 'email') sendEmailVisible.value = true
  else if (action === 'export') handleExport()
  else if (action === 'delete') openBatchEditDialog()
}

const handleBatchLevelConfirm = async (_data: { scale_level: string; consume_level: string }) => {
  batchLoading.value = true
  try {
    // API call for batch update
    batchLevelVisible.value = false
    handleSearch()
  } finally {
    batchLoading.value = false
  }
}

const handleSendEmailConfirm = async (_data: { subject: string; content: string }) => {
  batchLoading.value = true
  try {
    sendEmailVisible.value = false
    handleSearch()
  } finally {
    batchLoading.value = false
  }
}

const handleAssignManagerConfirm = async (_managerId: number) => {
  batchLoading.value = true
  try {
    assignManagerVisible.value = false
    handleSearch()
  } finally {
    batchLoading.value = false
  }
}

const handleBatchAddTags = async (tagIds: number[]) => {
  batchLoading.value = true
  try {
    await batchAddCustomerTags({
      customer_ids: selectedCustomerIds.value,
      tag_ids: tagIds,
    })
    tagModalVisible.value = false
    handleSearch()
  } finally {
    batchLoading.value = false
  }
}
</script>

<style scoped>
.customer-list-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 0 0 32px 0;
}

.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.25s ease-out;
}
.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
