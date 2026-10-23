# 客户「是否对账」属性 — 需求

## 背景

客户管理页面需要新增「是否对账」属性，控制结算单是否走完整确认流程。排查确认现有 `auto_initiate_settlement`（自动发起结算）是死字段——所有结算业务逻辑均不读取它，仅在模型/CRUD/筛选/表单/导入导出/测试中空转。用户决策：移除该字段，新增独立 `require_reconciliation`。

## 需求

1. 客户新增「是否对账」属性（`require_reconciliation`），**默认「否」**。
2. 「否」：结算单提交（submit）时跳过运营经理、商务经理确认，`draft → pending_customer`（直接待客户确认）。
3. 「是」：走完整流程 `draft → pending_ops → pending_sales → pending_customer`，且**保存客户时强制**运营经理（`manager_id`）与商务经理（`sales_manager_id`）非空。
4. 流程条不改结构，跳过的确认步由 Arco Steps 自动标为已完成。

## 范围外

- 不新增按「是否对账」的筛选项（客户/余额筛选器删除 auto 项后不补）。
- `is_settlement_enabled`（是否启用结算）语义独立，不动。
- `confirm_ops`/`confirm_sales`/`generate_invoice`/`generate_invoices_batch` 行为不变。

## 验收标准

- [ ] AC1 迁移：`require_reconciliation` 列建立（`server_default=false`），`auto_initiate_settlement` 列删除，`alembic heads` 显示新 head。
- [ ] AC2 模型/服务：创建客户默认 `require_reconciliation=False`；`True` 但缺 `manager_id`/`sales_manager_id` → ValueError → 400；补齐经理创建成功。
- [ ] AC3 更新客户：`require_reconciliation` 可更新；开对账时综合传入值与现有值校验经理非空；显式传 `manager_id=None` 清空同样被拦截。
- [ ] AC4 submit 分流：`require_reconciliation=False`（含历史迁移后默认否）→ `draft → pending_customer`（即使客户有经理）；`True` + 有 manager → `pending_ops`；`True` + 无 manager 有 sales → `pending_sales`。
- [ ] AC5 存量兼容：现有 `pending_ops`/`pending_sales`/`pending_customer` 状态结算单不受影响。
- [ ] AC6 前端：客户表单 label「是否对账」，是/否选项默认否；开对账=是时经理字段前端 required 拦截；客户详情 tab 展示「是否对账」标签。
- [ ] AC7 回归：后端全量测试通过且覆盖率 ≥50% 不退化；`npm run type-check`、`npm run test` 通过。
- [ ] AC8 UI 端到端：新增客户开对账=是不填经理被前端拦截、填齐保存成功；不开对账不填经理保存成功；「否」客户结算单 submit 后状态 `pending_customer`；「是」客户 submit 后 `pending_ops`。
