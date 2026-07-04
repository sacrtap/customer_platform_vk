import { reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getBalances, recharge as rechargeApi } from '@/api/billing'
import type { Balance } from '@/api/billing'
import { getIndustryTypes } from '@/api/customers'
import { getTags } from '@/api/tags'
import { getManagers } from '@/api/users'
import type { IndustryType, Tag, User } from '@/types'

const defaultFilters = () => ({
  keyword: '',
  recharge_date: [] as string[],
industry: [] as string[],
account_type: '',
  is_key_customer: null as boolean | null,
  is_real_estate: null as boolean | null,
  settlement_type: '',
})

const defaultAdvancedFilters = () => ({
  manager_id: null as number | null,
  sales_manager_id: null as number | null,
  tag_ids: [] as number[],
})

export interface SortState {
  sort_by: string
  sort_order: 'ascend' | 'descend' | ''
}

export function useBalance() {
  const loading = ref(false)
  const balances = ref<Balance[]>([])
  const total = ref(0)

  const filters = reactive(defaultFilters())
  const advancedFilters = reactive(defaultAdvancedFilters())

  const sortState = reactive<SortState>({
    sort_by: '',
    sort_order: '',
  })

  const pagination = reactive({
    current: 1,
    pageSize: 20,
    showTotal: true,
    showPageSize: true,
    pageSizeOptions: [10, 20, 50, 100],
  })

  const industryTypes = ref<IndustryType[]>([])
  const tagOptions = ref<Tag[]>([])
  const managers = ref<User[]>([])

  const backendSortOrder = (): 'asc' | 'desc' => {
    if (sortState.sort_order === 'ascend') return 'asc'
    if (sortState.sort_order === 'descend') return 'desc'
    return 'asc'
  }

  const loadBalances = async () => {
    loading.value = true
    try {
      const params: Record<string, unknown> = {
        page: pagination.current,
        page_size: pagination.pageSize,
        sort_by: sortState.sort_by || undefined,
        sort_order: backendSortOrder(),
      }
      if (filters.keyword) params.keyword = filters.keyword
      if (filters.account_type) params.account_type = filters.account_type
      if (filters.industry?.length) params.industry = filters.industry.join(',')
      if (filters.recharge_date?.length === 2) {
        params.recharge_date_from = filters.recharge_date[0]
        params.recharge_date_to = filters.recharge_date[1]
      }
      if (advancedFilters.manager_id) params.manager_id = advancedFilters.manager_id
      if (advancedFilters.sales_manager_id) params.sales_manager_id = advancedFilters.sales_manager_id
      if (advancedFilters.tag_ids?.length) params.tag_ids = advancedFilters.tag_ids.join(',')
      if (filters.is_real_estate !== null && filters.is_real_estate !== undefined) {
        params.is_real_estate = filters.is_real_estate
      }
      if (filters.settlement_type) params.settlement_type = filters.settlement_type

      const res = await getBalances(params)
      balances.value = res.data?.items || []
      total.value = res.data?.total || 0
    } catch {
      balances.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  const handlePageChange = (page: number) => {
    pagination.current = page
    loadBalances()
  }

  const handlePageSizeChange = (pageSize: number) => {
    pagination.pageSize = pageSize
    pagination.current = 1
    loadBalances()
  }

  const handleSortChange = (dataIndex: string, direction: string) => {
    sortState.sort_by = dataIndex
    sortState.sort_order = direction as 'ascend' | 'descend' | ''
    loadBalances()
  }

  const handleSearch = () => {
    pagination.current = 1
    loadBalances()
  }

  const handleReset = () => {
    Object.assign(filters, defaultFilters())
    Object.assign(advancedFilters, defaultAdvancedFilters())
    pagination.current = 1
    loadBalances()
  }

  const doRecharge = async (data: { customer_id: number; real_amount: number; bonus_amount?: number; remark?: string }) => {
    await rechargeApi(data)
    Message.success('充值成功')
    loadBalances()
  }

  const loadIndustries = async () => {
    const res = await getIndustryTypes()
    industryTypes.value = res.data || []
  }

  const loadTags = async () => {
    const res = await getTags()
    tagOptions.value = res.data || []
  }

  const loadManagers = async () => {
    const res = await getManagers()
    managers.value = res.data || []
  }

  return {
    loading, balances, total,
    filters, advancedFilters, sortState, pagination,
    industryTypes, tagOptions, managers,
    loadBalances, handlePageChange, handlePageSizeChange,
    handleSortChange, handleSearch, handleReset,
    doRecharge, loadIndustries, loadTags, loadManagers,
  }
}
