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
| 导出失败时提示英文 `Bad Request` 而非后端文案 | axios 拦截器错误分支不解析 Blob 错误体（`api/index.ts`） | 已知遗留项，需要时在错误分支对 `Blob` 先 `await blob.text()` 再 `JSON.parse` |
