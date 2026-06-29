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

  // Task 2: Cache expiration test
  it('should refetch when cache expires', async () => {
    vi.useFakeTimers()
    
    const mockData1 = { value: 1 }
    const mockData2 = { value: 2 }
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(mockData1)
      .mockResolvedValueOnce(mockData2)
    
    const { execute } = useCachedRequest('test-expire', fetcher, 5000)
    
    // First call
    const result1 = await execute()
    expect(result1).toEqual(mockData1)
    expect(fetcher).toHaveBeenCalledTimes(1)
    
    // Advance time past TTL
    vi.advanceTimersByTime(6000)
    
    // Second call should refetch
    const result2 = await execute()
    expect(result2).toEqual(mockData2)
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  // Task 2: Force refresh test
  it('should bypass cache when forceRefresh is true', async () => {
    const mockData1 = { value: 1 }
    const mockData2 = { value: 2 }
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(mockData1)
      .mockResolvedValueOnce(mockData2)
    
    const { execute } = useCachedRequest('test-force', fetcher, 5000)
    
    // First call
    await execute()
    expect(fetcher).toHaveBeenCalledTimes(1)
    
    // Force refresh should bypass cache
    const result2 = await execute(true)
    expect(result2).toEqual(mockData2)
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  // Task 3: Stale cache fallback test
  it('should return stale cache when fetch fails', async () => {
    vi.useFakeTimers()
    
    const mockData = { value: 42 }
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(mockData)
      .mockRejectedValueOnce(new Error('Network error'))
    
    const { execute } = useCachedRequest('test-stale', fetcher, 5000)
    
    // First call succeeds
    const result1 = await execute()
    expect(result1).toEqual(mockData)
    
    // Advance time past TTL
    vi.advanceTimersByTime(6000)
    
    // Second call fails but should return stale cache
    const result2 = await execute()
    expect(result2).toEqual(mockData)
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  // Task 3: Error when no cache exists
  it('should throw error when fetch fails and no cache exists', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('Network error'))
    
    const { execute } = useCachedRequest('test-error', fetcher, 5000)
    
    await expect(execute()).rejects.toThrow('Network error')
  })
})