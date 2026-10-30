# 计费规则列表客户列宽优化与客户ID展示

## Goal

计费规则页「客户」列过宽且缺少客户ID：后端列表补 company_id 字段，前端拆分客户ID/客户名称两列并收窄宽度，对齐余额管理页。

## Background

- 余额管理页（`BalanceTable.vue`）已采用 `客户ID`（width 64，`company_id`）+ `客户名称`（width 200）双列布局，视觉与信息密度俱佳。
- 计费规则页（`PricingRules.vue`）当前只有单个 `客户` 列（无 width，弹性撑满），渲染 `customer_name`，无名称时兜底显示 `客户{customer_id}`——该 `customer_id` 是 DB 内部主键，对用户无意义且误导。
- 后端 `/api/v1/billing/pricing-rules` 列表序列化未返回 `company_id`（导出 Excel 已有），前端无数据源可展示客户编号。

## Requirements

- 后端列表接口返回 `company_id`（客户编号），与 balances 导出口径一致。
- 前端计费规则表格拆分为「客户ID」+「客户名称」两列，宽度对齐余额管理页（64 / 200）。
- 客户ID 使用 `company_id`，不回退 `customer_id`（与 `BalanceTable.test.ts` 的既有约定一致）。
- 表格 `scroll.x` 相应增加（786 → 900），避免列挤压。
- 保持既有列设置持久化（`pricing_rules_table_columns`）可用：存量 localStorage 配置缺 `company_id` 键时回退默认全显（DataTable 已有兜底逻辑，无需额外处理）。
- 旧兜底文案「客户{customer_id}」移除——客户ID 已独立成列，名称空时显示 `-`。

## Acceptance Criteria

- [x] `GET /api/v1/billing/pricing-rules` 返回的每条规则含 `company_id` 字段（值为客户编号，非 DB 主键）。
- [x] 计费规则页表格表头含「客户ID」与「客户名称」两列，客户ID 列宽约 64px、客户名称列宽约 200px，与余额管理页一致。
- [x] 客户ID 列展示 `company_id`；`company_id` 为空时显示空而非回退 DB 主键 `customer_id`。
- [x] 无 `customer_name` 的规则在客户名称列显示 `-`（原「客户123」误导文案移除）。
- [x] `cd frontend && npx vue-tsc --noEmit` 通过。
- [x] 前端单测通过：`cd frontend && npx vitest run`（既有 BalanceTable/DataTable 用例不受影响）。

## Notes

- 视觉回归基线 `pricing-rules-chromium.png` 将因列宽变化过期；PR CI 默认不跑视觉回归（e2e-full 的 `skip_visual` 默认 true），基线更新留待本地或手动 e2e-full 触发时处理，不在本次改动范围内强制。
- 本任务为轻量级（PRD-only），无 design.md / implement.md。
