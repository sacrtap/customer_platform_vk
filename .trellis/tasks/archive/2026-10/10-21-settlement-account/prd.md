# 支持客户代扣结算功能（客户结算账户 / 代扣余额）

## Goal

客户信息新增「结算账户」字段：空 = 用自身 `CustomerBalance` 结算；非空 = 用所选客户的余额结算。生成结算单时快照该配置到结算单，扣款按快照执行，结算单详情可查看/修改，消耗记录对「被结算客户」可见。

需求来源：`docs/specs/2026-10-21-settlement-account-plan.md`（执行计划，技术细节以该文档为准）。

## Requirements

1. **客户配置**：`Customer.settlement_account_id` 自引用 FK（nullable，默认空），客户新增/编辑表单可选已有客户；历史客户一律 NULL（空 = 自身余额）。禁止自引用（`== 自身` 拒绝，前后端双保险），目标客户必须存在且未删除。批量更新与 Excel 导入**不支持**该字段。
2. **生成快照**：`generate_invoice`（含 batch 路径）生成时把客户当前 `settlement_account_id` 写入 `Invoice.settlement_account_id`。
3. **扣款走快照**：`_execute_deduction` / `complete_invoice`（覆盖 `confirm_invoice`、`retry_deduction`）扣款 `customer_id` 由 `invoice.customer_id` 改为 `invoice.settlement_account_id or invoice.customer_id`；结算账户客户不存在时扣款失败返回明确错误。`ConsumptionRecord.customer_id` 记实际被扣余额的客户（不改 `consume` 本身）。
4. **详情查看/修改**：结算单列表/详情序列化暴露 `settlement_account_id` / `settlement_account_name`；`PUT /invoices/<id>/settlement-account` 仅在审批流中（`draft/pending_ops/pending_sales/pending_customer`）可改，`customer_confirmed` 及之后锁定；自引用/目标不存在拒绝；审计日志。
5. **消耗记录可见性**：`GET /billing/consumption-records?customer_id=A` 同时返回扣 A 自身余额的记录与「A 的结算单、扣结算账户余额」的记录（OR 查询 + scope_user_id 可见性相应放宽）。
6. **前端**：客户表单三处入口（AddCustomerModal / EditCustomerDialog / CustomerFormModal）+ 详情展示；结算单详情抽屉显示「结算账户」并在可改状态可编辑。

## Acceptance Criteria

- [ ] 迁移可 upgrade/downgrade，两列 nullable 无默认，历史行 NULL
- [ ] 客户配置往返 API 成功；自引用/目标不存在返回 400
- [ ] 生成结算单快照结算账户；详情/列表序列化含 `settlement_account_id/name`
- [ ] 客户 A（结算账户=B）确认扣款后：B 的 `total_amount` 减、`used_total` 增；A 余额不变；`ConsumptionRecord.customer_id == B`
- [ ] `customer_confirmed` 后修改结算账户返回 400；审批流中修改成功并记审计
- [ ] 消耗记录查询对 A、B 均含该笔
- [ ] 后端 pytest 相关文件全绿，CI 合并覆盖率 ≥50%；`ruff` / `pyright` 通过；前端 `pnpm type-check` 通过
- [ ] 迁移已应用到运行库（`alembic upgrade head` + `scripts/check_schema_drift.py` 无漂移）

## Notes

- 业务决策（已确认）：可修改时机=审批流中；可选账户=任意客户（不限制类型）；消耗记录归属=实际扣款客户。
- 包年/后付费客户作结算账户按「任意」实现，预留回退点（仅用户反馈后加 `settlement_type=='prepaid'` 限制）。
- `alembic heads` 当前单 head：`x3y4z5a6b7c8`。
