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
import type { IndustryType, Customer } from '@/types'

/**
 * 客户列表页 composable
 * 封装列表数据加载、分页、筛选、批量操作、导出等逻辑
 */
export function useCustomerList() {
  const router = useRouter()
  const userStore = useUserStore()
  const can = (permission: string) => userStore.hasPermission(permission)

  // ---------- 筛选条件 ----------
  const createDefaultFilters = () => ({
    keyword: '',
    account_type: '正式账号',
    industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
    scale_level: '',
    consume_level: '',
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

  // ---------- 字典数据 ----------
  const managersLoading = ref(false)
  const managers = ref<Array<Record<string, unknown>>>([])
  const tagsLoading = ref(false)
  const customerTags = ref<Array<Record<string, unknown>>>([])
  const industryTypes = ref<IndustryType[]>([
    { id: 1, name: '房产经纪', sort_order: 1 },
    { id: 2, name: '房产ERP', sort_order: 2 },
    { id: 3, name: '房产平台', sort_order: 3 },
  ])

  // ---------- 表格数据 ----------
  const loading = ref(false)
  const customers = ref<Customer[]>([])
  const pagination = reactive({
    current: 1,
    pageSize: 20,
    total: 0,
    showTotal: true,
    showPageSize: true,
    pageSizeOptions: [10, 20, 50, 100],
  })

  // ---------- 批量选择 ----------
  const selectedCustomerIds = ref<number[]>([])
  const hasSelectedCustomers = computed(() => selectedCustomerIds.value.length > 0)

  // ---------- 模态框状态 ----------
  const customerModalVisible = ref(false)
  const isEditMode = ref(false)
  const editingCustomerData = ref<Customer | null>(null)
  const batchEditDialogVisible = ref(false)
  const importModalVisible = ref(false)

  // ---------- 数据加载 ----------
  const loadCustomers = async () => {
    loading.value = true
    try {
      const params: Record<string, unknown> = {
        page: pagination.current,
        page_size: pagination.pageSize,
        force_refresh: true,
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
    } catch (error: unknown) {
      handleError(error, '加载客户列表失败')
    } finally {
      loading.value = false
    }
  }

  const handleRefresh = async () => {
    loading.value = true
    try {
      const params: Record<string, unknown> = {
        page: pagination.current,
        page_size: pagination.pageSize,
        force_refresh: true,
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

  // ---------- 分页 ----------
  const handlePageChange = (page: number) => {
    pagination.current = page
    loadCustomers()
  }

  const handlePageSizeChange = (pageSize: number) => {
    pagination.pageSize = pageSize
    pagination.current = 1
    loadCustomers()
  }

  const handleSort = (dataIndex: string, direction: string) => {
    // 排序逻辑（当前后端已实现）
    console.debug('sort:', dataIndex, direction)
  }

  // ---------- 客户操作 ----------
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

  const handleSearch = () => {
    pagination.current = 1
    loadCustomers()
  }

  const handleReset = () => {
    Object.assign(filters, createDefaultFilters())
    advancedFilters.manager_id = null
    advancedFilters.sales_manager_id = null
    advancedFilters.tag_ids = []
    pagination.current = 1
    loadCustomers()
  }

  const handleAdvancedSearch = () => {
    pagination.current = 1
    loadCustomers()
  }

  // ---------- 字典加载 ----------
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

  const loadIndustryTypesData = async () => {
    try {
      const res = await getIndustryTypes()
      industryTypes.value = res.data?.data || res.data || []
    } catch (error) {
      console.error('Failed to load industry types:', error)
    }
  }

  // ---------- 批量操作 ----------
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

  const handleBatchSelectAll = (checked: boolean) => {
    if (checked) {
      selectedCustomerIds.value = customers.value.map(c => c.id)
    } else {
      selectedCustomerIds.value = []
    }
  }

  const openBatchEditDialog = () => {
    batchEditDialogVisible.value = true
  }

  const clearBatchSelection = () => {
    selectedCustomerIds.value = []
    batchEditDialogVisible.value = false
  }

  // ---------- 导出 ----------
  const handleExport = async () => {
    try {
      const params: Record<string, unknown> = {}
      if (filters.keyword) params.keyword = filters.keyword
      if (filters.account_type) params.account_type = filters.account_type

      const res = await exportCustomers(params)
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })
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

  // ---------- 模态框操作 ----------
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

  const viewCustomer = (id: number) => {
    router.push(`/customers/${id}`)
  }

  const viewProfile = (id: number) => {
    router.push(`/customers/${id}`)
  }

  const openImportModal = () => {
    importModalVisible.value = true
  }

  // ---------- 生命周期 ----------
  onMounted(() => {
    loadCustomers()
    loadManagers()
    loadCustomerTags()
    loadIndustryTypesData()
  })

  return {
    // 权限
    can,
    // 筛选
    filters, advancedFilters,
    // 字典
    managers, managersLoading, customerTags, tagsLoading, industryTypes,
    // 表格
    loading, customers, pagination,
    // 批量选择
    selectedCustomerIds, hasSelectedCustomers,
    // 模态框
    customerModalVisible, isEditMode, editingCustomerData,
    batchEditDialogVisible, importModalVisible,
    // 数据方法
    loadCustomers, handleRefresh, handleSearch, handleReset, handleAdvancedSearch,
    // 分页
    handlePageChange, handlePageSizeChange, handleSort,
    // 客户操作
    handleDelete,
    // 批量操作
    handleBatchSelect, handleBatchSelectAll, openBatchEditDialog, clearBatchSelection,
    // 导出
    handleExport,
    // 模态框方法
    openCreateModal, openEditModal, viewCustomer, viewProfile, openImportModal,
  }
}
