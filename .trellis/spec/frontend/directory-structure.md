# Directory Structure

> How frontend code is organized in this project.

---

## Overview

The frontend is a Vue 3 + TypeScript SPA built with Vite. Code lives under `frontend/src/` and follows a **module-based** organization — each business domain (customers, billing, analytics, system) has its own directory under `views/` with co-located components.

---

## Directory Layout

[来源: 项目源码 — `frontend/src/`]

```
src/
├── api/                    # API layer — typed axios functions per module
│   ├── index.ts            # Axios instance + interceptors (auth, error, refresh)
│   ├── billing.ts          # Billing APIs + co-located types (Balance, Invoice, etc.)
│   ├── customers.ts        # Customer APIs
│   ├── analytics.ts        # Analytics APIs
│   ├── tags.ts             # Tag APIs
│   ├── users.ts            # User/role APIs
│   └── ...
├── components/             # Shared cross-module components
│   ├── ui/                 # Generic UI primitives (Tag, ProgressBar, KpiCard, etc.)
│   ├── charts/             # Chart components (BalanceTrendChart, HealthGauge, etc.)
│   ├── invoice/            # Invoice-specific shared components
│   ├── layout/             # AppHeader, AppSidebar
│   ├── ActionButton.vue    # Feature-level shared components
│   ├── BatchToolbar.vue
│   ├── PageHeader.vue
│   └── ...
├── composables/            # Vue composables (page logic extraction)
│   ├── useBalance.ts       # Balance page state + actions
│   ├── useCustomerList.ts  # Customer list page state + actions
│   ├── useCustomerDetail.ts# Customer detail page state + actions
│   ├── useInvoice.ts       # Invoice page state + actions
│   ├── useAppLayout.ts     # App layout (sidebar, nav, permissions) — singleton
│   ├── useCachedRequest.ts # Generic localStorage-cached fetcher
│   └── __tests__/          # Composable unit tests
├── stores/                 # Pinia stores
│   ├── index.ts            # createPinia() instance
│   ├── user.ts             # Auth, token, permissions
│   └── customer.ts         # Customer data cache (TTL-based)
├── types/                  # Shared TypeScript type definitions
│   └── index.ts            # Domain models (Customer, Balance, Tag, User, etc.)
├── utils/                  # Utility functions
│   ├── errorHandler.ts     # Unified error handling (handleError, ErrorCategory)
│   ├── formatters.ts       # Display formatters
│   └── __tests__/
├── views/                  # Page components organized by module
│   ├── Home.vue            # Dashboard page
│   ├── Login.vue           # Auth pages
│   ├── customers/          # Customer module
│   │   ├── Index.vue       # List page
│   │   ├── Detail.vue      # Detail page
│   │   ├── components/     # Page-specific components (modals, filters, table)
│   │   └── detail/         # Detail tab components (BasicTab, ProfileTab, etc.)
│   ├── billing/            # Billing module
│   │   ├── Balance.vue
│   │   ├── Invoices.vue
│   │   ├── PricingRules.vue
│   │   └── components/     # BalanceTable, GenerateInvoiceModal, etc.
│   ├── analytics/          # Analytics module
│   │   ├── Consumption.vue
│   │   ├── Health.vue
│   │   └── components/
│   ├── system/             # System admin module
│   ├── roles/
│   ├── tags/
│   └── users/
├── router/
│   └── index.ts            # Vue Router config with route-level code splitting
├── styles/
│   ├── global.css          # Global styles, CSS custom properties
│   └── arco-theme.css      # Arco Design theme overrides
├── App.vue                 # Root component
└── main.ts                 # App entry (Pinia, router, Arco Design registration)
```

---

## Module Organization

Each view module follows this pattern:

[来源: 项目源码 — `frontend/src/views/customers/`, `frontend/src/views/billing/`]

```
views/<module>/
├── Index.vue              # Main list page
├── Detail.vue             # Detail page (if applicable)
├── components/            # Page-specific components
│   ├── *Filters.vue       # Filter bar component
│   ├── *Table.vue         # Data table component
│   ├── *Modal.vue         # Create/edit/import modals
│   └── *BatchToolbar.vue  # Batch operation toolbar
└── detail/                # Detail tab components (if applicable)
    ├── *BasicTab.vue
    └── *ProfileTab.vue
```

**Rules:**
- Components used by only one page module live in that module's `components/` directory
- Components shared across modules live in `src/components/`
- Shared UI primitives (no business logic) live in `src/components/ui/`

---

## Naming Conventions

[来源: 项目源码 — 全项目]

| Type | Convention | Example |
|------|-----------|---------|
| Vue files | PascalCase | `CustomerFormModal.vue`, `BalanceTable.vue` |
| TS files | camelCase | `errorHandler.ts`, `useBalance.ts` |
| Composables | `use<Domain>.ts` | `useBalance.ts`, `useCustomerDetail.ts` |
| Stores | `<entity>.ts` | `customer.ts`, `user.ts` |
| API modules | `<module>.ts` | `billing.ts`, `customers.ts` |
| Directories | kebab-case or camelCase | `components/`, `detail/`, `ui/` |
| Test files | `<name>.test.ts` or `<name>.spec.ts` | `useBalance.test.ts`, `useCustomerDetail.spec.ts` |

---

## Examples

Well-organized modules to reference:

- **Customer module**: `frontend/src/views/customers/` — list + detail + 14 page components + 7 detail tabs
- **Billing module**: `frontend/src/views/billing/` — 4 pages + 13 page components with test files
- **Shared UI**: `frontend/src/components/ui/` — 5 reusable primitives (Tag, ProgressBar, KpiCard, FilterDropdown, CheckboxArray)
