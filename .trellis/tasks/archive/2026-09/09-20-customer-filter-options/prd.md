# 增加筛选项（是否结算/重点客户/房产客户/是否停用）

## Goal

客户管理列表页筛选项增强，共 4 项：

| 筛选项 | 字段 | 现状 | 本次动作 |
|---|---|---|---|
| 是否结算 | `is_settlement_enabled` | 前后端均不支持 | 前后端新增 |
| 是否重点客户 | `is_key_customer` | 后端支持、前端 filters 有字段但无 UI | 前端补下拉 |
| 是否房产客户 | `is_real_estate` | 后端支持、前端 filters 有字段但无 UI | 前端补下拉 |
| 是否停用 | `is_disabled` | 前后端均不支持 | 前后端新增 |

## Requirements

- 前端 `CustomerFilters.vue` 增加 4 个 FilterDropdown（布尔选项：是/否/全部，默认全部）。
- 前端 `useCustomerList.ts`：
  - `createDefaultFilters` 增加 `is_settlement_enabled: null`、`is_disabled: null`（`is_key_customer` / `is_real_estate` 已有）。
  - `buildParams` 传递 4 个布尔参数。
- 前端 `api/customers.ts` `getCustomers` 参数类型增加 `is_settlement_enabled`、`is_disabled`。
- 后端 `routes/customers.py` `list_customers` 解析 `is_settlement_enabled`、`is_disabled` 布尔参数（参照现有 `is_key_customer` 写法）。
- 后端 `services/customers.py` `get_all_customers` 增加对应筛选条件（参照现有 `is_key_customer` / `is_real_estate` 写法）。
- FilterDropdown 组件期望 string value，布尔筛选需在前端做 string ↔ boolean/null 转换（参照现有 managerValue computed 模式，或新增布尔 computed 辅助）。

## Constraints

- 不改变现有筛选项行为与默认值。
- 不改变 FilterDropdown 组件本身（保持最小改动，转换逻辑放 CustomerFilters.vue 内）。
- 列表缓存：后端 `list_customers` 的缓存键基于 filters 字典，新增参数天然纳入缓存键，无需额外处理。

## Acceptance Criteria

- [ ] 客户列表页可看到 4 个新筛选项（建议放置于「更多筛选」区）。
- [ ] 每个筛选项选择「是」/「否」均能正确过滤列表；选择「全部」或清空恢复默认。
- [ ] 4 个筛选项可与其他现有筛选项组合使用。
- [ ] 后端测试：`test_customer_service.py` 增加 `is_settlement_enabled` / `is_disabled` 筛选用例。
- [ ] 前端类型检查与构建通过。
