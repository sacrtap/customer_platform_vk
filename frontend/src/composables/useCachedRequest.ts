import { useUserStore } from '@/stores/user'

interface CacheEntry<T> {
  data: T
  timestamp: number
}

export function useCachedRequest<T>(key: string, fetcher: () => Promise<T>, ttl: number) {
  const userStore = useUserStore()
  const userId = userStore.userInfo?.id || 'anonymous'
  const cacheKey = `dashboard_${key}_${userId}`

  const getCache = (): T | null => {
    try {
      const raw = localStorage.getItem(cacheKey)
      if (!raw) return null
      const entry: CacheEntry<T> = JSON.parse(raw)
      if (Date.now() - entry.timestamp > ttl) return null
      return entry.data
    } catch (error) {
      console.error('Cache read error:', error)
      localStorage.removeItem(cacheKey)
      return null
    }
  }

  const setCache = (data: T) => {
    try {
      localStorage.setItem(
        cacheKey,
        JSON.stringify({
          data,
          timestamp: Date.now(),
        })
      )
    } catch (error) {
      console.error('Cache write error:', error)
    }
  }

  const getStaleCache = (): T | null => {
    try {
      const raw = localStorage.getItem(cacheKey)
      if (!raw) return null
      const entry: CacheEntry<T> = JSON.parse(raw)
      return entry.data
    } catch {
      return null
    }
  }

  const execute = async (forceRefresh = false): Promise<T> => {
    if (!forceRefresh) {
      const cached = getCache()
      if (cached) return cached
    }

    try {
      const data = await fetcher()
      setCache(data)
      return data
    } catch (error) {
      const staleCache = getStaleCache()
      if (staleCache) {
        console.warn('Using stale cache due to fetch error')
        return staleCache
      }
      throw error
    }
  }

  return { execute }
}
