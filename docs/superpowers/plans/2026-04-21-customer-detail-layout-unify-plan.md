# 客户详情页排版统一实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为结算单和用量数据的表格区域添加统一的白色圆角卡片容器，使所有 Tab 视觉风格一致。

**Architecture:** 在 Detail.vue 中为结算单 `<a-table>` 和用量表格区域新增 `.data-table-card` CSS 类包裹，复用项目已有的 CSS 变量（`--neutral-2`, `--shadow-sm`, `--radius-md`），保持与基础信息/画像/余额 Tab 的卡片风格一致。

**Tech Stack:** Vue 3 + TypeScript + Arco Design + scoped CSS

---

## 文件结构

| 操作     | 文件路径                                       | 责任                 |
| -------- | ---------------------------------------------- | -------------------- |
| 修改     | `frontend/src/views/customers/Detail.vue`       | 模板包裹 + CSS 样式  |

**参考文件**（无需修改，仅用于复用模式）：
- `frontend/src/views/customers/Index.vue` — 参考 `.table-section` 的卡片样式模式
- `docs/superpowers/specs/2026-04-21-customer-detail-layout-unify-design.md` — 设计文档

---

### Task 1: 结算单 Tab 添加卡片容器

**Files:**
- Modify: `frontend/src/views/customers/Detail.vue` (template + style)

- [ ] **Step 1: 修改结算单 Tab 模板**

找到结算单 Tab（约第 300-318 行），在 `<a-table>` 外层包裹 `<div class="data-table-card">`。

**当前代码**:
```vue
<a-tab-pane key="invoices" title="结算单">
  <a-table :columns="invoiceColumns" :data="invoices" :pagination="false" row-key="id">
    <!-- ... -->
  </a-table>
</a-tab-pane>
```

**修改为**:
```vue
<a-tab-pane key="invoices" title="结算单">
  <div class="data-table-card">
    <a-table :columns="invoiceColumns" :data="invoices" :pagination="false" row-key="id">
      <template #status="{ record }">
        <span :class="['status-badge', getStatusClass(record.status)]">
          <span class="status-dot"></span>
          {{ getStatusText(record.status) }}
        </span>
      </template>
      <template #amount="{ record }">
        {{ formatCurrency(record.final_amount || record.total_amount) }}
      </template>
      <template #action="{ record }">
        <a-button type="primary" size="small" @click="viewInvoice(record)">查看</a-button>
      </template>
      <template #empty>
        <EmptyState title="暂无结算单数据" description="当前客户暂无结算单" />
      </template>
    </a-table>
  </div>
</a-tab-pane>
```

- [ ] **Step 2: 用量数据表格区域添加卡片容器**

找到用量数据 Tab（约第 320-352 行），将 `usage-table-section` 的 div 添加 `data-table-card` 类。

**当前代码**:
```vue
<div class="usage-table-section">
  <a-table :columns="usageColumns" :data="usageData" ...>
```

**修改为**:
```vue
<div class="usage-table-section">
  <div class="data-table-card">
    <a-table :columns="usageColumns" :data="usageData" :loading="usageLoading"
      :pagination="usagePagination" row-key="id" @page-change="handleUsagePageChange">
      <template #deviceType="{ record }">
        <a-tag>{{ record.device_type }}</a-tag>
      </template>
      <template #quantity="{ record }">
        {{ formatNumber(record.quantity || 0) }}
      </template>
      <template #empty>
        <EmptyState title="暂无用量数据" description="当前客户暂无用量记录" />
      </template>
    </a-table>
  </div>
</div>
```

- [ ] **Step 3: 添加 `.data-table-card` CSS 样式**

在 `<style scoped>` 中找到合适位置（建议放在 `.status-dot` 样式之后，约第 1674 行之后），添加以下 CSS：

```css
/* ========== 数据表格卡片容器 ========== */
.data-table-card {
  background: white;
  border-radius: var(--radius-md, 10px);
  border: 1px solid var(--neutral-2);
  box-shadow: var(--shadow-sm, 0 1px 2px rgba(0, 0, 0, 0.04));
  padding: 16px;
  width: 100%;
  box-sizing: border-box;
}

/* 用量表格区域的卡片间距 */
.usage-table-section .data-table-card {
  margin-top: 0;
}
```

- [ ] **Step 4: 验证前端类型检查**

```bash
cd frontend && rtk npm run type-check
```

预期：无新增错误（已有的 28 个 eslint 错误在测试文件中，与此变更无关）

- [ ] **Step 5: 提交**

```bash
rtk git add frontend/src/views/customers/Detail.vue
rtk git commit -m "style(detail): 统一结算单和用量数据区域卡片容器风格

- 结算单表格添加 .data-table-card 卡片容器
- 用量数据表格添加 .data-table-card 卡片容器
- 与基础信息/画像/余额 Tab 风格保持一致"
```

---
