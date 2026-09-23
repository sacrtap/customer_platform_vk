import { reactive, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getBalances, getBalanceStats, recharge as rechargeApi } from '@/api/billing'
import type { Balance, BalanceQueryParams } from '@/api/billing'
import { getIndustryTypes } from '@/api/customers'
import { getTags } from '@/api/tags'
import { getManagers } from '@/api/users'
import type { IndustryType, Tag, User } from '@/types'

// 默认行业筛选（与客户管理页 useCustomerList 保持一致：默认全部行业，仅限定正式账号）
export const DEFAULT_INDUSTRY: string[] = []
export const DEFAULT_ACCOUNT_TYPE = '正式账号'

const defaultFilters = () => ({
  keyword: '',
  recharge_date: [] as string[],
  industry: [] as string[],
  account_type: '正式账号',
  is_key_customer: null as boolean | null,
  is_real_estate: null as boolean | null,
  is_settlement_enabled: null as boolean | null,
  settlement_type: '',
  // 结算类型分组（KPI 卡片联动）：prepaid = 非后付费（含未设置），postpaid = 后付费
  settlement_group: '' as '' | 'prepaid' | 'postpaid',
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
// 注意：max 值使用 -0.01/9999.99/99999.99/999999.99 避免与下一档边界重叠。
// 「1万以下」的 min 有意为 null（含欠费与零余额），与 KPI「余额不足」卡片的统计口径
// （余额 < 1 万，含欠费）保持一致；「欠费」是其中只看负余额的窄档，两者重叠属预期。
export const BALANCE_RANGE_OPTIONS = [
  { label: '欠费', value: 'debt', min: null as number | null, max: -0.01 },
  { label: '1万以下', value: 'low', min: null as number | null, max: 9999.99 },
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
    total_balance_prepaid: 0,
    prepaid_customers: 0,
    total_balance_postpaid: 0,
    postpaid_customers: 0,
    postpaid_receivable: 0,
    this_month_count: 0,
    this_month_amount: 0,
    this_month_real_amount: 0,
    this_month_bonus_amount: 0,
    low_balance_count: 0,
    burning_soon_count: 0,
  })

  const sortState = reactive<SortState>({
    sort_by: 'company_id',
    sort_order: 'asc',
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

  // 列表（loadBalances）/ 统计（loadStats）/ 导出（buildExportParams）三处
  // 筛选参数构建共享的通用字段。is_key_customer / is_real_estate 在导出接口
  // （BalanceQueryParams）中定义为 string，其余接口为 boolean，故用 stringifyBooleans
  // 区分；axios 序列化时布尔值与 "true"/"false" 字符串在 URL 上等价。
  const buildCommonFilterParams = (stringifyBooleans: boolean): Record<string, unknown> => {
    const params: Record<string, unknown> = {}
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.account_type) params.account_type = filters.account_type
    if (filters.industry?.length) params.industry = filters.industry.join(',')
    if (filters.settlement_type) params.settlement_type = filters.settlement_type
    if (advancedFilters.manager_id) params.manager_id = advancedFilters.manager_id
    if (advancedFilters.sales_manager_id) params.sales_manager_id = advancedFilters.sales_manager_id
    if (advancedFilters.tag_ids?.length) params.tag_ids = advancedFilters.tag_ids.join(',')
    if (filters.is_key_customer !== null && filters.is_key_customer !== undefined) {
      params.is_key_customer = stringifyBooleans
        ? String(filters.is_key_customer)
        : filters.is_key_customer
    }
    if (filters.is_real_estate !== null && filters.is_real_estate !== undefined) {
      params.is_real_estate = stringifyBooleans
        ? String(filters.is_real_estate)
        : filters.is_real_estate
    }
    if (filters.is_settlement_enabled !== null && filters.is_settlement_enabled !== undefined) {
      params.is_settlement_enabled = stringifyBooleans
        ? String(filters.is_settlement_enabled)
        : filters.is_settlement_enabled
    }
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
        ...buildCommonFilterParams(false),
      }
      if (forceRefresh) params.force_refresh = true
      if (filters.recharge_date?.length === 2) {
        params.recharge_date_from = filters.recharge_date[0]
        params.recharge_date_to = filters.recharge_date[1]
      }

      // 余额范围
      const rangeParams = getBalanceRangeParams()
      if (rangeParams.balance_min != null) params.balance_min = rangeParams.balance_min
      if (rangeParams.balance_max != null) params.balance_max = rangeParams.balance_max

      // 结算类型分组（KPI 卡片联动；统计接口不使用该参数，两张卡片各自统计）
      if (filters.settlement_group) params.settlement_group = filters.settlement_group

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

  // 构建余额导出的筛选参数（与列表筛选条件保持一致，不含分页与排序）
  const buildExportParams = (): BalanceQueryParams => {
    const params = buildCommonFilterParams(true) as BalanceQueryParams
    if (filters.recharge_date?.length === 2) {
      params.recharge_date_from = filters.recharge_date[0]
      params.recharge_date_to = filters.recharge_date[1]
    }

    const rangeParams = getBalanceRangeParams()
    if (rangeParams.balance_min != null) params.balance_min = rangeParams.balance_min
    if (rangeParams.balance_max != null) params.balance_max = rangeParams.balance_max

    if (filters.settlement_group) params.settlement_group = filters.settlement_group

    return params
  }

  // 加载 KPI 统计 — 单次请求获取所有 KPI 数据
  // 后端 balance-stats 接口已聚合返回全部指标（预付费/后付费总余额与客户数、应收款、
  // 本月充值、余额不足、即将耗尽），无需额外发起多次 getBalances 请求
  const loadStats = async () => {
    try {
      const statsRes = await getBalanceStats(buildCommonFilterParams(false))
      if (statsRes.data) {
        stats.total_balance_prepaid = statsRes.data.total_balance_prepaid
        stats.prepaid_customers = statsRes.data.prepaid_customers
        stats.total_balance_postpaid = statsRes.data.total_balance_postpaid
        stats.postpaid_customers = statsRes.data.postpaid_customers
        stats.postpaid_receivable = statsRes.data.postpaid_receivable
        stats.this_month_amount = statsRes.data.this_month_amount
        stats.this_month_count = statsRes.data.this_month_count
        stats.this_month_real_amount = statsRes.data.this_month_real_amount
        stats.this_month_bonus_amount = statsRes.data.this_month_bonus_amount
        stats.low_balance_count = statsRes.data.low_balance_count ?? 0
        stats.burning_soon_count = statsRes.data.burning_soon_count ?? 0
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
    loadStats()
  }

  const handleReset = () => {
    Object.assign(filters, defaultFilters())
    Object.assign(advancedFilters, defaultAdvancedFilters())
    pagination.current = 1
    loadBalances()
    loadStats()
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
    // getTags 返回分页结构 {list, total}，与客户管理页处理方式保持一致
    tagOptions.value = res.data?.list || res.data || []
  }

  const loadManagers = async () => {
    const res = await getManagers()
    // getManagers 返回分页结构 {list, total}，与客户管理页处理方式保持一致
    managers.value = res.data?.list || res.data || []
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
    loadBalances,
    loadStats,
    buildExportParams,
    handleRefresh,
    handlePageChange,
    handlePageSizeChange,
    handleSortChange,
    handleSearch,
    handleReset,
    doRecharge,
    loadIndustries,
    loadTags,
    loadManagers,
  }
}
