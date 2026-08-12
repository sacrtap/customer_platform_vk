# State Management

> How state is managed in this project.

---

## Overview

This project uses **Pinia** (Composition API style) for global state and **Vue reactivity** (`ref`, `reactive`, `computed`) for local/page-level state. There is no Vuex. The state strategy is layered:

1. **Global state** → Pinia stores (auth, cross-page cache)
2. **Page state** → Composables (filters, pagination, table data)
3. **Component state** → `ref()` / `reactive()` inside `.vue` files (form data, modal visibility)
4. **Persistence** → `localStorage` (token, user info, UI preferences)

---

## State Categories

| Category | Where it lives | Example | Source |
|----------|---------------|---------|--------|
| Auth state | Pinia store | `token`, `userInfo`, `permissions` | `frontend/src/stores/user.ts` |
| Cross-page cache | Pinia store | Customer data cache with TTL | `frontend/src/stores/customer.ts` |
| Page state | Composable | `filters`, `pagination`, `balances` | `frontend/src/composables/useBalance.ts` |
| Component state | `ref()`/`reactive()` in `.vue` | `editForm`, `modalVisible` | `frontend/src/views/customers/components/CustomerFormModal.vue` |
| URL state | Vue Router | `route.params.id`, `route.query` | `frontend/src/composables/useCustomerDetail.ts:52` |
| Persistence | `localStorage` | `access_token`, `prototype-sidebar-collapsed` | `frontend/src/stores/user.ts:25` |

---

## Pinia Stores

### Store Style: Composition API (Setup Stores)

All stores use the `defineStore('name', () => { ... })` setup syntax — not the options syntax.

[来源: 项目源码 — `frontend/src/stores/user.ts:15-164`]

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  // State
  const token = ref<string>('')
  const userInfo = ref<UserInfo | null>(null)
  const permissions = ref<Set<string>>(new Set())

  // Actions (plain functions)
  function setToken(newToken: string, newRefreshToken: string) {
    token.value = newToken
    localStorage.setItem('access_token', newToken)
    // ...
  }

  function hasPermission(code: string): boolean {
    if (userInfo.value?.roles.includes('超级管理员')) return true
    return permissions.value.has(code)
  }

  // Getters (computed)
  const isSuperAdmin = computed(() =>
    userInfo.value?.roles.includes('超级管理员') ?? false
  )

  return { token, userInfo, permissions, setToken, hasPermission, isSuperAdmin }
})
```

### Store List

| Store | File | Purpose |
|-------|------|---------|
| `useUserStore` | `frontend/src/stores/user.ts` | Auth token, user info, permissions, JWT expiry checks |
| `useCustomerStore` | `frontend/src/stores/customer.ts` | TTL-based cache for customer detail, tags, managers |

### Customer Cache Store Pattern

[来源: 项目源码 — `frontend/src/stores/customer.ts:32-212`]

The customer store implements a multi-tier cache with different TTLs:

```typescript
const CACHE_TTL = 5 * 60 * 1000       // 5 min — customer detail
const TAGS_CACHE_TTL = 10 * 60 * 1000  // 10 min — tags (change infrequently)
const MANAGERS_CACHE_TTL = 15 * 60 * 1000 // 15 min — managers (rarely change)
```

- Cache stored in `Map<number, CachedData>` keyed by customer ID
- `has<Cached>(id)` checks existence + freshness
- `getCached(id)` returns data without TTL check
- `invalidate<Cached>(id)` removes single entry
- `updateCachedCustomerPart(id, key, value)` updates a slice of cached data

---

## When to Use Global State (Pinia)

Use a Pinia store when:

1. **State must persist across page navigations** — e.g., user auth token survives route changes
2. **Multiple pages need the same cached data** — e.g., customer detail data cached for list→detail→back navigation
3. **State is truly global** — e.g., current user permissions checked by every page

**Do NOT use Pinia for:**
- Single-page table data, filters, pagination → use a composable
- Form state inside a modal → use `reactive()` in the component
- Temporary UI state (dropdown open/close) → use `ref()` in the component

---

## Server State

This project does **not** use a server-state library (no React Query, SWR, or VueQuery equivalent). Server data is fetched directly via API calls inside composables.

### Fetch Pattern

[来源: 项目源码 — `frontend/src/composables/useBalance.ts:107-152`]

```typescript
const loadBalances = async (forceRefresh = false) => {
  loading.value = true
  try {
    const params: Record<string, unknown> = { ... }
    if (forceRefresh) params.force_refresh = true
    const res = await getBalances(params)
    balances.value = res.data?.list || []
    pagination.total = res.data?.total || 0
  } catch {
    balances.value = []
  } finally {
    loading.value = false
  }
}
```

### Caching Strategies

| Strategy | Where | TTL | Use case |
|----------|-------|-----|----------|
| Force refresh param | API call | — | User clicks "刷新" button |
| Pinia cache | `useCustomerStore` | 5-15 min | Customer detail page back-navigation |
| localStorage cache | `useCachedRequest` | Configurable | Dashboard analytics data |
| Backend Redis cache | Server-side | 300s | Balance list (transparent to frontend) |

### Stale-While-Revalidate

[来源: 项目源码 — `frontend/src/composables/useCachedRequest.ts:52-70`]

`useCachedRequest` implements stale-while-revalidate: on fetch failure, returns stale cache instead of throwing:

```typescript
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
```

---

## Persistence (localStorage)

| Key | Store | Purpose | Source |
|-----|-------|---------|--------|
| `access_token` | `useUserStore` | JWT access token | `stores/user.ts:25` |
| `refresh_token` | `useUserStore` | JWT refresh token | `stores/user.ts:26` |
| `user_info` | `useUserStore` | Serialized `UserInfo` | `stores/user.ts:30` |
| `user_permissions` | `useUserStore` | Serialized permission array | `stores/user.ts:35` |
| `prototype-sidebar-collapsed` | `useAppLayout` | Sidebar collapse state | `composables/useAppLayout.ts:145` |
| `dashboard_<key>_<userId>` | `useCachedRequest` | Per-user cached data | `composables/useCachedRequest.ts:11` |

**Convention**: localStorage keys are string-scoped with a prefix to avoid collisions. User-scoped keys include `userId`.

---

## Common Mistakes

- ❌ **Creating a Pinia store for page-local state** — use a composable instead
- ❌ **Using `localStorage` directly in components** — wrap in a store or `useCachedRequest`
- ❌ **Forgetting to invalidate cache on mutation** — call `invalidateCustomerCache(id)` after update/delete
- ❌ **Not checking TTL before using cached data** — always use `hasCachedCustomer(id)` before `getCachedCustomer(id)`
- ❌ **Using Options API store syntax** — always use `defineStore('name', () => { ... })` setup syntax
