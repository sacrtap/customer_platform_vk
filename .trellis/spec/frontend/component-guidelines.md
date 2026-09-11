# Component Guidelines

> How components are built in this project.

---

## Overview

The frontend uses **Vue 3** (Composition API with `<script setup lang="ts">`), **Arco Design Vue** (`@arco-design/web-vue`) as the UI library, and **TypeScript** for type safety.

---

## Modal Form Pattern

This is the most common component type — a modal dialog containing a form for create/edit operations.

### Standard Structure

[来源: 项目源码 — `frontend/src/views/customers/components/CustomerFormModal.vue`]

```vue
<template>
  <a-modal
    v-model:visible="isVisible"
    :title="isEditMode ? '编辑客户' : '新建客户'"
    :confirm-loading="loading"
    width="600px"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form
      ref="formRef"
      :model="form"
      :rules="formRules"
      layout="vertical"
      validate-trigger="['blur', 'change']"
    >
      <!-- form items -->
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { reactive, ref, computed, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { handleError } from '@/utils/errorHandler'
import { createCustomer, updateCustomer } from '@/api/customers'

// 1. Define typed form interface
interface CustomerForm {
  company_id: number | undefined
  name: string
  email: string
  // ...
}

// 2. Define props with TypeScript
const props = defineProps<{
  visible: boolean
  isEditMode: boolean
  customerRecord: Customer | null
  industryTypes: IndustryType[]
}>()

// 3. Define emits
const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'saved'): void
}>()

// 4. Computed visible (v-model pattern)
const isVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

// 5. Form state with reactive()
const loading = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<CustomerForm>({ ... })

// 6. Validation rules
const formRules = {
  company_id: [{ required: true, message: '请输入公司 ID', trigger: ['blur', 'change'] as const }],
  name: [{ required: true, message: '请输入客户名称', trigger: ['blur', 'change'] as const }],
}

// 7. Watch visible to init form for create/edit
watch(() => props.visible, (val) => {
  if (val && props.isEditMode && props.customerRecord) {
    initFormForEdit(props.customerRecord)
  } else if (val && !props.isEditMode) {
    initFormForCreate()
  }
})

// 8. Submit handler — validate → API call → emit saved
const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
  } catch {
    return false  // prevent modal close
  }
  loading.value = true
  try {
    if (props.isEditMode && props.customerRecord?.id) {
      await updateCustomer(props.customerRecord.id, data)
      Message.success('更新成功')
    } else {
      await createCustomer(data)
      Message.success('创建成功')
    }
    emit('saved')
    emit('update:visible', false)
    return true
  } catch (error: unknown) {
    handleError(error, '操作失败')
    return false  // prevent modal close
  } finally {
    loading.value = false
  }
}
</script>
```

---

## Key Conventions

### Props and Emits
- Always use `defineProps<{ ... }>()` with TypeScript interfaces — never runtime defaults
- Use `defineEmits<{ ... }>()` with typed event signatures
- Modal visibility follows `v-model:visible` pattern with computed get/set

### Form State
- Use `reactive<TypedForm>({ ... })` for form data
- Use `ref<FormInstance>()` for the form ref
- Initialize form with `watch()` on the `visible` prop — separate `initFormForCreate()` and `initFormForEdit(record)` functions

### Validation
- Rules object with `trigger: ['blur', 'change'] as const`
- Call `await formRef.value?.validate()` before API submission
- Return `false` from `@before-ok` handler to prevent modal close on validation failure

### Error Handling
- Import `handleError` from `@/utils/errorHandler`
- Wrap API calls in try/catch, call `handleError(error, 'fallback message')` on failure
- Use `Message.success()` from Arco Design for success feedback

### API Calls
- Import typed API functions from `@/api/<module>`
- API functions return axios promises (already intercepted for auth/errors)

---

## Styling

- Use `<style scoped>` in every component
- Deep selectors with `:deep(.arco-class-name)` for Arco Design overrides
- CSS custom properties (e.g., `var(--ink)`) for theme colors

[来源: 项目源码 — `frontend/src/views/customers/components/CustomerFormModal.vue:297-307`]

```vue
<style scoped>
:deep(.arco-modal) {
  border-radius: 18px;
}
:deep(.arco-form-item-label) {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}
</style>
```

---

## Component Organization

View-level components live in `frontend/src/views/<module>/components/`:

```
views/customers/
├── Index.vue                     # Main page
├── Detail.vue                    # Detail page
├── components/
│   ├── CustomerFormModal.vue     # Create/edit form modal
│   ├── CustomerFilters.vue       # Filter bar
│   ├── CustomerTable.vue         # Data table
│   └── CustomerImportModal.vue   # Import modal
└── detail/
    ├── CustomerBasicTab.vue      # Detail tab
    └── CustomerProfileTab.vue
```

Shared UI components live in `frontend/src/components/ui/`.

---

## Forbidden Patterns

- ❌ **Using Options API** — always use `<script setup lang="ts">`
- ❌ **Using `any` type** — define interfaces for all form data
- ❌ **Calling axios directly** — use the API layer functions from `@/api/<module>`
- ❌ **Handling errors with `try/catch` + `Message.error()` inline** — use `handleError()` from `@/utils/errorHandler`
- ❌ **Forgetting to reset form on modal close** — call `formRef.value?.resetFields()` in cancel handler

---

## Shared Options Constants (选项一致性)

**Problem**: When the same field (e.g., `settlement_cycle`, `account_type`, `invoice status`) appears in multiple forms (Add, Edit, BatchEdit, Filters, Detail display), hardcoding options in each component leads to **option drift** — some forms have fewer options than others.

**Rule**: All dropdown/select options and display mappings must be defined in `frontend/src/constants/customerOptions.ts` and imported by every form component.

### Checklist: When adding or modifying a field with fixed options

- [ ] Check if the field already exists in `customerOptions.ts`
- [ ] If yes, import the constant and use it — do NOT hardcode options in the template
- [ ] If no, add the option constant to `customerOptions.ts` first, then use it in all forms
- [ ] Search for ALL components that render this field: `grep -r "field_name" frontend/src/views/`
- [ ] Verify every component uses the same option set
- [ ] If a backend enum exists (e.g., `InvoiceStatus`), ensure frontend options match it exactly

### Real-world examples (2026-09-11)

- `settlement_cycle` was 3 options in AddCustomerModal, 4 in CustomerFormModal, 3 in CustomerBatchEditModal, but 5 in the backend — fixed by unifying to 5
- `account_type` was 2 options in CustomerFormModal but 3 in all other forms — fixed by unifying to 3
- `InvoiceFilters` status options were missing `pending_ops` and `pending_sales` that the backend `InvoiceStatus` enum defines — fixed by adding them
- `EditCustomerDialog` scale_level was missing the `E` option that `CustomerBatchEditModal` and the backend model comment defined

### Three-state boolean fields

When a boolean field supports `null` in the backend model (e.g., `is_real_estate = Column(Boolean, nullable=True, default=None)`), the form control must be a three-state `a-select` (是/否/未设置), NOT a two-state `a-switch`. This ensures the user can explicitly set "未设置" and that editing doesn't accidentally override `null` to `false`.

---

## Layout Stability in Modal Forms (布局稳定性)

**Problem**: When users interact with form fields (clear a select, trigger validation, etc.), the modal layout visually jumps/shifts. This is caused by:
1. Error messages appearing/disappearing, changing `a-form-item` height
2. Multi-column layouts with unequal column heights
3. `a-spin` loading state destroying and recreating DOM content
4. Async dictionary data loading causing options to appear after form render

### Rules for Layout-Stable Modal Forms

#### R1: Reserve error message space (P0)
Always add `min-height` to Arco's error message element so form items don't grow when validation messages appear:

```css
:deep(.arco-form-item-message) {
  min-height: 22px;
  line-height: 22px;
}
```

#### R2: Use CSS Grid instead of `a-row`/`a-col` for multi-column forms (P0)
`a-row`/`a-col` doesn't guarantee equal-height columns. Use CSS Grid:

```css
.form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  align-items: start;
}
```

Responsive breakpoints:
```css
@media (max-width: 767px) { .form-grid { grid-template-columns: 1fr; } }
@media (min-width: 768px) and (max-width: 1023px) { .form-grid { grid-template-columns: repeat(2, 1fr); } }
```

#### R3: Use `validate-trigger="['blur']"` for large forms (P1)
For forms with 10+ fields, avoid `change` trigger — it causes validation on every keystroke/selection, leading to frequent layout shifts. Use `blur`-only validation; the final `validate()` call at submit time catches everything.

#### R4: Preload dictionary data in the parent component (P1)
If a modal form uses dropdown data (managers, industry types, cooperation statuses, ERP systems), load it in the **parent page's `onMounted`** — not inside the modal's open watcher. Pass as props. The modal's own `loadDictData()` should only run as a fallback when props are not provided.

#### R5: Use `v-show` instead of `v-if` for loading transitions (P2)
When wrapping form content in `a-spin`, use `v-show="!loading"` on the content wrapper to keep DOM mounted during loading transitions, preventing DOM rebuild layout shifts:

```vue
<a-spin :loading="fetchLoading">
  <div v-show="!fetchLoading">
    <!-- form content stays in DOM -->
  </div>
</a-spin>
```

#### R6: All `a-select` with `required` validation must have `allow-clear` (P2)
A `required` select without `allow-clear` is a UX contradiction — the user can select a value but cannot clear it to re-select. Always add `allow-clear` to required selects.

### Real-world example (2026-09-11)

`EditCustomerDialog.vue` had all 6 problems: no error message spacing, `a-row` with unequal columns, `change` validation trigger, async dict loading in modal, `a-spin` DOM replacement, and `settlement_type` missing `allow-clear`. All 6 fixed in one batch.
