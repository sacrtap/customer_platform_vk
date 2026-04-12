import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Customer, CustomerProfile, Balance } from '@/types'
import type { Invoice, BalanceTrendItem } from '@/api/billing'
import type { CustomerHealthScore } from '@/api/analytics'

interface CachedCustomerData {
  customer: Customer
  profile: CustomerProfile
  balance: Balance
  invoices: Invoice[]
  healthScore: CustomerHealthScore | null
  balanceTrend: BalanceTrendItem[]
  timestamp: number
}

interface Tag {
  id: number
  name: string
  type: string
  category?: string
}

interface CachedTagsData {
  customerTags: Tag[]
  allTags: Tag[]
  timestamp: number
}

interface CachedManagersData {
  managers: Array<{ id: number; username: string; real_name?: string }>
  timestamp: number
}

const CACHE_TTL = 5 * 60 * 1000 // 5 minutes
const TAGS_CACHE_TTL = 10 * 60 * 1000 // 10 minutes (tags change infrequently)
const MANAGERS_CACHE_TTL = 15 * 60 * 1000 // 15 minutes (managers rarely change)

export const useCustomerStore = defineStore('customer', () => {
  // Cache storage
  const customerCache = ref<Map<number, CachedCustomerData>>(new Map())
  const tagsCache = ref<Map<number, CachedTagsData>>(new Map())
  const managersCache = ref<CachedManagersData | null>(null)

  // Loading states for individual customers
  const loadingCustomers = ref<Set<number>>(new Set())

  /**
   * Check if customer data is cached and fresh
   */
  function hasCachedCustomer(customerId: number): boolean {
    const cached = customerCache.value.get(customerId)
    if (!cached) return false
    return Date.now() - cached.timestamp < CACHE_TTL
  }

  /**
   * Get cached customer data
   */
  function getCachedCustomer(customerId: number): CachedCustomerData | undefined {
    return customerCache.value.get(customerId)
  }

  /**
   * Cache customer data
   */
  function cacheCustomerData(
    customerId: number,
    data: Omit<CachedCustomerData, 'timestamp'>
  ): void {
    customerCache.value.set(customerId, {
      ...data,
      timestamp: Date.now(),
    })
  }

  /**
   * Update specific part of cached customer data
   */
  function updateCachedCustomerPart<T extends keyof Omit<CachedCustomerData, 'timestamp'>>(
    customerId: number,
    key: T,
    value: CachedCustomerData[T]
  ): void {
    const cached = customerCache.value.get(customerId)
    if (cached) {
      cached[key] = value
      cached.timestamp = Date.now()
    }
  }

  /**
   * Invalidate customer cache
   */
  function invalidateCustomerCache(customerId: number): void {
    customerCache.value.delete(customerId)
  }

  /**
   * Clear all cached data
   */
  function clearAllCache(): void {
    customerCache.value.clear()
    tagsCache.value.clear()
    managersCache.value = null
  }

  // ========== Tags Cache ==========

  /**
   * Check if tags data is cached and fresh for a customer
   */
  function hasCachedTags(customerId: number): boolean {
    const cached = tagsCache.value.get(customerId)
    if (!cached) return false
    return Date.now() - cached.timestamp < TAGS_CACHE_TTL
  }

  /**
   * Get cached tags data for a customer
   */
  function getCachedTags(customerId: number): CachedTagsData | undefined {
    return tagsCache.value.get(customerId)
  }

  /**
   * Cache tags data for a customer
   */
  function cacheTagsData(
    customerId: number,
    data: { customerTags: Tag[]; allTags: Tag[] }
  ): void {
    tagsCache.value.set(customerId, {
      ...data,
      timestamp: Date.now(),
    })
  }

  /**
   * Invalidate tags cache for a customer
   */
  function invalidateTagsCache(customerId: number): void {
    tagsCache.value.delete(customerId)
  }

  // ========== Managers Cache ==========

  /**
   * Check if managers data is cached and fresh
   */
  function hasCachedManagers(): boolean {
    if (!managersCache.value) return false
    return Date.now() - managersCache.value.timestamp < MANAGERS_CACHE_TTL
  }

  /**
   * Get cached managers data
   */
  function getCachedManagers(): Array<{ id: number; username: string; real_name?: string }> | null {
    return managersCache.value?.managers ?? null
  }

  /**
   * Cache managers data
   */
  function cacheManagersData(
    managers: Array<{ id: number; username: string; real_name?: string }>
  ): void {
    managersCache.value = {
      managers,
      timestamp: Date.now(),
    }
  }

  /**
   * Invalidate managers cache
   */
  function invalidateManagersCache(): void {
    managersCache.value = null
  }

  /**
   * Mark customer as loading
   */
  function setLoading(customerId: number, loading: boolean): void {
    if (loading) {
      loadingCustomers.value.add(customerId)
    } else {
      loadingCustomers.value.delete(customerId)
    }
  }

  /**
   * Check if customer is currently loading
   */
  function isLoading(customerId: number): boolean {
    return loadingCustomers.value.has(customerId)
  }

  return {
    customerCache,
    tagsCache,
    managersCache,
    loadingCustomers,
    hasCachedCustomer,
    getCachedCustomer,
    cacheCustomerData,
    updateCachedCustomerPart,
    invalidateCustomerCache,
    clearAllCache,
    setLoading,
    isLoading,
    // Tags cache
    hasCachedTags,
    getCachedTags,
    cacheTagsData,
    invalidateTagsCache,
    // Managers cache
    hasCachedManagers,
    getCachedManagers,
    cacheManagersData,
    invalidateManagersCache,
  }
})
