# 设计文档：结算单明细楼层类型显示修复

**日期**: 2026-04-28
**状态**: 待实施
**作者**: AI Assistant

---

## 问题描述

结算单详情页面的结算明细列表中，"楼层类型"列存在两个问题：
1. 列标题显示为"层级类型"（应为"楼层类型"）
2. 直接显示数据库字段值（`single`/`multi`），而非用户友好的"单层/多层"

## 参考标准

计费规则页面（`PricingRules.vue`）已正确实现：
- 列标题为"楼层类型"
- 使用 `<a-tag>` 组件格式化显示：
  - `single` → 蓝色标签"单层"
  - `multi` → 紫色标签"多层"

## 修改方案

### 文件：`frontend/src/views/billing/Invoices.vue`

**修改 1**：列定义（第 544 行）
```typescript
// 修改前
{ title: '层级类型', dataIndex: 'layer_type', width: 100 },

// 修改后
{ title: '楼层类型', dataIndex: 'layer_type', slotName: 'layer_type', width: 100 },
```

**修改 2**：添加格式化模板（在第 236 行后添加）
```vue
<template #layer_type="{ record }">
  <a-tag :color="record.layer_type === 'multi' ? 'purple' : 'blue'">
    {{ record.layer_type === 'multi' ? '多层' : '单层' }}
  </a-tag>
</template>
```

## 影响范围

| 文件                                    | 修改内容                      |
| --------------------------------------- | ----------------------------- |
| `frontend/src/views/billing/Invoices.vue` | 列标题 + 添加格式化模板       |

## 验收标准

1. 结算单详情页的结算明细列表中，"楼层类型"列标题正确
2. `single` 显示为蓝色标签"单层"
3. `multi` 显示为紫色标签"多层"
4. 与计费规则页面的显示效果完全一致
