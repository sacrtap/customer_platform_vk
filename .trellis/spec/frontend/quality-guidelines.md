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

## Pre-commit: Trellis 任务文件提交陷阱

> [来源: 2026-10-22 会话 — `task.py archive` / `create` 后提交 `task.json` 连续失败]

**What**: `.trellis/scripts/task.py` 生成的 `task.json` / `prd.md` **不带文件末尾换行**，而 pre-commit 的 `end-of-file-fixer` 钩子（`.pre-commit-config.yaml:19`）会补上该换行。钩子修改文件后，pre-commit 的 stash 还原步骤与 auto-fix 冲突并回滚，表现为提交"成功"（hook 全 Passed）但 `git log` 中无新提交。

**Why**: 该冲突对 `.trellis/` 与 `frontend/` 同时修改的提交几乎必然触发（前端文件本身合规，钩子只改 `task.json`），且报错信息（`Stashed changes conflicted with hook auto-fixes... Rolling back fixes...`）不指向具体文件，容易被误判为代码问题而反复重试同一提交，形成"重写循环"。

**Example**：

```bash
# 现象：hook 全 Passed，但没有新 commit
git commit -m "chore(trellis): 归档任务 ..."
# [WARNING] Stashed changes conflicted with hook auto-fixes... Rolling back fixes...
# Archive moved on disk, but git auto-commit did not complete.

# 诊断：哪个文件被钩子改了
git diff --stat        # 只有 task.json，1 insertion(+), 1 deletion(-)

# 修复：把钩子修复后的内容重新入索引，再提交（不要改文件内容）
git add .trellis/tasks/ && git commit -m "chore(trellis): 归档任务 ..."
```

**Related**:

- 若提交内**只**含前端代码，`task.json` 未暂存则不触发；一旦与 `.trellis/` 变更混在同一提交就会触发。
- 一次性规避：先 `printf '\n' >> <task.json>` 手动补换行再提交。
- 根治方案（未实施）：修改 `.trellis/scripts/` 中写文件的逻辑，统一以 `\n` 结尾生成 JSON/Markdown。
- 检测到"提交后 HEAD 未前进 + 钩子 auto-fix 冲突"时，按 `.omp/rules/stop-file-rewrite-loop-on-corruption.md` 的退出协议处理：停止自动修改、锁定已完成工作、向用户报告，不要重试同一提交路径。

---

## Dev Commands

```bash
cd frontend
pnpm dev          # Start dev server (localhost:5173)
pnpm build        # Production build
pnpm type-check   # TypeScript type checking
```
