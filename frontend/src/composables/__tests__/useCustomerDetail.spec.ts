import type { CustomerProfile } from '@/types'
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
    const { customer, activeTab, loading } = useCustomerDetail()
    expect(customer.value).toBeNull()
    expect(activeTab.value).toBe('basic')
    expect(loading.value).toBe(false)
  })

  it('loadDetail fetches and sets detail on mount', async () => {
    const { customer, loadDetail } = useCustomerDetail()
    await loadDetail()
    expect(customer.value).toEqual(expect.objectContaining({ id: 1, name: 'test' }))
  })

  it('handleTabChange updates activeTab', () => {
    const { handleTabChange, activeTab } = useCustomerDetail()
    handleTabChange('profile')
    expect(activeTab.value).toBe('profile')
  })

  it('openEdit sets editModalVisible true', async () => {
    const { editModalVisible, profile, openEdit } = useCustomerDetail()
    profile.value = {
      id: 1, customer_id: 1, scale_level: 'high', consume_level: null,
      industry_type_id: null, is_real_estate: false, description: null,
      created_at: '', updated_at: '',
      monthly_avg_shots: null, monthly_avg_shots_estimated: null,
      estimated_annual_spend: null, actual_annual_spend_2025: null,
      industry: undefined,
    } as CustomerProfile
    openEdit()
    expect(editModalVisible.value).toBe(true)
  })

  it('closeEdit sets editModalVisible false', () => {
    const { editModalVisible, closeEdit } = useCustomerDetail()
    editModalVisible.value = true
    closeEdit()
    expect(editModalVisible.value).toBe(false)
  })

  it('balance starts as undefined to prevent render crash', () => {
    const { balance, customer, profile } = useCustomerDetail()
    // 关键：初始值为 null/undefined，模板必须用 v-if 守卫
    expect(balance.value).toBeUndefined()
    expect(customer.value).toBeNull()
    expect(profile.value).toBeNull()
  })

  it('loadBalance sets balance data', async () => {
    const { balance, loadBalance } = useCustomerDetail()
    expect(balance.value).toBeUndefined()
    await loadBalance()
    expect(balance.value).toBeDefined()
    expect(balance.value?.total_amount).toBe(100)
  })

  it('loading transitions correctly during loadDetail', async () => {
    const { loading, customer, loadDetail } = useCustomerDetail()
    expect(loading.value).toBe(false)
    const promise = loadDetail()
    expect(loading.value).toBe(true)
    await promise
    expect(loading.value).toBe(false)
    expect(customer.value).toBeTruthy()
  })


  it('initial loading is false before any data fetch', () => {
    const { loading } = useCustomerDetail()
    expect(loading.value).toBe(false)
  })

})