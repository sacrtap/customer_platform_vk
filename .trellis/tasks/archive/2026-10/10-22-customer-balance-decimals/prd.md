# 客户管理列表余额显示两位小数

## Goal

客户管理页面列表中的余额列当前取整显示，需改为支持小数点后两位，避免用户看到的金额与实际账面金额不一致。

## Background

- `frontend/src/views/customers/components/CustomerTable.vue` 内的本地 `formatNumber` 使用 `toLocaleString('zh-CN', { maximumFractionDigits: 0 })`，余额被四舍五入到整数。
- 同一组件内 `usage_30d`（30天消耗）列也调用同一个本地 `formatNumber`。
- 仓库已有共享工具 `frontend/src/utils/formatters.ts` 的 `formatNumber`（基于 `Intl.NumberFormat('zh-CN')`），保留完整小数精度。

## Requirements

- 客户管理列表的余额列（含包年客户套餐剩余额度场景）必须显示小数部分，保留两位小数口径。
- 30天消耗列等共用同一格式函数的其他列，格式口径不得被破坏（消耗本身为整数场景时表现不变；若存在小数也应正确显示）。
- 优先复用仓库已有共享 formatter，不在组件内重复造第二个格式化实现。

## Acceptance Criteria

- [ ] 后端返回余额含小数（如 `1234.56`）时，客户管理列表余额列渲染为 `¥1,234.56`（千分位 + 两位小数），而非 `¥1,235`。
- [ ] 整数值余额（如 `1000`）显示为 `¥1,000.00` 或 `¥1,000`——与所选格式化口径一致且不丢失信息；优先统一为两位小数显示（`¥1,000.00`），与金额展示习惯一致。
- [ ] 包年客户（`is_package`）的套餐剩余额度同样显示两位小数，tooltip 文案不变。
- [ ] 列表中 30天消耗、健康度等其他使用同一格式函数的列显示不回归。
- [ ] 前端构建/类型检查通过。

## Non-Goals

- 不修改后端接口或余额计算精度。
- 不改动余额管理页（`BalanceTable.vue`）等其他页面的展示口径。

## Notes

- 单文件改动，轻量任务，PRD-only。
- 验收标准第 2 条采用固定两位小数口径（`minimumFractionDigits: 2`），使整数值也显示 `.00`。
