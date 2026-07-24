import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useInvoice } from '../useInvoice'

// Mock API modules
const mockGetInvoices = vi.fn()

vi.mock('@/api/billing', () => ({
  getInvoices: (...args: unknown[]) => mockGetInvoices(...args),
  getInvoice: vi.fn(),
  generateInvoice: vi.fn(),
  applyDiscount: vi.fn(),
  payInvoice: vi.fn(),
  submitInvoice: vi.fn(),
  confirmInvoice: vi.fn(),
  cancelInvoice: vi.fn(),
  deleteInvoice: vi.fn(),
  confirmOps: vi.fn(),
  confirmSales: vi.fn(),
  retryDeduction: vi.fn(),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

describe('useInvoice - 排序逻辑', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetInvoices.mockResolvedValue({
      data: { list: [], total: 0 },
    })
  })

  it('初始状态下 sort_by 为空，sort_order 为空', () => {
    const { sortState } = useInvoice()
    expect(sortState.sort_by).toBe('')
    expect(sortState.sort_order).toBe('')
  })

  it('handleSortChange 设置升序时，API 收到 sort_by 和 sort_order=asc', async () => {
    const { handleSortChange } = useInvoice()
    handleSortChange('total_amount', 'asc')
    await vi.waitFor(() => {
      expect(mockGetInvoices).toHaveBeenCalled()
    })
    const callArgs = mockGetInvoices.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('total_amount')
    expect(callArgs.sort_order).toBe('asc')
  })

  it('handleSortChange 设置降序时，API 收到 sort_order=desc', async () => {
    const { handleSortChange } = useInvoice()
    handleSortChange('total_amount', 'desc')
    await vi.waitFor(() => {
      expect(mockGetInvoices).toHaveBeenCalled()
    })
    const callArgs = mockGetInvoices.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('total_amount')
    expect(callArgs.sort_order).toBe('desc')
  })

  it('handleSortChange 清除排序时（空字符串），API 不发送 sort_by 和 sort_order', async () => {
    const { handleSortChange } = useInvoice()
    handleSortChange('', '')
    await vi.waitFor(() => {
      expect(mockGetInvoices).toHaveBeenCalled()
    })
    const callArgs = mockGetInvoices.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBeUndefined()
    expect(callArgs.sort_order).toBeUndefined()
  })

  it('切换不同列排序时，sort_by 更新为新列', async () => {
    const { handleSortChange, sortState } = useInvoice()
    handleSortChange('total_amount', 'asc')
    await vi.waitFor(() => expect(mockGetInvoices).toHaveBeenCalled())
    expect(sortState.sort_by).toBe('total_amount')

    vi.clearAllMocks()
    mockGetInvoices.mockResolvedValue({ data: { list: [], total: 0 } })

    handleSortChange('created_at', 'desc')
    await vi.waitFor(() => expect(mockGetInvoices).toHaveBeenCalled())
    expect(sortState.sort_by).toBe('created_at')
    const callArgs = mockGetInvoices.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('created_at')
    expect(callArgs.sort_order).toBe('desc')
  })

  it('排序方向在 asc → desc → 清除 之间正确循环', async () => {
    const { handleSortChange, sortState } = useInvoice()

    // 第一次：升序
    handleSortChange('total_amount', 'asc')
    await vi.waitFor(() => expect(mockGetInvoices).toHaveBeenCalled())
    expect(sortState.sort_by).toBe('total_amount')
    expect(sortState.sort_order).toBe('asc')

    vi.clearAllMocks()
    mockGetInvoices.mockResolvedValue({ data: { list: [], total: 0 } })

    // 第二次：降序
    handleSortChange('total_amount', 'desc')
    await vi.waitFor(() => expect(mockGetInvoices).toHaveBeenCalled())
    expect(sortState.sort_by).toBe('total_amount')
    expect(sortState.sort_order).toBe('desc')

    vi.clearAllMocks()
    mockGetInvoices.mockResolvedValue({ data: { list: [], total: 0 } })

    // 第三次：清除排序
    handleSortChange('', '')
    await vi.waitFor(() => expect(mockGetInvoices).toHaveBeenCalled())
    expect(sortState.sort_by).toBe('')
    expect(sortState.sort_order).toBe('')
  })

  it('invoice_no 列排序时正确传递参数', async () => {
    const { handleSortChange } = useInvoice()
    handleSortChange('invoice_no', 'asc')
    await vi.waitFor(() => {
      expect(mockGetInvoices).toHaveBeenCalled()
    })
    const callArgs = mockGetInvoices.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('invoice_no')
    expect(callArgs.sort_order).toBe('asc')
  })

  it('final_amount 列排序时正确传递参数', async () => {
    const { handleSortChange } = useInvoice()
    handleSortChange('final_amount', 'desc')
    await vi.waitFor(() => {
      expect(mockGetInvoices).toHaveBeenCalled()
    })
    const callArgs = mockGetInvoices.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('final_amount')
    expect(callArgs.sort_order).toBe('desc')
  })

  it('created_at 列排序时正确传递参数', async () => {
    const { handleSortChange } = useInvoice()
    handleSortChange('created_at', 'desc')
    await vi.waitFor(() => {
      expect(mockGetInvoices).toHaveBeenCalled()
    })
    const callArgs = mockGetInvoices.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('created_at')
    expect(callArgs.sort_order).toBe('desc')
  })
})
