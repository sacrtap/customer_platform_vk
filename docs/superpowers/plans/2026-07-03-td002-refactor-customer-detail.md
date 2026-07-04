# TD-002 Refactor Customer Detail — Implementation Plan

**Date**: 2026-07-03  
**Spec**: `docs/superpowers/specs/2026-07-03-td002-refactor-customer-detail-design.md`  
**Base**: `frontend/src/views/customers/Detail.vue` (2332 lines)  
**Strategy**: tab-after-tab 拆分，每步可回滚，E2E 验证贯穿始终

---

## File Structure

### 新建文件

| 文件 | 职责 | Phase |
|---|---|---|
| `src/composables/useCustomerDetail.ts` | 共享状态与 API | 1 |
| `src/composables/__tests__/useCustomerDetail.spec.ts` | composable 单元测试 | 1 |
| `src/views/customers/detail/EditCustomerDialog.vue` | 编辑客户对话框 | 1 |
| `src/views/customers/detail/TagSelectorDialog.vue` | 标签选择对话框 | 1 |
| `src/views/customers/detail/CustomerBasicTab.vue` | 基础信息标签页模板+脚本 | 2 |
| `src/views/customers/detail/CustomerProfileTab.vue` | 画像信息标签页 | 2 |
| `src/views/customers/detail/CustomerBalanceTab.vue` | 余额信息标签页 | 2 |
| `src/views/customers/detail/CustomerInvoicesTab.vue` | 结算单表格 | 2 |
| `src/views/customers/detail/CustomerUsageTab.vue` | 用量分布图+表格 | 2 |

### 修改文件

| 文件 | Phase 1 改动 | Phase 2 改动 | Phase 3 改动 |
|---|---|---|---|
| `src/views/customers/Detail.vue` | 改为引用 composable 和对话框，删除重复逻辑 | 逐个 `<a-tab-pane>` 体替换为子组件 | 删除未使用引用、统计行数 ≤150 |

---

## Phase 1: 提取 Composable + 对话框（不动 tab 结构）

### Task 1: 创建 `useCustomerDetail` composable

**文件**: `frontend/src/composables/useCustomerDetail.ts`

**实现内容**:
- 从 Detail.vue script 迁移以下状态：
  - `detail`, `loading` — 客户基础信息
  - `balance`, `balanceLoading` — 余额数据
  - `profile`, `profileLoading` — 画像数据
  - `invoices` — 结算单列表
  - `usageData`, `usageLoading`, `usagePagination` — 用量数据
  - `loadedTabs`, `chartRenderState`, `tabLoadTimer` — 性能优化
  - `editModalVisible`, `tagSelectorVisible` — 对话框开关
- 迁移方法：
  - `loadDetail()` — 调用 `getCustomer()`
  - `loadBalance()` — 调用 `getCustomerBalance()`
  - `loadProfile()` — 调用 `getProfile()`
  - `loadInvoices()` — 调用 `getInvoices()`
  - `loadUsage(page)` — 调用 `getDailyUsage()`
  - `handleTabChange(key)` — 控制懒加载 + 图表延迟渲染
  - `openEdit()`, `closeEdit()`, `submitEdit(form)` — 编辑对话框
  - `openTagSelector()`, `closeTagSelector()`, `addTags(tags)` — 标签对话框
- 返回统一暴露的状态和方法对象

**关键约束**:
- 保留 `loadedTabs` 和 `chartRenderState` 的懒加载逻辑原样迁移
- `handleTabChange` 内部延迟 100ms 渲染图表的逻辑保持不变
- `modalWidth` 计算属性保留在 composable 内

**验证**: `npm run type-check` 通过

---

### Task 2: 编写 composable 单元测试

**文件**: `frontend/src/composables/__tests__/useCustomerDetail.spec.ts`

**实现内容**:
- Mock 所有 API (`@/api/customers`, `@/api/billing`, `@/api/usage`, `@/api/tags`)
- 测试用例：
  1. `loadDetail` 成功后 `detail` 有值且 `loading=false`
  2. `handleTabChange('balance')` 触发 `loadBalance`（首次访问）
  3. `handleTabChange('balance')` 第二次调用不触发重复加载（cached）
  4. `openEdit()` 设置 `editModalVisible = true`
  5. `closeEdit()` 设置 `editModalVisible = false`
  6. UI 不相关的状态隔离：tab A 的数据不影响 tab B

**关键约束**:
- 使用 `vi.stubGlobal('localStorage', ...)` 处理可能的缓存层
- 测试保持 < 50ms 每条（即时 mock）

**验证**: `npm test -- --run composables/__tests__/useCustomerDetail.spec.ts` 全部通过

---

### Task 3: 创建 `EditCustomerDialog.vue`

**文件**: `frontend/src/views/customers/detail/EditCustomerDialog.vue`

**实现内容**:

```vue
<template>
  <a-modal
    :visible="visible"
    title="编辑客户"
    :width="modalWidth"
    :confirm-loading="editLoading"
    @ok="$emit('submit', editForm)"
    @close="$emit('close')"
  >
    <!-- 表单体从 Detail.vue:385-594 复制 -->
  </a-modal>
</template>

<script setup lang="ts">
const props = defineProps<{
  visible: boolean
  customer: Customer
  editLoading: boolean
}>()

defineEmits<{
  submit: [form: EditForm]
  close: []
}>()

// 价格策略选项、表单验证规则等从原组件迁移
</script>
```

**关键约束**:
- `modalWidth` 计算逻辑从 composable 获取
- 表单验证规则与原来 `$omp-project/frontend/src/views/customers/Detail.vue` 完全一致
- 样式 `<style scoped>` 单独存在于本组件

**验证**: `npm run type-check` 通过

---

### Task 4: 创建 `TagSelectorDialog.vue`

**文件**: `frontend/src/views/customers/detail/TagSelectorDialog.vue`

**实现内容**:
- 对话框体从 Detail.vue:598-621 迁移
- Props: `visible: boolean`
- Emits: `add(tags: Tag[])`, `close()`

**验证**: `npm run type-check` 通过

---

### Task 5: Detail.vue 改用 composable + 对话框组件

**文件**: `Detail.vue`

**改动**:
1. 移除原 script 中 composable 已包含的状态/方法
2. `import` composable 并使用 `const { detail, loading, ... } = useCustomerDetail(customerIdRef)`
3. 移除 `message` 导入（composable 处理）
4. 移除 `useRouter`, `useCustomerStore` 导入
5. 移除 `pricePolicyOptions` 声明（移到 EditCustomerDialog）
6. 移除 `editFormRef`, `modalWidth` 本地声明

**验证**:
- `npm run type-check` 通过
- `npm run test:e2e -- tests/e2e/customer-detail.spec.ts` 全部 14 个用例通过

---

### Task 6: Commit Phase 1

```bash
git add frontend/src/composables/useCustomerDetail.ts \
        frontend/src/composables/__tests__/useCustomerDetail.spec.ts \
        frontend/src/views/customers/detail/EditCustomerDialog.vue \
        frontend/src/views/customers/detail/TagSelectorDialog.vue \
        frontend/src/views/customers/Detail.vue
git commit -m "refactor: extract useCustomerDetail composable and dialogs from Detail.vue"
```

---

## Phase 2: 逐个 Tab 组件

每个 Tab 的抽取按相同模式：

```
创建 tab 组件 → Detail.vue import + 替换模板体 → E2E 验证 → Commit
```

### Task 7: Create `CustomerBasicTab.vue`

**文件**: `src/views/customers/detail/CustomerBasicTab.vue`

**模板源**: Detail.vue:32-186 (the `<a-tab-pane key="basic">...</a-tab-pane>`)

**Props**:
- `detail: Customer`

**内部逻辑**: 无状态，纯展示

**验证**: `npm run type-check` 通过

### Task 8: Detail.vue 替换基础信息为组件

**改动**:
```vue
<template>
  ...
  <a-tab-pane key="basic" title="基础信息">
    <CustomerBasicTab :detail="detail" />
  </a-tab-pane>
  ...
</template>

<script>
import CustomerBasicTab from './detail/CustomerBasicTab.vue'
</script>
```

**验证**: `npm run test:e2e -- tests/e2e/customer-detail.spec.ts` 通过（至少 2, 14 用例相关 basic tab）

### Task 9: Commit `CustomerBasicTab`

```bash
git add frontend/src/views/customers/detail/CustomerBasicTab.vue \
        frontend/src/views/customers/Detail.vue
git commit -m "refactor: extract CustomerBasicTab from Detail.vue"
```

### Task 10: Create `CustomerProfileTab.vue`

**文件**: `src/views/customers/detail/CustomerProfileTab.vue`

**模板源**: Detail.vue:187-282

**Props**:
- `profile: Profile`
- `profileLoading: boolean`
- `renderedCharts: Set<string>` (or similar)

**内部逻辑**:
- `consumeLevelDisplay` 计算属性
- `profileExtensionList` 列表数据

**验证**: `npm run type-check` 通过

### Task 11: Detail.vue 替换画像为组件

**验证**: E2E 包含「画像信息 Tab」相关用例通过

### Task 12: Commit `CustomerProfileTab`

### Task 13: Create `CustomerBalanceTab.vue`

**文件**: `src/views/customers/detail/CustomerBalanceTab.vue`

**模板源**: Detail.vue:283-315

**Props**:
- `balance: Balance`
- `balanceLoading: boolean`
- `renderedCharts: Set<string>`

**内部逻辑**: 无复杂逻辑（卡片展示 + 图表绑定）

**验证**: `npm run type-check` 通过

### Task 14: Detail.vue 替换余额为组件

**验证**: E2E 包含「余额信息 Tab」用例通过

### Task 15: Commit `CustomerBalanceTab`

### Task 16: Create `CustomerInvoicesTab.vue`

**文件**: `src/views/customers/detail/CustomerInvoicesTab.vue`

**模板源**: Detail.vue:316-336

**Props**:
- `invoices: Invoice[]`

**Emits**:
- `view-invoice(record: Invoice)`

**内部逻辑**: `invoiceColumns`, `formatCurrency`, `getStatusClass`, `getStatusText`

**验证**: `npm run type-check` 通过

### Task 17: Detail.vue 替换结算单为组件

**验证**: E2E 包含「结算单 Tab」用例通过

### Task 18: Commit `CustomerInvoicesTab`

### Task 19: Create `CustomerUsageTab.vue`

**文件**: `src/views/customers/detail/CustomerUsageTab.vue`

**模板源**: Detail.vue:338-372

**Props**:
- `usageData: UsageRecord[]`
- `usageLoading: boolean`
- `usagePagination: { current, pageSize, total }`
- `renderedCharts: Set<string>`

**Emits**:
- `page-change(payload: { current: number})`

**内部逻辑**: `usageColumns`, `usageDistribution`, `totalUsageQuantity` 计算（来自 composable 还是 props？）

**验证**: `npm run type-check` 通过

### Task 20: Detail.vue 替换用量为组件

**验证**: E2E 包含「用量数据 Tab」用例通过

### Task 21: Commit `CustomerUsageTab`

---

## Phase 3: 清理与最终验证

### Task 22: 清理 Detail.vue 残留引用

**改动**:
- 移除原 `import { updateProfile } from '@/api/customers'` 等已在 composable 的 API 客户端导入
- 移除 `HealthGauge`, `ConsumeLevelProgress` 等不会再模板直接使用的图表组件导入
- 移除 `EmptyState`, `SkeletonCard` 等已下沉到子组件的通用组件导入
- 保留 `a-tabs`、`a-spin`、`a-modal`（对话框仍引用）

---

### Task 23: 验证 Detail.vue 行数

**命令**:
```
wc -l frontend/src/views/customers/Detail.vue
```

**通过标准**: ≤ 150 行（不含空行和注释）

如果超了，检查是否还有可迁移至 composable 的函数。

---

### Task 24: 最终 E2E 验证

**命令**:
```bash
npm run test:e2e -- tests/e2e/customer-detail.spec.ts
```

**通过标准**: 全部 14 个用例通过

同时跑：
```bash
npm run test:e2e -- tests/e2e/test_customer_crud.spec.ts
```

保证不破坏其他 E2E。

---

### Task 25: 最终 Commit

```bash
git add frontend/src/views/customers/Detail.vue
git commit -m "refactor: Detail.vue moves all tab contents into subcomponents, final cleanup"
```

---

## Acceptance Criteria

Detail spec 的 Acceptance Criteria 100%：

- [ ] `frontend/src/views/customers/Detail.vue` ≤ 150 行
- [ ] 5 个 tab 组件独立存在
- [ ] 现有 E2E `customer-detail.spec.ts` 14 个用例全量通过
- [ ] `useCustomerDetail` 单元测试覆盖率 ≥ 60%
- [ ] 样式公私分离完成
- [ ] 浏览器中视觉与改造前一致

---

## Risks & Mitigations（来自 spec）

| 风险 | Plan 中的缓解 |
|---|---|
| Tab 间隐式依赖 | composable 统一在 `handleTabChange` 处理加载顺序 |
| 样式迁移遗漏 | 每 Phase 单独 E2E + visual check |
| 过度重构 | 按 tab 拆分，多次 commit 多次 review |
| 延迟加载破坏交互 | Phase 5 严格 E2E 验证 |

---

## Notes

- 使用 `npm run test` 而非直接 `vitest`（package.json 脚本）
- composable mock 参考现有 `src/composables/__tests__/useCachedRequest.test.ts` 模式
- E2E 跑了 14 个用例确保不破坏用户路径
- 如需中途回滚，每个 Task 都是原子 commit，可直接 `git revert`
