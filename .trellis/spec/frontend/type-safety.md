# Type Safety

> Type safety patterns in this project.

---

## Overview

The frontend uses **TypeScript in strict mode**. All components use `<script setup lang="ts">`, and type definitions are shared across the app via a centralized types file and co-located API types.

---

## Type Organization

### 1. Shared Domain Types — `src/types/index.ts`

Central location for domain models used across multiple modules.

[来源: 项目源码 — `frontend/src/types/index.ts`]

```typescript
/** API 响应格式 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
  meta?: { page: number; page_size: number; total: number }
}

/** 分页响应 */
export interface PaginatedResponse<T> {
  list: T[]
  total: number
}

/** 客户 */
export interface Customer {
  id: number
  company_id: number
  name: string
  account_type: string | null
  // ...
}
```

**What goes here**: Core domain entities (`Customer`, `User`, `Tag`, `Balance`, `Invoice`, `PricingRule`, etc.), API envelope types (`ApiResponse<T>`, `PaginatedResponse<T>`), and shared enums (`PricePolicy`).

### 2. Co-located API Types — `src/api/<module>.ts`

Types specific to a single API module live alongside the API functions.

[来源: 项目源码 — `frontend/src/api/billing.ts:5-27`]

```typescript
// In frontend/src/api/billing.ts
export interface Balance {
  id: number
  customer_id: number
  total_amount: number
  daily_avg_cost: number | null    // API-specific field
  days_remaining: number | null     // API-specific field
  // ...
}

export interface RechargeParams {
  customer_id: number
  real_amount: number
  bonus_amount?: number
  remark?: string
}
```

**What goes here**: API request param interfaces (`RechargeParams`, `GenerateInvoiceParams`), API response shapes with backend-specific fields, and function param types.

### 3. Component-Local Types

Types used only within a single component or composable are defined inline.

[来源: 项目源码 — `frontend/src/composables/useCustomerDetail.ts:23-45`]

```typescript
// In useCustomerDetail.ts
export interface EditForm {
  name: string
  company_id: number
  email: string
  is_key_customer: boolean
  is_real_estate: boolean | null
  // ...
}
```

---

## Validation

This project does **not** use a runtime validation library (no Zod, Yup, or io-ts). Runtime validation is handled by:

1. **Arco Design Form validation** — declarative rules with `formRef.value?.validate()`
2. **TypeScript compile-time checks** — interfaces ensure shape correctness at build time
3. **API interceptor** — `frontend/src/api/index.ts` validates response shape (`res.code === 0`)

### Form Validation Pattern

[来源: 项目源码 — `frontend/src/views/customers/components/CustomerFormModal.vue` (via component-guidelines.md)]

```typescript
const formRules = {
  company_id: [{ required: true, message: '请输入公司 ID', trigger: ['blur', 'change'] as const }],
  name: [{ required: true, message: '请输入客户名称', trigger: ['blur', 'change'] as const }],
}

const handleSubmit = async () => {
  try {
    await formRef.value?.validate()  // runtime validation
  } catch {
    return false  // prevent modal close
  }
  // ... API call
}
```

---

## Common Patterns

### Nullable Fields

Backend fields that can be null use `| null` union — not optional `?`:

[来源: 项目源码 — `frontend/src/types/index.ts:94-130`]

```typescript
export interface Customer {
  manager_id: number | null      // can be null (no manager assigned)
  email: string | null
  is_real_estate: boolean | null
  // Optional fields (may not be returned by API):
  usage_30d?: number | null
  health?: string | null
}
```

**Convention**:
- `| null` — field exists in the response but value can be null
- `?` — field may be absent from the response entirely

### Generic Type Patterns

[来源: 项目源码 — `frontend/src/types/index.ts:6-27`, `frontend/src/composables/useCachedRequest.ts:3-8`]

```typescript
// Generic API response wrapper
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

// Generic paginated response
export interface PaginatedResponse<T> {
  list: T[]
  total: number
}

// Generic cache entry
interface CacheEntry<T> {
  data: T
  timestamp: number
}

// Generic composable
export function useCachedRequest<T>(key: string, fetcher: () => Promise<T>, ttl: number) { ... }
```

### Dynamic Params

When building API request params dynamically, use `Record<string, unknown>`:

[来源: 项目源码 — `frontend/src/composables/useBalance.ts:110-139`]

```typescript
const params: Record<string, unknown> = {
  page: pagination.current,
  page_size: pagination.pageSize,
}
if (filters.keyword) params.keyword = filters.keyword
if (filters.industry?.length) params.industry = filters.industry.join(',')
```

### Enums

Use TypeScript `enum` for finite value sets with display mappings:

[来源: 项目源码 — `frontend/src/types/index.ts:80-91`]

```typescript
export enum PricePolicy {
  PRICING = 'pricing',
  TIERED = 'tiered',
  YEARLY = 'yearly',
}

export const PRICE_POLICY_DISPLAY_MAP: Record<string, string> = {
  pricing: '定价',
  tiered: '阶梯',
  yearly: '包年',
}
```

### Type Imports

Always use `import type` for type-only imports:

```typescript
import type { Customer, CustomerProfile, Balance, Tag } from '@/types'
import type { Invoice, BalanceTrendItem } from '@/api/billing'
import type { FormInstance } from '@arco-design/web-vue'
```

### Component Props (TypeScript Generic Props)

[来源: 项目源码 — `frontend/src/components/ui/ProgressBar.vue:14-22`]

```typescript
// Simple props with withDefaults
withDefaults(
  defineProps<{
    value: number
    color?: string
  }>(),
  { color: '' }
)

// Complex props with emits
const props = defineProps<{
  visible: boolean
  isEditMode: boolean
  customerRecord: Customer | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'saved'): void
}>()
```

### Error Type Narrowing

[来源: 项目源码 — `frontend/src/utils/errorHandler.ts:68-94`]

```typescript
export function handleError(error: unknown, fallbackMessage = '操作失败'): void {
  // Type guard: check for AppError shape
  if (error && typeof error === 'object' && 'code' in error) {
    const appError = error as AppError
    // ...
  }
  // Type guard: check for standard Error
  if (error instanceof Error) {
    showError(error.message || fallbackMessage)
    return
  }
  // Fallback
  showError(fallbackMessage)
}
```

---

## Forbidden Patterns

- ❌ **Using `any`** — use `unknown` and narrow with type guards, or define a proper interface
- ❌ **Non-type-safe `as` assertions without narrowing** — only use `as` after a runtime check (e.g., `error as AppError` after `'code' in error`)
- ❌ **Defining types inline in `.vue` `<script>` when reused** — move to `src/types/index.ts`
- ❌ **Using `@ts-ignore` or `@ts-expect-error`** — fix the type error instead
- ❌ **Optional `?` for nullable backend fields** — use `| null` to distinguish "absent" from "null"
- ❌ **Runtime default values in `defineProps`** — use `withDefaults()` or computed getters instead
