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

## Visual Regression Baselines

> [来源: `frontend/tests/e2e/test_visual_regression.spec.ts`]

基线截图只校验**布局与结构**，不校验数据。数据驱动区域必须显式遮罩，否则基线会随造数波动而失败。

**What**: 通用遮罩 `getDynamicMaskSelectors()` 只覆盖 `.arco-table tbody`、`canvas` 等；若页面用原生 `<table>`（如余额管理 `.table-wrap`）、或数值来自接口（KPI 卡片），需在用例内追加遮罩。

**Why**: e2e-full 工作流并行跑全部用例，其它用例通过 API 造数会改变余额页的行数、KPI 数值与分页条数；未遮罩时同一份基线在不同运行间必然不一致。

**Example**（余额管理 A06）：

```typescript
mask: [
  ...getDynamicMaskSelectors(page),
  page.locator('.table-wrap tbody'),
  page.locator('.pagination'),
  page.locator('.kpi-value'),
  page.locator('.kpi-trend'),
]
```

**Related**: 遮罩内仍会比对卡片数量、标签文案、筛选器与表头，因此「新增/删除卡片、布局错位」这类回归依旧会被检出。更新基线须在**种子数据环境**（`scripts/seed.py --reset`）下执行 `npx playwright test test_visual_regression.spec.ts -g "A06" --update-snapshots`，不要用本地脏数据环境。

---

## Dev Commands

```bash
cd frontend
pnpm dev          # Start dev server (localhost:5173)
pnpm build        # Production build
pnpm type-check   # TypeScript type checking
```
