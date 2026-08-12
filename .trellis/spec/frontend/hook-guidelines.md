# Hook Guidelines

> How composables are used in this project.

---

## Overview

This project uses Vue 3 **Composables** (`use<Domain>.ts`) to extract page-level logic from `.vue` components. Composables live in `frontend/src/composables/` and encapsulate state management, API calls, filters, pagination, and user action handlers for a specific page or feature.

**No React-style hooks** — this is a Vue 3 project. Composables are Vue Composition API functions that return reactive state and methods.

---

## Composable Categories

### 1. Page-Level Composables (most common)

Encapsulate all state and actions for a single page view. The `.vue` component becomes a thin wrapper that destructures the composable's return value.

[来源: 项目源码 — `frontend/src/composables/useBalance.ts`, `frontend/src/composables/useCustomerList.ts`]

### 2. App-Level Composables (singleton pattern)

Module-level state shared across components, initialized only once.

[来源: 项目源码 — `frontend/src/composables/useAppLayout.ts`]

### 3. Utility Composables (generic, reusable)

Generic logic not tied to a specific domain.

[来源: 项目源码 — `frontend/src/composables/useCachedRequest.ts`]

---

## Standard Page-Level Composable Pattern

[来源: 项目源码 — `frontend/src/composables/useCustomerList.ts:15-369`]

```typescript
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Modal } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import { handleError } from '@/utils/errorHandler'
import { getCustomers, deleteCustomer } from '@/api/customers'
import type { Customer } from '@/types'

export function useCustomerList() {
  const router = useRouter()
  const userStore = useUserStore()
  const can = (permission: string) => userStore.hasPermission(permission)

  // 1. Filter state — factory function for defaults
  const createDefaultFilters = () => ({
    keyword: '',
    account_type: '正式账号',
    industry: ['房产经纪', '房产ERP', '房产平台'] as string[],
    // ...
  })
  const filters = reactive(createDefaultFilters())

  // 2. Table state
  const loading = ref(false)
  const customers = ref<Customer[]>([])
  const pagination = reactive({
    current: 1,
    pageSize: 20,
    total: 0,
    showTotal: true,
    showPageSize: true,
    pageSizeOptions: [10, 20, 50, 100],
  })

  // 3. Selection state
  const selectedIds = ref<number[]>([])
  const hasSelected = computed(() => selectedIds.value.length > 0)

  // 4. Build params — central function for API call params
  const buildParams = (): Record<string, unknown> => { ... }

  // 5. Load methods — load<Domain>
  const loadCustomers = async (forceRefresh = false) => {
    loading.value = true
    try {
      const params = buildParams(forceRefresh)
      const res = await getCustomers(params)
      customers.value = res.data.list || []
      pagination.total = res.data.total || 0
    } catch (error: unknown) {
      handleError(error, '加载客户列表失败')
    } finally {
      loading.value = false
    }
  }

  // 6. Handler methods — handle<Action>
  const handleSearch = () => {
    pagination.current = 1
    loadCustomers()
  }
  const handleReset = () => {
    Object.assign(filters, createDefaultFilters())
    pagination.current = 1
    loadCustomers()
  }
  const handlePageChange = (page: number) => {
    pagination.current = page
    loadCustomers()
  }

  // 7. Lifecycle
  onMounted(() => {
    loadCustomers()
  })

  // 8. Return — plain object with refs, reactives, computed, and methods
  return {
    can,
    filters,
    loading,
    customers,
    pagination,
    selectedIds,
    hasSelected,
    loadCustomers,
    handleSearch,
    handleReset,
    handlePageChange,
    // ...
  }
}
```

---

## Key Conventions

### Naming

| Pattern | Convention | Examples |
|---------|-----------|---------|
| File name | `use<Domain>.ts` | `useBalance.ts`, `useInvoice.ts` |
| Function name | `use<Domain>()` | `useBalance()`, `useCustomerDetail()` |
| Load methods | `load<Entity>` | `loadBalances`, `loadCustomers`, `loadInvoices` |
| Action handlers | `handle<Action>` | `handleSearch`, `handleReset`, `handlePageChange`, `handleSort` |
| Mutations | `do<Action>` | `doRecharge`, `doGenerate`, `doPay`, `doCancel` |
| Filter defaults | factory function | `defaultFilters()`, `createDefaultFilters()` |

### State Management Inside Composables

- Use `ref()` for primitive values and arrays: `loading`, `balances`, `selectedIds`
- Use `reactive()` for objects with multiple fields: `filters`, `pagination`, `stats`, `sortState`
- Use `computed()` for derived state: `hasSelected`, `modalWidth`
- Reset reactive objects with `Object.assign(filters, defaultFilters())` — never reassign

### Error Handling

- Use `handleError(error, 'fallback message')` from `@/utils/errorHandler` for user-facing errors
- Use `Message.success('操作成功')` for success feedback
- For non-critical failures (e.g., stats loading), use `catch {}` with silent fallback
- Always use `finally { loading.value = false }` to reset loading state

### Lifecycle Hooks

- `onMounted()` is called inside the composable — not in the `.vue` component
- `onUnmounted()` is used for cleanup (timers, etc.)
- `watch()` can be used for reactive side effects

### API Calls

- Import typed API functions from `@/api/<module>`
- Build params with a `buildParams()` helper for consistency
- Use `Promise.all()` or `Promise.allSettled()` for parallel requests
- Use `.catch(() => null)` for optional parallel requests in `Promise.all()`

---

## Singleton Pattern (App-Level)

[来源: 项目源码 — `frontend/src/composables/useAppLayout.ts:7-11`]

```typescript
// Module-level state — persists across all components using this composable
const sidebarCollapsed = ref(false)
const expandedSubmenu = ref<string | null>(null)
let initialized = false

export function useAppLayout() {
  // ...
  if (!initialized) {
    initialized = true
    watch(() => route.path, (newPath) => { ... }, { immediate: true })
    onMounted(() => { ... })
  }
  return { sidebarCollapsed, /* ... */ }
}
```

**When to use**: Layout state, navigation, app-wide UI state shared across multiple components without a Pinia store.

---

## Generic Composable Pattern

[来源: 项目源码 — `frontend/src/composables/useCachedRequest.ts:8-73`]

```typescript
export function useCachedRequest<T>(key: string, fetcher: () => Promise<T>, ttl: number) {
  // Generic typed cache entry
  const getCache = (): T | null => { ... }
  const setCache = (data: T) => { ... }
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
      if (staleCache) return staleCache  // graceful degradation
      throw error
    }
  }
  return { execute }
}
```

---

## Common Mistakes

- ❌ **Putting business logic in `.vue` components** — extract to a composable when the component exceeds ~200 lines of `<script>`
- ❌ **Reassigning reactive objects** — use `Object.assign()` to reset, not `filters = defaultFilters()`
- ❌ **Forgetting to reset `loading` in `finally`** — always use try/catch/finally
- ❌ **Calling `onMounted()` in the component instead of the composable** — lifecycle hooks belong in the composable
- ❌ **Not using factory functions for filter defaults** — `defaultFilters()` ensures clean reset
