import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useBalance, BALANCE_RANGE_OPTIONS } from '../useBalance'

// Mock API modules
const mockGetBalances = vi.fn()
const mockGetBalanceStats = vi.fn()

vi.mock('@/api/billing', () => ({
  getBalances: (...args: unknown[]) => mockGetBalances(...args),
  getBalanceStats: (...args: unknown[]) => mockGetBalanceStats(...args),
  recharge: vi.fn(),
}))

vi.mock('@/api/customers', () => ({
  getIndustryTypes: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('@/api/tags', () => ({
  getTags: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('@/api/users', () => ({
  getManagers: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@/stores/user', () => ({
  useUserStore: vi.fn(() => ({
    hasPermission: vi.fn(() => true),
  })),
}))

describe('useBalance - 排序逻辑', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // 默认返回空列表
    mockGetBalances.mockResolvedValue({
      data: { list: [], total: 0 },
    })
    mockGetBalanceStats.mockResolvedValue({
      data: {
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
      },
    })
  })

  it('初始状态下 sort_by 为 company_id，sort_order 为 asc', () => {
    const { sortState } = useBalance()
    expect(sortState.sort_by).toBe('company_id')
    expect(sortState.sort_order).toBe('asc')
  })

  it('handleSortChange 设置升序时，API 收到 sort_by 和 sort_order=asc', async () => {
    const { handleSortChange } = useBalance()
    handleSortChange('total_amount', 'asc')
    // 等待异步 loadBalances 完成
    await vi.waitFor(() => {
      expect(mockGetBalances).toHaveBeenCalled()
    })
    const callArgs = mockGetBalances.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('total_amount')
    expect(callArgs.sort_order).toBe('asc')
  })

  it('handleSortChange 设置降序时，API 收到 sort_order=desc', async () => {
    const { handleSortChange } = useBalance()
    handleSortChange('total_amount', 'desc')
    await vi.waitFor(() => {
      expect(mockGetBalances).toHaveBeenCalled()
    })
    const callArgs = mockGetBalances.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('total_amount')
    expect(callArgs.sort_order).toBe('desc')
  })

  it('handleSortChange 清除排序时（空字符串），API 不发送 sort_by 和 sort_order', async () => {
    const { handleSortChange } = useBalance()
    handleSortChange('', '')
    await vi.waitFor(() => {
      expect(mockGetBalances).toHaveBeenCalled()
    })
    const callArgs = mockGetBalances.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBeUndefined()
    expect(callArgs.sort_order).toBeUndefined()
  })

  it('切换不同列排序时，sort_by 更新为新列', async () => {
    const { handleSortChange, sortState } = useBalance()
    // 先按 total_amount 排序
    handleSortChange('total_amount', 'asc')
    await vi.waitFor(() => {
      expect(mockGetBalances).toHaveBeenCalled()
    })
    expect(sortState.sort_by).toBe('total_amount')

    vi.clearAllMocks()
    mockGetBalances.mockResolvedValue({ data: { list: [], total: 0 } })

    // 切换到 used_total
    handleSortChange('used_total', 'desc')
    await vi.waitFor(() => {
      expect(mockGetBalances).toHaveBeenCalled()
    })
    expect(sortState.sort_by).toBe('used_total')
    const callArgs = mockGetBalances.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('used_total')
    expect(callArgs.sort_order).toBe('desc')
  })

  it('排序方向在 asc → desc → 清除 之间正确循环', async () => {
    const { handleSortChange, sortState } = useBalance()

    // 第一次：升序
    handleSortChange('total_amount', 'asc')
    await vi.waitFor(() => expect(mockGetBalances).toHaveBeenCalled())
    expect(sortState.sort_by).toBe('total_amount')
    expect(sortState.sort_order).toBe('asc')

    vi.clearAllMocks()
    mockGetBalances.mockResolvedValue({ data: { list: [], total: 0 } })

    // 第二次：降序
    handleSortChange('total_amount', 'desc')
    await vi.waitFor(() => expect(mockGetBalances).toHaveBeenCalled())
    expect(sortState.sort_by).toBe('total_amount')
    expect(sortState.sort_order).toBe('desc')

    vi.clearAllMocks()
    mockGetBalances.mockResolvedValue({ data: { list: [], total: 0 } })

    // 第三次：清除排序
    handleSortChange('', '')
    await vi.waitFor(() => expect(mockGetBalances).toHaveBeenCalled())
    expect(sortState.sort_by).toBe('')
    expect(sortState.sort_order).toBe('')
  })

  it('last_recharge_at 列排序时正确传递参数', async () => {
    const { handleSortChange } = useBalance()
    handleSortChange('last_recharge_at', 'desc')
    await vi.waitFor(() => {
      expect(mockGetBalances).toHaveBeenCalled()
    })
    const callArgs = mockGetBalances.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('last_recharge_at')
    expect(callArgs.sort_order).toBe('desc')
  })

  it('company_id 列排序时正确传递参数', async () => {
    const { handleSortChange } = useBalance()
    handleSortChange('company_id', 'asc')
    await vi.waitFor(() => {
      expect(mockGetBalances).toHaveBeenCalled()
    })
    const callArgs = mockGetBalances.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('company_id')
    expect(callArgs.sort_order).toBe('asc')
  })

  it('customer_name 列排序时正确传递参数', async () => {
    const { handleSortChange } = useBalance()
    handleSortChange('customer_name', 'desc')
    await vi.waitFor(() => {
      expect(mockGetBalances).toHaveBeenCalled()
    })
    const callArgs = mockGetBalances.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('customer_name')
    expect(callArgs.sort_order).toBe('desc')
  })
})

describe('useBalance - 余额范围选项边界', () => {
  it('BALANCE_RANGE_OPTIONS 各档位边界符合口径', () => {
    // 零余额档已移除（零余额客户不再单独成档）
    expect(BALANCE_RANGE_OPTIONS.find((o) => o.value === 'zero')).toBeUndefined()

    // debt: null ~ -0.01（仅负余额）
    const debt = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'debt')!
    expect(debt.min).toBeNull()
    expect(debt.max).toBe(-0.01)

    // low: null ~ 9999.99（含欠费与零余额，与 KPI「余额不足」口径一致）
    const low = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'low')!
    expect(low.min).toBeNull()
    expect(low.max).toBe(9999.99)

    // mid: 10000 ~ 99999.99（不含 100000）
    const mid = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'mid')!
    expect(mid.min).toBe(10000)
    expect(mid.max).toBe(99999.99)

    // high: 100000 ~ 999999.99（不含 1000000）
    const high = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'high')!
    expect(high.min).toBe(100000)
    expect(high.max).toBe(999999.99)

    // top: 1000000 ~ null
    const top = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'top')!
    expect(top.min).toBe(1000000)
    expect(top.max).toBeNull()
  })

  it('low 的 max 小于 mid 的 min（无重叠）', () => {
    const low = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'low')!
    const mid = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'mid')!
    expect(low.max!).toBeLessThan(mid.min!)
  })

  it('mid 的 max 小于 high 的 min（无重叠）', () => {
    const mid = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'mid')!
    const high = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'high')!
    expect(mid.max!).toBeLessThan(high.min!)
  })

  it('high 的 max 小于 top 的 min（无重叠）', () => {
    const high = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'high')!
    const top = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'top')!
    expect(high.max!).toBeLessThan(top.min!)
  })
})

describe('useBalance - KPI 统计计算', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetBalances.mockResolvedValue({
      data: { list: [], total: 0 },
    })
    mockGetBalanceStats.mockResolvedValue({
      data: {
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
      },
    })
  })

  it('loadStats 使用 getBalanceStats 获取 this_month_count（交易笔数）', async () => {
    // 模拟后端返回本月充值 5 笔，金额 50000（实充 45000 + 赠送 5000）
    mockGetBalanceStats.mockResolvedValue({
      data: {
        total_balance_prepaid: 1000000,
        prepaid_customers: 50,
        total_balance_postpaid: 0,
        postpaid_customers: 0,
        postpaid_receivable: 0,
        this_month_count: 5,
        this_month_amount: 50000,
        this_month_real_amount: 45000,
        this_month_bonus_amount: 5000,
        low_balance_count: 10,
        burning_soon_count: 2,
      },
    })

    const { stats, loadStats } = useBalance()
    await loadStats()

    // this_month_count 应来自 balance-stats（交易笔数），而非 getBalances（客户数）
    expect(stats.this_month_count).toBe(5)
    expect(stats.this_month_amount).toBe(50000)
    expect(stats.this_month_real_amount).toBe(45000)
    expect(stats.this_month_bonus_amount).toBe(5000)
  })

  it('loadStats 使用 getBalanceStats 获取预付费总余额与客户数', async () => {
    mockGetBalanceStats.mockResolvedValue({
      data: {
        total_balance_prepaid: 999999.99,
        prepaid_customers: 42,
        total_balance_postpaid: 0,
        postpaid_customers: 0,
        postpaid_receivable: 0,
        this_month_count: 3,
        this_month_amount: 15000,
        this_month_real_amount: 12000,
        this_month_bonus_amount: 3000,
        low_balance_count: 5,
        burning_soon_count: 1,
      },
    })

    const { stats, loadStats } = useBalance()
    await loadStats()

    expect(stats.total_balance_prepaid).toBe(999999.99)
    expect(stats.prepaid_customers).toBe(42)
  })

  it('loadStats 使用 getBalanceStats 获取后付费余额合计与应收款', async () => {
    mockGetBalanceStats.mockResolvedValue({
      data: {
        total_balance_prepaid: 0,
        prepaid_customers: 0,
        total_balance_postpaid: -3000,
        postpaid_customers: 2,
        postpaid_receivable: 3000,
        this_month_count: 0,
        this_month_amount: 0,
        this_month_real_amount: 0,
        this_month_bonus_amount: 0,
        low_balance_count: 0,
        burning_soon_count: 0,
      },
    })

    const { stats, loadStats } = useBalance()
    await loadStats()

    expect(stats.total_balance_postpaid).toBe(-3000)
    expect(stats.postpaid_customers).toBe(2)
    expect(stats.postpaid_receivable).toBe(3000)
    expect(mockGetBalanceStats).toHaveBeenCalledTimes(1)
    expect(mockGetBalances).not.toHaveBeenCalled()
  })

  it('loadStats 使用 getBalanceStats 获取 low_balance_count', async () => {
    mockGetBalanceStats.mockResolvedValue({
      data: {
        total_balance_prepaid: 0,
        prepaid_customers: 0,
        total_balance_postpaid: 0,
        postpaid_customers: 0,
        postpaid_receivable: 0,
        this_month_count: 0,
        this_month_amount: 0,
        this_month_real_amount: 0,
        this_month_bonus_amount: 0,
        low_balance_count: 8,
        burning_soon_count: 0,
      },
    })

    const { stats, loadStats } = useBalance()
    await loadStats()

    expect(stats.low_balance_count).toBe(8)
  })

  it('loadStats 使用 getBalanceStats 获取 burning_soon_count', async () => {
    mockGetBalanceStats.mockResolvedValue({
      data: {
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
        burning_soon_count: 3,
      },
    })

    const { stats, loadStats } = useBalance()
    await loadStats()

    expect(stats.burning_soon_count).toBe(3)
  })

  it('loadStats 不再调用 getBalances', async () => {
    const { loadStats } = useBalance()
    await loadStats()

    // loadStats 重构后仅调用 getBalanceStats，不再调用 getBalances
    expect(mockGetBalanceStats).toHaveBeenCalledTimes(1)
    expect(mockGetBalances).not.toHaveBeenCalled()
  })

  it('loadStats 仅发起 1 次 getBalanceStats 请求（不再调用 getBalances）', async () => {
    const { loadStats } = useBalance()
    await loadStats()

    // 重构后从多次 getBalances 改为单次 getBalanceStats 聚合请求
    expect(mockGetBalanceStats).toHaveBeenCalledTimes(1)
    expect(mockGetBalances).not.toHaveBeenCalled()
  })

  it('loadStats 传递 industry 和 account_type 给 getBalanceStats', async () => {
    const { loadStats, filters } = useBalance()
    filters.industry = ['房产经纪', '房产ERP']
    filters.account_type = '正式账号'

    await loadStats()

    expect(mockGetBalanceStats).toHaveBeenCalledWith({
      industry: '房产经纪,房产ERP',
      account_type: '正式账号',
    })
  })

  it('loadStats 在 getBalanceStats 失败时静默处理', async () => {
    mockGetBalanceStats.mockRejectedValue(new Error('Network error'))

    const { stats, loadStats } = useBalance()
    await loadStats()

    // 不应抛出异常，stats 保持默认值
    expect(stats.total_balance_prepaid).toBe(0)
    expect(stats.this_month_count).toBe(0)
  })
})

describe('useBalance - 结算类型分组筛选', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetBalances.mockResolvedValue({ data: { list: [], total: 0 } })
    mockGetBalanceStats.mockResolvedValue({
      data: {
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
      },
    })
  })

  it('settlement_group 传入余额列表查询', async () => {
    const { loadBalances, filters } = useBalance()
    filters.settlement_group = 'postpaid'

    await loadBalances()

    const callArgs = mockGetBalances.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.settlement_group).toBe('postpaid')
  })

  it('统计请求不携带 settlement_group，且始终按默认筛选口径统计', async () => {
    const { loadStats, filters } = useBalance()
    filters.settlement_group = 'postpaid'

    await loadStats()

    // 两张卡片各自统计，统计接口不接受分组参数；
    // 默认筛选与客户管理页一致：仅限定正式账号，行业为全部（不传 industry）
    expect(mockGetBalanceStats).toHaveBeenCalledWith({
      account_type: '正式账号',
    })
  })

  it('handleReset 清空结算类型分组', async () => {
    const { handleReset, filters } = useBalance()
    filters.settlement_group = 'prepaid'

    handleReset()

    expect(filters.settlement_group).toBe('')
  })
})

describe('useBalance - 默认筛选与客户管理页对齐', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetBalances.mockResolvedValue({ data: { list: [], total: 0 } })
    mockGetBalanceStats.mockResolvedValue({
      data: {
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
      },
    })
  })

  it('默认行业为全部（空数组），避免默认视图被行业筛选清空', () => {
    const { filters } = useBalance()
    expect(filters.industry).toEqual([])
    expect(filters.account_type).toBe('正式账号')
  })

  it('默认行业为空时不发送 industry 参数', async () => {
    const { loadBalances } = useBalance()

    await loadBalances()

    const callArgs = mockGetBalances.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.industry).toBeUndefined()
    expect(callArgs.account_type).toBe('正式账号')
  })

  it('is_settlement_enabled 传入列表与统计请求', async () => {
    const { loadBalances, loadStats, filters } = useBalance()
    filters.is_settlement_enabled = true

    await loadBalances()
    expect(
      (mockGetBalances.mock.calls[0][0] as Record<string, unknown>).is_settlement_enabled
    ).toBe(true)

    await loadStats()
    expect(
      (mockGetBalanceStats.mock.calls[0][0] as Record<string, unknown>).is_settlement_enabled
    ).toBe(true)
  })

  it('handleReset 恢复默认筛选（行业全部、是否结算清空）', () => {
    const { handleReset, filters } = useBalance()
    filters.industry = ['房产经纪']
    filters.account_type = '内部账号'
    filters.is_settlement_enabled = false

    handleReset()

    expect(filters.industry).toEqual([])
    expect(filters.account_type).toBe('正式账号')
    expect(filters.is_settlement_enabled).toBeNull()
  })
})
