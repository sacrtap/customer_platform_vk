# Design — 余额管理页第二排筛选项对齐客户管理页

## Boundaries

| Layer | Files |
| --- | --- |
| Backend | `backend/app/routes/billing/balances.py`（列表 `_parse_balance_filters` + `_query_balance_rows_raw`；统计 `get_balance_stats`；导出复用同解析） |
| Frontend API | `frontend/src/api/billing.ts`（`BalanceQueryParams`、`getBalanceStats` 参数） |
| Frontend state | `frontend/src/composables/useBalance.ts`（filters 默认值、参数构建、ERP/合作状态加载、移除标签） |
| Frontend UI | `frontend/src/views/billing/components/BalanceFilters.vue`（第二排 UI） |
| Frontend page | `frontend/src/views/billing/Balance.vue`（透传 props、加载调用） |

## Contracts

### Backend query params（列表 / 统计 / 导出共享）

新增（在既有 `is_settlement_enabled`、`settlement_type` 之外）：

- `auto_initiate_settlement`：`"true" | "false"`（其它值 → 400）
- `is_disabled`：`"true" | "false"`（其它值 → 400）
- `erp_system`：字符串精确匹配（空串视为未筛选）
- `cooperation_status`：字符串精确匹配（空串视为未筛选）

`_parse_balance_filters` 返回 dict 增加以上四个键，`_query_balance_rows_raw` 的
`base_stmt` 与 `count_stmt` 均应用；`get_balance_stats` 的 `customer_filters` 同步应用。

### 布尔筛选 NULL 兼容语义（对齐 `backend/app/services/customers.py:331-357`）

- `auto_initiate_settlement`（默认「是」，历史 NULL 视为是）
  - `true` → `or_(col.is_(True), col.is_(None))`
  - `false` → `col.is_(False)`
- `is_disabled`（历史 NULL 视为未停用）
  - `true` → `col.is_(True)`
  - `false` → `or_(col.is_(False), col.is_(None))`

`is_settlement_enabled` 列表侧沿用既有简单等值（`Customer.is_settlement_enabled == value`）；
本次不改其行为（避免顺带扩大改动面），仅新增四项。

### Frontend `BalanceQueryParams`（`api/billing.ts`）

新增可选字段：`auto_initiate_settlement?: string`、`is_disabled?: string`、
`erp_system?: string`、`cooperation_status?: string`。`getBalanceStats` 参数对象同步新增
（布尔两项为 `boolean`，与既有 `is_key_customer` 风格一致）。

### `useBalance.ts`

- `defaultFilters()` 新增：`auto_initiate_settlement: null`、`is_disabled: null`、
  `erp_system: ''`、`cooperation_status: ''`。
- `buildCommonFilterParams` 增加对应参数构建（布尔项走 `stringifyBooleans` 分支）。
- 移除：`tagOptions` ref、`loadTags()`、`advancedFilters.tag_ids`（第二排不再有「标签」筛选项，
  故一并移除 `tag_ids` 字段与参数构建）。
- 新增：`erpSystems` ref + `loadErpSystems()`（`getErpSystemsList`）、`cooperationStatuses` ref +
  `loadCooperationStatuses()`（`getCooperationStatusesList`），来源与客户页 `useCustomerList` 一致。

### `BalanceFilters.vue`

第二排 `more-row` 渲染顺序：
`是否结算` → `自动发起结算` → `是否重点客户` → `是否房产客户` → `是否停用` → `ERP系统` → `合作状态`。

- 布尔项选项统一用 `BOOLEAN_FILTER_OPTIONS`（import 自 `@/constants/customerOptions`）。
- ERP/合作状态选项为 computed，映射 `{ label: name, value: value }`。
- 新增 props：`erpSystems: ErpSystem[]`、`cooperationStatuses: CooperationStatus[]`。
- 删除 props：`tagOptions`、`tagsLoading`（如无）。
- 删除 `tagValue` computed 与「标签」FilterDropdown。

## Data Flow

```
BalanceFilters (第二排) ── v-model:filters ──▶ useBalance.filters (reactive)
                                                   │
                              buildCommonFilterParams()  ──▶ getBalances / getBalanceStats / buildExportParams
                                                   │
                                        /billing/balances, /billing/balance-stats, /billing/balances/export
                                                   │
                                    _parse_balance_filters → _query_balance_rows_raw / get_balance_stats
```

## Compatibility / Rollout

- 后端 `tag_ids` 解析保留，OpenAPI 调用不受影响；仅前端本页面停止发送 `tag_ids`。
- 新参数缺省时行为与现状完全一致（`None` 不生效）。
- 无数据库迁移。
- 回滚：还原本任务涉及文件即可。

## Risks

- **ERP/合作状态下拉数据源**：需确认 `/erp-systems`、`/cooperation-statuses` 返回结构与
  客户页一致（`res.data?.data || res.data`）。已确认 `api/erpSystems.ts`、`api/cooperationStatuses.ts`
  返回 `{ data: [...] }`，`useCustomerList` 用 `res.data?.data || res.data`。
- **KPI 统计一致性**：新筛选须同时进 `get_balance_stats`，否则卡片与列表口径不一致。
