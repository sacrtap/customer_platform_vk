import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useCustomerDetail } from '../useCustomerDetail'

vi.mock('@/stores/customer', () => ({
  useCustomerStore: vi.fn(() => ({
    updateCachedCustomerPart: vi.fn(),
    getCachedTags: vi.fn(() => null),
    hasCachedTags: vi.fn(() => false),
    cacheTagsData: vi.fn(),
  })),
}))

const mockPush = vi.fn()
const mockBack = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: vi.fn(() => ({ params: { id: '1' } })),
  useRouter: vi.fn(() => ({ push: mockPush, back: mockBack })),
}))

vi.mock('@arco-design/web-vue', () => ({
  Message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@/api/customers', () => ({
  getCustomer: vi.fn(() => Promise.resolve({ data: { id: 1, name: 'test' } })),
  updateCustomer: vi.fn(() => Promise.resolve({ data: { id: 1, name: 'updated' } })),
  getProfile: vi.fn(() => Promise.resolve({ data: { scale_level: 'high' } })),
  updateProfile: vi.fn(() => Promise.resolve({ data: { scale_level: 'high' } })),
  getIndustryTypes: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('@/api/billing', () => ({
  getCustomerBalance: vi.fn(() => Promise.resolve({ data: { total_amount: 100 } })),
  getInvoices: vi.fn(() => Promise.resolve({ data: [{ id: 1 }] })),
  getBalanceTrend: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('@/api/tags', () => ({
  getTags: vi.fn(() => Promise.resolve({ data: [] })),
  getCustomerTags: vi.fn(() => Promise.resolve({ data: [] })),
  addCustomerTag: vi.fn(() => Promise.resolve()),
  removeCustomerTag: vi.fn(() => Promise.resolve()),
}))

vi.mock('@/api/usage', () => ({
  getDailyUsage: vi.fn(() => Promise.resolve({ data: [{ id: 1 }] })),
}))

vi.mock('@/api/users', () => ({
  getManagers: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('@/api/analytics', () => ({
  getCustomerHealthScore: vi.fn(() => Promise.resolve({ data: null })),
}))

describe('useCustomerDetail', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('initial state has null detail and default tab', () => {
    const { detail, activeTab, loading } = useCustomerDetail()
    expect(detail.value).toBeNull()
    expect(activeTab.value).toBe('basic')
    expect(loading.value).toBe(false)
  })

  it('loadDetail fetches and sets detail on mount', async () => {
    const { detail, loadDetail } = useCustomerDetail()
    await loadDetail()
    expect(detail.value).toEqual(expect.objectContaining({ id: 1, name: 'test' }))
  })

  it('handleTabChange updates activeTab', () => {
    const { handleTabChange, activeTab } = useCustomerDetail()
    handleTabChange('profile')
    expect(activeTab.value).toBe('profile')
  })

  it('openEdit sets editModalVisible true', () => {
    const { editModalVisible, openEdit } = useCustomerDetail()
    openEdit()
    expect(editModalVisible.value).toBe(true)
  })

  it('closeEdit sets editModalVisible false', () => {
    const { editModalVisible, closeEdit } = useCustomerDetail()
    editModalVisible.value = true
    closeEdit()
    expect(editModalVisible.value).toBe(false)
  })
})
