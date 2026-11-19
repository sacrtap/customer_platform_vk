# 余额管理页面修复（列宽 / 客户名预填 / 时间格式化）

> 归档来源：`.omo/plans/balance-page-fixes.md`、`.omo/drafts/balance-page-optimization.md`、`.omo/drafts/balance-edit-feature.md`（2026-11-19 蒸馏合并，原件已删除）
> 状态：已实施 —— `frontend/src/components/CustomerAutoComplete.vue` 已有 `displayName` prop；后续重构后余额表在 `frontend/src/views/billing/components/BalanceTable.vue`（余额列 width 138）、充值记录时间在 `RechargeRecordModal.vue`（`formatDateTime(record.created_at)`）
> 锚点说明：文中 `文件:行号` 为 2026-05 期快照，定位以符号名与路径为准

## Context

余额管理页面（原 `frontend/src/views/billing/Balance.vue`）4 个 UI/UX 细节问题：

| # | 现象 | 根因 |
|---|---|---|
| 1 | 余额列 280px 与已消耗列 200px 不等宽 | `columns` 中余额列 `width: 280`（line 406） |
| 2 | 点行内"充值"打开弹框，客户名不显示，需重新搜索 | `CustomerAutoComplete` 内部 `displayText` 只绑定 `model-value`，不响应外部传入的客户名变化（line 3 `:model-value="displayText"` 绑内部 ref） |
| 3 | 充值记录"充值时间"列显示原始 ISO 字符串 | 列定义 `{ title: '充值时间', dataIndex: 'created_at', width: 180 }` 无 slot（line 452） |
| 4 | 弹框中 `CustomerAutoComplete` 拿不到客户名 | `openRechargeModal` 只设 `rechargeForm.customer_id`，不传客户名（line 558-564） |

## Approach

1. **列宽**：余额列 `width: 280 → 200`，与已消耗列等宽。
2. **`CustomerAutoComplete.vue`**：新增可选 prop `displayName?: string` + `watch(() => props.displayName)`，外部名称变化同步到内部 `displayText`（`displayName` 有值且 `displayText` 为空时填入，即外部预填场景）。`modelValue` 仍为 `number | undefined`，向后兼容。
3. **充值记录时间**：列改 `{ title: '充值时间', dataIndex: 'created_at', slotName: 'created_at', width: 180 }`，模板 slot 复用已有 `formatLastRechargeTime(record.created_at)`（`YYYY-MM-DD HH:mm:ss`，与"最新充值时间"列一致；复用 line 217-224 已有 `#last_recharge_at` slot 模式）。
4. **弹框预填**：`openRechargeModal` 中保存 `balance.customer_name` 到响应式 `rechargeCustomerName`，传给 `<CustomerAutoComplete :display-name="rechargeCustomerName">`；弹框关闭后重置为空。

## Critical files & anchors

- `frontend/src/components/CustomerAutoComplete.vue` — `displayName` prop + watch
- `frontend/src/views/billing/Balance.vue` — 余额列宽、充值记录 slot、弹框预填（原实现位置，后拆分为 `components/BalanceTable.vue` 与 `components/RechargeRecordModal.vue`）

## Verification

- `cd frontend && npx vue-tsc --noEmit` → 0 错误
- `npm run build` 通过
- 三项验收：余额列与已消耗列等宽（200px）；充值时间正则 `/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/` 匹配；点"充值"后输入框值等于该行客户名，关闭弹框后重置
- 提交：`fix(balance): 优化余额页面列宽、时间格式化和客户名预填`（Balance.vue + CustomerAutoComplete.vue，仅此两文件）

## 未实施需求（2026-05-25 草案）

**原始诉求**：余额管理页面列表项增加编辑余额功能，需单独权限配置。

**彼时现状**：操作列仅有充值（`v-if="can('billing:recharge')"`）与记录按钮；后端已有 `billing:view` / `billing:recharge` / `billing:edit` / `billing:delete` / `billing:confirm` / `billing:pay`，**无** `billing:edit_balance`。

**4 个未决问题**（截至蒸馏时仍未闭环）：

1. 编辑余额的语义——直接改余额数值 vs 通过冲正记录调整？
2. 是否新增 `billing:edit_balance` 权限码？
3. 是否需要审计日志？
4. 入口位置——操作列新增按钮 vs 余额数字旁编辑图标？

**现状核实（2026-11-19）**：现系统只有 `BalanceWhitelist.vue` 的白名单余额编辑，业务页（BalanceTable）未实施编辑余额入口；上述问题如要推进需重新立项。

## Assumptions

- 本次为纯 UI 微调（约 20 行），不新增单测；`CustomerAutoComplete` 向后兼容是硬约束。
