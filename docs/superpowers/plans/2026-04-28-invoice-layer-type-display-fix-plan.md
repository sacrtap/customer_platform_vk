# 结算单明细楼层类型显示修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复结算单详情页面结算明细列表中"楼层类型"列的显示问题，使其与计费规则页面保持一致。

**Architecture:** 在 Invoices.vue 中修改结算明细表格的列定义，添加 slotName 并复用 PricingRules.vue 中已有的 `<a-tag>` 格式化逻辑。

**Tech Stack:** Vue 3, Arco Design, TypeScript

**参考文件**: `frontend/src/views/billing/PricingRules.vue` 第 81-84 行（楼层类型格式化模板）

---

### Task 1: 修改结算明细列定义

**Files:**
- Modify: `frontend/src/views/billing/Invoices.vue:542-548`

当前代码（第 542-548 行）：
```typescript
// 结算明细列定义
const invoiceItemColumns = [
  { title: '设备类型', dataIndex: 'device_type', width: 100 },
  { title: '层级类型', dataIndex: 'layer_type', width: 100 },
  { title: '数量', dataIndex: 'quantity', width: 120, align: 'right' as const },
  { title: '单价', dataIndex: 'unit_price', width: 120, align: 'right' as const },
  { title: '小计', slotName: 'subtotal', width: 120, align: 'right' as const },
]
```

修改为：
```typescript
// 结算明细列定义
const invoiceItemColumns = [
  { title: '设备类型', dataIndex: 'device_type', width: 100 },
  { title: '楼层类型', dataIndex: 'layer_type', slotName: 'layer_type', width: 100 },
  { title: '数量', dataIndex: 'quantity', width: 120, align: 'right' as const },
  { title: '单价', dataIndex: 'unit_price', width: 120, align: 'right' as const },
  { title: '小计', slotName: 'subtotal', width: 120, align: 'right' as const },
]
```

**变更说明**：
- 将"层级类型"改为"楼层类型"
- 添加 `slotName: 'layer_type'` 以启用自定义模板

- [ ] 使用 edit 工具修改 `frontend/src/views/billing/Invoices.vue` 第 544 行

---

### Task 2: 添加楼层类型格式化模板

**Files:**
- Modify: `frontend/src/views/billing/Invoices.vue:234-236`

在第 236 行（`<template #subtotal>` 之前）添加楼层类型的格式化模板。

参考 `PricingRules.vue` 第 81-84 行的实现：
```vue
<template #layer_type="{ record }">
  <a-tag :color="record.layer_type === 'multi' ? 'purple' : 'blue'">
    {{ record.layer_type === 'multi' ? '多层' : '单层' }}
  </a-tag>
</template>
```

在 `<template #subtotal="{ record }">` 之前插入上述代码。

完整的目标区域（第 233-240 行）应修改为：
```vue
              <template #layer_type="{ record }">
                <a-tag :color="record.layer_type === 'multi' ? 'purple' : 'blue'">
                  {{ record.layer_type === 'multi' ? '多层' : '单层' }}
                </a-tag>
              </template>
              <template #subtotal="{ record }">
                <span class="amount">{{ formatCurrency(record.subtotal || record.quantity * record.unit_price) }}</span>
              </template>
```

- [ ] 使用 edit 工具在 `<template #subtotal>` 之前插入 `<template #layer_type>` 模板

---

### Task 3: 验证修改

**Files:**
- Verify: `frontend/src/views/billing/Invoices.vue`

**验证步骤**：
1. 检查 `invoiceItemColumns` 中第 544 行是否已修改为"楼层类型"且包含 `slotName: 'layer_type'`
2. 检查模板区域是否包含 `<template #layer_type>` 且逻辑正确
3. 运行前端类型检查：`cd frontend && npm run type-check`
4. 运行前端 lint：`cd frontend && npm run lint`

**预期结果**：
- TypeScript 类型检查通过
- Lint 检查通过
- 代码格式正确

- [ ] 运行 `cd frontend && npm run type-check` 验证无类型错误
- [ ] 运行 `cd frontend && npm run lint` 验证无 lint 错误

---

## 自审检查

### 1. 规格覆盖检查

| 规格要求                          | 对应任务     | 状态 |
| --------------------------------- | ------------ | ---- |
| 列标题从"层级类型"改为"楼层类型" | Task 1       | ✅   |
| 添加 slotName 启用自定义模板     | Task 1       | ✅   |
| 显示"单层/多层"而非字段值        | Task 2       | ✅   |
| 与计费规则页面显示效果一致       | Task 2       | ✅   |

### 2. 占位符扫描

- ✅ 无 "TBD"、"TODO"、"implement later"
- ✅ 无 "Add appropriate error handling" 等模糊描述
- ✅ 所有代码步骤包含完整代码
- ✅ 无 "Similar to Task N"

### 3. 类型一致性

- `layer_type` 字段在 `InvoiceItem` 接口中已定义为 `string`
- 模板中使用 `record.layer_type` 与接口定义一致
- 格式化逻辑与 `PricingRules.vue` 完全一致
