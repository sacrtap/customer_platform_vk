# Quality Guidelines

> Code standards, type safety, and forbidden patterns for the frontend.

---

## Pre-Development Checklist

Before writing frontend code, verify:

- [ ] Read a similar component in the same module to match patterns
- [ ] Use `<script setup lang="ts">` — never Options API
- [ ] Import API functions from `@/api/<module>` — never call axios directly
- [ ] Use `handleError()` from `@/utils/errorHandler` for all error handling
- [ ] Define TypeScript interfaces for all form data and component props
- [ ] Use Arco Design Vue components (`a-*` prefix) — do not mix UI libraries

---

## Tech Stack

| Tool | Version / Purpose |
|------|-------------------|
| Vue 3 | Composition API (`<script setup>`) |
| TypeScript | Type safety (strict mode) |
| Arco Design Vue | UI component library |
| Axios | HTTP client (with interceptors) |
| Vite | Build tool / dev server |
| pnpm | Package manager |

---

## API Layer

[来源: 项目源码 — `frontend/src/api/index.ts`]

The Axios instance is configured with:
- `baseURL: '/api/v1'`
- Request interceptor: attaches `Bearer` token from `localStorage`
- Response interceptor: checks `res.code !== 0` for business errors, auto-refreshes on 401

Per-module API files export typed functions:

[来源: 项目源码 — `frontend/src/api/customers.ts:4-39`]

```typescript
import api from './index'

export interface CustomerCreate {
  company_id: number
  name: string
  email?: string
  // ...
}

export function createCustomer(data: CustomerCreate) {
  return api.post('/customers', data)
}

export function getCustomers(params?: {
  page?: number
  page_size?: number
  keyword?: string
  // ...
}) {
  return api.get('/customers', { params })
}
```

---

## Error Handling

[来源: 项目源码 — `frontend/src/utils/errorHandler.ts`]

The unified error handler maps backend error codes to categories and user-friendly messages:

```typescript
import { handleError } from '@/utils/errorHandler'

try {
  await createCustomer(data)
  Message.success('创建成功')
} catch (error: unknown) {
  handleError(error, '操作失败')
}
```

**Error categories** (matching backend `ErrorCodes`):

| Category | Code range | Example |
|----------|------------|---------|
| `CLIENT_ERROR` | 40000–40099 | Invalid params |
| `AUTH_ERROR` | 40100–40199 | Token expired |
| `FORBIDDEN_ERROR` | 40300–40399 | No permission |
| `NOT_FOUND_ERROR` | 40400–40499 | Resource missing |
| `SERVER_ERROR` | 50000+ | Internal error |

---

## Type Safety

- All form data must have a TypeScript interface defined
- Props must use `defineProps<{ ... }>()` with explicit types
- API response types should be defined in `@/types` and used in components
- Use `as const` for array literals in validation rules to satisfy type inference

---

## Forbidden Patterns

- ❌ **Options API** (`export default { data() { ... } }`) — use `<script setup lang="ts">`
- ❌ **Direct `axios.get/post` calls in components** — use `@/api/<module>` functions
- ❌ **`any` type** — define proper interfaces
- ❌ **`console.log` in production code** — remove before commit
- ❌ **Inline error handling** (`catch (e) { Message.error(e.message) }`) — use `handleError()`
- ❌ **Hardcoded API URLs** — the base URL is `/api/v1` (configured in `api/index.ts`)

---

## Dev Commands

```bash
cd frontend
pnpm dev          # Start dev server (localhost:5173)
pnpm build        # Production build
pnpm type-check   # TypeScript type checking
```
