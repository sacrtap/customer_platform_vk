# 技术设计：客户结算账户（代扣余额）

完整执行计划见 `docs/specs/2026-10-21-settlement-account-plan.md`，本文件记录设计要点与边界。

## 数据模型

- `Customer.settlement_account_id: Mapped[int | None]` → FK `customers.id`，indexed，nullable。
- `Invoice.settlement_account_id: Mapped[int | None]` → FK `customers.id`，indexed，nullable；关系 `settlement_account = relationship("Customer", foreign_keys=[settlement_account_id], lazy="selectin")`（`Invoice.customer` 已存在，必须 `foreign_keys` 消歧）。
- 迁移 `down_revision = x3y4z5a6b7c8`；两列 nullable 无默认 → 历史行自动 NULL，无 backfill。

## 核心改动单点

扣款传参：`consume(customer_id=(invoice.settlement_account_id or invoice.customer_id), ...)`，位于 `_execute_deduction` 与 `complete_invoice` 两处；`confirm_invoice`/`retry_deduction` 经 `_execute_deduction` 自动覆盖。`consume` 本身不改。

## 服务层契约

- `InvoiceService.update_settlement_account(invoice_id, settlement_account_id)`：状态校验（审批流四态外返回错误）→ scope 可见性 → 自引用拒绝 → 目标存在校验 → 写库 + 审计 + 清缓存。
- `CustomerService.update_customer`：`settlement_account_id` 进 `updatable_fields`；白名单循环前自引用/存在校验，抛 `ValueError`（路由已捕获 → 40003）。`batch_update_customers` 拒绝该字段。
- `generate_invoice`：内部经 `_get_customer(customer_id)` 取客户快照；batch 自动覆盖，不改签名。

## 序列化

- `get_invoices` / `get_invoice` 路由手动 dict 加 `settlement_account_id` + `settlement_account_name`（`i.settlement_account.name if i.settlement_account else None`）。
- service 两处 `selectinload` 加 `selectinload(Invoice.settlement_account)`。

## 消耗记录可见性

`get_consumption_records`（`routes/billing/balances.py`）：`customer_id` 过滤改 `or_(ConsumptionRecord.customer_id == customer_id, ConsumptionRecord.invoice_id.in_(select(Invoice.id).where(Invoice.customer_id == customer_id)))`；`scope_user_id` 判定用 `or_` 包两套 manager 判定（cr.customer 或 invoice.customer）。

## 前端

- 类型：`Customer` / `Invoice` 接口加 `settlement_account_id` + `settlement_account_name`。
- 表单三入口复用 `CustomerAutoComplete.vue`（emit `update:modelValue`）或 `CustomerSearchInput.vue`；占位「留空使用自身余额」；前端自引用校验。
- `InvoiceDetailDrawer.vue` 加「结算账户」行：只读显示（空=「自身」），审批流中显示编辑入口，确认后禁用。
- `useInvoice.ts` 加 `doUpdateSettlementAccount`。

## 兼容与回滚

- 无 API 破坏性变更（新增可选字段 + 新路由）。
- 回滚：迁移 downgrade 删两列；包年客户作结算账户若引发语义混淆，回退点为账户校验追加 `settlement_type=='prepaid'` 限制（仅用户反馈后启用）。

## 已知取舍

- 结算账户名称走关系 join（与 `Invoice.customer` 一致）：改名/软删后显示当前名/可能空，不存历史名快照。
- 代扣笔 `balance_after` 为结算账户客户余额，被结算客户列表中可能困惑——靠 `invoice_no`/`customer_id` 列区分，不加标记列。
