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
