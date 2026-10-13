# 余额管理页第二排筛选项对齐客户管理页

## Goal

将「余额管理」页（`frontend/src/views/billing/Balance.vue`）表格筛选区**第二排（「更多」展开行）**
的筛选项，参照「客户管理」页（`frontend/src/views/customers/Index.vue` +
`CustomerFilters.vue`）保持一致，并**去掉「标签」筛选项**。

## Background

| 页面 | 第二排（更多）当前筛选项 |
| --- | --- |
| 客户管理（参照基准） | 是否结算 / 自动发起结算 / 是否重点客户 / 是否房产客户 / 是否停用 / ERP系统 / 合作状态 / 结算方式 |
| 余额管理（改造对象） | 是否结算 / 是否重点客户 / 是否房产客户 / **标签** |

差异与约束：

1. 余额管理页**首行**已有「结算类型」（`settlement_type`，值域 prepaid/postpaid），与客户管理页
   第二排的「结算方式」是**同一字段**。为避免同页重复，第二排**不再重复添加「结算方式」**。
2. 因此余额管理页第二排目标集合（按客户页顺序，去掉「标签」与重复的「结算方式」）为：
   **是否结算 / 自动发起结算 / 是否重点客户 / 是否房产客户 / 是否停用 / ERP系统 / 合作状态**。
3. 「标签」筛选项需**移除**（前端筛选项 + 相关数据加载/状态），后端 `tag_ids` 解析可保留以兼容
   OpenAPI/其他调用方，但不再由本页面 UI 触发。

## Requirements

- R1. 第二排「更多」筛选项顺序与文案对齐客户管理页：是否结算 → 自动发起结算 → 是否重点客户 →
  是否房产客户 → 是否停用 → ERP系统 → 合作状态。
- R2. 新增筛选项：`auto_initiate_settlement`（自动发起结算）、`is_disabled`（是否停用）、
  `erp_system`（ERP系统）、`cooperation_status`（合作状态），布尔项复用 `BOOLEAN_FILTER_OPTIONS`。
- R3. 移除第二排「标签」筛选项，以及余额页对标签数据（`tagOptions`/`loadTags`）的加载与依赖。
- R4. 新筛选项需贯通：**列表** `/billing/balances`、**KPI 统计** `/billing/balance-stats`、
  **导出** `/billing/balances/export`（共享筛选参数）。
- R5. 布尔筛选语义对齐客户管理页的历史 NULL 兼容规则：
  - 「自动发起结算」= 是 → `auto_initiate_settlement IS TRUE OR IS NULL`；= 否 → `IS FALSE`。
  - 「是否停用」= 是 → `is_disabled IS TRUE`；= 否 → `IS FALSE OR IS NULL`。
- R6. 保持首行（搜索/账号类型/行业/结算类型/余额范围/运营经理/销售经理）与按钮组不变。

## Acceptance Criteria

- [ ] AC1. 余额管理页点击「更多」后，第二排筛选项为：是否结算 / 自动发起结算 / 是否重点客户 /
      是否房产客户 / 是否停用 / ERP系统 / 合作状态（无「标签」、无重复「结算方式」）。
- [ ] AC2. ERP系统下拉选项来自 `/erp-systems`、合作状态下拉来自 `/cooperation-statuses`；
      选项为空时展示「全部」占位不报错。
- [ ] AC3. 设置任一新筛选项后点击「筛选」，列表结果与所选条件一致（后端过滤生效）。
- [ ] AC4. 新筛选项参与 KPI 统计口径（切换筛选项后 KPI 数字随筛选联动）。
- [ ] AC5. 导出按当前筛选条件导出匹配数据，含新筛选项。
- [ ] AC6. 「清除筛选条件」可重置新筛选项；「更多」折叠/展开正常。
- [ ] AC7. `cd frontend && pnpm type-check` 通过；相关单测通过。
- [ ] AC8. 后端相关单测通过（新增筛选解析与过滤用例）。

## Out of Scope

- 不改动客户管理页的筛选项。
- 不改动余额管理页首行筛选项。
- 不移除后端 `tag_ids` 解析（保留向后兼容）。

## Notes

- 前端 UI 文案为中文；spec 文档为英文。
- 复用 `@/constants/customerOptions` 中的 `BOOLEAN_FILTER_OPTIONS`，与客户页保持一致。
