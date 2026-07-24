import { reactive, ref, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getBalances, getBalanceStats, recharge as rechargeApi } from '@/api/billing'
import type { Balance } from '@/api/billing'
import { getIndustryTypes } from '@/api/customers'
import { getTags } from '@/api/tags'
import { getManagers } from '@/api/users'
import type { IndustryType, Tag, User } from '@/types'

// 默认行业筛选（与客户管理页 useCustomerList 保持一致）
export const DEFAULT_INDUSTRY = '房产经纪,房产ERP,房产平台'
export const DEFAULT_ACCOUNT_TYPE = '正式账号'

const defaultFilters = () => ({
  keyword: '',
  recharge_date: [] as string[],
  industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
  account_type: '正式账号',
  is_key_customer: null as boolean | null,
  is_real_estate: null as boolean | null,
  settlement_type: '',
  balance_range: '' as string,
})

const defaultAdvancedFilters = () => ({
  manager_id: null as number | null,
  sales_manager_id: null as number | null,
  tag_ids: [] as number[],
})

export interface SortState {
  sort_by: string
  sort_order: 'asc' | 'desc' | ''
}

// 余额范围预设
// 注意：max 值使用 9999.99/99999.99/999999.99 避免与下一档 min 边界重叠
// 'low' 的 min=0.01 排除零余额，与 KPI 统计逻辑一致（total_amount > 0 且 < 10000）
export const BALANCE_RANGE_OPTIONS = [
  { label: '零余额', value: 'zero', min: 0, max: 0 },
  { label: '1万以下', value: 'low', min: 0.01, max: 9999.99 },
  { label: '1万-10万', value: 'mid', min: 10000, max: 99999.99 },
  { label: '10万-100万', value: 'high', min: 100000, max: 999999.99 },
  { label: '100万以上', value: 'top', min: 1000000, max: null as number | null },
]

export function useBalance() {
  const loading = ref(false)
  const balances = ref<Balance[]>([])
  const total = ref(0)

  const filters = reactive(defaultFilters())
  const advancedFilters = reactive(defaultAdvancedFilters())

  // KPI 统计数据
  const stats = reactive({
    total_balance: 0,
    total_customers: 0,
    this_month_count: 0,
    this_month_amount: 0,
    this_month_real_amount: 0,
    this_month_bonus_amount: 0,
    low_balance_count: 0,
    zero_balance_count: 0,
  })

  const sortState = reactive<SortState>({
    sort_by: '',
    sort_order: '',
  })

  const pagination = reactive({
    current: 1,
    pageSize: 20,
    total: 0,
    showTotal: true,
    showPageSize: true,
    pageSizeOptions: [10, 20, 50, 100],
  })

  const industryTypes = ref<IndustryType[]>([])
  const tagOptions = ref<Tag[]>([])
  const managers = ref<User[]>([])

  // 批量选择
  const selectedIds = ref<number[]>([])
  const hasSelected = computed(() => selectedIds.value.length > 0)

  const backendSortOrder = (): 'asc' | 'desc' => {
    if (sortState.sort_order === 'asc') return 'asc'
    if (sortState.sort_order === 'desc') return 'desc'
    return 'asc'
  }

  // 根据 balance_range 过滤值获取 min/max
  const getBalanceRangeParams = (): { balance_min?: number; balance_max?: number } => {
    if (!filters.balance_range) return {}
    const option = BALANCE_RANGE_OPTIONS.find((o) => o.value === filters.balance_range)
    if (!option) return {}
    const params: { balance_min?: number; balance_max?: number } = {}
    if (option.min != null) params.balance_min = option.min
    if (option.max != null) params.balance_max = option.max
    return params
  }

  const loadBalances = async (forceRefresh = false) => {
    loading.value = true
    try {
      const params: Record<string, unknown> = {
        page: pagination.current,
        page_size: pagination.pageSize,
        sort_by: sortState.sort_by || undefined,
        sort_order: sortState.sort_by ? backendSortOrder() : undefined,
      }
      if (forceRefresh) params.force_refresh = true
      if (filters.keyword) params.keyword = filters.keyword
      if (filters.account_type) params.account_type = filters.account_type
      if (filters.industry?.length) params.industry = filters.industry.join(',')
      if (filters.recharge_date?.length === 2) {
        params.recharge_date_from = filters.recharge_date[0]
        params.recharge_date_to = filters.recharge_date[1]
      }
      if (advancedFilters.manager_id) params.manager_id = advancedFilters.manager_id
      if (advancedFilters.sales_manager_id)
        params.sales_manager_id = advancedFilters.sales_manager_id
      if (advancedFilters.tag_ids?.length) params.tag_ids = advancedFilters.tag_ids.join(',')
      if (filters.is_real_estate !== null && filters.is_real_estate !== undefined) {
        params.is_real_estate = filters.is_real_estate
      }
      if (filters.is_key_customer !== null && filters.is_key_customer !== undefined) {
        params.is_key_customer = filters.is_key_customer
      }
      if (filters.settlement_type) params.settlement_type = filters.settlement_type

      // 余额范围
      const rangeParams = getBalanceRangeParams()
      if (rangeParams.balance_min != null) params.balance_min = rangeParams.balance_min
      if (rangeParams.balance_max != null) params.balance_max = rangeParams.balance_max

      const res = await getBalances(params)
      balances.value = res.data?.list || []
      total.value = res.data?.total || 0
      pagination.total = total.value
    } catch {
      balances.value = []
      total.value = 0
      pagination.total = 0
    } finally {
      loading.value = false
    }
  }

  // 构建 KPI 统计基础参数（与列表筛选条件保持一致）
  // 参照客户管理页面 loadKpiData 模式：使用 getBalances API 的 total 字段获取计数
  // 确保 KPI 卡片数字与点击后列表筛选结果完全一致
  const buildKpiBaseParams = (): Record<string, unknown> => {
    const params: Record<string, unknown> = {
      page: 1,
      page_size: 1,
    }
    if (filters.industry?.length) params.industry = filters.industry.join(',')
    if (filters.account_type) params.account_type = filters.account_type
    return params
  }

  // 加载 KPI 统计
  // 使用与列表相同的 getBalances API，通过不同筛选条件获取 total 计数
  // 确保 KPI 卡片数字与点击后列表筛选结果完全一致
  // 注意：总余额、本月充值金额/笔数使用后端 balance-stats 聚合接口
  const loadStats = async () => {
    try {
      const baseParams = buildKpiBaseParams()

      // 构建各 KPI 的筛选参数（与点击 KPI 卡片后列表筛选条件完全一致）
      // 余额不足：total_amount > 0 且 < 10000（与 BALANCE_RANGE_OPTIONS 的 'low' 一致）
      const lowParams = { ...baseParams, balance_min: 0.01, balance_max: 9999.99 }
      // 零余额：total_amount = 0（与 BALANCE_RANGE_OPTIONS 的 'zero' 一致）
      const zeroParams = { ...baseParams, balance_min: 0, balance_max: 0 }

      const results = await Promise.allSettled([
        getBalances(baseParams), // 总客户数
        getBalances(lowParams), // 余额不足
        getBalances(zeroParams), // 零余额
      ])

      // 总客户数
      if (results[0].status === 'fulfilled') {
        stats.total_customers = results[0].value.data?.total ?? 0
      }
      // 余额不足客户数
      if (results[1].status === 'fulfilled') {
        stats.low_balance_count = results[1].value.data?.total ?? 0
      }
      // 零余额客户数
      if (results[2].status === 'fulfilled') {
        stats.zero_balance_count = results[2].value.data?.total ?? 0
      }

      // 总余额、本月充值金额/笔数：使用后端 balance-stats 接口的 SQL 聚合查询
      // 不受分页限制，确保金额计算准确
      // this_month_count 为实际充值交易笔数（非客户数），与卡片 "X 笔" 含义一致
      try {
        const statsRes = await getBalanceStats({
          industry: filters.industry?.length ? filters.industry.join(',') : undefined,
          account_type: filters.account_type || undefined,
        })
        if (statsRes.data) {
          stats.total_balance = statsRes.data.total_balance
          stats.this_month_amount = statsRes.data.this_month_amount
          stats.this_month_count = statsRes.data.this_month_count
          stats.this_month_real_amount = statsRes.data.this_month_real_amount
          stats.this_month_bonus_amount = statsRes.data.this_month_bonus_amount
        }
      } catch {
        // 静默失败
      }
    } catch {
      // 静默失败，不影响列表
    }
  }

  // 数据刷新：强制跳过缓存重新加载列表 + 统计
  const handleRefresh = async () => {
    await Promise.all([loadBalances(true), loadStats()])
    Message.success('数据已刷新')
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
    sortState.sort_order = direction as 'asc' | 'desc' | ''
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
    selectedIds.value = []
    loadBalances()
  }

  // 批量选择
  const handleSelect = (checked: boolean, id: number) => {
    if (checked) {
      if (!selectedIds.value.includes(id)) {
        selectedIds.value.push(id)
      }
    } else {
      selectedIds.value = selectedIds.value.filter((sid) => sid !== id)
    }
  }

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      selectedIds.value = balances.value.map((b) => b.customer_id)
    } else {
      selectedIds.value = []
    }
  }

  const clearSelection = () => {
    selectedIds.value = []
  }

  const doRecharge = async (data: {
    customer_id: number
    real_amount: number
    bonus_amount?: number
    remark?: string
  }) => {
    await rechargeApi(data)
    Message.success('充值成功')
    loadBalances()
    loadStats()
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
    loading,
    balances,
    total,
    filters,
    advancedFilters,
    sortState,
    pagination,
    industryTypes,
    tagOptions,
    managers,
    stats,
    selectedIds,
    hasSelected,
    loadBalances,
    loadStats,
    handleRefresh,
    handlePageChange,
    handlePageSizeChange,
    handleSortChange,
    handleSearch,
    handleReset,
    handleSelect,
    handleSelectAll,
    clearSelection,
    doRecharge,
    loadIndustries,
    loadTags,
    loadManagers,
  }
}
