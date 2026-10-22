# 统一客户与余额页金额小数口径

## Goal

前一任务已将客户管理列表余额列改为固定两位小数。但同页面及其他页仍有金额取整/浮动小数口径，与列表金额列不一致，需统一为小数点后两位。

## Background（排查结果）

三处口径不一致：

| 位置 | 当前实现 | 表现 | 用途 |
|---|---|---|---|
| `BalanceTable.vue` 本地 `formatNumber`（L274-277） | `maximumFractionDigits: 0` | `1,234.56 → 1,235` | tooltip 文案（日均消耗、当前余额、套餐剩余额度/年费/累计消耗、剩余次数） |
| `BalanceTable.vue` 本地 `formatAmount`（L279-282） | 固定两位小数 | `1,234.56 → 1,234.56` | 主表格所有金额列（已是目标口径） |
| `CustomerTable.vue` 30天消耗 tooltip | 共享 `formatNumber` | `1,234.56 → 1,234.56`，`1000 → 1,000` | `usage_30d_amount` tooltip |
| `CustomerTable.vue` 余额列 | 共享 `formatCurrency` | `¥1,234.56` | 前一任务已修复 |

`BalanceTable.vue` 存在**同一文件内双口径**：主表格金额列已固定两位，但 tooltip 文案仍取整，用户 hover 看到的数字与列表列对不上。

## Requirements

- `BalanceTable.vue` 所有 tooltip 内的金额（日均消耗、当前余额、套餐剩余额度、套餐年费、套餐内累计消耗）改为固定两位小数，与该文件 `formatAmount` 口径一致。
- `CustomerTable.vue` 30天消耗 tooltip 金额改为固定两位小数（`¥1,000.00`），与余额列口径一致。
- 非金额计数类数值（套餐剩余次数 `package_remaining_count`、消费天数 `consumption_days`）保持整数，不追加小数。
- 复用共享/文件内已有的两位小数实现，不新增第二套格式化逻辑。

## Acceptance Criteria

- [ ] `BalanceTable.vue` tooltip 中金额字段渲染为两位小数：`¥1,234.56`、`¥1,000.00`。
- [ ] `BalanceTable.vue` 剩余次数仍为整数（`次数：50`），不受影响。
- [ ] `CustomerTable.vue` 30天消耗 tooltip 渲染为 `30天消耗 ¥1,234.56` / `¥1,000.00`。
- [ ] `vue-tsc --noEmit`、ESLint、Prettier、相关单测全部通过。

## Non-Goals

- 不修改后端接口或计算精度。
- 不改动 `ConsumeLevelProgress.vue` 等其他页面的格式口径（其 `formatNumber` 用于等级/比率类展示，非金额）。

## Notes

- 单文件 ×2，轻量任务，PRD-only。
- 倾向做法：`BalanceTable.vue` 的 tooltip 文案直接复用文件内 `formatAmount`（与主表格同源），删除取整的本地 `formatNumber`；`CustomerTable.vue` 的 tooltip 改用共享 `formatCurrency` 或显式两位小数的 formatNumber 包装。
- **排查扩展**：`PreviewDrawer.vue`（客户列表行预览抽屉）的余额与30天消耗同样是金额且取整显示，与列表列口径冲突，同属本任务目标，已一并修复。
