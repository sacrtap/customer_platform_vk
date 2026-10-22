import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useInvoice } from '../useInvoice'

// Mock API modules
const mockGetInvoices = vi.fn()
const mockBatchSubmitInvoices = vi.fn()
const mockBatchCancelInvoices = vi.fn()
const mockBatchDeleteInvoices = vi.fn()
const mockGetInvoiceFileStatus = vi.fn()

vi.mock('@/api/billing', () => ({
  getInvoices: (...args: unknown[]) => mockGetInvoices(...args),
  getInvoice: vi.fn(),
  generateInvoice: vi.fn(),
  applyDiscount: vi.fn(),
  submitInvoice: vi.fn(),
  confirmInvoice: vi.fn(),
  cancelInvoice: vi.fn(),
  deleteInvoice: vi.fn(),
  confirmOps: vi.fn(),
  confirmSales: vi.fn(),
  retryDeduction: vi.fn(),
  updateInvoiceSettlementAccount: vi.fn(),
  getInvoiceFileStatus: (...args: unknown[]) => mockGetInvoiceFileStatus(...args),
  batchSubmitInvoices: (...args: unknown[]) => mockBatchSubmitInvoices(...args),
  batchCancelInvoices: (...args: unknown[]) => mockBatchCancelInvoices(...args),
  batchDeleteInvoices: (...args: unknown[]) => mockBatchDeleteInvoices(...args),
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

describe('useInvoice - 经理筛选参数', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetInvoices.mockResolvedValue({
      data: { list: [], total: 0 },
    })
  })

  it('defaultFilters 包含 manager_id / sales_manager_id 空串', () => {
    const { filters } = useInvoice()
    expect(filters.manager_id).toBe('')
    expect(filters.sales_manager_id).toBe('')
  })

  it('loadInvoices 在 filters.manager_id 非空时 params 含 manager_id', async () => {
    const { filters, loadInvoices } = useInvoice()
    filters.manager_id = '3'
    await loadInvoices()
    const callArgs = mockGetInvoices.mock.calls.at(-1)?.[0] as Record<string, unknown>
    expect(callArgs.manager_id).toBe('3')
  })

  it('loadInvoices 在 filters.sales_manager_id 非空时 params 含 sales_manager_id', async () => {
    const { filters, loadInvoices } = useInvoice()
    filters.sales_manager_id = '5'
    await loadInvoices()
    const callArgs = mockGetInvoices.mock.calls.at(-1)?.[0] as Record<string, unknown>
    expect(callArgs.sales_manager_id).toBe('5')
  })

  it('loadInvoices 在经理筛选为空时不发送对应参数', async () => {
    const { loadInvoices } = useInvoice()
    await loadInvoices()
    const callArgs = mockGetInvoices.mock.calls.at(-1)?.[0] as Record<string, unknown>
    expect(callArgs.manager_id).toBeUndefined()
    expect(callArgs.sales_manager_id).toBeUndefined()
  })

  it('handleReset 清空经理筛选', async () => {
    const { filters, handleReset } = useInvoice()
    filters.manager_id = '3'
    filters.sales_manager_id = '5'
    handleReset()
    expect(filters.manager_id).toBe('')
    expect(filters.sales_manager_id).toBe('')
  })
})

describe('useInvoice - 批量选择', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetInvoices.mockResolvedValue({
      data: { list: [], total: 0 },
    })
  })

  it('handleBatchSelect 勾选/取消幂等（去重、移除）', () => {
    const { selectedInvoiceIds, handleBatchSelect } = useInvoice()
    handleBatchSelect(true, 1)
    handleBatchSelect(true, 1)
    expect(selectedInvoiceIds.value).toEqual([1])
    handleBatchSelect(false, 1)
    expect(selectedInvoiceIds.value).toEqual([])
  })

  it('handleBatchSelectAll 全选当前页、取消清空', () => {
    const { selectedInvoiceIds, handleBatchSelectAll } = useInvoice()
    const invoices = [{ id: 1 }, { id: 2 }] as unknown as Parameters<
      ReturnType<typeof useInvoice>['handleBatchSelectAll']
    >[1]
    handleBatchSelectAll(true, invoices)
    expect(selectedInvoiceIds.value).toEqual([1, 2])
    handleBatchSelectAll(false, invoices)
    expect(selectedInvoiceIds.value).toEqual([])
  })

  it('hasSelected 与 clearSelection', () => {
    const { hasSelected, handleBatchSelect, clearSelection } = useInvoice()
    expect(hasSelected.value).toBe(false)
    handleBatchSelect(true, 7)
    expect(hasSelected.value).toBe(true)
    clearSelection()
    expect(hasSelected.value).toBe(false)
  })
})

describe('useInvoice - 批量操作', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetInvoices.mockResolvedValue({
      data: { list: [], total: 0 },
    })
    mockBatchSubmitInvoices.mockResolvedValue({
      data: { success_count: 2, skipped: [{ id: 3, reason: '当前状态不可提交' }] },
    })
    mockBatchCancelInvoices.mockResolvedValue({ data: { success_count: 1, skipped: [] } })
    mockBatchDeleteInvoices.mockResolvedValue({ data: { success_count: 1, skipped: [] } })
  })

  it('doBatchSubmit 调用 batchSubmitInvoices 并成功后清空选择 + 刷新列表', async () => {
    const { handleBatchSelect, doBatchSubmit, selectedInvoiceIds } = useInvoice()
    handleBatchSelect(true, 1)
    handleBatchSelect(true, 2)
    handleBatchSelect(true, 3)
    await doBatchSubmit()

    expect(mockBatchSubmitInvoices).toHaveBeenCalledWith([1, 2, 3])
    expect(selectedInvoiceIds.value).toEqual([])
    // 列表已刷新
    await vi.waitFor(() => {
      expect(mockGetInvoices).toHaveBeenCalled()
    })
  })

  it('doBatchCancel 调用 batchCancelInvoices', async () => {
    const { handleBatchSelect, doBatchCancel } = useInvoice()
    handleBatchSelect(true, 1)
    await doBatchCancel()
    expect(mockBatchCancelInvoices).toHaveBeenCalledWith([1])
  })

  it('doBatchDelete 调用 batchDeleteInvoices', async () => {
    const { handleBatchSelect, doBatchDelete } = useInvoice()
    handleBatchSelect(true, 1)
    await doBatchDelete()
    expect(mockBatchDeleteInvoices).toHaveBeenCalledWith([1])
  })
})
