# 组件规范（Vue 3 + Arco Design）

> `frontend/src/views/**`、`frontend/src/components/**` 的组件编写契约与实战陷阱。

## Scope / Trigger

- 触发：新增/改造页面组件、弹窗组件，或调整按钮权限门控
- 适用于所有 `.vue` 单文件组件

---

## 基本约定

- 一律 `<script setup lang="ts">`；props 用 `defineProps<{...}>()`（类型字面量，不用运行时对象写法）
- emits 用 `defineEmits<{ 'update:visible': [value: boolean]; success: [] }>()` 类型化写法
- 不使用 `any`（见 [Type Safety](./type-safety.md)）；数据访问走 `@/api/<module>`，不直接调 axios
- 弹窗出现/关闭状态由父组件持有：子组件 `visible` prop + `update:visible` emit（`computed` 双向桥接）

---

## Modal 表单模式（项目既有约定）

```vue
<a-modal
  v-model:visible="isVisible"
  :title="title"
  :ok-text="loading ? '导入中...' : '开始导入'"
  :confirm-loading="loading"
  @before-ok="handleSubmit"
  @cancel="emit('update:visible', false)"
>
```

- `@before-ok` 返回 `false` 可阻止弹窗关闭（校验失败/存在错误行时保持打开，便于用户查看错误明细）
- 提交按钮的 loading 文案通过 `:ok-text` 切换，不用额外 loading 组件

---

## 导入弹窗契约（`views/billing/components/ImportModal.vue`）

通用导入弹窗，四个 billing 页面复用。

| prop | 类型 | 说明 |
|---|---|---|
| `visible` | `boolean` | 弹窗可见性（父组件持有） |
| `title` | `string` | 标题，如「批量导入计费规则」 |
| `importApi` | `(file: File) => Promise<{ data: ImportResult }>` | 导入接口 |
| `templateApi` | `() => Promise<{ data: Blob }>` | 模板下载接口 |
| `templateFileName` | `string` | 下载保存的模板文件名 |

| emit | 说明 |
|---|---|
| `update:visible` | 可见性变更 |
| `success` | **至少一条导入成功**时触发，父组件据此刷新列表 |

```ts
interface ImportResult {
  success_count: number
  error_count: number
  errors?: string[]
}
```

### 关键行为

- 文件校验：`f.type.includes('spreadsheetml') || f.name.endsWith('.xlsx')`，大小 ≤ 10MB
- 结果区按 `error_count === 0` 切换 success/warning 提示，并列出 `errors`
- **`emit('success')` 的条件必须是 `success_count > 0`（不是 `error_count === 0`）**：部分成功的场景下若依赖 `error_count === 0`，父列表不会刷新，用户看不到刚导入成功的数据

---

## 按钮权限门控

```vue
<button v-if="can('billing:pricing_import')" class="btn" @click="importVisible = true">导入规则</button>
<button v-if="can('billing:pricing_export')" class="btn" @click="handleExport">导出</button>
```

- `can()` 来源于 `useAppLayout()` / 页面 composable，内部调用 `userStore.hasPermission(code)`
- 新增权限码须同步后端 `@require_permission`、`seed.py`、`conftest.py`（见 [后端导入导出规范](../backend/import-export.md) 的权限码变更检查清单）

> **Warning（验证陷阱）**：`userStore.hasPermission` 对 `roles` 含「超级管理员」的用户**无条件返回 `true`**。
> 用管理员账号验证"按钮是否按权限显隐"永远会通过。验证权限门控必须构造**非超管身份**
> （如把 `user_info.roles` 改为业务角色 + 只写入部分权限码的 `user_permissions`）后再观察按钮。

---

## 常见陷阱

| 现象 | 原因 | 处理 |
|---|---|---|
| 页面白屏，`#app` 只剩 `<!---->`，无 console 报错 | 访问了未定义的路由路径（如 `/billing/balance`，实际路由是 `/billing/balances`），`router-view` 渲染空注释节点 | 核对 `router/index.ts` 的实际 `path`；路径错误不会产生 JS 错误 |
| 断言"弹窗未打开"却读到别的弹窗内容 | 页面 DOM 中同时存在多个 `.arco-modal`（历史弹窗未卸载） | 按可见性过滤：`Array.from(document.querySelectorAll('.arco-modal')).find(x => x.offsetParent !== null)` |
| 导出失败时提示英文 `Bad Request` 而非后端文案 | axios 拦截器错误分支未解析 Blob 错误体 | **已修复**：`api/index.ts` 错误分支对 `Blob` 先 `await data.text()` 再 `JSON.parse`。新增下载链路无需额外处理，但**不要**在拦截器外重复解析 Blob |

---

## 受控显示文本组件：清空显示需重建实例

**现象**：父组件把 `v-model` 绑定的值置为 `undefined` 后，子组件输入框里**仍显示上一次选中的文本**（数据层已清空，视图层没清）。

**原因**：`CustomerAutoComplete` 这类组件把显示文本存在**组件内部 ref**（`displayText`），
模板绑的是 `:model-value="displayText"` 而不是 `props.modelValue`：

```vue
<!-- 子组件内部：显示文本与 modelValue 解耦 -->
<a-auto-complete :model-value="displayText" @select="handleSelect" @input="handleInput" />
```

组件只在自己交互（`handleSelect` / `handleClear` / `handleInput`）或 `displayName` prop 变化时更新它。
父组件**单向**改 `modelValue`（尤其置 `undefined`）不会回写显示文本。

**处理**（在不改动通用组件本身的前提下）：父组件用 `:key` 重建该实例。

```vue
<!-- 父组件：每次弹窗打开递增 key，强制重建 → displayText 归零 -->
<CustomerAutoComplete :key="customerPickerKey" v-model="form.customer_id" />
```

```ts
const customerPickerKey = ref(0)

watch(
  () => props.visible,
  (val) => {
    if (val) {
      customerPickerKey.value += 1 // 先重建组件，再清数据模型
      form.customer_id = undefined
    }
  }
)
```

> **验证陷阱**：`watch(() => form.customer_id)` **在值未变化时不触发**（例如重新选中同一个客户）。
> 因此「重选同一客户」不能用来验证刷新逻辑 —— 必须做真实变更（改周期、换客户）。

---

## 布尔筛选项：FilterDropdown 的 string ↔ boolean 桥接

[来源: 2026-09-20 — 客户列表新增 是否结算/是否重点客户/是否房产客户/是否停用 四个布尔筛选]

`FilterDropdown.vue` 的 `modelValue` 类型是 `string | string[]`，options 的 value 也是 string
（「全部」用空串 `''` 表示）。**布尔字段不能直接 `v-model`**，需在 `CustomerFilters.vue` 内做
string ↔ boolean | null 转换，遵循现有 `managerValue` computed 模式：

```vue
<FilterDropdown v-model="settlementEnabledValue" label="是否结算"
  :options="BOOLEAN_FILTER_OPTIONS" @apply="handleSearch" />
```

```ts
// BOOLEAN_FILTER_OPTIONS 定义在 constants/customerOptions.ts
// [{ label: '是', value: 'true' }, { label: '否', value: 'false' }]

const settlementEnabledValue = computed({
  get: () => (filters.value.is_settlement_enabled === null ? '' : String(filters.value.is_settlement_enabled)),
  set: (val: string) => { filters.value.is_settlement_enabled = val === '' ? null : val === 'true' },
})
// keyCustomerValue / realEstateValue / disabledValue 同理
```

**约定**：
- filters 模型字段类型 `boolean | null`，`null` = 全部（不筛选）。
- 新增布尔筛选项 = 4 处同步：`Filters` 接口 + `createDefaultFilters` 默认值 +
  `buildParams` 传参（`if (x !== null) params.x = x`）+ `CustomerFilters.vue` 下拉与 computed。
- 共享选项常量 `BOOLEAN_FILTER_OPTIONS`（是/否，string value）放 `constants/customerOptions.ts`，
  不要在各页面重复定义。

> **Warning**: FilterDropdown 的「全部」选中时 emit `''`，必须映射回 `null`（不是 `false`），
> 否则「全部」会变成筛选「否」。

---

## a-spin 加载态居中：根元素撑满 + AND 组合选择器

[来源: 2026-09-20 — `EditCustomerDialog.vue` loading 图标偏上/偏左修复]

**现象**：`<a-spin :loading="fetchLoading">` 包裹暂不显示的表单（内容 `v-show` 隐藏）时，
loading 图标不在弹窗内居中——因为 a-spin 根元素高度塌陷。

**根因**：Arco 的 `.arco-spin-loading .arco-spin-mask-icon` 已经用
`top:50%; left:50%; transform:translate(-50%,-50%)` 定位图标；但容器（modal body）塌陷
（内容隐藏 → 高度/宽度为 0），50% 参照就是 0，图标偏到一角。

**修复**（关键两点）：

```vue
<a-spin :loading="fetchLoading" class="edit-dialog-spin">
```

```css
/* 根元素在 loading 时自身带 .arco-spin-loading class（Arco 加在根节点上） */
.edit-dialog-spin.arco-spin-loading {
  display: block;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
}
```

1. **要用 AND 组合选择器 `.edit-dialog-spin.arco-spin-loading`，不是 `:deep(.arco-spin)`**：
   `<a-spin>` 渲染的根元素 **自身**就是 `.arco-spin`（class 合并到同一节点），
   `:deep(.arco-spin)` 后代选择器匹配不到自己 → 样式不生效。
   同样不能选 `.edit-dialog-spin :deep(.arco-spin)`（它要求 `.arco-spin` 是后代）。
2. **用 `height:100%` 对齐 modal body 的 content-box，不要用 `min-height` 硬编码**：
   body `height:600px` + padding 24px 上下 → content 552px；`height:100%` 精确填满内容区，
   mask-icon `top:50%` 即为可视区正中。用 `min-height:600px` 会因 padding 叠加溢出，
   图标仍偏下（dy≈24px）。

> **验证陷阱**：本地 API 很快，加载态一闪而过，浏览器截图往往来不及 —— 用 XHR/fetch
> 拦截延迟响应制造加载窗口再量 `getBoundingClientRect()` 与 body/内容区中心对比；
> 断言 `dy<2px` 且图标中心 ≈ 内容区中心。模态容器 padding 左右可能不对称
> （`paddingRight` 被 body-style 覆盖过），水平对比应参照内容区中心而非 border-box 中心。
