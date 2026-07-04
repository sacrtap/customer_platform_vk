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
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"
              />
            </svg>
          </template>
          新建客户
        </a-button>
        <a-button v-if="can('customers:import')" @click="openImportModal">
          <template #icon>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"
              />
              <path
                d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708l3 3z"
              />
            </svg>
          </template>
          导入
        </a-button>
        <a-button v-if="can('customers:export')" @click="handleExport">
          <template #icon>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5z"
              />
              <path
                d="M7.646 4.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1-.708.708L8.5 5.707V14.5a.5.5 0 0 1-1 0V5.707L5.354 7.854a.5.5 0 1 1-.708-.708l3-3z"
              />
            </svg>
          </template>
          导出
        </a-button>
        <a-button :loading="loading" @click="handleRefresh">
          <template #icon>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                fill-rule="evenodd"
                d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2v1z"
              />
              <path d="M8 1a.5.5 0 0 1 .5.5v4a.5.5 0 0 1-1 0v-4A.5.5 0 0 1 8 1z" />
              <path d="M8 5.5L5.5 3H10.5L8 5.5z" />
            </svg>
          </template>
          刷新
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


    <!-- 表格 -->
    <!-- 批量操作工具栏（仅选中客户时显示） -->
    <div v-if="hasSelectedCustomers" class="batch-toolbar">
      <a-space>
        <a-tag color="arcoblue" size="large">
          已选择 {{ selectedCustomerIds.length }} 条
        </a-tag>
        <a-button type="primary" @click="openBatchEditDialog">
          <template #icon>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168l10-10zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207 11.207 2.5zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293l6.5-6.5zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5v.5a.5.5 0 0 1-.5.5H4a.5.5 0 0 1-.5-.5v-.5a.5.5 0 0 1 .146-.354z"
              />
            </svg>
          </template>
          批量编辑
        </a-button>
        <a-button @click="clearBatchSelection">取消选择</a-button>
      </a-space>
    </div>

    <div class="table-section">
      <a-table
        :columns="columns"
        :data="customers"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        :scroll="{ x: 'max-content' }"
        :row-selection="{
          type: 'checkbox',
          showCheckedAll: true,
          onlyCurrent: false,
          selectedRowKeys: selectedCustomerIds,
        }"
        @select="handleBatchSelect"
        @select-all="handleBatchSelectAll"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
        @sorter-change="handleSort"
      >
        <template #name="{ record }">
          <div class="name-cell">
            <span v-if="record.is_key_customer" class="key-customer-badge" title="重点客户">★</span>
            <span class="name-text">{{ record.name }}</span>
          </div>
        </template>
        <template #createdAt="{ record }">
          {{ formatDateTime(record.created_at) }}
        </template>
        <template #settlementType="{ record }">
          {{ getSettlementTypeName(record.settlement_type) }}
        </template>
        <template #manager="{ record }">
          {{ getManagerName(record.manager_id) }}
        </template>
        <template #salesManager="{ record }">
          {{ getSalesManagerName(record.sales_manager_id) }}
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button type="primary" size="small" @click="viewCustomer(record.id)">查看</a-button>
            <a-button
              v-if="can('customers:edit')"
              type="text"
              size="small"
              @click="openEditModal(record)"
              >编辑</a-button
            >
            <a-dropdown>
              <a-button type="text" size="small">更多</a-button>
              <template #content>
                <a-doption @click="viewProfile(record.id)">画像</a-doption>
                <a-doption
                  v-if="can('customers:delete')"
                  style="color: #ff4d4f"
                  @click="() => handleDelete(record.id)"
                  >删除</a-doption
                >
              </template>
            </a-dropdown>
          </a-space>
        </template>
        <template #empty>
          <EmptyState title="暂无客户数据" description="点击「新建客户」添加第一个客户">
            <template #action>
              <a-button v-if="can('customers:create')" type="primary" @click="openCreateModal"
                >新建客户</a-button
              >
            </template>
          </EmptyState>
        </template>
      </a-table>
    </div>

    <!-- 新建/编辑客户对话框 -->
    <CustomerFormModal
      v-model:visible="customerModalVisible"
      :is-edit-mode="isEditMode"
      :customer-record="editingCustomerData"
      :industry-types="industryTypes"
      :managers="managers"
      :managers-loading="managersLoading"
      @saved="loadCustomers"
    />

    <!-- 导入对话框 -->
    <CustomerImportModal
      v-model:visible="importModalVisible"
      @imported="loadCustomers"
    />

    <!-- 批量编辑对话框 -->
    <CustomerBatchEditModal
      v-model:visible="batchEditDialogVisible"
      :selected-customer-ids="selectedCustomerIds"
      :managers="managers"
      @submitted="loadCustomers"
    />

  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import { handleError } from '@/utils/errorHandler'
import {
  getCustomers,
  deleteCustomer,
  exportCustomers,
  getIndustryTypes,
} from '@/api/customers'
import { getTags } from '@/api/tags'
import { getManagers } from '@/api/users'
import EmptyState from '@/components/EmptyState.vue'
import { formatDateTime } from '@/utils/formatters'
import type { IndustryType, Customer } from '@/types'

import CustomerFilters from '@/views/customers/components/CustomerFilters.vue'
import CustomerFormModal from '@/views/customers/components/CustomerFormModal.vue'
import CustomerImportModal from '@/views/customers/components/CustomerImportModal.vue'
import CustomerBatchEditModal from '@/views/customers/components/CustomerBatchEditModal.vue'

const router = useRouter()
const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

// 默认筛选值（工厂函数，确保每次调用返回新引用）
const createDefaultFilters = () => ({
  keyword: '',
  account_type: '正式账号',
  industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
  is_key_customer: null as boolean | null,
  is_real_estate: null as boolean | null,
  settlement_type: '',
})

const filters = reactive(createDefaultFilters())

const advancedFilters = reactive({
  manager_id: null as number | null,
  sales_manager_id: null as number | null,
  tag_ids: [] as number[],
})

const managersLoading = ref(false)
const managers = ref<Array<Record<string, unknown>>>([])
const tagsLoading = ref(false)
const customerTags = ref<Array<Record<string, unknown>>>([])
const industryTypes = ref<IndustryType[]>([])

const loading = ref(false)
const customers = ref<Customer[]>([])

// 排序状态
const sortState = reactive({
  sort_by: 'company_id',
  sort_order: 'ascend' as 'ascend' | 'descend' | '',
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

const columns = [
  {
    title: '公司 ID',
    dataIndex: 'company_id',
    width: 100,
    sortable: { sortDirections: ['ascend', 'descend'] },
    ellipsis: true,
    tooltip: true,
  },
  {
    title: '客户名称',
    dataIndex: 'name',
    slotName: 'name',
    width: 220,
    sortable: { sortDirections: ['ascend', 'descend'] },
    ellipsis: true,
    tooltip: true,
  },
  {
    title: '行业类型',
    dataIndex: 'industry',
    width: 120,
    sortable: { sortDirections: ['ascend', 'descend'] },
    ellipsis: true,
    tooltip: true,
  },
  {
    title: '结算方式',
    dataIndex: 'settlement_type',
    slotName: 'settlementType',
    width: 120,
    sortable: { sortDirections: ['ascend', 'descend'] },
    ellipsis: true,
    tooltip: true,
  },
  {
    title: '商务经理',
    dataIndex: 'sales_manager_id',
    slotName: 'salesManager',
    width: 130,
    sortable: { sortDirections: ['ascend', 'descend'] },
    ellipsis: true,
    tooltip: true,
  },
  {
    title: '运营经理',
    dataIndex: 'manager_id',
    slotName: 'manager',
    width: 130,
    sortable: { sortDirections: ['ascend', 'descend'] },
    ellipsis: true,
    tooltip: true,
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    slotName: 'createdAt',
    width: 180,
    sortable: { sortDirections: ['ascend', 'descend'] },
  },
  { title: '操作', slotName: 'action', width: 180, fixed: 'right' as const },
]

// 结算方式映射
const settlementTypeMap: Record<string, string> = {
  prepaid: '预付费',
  postpaid: '后付费',
}

// 获取结算方式显示名称
const getSettlementTypeName = (type: string | undefined): string => {
  if (!type) return '-'
  return settlementTypeMap[type] || type
}

// 获取运营经理显示名称
const getManagerName = (managerId: number | null | undefined): string => {
  if (!managerId) return '-'
  const manager = managers.value.find((m) => m.id === managerId)
  return manager ? ((manager.real_name || manager.username) as string) : '-'
}

// 获取商务经理显示名称
const getSalesManagerName = (managerId: number | null | undefined): string => {
  if (!managerId) return '-'
  const manager = managers.value.find((m) => m.id === managerId)
  return manager ? ((manager.real_name || manager.username) as string) : '-'
}

// 处理排序
const handleSort = (dataIndex: string, direction: 'ascend' | 'descend' | '') => {
  if (!direction) {
    // 取消排序时恢复默认
    sortState.sort_by = 'id'
    sortState.sort_order = 'ascend'
  } else {
    sortState.sort_by = dataIndex
    sortState.sort_order = direction
  }
  pagination.current = 1 // 重置到第一页
  loadCustomers()
}

// 加载客户列表
const loadCustomers = async () => {
  loading.value = true
  try {
    // 将前端的 ascend/descend 转换为后端期望的 asc/desc
    const backendSortOrder =
      sortState.sort_order === 'ascend'
        ? 'asc'
        : sortState.sort_order === 'descend'
          ? 'desc'
          : 'asc'

    const params: {
      page: number
      page_size: number
      keyword?: string
      account_type?: string
      industry?: string
      manager_id?: number
      sales_manager_id?: number
      is_key_customer?: boolean
      settlement_type?: string
      is_real_estate?: boolean
      sort_by: string
      sort_order: 'asc' | 'desc'
    } = {
      page: pagination.current,
      page_size: pagination.pageSize,
      sort_by: sortState.sort_by,
      sort_order: backendSortOrder,
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.account_type) params.account_type = filters.account_type
    if (filters.industry && filters.industry.length > 0)
      params.industry = filters.industry.join(',')
    if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer
    if (filters.settlement_type) params.settlement_type = filters.settlement_type
    if (filters.is_real_estate !== null) params.is_real_estate = filters.is_real_estate
    if (advancedFilters.manager_id) params.manager_id = advancedFilters.manager_id
    if (advancedFilters.sales_manager_id) params.sales_manager_id = advancedFilters.sales_manager_id

    const res = await getCustomers(params)
    customers.value = res.data.list || []
    pagination.total = res.data.total || 0
    pagination.current = res.data.page || 1
  } catch (error: unknown) {
    handleError(error, '客户列表加载失败')
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  pagination.current = 1
  loadCustomers()
}

// 重置
const handleReset = () => {
  Object.assign(filters, createDefaultFilters())
  advancedFilters.manager_id = null
  advancedFilters.sales_manager_id = null
  advancedFilters.tag_ids = []
  pagination.current = 1
  loadCustomers()
}

// 刷新（强制跳过缓存）
const handleRefresh = async () => {
  loading.value = true
  try {
    // 将前端的 ascend/descend 转换为后端期望的 asc/desc
    const backendSortOrder =
      sortState.sort_order === 'ascend'
        ? 'asc'
        : sortState.sort_order === 'descend'
          ? 'desc'
          : 'asc'

    const params: {
      page: number
      page_size: number
      keyword?: string
      account_type?: string
      industry?: string
      manager_id?: number
      sales_manager_id?: number
      is_key_customer?: boolean
      is_real_estate?: boolean
      settlement_type?: string
      sort_by: string
      sort_order: 'asc' | 'desc'
      force_refresh?: boolean
    } = {
      page: pagination.current,
      page_size: pagination.pageSize,
      sort_by: sortState.sort_by,
      sort_order: backendSortOrder,
      force_refresh: true, // 强制刷新，跳过缓存
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.account_type) params.account_type = filters.account_type
    if (filters.industry && filters.industry.length > 0)
      params.industry = filters.industry.join(',')
    if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer
    if (filters.is_real_estate !== null) params.is_real_estate = filters.is_real_estate
    if (filters.settlement_type) params.settlement_type = filters.settlement_type
    if (advancedFilters.manager_id) params.manager_id = advancedFilters.manager_id
    if (advancedFilters.sales_manager_id) params.sales_manager_id = advancedFilters.sales_manager_id

    const res = await getCustomers(params)
    customers.value = res.data.list || []
    pagination.total = res.data.total || 0
    pagination.current = res.data.page || 1
    Message.success('已刷新')
  } catch (error: unknown) {
    handleError(error, '刷新失败')
  } finally {
    loading.value = false
  }
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page
  loadCustomers()
}

// 每页条数变化
const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1 // 切换条数时回到第一页
  loadCustomers()
}

// 删除客户
const handleDelete = async (id: number) => {
  await Modal.confirm({
    title: '确认删除',
    content: '删除后无法恢复，确定要删除该客户吗？',
    onOk: async () => {
      try {
        await deleteCustomer(id)
        Message.success('删除成功')
        loadCustomers()
      } catch (error: unknown) {
        handleError(error, '删除失败')
      }
    },
  })
}

// 高级筛选搜索
const handleAdvancedSearch = () => {
  pagination.current = 1
  loadCustomers()
}

// 加载运营经理列表
const loadManagers = async () => {
  managersLoading.value = true
  try {
    const res = await getManagers()
    managers.value = res.data?.list || res.data || []
  } catch (error: unknown) {
    console.error('加载运营经理失败:', error)
  } finally {
    managersLoading.value = false
  }
}

// 加载客户标签列表
const loadCustomerTags = async () => {
  tagsLoading.value = true
  try {
    const res = await getTags({ type: 'customer', page_size: 100 })
    customerTags.value = res.data?.list || []
  } catch (error: unknown) {
    console.error('加载标签失败:', error)
  } finally {
    tagsLoading.value = false
  }
}

// 加载行业类型
const loadIndustryTypesData = async () => {
  try {
    const res = await getIndustryTypes()
    industryTypes.value = res.data?.data || res.data || []
  } catch (error) {
    console.error('Failed to load industry types:', error)
  }
}

// ========== 批量选择事件 ==========
// 单个选择/取消
const handleBatchSelect = (checked: boolean, row: Customer) => {
  if (checked) {
    if (!selectedCustomerIds.value.includes(row.id)) {
      selectedCustomerIds.value.push(row.id)
    }
  } else {
    const idx = selectedCustomerIds.value.indexOf(row.id)
    if (idx > -1) {
      selectedCustomerIds.value.splice(idx, 1)
    }
  }
}

// 全选/取消全选
const handleBatchSelectAll = (checked: boolean) => {
  if (checked) {
    selectedCustomerIds.value = customers.value.map(c => c.id)
  } else {
    selectedCustomerIds.value = []
  }
}

// 导出客户
const handleExport = async () => {
  try {
    const params: Record<string, unknown> = {}
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.account_type) params.account_type = filters.account_type
    if (filters.industry && filters.industry.length > 0)
      params.industry = filters.industry.join(',')
    if (filters.is_key_customer !== null) params.is_key_customer = filters.is_key_customer
    if (filters.is_real_estate !== null) params.is_real_estate = filters.is_real_estate
    if (filters.settlement_type) params.settlement_type = filters.settlement_type
    if (advancedFilters.manager_id) params.manager_id = advancedFilters.manager_id
    if (advancedFilters.sales_manager_id) params.sales_manager_id = advancedFilters.sales_manager_id

    const res = await exportCustomers(params)

    // 处理文件下载
    const blob = res.data as Blob
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `customers_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    Message.success('导出成功')
  } catch (error: unknown) {
    handleError(error, '导出失败')
  }
}

// ========== 新建/编辑客户 ==========
const customerModalVisible = ref(false)
const isEditMode = ref(false)
const editingCustomerData = ref<Customer | null>(null)

const openCreateModal = () => {
  isEditMode.value = false
  editingCustomerData.value = null
  customerModalVisible.value = true
}

const openEditModal = (record: Customer) => {
  isEditMode.value = true
  editingCustomerData.value = record
  customerModalVisible.value = true
}

// ========== 批量选择相关 ==========
const selectedCustomerIds = ref<number[]>([])
const hasSelectedCustomers = computed(() => selectedCustomerIds.value.length > 0)

const batchEditDialogVisible = ref(false)

const openBatchEditDialog = () => {
  batchEditDialogVisible.value = true
}

const clearBatchSelection = () => {
  selectedCustomerIds.value = []
  batchEditDialogVisible.value = false
}

const viewCustomer = (id: number) => {
  router.push(`/customers/${id}`)
}

const viewProfile = (id: number) => {
  router.push(`/customers/${id}`)
}

// ========== 导入客户 ==========
const importModalVisible = ref(false)

const openImportModal = () => {
  importModalVisible.value = true
}

onMounted(() => {
  loadCustomers()
  loadManagers()
  loadCustomerTags()
  loadIndustryTypesData()
})
</script>

<style scoped>
.customer-list-page {
  padding: 0; /* 移除 padding，由 Dashboard 统一提供 */
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-3: #e0e2e7;
  --neutral-5: #8f959e;
  --neutral-6: #646a73;
  --neutral-7: #4c5360;
  --neutral-9: #2f3645;
  --neutral-10: #1d2330;
  --primary-6: #0369a1;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--neutral-10);
  margin-bottom: 8px;
}

.header-subtitle {
  font-size: 14px;
  color: var(--neutral-6);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.filter-section {
  background: white;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  margin-bottom: 24px;
}

.filter-section .arco-form-item {
  margin-bottom: 0;
}

.filter-section .arco-select,
.filter-section .arco-input {
  width: 100%;
}

.advanced-filter-collapse {
  margin-top: 16px;
}

.advanced-filter-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.advanced-filter-toggle svg {
  transition: transform 0.2s;
}

.table-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

:deep(.arco-table) {
  font-size: 14px;
}

:deep(.arco-table th) {
  font-size: 13px;
  white-space: nowrap;
  background: var(--neutral-1);
  color: var(--neutral-6);
  font-weight: 600;
}

:deep(.arco-table td) {
  color: var(--neutral-7);
}

:deep(.arco-table tr:hover td) {
  background: var(--neutral-1);
}

/* 重点客户名称单元格布局 */
.name-cell {
  display: flex;
  align-items: center;
  gap: 4px;
}

.key-customer-badge {
  color: #ff4d4f;
  font-size: 14px;
  line-height: 1;
  flex-shrink: 0;
}

.name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.arco-form-item-required) .arco-form-item-label::before {
  content: '*';
  color: #ff4d4f;
  margin-right: 4px;
}

/* 导入弹框样式 */
.import-modal-content {
  padding: 4px 0;
}

.upload-area {
  border: 2px dashed var(--neutral-3);
  border-radius: 12px;
  padding: 40px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s ease;
  background: var(--neutral-1);
  margin-bottom: 20px;
}

.upload-area:hover {
  border-color: var(--primary-6);
  background: rgba(3, 105, 161, 0.04);
}

.upload-area:active {
  transform: scale(0.99);
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.upload-icon {
  color: var(--neutral-5);
  margin-bottom: 8px;
  transition: color 0.25s ease;
}

.upload-area:hover .upload-icon {
  color: var(--primary-6);
}

.upload-icon svg {
  width: 48px;
  height: 48px;
}

.upload-text-primary {
  font-size: 16px;
  font-weight: 500;
  color: var(--neutral-9);
  line-height: 1.5;
}

.upload-text-secondary {
  font-size: 13px;
  color: var(--neutral-6);
  line-height: 1.4;
}

.file-selected {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: white;
  border-radius: 10px;
  border: 1px solid var(--neutral-2);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.file-icon {
  color: var(--primary-6);
  flex-shrink: 0;
}

.file-info {
  flex: 1;
  min-width: 0;
  text-align: left;
}

.file-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--neutral-9);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.file-size {
  font-size: 12px;
  color: var(--neutral-6);
}

.file-remove {
  color: var(--neutral-5);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.file-remove:hover {
  color: #ff4d4f;
  background: rgba(255, 77, 79, 0.08);
}

.file-input-hidden {
  display: none;
}

.import-tips {
  background: rgba(3, 105, 161, 0.04);
  border-radius: 8px;
  padding: 14px 16px;
  border-left: 3px solid var(--primary-6);
}

.tips-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--neutral-9);
  margin-bottom: 10px;
}

.tips-list {
  margin: 0;
  padding-left: 16px;
  list-style: disc;
}

.tips-list li {
  font-size: 12px;
  color: var(--neutral-7);
  line-height: 1.8;
}

.tips-list li:last-child {
  margin-bottom: 0;
}

/* 行业类型多选标签样式优化 */
.filter-section :deep(.arco-select-multiple .arco-tag) {
  max-width: calc(100% - 40px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: rgba(3, 105, 161, 0.08);
  color: var(--primary-6);
  border: none;
  border-radius: 4px;
  font-size: 12px;
  padding: 2px 8px;
}

/* 标签关闭按钮样式 */
.filter-section :deep(.arco-select-multiple .arco-tag .arco-icon-close) {
  color: var(--primary-6);
  opacity: 0.7;
  transition: opacity 0.2s;
}

.filter-section :deep(.arco-select-multiple .arco-tag .arco-icon-close:hover) {
  opacity: 1;
}

/* "+N" 提示样式 */
.filter-section :deep(.arco-select-multiple .arco-select-tag) {
  background: rgba(15, 23, 42, 0.06);
  color: var(--neutral-10);
  border: none;
  border-radius: 4px;
  font-size: 12px;
}

/* 批量操作工具栏 */
.batch-toolbar {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: var(--color-fill-1);
  border-bottom: 1px solid var(--neutral-2);
}

/* 批量编辑表单布局 */
.batch-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.batch-field-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>

