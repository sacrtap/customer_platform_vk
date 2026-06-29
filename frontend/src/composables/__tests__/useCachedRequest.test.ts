import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

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

vi.mock('@/stores/user', () => ({
  useUserStore: vi.fn(() => ({
    userInfo: { id: 1 },
  })),
}))

import { useCachedRequest } from '../useCachedRequest'

describe('useCachedRequest', () => {
  beforeEach(() => {
    localStorageMock.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should fetch data and cache it', async () => {
    const mockData = { value: 42 }
    const fetcher = vi.fn().mockResolvedValue(mockData)
    
    const { execute } = useCachedRequest('test', fetcher, 5000)
    const result = await execute()
    
    expect(result).toEqual(mockData)
    expect(fetcher).toHaveBeenCalledTimes(1)
    
    // Second call should use cache
    const result2 = await execute()
    expect(result2).toEqual(mockData)
    expect(fetcher).toHaveBeenCalledTimes(1) // Still 1, not 2
  })
})