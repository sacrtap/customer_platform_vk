# Implement — 余额管理页第二排筛选项对齐客户管理页

## Ordered Checklist

### Backend

1. [x] `_parse_balance_filters`：新增解析 `auto_initiate_settlement` / `is_disabled`
       （bool，非法值 400）、`erp_system` / `cooperation_status`（字符串，空串→None），并写入返回 dict。
2. [x] `_query_balance_rows_raw`：`base_stmt` 与 `count_stmt` 应用四个新筛选
       （两个布尔项用 NULL 兼容条件，两个字符串用等值）。
3. [x] `get_balance_stats`：在 `customer_filters` 中应用四个新筛选（同语义），保证 KPI 口径一致。

### Frontend

4. [x] `api/billing.ts`：`BalanceQueryParams` 增加四个可选字段；`getBalanceStats` 参数对象扩展。
5. [x] `useBalance.ts`：
       - `defaultFilters()` 增加四个字段；
       - `buildCommonFilterParams` 构建新参数（布尔项走 `stringifyBooleans`）；
       - 移除 `tagOptions` / `loadTags` / `tag_ids` 相关；
       - 新增 `erpSystems` / `cooperationStatuses` ref 与 `loadErpSystems()` / `loadCooperationStatuses()`。
6. [x] `BalanceFilters.vue`：第二排改为
       是否结算 / 自动发起结算 / 是否重点客户 / 是否房产客户 / 是否停用 / ERP系统 / 合作状态；
       删除「标签」；布尔项用 `BOOLEAN_FILTER_OPTIONS`；新增 `erpSystems` / `cooperationStatuses` props。
7. [x] `Balance.vue`：新增 `:erp-systems` / `:cooperation-statuses` 透传，移除 `:tag-options`；
       `onMounted` 调用新加载函数，移除 `loadTags`。

### Tests

8. [x] 后端：在 `backend/tests/integration/test_billing_api.py` 增加新筛选用例
       （erp_system / cooperation_status / auto_initiate_settlement / is_disabled，含 NULL 兼容）。
9. [x] 前端：`useBalance.test.ts` 调整（移除标签相关 mock 断言如有，补充新字段默认值/参数构建）。

## Validation Commands

```bash
# 前端
cd frontend && pnpm type-check
cd frontend && pnpm vitest run src/composables/__tests__/useBalance.test.ts

# 后端（按需，涉及 sqlite 测试库自动补列）
cd backend && python -m pytest tests/integration/test_billing_api.py -k "filter" -q
```

## Review Gates

- Gate A（后端）：四个筛选项在列表/统计/导出三处一致生效；非法布尔值返回 400。
- Gate B（前端）：`pnpm type-check` 通过；第二排 UI 与客户页一致且无「标签」。
- Gate C（一致性）：KPI 卡片随新筛选联动（列表条数与卡片口径一致）。

## Rollback Points

- 每个文件改动独立可回滚（无跨文件强耦合）；`git checkout -- <file>` 即可局部还原。

## Out of Scope（勿动）

- 客户管理页筛选项；余额页首行筛选项；后端 `tag_ids` 解析（保留兼容）。
