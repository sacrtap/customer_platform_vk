# Phase 0: 基础层统一 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一全局基础层（设计令牌、全局样式、布局组件、通用组件），为后续 Phase 1-4 页面重构奠定基础。

**Architecture:** 清除死文件 td002-component-styles.css，迁移旧别名变量到原型令牌，补充缺失工具类，创建 6 个通用页面组件，验证布局组件对齐原型。

**Tech Stack:** Vue 3 + Arco Design + TypeScript + Vite + Vitest + Playwright

## Global Constraints

- 文件修改前必须先读取（项目硬规则）
- Python 3.12.x（后端，本 Phase 不涉及）
- 所有 API 端点添加 `@auth_required`（后端，本 Phase 不涉及）
- 思考过程及会话内回复必须使用中文
- pre-commit 脚本使用 `$BACKEND_DIR/.venv/bin/python`

## File Structure

**Files to create:**
- `frontend/src/components/PageHeader.vue` — 页面标题 + 副标题 + 操作按钮组
- `frontend/src/components/FilterSection.vue` — 白色卡片筛选区容器
- `frontend/src/components/TableSection.vue` — 表格容器（圆角 + 表头样式）
- `frontend/src/components/ChartCard.vue` — 图表卡片（标题 + 内容区）
- `frontend/src/components/BatchToolbar.vue` — 批量操作工具栏
- `frontend/src/components/QuickFilterTags.vue` — 快速筛选标签组

**Files to modify:**
- `frontend/src/styles/global.css` — 补充工具类，最终删除 backward-compat 别名
- `frontend/src/components/EmptyState.vue` — 迁移 `--neutral-*` → 原型令牌
- `frontend/src/components/ActionButton.vue` — 迁移 `--neutral-*` / `--danger-*` → 原型令牌
- `frontend/src/components/SkeletonCard.vue` — 迁移 `--neutral-*` → 原型令牌
- `frontend/src/components/layout/AppSidebar.vue` — 验证/对齐原型样式
- `frontend/src/components/layout/AppHeader.vue` — 验证/对齐原型样式
- `frontend/src/views/system/AuditLogs.vue` — 迁移 `--neutral-*` → 原型令牌
- `frontend/src/views/system/IndustryTypes.vue` — 迁移 `--neutral-*` → 原型令牌
- `frontend/src/views/system/SyncLogs.vue` — 迁移 `--neutral-*` → 原型令牌
- `frontend/src/views/system/DatabaseManagement.vue` — 迁移 `--neutral-*` → 原型令牌
- `frontend/src/views/customers/detail/CustomerProfileTab.vue` — 迁移 `--neutral-*` → 原型令牌

**Files to delete:**
- `frontend/src/styles/td002-component-styles.css` — 死文件（未被任何地方导入）

---

### Task 1: 删除死文件 td002-component-styles.css

**Files:**
- Delete: `frontend/src/styles/td002-component-styles.css`

**Interfaces:**
- Consumes: 无（该文件未被任何地方导入，grep 确认无引用）
- Produces: 无

- [ ] **Step 1: 确认文件未被导入**

Run: `cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && grep -r "td002" frontend/src/ --include="*.ts" --include="*.vue" --include="*.css" -l`
Expected: 无输出（确认无引用）

- [ ] **Step 2: 删除文件**

Run: `rm frontend/src/styles/td002-component-styles.css`

- [ ] **Step 3: 验证前端构建正常**

Run: `cd frontend && npm run build`
Expected: 构建成功，无错误

- [ ] **Step 4: 验证类型检查通过**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 5: 提交**

```bash
git add frontend/src/styles/td002-component-styles.css
git commit -m "refactor: remove dead td002-component-styles.css file"
```

---

### Task 2: 迁移 EmptyState.vue 到原型令牌

**Files:**
- Modify: `frontend/src/components/EmptyState.vue`

**Interfaces:**
- Consumes: `global.css` 中的 `:root` 令牌变量
- Produces: 不再依赖 backward-compat 别名 `--neutral-3` / `--neutral-9` / `--neutral-5`

**变量映射:**
| 旧变量 | 新变量 |
|--------|--------|
| `--neutral-3` | `var(--line)` |
| `--neutral-5` | `var(--muted)` |
| `--neutral-9` | `var(--ink)` |

- [ ] **Step 1: 读取当前文件**

Read: `frontend/src/components/EmptyState.vue`

- [ ] **Step 2: 替换 scoped CSS 中的旧变量**

将 `<style scoped>` 中的以下内容替换：

```css
/* 旧 */
.empty-state-icon { color: var(--neutral-3); }
.empty-title { color: var(--neutral-9); }
.empty-description { color: var(--neutral-5); }

/* 新 */
.empty-state-icon { color: var(--line); }
.empty-title { color: var(--ink); }
.empty-description { color: var(--muted); }
```

- [ ] **Step 3: 验证构建正常**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/EmptyState.vue
git commit -m "refactor: migrate EmptyState.vue to prototype design tokens"
```

---

### Task 3: 迁移 ActionButton.vue 到原型令牌

**Files:**
- Modify: `frontend/src/components/ActionButton.vue`

**Interfaces:**
- Consumes: `global.css` 中的 `:root` 令牌变量
- Produces: 不再依赖 backward-compat 别名

**变量映射:**
| 旧变量 | 新变量 |
|--------|--------|
| `--neutral-1` | `var(--bg)` |
| `--neutral-6` | `var(--muted)` |
| `--neutral-9` | `var(--ink)` |
| `--neutral-10` | `var(--ink)` |
| `--danger-5` | `var(--red)` |

- [ ] **Step 1: 读取当前文件**

Read: `frontend/src/components/ActionButton.vue`

- [ ] **Step 2: 替换 scoped CSS 中的旧变量**

将 `<style scoped>` 中所有 `--neutral-*` 和 `--danger-*` 替换为原型令牌：

```css
.header-action { color: var(--muted); }  /* 旧: --neutral-6 */
.header-action:hover { background: var(--bg); color: var(--ink); }  /* 旧: --neutral-1, --neutral-9 */
.action-badge { background: var(--red); }  /* 旧: --danger-5 */
.tooltip { background: var(--ink); }  /* 旧: --neutral-10 */
.tooltip::before { background: var(--ink); }  /* 旧: --neutral-10 */
```

- [ ] **Step 3: 验证构建正常**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/ActionButton.vue
git commit -m "refactor: migrate ActionButton.vue to prototype design tokens"
```

---

### Task 4: 迁移 SkeletonCard.vue 到原型令牌

**Files:**
- Modify: `frontend/src/components/SkeletonCard.vue`

**Interfaces:**
- Consumes: `global.css` 中的 `:root` 令牌变量
- Produces: 不再依赖 backward-compat 别名

**变量映射:**
| 旧变量 | 新变量 |
|--------|--------|
| `--neutral-1` | `var(--bg)` |
| `--neutral-2` | `var(--soft)` |

- [ ] **Step 1: 读取当前文件**

Read: `frontend/src/components/SkeletonCard.vue`

- [ ] **Step 2: 替换 scoped CSS 中的旧变量**

将 `<style scoped>` 中所有 `--neutral-1` 替换为 `var(--bg)`，`--neutral-2` 替换为 `var(--soft)`：

```css
.skeleton-card { border: 1px solid var(--soft); }  /* 旧: --neutral-2 */
.skeleton-line {
  background: linear-gradient(90deg,
    var(--bg) 0%,      /* 旧: --neutral-1 */
    var(--soft) 25%,   /* 旧: --neutral-2 */
    var(--bg) 50%,     /* 旧: --neutral-1 */
    var(--soft) 75%,   /* 旧: --neutral-2 */
    var(--bg) 100%     /* 旧: --neutral-1 */
  );
}
/* reduced motion fallback */
.skeleton-line { background: var(--soft); }  /* 旧: --neutral-2 */
```

- [ ] **Step 3: 验证构建正常**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/SkeletonCard.vue
git commit -m "refactor: migrate SkeletonCard.vue to prototype design tokens"
```

---

### Task 5: 迁移页面级文件中的旧别名变量

**Files:**
- Modify: `frontend/src/views/system/AuditLogs.vue`
- Modify: `frontend/src/views/system/IndustryTypes.vue`
- Modify: `frontend/src/views/system/SyncLogs.vue`
- Modify: `frontend/src/views/system/DatabaseManagement.vue`
- Modify: `frontend/src/views/customers/detail/CustomerProfileTab.vue`

**Interfaces:**
- Consumes: `global.css` 中的 `:root` 令牌变量
- Produces: 不再依赖 backward-compat 别名

**变量映射（通用）:**
| 旧变量 | 新变量 |
|--------|--------|
| `--neutral-1` | `var(--bg)` |
| `--neutral-2` | `var(--soft)` |
| `--neutral-3` | `var(--line)` |
| `--neutral-5` | `#94A3B8`（无直接令牌，用 hex 或定义新令牌） |
| `--neutral-6` | `var(--muted)` |
| `--neutral-7` | `#334155`（用 hex） |
| `--neutral-9` | `var(--ink)` |
| `--neutral-10` | `var(--ink)` |
| `--danger-5` | `var(--red)` |
| `--danger-6` | `var(--red)` |
| `--primary-5` | `var(--primary-2)` |
| `--primary-6` | `var(--primary)` |
| `--primary-7` | `#1E40AF` |
| `--success-5` | `#34D399` |
| `--success-6` | `var(--green)` |
| `--warning-5` | `#FBBF24` |
| `--warning-6` | `var(--amber)` |

- [ ] **Step 1: 读取所有需迁移文件**

Read: `frontend/src/views/system/AuditLogs.vue`
Read: `frontend/src/views/system/IndustryTypes.vue`
Read: `frontend/src/views/system/SyncLogs.vue`
Read: `frontend/src/views/system/DatabaseManagement.vue`
Read: `frontend/src/views/customers/detail/CustomerProfileTab.vue`

- [ ] **Step 2: 逐文件替换旧变量**

对每个文件中的 `<style scoped>` 部分，使用上表的变量映射进行替换。使用 `string_replace` 工具逐个替换。

- [ ] **Step 3: 验证构建正常**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 4: 验证类型检查通过**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/system/AuditLogs.vue frontend/src/views/system/IndustryTypes.vue frontend/src/views/system/SyncLogs.vue frontend/src/views/system/DatabaseManagement.vue frontend/src/views/customers/detail/CustomerProfileTab.vue
git commit -m "refactor: migrate page-level files from old alias variables to prototype tokens"
```

---

### Task 6: 补充 global.css 缺失工具类

**Files:**
- Modify: `frontend/src/styles/global.css`

**Interfaces:**
- Consumes: 已有的 `:root` 令牌变量
- Produces: `.mini` / `.ia` / `.prototype-note` / `.chart-placeholder` 工具类

- [ ] **Step 1: 读取当前文件**

Read: `frontend/src/styles/global.css`

- [ ] **Step 2: 在 `.pad` 类后面追加缺失工具类**

在 `global.css` 中 `.pad` 定义之后，添加：

```css
/* ---- KPI Compact Card (design.md 3.12) ---- */
.mini {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 11px;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mini > span {
  font-size: 13px;
  color: var(--muted);
}

.mini > b {
  font-size: 22px;
  font-weight: 850;
  color: var(--ink);
}

.mini > .subtle {
  font-size: 12px;
}

/* ---- Information Architecture Grid (design.md 3.26) ---- */
.ia {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.ia .card {
  padding: 14px;
}

.ia .card h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.ia .card ul {
  margin: 0;
  padding-left: 18px;
  color: var(--muted);
  font-size: 13px;
}

/* ---- Prototype Note (design.md 3.27) ---- */
.prototype-note {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.prototype-note .wire {
  border: 1px dashed #BFDBFE;
  border-radius: 16px;
  padding: 12px;
  background: #F8FBFF;
}

/* ---- Chart Placeholder (design.md 3.21.5) ---- */
.chart-placeholder {
  padding: 40px 20px;
  text-align: center;
  color: var(--muted);
  background: var(--bg);
  border-radius: 12px;
  font-size: 13px;
}
```

- [ ] **Step 3: 补充响应式规则**

在已有的 `@media (max-width: 1100px)` 块中追加：

```css
  .ia,
  .prototype-note {
    grid-template-columns: 1fr;
  }
```

- [ ] **Step 4: 验证构建正常**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 5: 提交**

```bash
git add frontend/src/styles/global.css
git commit -m "style: add missing utility classes (.mini, .ia, .prototype-note, .chart-placeholder)"
```

---

### Task 7: 删除 global.css 中的 backward-compat 别名

**Files:**
- Modify: `frontend/src/styles/global.css`

**Interfaces:**
- Consumes: Task 2-5 已完成（所有文件不再引用旧别名）
- Produces: `global.css` 不再包含 backward-compat 别名段

- [ ] **Step 1: 确认无文件引用旧别名**

Run: `cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && grep -r "neutral-[0-9]" frontend/src/ --include="*.vue" --include="*.ts" | grep -v "global.css"`
Expected: 无输出（所有文件已迁移）

- [ ] **Step 2: 删除 backward-compat 别名段**

读取 `frontend/src/styles/global.css`，删除以下部分：

```css
  /* ---- Backward-compat aliases (兼容期，逐步迁移) ---- */
  --primary-1: #DBEAFE;
  --primary-5: #2563EB;
  --primary-6: #1D4ED8;
  --primary-7: #1E40AF;
  --neutral-1: var(--bg);
  --neutral-2: var(--soft);
  --neutral-3: var(--line);
  --neutral-5: #94A3B8;
  --neutral-6: var(--muted);
  --neutral-7: #334155;
  --neutral-9: #1E293B;
  --neutral-10: var(--ink);
  --success-1: #DCFCE7;
  --success-5: #34D399;
  --success-6: var(--green);
  --warning-1: #FEF3C7;
  --warning-5: #FBBF24;
  --warning-6: var(--amber);
  --danger-1: #FEE2E2;
  --danger-5: #F87171;
  --danger-6: var(--red);
```

- [ ] **Step 3: 验证构建正常**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 4: 验证类型检查通过**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 5: 提交**

```bash
git add frontend/src/styles/global.css
git commit -m "refactor: remove backward-compat alias variables from global.css"
```

---

### Task 8: 创建 PageHeader 组件

**Files:**
- Create: `frontend/src/components/PageHeader.vue`
- Test: `frontend/src/components/__tests__/PageHeader.test.ts`

**Interfaces:**
- Consumes: `global.css` 的 `.eyebrow` / `.subtle` 工具类
- Produces: `<PageHeader :eyebrow="..." :title="..." :subtitle="..." />` 组件，含 `#actions` slot

- [ ] **Step 1: 编写组件测试**

创建 `frontend/src/components/__tests__/PageHeader.test.ts`：

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PageHeader from '@/components/PageHeader.vue'

describe('PageHeader', () => {
  it('renders eyebrow, title, and subtitle', () => {
    const wrapper = mount(PageHeader, {
      props: {
        eyebrow: '客户管理',
        title: '客户列表',
        subtitle: '统一客户基础信息与画像数据管理',
      },
    })
    expect(wrapper.find('.eyebrow').text()).toBe('客户管理')
    expect(wrapper.find('h1').text()).toBe('客户列表')
    expect(wrapper.find('.desc').text()).toBe('统一客户基础信息与画像数据管理')
  })

  it('renders actions slot', () => {
    const wrapper = mount(PageHeader, {
      props: { eyebrow: '测试', title: '标题' },
      slots: { actions: '<button>操作</button>' },
    })
    expect(wrapper.find('.actions button').exists()).toBe(true)
  })

  it('hides subtitle when not provided', () => {
    const wrapper = mount(PageHeader, {
      props: { eyebrow: '测试', title: '标题' },
    })
    expect(wrapper.find('.desc').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npx vitest run src/components/__tests__/PageHeader.test.ts`
Expected: FAIL — 组件不存在

- [ ] **Step 3: 创建 PageHeader.vue**

创建 `frontend/src/components/PageHeader.vue`：

```vue
<template>
  <div class="page-header">
    <div class="header-info">
      <span v-if="eyebrow" class="eyebrow">{{ eyebrow }}</span>
      <h1>{{ title }}</h1>
      <p v-if="subtitle" class="desc">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  eyebrow?: string
  title: string
  subtitle?: string
}>()
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header-info h1 {
  font-size: 26px;
  font-weight: 850;
  margin: 4px 0;
  color: var(--ink);
}

.desc {
  color: var(--muted);
  margin: 0;
  max-width: 760px;
  font-size: 14px;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/components/__tests__/PageHeader.test.ts`
Expected: PASS — 3 个测试全部通过

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/PageHeader.vue frontend/src/components/__tests__/PageHeader.test.ts
git commit -m "feat: add PageHeader component"
```

---

### Task 9: 创建 FilterSection 组件

**Files:**
- Create: `frontend/src/components/FilterSection.vue`
- Test: `frontend/src/components/__tests__/FilterSection.test.ts`

**Interfaces:**
- Produces: `<FilterSection />` 组件，含默认 slot 用于筛选表单内容

- [ ] **Step 1: 编写组件测试**

创建 `frontend/src/components/__tests__/FilterSection.test.ts`：

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FilterSection from '@/components/FilterSection.vue'

describe('FilterSection', () => {
  it('renders slot content', () => {
    const wrapper = mount(FilterSection, {
      slots: { default: '<div class="filter-content">筛选内容</div>' },
    })
    expect(wrapper.find('.filter-content').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npx vitest run src/components/__tests__/FilterSection.test.ts`
Expected: FAIL — 组件不存在

- [ ] **Step 3: 创建 FilterSection.vue**

创建 `frontend/src/components/FilterSection.vue`：

```vue
<template>
  <div class="filter-section">
    <slot />
  </div>
</template>

<script setup lang="ts">
// 筛选区域容器组件 — 来源: design.md 4.2
</script>

<style scoped>
.filter-section {
  background: white;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid var(--line);
  box-shadow: 0 1px 2px rgba(0, 0, 0, .04);
  margin-bottom: 24px;
}
</style>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/components/__tests__/FilterSection.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/FilterSection.vue frontend/src/components/__tests__/FilterSection.test.ts
git commit -m "feat: add FilterSection component"
```

---

### Task 10: 创建 TableSection 组件

**Files:**
- Create: `frontend/src/components/TableSection.vue`
- Test: `frontend/src/components/__tests__/TableSection.test.ts`

**Interfaces:**
- Produces: `<TableSection />` 组件，含默认 slot 用于表格内容

- [ ] **Step 1: 编写组件测试**

创建 `frontend/src/components/__tests__/TableSection.test.ts`：

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TableSection from '@/components/TableSection.vue'

describe('TableSection', () => {
  it('renders slot content', () => {
    const wrapper = mount(TableSection, {
      slots: { default: '<table><tbody><tr><td>测试</td></tr></tbody></table>' },
    })
    expect(wrapper.find('table').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npx vitest run src/components/__tests__/TableSection.test.ts`
Expected: FAIL — 组件不存在

- [ ] **Step 3: 创建 TableSection.vue**

创建 `frontend/src/components/TableSection.vue`：

```vue
<template>
  <div class="table-section">
    <slot />
  </div>
</template>

<script setup lang="ts">
// 表格区域容器组件 — 来源: design.md 4.3
</script>

<style scoped>
.table-section {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--line);
  box-shadow: 0 1px 2px rgba(0, 0, 0, .04);
  overflow: hidden;
}

/* Arco 表格表头样式覆盖 — 对齐 design.md 4.3 */
:deep(.arco-table-th) {
  background-color: var(--bg) !important;
  color: #334155 !important;
  font-weight: 600 !important;
  font-size: 12px !important;
}

:deep(.arco-table-tr:hover .arco-table-td) {
  background-color: #F8FBFF !important;
}
</style>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/components/__tests__/TableSection.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/TableSection.vue frontend/src/components/__tests__/TableSection.test.ts
git commit -m "feat: add TableSection component"
```

---

### Task 11: 创建 ChartCard 组件

**Files:**
- Create: `frontend/src/components/ChartCard.vue`
- Test: `frontend/src/components/__tests__/ChartCard.test.ts`

**Interfaces:**
- Produces: `<ChartCard :title="..." />` 组件，含 `#actions` slot 和默认 slot

- [ ] **Step 1: 编写组件测试**

创建 `frontend/src/components/__tests__/ChartCard.test.ts`：

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ChartCard from '@/components/ChartCard.vue'

describe('ChartCard', () => {
  it('renders title', () => {
    const wrapper = mount(ChartCard, {
      props: { title: '经营趋势' },
    })
    expect(wrapper.find('.section-title h2').text()).toBe('经营趋势')
  })

  it('renders actions slot', () => {
    const wrapper = mount(ChartCard, {
      props: { title: '测试' },
      slots: { actions: '<button>导出</button>' },
    })
    expect(wrapper.find('.section-title .actions button').exists()).toBe(true)
  })

  it('renders default slot content', () => {
    const wrapper = mount(ChartCard, {
      props: { title: '测试' },
      slots: { default: '<div class="chart-body">图表内容</div>' },
    })
    expect(wrapper.find('.chart-body').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npx vitest run src/components/__tests__/ChartCard.test.ts`
Expected: FAIL — 组件不存在

- [ ] **Step 3: 创建 ChartCard.vue**

创建 `frontend/src/components/ChartCard.vue`：

```vue
<template>
  <div class="card pad chart-card">
    <div class="section-title">
      <h2>{{ title }}</h2>
      <div v-if="$slots.actions" class="actions">
        <slot name="actions" />
      </div>
    </div>
    <slot />
  </div>
</template>

<script setup lang="ts">
// 图表卡片组件 — 来源: design.md 4.4
defineProps<{
  title: string
}>()
</script>

<style scoped>
.chart-card {
  background: white;
  border-radius: 16px;
  border: 1px solid var(--line);
  box-shadow: 0 1px 2px rgba(0, 0, 0, .04);
  padding: 20px;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title h2 {
  font-size: 17px;
  font-weight: 600;
  margin: 0;
}

.actions {
  display: flex;
  gap: 8px;
}
</style>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/components/__tests__/ChartCard.test.ts`
Expected: PASS — 3 个测试全部通过

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/ChartCard.vue frontend/src/components/__tests__/ChartCard.test.ts
git commit -m "feat: add ChartCard component"
```

---

### Task 12: 创建 BatchToolbar 组件

**Files:**
- Create: `frontend/src/components/BatchToolbar.vue`
- Test: `frontend/src/components/__tests__/BatchToolbar.test.ts`

**Interfaces:**
- Produces: `<BatchToolbar :count="N" />` 组件，含默认 slot 用于操作按钮

- [ ] **Step 1: 编写组件测试**

创建 `frontend/src/components/__tests__/BatchToolbar.test.ts`：

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BatchToolbar from '@/components/BatchToolbar.vue'

describe('BatchToolbar', () => {
  it('displays selected count', () => {
    const wrapper = mount(BatchToolbar, {
      props: { count: 5 },
    })
    expect(wrapper.text()).toContain('5')
  })

  it('renders action slot', () => {
    const wrapper = mount(BatchToolbar, {
      props: { count: 3 },
      slots: { default: '<button>批量编辑</button>' },
    })
    expect(wrapper.find('button').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npx vitest run src/components/__tests__/BatchToolbar.test.ts`
Expected: FAIL — 组件不存在

- [ ] **Step 3: 创建 BatchToolbar.vue**

创建 `frontend/src/components/BatchToolbar.vue`：

```vue
<template>
  <div class="batch-toolbar">
    <a-tag color="arcoblue" size="large">
      已选择 {{ count }} 条
    </a-tag>
    <slot />
  </div>
</template>

<script setup lang="ts">
// 批量操作工具栏 — 来源: design.md 4.6
defineProps<{
  count: number
}>()
</script>

<style scoped>
.batch-toolbar {
  margin-bottom: 16px;
  padding: 12px 16px;
  background: rgba(29, 78, 216, .06);
  border: 1px solid rgba(29, 78, 216, .15);
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/components/__tests__/BatchToolbar.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/BatchToolbar.vue frontend/src/components/__tests__/BatchToolbar.test.ts
git commit -m "feat: add BatchToolbar component"
```

---

### Task 13: 创建 QuickFilterTags 组件

**Files:**
- Create: `frontend/src/components/QuickFilterTags.vue`
- Test: `frontend/src/components/__tests__/QuickFilterTags.test.ts`

**Interfaces:**
- Produces: `<QuickFilterTags v-model="activeTag" :tags="[{label, value, count}]" />` 组件

- [ ] **Step 1: 编写组件测试**

创建 `frontend/src/components/__tests__/QuickFilterTags.test.ts`：

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import QuickFilterTags from '@/components/QuickFilterTags.vue'

describe('QuickFilterTags', () => {
  const tags = [
    { label: '待确认', value: 'pending', count: 8 },
    { label: '逾期', value: 'overdue', count: 3 },
    { label: '本月新增', value: 'new', count: 12 },
  ]

  it('renders all tags with counts', () => {
    const wrapper = mount(QuickFilterTags, {
      props: { tags, modelValue: '' },
    })
    expect(wrapper.findAll('.quick-tag')).toHaveLength(3)
    expect(wrapper.text()).toContain('待确认')
    expect(wrapper.text()).toContain('8')
  })

  it('highlights active tag', () => {
    const wrapper = mount(QuickFilterTags, {
      props: { tags, modelValue: 'pending' },
    })
    expect(wrapper.find('.quick-tag.active').exists()).toBe(true)
  })

  it('emits update:modelValue on click', async () => {
    const wrapper = mount(QuickFilterTags, {
      props: { tags, modelValue: '' },
    })
    await wrapper.findAll('.quick-tag')[1].trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['overdue'])
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npx vitest run src/components/__tests__/QuickFilterTags.test.ts`
Expected: FAIL — 组件不存在

- [ ] **Step 3: 创建 QuickFilterTags.vue**

创建 `frontend/src/components/QuickFilterTags.vue`：

```vue
<template>
  <div class="quick-filter-tags">
    <button
      v-for="tag in tags"
      :key="tag.value"
      class="quick-tag"
      :class="{ active: modelValue === tag.value }"
      @click="$emit('update:modelValue', modelValue === tag.value ? '' : tag.value)"
    >
      {{ tag.label }}
      <span v-if="tag.count != null" class="tag-count">{{ tag.count }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
interface QuickTag {
  label: string
  value: string
  count?: number
}

defineProps<{
  tags: QuickTag[]
  modelValue: string
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<style scoped>
.quick-filter-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.quick-tag {
  border: 1px solid var(--line);
  background: white;
  border-radius: 999px;
  padding: 7px 10px;
  color: var(--muted);
  font-weight: 700;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.18s ease;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.quick-tag:hover {
  border-color: #93C5FD;
  background: #EFF6FF;
  color: var(--primary);
}

.quick-tag.active {
  background: #DBEAFE;
  border-color: #BFDBFE;
  color: #1D4ED8;
}

.tag-count {
  font-size: 12px;
  opacity: 0.8;
}
</style>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npx vitest run src/components/__tests__/QuickFilterTags.test.ts`
Expected: PASS — 3 个测试全部通过

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/QuickFilterTags.vue frontend/src/components/__tests__/QuickFilterTags.test.ts
git commit -m "feat: add QuickFilterTags component"
```

---

### Task 14: 验证布局组件对齐原型

**Files:**
- Read: `frontend/src/components/layout/AppSidebar.vue` (全部)
- Read: `frontend/src/components/layout/AppHeader.vue` (全部)
- Read: `frontend/src/views/Dashboard.vue` (全部)
- Modify: 上述文件如需对齐

**Interfaces:**
- Consumes: `design.md` 第 5、6 节布局规范
- Produces: 布局组件与原型一致

- [ ] **Step 1: 读取 AppSidebar.vue 全文**

Read: `frontend/src/components/layout/AppSidebar.vue`

- [ ] **Step 2: 对照 design.md 第 6 节检查样式**

检查项：
- 导航组圆角 `16px` + 背景色 `rgba(15,23,42,.20)`
- 折叠按钮样式（`design.md` 6.2.6）
- 品牌标识 `.mark` 尺寸 `36×36px` + 渐变 `linear-gradient(135deg, #3B82F6, #06B6D4)` + 阴影
- 导航按钮 active 样式：`linear-gradient(90deg, rgba(59,130,246,.24), rgba(6,182,212,.12))`
- 折叠态二级菜单强制隐藏 `!important`
- 侧边栏滚动：`.nav` 的 `overflow-y: auto` + `overflow-x: visible`

- [ ] **Step 3: 修复发现的差异**

如发现样式与原型不一致，使用 `string_replace` 修正。如完全一致则跳过。

- [ ] **Step 4: 读取 AppHeader.vue 全文**

Read: `frontend/src/components/layout/AppHeader.vue`

- [ ] **Step 5: 对照 design.md 5.1 节检查样式**

检查项：
- 毛玻璃效果 `backdrop-filter: blur(14px)` + 背景 `rgba(246,248,251,.86)`
- 搜索框样式（`design.md` 3.5）
- 状态药丸标签 `.pill` 样式

- [ ] **Step 6: 修复发现的差异**

如发现样式与原型不一致，使用 `string_replace` 修正。如完全一致则跳过。

- [ ] **Step 7: 验证前端构建和类型检查**

Run: `cd frontend && npm run build && npx vue-tsc --noEmit`
Expected: 构建和类型检查均通过

- [ ] **Step 8: 提交（如有修改）**

```bash
git add frontend/src/components/layout/AppSidebar.vue frontend/src/components/layout/AppHeader.vue
git commit -m "style: align layout components with prototype design spec"
```

---

### Task 15: Phase 0 最终验证

**Files:**
- 无文件修改

- [ ] **Step 1: 验证前端构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 2: 验证类型检查**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 3: 运行所有前端单元测试**

Run: `cd frontend && npx vitest run`
Expected: 所有测试通过

- [ ] **Step 4: 启动开发服务器验证无控制台错误**

Run: `cd frontend && npm run dev` (后台运行，然后浏览器访问 http://localhost:5173)
Expected: 页面正常加载，控制台无错误

- [ ] **Step 5: 验证侧边栏折叠/展开**

在浏览器中：
- 点击折叠按钮 → 侧边栏收窄至 72px
- 再次点击 → 侧边栏展开至 252px
- 刷新页面 → 折叠状态保持（localStorage 持久化）

- [ ] **Step 6: 验证搜索框快捷键**

在浏览器中按 `/` 键 → 搜索框获得焦点

- [ ] **Step 7: 验证 td002 文件已删除**

Run: `ls frontend/src/styles/td002-component-styles.css 2>&1`
Expected: "No such file or directory"

- [ ] **Step 8: 验证无旧别名变量残留**

Run: `cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && grep -r "neutral-[0-9]" frontend/src/ --include="*.vue" --include="*.ts" --include="*.css"`
Expected: 无输出

- [ ] **Step 9: 标记 Phase 0 完成**

在 `docs/superpowers/specs/2026-07-14-prototype-driven-fullstack-refactoring-design.md` 中，Phase 0 部分标注为已完成。

```bash
git add docs/superpowers/specs/2026-07-14-prototype-driven-fullstack-refactoring-design.md
git commit -m "docs: mark Phase 0 as complete"
```
