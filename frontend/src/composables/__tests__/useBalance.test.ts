import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useBalance } from '../useBalance'

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
        total_balance: 0,
        total_customers: 0,
        this_month_count: 0,
        this_month_amount: 0,
        this_month_real_amount: 0,
        this_month_bonus_amount: 0,
        low_balance_count: 0,
        zero_balance_count: 0,
      },
    })
  })

  it('初始状态下 sort_by 为空，sort_order 为空', () => {
    const { sortState } = useBalance()
    expect(sortState.sort_by).toBe('')
    expect(sortState.sort_order).toBe('')
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
  it('BALANCE_RANGE_OPTIONS 各档位边界不重叠', async () => {
    const { BALANCE_RANGE_OPTIONS } = await import('../useBalance')
    // zero: 0 ~ 0
    const zero = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'zero')!
    expect(zero.min).toBe(0)
    expect(zero.max).toBe(0)

    // low: 0.01 ~ 9999.99（不含 10000）
    const low = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'low')!
    expect(low.min).toBe(0.01)
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

  it('low 的 max 小于 mid 的 min（无重叠）', async () => {
    const { BALANCE_RANGE_OPTIONS } = await import('../useBalance')
    const low = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'low')!
    const mid = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'mid')!
    expect(low.max!).toBeLessThan(mid.min)
  })

  it('mid 的 max 小于 high 的 min（无重叠）', async () => {
    const { BALANCE_RANGE_OPTIONS } = await import('../useBalance')
    const mid = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'mid')!
    const high = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'high')!
    expect(mid.max!).toBeLessThan(high.min)
  })

  it('high 的 max 小于 top 的 min（无重叠）', async () => {
    const { BALANCE_RANGE_OPTIONS } = await import('../useBalance')
    const high = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'high')!
    const top = BALANCE_RANGE_OPTIONS.find((o) => o.value === 'top')!
    expect(high.max!).toBeLessThan(top.min)
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
        total_balance: 0,
        total_customers: 0,
        this_month_count: 0,
        this_month_amount: 0,
        this_month_real_amount: 0,
        this_month_bonus_amount: 0,
        low_balance_count: 0,
        zero_balance_count: 0,
      },
    })
  })

  it('loadStats 使用 getBalanceStats 获取 this_month_count（交易笔数）', async () => {
    // 模拟后端返回本月充值 5 笔，金额 50000（实充 45000 + 赠送 5000）
    mockGetBalanceStats.mockResolvedValue({
      data: {
        total_balance: 1000000,
        total_customers: 50,
        this_month_count: 5,
        this_month_amount: 50000,
        this_month_real_amount: 45000,
        this_month_bonus_amount: 5000,
        low_balance_count: 10,
        zero_balance_count: 3,
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

  it('loadStats 使用 getBalanceStats 获取 total_balance', async () => {
    mockGetBalanceStats.mockResolvedValue({
      data: {
        total_balance: 999999.99,
        total_customers: 42,
        this_month_count: 3,
        this_month_amount: 15000,
        this_month_real_amount: 12000,
        this_month_bonus_amount: 3000,
        low_balance_count: 5,
        zero_balance_count: 2,
      },
    })

    const { stats, loadStats } = useBalance()
    await loadStats()

    expect(stats.total_balance).toBe(999999.99)
  })

  it('loadStats 使用 getBalances 获取 total_customers（与列表一致）', async () => {
    // getBalances 返回 total=42
    mockGetBalances.mockImplementation((params: Record<string, unknown>) => {
      // 基础参数调用（无 balance_min/max）返回 42
      if (params.balance_min === undefined && params.balance_max === undefined) {
        return Promise.resolve({ data: { list: [], total: 42 } })
      }
      return Promise.resolve({ data: { list: [], total: 0 } })
    })

    const { stats, loadStats } = useBalance()
    await loadStats()

    expect(stats.total_customers).toBe(42)
  })

  it('loadStats 使用 getBalances 获取 low_balance_count（与列表一致）', async () => {
    mockGetBalances.mockImplementation((params: Record<string, unknown>) => {
      if (params.balance_min === 0.01 && params.balance_max === 9999.99) {
        return Promise.resolve({ data: { list: [], total: 8 } })
      }
      return Promise.resolve({ data: { list: [], total: 0 } })
    })

    const { stats, loadStats } = useBalance()
    await loadStats()

    expect(stats.low_balance_count).toBe(8)
  })

  it('loadStats 使用 getBalances 获取 zero_balance_count（与列表一致）', async () => {
    mockGetBalances.mockImplementation((params: Record<string, unknown>) => {
      if (params.balance_min === 0 && params.balance_max === 0) {
        return Promise.resolve({ data: { list: [], total: 3 } })
      }
      return Promise.resolve({ data: { list: [], total: 0 } })
    })

    const { stats, loadStats } = useBalance()
    await loadStats()

    expect(stats.zero_balance_count).toBe(3)
  })

  it('loadStats 不再使用 getBalances 获取本月充值数据', async () => {
    const { loadStats } = useBalance()
    await loadStats()

    // 检查所有 getBalances 调用，不应有 recharge_date_from/recharge_date_to 参数
    for (const call of mockGetBalances.mock.calls) {
      const params = call[0] as Record<string, unknown>
      expect(params.recharge_date_from).toBeUndefined()
      expect(params.recharge_date_to).toBeUndefined()
    }
  })

  it('loadStats 只发起 3 次 getBalances 请求（总客户/余额不足/零余额）', async () => {
    const { loadStats } = useBalance()
    await loadStats()

    // 之前是 4 次（含本月充值），修复后应为 3 次
    expect(mockGetBalances).toHaveBeenCalledTimes(3)
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
    expect(stats.total_balance).toBe(0)
    expect(stats.this_month_count).toBe(0)
  })

  it('lowParams 使用 balance_max=9999.99（不含 10000）', async () => {
    const { loadStats } = useBalance()
    await loadStats()

    // 找到 lowParams 调用
    const lowCall = mockGetBalances.mock.calls.find((call) => {
      const params = call[0] as Record<string, unknown>
      return params.balance_min === 0.01
    })
    expect(lowCall).toBeTruthy()
    const params = lowCall![0] as Record<string, unknown>
    expect(params.balance_max).toBe(9999.99)
  })
})
