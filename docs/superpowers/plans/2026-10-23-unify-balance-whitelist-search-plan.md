# 统一余额白名单搜索组件样式 Implementation Plan

**创建日期**: 2026-10-23
**状态**: ✅ 完成
**目标**: 将余额白名单页搜索区统一为客户管理页同款 `CustomerSearchInput` 组件，去掉 Arco 搜索按钮，右侧保留蓝色「筛选」按钮。

## Context

余额白名单页面（`frontend/src/views/system/BalanceWhitelist.vue`）的搜索区使用 Arco `a-input`（prefix 图标、`allow-clear`、`width:260px`）+ 独立 `<a-button>搜索</a-button>`，与客户管理页（`CustomerFilters.vue`）及已统一的余额管理页（`BalanceFilters.vue`，源码注释「与客户管理页布局一致」）所使用的自定义 `CustomerSearchInput` 组件视觉风格明显不一致。

目标：将白名单搜索框统一为 `CustomerSearchInput`，去掉 Arco 搜索按钮，右侧保留一个蓝色「筛选」按钮（`.btn.primary`）可点击触发搜索，使其与客户管理页首行搜索区视觉一致。用户已选定「搜索框+筛选按钮」方案。

## Approach

单文件改动 `frontend/src/views/system/BalanceWhitelist.vue`。

### 步骤 1 — 模板替换搜索区（第 19–31 行）

将 `.search-bar` 内现有 Arco 搜索组件：

```html
<div class="search-bar">
  <a-input
    v-model="keyword"
    placeholder="按客户名称 / 公司 ID 搜索"
    allow-clear
    style="width: 260px"
    @press-enter="handleSearch"
    @clear="handleSearch"
  >
    <template #prefix><icon-search /></template>
  </a-input>
  <a-button @click="handleSearch">搜索</a-button>
</div>
```

替换为：

```html
<div class="search-bar">
  <CustomerSearchInput v-model="keyword" @search="handleSearch" />
  <div class="search-actions">
    <button type="button" class="btn primary" @click="handleSearch">筛选</button>
  </div>
</div>
```

- 复用 `CustomerSearchInput`（`@/views/customers/components/CustomerSearchInput.vue`），用法与 `CustomerFilters.vue:5` / `BalanceFilters.vue:5` 完全一致：`v-model="keyword" @search="handleSearch"`。
- placeholder 由组件内置为「搜索客户名称 / 公司 ID」，文案随之统一。
- 宽度由组件内置 `160px`（响应式 `≤1100px` 撑满），与客户管理一致。
- 「筛选」按钮用 `.btn.primary` 自定义样式（与 `CustomerFilters.vue:327-343` 一致），可点击触发 `handleSearch`，保留可点击搜索的可达性。
- 无需新增 FilterDropdown；白名单只有关键字搜索。

### 步骤 2 — 脚本导入调整（第 183 行 / 第 187 行附近）

- 移除第 183 行 `import { IconSearch } from '@arco-design/web-vue/es/icon'`（已确认全文仅第 28 行模板 + 此导入两处使用，移除 a-input 后不再需要）。
- 新增 `import CustomerSearchInput from '@/views/customers/components/CustomerSearchInput.vue'`（参照 `BalanceFilters.vue:119` 写法）。
- `keyword` ref（第 207 行）与 `handleSearch`（第 249–252 行：`pagination.current = 1; loadList()`）已存在，无需改动；`CustomerSearchInput` 的 `v-model` / `@search` 直接复用。

### 步骤 3 — 样式补充（第 498–504 行 `.search-bar` 之后）

`.search-bar` 容器（`display:flex; align-items:center; gap:8px; padding:16px; border-bottom:1px solid var(--soft)`）保留不变。在其后追加右侧按钮组与按钮样式，复制自 `CustomerFilters.vue:319-343`：

```css
.search-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.btn.primary {
  padding: 9px 12px;
  border: 1px solid var(--primary);
  border-radius: 12px;
  background: var(--primary);
  color: white;
  font-weight: 700;
  cursor: pointer;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
  white-space: nowrap;
}
.btn.primary:hover {
  background: #1e40af;
}
```

- `.search-actions { margin-left: auto }` 让筛选按钮靠右（与 `filters-actions` 一致）。
- `CustomerSearchInput` 的 `.search-input-wrap` 等样式由组件 scoped 自带（圆角 12px、聚焦蓝色边框、联想下拉），无需白名单提供，互不干扰。

## Critical files & anchors

- `frontend/src/views/system/BalanceWhitelist.vue` — 改动主体：模板第 19–31 行搜索区、脚本第 183 行导入、样式第 498–504 行后追加。
- `frontend/src/views/customers/components/CustomerSearchInput.vue` — 复用的搜索组件（props: `modelValue: string`；emits: `update:modelValue` / `search` / `select`），自带圆角 12px + 联想下拉样式。
- `frontend/src/views/customers/components/CustomerFilters.vue:319-343` — `.btn.primary` / `.filters-actions` 样式范本（复制源）。

## Verification

仅前端改动，无需后端或数据库变更。工作目录 `frontend/`。

1. `npm run build`（或 `npm run dev` 起开发服务器）确认无编译错误、无 `IconSearch` 未使用告警。
2. 浏览器打开 `/system/balance-whitelist`（以具备 `balance_whitelist:manage` 权限的账号登录）验证：
   - 搜索框为圆角 12px 自定义样式（左侧 SVG 图标、聚焦蓝色边框），宽度 160px，placeholder「搜索客户名称 / 公司 ID」，与客户管理页搜索框外观一致。
   - 右侧蓝色「筛选」按钮，点击后表格重新加载（分页回到第 1 页）。
   - 输入关键字回车 → 触发搜索；输入时出现客户联想下拉，选中联想项 → 自动搜索。
   - 不再有 Arco `a-input` 的 allow-clear 叉号与独立「搜索」按钮。
3. 截图对比客户管理页 `/customers` 搜索框，确认两者外观一致。

## Assumptions & contingencies

- 采用用户选定方案「搜索框+筛选按钮」：去掉独立 Arco 搜索按钮，右侧保留单个蓝色「筛选」按钮可点击触发搜索；本次不加「清除」按钮，如后续需要可再追加。
- 搜索框宽度统一为 `CustomerSearchInput` 内置 160px（原 260px），响应式 `≤1100px` 撑满；这是统一外观的必然结果，如需更宽须改组件本身（不在本次范围）。
- `CustomerSearchInput` 的联想下拉调用 `getCustomers` API，在白名单页同样按客户名/公司 ID 联想，语义适用，无需改组件。

---

## 实施结果（2026-10-23 补记）

三项改动全部按本计划落地，最终 diff 为 `frontend/src/views/system/BalanceWhitelist.vue` 单文件 +32 / −12。

| 验收项 | 结果 |
| --- | --- |
| `npm run build` | ✅ 13.74s 通过，无编译错误、无 `IconSearch` 未使用告警 |
| `npm run type-check`（vue-tsc） | ✅ 零错误零告警 |
| 搜索框圆角 12px / 宽 160px / placeholder「搜索客户名称 / 公司 ID」 | ✅ 计算样式与 DOM 均符合 |
| 「筛选」按钮靠右、蓝色（`#1d4ed8`）、点击后分页回第 1 页并重新请求 | ✅ 点击后请求 `page=1&keyword=紫光` 返回 200 |
| 输入回车 → 触发搜索 | ✅ 发出 `keyword=中原` 请求（200） |
| 客户联想下拉 + 选中自动搜索 | ✅ 8 条联想项；选中「北京巍阁投资管理」后自动发出对应 keyword 请求（200） |
| Arco `a-input` / allow-clear 叉号 / 独立「搜索」按钮已移除 | ✅ `.search-bar` 内 `.arco-input-wrapper` 计数为 0 |
| 与客户管理页 `/customers` 搜索区外观一致 | ✅ 10 项视觉属性（宽度、圆角、边框、背景、内边距、字号、按钮背景/圆角/内边距/字重）逐项对比无差异 |

**遗留说明**：搜索框宽度由 260px 变为组件内置 160px，为统一外观的必然结果；如需更宽须改 `CustomerSearchInput` 组件本身（会影响客户管理页与余额管理页）。本次未加「清除」按钮。
