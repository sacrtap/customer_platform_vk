# 客户筛选器输入检索功能优化设计

**日期**: 2026-04-23
**状态**: 已批准
**涉及页面**: 余额管理、计费规则、消耗分析、回款分析、预测回款

---

## 问题描述

当前5个页面的客户筛选项使用 `a-select` + `filterable` + `remote` 模式，虽然支持远程搜索，但交互形式受限于下拉选择框，用户希望改为输入框+下拉组合（AutoComplete）形式，提供更自由的输入检索体验。

## 涉及页面

| 页面 | 文件路径 |
|------|----------|
| 余额管理 | `frontend/src/views/billing/Balance.vue` |
| 计费规则 | `frontend/src/views/billing/PricingRules.vue` |
| 消耗分析 | `frontend/src/views/analytics/Consumption.vue` |
| 回款分析 | `frontend/src/views/analytics/Payment.vue` |
| 预测回款 | `frontend/src/views/analytics/Forecast.vue` |

## 设计方案

### 核心组件

新建 `frontend/src/components/CustomerAutoComplete.vue` 可复用组件，封装客户搜索逻辑。

### 组件 API

**Props**:
- `modelValue`: `number | undefined` — 选中的客户 ID（v-model 双向绑定）
- `placeholder`: `string` — 占位文本，默认 "请输入客户名称搜索"
- `width`: `number | string` — 组件宽度，默认 250

**Emits**:
- `update:modelValue`: `(id: number | undefined) => void` — 选中/清除客户时触发

### 组件内部逻辑

1. 用户输入关键词，300ms 防抖后调用 `getCustomers({ keyword, page: 1, page_size: 50 })`
2. 将搜索结果映射为 AutoComplete 所需格式：`{ value: customer.name, label: customer.name }`
3. 维护 `idByName` Map 用于选中时 name → id 反查
4. 用户选中某项时，通过 name 查找对应 id，emit `update:modelValue(id)`
5. 用户清除时，emit `update:modelValue(undefined)`
6. 组件 mounted 时不预加载数据，按需搜索

### 依赖

- Arco Design `a-auto-complete` 组件
- 现有 `getCustomers` API（`@/api/customers`）
- `lodash-es` 的 `debounce`（用于防抖）

### 各页面改动

每个页面改动一致：

1. **模板**: 将 `a-select` 客户筛选替换为 `<CustomerAutoComplete v-model="filters.customer_id" />`
2. **脚本**:
   - 移除 `customerOptions` ref
   - 移除 `handleCustomerSearch` 函数
   - 移除 `getCustomers` import
   - 移除 `onMounted` 中的 `handleCustomerSearch()` 预加载调用
3. **充值弹窗中的客户选择器（如 Balance.vue、PricingRules.vue 的弹窗）保持不变**，因为弹窗内的选择器是表单字段，不是筛选器

### 数据流

```
用户输入关键词 → 防抖 300ms → getCustomers({ keyword })
    → 返回客户列表 → 映射为 AutoComplete data
    → 用户选中 → 通过 name 反查 id → emit update:modelValue(customerId)
    → 父页面 filters.customer_id 更新 → 触发数据加载
```

### 错误处理

- 搜索失败：console.error 静默处理，不影响用户输入
- 无搜索结果：AutoComplete 组件自动显示空状态
- 清除操作：重置搜索文本和 customer_id

## 成功标准

1. 5个页面的客户筛选器均改为输入框+下拉形式
2. 输入关键词可实时搜索客户
3. 选中客户后筛选生效，功能与改动前一致
4. 公共组件可复用，无重复代码
