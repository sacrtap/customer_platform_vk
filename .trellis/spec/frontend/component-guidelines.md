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

### 同一操作的多入口必须同门控（列表行内 vs 详情抽屉）

**基线问题**（2026-11-05，PR #117 review 发现）：`Invoices.vue` 列表行内的「提交」「取消」「客户确认」「重试扣款」4 个按钮**从未有过 `can()` 门控**（仅状态判断），而详情抽屉 `InvoiceDetailDrawer.vue` 的同名操作一直有门控——同一操作两个入口，一个拦一个不拦。无权限用户点列表按钮走到后端才 403，体验上「按钮可见但点击失败」。

**根因（变更方法论盲区）**：权限码切换/整改时用 `grep 'billing:edit'` 之类**以旧码为锚点**定位切换点，天然漏掉「历史上就没有 can() 的按钮」——它们不匹配任何旧码 grep。正确锚点是**操作**：列出页面全部操作按钮 → 对每个按钮核对「后端端点权限码 ↔ 前端 can()」双向存在。

**预期改进（操作按钮审计表）**：改造任一页面按钮权限时，先在 spec/任务文档落一张表再动手：

| 按钮 | 所在入口 | 后端端点 | 后端码 | 前端 can() |
|---|---|---|---|---|
| 提交 | 列表行内 + 抽屉 + 批量工具栏 | submit/batch-submit | `billing:invoice_submit` | 三处都要有 |

多入口（列表行内/详情抽屉/批量工具栏/页头）必须逐格打勾，不允许「抽屉有了就行」——本案例中抽屉全对、行内全无，就是逐格核对抗住的典型。

**验证方式**：非超管身份下对同一状态记录各入口按钮集（DOM 级），与超管身份对比——权限差即按钮差，两者有一处相同即为漏门控。

---

## 页面级异步按钮契约（导出/同步类请求）

导出、同步等**同步阻塞型**请求必须给按钮加「进行中」状态。缺了它，用户会重复点击触发多次请求。

### 首选：`useExportAction` composable

导出类动作（调 `exportXxx` 拿 Blob 再触发下载）**一律用 `useExportAction`**，不要手抄状态与下载代码：

```ts
import { useExportAction } from '@/composables/useExportAction'

const { exporting, run: runExport } = useExportAction({
  exportApi: exportBalances,
  // 传函数以依赖当前筛选条件；传字符串则固定
  filename: () => `balances_${new Date().toISOString().slice(0, 10)}.xlsx`,
  // 有自定义提示时置为 false，改由 onSuccess 接管
  successMessage: false,
  onSuccess: (res) => {
    if (res.headers?.['x-truncated'] === 'true') {
      Message.warning('数据超过 5 万条，仅导出了前 5 万条，请缩小筛选范围后再导出')
    } else {
      Message.success('导出成功')
    }
  },
})

const handleExport = () => runExport(buildExportParams())
```

该 composable 已统一处理：`exporting` 状态与 `try/finally` 复位、Blob 构造、`<a download>` 点击、**延迟 1s 回收 object URL**（Safari/Firefox 会在下载启动前撤销导致失败）、`handleError` 兜底。

| 选项 | 说明 |
|---|---|
| `exportApi` | 导出接口，参数由 `run()` 传入 |
| `filename` | 字符串或函数（函数可读取当前筛选条件） |
| `successMessage` | 默认 `'导出成功'`；`false` 表示不提示（交给 `onSuccess`） |
| `onSuccess(res)` | 收到原始响应，可读 `X-Truncated` 等响应头 |
| `errorMessage` | 失败兜底文案，默认 `'导出失败'` |

### 非导出类异步动作：手写状态

批量提交/删除、下载明细、重新生成等非导出动作用不到 `useExportAction`，按既有范式手写：

```ts
const batchLoading = ref(false)
const onBatchDelete = () => {
  Modal.confirm({
    title: '确认批量删除',
    onOk: async () => {
      batchLoading.value = true
      try {
        await doBatchDelete()
      } catch {
        // 错误消息已由上层处理
      } finally {
        batchLoading.value = false
      }
    },
  })
}
```

```vue
<!-- 页面按钮：禁用 + 文案切换，二者缺一不可 -->
<button class="btn" :disabled="batchLoading" @click="onBatchDelete">批量删除</button>
```

| 要点 | 说明 |
|---|---|
| `finally` 复位 | 只写 try 分支的话，请求失败后按钮会**永久卡在「进行中」** |
| 状态放 composable | 页面级按钮与批量工具栏可能共用同一 handler，状态须从 composable 暴露，两边才能同步 |
| 批量入口同步禁用 | 同一 action 的第二个入口（如批量工具栏的「批量导出」）必须同步 `:disabled`，否则绕过防护 |
| 仅禁自身按钮 | 禁用范围限于触发该 action 的按钮，不要连带禁用页面其他操作（如「刷新」） |
| 共享 loading 的取舍 | 一组互斥的批量按钮可共用一个 `batchLoading`（任一进行中即全禁），避免用户中途切换动作 |

### ESLint 护栏：`local/async-button-loading`

`eslint-rules/async-button-loading.js` 会检查 `<button @click="handleXxx">` 是否绑定了 `:disabled` / `disabled` / `:loading`，命中即报错（CI 阻断）。

- 判据：`@click` 为裸标识符或 `identifier(...)` 调用，且标识符匹配 `^(handle\|on\|run\|do)[A-Z]`
- 白名单 `SYNC_HANDLERS`：确属同步的 handler（打开弹窗、分页、纯前端提示）加进去即可豁免
- **不要把规则关掉了事**——它是这类 bug 的静态防线

> **Warning（一致性陷阱）**：本契约曾被 5 个页面手抄，其中 2 个抄漏（客户管理页、结算单页），
> 另有 9 处其他异步按钮从未实现。新增异步按钮前先跑 `npx eslint .`，确认不触发
> `local/async-button-loading` 再提交。

---

## 常见陷阱

| 现象 | 原因 | 处理 |
|---|---|---|
| 页面白屏，`#app` 只剩 `<!---->`，无 console 报错 | 访问了未定义的路由路径（如 `/billing/balance`，实际路由是 `/billing/balances`），`router-view` 渲染空注释节点 | 核对 `router/index.ts` 的实际 `path`；路径错误不会产生 JS 错误 |
| 断言"弹窗未打开"却读到别的弹窗内容 | 页面 DOM 中同时存在多个 `.arco-modal`（历史弹窗未卸载） | 按可见性过滤：`Array.from(document.querySelectorAll('.arco-modal')).find(x => x.offsetParent !== null)` |
| 导出失败时提示英文 `Bad Request` 而非后端文案 | axios 拦截器错误分支未解析 Blob 错误体 | **已修复**：`api/index.ts` 错误分支对 `Blob` 先 `await data.text()` 再 `JSON.parse`。新增下载链路无需额外处理，但**不要**在拦截器外重复解析 Blob |
| 单测挂载含 `a-modal` 的组件：`wrapper.find('textarea')` 找不到，`attachTo: document.body` 后仍不稳定 | `a-modal` 内容 Teleport 到 body，不在 VTU 组件树内；且真实 modal 打开依赖 rAF，jsdom 下时序不稳 | stub `a-modal` 并透传交互事件（`@before-ok`/`@cancel`）与 `title`，弹窗主体（表单/校验）保持真实组件：`{ props: ['title'], template: '<div><slot /><button @click="$emit(\'before-ok\')">确定</button></div>' }`；参照 `components/__tests__/RollbackModal.test.ts` |

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

## 标签类样式不得按颜色变体单独加 margin（列内左对齐）

[来源: 2026-10-28 — 客户列表「结算方式」列标签未左对齐]

**现象**：客户列表「结算方式」列，预付费（`.tag.green`）标签紧贴单元格左缘，
后付费（`.tag.blue`）标签却向右偏移 6px，两行不对齐。

**根因**：`.tag.blue` 规则里单独写了 `margin-left: 6px`，而 `.tag.green`/
`.tag.amber`/`.tag.red`/`.tag.gray` 都没有——同一组「标签」的视觉变体
（颜色类）被赋予了**不对称的外边距**。这条 `margin-left` 原是为「行业单元格」
里行业名与「重点」蓝标签之间隔而加，但该单元格已用 flex `gap: 6px` 控制间距，
且 `.industry-cell .tag { margin-left: 0 }` 覆盖了它——所以行业单元格内实际不生效，
真正受影响的只有行业单元格**之外**、直接渲染在单元格里的蓝标签（即结算方式列）。

**修复**：删除 `.tag.blue` 上的 `margin-left: 6px`（颜色变体只管配色，不管定位）。
元素间间距一律交给**布局容器**（flex `gap` / grid `gap`）或**局部规则**
（`.industry-cell .tag`），不要写在全局颜色类上。

**规则**：
- 颜色变体类（`.tag.blue/green/...`）只承载 `background`/`color`，**不承载
  `margin`/`padding`/`position` 等布局属性**——否则同一 `.tag` 在不同列里
  因为颜色不同而错位。
- 元素间距用容器 `gap`（flex/grid）统一控制，避免「某颜色标签多一块 margin」
  的隐式偏移；`.industry-cell .tag` 这类局部覆盖若已存在，全局 `margin` 就是
  死代码 + 陷阱。
- 新增一列复用现有 `.tag` 体系时，先 grep 该颜色的全局规则有无布局副作用
  （`grep -n "tag\." *.vue`），再决定是否需要为该列单独加容器。

## 列表页客户列：客户ID + 客户名称双列约定

[来源: 2026-10-30 — 计费规则页「客户」列过宽且缺客户ID，对齐余额管理页]

**约定**：凡需展示「客户」的列表页，一律拆成 **客户ID（`company_id`）+ 客户名称** 两列，
不要用单个宽列把两者挤在一起。已对齐页面：余额管理（`BalanceTable.vue`）、
客户管理（`CustomerTable.vue`）、计费规则（`PricingRules.vue`）。

| 列 | key | width | 样式 |
|---|---|---|---|
| 客户ID | `company_id` | 64 | `.cust-id`：`font-variant-numeric: tabular-nums` + `--muted` 色 + 13px |
| 客户名称 | `customer_name` | 200 | `.cust-name`：`font-weight: 600` + `--ink` 色 |

**要点**：
- **客户ID 列只展示 `company_id`（客户编号），绝不以 DB 内部主键 `customer_id` 兜底**。
  两个字段语义不同：`company_id` 是对外可读编号（导入/导出/搜索的主键列），
  `customer_id` 是 DB 自增主键（用户不可见）。`company_id` 为空就显示空，
  详见 `BalanceTable.test.ts` 的「客户ID 列只展示 company_id，不回退 customer_id」用例。
- 后端列表接口必须显式序列化 `company_id`。计费规则页曾只返回 `customer_id`，
  前端只能拿 DB 主键凑数，误导用户。新增/改造客户相关列表接口时，
  先确认 `company_id` 在响应里（参照 `pricing.py` 列表与 `balances.py`）。
- `customer_name` 为空时显示 `-`（`.subtle`），**不要**拼「客户123」这类
  含 DB 主键的兜底文案（客户ID 已独立成列，再拼一次是冗余且误导）。

### DataTable 列宽陷阱：`scroll.x` 要略大于容器宽度

`DataTable` 底层 `a-table` 用 `table-layout: fixed`，当 `scroll.x` **小于**表格容器
实际宽度时，各列会被**等比拉伸**（例：916px 内容铺进 1086px 容器 → 全部 ×1.185，
配置 64px 的客户ID 实际显示 78px），与参照页面对不齐。

- 设 `scroll.x` 时**量一下页面表格容器宽度**（`.arco-table` 的
  `getBoundingClientRect().width`），让 `scroll.x ≥ 容器宽度`。
- 列宽对齐不要只看 `columnDefs` 的配置值——配置 64/200 但显示 78/243 是拉伸，
  不是配置生效。验证必须读 `.arco-table-th` 的实际 `getBoundingClientRect().width`。
- **`scroll.x` 取「各列 width 之和 + 每列 1px 边框」即精确铺满**，不要拍脑袋给整数。
  实测（2026-11-02 结算单管理页，9 列 + selection 40 + action 175）：
  `40 + 214+180+190+104+76+110+108+78+158 + 175 = 1440`，与
  `.arco-table-th` 实测宽度合计（215/181/191/105/76/111/109/78/159/175，各 +1px）完全吻合。
  给 1410/1500 这类值会分别造成列被拉伸或尾部空白。
- **容器宽度远小于列宽总和时横向滚动条必然出现**，这是既有状态而非回归：结算单页
  容器仅 1325px（1600 视口）/1165px（1440 视口），列总和 1440px。改动前 `scroll.x=1410`
  同样溢出。要让滚动条消失只能缩减列宽，属产品取舍，不要为「消除滚动条」盲目调大
  `scroll.x`（那只会增加滚动量）。

### ellipsis + tooltip 对 slot 渲染内容同样生效

`columnDefs` 加 `ellipsis: true, tooltip: true` 后，`tableColumns` 必须把两个字段
透传给 `DataTableColumn`（`DataTable.vue` 已支持，缺了就静默失效）。对**自定义
slot 渲染**的列（如客户列）同样生效——Arco `table-td.js` 在
`ellipsis && tooltip` 时把内容包进 `AutoTooltip`，DOM 表现为
`<span class="arco-auto-tooltip arco-table-td-content">`（**不是**
`arco-table-text-ellipsis`，后者只在 `ellipsis` 单独为 true 时出现）。

- 验证方式：给该列造一条超长数据，检查 `.arco-auto-tooltip` 的
  `overflow:hidden; white-space:nowrap`，且 `scrollWidth > clientWidth`；
  hover 后 `.arco-tooltip-content` 文本 = 完整值。
- 不溢出的行不挂 tooltip（AutoTooltip 只在溢出时渲染），这是预期行为。

## 列表列文件图标：状态指示不可点击，同构列跨页必须对齐

[来源: 2026-11-05 — VR 结算单列表「文件」列图标可点击跳转，用户反馈去除]

**现象**：VR 编辑费用结算页（`VrSettlements.vue`）列表「文件」列中，明细文件
生成成功后渲染为 `<a :href="detail_file_path" target="_blank">📄</a>`，用户点击
图标即跳转/下载文件链接。而普通结算单页（`Invoices.vue`）同列本就是纯
`<span title="明细文件已生成">📄</span>` 状态指示——**两页同构列行为不一致**，
列表场景下可点图标属误导性交互（用户以为有操作，实际只是状态）。

**根因**：VR 页由普通结算单页复制改造而来，改造时给文件列「加了下载便利」
（span → a），但**两页无共享列定义**，平行演进必然漂移；普通单页侧从未跟进。
本质是「有文件路径 ⇒ 应提供下载入口」的隐式假设，未区分**列表=状态指示区**、
**抽屉/弹窗=操作区**两个语义层。

**规则**：
- **列表列中的文件/附件图标一律纯展示**（`<span>` + `title`），不可点击；
  下载入口只放详情抽屉/弹窗附件区（显式文字链接，如「当前附件」「下载明细」）。
  已验证正确的现存实现：`Invoices.vue` detail_file 列、
  `VrSettlementDetailDrawer.vue` 附件区。
- **同构列跨页必须对齐**：VR 结算单与普通结算单是同一业务的两个平行列表页
  （同状态机、同操作集、同列集），改一页的列定义/交互时，**必须 grep 另一页
  的同名列并同步**（`grep -n "detail_file" src/views/billing/`），不允许
  「只改一页」。同理适用于其他成对页面（如后续新增的结算单变体页）。
- 新增/改造列交互前先问：这个交互属于**状态指示**（列内）还是**操作**（按钮/
  链接）？列内图标承载操作是漂移高发区——操作请挪到抽屉或用带文字的按钮。

**验证方式**：浏览器实测列表页 `document.querySelectorAll('td a[href]').length`
应为 0（无文件的行动态列除外）；对比修复前后同状态行的 DOM 标签
（`a` → `span`）。

## a-table 排序词表映射：Arco `ascend/descend` → 后端 `asc/desc`

[来源: 2026-10-31 — 客户管理页点击表头排序报 `Invalid sort order: ascend`]

**现象**：客户管理列表点击任意可排序列头，请求报错 `Invalid sort order: ascend`，列表无法排序。

**根因**：Arco `a-table` 三态排序词表是 `'ascend' | 'descend' | ''`，`DataTable.vue`
把 `sorter-change(dataIndex, direction)` **原样透传**给页面组件（见 `DataTable.test.ts`
的「sorter-change 冒泡到宿主组件监听器」用例，透传的就是 `'ascend'`）。若页面组件
把 `direction` 原样 emit 出去，下游 `useCustomerList.handleSort` 会用
`direction as 'asc' | 'desc'` 断言把 `'ascend'` 当真存进 `sortOrder`，`buildParams`
遂发出 `sort_order=ascend`；后端 `services/customers.py` 严格校验
`sort_order in {"asc","desc"}`（`VALID_SORT_ORDERS`）直接抛 `ValueError`，
路由转 `{code:40001}`。

**约定**：**排序词表映射必须在组件 emit 出口完成**（页面组件的 `onSorterChange`），
不要把 Arco 词表透传进 composable / 请求层。composable 的
`sortOrder: ref<'asc'|'desc'>` 与 `handleSort` 都按后端词表设计，`as` 断言只是掩盖类型错配。

```ts
// CustomerTable.vue onSorterChange（正确）
const onSorterChange = (dataIndex: string, direction: string) => {
  if (direction !== 'ascend' && direction !== 'descend') {
    emit('sortChange', '', '') // 清除排序，见下方陷阱
    return
  }
  const order = direction === 'ascend' ? 'asc' : 'desc'
  emit('sortChange', dataIndex, order)
}
```

> **Warning（取消排序回传列 key，不是空串）**：实测 a-table 第三态（取消排序）回调的
> `direction` 是 `''`，但 **`dataIndex` 仍回传列 key**（如 `('company_id', '')`），
> **并非** `('', '')`。若把 `dataIndex` 直接透传，取消排序时会 emit `('company_id', '')`——
> 语义矛盾（有字段却无方向）。必须在取消分支显式 `emit('sortChange', '', '')`，
> 与 `BalanceTable.vue#242-249` 的既有契约保持一致。`handleSort` 只据 `direction`
> 判空恢复默认排序、忽略 `dataIndex`，故两种写法都不会把非法值发给后端，但 `('', '')`
> 才是干净且跨组件一致的契约。

**为什么仅客户页报错**：`balances.py#890` 与 `invoices.py#139` 在路由层把无效 `sort_order`
归一化回 `asc`/`desc`，掩盖了前端词表不一致；`customers.py#124` **不归一化**，直接交给
service 严格校验才暴露。**新增排序列表时，即使后端会兜底，也应在组件出口映射词表**，
不要依赖后端归一化——否则换个不归一化的后端就复现同类 bug。

**回归测试**：`views/customers/components/__tests__/CustomerTable.test.ts` 点击「客户ID」
表头三次，依次断言 emit `['company_id','asc']` / `['company_id','desc']` / `['','']`。
新增可排序列表一律补这套三态断言，锁死词表映射。

---

## 状态机时间线：共享哑渲染层 + 共享状态推导（单一 owner）

**模式**（2026-11-03 落地，2026-11-04 收敛状态推导）：

- `components/common/timelineStatus.ts`：**状态推导的单一 owner**。
  `resolveTimelineNodeStyle(node, status, hasTime)` 输入节点定义（field/label/statusKey/operatorField/detailParts）
  与单据 status，输出 `dotColor` / `textClass`；`TIMELINE_STYLES` 是四种配色
  （current/completed/pending/cancelled）的唯一常量源。规则：
  completed 终态全部 completed、无 current；cancelled 时流程节点按 completed 展示，取消节点由调用方
  以 `TIMELINE_STYLES.cancelled` 追加；其余状态 `statusKey` 命中 `status` 的节点为 current，
  已发生但未命中的为 completed，无时间戳的为 pending。
- `components/common/StatusTimeline.vue`：**哑渲染**，props 只收 `events: TimelineEvent[]`
  （label/time/operator/detailParts/dotColor/textClass），不含任何业务判断
- 业务 wrapper（`components/invoice/InvoiceTimeline.vue`、`components/vr/VrSettlementTimeline.vue`）：
  只保留流程节点表（field/label/statusKey/operatorField/detailParts）与数据映射（时间格式化、操作人、
  减免历史），**禁止**各自实现 `allCompleted` / `currentRemIndex` / `isCurrent` / `dotColor` 判定；
  颜色一律取自 `TIMELINE_STYLES`
- 新单据类型接时间线 = 新建 wrapper + 节点表，**不要复制整条渲染链，也不要复制状态判定**

**completed 终态判定陷阱（2026-11-03 一天内复发两次）**：

旧判定 `isCompleted = timeValue && index !== currentRemIndex` 在 completed 终态把末节点误判为未到达灰色。
VR 侧随时间线新建时修，Invoice 侧随后又单独修一次——根因是判定在两个消费方各存一份。
现状唯一实现是 `resolveTimelineNodeStyle`：`status === 'completed'` 直接返回 completed，不存在 current 分支。

```ts
// 共享层（唯一实现）
if (!hasTime) return TIMELINE_STYLES.pending
if (status === 'completed' || status === 'cancelled') return TIMELINE_STYLES.completed
return node.statusKey === status ? TIMELINE_STYLES.current : TIMELINE_STYLES.completed
```

回归测试：`components/common/__tests__/timelineAssertions.ts` 的 `expectCompletedTerminalTimeline()`
被 `components/invoice/__tests__/InvoiceTimeline.test.ts` 与
`components/vr/__tests__/VrSettlementTimeline.test.ts` 的 completed 用例共同复用，断言末节点为
`completed-event` 且无 current/pending。新增时间线 wrapper 必须接入同一共享断言——
旧缺陷正是「只有中间态测试、缺终态断言」才得以潜伏。

**测试要求**：新时间线 wrapper 必须覆盖三态——已完成全绿（终态无 current）、
当前节点蓝色高亮、取消末位红节点；减免历史插在「创建」节点之后（后端倒序返回需反转）。

---

## 共享组件外观归属：样式必须随结构一起搬 + 专属根类名（2026-11-03 减免历史样式二次不一致）

**现象**：`DiscountHistoryTable.vue` 抽成共享组件、两个详情抽屉（VR 结算单 / 结算单管理）
同时接入后，两处渲染仍不一致——结算单管理侧的历史表格**多一圈边框 + 15px 圆角**，
标题字号也不同（16px/600 vs 14px/700）。用户实测发现，第一轮"统一"只统一了结构。

**根因（Vue 3 scoped 的穿透规则）**：scoped 样式编译后为 `.sel[data-v-parent]`，而
**子组件的根元素同时带父组件的 scope id**。共享组件的根元素原本叫 `.table-wrap`：

- 结算单管理抽屉父组件保留 `.table-wrap { border: 1px solid var(--line); border-radius: 15px; }`
  （给「计费明细」表用）→ **穿透命中**共享组件根元素 → 历史表格被"美化"
- VR 抽屉父组件的 `.table-wrap` 在抽组件时被删掉 → 同一个组件裸奔

组件内部的 `table/th/td` 不是根元素，不带父 scope id，所以父规则不命中——**只有根元素被穿透**，
这正是"看起来结构一样、外框却不同"的原因。

**契约（抽共享展示组件时逐条执行）**：

1. **外观归属单一**：组件要么自带**全部**外观（标题、外框、边框、圆角、单元格样式），
   要么完全不带；**禁止**"结构在组件、装饰在父组件"——两侧父组件样式必然漂移。
2. **根元素用专属类名**（如 `.discount-history`），**不要复用**父组件里已有的通用类
   （`.table-wrap`/`.table`/`.detail-section`/`.section-header`），否则父 scope id 必然穿透。
3. **父组件模板不再包裹**：`<DiscountHistoryTable v-if="list.length > 0" :histories="list" />`，
   不要再套 `<div class="detail-section"><div class="section-header"><h3>…</h3></div>`——
   区块标题由组件自带，否则标题样式仍是父组件的（字号/字重继续漂移）。
4. **验收用 computed style 结构化对比**，不能只看截图：
   取同一组属性（标题 fontSize/fontWeight/color/margin、容器 border*/borderRadius/overflow、
   单元格 padding/borderBottom/textAlign/whiteSpace、金额色、列宽）逐项比对，
   输出 `none — 完全一致` 才算通过。注意排除 `getBoundingClientRect` 尺寸项
   （行数不同导致的差异不是样式差异）。

**修复后基线（两处完全一致）**：标题 `16px/600/var(--ink)` + header `flex/space-between`
`margin-bottom:12px`；容器 `1px solid var(--line)` + `border-radius:15px` + `overflow:auto`；
表格 `13px`、`th/td padding 8px 10px`、`border-bottom 1px #e5e7eb`、列宽 `160/110/316/100`。

**同类残留**：抽屉级 `.section-header h3` 也必须两侧一致（本次把 VR 侧 14px/700 对齐为
16px/600 + `color: var(--ink)`），否则同一抽屉内「操作记录」标题仍与另一侧不同。

---

## 平行详情页外观一致性：抽屉级公共样式必须单源（2026-11-03 VR 结算单 vs 结算单管理整体样式）

**现象**：抽完共享组件后，用户再要求「两个详情抽屉**整体样式**一致」，实测仍有 12 处差异——
内容区间距 16px/24px、标题 18px/20px（且 VR 未设 `color: var(--ink)`）、
**VR 状态条完全没有背景/边框/圆角**（模板有 `.flow-steps` 但样式区无该规则）、
steps 标题 16px/13px、description `maxWidth 140px/clip` vs `100px/ellipsis`、
「操作记录」标题头 `block` vs `flex/space-between + margin-bottom:12px`、
最终金额 14px/600 vs 16px/700、`.subtle` `#94a3b8` vs `var(--muted)`、
附件链接无/有下划线、操作区 `flex-wrap + padding-top:8px + var(--border)` vs
`flex-end + 16px + var(--line)`、按钮 padding `9px 12px` vs `9px 16px`（且 VR 无 transition、
`.btn.disabled` 缺 `pointer-events:auto` 与 `:hover` 保持主色）。

**根因**：两个平行抽屉各自维护一份几乎相同的 CSS（C 类：变更传播失败），
没有单一来源——只修一侧就会再漂移。**只对齐数值不算修复**。

**方案：公共规则抽到 `frontend/src/styles/detail-drawer.css`，两组件在 `<style scoped>` 内 `@import`。**

**已实测的关键事实（勿再试探）**：

1. Vite + `@vitejs/plugin-vue` 会把 `<style scoped>` 里的 `@import` **内联进该 scoped 块**，
   随后统一加 scope id。CSSOM 验证：共享的 24 条规则**全部**带 `[data-v-*]`，**0 条泄漏为全局**；
   列表页自有的 `.btn { padding: 9px 12px }` 未被共享的 `9px 16px` 覆盖。
2. `@import` 必须位于 style 块**最顶部**（仅注释可前置），否则 CSS 规范要求浏览器忽略它。
3. **`:deep()` 不能放进共享文件**——它是 SFC 编译期语法，@import 内联与 scoped 插件的执行顺序不可依赖。
   `:deep(.arco-steps*)` 三条仍各组件内联维护（重复但短，且是 Arco 内部结构）。
4. 组件特有规则留在各自文件：VR 的 `.remark-text`；Invoice 的 `.table-wrap/.table`、
   `.amount`、`.pricing-*`、`.rule-detail`、`.empty-state` 等。

**明细文件区必须同构**（2026-11-03 补）：两个抽屉都用
`.detail-file-section`（flex/align-center/gap 8px）+ `.file-status.{completed|generating|failed|pending}`
+ `.btn.btn-sm`（padding 4px 10px / 12px / radius 8px）「下载明细」按钮，三者均在 `detail-drawer.css` 单源。
**禁止**用裸 `<a>` 链接下载（VR 侧曾如此：`<a :href="detail_file_path" download>{{ detail_file_name }}</a>`，
既无状态文本也无按钮，与结算单管理的按钮交互不一致）。VR 明细文件是创建时上传的静态文件，
无生成状态机，只用「✅ 已生成 / — 无明细文件」两态，且无「重新生成」按钮（那是 Invoice 专属）。
下载实现：`document.createElement('a')` + `href = detail_file_path` + `download = detail_file_name` + `target="_blank"`，
同源 `/uploads/**` 由 vite proxy 转发后端静态服务。

**契约**：

1. 抽屉级公共类（`.drawer-content`/`.detail-title`/`.flow-steps`/`.flow-cancelled`/
   `.section-header`/`.amount-final`/`.text-danger`/`.text-success`/`.attachment-link`/
   `.subtle`/`.action-section`/`.detail-file-section`/`.file-status.*`/`.btn` 系列含 `.btn-sm`）
   **只允许在 `detail-drawer.css` 定义一次**；
   组件内不得再出现同选择器（重复定义 = 下次漂移的入口）。
2. 新增/修改抽屉公共样式，**只改共享文件**；改完必须复测两个抽屉。
3. 删除某侧不再使用的规则时，先确认另一侧也不依赖（`grep` 类名在模板中的出现）。
4. **验收两步**，缺一不可：
   - **一致性**：同一组元素在两抽屉取 computed style 逐项 diff（`drawer width`、`content gap`、
     `title fontSize/fontWeight/color`、`flow background/border/borderRadius/padding`、
     `step title/description fontSize+maxWidth+textOverflow`、`section-header display/justifyContent/marginBottom`、
     `h3 fontSize/fontWeight/color`、`amount-final fontSize/fontWeight/color`、`subtle color`、
     `action-section justifyContent/paddingTop/borderTopColor`、`btn padding/borderRadius/fontWeight/transitionDuration`、
     descriptions label/value 的 `padding/backgroundColor/fontSize`），输出 `none — 完全一致`。
   - **无泄漏**：遍历 `document.styleSheets` 收集匹配 `.btn|.drawer-content|.action-section|.section-header`
     的规则，断言全部含 `[data-v-`；再抽查一个列表页按钮 padding 未被共享值覆盖。
5. 数据差异导致的「元素缺失」（如某单据无减免 → 无 `.subtle` 节点）**不是样式差异**，
   换一个含该元素的单据复测，不要为了对齐往抽屉里塞占位元素。

**修复后基线（两抽屉 computed style 完全一致）**：`drawer 720px`；`content gap 24px`；
`title 20px/700/rgb(15,23,42)`；`flow bg rgb(248,250,252) + 1px rgb(226,232,240) + radius 12px + padding 16px 20px 6px`；
`step title 13px`；`step desc 12px/maxWidth 100px/ellipsis/nowrap`；
`section-header flex/space-between + margin-bottom 12px`；`h3 16px/600`；
`amount-final 16px/700`；`action-section flex-end + padding-top 16px + 1px var(--line)`；
`btn padding 9px 16px + radius 12px + transition 0.2s×3`；`desc label/value padding 3px 20px`；
`detail-file-section flex/gap 8px` + `btn-sm padding 4px 10px/12px/radius 8px`（「下载明细」两侧一致）。

---

## 受控 file-list 与上传错误处理契约（2026-11-03 三弹窗同款缺陷修复）

**Bug 症状**：创建/编辑弹窗选择附件后，「移除」按钮点击无效（文件条目残留）；上传失败时只显示统一文案「附件上传失败」，真实原因（无权限 / 大小超限 / 类型不符）不可见。

**两条契约**（`a-upload` + 手动上传模式）：

1. **`@change` 必须无条件同步受控列表**——Arco 在用户点移除时回传**空数组**，
   守卫 `if (list.length > 0)` 会把这次清空忽略掉：

   ```ts
   // 错误（三处同款缺陷）：移除无效
   const handleFileChange = (list) => {
     if (list && list.length > 0) form.attachment = list[0].file
   }

   // 正确：空数组自然落到 undefined，选中/移除语义统一
   const handleFileChange = (list) => {
     form.attachment = list?.[0]?.file
   }
   ```

2. **上传失败的 catch 必须走 `handleError(error, fallback)`**——禁止
   `catch { Message.error('统一文案') }`。拦截器已把后端错误归一为
   `{ code, message }`，`getUserFriendlyMessage` 对 400 类（参数/业务错误）
   **透传后端 message**；吞掉它等于把「文件大小超过限制 (10MB)」「不支持的文件类型」
   「您没有执行此操作的权限」降级为无法行动的统一文案：

   ```ts
   // 正确
   } catch (error) {
     handleError(error, '附件上传失败') // fallback 仅在错误形状无法解析时生效
     return false
   }
   ```

**系统性排查结论**（break-loop）：全仓 `catch { Message.error(...) }` 模式 10 余处，
按场景分类处理——

| 场景 | 位置 | 处置 |
|---|---|---|
| 附件上传（3 处） | `VrSettlementCreateModal` / `DiscountEditModal` / `SubmitModal` | **已全部修复**（2026-11-03） |
| 页面数据加载失败 | `Profile.vue` 等 | 保留 fallback（加载类无更细粒度后端文案可透传） |
| 下载/导出失败 | `InvoiceDetailDrawer` 等 | 保留 fallback（blob 错误对用户无可读信息） |

**新增上传组件检查单**：受控列表空数组同步、错误走 handleError、测试覆盖
「移除清空 / 失败透传 / 成功路径」三态（参考
`views/billing/components/__tests__/VrSettlementCreateModal.upload.test.ts`）。

### 覆盖 `a-upload` 内部样式的 DOM 事实（2026-11-03 选择器误判校准）

直觉命名与真实 DOM 不符，写 `:deep()` 前必须浏览器 computed style 实测：

| 元素 | 真实 class | 易错写法 |
|---|---|---|
| 列表/触发器容器 | `.arco-upload-wrapper`（有宽度） | `.arco-upload`（是 **display:none 的隐藏 trigger**，设 width 无效） |
| 删除图标（text 类型） | `.arco-upload-icon-remove` | `.arco-upload-list-remove-icon`（picture 类型才叫这个，text 类型不存在） |
| ▶ 开始按钮 + 进度圈 | `.arco-upload-progress`（内含 `arco-upload-icon-start`） | 不存在 `.arco-upload-list-preview-icon`（text 类型无预览按钮） |

`auto-upload="false"` 场景下 `.arco-upload-progress`（进度圈 + ▶ 开始图标）对用户无意义，可直接隐藏。

### 把 Arco upload 操作按钮收进自定义容器的 flex 链要求

给 `.arco-upload-list-item` 做输入框外观后，删除按钮仍被挤出框外——只给最内层
`.arco-upload-list-item-name-text` 设 `flex:1; min-width:0` **不够**，`content`/`name`
两级容器默认 `min-width:auto` 不收缩。必须整链设置：

```css
:deep(.arco-upload-list-item-content),
:deep(.arco-upload-list-item-name),
:deep(.arco-upload-list-item-name-text) {
  flex: 1;
  min-width: 0;
}
```

另：元素截图形状贴近边框时有视觉误判，几何判定（`getBoundingClientRect` 对比）与整弹窗截图才是可靠证据。

### upload 文件条目输入框化的三个内置样式陷阱

`.arco-upload-list-item` 做成输入框外观时，Arco 内置样式会叠出丑陋层叠：

1. **`content` 自带灰底**：`.arco-upload-list-item-content` 内置
   `background-color: var(--color-fill-1)` + `padding: 8px 0 8px 12px`——
   在自定义边框内又叠一层「框中框灰条」。必须 `background-color: transparent; padding: 0`。
2. **无效 fallback 值**：`background: var(--fg) 0a` 这类写法——变量未定义
   （项目只有 `--primary`，无 `--fg`/`--accent`）时整个声明 invalid，静默变透明。
   自定义控件对齐 a-input 用 Arco token：背景 `var(--color-fill-2)`、
   hover 边框 `var(--primary)`（与 arco-theme.css 的 input 规则一致）。
3. **name-text 的 cursor:pointer**：Arco 内置给链接场景用，手动上传不可点击文件名，
   改 `cursor: default` 避免误导。
