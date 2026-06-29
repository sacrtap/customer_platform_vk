import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// Mock echarts before importing Home
vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
  })),
  graphic: {
    LinearGradient: vi.fn(),
  },
}))

// Mock API calls
vi.mock('@/api/analytics', () => ({
  getDashboardStats: vi.fn().mockResolvedValue({
    data: {
      total_customers: 100,
      key_customers: 20,
      total_balance: 1000000,
      real_balance: 800000,
      bonus_balance: 200000,
      month_invoice_count: 50,
      pending_confirmation: 5,
      month_consumption: 500000,
    },
  }),
  getDashboardChartData: vi.fn().mockResolvedValue({
    data: {
      consumption_trend: [
        { period: '2024-01', total_amount: 100000 },
        { period: '2024-02', total_amount: 120000 },
      ],
    },
  }),
  getPendingTasks: vi.fn().mockResolvedValue({
    tasks: [
      {
        id: 1,
        title: 'Test task',
        type: 'warning',
        created_at: '2024-01-01',
      },
    ],
  }),
}))

vi.mock('@/api/billing', () => ({
  getRecentInvoices: vi.fn().mockResolvedValue({
    data: {
      list: [
        {
          id: 1,
          invoice_no: 'INV-001',
          period_start: '2024-01-01',
          period_end: '2024-01-31',
          total_amount: 50000,
          status: 'paid',
          created_at: '2024-01-01',
        },
      ],
    },
  }),
}))

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    }),
  }
})()

vi.stubGlobal('localStorage', localStorageMock)

// Mock useUserStore
vi.mock('@/stores/user', () => ({
  useUserStore: vi.fn(() => ({
    userInfo: { id: 1 },
  })),
}))

import Home from '../Home.vue'

interface HomeVM {
  statsLoading: boolean
  chartLoading: boolean
  todosLoading: boolean
  invoicesLoading: boolean
  stats: { totalCustomers: number }
  todos: unknown[]
  invoices: unknown[]
}

describe('Home.vue', () => {
  beforeEach(() => {
    localStorageMock.clear()
    vi.clearAllMocks()
  })

  it('should load all data in parallel on mount', async () => {
    const wrapper = mount(Home)
    const vm = wrapper.vm as unknown as HomeVM

    // Wait for all async operations
    await vi.waitFor(() => {
      expect(vm.statsLoading).toBe(false)
      expect(vm.chartLoading).toBe(false)
      expect(vm.todosLoading).toBe(false)
      expect(vm.invoicesLoading).toBe(false)
    })

    // Verify data was loaded
    expect(vm.stats.totalCustomers).toBe(100)
    expect(vm.todos).toHaveLength(1)
    expect(vm.invoices).toHaveLength(1)
  })

  it('should use cache on subsequent loads', async () => {
    // First mount
    const wrapper1 = mount(Home)
    const vm1 = wrapper1.vm as unknown as HomeVM
    await vi.waitFor(() => {
      expect(vm1.statsLoading).toBe(false)
    })

    // Second mount should use cache
    const wrapper2 = mount(Home)
    const vm2 = wrapper2.vm as unknown as HomeVM
    await vi.waitFor(() => {
      expect(vm2.statsLoading).toBe(false)
    })

    // Verify data was loaded
    expect(vm2.stats.totalCustomers).toBe(100)
  })
})
