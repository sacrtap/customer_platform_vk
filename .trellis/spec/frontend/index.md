# Frontend Development Guidelines

> Coding conventions for the Vue 3 + Arco Design + TypeScript frontend.

---

## Pre-Development Checklist

Before writing frontend code, read and follow:

- [ ] [Directory Structure](./directory-structure.md) — Module-based layout, naming conventions, where files go
- [ ] [Component Guidelines](./component-guidelines.md) — Modal form pattern, `<script setup lang="ts">`, props/emits
- [ ] [Hook Guidelines](./hook-guidelines.md) — Composable patterns, naming, page-level logic extraction
- [ ] [State Management](./state-management.md) — Pinia stores, page state, localStorage, caching
- [ ] [Type Safety](./type-safety.md) — Type organization, nullable fields, generics, forbidden `any`
- [ ] [Quality Guidelines](./quality-guidelines.md) — API layer, error handling, linting, testing

---

## Quick Reference

| Concern | Pattern | Source |
|---------|---------|--------|
| Framework | Vue 3 (Composition API) | All `.vue` files |
| UI Library | Arco Design Vue (`@arco-design/web-vue`) | All components |
| Language | TypeScript (strict) | `tsconfig.json` |
| HTTP Client | Axios with interceptors | `frontend/src/api/index.ts` |
| API Functions | Per-module typed functions | `frontend/src/api/<module>.ts` |
| Error Handling | `handleError()` from `@/utils/errorHandler` | `frontend/src/utils/errorHandler.ts` |
| Routing | Vue Router | `frontend/src/router/index.ts` |
| Dev Server | Vite (localhost:5173) | `frontend/vite.config.ts` |

---

## Quality Check

Before submitting code:

1. **Type-check passes**: `cd frontend && pnpm type-check`
2. **No `any` types** — define interfaces for all data structures
3. **No direct axios calls** — use `@/api/<module>` functions
4. **Error handling uses `handleError()`** — not inline `Message.error()`
5. **Form components follow the modal form pattern** — see [Component Guidelines](./component-guidelines.md)

---

**Language**: Specs are written in English. UI text and user-facing messages are in Chinese.
