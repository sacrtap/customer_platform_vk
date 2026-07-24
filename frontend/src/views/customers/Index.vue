<template>
  <div class="customer-list-page">
    <!-- PageHeader -->
    <PageHeader
      eyebrow="Customers"
      title="客户管理"
      subtitle="将客户筛选、标签、画像、余额风险与批量操作放在同一工作面，避免运营在多个页面来回跳转。"
    >
      <template #actions>
        <button class="btn" :disabled="loading" @click="handleDataRefresh">
          <span v-if="loading" class="refresh-spin">⟳</span>
          <span v-else>⟳</span>
          数据刷新
        </button>
        <button v-if="can('customers:import')" class="btn" @click="openImportModal">
          导入客户
        </button>
        <button v-if="can('customers:export')" class="btn" @click="handleExport">导出</button>
        <button v-if="can('customers:create')" class="btn primary" @click="openCreateModal">
          新增客户
        </button>
      </template>
    </PageHeader>

    <!-- KPI 联动筛选 -->
    <CustomerKpi :data="kpiData" :active="activeKpi" @kpi-change="applyKpiFilter" />

    <!-- 筛选 + 批量操作 + 表格 在同一卡片内 -->
    <div class="card pad main-card">
      <!-- 筛选器 -->
      <CustomerFilters
        v-model:filters="filters"
        v-model:advanced-filters="advancedFilters"
        :industry-types="industryTypes"
        :managers="managers"
        :customer-tags="customerTags"
        :managers-loading="managersLoading"
        :tags-loading="tagsLoading"
        :active-kpi-badge="kpiBadgeText"
        @search="handleSearch"
        @reset="handleReset"
        @advanced-search="handleAdvancedSearch"
        @clear-kpi="clearKpiFilter"
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
    </div>

    <!-- 客户预览抽屉 -->
    <PreviewDrawer
      :visible="previewDrawerVisible"
      :customer="previewCustomer"
      @close="previewDrawerVisible = false"
      @view-detail="handleViewDetail"
      @edit="openEditModal"
      @add-tag="openTagModal"
    />

    <!-- 新增客户弹窗 -->
    <AddCustomerModal
      :visible="customerModalVisible"
      :industry-types="industryTypes"
      :managers="managers"
      :managers-loading="managersLoading"
      @saved="handleSearch"
      @update:visible="customerModalVisible = $event"
    />

    <!-- 编辑客户弹窗（全量字段） -->
    <EditCustomerDialog
      :visible="editDialogVisible"
      :customer-id="editingCustomerId"
      :industry-types="industryTypes"
      @saved="handleSearch"
      @update:visible="editDialogVisible = $event"
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
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCustomerList } from '@/composables/useCustomerList'
import type { Customer, Tag } from '@/types'
import { batchAddCustomerTags } from '@/api/tags'
import { getCustomers } from '@/api/customers'

// 默认行业筛选（与 useCustomerList 中的 createDefaultFilters 保持一致）
const DEFAULT_INDUSTRY = '房产经纪,房产ERP,房产平台'

import PageHeader from '@/components/PageHeader.vue'
import CustomerKpi from './components/CustomerKpi.vue'
import CustomerFilters from './components/CustomerFilters.vue'
import BatchToolbar from './components/BatchToolbar.vue'
import CustomerTable from './components/CustomerTable.vue'
import PreviewDrawer from './components/PreviewDrawer.vue'
import AddCustomerModal from './components/AddCustomerModal.vue'
import EditCustomerDialog from './detail/EditCustomerDialog.vue'
import CustomerImportModal from './components/CustomerImportModal.vue'
import CustomerBatchEditModal from './components/CustomerBatchEditModal.vue'
import BatchLevelModal from './components/BatchLevelModal.vue'
import SendEmailModal from './components/SendEmailModal.vue'
import AssignManagerModal from './components/AssignManagerModal.vue'
import TagSelectorDialog from './detail/TagSelectorDialog.vue'

// 使用 composable 管理列表页所有状态和逻辑
const {
  can,
  filters,
  advancedFilters,
  managers,
  managersLoading,
  customerTags,
  tagsLoading,
  industryTypes,
  loading,
  customers,
  pagination,
  selectedCustomerIds,
  hasSelectedCustomers,
  customerModalVisible,
  batchEditDialogVisible,
  importModalVisible,
  handleRefresh,
  handleSearch,
  handleReset,
  handleAdvancedSearch,
  handlePageChange,
  handlePageSizeChange,
  handleSort,
  handleDelete,
  handleBatchSelect,
  handleBatchSelectAll,
  openBatchEditDialog,
  handleExport,
  openCreateModal,
  openImportModal,
} = useCustomerList()

// KPI 联动筛选
const activeKpi = ref<'all' | 'key' | 'incomplete' | 'mine'>('all')
const kpiData = reactive({
  total: '—',
  newThisMonth: 0,
  keyCustomers: 0,
  keyContribution: 0,
  incompleteProfile: 0,
  myCustomers: 0,
})

// 动态加载 KPI 统计数据
// 使用 Promise.allSettled 确保单个请求失败不影响其他 KPI 计数
// 所有 KPI 计数包含与列表默认筛选一致的行业条件，确保点击卡片后列表数字与卡片一致
const loadKpiData = async () => {
  const baseParams = {
    page: 1,
    page_size: 1,
    account_type: '正式账号',
    industry: DEFAULT_INDUSTRY,
    force_refresh: true as boolean,
  }
  const results = await Promise.allSettled([
    getCustomers(baseParams),
    getCustomers({ ...baseParams, is_key_customer: 'true' }),
    getCustomers({ ...baseParams, incomplete_profile: 'true' }),
    getCustomers({ ...baseParams, mine: 'true' }),
  ])
  // 客户总数
  if (results[0].status === 'fulfilled') {
    const total = results[0].value.data?.total ?? 0
    kpiData.total = total.toLocaleString()
  }
  // 重点客户
  if (results[1].status === 'fulfilled') {
    kpiData.keyCustomers = results[1].value.data?.total ?? 0
  }
  // 待完善画像
  if (results[2].status === 'fulfilled') {
    kpiData.incompleteProfile = results[2].value.data?.total ?? 0
  }
  // 我的客户：运营经理或商务经理与当前登录用户一致的客户数量
  if (results[3].status === 'fulfilled') {
    kpiData.myCustomers = results[3].value.data?.total ?? 0
  } else {
    console.error('[loadKpiData] 我的客户计数请求失败:', results[3])
  }
}

const kpiBadgeText = computed(() => {
  if (activeKpi.value === 'all') return ''
  const labels: Record<string, string> = {
    key: '重点客户',
    incomplete: '待完善画像',
    mine: '我的客户',
  }
  return labels[activeKpi.value] || ''
})

const applyKpiFilter = (kpi: 'all' | 'key' | 'incomplete' | 'mine') => {
  activeKpi.value = kpi
  // 先清除所有 KPI 联动的筛选
  filters.is_key_customer = null
  filters.incomplete_profile = false
  filters.mine = false

  if (kpi === 'key') {
    filters.is_key_customer = true
  } else if (kpi === 'incomplete') {
    filters.incomplete_profile = true
  } else if (kpi === 'mine') {
    filters.mine = true
  }
  handleSearch()
}

const clearKpiFilter = () => {
  activeKpi.value = 'all'
  filters.is_key_customer = null
  filters.incomplete_profile = false
  filters.mine = false
  handleSearch()
}

// 预览抽屉
const previewDrawerVisible = ref(false)
const previewCustomer = ref<Customer | null>(null)
const openPreview = (id: number) => {
  previewCustomer.value = customers.value.find((c) => c.id === id) || null
  previewDrawerVisible.value = true
}

// 从 360 预览抽屉点击「查看详情」时，在新标签页打开客户详情页
const router = useRouter()
const handleViewDetail = (id: number) => {
  previewDrawerVisible.value = false
  const resolved = router.resolve(`/customers/${id}`)
  window.open(resolved.href, '_blank')
}

// 编辑弹窗
const editDialogVisible = ref(false)
const editingCustomerId = ref<number | null>(null)
const openEditModal = (record: Customer) => {
  editingCustomerId.value = record.id
  editDialogVisible.value = true
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
  else if (action === 'edit') openBatchEditDialog()
}

const handleBatchLevelConfirm = async (_data: { scale_level: string; consume_level: string }) => {
  batchLoading.value = true
  try {
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
    loadKpiData()
  } finally {
    batchLoading.value = false
  }
}

// 数据刷新：强制跳过缓存重新加载列表 + KPI
const handleDataRefresh = async () => {
  await handleRefresh()
  loadKpiData()
}

// 页面挂载时加载 KPI 数据
onMounted(() => {
  loadKpiData()
})
</script>

<style scoped>
.customer-list-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px 24px 44px;
  max-width: 1440px;
  margin: 0 auto;
}

/* 覆盖 PageHeader 的 margin-bottom，使用 gap 控制间距 */
.customer-list-page :deep(.page-header) {
  margin-bottom: 0;
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
