# Design — 筛选项增强（是否结算/重点客户/房产客户/是否停用）

## 边界

- 前端：`CustomerFilters.vue`、`useCustomerList.ts`、`api/customers.ts`
- 后端：`routes/customers.py`、`services/customers.py`
- 不改：`FilterDropdown.vue` 组件本身、现有筛选项行为、默认筛选值

## 数据流

```
CustomerFilters.vue (FilterDropdown)
  → v-model 绑定 filters.is_settlement_enabled / is_disabled / is_key_customer / is_real_estate
  → useCustomerList.buildParams() 组装查询参数
  → GET /api/v1/customers?is_settlement_enabled=true&is_disabled=false&...
  → routes/customers.py 解析布尔参数 → filters dict
  → services/customers.py get_all_customers 追加 WHERE 条件
  → 返回过滤后的列表
```

## 布尔值转换（关键点）

`FilterDropdown.vue` 的 `modelValue` 类型为 `string | string[]`，options 的 value 为 string。
客户列表 filters 中布尔字段为 `boolean | null`（null = 全部）。因此在 `CustomerFilters.vue`
内为每个布尔筛选项定义 computed 桥接（参照现有 `managerValue` 模式）：

```ts
const isSettlementEnabledValue = computed({
  get: () => {
    if (filters.value.is_settlement_enabled === null) return ''
    return filters.value.is_settlement_enabled ? 'true' : 'false'
  },
  set: (val: string) => {
    filters.value.is_settlement_enabled = val === '' ? null : val === 'true'
  },
})
```

- options：`[{ label: '是', value: 'true' }, { label: '否', value: 'false' }]`
- FilterDropdown 自带「全部」选项（清空 → null）

## 后端参数解析

`routes/customers.py` `list_customers` 参照现有 `is_key_customer` 写法：

```python
is_settlement_enabled = request.args.get("is_settlement_enabled")
if is_settlement_enabled is not None:
    filters["is_settlement_enabled"] = is_settlement_enabled.lower() == "true"

is_disabled = request.args.get("is_disabled")
if is_disabled is not None:
    filters["is_disabled"] = is_disabled.lower() == "true"
```

## 后端 Service 条件

`services/customers.py` `get_all_customers` 参照现有 `is_key_customer`：

```python
if (is_settlement_enabled := filters.get("is_settlement_enabled")) is not None:
    conditions.append(Customer.is_settlement_enabled == is_settlement_enabled)

if (is_disabled := filters.get("is_disabled")) is not None:
    conditions.append(Customer.is_disabled == is_disabled)
```

注意：`is_disabled` 现有字段 `nullable=True, default=False`，SQL 中 `NULL = false` 不成立
（NULL 比较返回 NULL → 过滤掉）。设计权衡：
- 若按「停用」筛选，`is_disabled = false` 会漏掉 NULL 值客户。
- 建议 `is_disabled == False` 时用 `or_(Customer.is_disabled.is_(False), Customer.is_disabled.is_(None))`
  保证历史 NULL 数据归入「未停用」。

## 放置位置

4 个筛选项放置于「更多筛选」区（`more-row`），与 ERP 系统/合作状态/结算方式并列：
- 是否结算、是否重点客户、是否房产客户、是否停用

## 缓存

后端缓存键基于 `filters` 字典的 md5，新增参数自动纳入缓存键，无需额外处理。
