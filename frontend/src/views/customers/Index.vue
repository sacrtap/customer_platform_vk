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
        :erp-systems="erpSystems"
        :cooperation-statuses="cooperationStatuses"
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
      :cooperation-statuses="cooperationStatuses"
      :erp-systems="erpSystems"
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
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCustomerList } from '@/composables/useCustomerList'
import type { Customer, Tag } from '@/types'
import { batchAddCustomerTags } from '@/api/tags'
import { batchUpdateCustomers, getKpiStats } from '@/api/customers'
import { Message } from '@arco-design/web-vue'
import { handleError } from '@/utils/errorHandler'

// 默认行业筛选（空 = 全部行业，用户可自行筛选）
const DEFAULT_INDUSTRY = ''

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
  erpSystems,
  cooperationStatuses,
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
// KPI 联动写入标志：applyKpiFilter 内部先清后设 is_key_customer，避免 watch 误判为用户手动修改
let applyingKpi = false
const kpiData = reactive({
  total: '—',
  newThisMonth: 0,
  keyCustomers: 0,
  keyContribution: 0,
  incompleteProfile: 0,
  myCustomers: 0,
})

// 动态加载 KPI 统计数据（单次聚合请求）
const loadKpiData = async () => {
  try {
    const params: {
      account_type: string
      industry?: string
      mine: string
      force_refresh: boolean
    } = {
      account_type: '正式账号',
      mine: 'true',
      force_refresh: true,
    }
    if (DEFAULT_INDUSTRY) params.industry = DEFAULT_INDUSTRY
    const res = await getKpiStats(params)
    const data = res.data?.data || res.data || {}
    kpiData.total = (data.total ?? 0).toLocaleString()
    kpiData.newThisMonth = data.new_this_month ?? 0
    kpiData.keyCustomers = data.key_customers ?? 0
    kpiData.incompleteProfile = data.incomplete_profile ?? 0
    kpiData.myCustomers = data.my_customers ?? 0
  } catch (error) {
    console.error('[loadKpiData] KPI 统计请求失败:', error)
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
  // 标记 KPI 联动写入中，避免 watch(filters.is_key_customer) 误清除刚激活的徽标
  applyingKpi = true
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
  applyingKpi = false
  handleSearch()
}

const clearKpiFilter = () => {
  activeKpi.value = 'all'
  filters.is_key_customer = null
  filters.incomplete_profile = false
  filters.mine = false
  handleSearch()
}

// 用户通过「是否重点客户」下拉手动改筛选时，若与 KPI「重点客户」徽标联动冲突，清除徽标状态
// （保留用户手动选择的值，避免双向控制互相覆盖造成脏状态）
watch(
  () => filters.is_key_customer,
  (val) => {
    // KPI 联动自身写入时跳过，仅响应用户在「是否重点客户」下拉的手动修改
    if (applyingKpi) return
    if (activeKpi.value === 'key' && val !== true) {
      activeKpi.value = 'all'
    }
  }
)

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

const handleBatchLevelConfirm = async (data: { scale_level: string; consume_level: string }) => {
  batchLoading.value = true
  try {
    const fields: Record<string, unknown> = {}
    if (data.scale_level) fields.scale_level = data.scale_level
    if (data.consume_level) fields.consume_level = data.consume_level
    if (Object.keys(fields).length === 0) {
      Message.warning('请至少选择一个等级字段')
      return
    }
    const result = await batchUpdateCustomers(selectedCustomerIds.value, fields)
    const res = result.data
    if (res.failed_count === 0) {
      Message.success(`批量设置等级成功，共修改 ${res.success_count} 个客户`)
    } else if (res.success_count > 0) {
      Message.warning(`批量设置完成：成功 ${res.success_count} 个，失败 ${res.failed_count} 个`)
    } else {
      Message.error(`批量设置失败，全部 ${res.failed_count} 个客户修改失败`)
    }
    batchLevelVisible.value = false
    handleSearch()
    loadKpiData()
  } catch (error: unknown) {
    handleError(error, '批量设置等级失败')
  } finally {
    batchLoading.value = false
  }
}

const handleSendEmailConfirm = async (data: { subject: string; content: string }) => {
  batchLoading.value = true
  try {
    // TODO: 后端暂未提供批量邮件发送 API，使用提示告知用户
    Message.info(
      `邮件发送功能开发中，已选择 ${selectedCustomerIds.value.length} 个客户，主题：${data.subject}`
    )
    sendEmailVisible.value = false
  } catch (error: unknown) {
    handleError(error, '发送邮件失败')
  } finally {
    batchLoading.value = false
  }
}

const handleAssignManagerConfirm = async (managerId: number) => {
  batchLoading.value = true
  try {
    if (!managerId) {
      Message.warning('请选择运营经理')
      return
    }
    const result = await batchUpdateCustomers(selectedCustomerIds.value, { manager_id: managerId })
    const res = result.data
    if (res.failed_count === 0) {
      Message.success(`分配负责人成功，共修改 ${res.success_count} 个客户`)
    } else if (res.success_count > 0) {
      Message.warning(`分配完成：成功 ${res.success_count} 个，失败 ${res.failed_count} 个`)
    } else {
      Message.error(`分配失败，全部 ${res.failed_count} 个客户修改失败`)
    }
    assignManagerVisible.value = false
    handleSearch()
    loadKpiData()
  } catch (error: unknown) {
    handleError(error, '分配负责人失败')
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
