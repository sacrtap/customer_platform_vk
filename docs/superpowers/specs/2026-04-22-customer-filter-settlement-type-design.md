# 设计文档：客户管理页面新增结算方式筛选项

**日期**: 2026-04-22
**状态**: 已批准
**涉及文件**: `frontend/src/views/customers/Index.vue`

---

## 需求概述

在客户管理页面第一行筛选项中新增"结算方式"筛选项，查询/重置按钮始终在第一行最右侧可见。商务经理、运营经理筛选项保持在高级筛选区域不动。

## 布局设计

### 当前布局（第一行）
```
[关键词] [账号类型] [行业类型] [重点客户] [查询/重置按钮]
```

### 新布局（第一行）
```
[关键词] [账号类型] [行业类型] [重点客户] [结算方式] [查询/重置按钮]
```

### 响应式列配置
- 筛选项列: `:xs="24" :sm="12" :md="8" :lg="4"`（保持不变）
- 按钮列: `:xs="24" :sm="12" :md="8" :lg="4"`（保持不变）
- 总计 6 列，lg 断点下 6×4=24，刚好占满一行

## 代码变更

### 1. 模板层变更

在现有第 4 个筛选项（重点客户）之后、按钮列之前，新增第 5 个 `a-col`：

```vue
<a-col :xs="24" :sm="12" :md="8" :lg="4">
  <a-form-item label="结算方式">
    <a-select v-model="filters.settlement_type" placeholder="请选择" allow-clear>
      <a-option value="prepaid">预付费</a-option>
      <a-option value="postpaid">后付费</a-option>
    </a-select>
  </a-form-item>
</a-col>
```

### 2. 脚本层变更

**filters 对象新增字段**:
```ts
const filters = reactive({
  keyword: '',
  account_type: '',
  industry: '',
  is_key_customer: null as boolean | null,
  settlement_type: '',  // 新增
})
```

**loadCustomers() 函数新增参数传递**:
```ts
if (filters.settlement_type) params.settlement_type = filters.settlement_type
```

**handleReset() 函数新增重置逻辑**:
```ts
filters.settlement_type = ''
```

**handleExport() 函数新增导出参数**:
```ts
if (filters.settlement_type) params.settlement_type = filters.settlement_type
```

## 后端兼容性

后端 `backend/app/services/customers.py` 已支持 `settlement_type` 筛选参数（Line 203），无需后端改动。

## 风险与约束

- **无破坏性变更**: 仅新增筛选项，不影响现有功能
- **响应式布局**: lg 断点下一行正好容纳 6 个元素（5 个筛选项 + 1 个按钮列）
- **数据源**: 结算方式选项为静态值（prepaid/postpaid），无需额外 API 调用

## 验收标准

1. 第一行显示 5 个筛选项 + 查询/重置按钮
2. 结算方式筛选项可正常选择"预付费"、"后付费"
3. 选择后点击"查询"，列表按结算方式过滤
4. 点击"重置"，结算方式筛选项清空
5. 导出功能包含结算方式筛选条件
