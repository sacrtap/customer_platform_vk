import { describe, it, expect, beforeEach, vi } from 'vitest'

// useCustomerList registers onMounted, which requires an active component
// instance when the composable is called directly in tests.
vi.mock('vue', async () => {
  const actual = await vi.importActual<typeof import('vue')>('vue')
  return {
    ...actual,
    onMounted: vi.fn(),
  }
})

import { useCustomerList } from '../useCustomerList'

const mockExportCustomers = vi.fn()
const mockGetCustomers = vi.fn()

vi.mock('@/api/customers', () => ({
  getCustomers: (...args: unknown[]) => mockGetCustomers(...args),
  deleteCustomer: vi.fn(),
  exportCustomers: (...args: unknown[]) => mockExportCustomers(...args),
  getIndustryTypes: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('@/api/tags', () => ({
  getTags: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('@/api/users', () => ({
  getManagers: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('@/api/erpSystems', () => ({
  getErpSystemsList: vi.fn(() => Promise.resolve({ data: { data: [] } })),
}))

vi.mock('@/api/cooperationStatuses', () => ({
  getCooperationStatusesList: vi.fn(() => Promise.resolve({ data: { data: [] } })),
}))

vi.mock('vue-router', () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}))

vi.mock('@/stores/user', () => ({
  useUserStore: vi.fn(() => ({ hasPermission: vi.fn(() => true) })),
}))

vi.mock('@/stores/customer', () => ({
  useCustomerStore: vi.fn(() => ({
    hasCachedManagers: vi.fn(() => true),
    getCachedManagers: vi.fn(() => []),
    cacheManagersData: vi.fn(),
  })),
}))

vi.mock('@/utils/errorHandler', () => ({
  handleError: vi.fn(),
}))

// 阻止 jsdom 中 createObjectURL 缺失导致的报错
vi.stubGlobal('URL', {
  ...URL,
  createObjectURL: vi.fn(() => 'blob:mock'),
  revokeObjectURL: vi.fn(),
})

// 导出成功后代码会创建 <a download> 并 click() 触发浏览器下载，
// jsdom 未实现 navigation 会刷未捕获错误，这里屏蔽链接点击副作用。
const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

describe('useCustomerList - 导出状态', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    clickSpy.mockImplementation(() => {})
    mockGetCustomers.mockResolvedValue({ data: { list: [], total: 0 } })
  })

  it('导出期间 exporting 为 true，结束后复位', async () => {
    mockExportCustomers.mockResolvedValue({ data: new Blob(['x']) })

    const { exporting, handleExport } = useCustomerList()
    expect(exporting.value).toBe(false)

    // exporting 在首个 await（请求发出）前置位，故同步即可观察到「导出中」
    const promise = handleExport()
    expect(exporting.value).toBe(true)

    await promise
    expect(exporting.value).toBe(false)
  })

  it('导出失败后 exporting 仍复位', async () => {
    mockExportCustomers.mockRejectedValue(new Error('network'))

    const { exporting, handleExport } = useCustomerList()
    expect(exporting.value).toBe(false)

    await handleExport()

    expect(exporting.value).toBe(false)
    expect(mockExportCustomers).toHaveBeenCalledTimes(1)
  })
})
