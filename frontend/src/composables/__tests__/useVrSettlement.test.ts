import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useVrSettlement } from '../useVrSettlement'

// Mock API modules
const mockGetVrSettlements = vi.fn()
const mockSubmitVrSettlement = vi.fn()
const mockConfirmCsSupervisor = vi.fn()
const mockConfirmSales = vi.fn()
const mockConfirmSalesSupervisor = vi.fn()
const mockRejectSalesSupervisor = vi.fn()
const mockApplyVrDiscount = vi.fn()
const mockConfirmVrSettlement = vi.fn()
const mockRetryVrDeduction = vi.fn()
const mockCancelVrSettlement = vi.fn()
const mockDeleteVrSettlement = vi.fn()
const mockCreateVrSettlement = vi.fn()
const mockGetVrSettlement = vi.fn()

vi.mock('@/api/vrSettlement', () => ({
  getVrSettlements: (...args: unknown[]) => mockGetVrSettlements(...args),
  getVrSettlement: (...args: unknown[]) => mockGetVrSettlement(...args),
  createVrSettlement: (...args: unknown[]) => mockCreateVrSettlement(...args),
  submitVrSettlement: (...args: unknown[]) => mockSubmitVrSettlement(...args),
  confirmCsSupervisor: (...args: unknown[]) => mockConfirmCsSupervisor(...args),
  confirmSales: (...args: unknown[]) => mockConfirmSales(...args),
  confirmSalesSupervisor: (...args: unknown[]) => mockConfirmSalesSupervisor(...args),
  rejectSalesSupervisor: (...args: unknown[]) => mockRejectSalesSupervisor(...args),
  applyVrDiscount: (...args: unknown[]) => mockApplyVrDiscount(...args),
  confirmVrSettlement: (...args: unknown[]) => mockConfirmVrSettlement(...args),
  retryVrDeduction: (...args: unknown[]) => mockRetryVrDeduction(...args),
  cancelVrSettlement: (...args: unknown[]) => mockCancelVrSettlement(...args),
  deleteVrSettlement: (...args: unknown[]) => mockDeleteVrSettlement(...args),
  uploadDiscountAttachment: vi.fn(),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

describe('useVrSettlement - 排序逻辑', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetVrSettlements.mockResolvedValue({
      data: { list: [], total: 0 },
    })
  })

  it('初始状态下 sort_by 为空，sort_order 为空', () => {
    const { sortState } = useVrSettlement()
    expect(sortState.sort_by).toBe('')
    expect(sortState.sort_order).toBe('')
  })

  it('handleSortChange 设置升序时，API 收到 sort_by 和 sort_order=asc', async () => {
    const { handleSortChange } = useVrSettlement()
    handleSortChange('total_amount', 'asc')
    await vi.waitFor(() => {
      expect(mockGetVrSettlements).toHaveBeenCalled()
    })
    const callArgs = mockGetVrSettlements.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('total_amount')
    expect(callArgs.sort_order).toBe('asc')
  })

  it('handleSortChange 设置降序时，API 收到 sort_order=desc', async () => {
    const { handleSortChange } = useVrSettlement()
    handleSortChange('settlement_no', 'desc')
    await vi.waitFor(() => {
      expect(mockGetVrSettlements).toHaveBeenCalled()
    })
    const callArgs = mockGetVrSettlements.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBe('settlement_no')
    expect(callArgs.sort_order).toBe('desc')
  })

  it('handleSortChange 兼容 arco 回调词表 ascend/descend', async () => {
    const { handleSortChange } = useVrSettlement()
    handleSortChange('total_amount', 'ascend')
    await vi.waitFor(() => {
      expect(mockGetVrSettlements).toHaveBeenCalled()
    })
    const callArgs = mockGetVrSettlements.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_order).toBe('asc')
  })

  it('handleSortChange 清除排序时（空字符串），API 不发送 sort_by 和 sort_order', async () => {
    const { handleSortChange } = useVrSettlement()
    handleSortChange('', '')
    await vi.waitFor(() => {
      expect(mockGetVrSettlements).toHaveBeenCalled()
    })
    const callArgs = mockGetVrSettlements.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.sort_by).toBeUndefined()
    expect(callArgs.sort_order).toBeUndefined()
  })
})

describe('useVrSettlement - 筛选与分页', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetVrSettlements.mockResolvedValue({
      data: { list: [], total: 0 },
    })
  })

  it('loadVrSettlements 透传筛选参数', async () => {
    const { filters, loadVrSettlements } = useVrSettlement()
    filters.keyword = 'VR-2026'
    filters.status = 'draft'
    filters.customer_id = 7
    await loadVrSettlements()
    const callArgs = mockGetVrSettlements.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.keyword).toBe('VR-2026')
    expect(callArgs.status).toBe('draft')
    expect(callArgs.customer_id).toBe(7)
  })

  it('handleSearch 重置分页到第一页', async () => {
    const { handleSearch, pagination } = useVrSettlement()
    pagination.current = 3
    handleSearch()
    expect(pagination.current).toBe(1)
    await vi.waitFor(() => {
      expect(mockGetVrSettlements).toHaveBeenCalled()
    })
    const callArgs = mockGetVrSettlements.mock.calls[0][0] as Record<string, unknown>
    expect(callArgs.page).toBe(1)
  })

  it('handleReset 清空筛选并重置分页', async () => {
    const { handleReset, filters, pagination } = useVrSettlement()
    filters.keyword = 'x'
    filters.status = 'draft'
    filters.customer_id = 7
    pagination.current = 2
    handleReset()
    expect(filters.keyword).toBe('')
    expect(filters.status).toBe('')
    expect(filters.customer_id).toBeNull()
    expect(pagination.current).toBe(1)
  })

  it('handlePageSizeChange 切换页大小并回到第一页', async () => {
    const { handlePageSizeChange, pagination } = useVrSettlement()
    pagination.current = 5
    handlePageSizeChange(50)
    expect(pagination.pageSize).toBe(50)
    expect(pagination.current).toBe(1)
  })
})

describe('useVrSettlement - 动作方法', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetVrSettlements.mockResolvedValue({
      data: { list: [], total: 0 },
    })
  })

  it('doSubmit 调用 submitVrSettlement', async () => {
    mockSubmitVrSettlement.mockResolvedValue({ data: {} })
    const { doSubmit } = useVrSettlement()
    await doSubmit(11)
    expect(mockSubmitVrSettlement).toHaveBeenCalledWith(11)
  })

  it('doConfirmCs 调用 confirmCsSupervisor', async () => {
    mockConfirmCsSupervisor.mockResolvedValue({ data: {} })
    const { doConfirmCs } = useVrSettlement()
    await doConfirmCs(12)
    expect(mockConfirmCsSupervisor).toHaveBeenCalledWith(12)
  })

  it('doConfirmSales 调用 confirmSales', async () => {
    mockConfirmSales.mockResolvedValue({ data: {} })
    const { doConfirmSales } = useVrSettlement()
    await doConfirmSales(13)
    expect(mockConfirmSales).toHaveBeenCalledWith(13)
  })

  it('doConfirmSalesSupervisor 透传 comment', async () => {
    mockConfirmSalesSupervisor.mockResolvedValue({ data: {} })
    const { doConfirmSalesSupervisor } = useVrSettlement()
    await doConfirmSalesSupervisor(14, '同意')
    expect(mockConfirmSalesSupervisor).toHaveBeenCalledWith(14, '同意')
  })

  it('doRejectSalesSupervisor 透传驳回理由', async () => {
    mockRejectSalesSupervisor.mockResolvedValue({ data: {} })
    const { doRejectSalesSupervisor } = useVrSettlement()
    await doRejectSalesSupervisor(15, '金额有误')
    expect(mockRejectSalesSupervisor).toHaveBeenCalledWith(15, '金额有误')
  })

  it('doApplyDiscount 透传减免数据', async () => {
    mockApplyVrDiscount.mockResolvedValue({ data: {} })
    const { doApplyDiscount } = useVrSettlement()
    await doApplyDiscount(16, { discount_amount: 100, discount_reason: '优惠' })
    expect(mockApplyVrDiscount).toHaveBeenCalledWith(16, {
      discount_amount: 100,
      discount_reason: '优惠',
    })
  })

  it('doConfirm 调用 confirmVrSettlement', async () => {
    mockConfirmVrSettlement.mockResolvedValue({ data: {} })
    const { doConfirm } = useVrSettlement()
    await doConfirm(17)
    expect(mockConfirmVrSettlement).toHaveBeenCalledWith(17)
  })

  it('doRetryDeduction 调用 retryVrDeduction', async () => {
    mockRetryVrDeduction.mockResolvedValue({ data: { message: '重试扣款成功' } })
    const { doRetryDeduction } = useVrSettlement()
    await doRetryDeduction(18)
    expect(mockRetryVrDeduction).toHaveBeenCalledWith(18)
  })

  it('doCancel 调用 cancelVrSettlement', async () => {
    mockCancelVrSettlement.mockResolvedValue({ data: {} })
    const { doCancel } = useVrSettlement()
    await doCancel(19)
    expect(mockCancelVrSettlement).toHaveBeenCalledWith(19)
  })

  it('doDelete 调用 deleteVrSettlement', async () => {
    mockDeleteVrSettlement.mockResolvedValue({ data: {} })
    const { doDelete } = useVrSettlement()
    await doDelete(20)
    expect(mockDeleteVrSettlement).toHaveBeenCalledWith(20)
  })

  it('doCreate 透传创建参数', async () => {
    mockCreateVrSettlement.mockResolvedValue({ data: {} })
    const { doCreate } = useVrSettlement()
    await doCreate({
      customer_id: 1,
      period_start: '2026-11-01',
      period_end: '2026-11-30',
      total_amount: 500,
      detail_file_path: '/uploads/a.xlsx',
      detail_file_name: 'a.xlsx',
    })
    expect(mockCreateVrSettlement).toHaveBeenCalledWith({
      customer_id: 1,
      period_start: '2026-11-01',
      period_end: '2026-11-30',
      total_amount: 500,
      detail_file_path: '/uploads/a.xlsx',
      detail_file_name: 'a.xlsx',
    })
  })

  it('动作失败时 re-throw 供调用方感知', async () => {
    mockSubmitVrSettlement.mockRejectedValue(new Error('提交失败'))
    const { doSubmit } = useVrSettlement()
    await expect(doSubmit(21)).rejects.toThrow('提交失败')
  })
})

describe('useVrSettlement - 多选', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetVrSettlements.mockResolvedValue({
      data: { list: [], total: 0 },
    })
  })

  it('handleBatchSelect 增删选中 id', () => {
    const { handleBatchSelect, selectedIds, hasSelected } = useVrSettlement()
    handleBatchSelect(true, 1)
    handleBatchSelect(true, 2)
    expect(selectedIds.value).toEqual([1, 2])
    expect(hasSelected.value).toBe(true)
    handleBatchSelect(false, 1)
    expect(selectedIds.value).toEqual([2])
  })

  it('handleBatchSelectAll 跨页保留选中', () => {
    const { handleBatchSelectAll, selectedIds } = useVrSettlement()
    handleBatchSelectAll(true, [{ id: 1 }, { id: 2 }] as never)
    expect(selectedIds.value).toEqual([1, 2])
    // 取消当前页全选只移除当前页 id
    handleBatchSelectAll(false, [{ id: 1 }] as never)
    expect(selectedIds.value).toEqual([2])
  })

  it('clearSelection 清空选中', () => {
    const { handleBatchSelect, clearSelection, selectedIds } = useVrSettlement()
    handleBatchSelect(true, 1)
    clearSelection()
    expect(selectedIds.value).toEqual([])
  })
})
