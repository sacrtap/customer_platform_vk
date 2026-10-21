# 结算账户（代扣余额）执行计划

## Context

当前大部分客户用自身 `CustomerBalance` 结算，少数客户需用**其他客户的余额**结算。需求四点：
1. 客户信息增加「结算账户」字段（默认空），空=用自身余额，非空=用所选客户的余额；用客户搜索输入框选择已有客户。
2. 生成结算单时在单上体现结算账户（自身或具体客户名）供核验。
3. 完成结算时按**结算单上标记的结算账户**扣款；因存在时间差，以生成结算单时为准（快照），并支持在结算单详情页查看/修改。
4. 新字段默认空，已有客户一律按空值存储。

已通过 codegraph + read 全链路确认影响范围。已确认三项业务决策（本轮 ask）：
- **可修改时机**：审批流中（`draft/pending_ops/pending_sales/pending_customer`）可改，`customer_confirmed` 及之后锁定。
- **可选账户范围**：任意客户（不限制类型），扣款一律走 `CustomerBalance`，余额不足记为欠费（负数，consume 已支持）。
- **消耗记录归属**：`ConsumptionRecord.customer_id` 记实际被扣余额的客户；**被结算客户也可见**该笔（通过 `invoice.customer_id` 关联查询）。

方案评估：用户方案（Customer 自引用 FK + Invoice 快照）是「代付/代扣」标准模式，无更优替代。独立「结算账户实体」对单字段自引用需求属过度设计，不采用。

## 核心链路事实（已确认，勿重复探查）

- 扣款核心：`BalanceService.consume(customer_id, amount, invoice_id)`（`backend/app/services/billing.py:221`）按传入 `customer_id` 锁 `CustomerBalance` 行（FOR UPDATE）先赠后实扣减，写 `ConsumptionRecord(customer_id=<传入的>, invoice_id=..., balance_after=...)`。
- **两条扣款入口**均传 `invoice.customer_id`：
  - `_execute_deduction`（`billing.py:1714`，由 `confirm_invoice:1668` 与 `retry_deduction:1691` 调用）
  - `complete_invoice`（`billing.py:1773`，`paid→completed` 旧流程）
- 生成：`InvoiceService.generate_invoice`（`billing.py:1369`）仅接收 `customer_id`，内部不查 `Customer`；`generate_invoices_batch`（`billing.py:1919`）循环调它。
- 序列化：列表 `get_invoices` 路由（`invoices.py:100`，手动 dict 144-170）与详情 `get_invoice` 路由（`invoices.py:177`，dict 297-355）；`get_invoice_by_id`（`billing.py:1519`）与 `get_invoices`（`billing.py:1435`）用 `selectinload(Invoice.customer)`。
- 客户白名单：`create_customer`（`services/customers.py:637`）显式构造字段；`update_customer`（`:703`）`updatable_fields`（`:721-743`）白名单；路由 `create/update/batch_update`（`routes/customers.py:555/626/718`）透传 `data` dict。
- 前端可复用：`CustomerSearchInput.vue`（emit `select {id,name,company_id}`）、`CustomerAutoComplete.vue`（emit `update:modelValue=customerId`，更适合表单 id 绑定）。
- 消耗记录查询：`get_consumption_records`（`routes/billing/balances.py:1815`）按 `ConsumptionRecord.customer_id == customer_id` 过滤，含 `scope_user_id` 可见性 join。
- 迁移：Alembic `backend/alembic/versions/`，标准 `op.add_column` 模式（参考 `w2x3y4z5a6b7_add_balance_warning_to_customers.py`）。

## Approach

### A. 数据模型与迁移

1. **`backend/app/models/customers.py`** `Customer`（约 `is_disabled` 字段后）：新增字段
   `settlement_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("customers.id"), nullable=True, index=True)` — 结算账户客户 ID，NULL=用自身余额。

2. **`backend/app/models/billing.py`** `Invoice`（`created_by` 字段后）：新增
   `settlement_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("customers.id"), nullable=True, index=True)` — 生成时快照。
   并新增关系（`customer` 关系已存在，需 `foreign_keys` 消歧）：
   `settlement_account = relationship("Customer", foreign_keys=[settlement_account_id], lazy="selectin")`

3. **新迁移** `backend/alembic/versions/<rev>_add_settlement_account.py`：`down_revision` 取 `alembic heads` 当前值（运行 `cd backend && .venv/bin/alembic heads` 确认；目录最后文件为 `x3y4z5a6b7c8_add_remark_to_balance_whitelists`）。`upgrade` 对 `customers`、`invoices` 各 `op.add_column(... settlement_account_id, Integer, nullable=True)` + `op.create_index`；`downgrade` 反向。两列 nullable 无默认 → 历史行自动 NULL（满足需求第 4 点，无需 backfill）。

### B. 客户管理（配置来源）

4. **`backend/app/services/customers.py`**
   - `create_customer`（:637）：`Customer(...)` 构造加 `settlement_account_id=data.get("settlement_account_id")`。
   - `update_customer`（:703）：`updatable_fields` 列表加 `"settlement_account_id"`；在白名单循环前加自引用校验：若 `data.get("settlement_account_id") == customer_id` 抛 `ValueError("结算账户不能为客户自身")`；若非空则校验目标客户存在且未删除（`select(Customer.id).where(id==val, deleted_at.is_(None))`，不存在抛 `ValueError("结算账户客户不存在")`）。
   - `batch_update_customers`：**不**将 `settlement_account_id` 纳入批量可改字段（敏感关系，逐个改）。若该字段出现在 `fields`，服务层忽略或拒绝（按现有批量实现校验逻辑处理，拒绝更安全）。

5. **`backend/app/routes/customers.py`**：`create_customer`/`update_customer` docstring 补字段说明；其余透传无需改。`update_customer` 的 `ValueError` 已被现有 `except ValueError` 捕获返回 40003。

6. **前端类型** `frontend/src/types/index.ts` `Customer` 接口：加 `settlement_account_id?: number | null`、`settlement_account_name?: string | null`。

7. **`frontend/src/api/customers.ts`**：`createCustomer`/`updateCustomer` 入参类型加 `settlement_account_id?: number | null`。

8. **客户表单组件**（新增「结算账户」字段，复用 `CustomerAutoComplete.vue` 绑定 id，或 `CustomerSearchInput` 监听 `select` 事件赋值）：
   - `frontend/src/views/customers/components/AddCustomerModal.vue`（`CreateForm` 加 `settlement_account_id`，提交 payload 含该字段）
   - `frontend/src/views/customers/detail/EditCustomerDialog.vue`（`EditForm` 加字段，`createDefaultForm` 与 `handleSubmit` payload 含该字段，回填 `props` 客户数据）
   - `frontend/src/views/customers/components/CustomerFormModal.vue`（`CustomerForm` 与 `handleCustomerSubmit` 的 `data` 加字段）
   - `frontend/src/composables/useCustomerDetail.ts` `editForm`（:80-103）加 `settlement_account_id: undefined as number | null | undefined`。
   - 字段默认空（`null`/`undefined`），占位提示「留空使用自身余额」。
   - **自引用前端校验**：选择后若 `id === 编辑中的客户 id`，提示「不能选择客户自身」并清空（与后端校验双保险）。

9. **客户详情基本信息展示**（`Detail.vue` 基础信息 tab / `useCustomerDetail`）：展示「结算账户：{name}」或「自身」（`settlement_account_id` 为空时）。客户列表 `CustomerTable.vue` **不加**该列（避免列膨胀；详情可见即可）。

### C. 结算单生成（快照）

10. **`backend/app/services/billing.py` `generate_invoice`**（:1369）：方法内用现有 `_get_customer(customer_id)`（:1746）查客户，将 `customer.settlement_account_id` 写入新建 `Invoice(... settlement_account_id=customer.settlement_account_id ...)`。批量 `generate_invoices_batch` 经此方法自动覆盖（无需改 batch 签名；可接受 N 次客户查询，批量量级有限）。

11. **`backend/app/routes/billing/invoices.py`** `generate_invoice`/`generate_invoices_batch` 路由：不改（快照在 service 层）。

### D. 完成结算（按结算单标记扣款）

12. **`backend/app/services/billing.py`**：
    - `_execute_deduction`（:1714）：`consume(customer_id=invoice.customer_id, ...)` → `consume(customer_id=(invoice.settlement_account_id or invoice.customer_id), ...)`。扣款前若 `invoice.settlement_account_id` 非空，校验该客户存在（`_get_customer`），不存在则 `return False, "结算账户客户不存在"`。
    - `complete_invoice`（:1773）：同上改 `consume` 的 `customer_id` 与校验。
    - `retry_deduction`（:1691）：无需单独改（经 `_execute_deduction`）。
    - `confirm_invoice`（:1668）：无需单独改（经 `_execute_deduction`）。

13. **消耗记录语义**：`consume` 写 `ConsumptionRecord(customer_id=<结算账户客户>, ...)` 自然成立（传入即结算账户客户）。`balance_after` 为结算账户客户扣款后余额——符合余额账本语义。**不改 `consume` 本身**。

### E. 结算单详情查看/修改

14. **后端新路由** `backend/app/routes/billing/invoices.py`：
    `PUT /invoices/<invoice_id:int>/settlement-account`，`@auth_required @require_permission("billing:edit")`，body `{ "settlement_account_id": int | null }`。
    - 校验 `invoice.status in ("draft","pending_ops","pending_sales","pending_customer")`，否则 400「客户确认后不可修改结算账户」。
    - `_ensure_invoice_scope` 数据可见性。
    - 自引用校验：`settlement_account_id == invoice.customer_id` → 400。
    - 非空时校验目标客户存在。
    - 写 `invoice.settlement_account_id`，`commit`，审计日志（`create_audit_entry` action=`update_settlement_account`），清缓存。
    - service 层加 `InvoiceService.update_settlement_account(invoice_id, settlement_account_id)` 封装上述逻辑。

15. **`backend/app/services/billing.py` `get_invoice_by_id`**（:1519）：`selectinload` 加 `selectinload(Invoice.settlement_account)`。

16. **`backend/app/services/billing.py` `get_invoices`**（:1435）：`selectinload` 加 `selectinload(Invoice.settlement_account)`。

17. **`backend/app/routes/billing/invoices.py`** 序列化加字段：
    - 列表 `get_invoices`（:144-170 dict）：加 `"settlement_account_id": i.settlement_account_id, "settlement_account_name": i.settlement_account.name if i.settlement_account else None`。
    - 详情 `get_invoice`（:297-355 dict）：同上两字段。

18. **前端类型** `frontend/src/api/billing.ts` `Invoice` 接口（:308）：加 `settlement_account_id?: number | null`、`settlement_account_name?: string | null`。

19. **前端 API** `frontend/src/api/billing.ts`：加 `export function updateInvoiceSettlementAccount(id, data: { settlement_account_id: number | null }) { return api.put(\`/billing/invoices/${id}/settlement-account\`, data) }`。

20. **`frontend/src/composables/useInvoice.ts`**：加 `doUpdateSettlementAccount(invoiceId, accountId)` 调上述 API，成功后 `fetchDetail` 刷新 + `loadInvoices`。

21. **结算单详情抽屉** `frontend/src/views/billing/components/InvoiceDetailDrawer.vue`：加「结算账户」行——只读显示 `settlement_account_name`（空显示「自身」）；当 `invoice.status in ('draft','pending_ops','pending_sales','pending_customer')` 时显示编辑入口（复用 `CustomerAutoComplete` 选择客户，含「清空=使用自身」），调 `doUpdateSettlementAccount`。客户确认后禁用编辑。

### F. 消耗记录（被结算客户也可见）

22. **`backend/app/routes/billing/balances.py` `get_consumption_records`**（:1815）：当 `customer_id` 给定时，过滤改为
    `or_(ConsumptionRecord.customer_id == customer_id, ConsumptionRecord.invoice_id.in_(select(Invoice.id).where(Invoice.customer_id == customer_id)))`。
    即：被结算客户 A 既看到扣自己余额的记录（`cr.customer_id==A`），也看到用自己结算单但扣别人余额的记录（`invoice.customer_id==A`，`cr.customer_id=结算账户`）。
    - `scope_user_id` 可见性 join 需相应放宽：scope 校验改为「cr.customer 或 关联 invoice.customer 任一归属该用户」——用 `or_` 包两套 manager 判定，避免被结算客户因 cr 指向别人而漏看。
    - 序列化不变（已含 `customer_id`/`invoice_no`）。前端 `RechargeRecordModal` 不改（后端已含被结算客户记录）。对「代扣笔」`balance_after` 是结算账户客户余额，语义正确（余额账本随实际扣减方）。

### G. 测试（CI 覆盖率 ≥50%，全量口径）

23. **`backend/tests/unit/test_billing_service.py`**：
    - `consume` 用 `invoice.settlement_account_id` 时扣的是该客户余额、`ConsumptionRecord.customer_id` 为结算账户客户。
    - `complete_invoice`/`_execute_deduction`/`retry_deduction` 走结算账户。
    - `generate_invoice` 快照 `settlement_account_id` = 客户当前值。
    - `update_settlement_account` 状态锁定与自引用拒绝。
24. **`backend/tests/unit/test_customer_service.py`**：`create/update` 含 `settlement_account_id` 往返；自引用拒绝；目标不存在拒绝。
25. **`backend/tests/integration/test_billing_api.py`**：详情修改结算账户（各状态权限/锁定）；扣款经结算账户；消耗记录被结算客户可见。
26. **`backend/tests/integration/test_customers_api.py`**：字段往返。
27. **`backend/tests/integration/test_migrations.py`**：新迁移 upgrade/downgrade。

## Critical files & anchors

- `backend/app/services/billing.py` — `consume:221`（不改逻辑，传参变）、`_execute_deduction:1714`、`complete_invoice:1773`、`generate_invoice:1369`、`get_invoice_by_id:1519`、`get_invoices:1435`，新增 `update_settlement_account`。扣款传参由 `invoice.customer_id` 改为 `invoice.settlement_account_id or invoice.customer_id` 是本需求的核心单点改动。
- `backend/app/models/billing.py` — `Invoice:121`（加字段 + settlement_account 关系，foreign_keys 消歧）。
- `backend/app/models/customers.py` — `Customer:22`（加 `settlement_account_id` 自引用 FK）。
- `backend/app/routes/billing/invoices.py` — `get_invoices:100`/`get_invoice:177` 序列化加字段；新增 `PUT /invoices/<id>/settlement-account`。
- `backend/app/routes/billing/balances.py` — `get_consumption_records:1815` 查询改 OR + scope 放宽。
- `frontend/src/views/billing/components/InvoiceDetailDrawer.vue` + `frontend/src/views/customers/detail/EditCustomerDialog.vue` — 前端两处编辑入口（结算单详情改、客户配置改）。

## Verification

前置：`cd backend`，用 `.venv`（Python 3.12）。数据库迁移后验证。

1. **迁移**：`.venv/bin/alembic upgrade head` 成功；`psql` 确认 `customers.settlement_account_id`、`invoices.settlement_account_id` 列存在且历史行均为 NULL。
2. **客户配置往返**：起后端，`PUT /api/v1/customers/<A>` body `{"settlement_account_id": <B>}` 返回成功；`GET /api/v1/customers/<A>` 含 `settlement_account_id=B, settlement_account_name=<B名>`。自引用 `{"settlement_account_id": <A>}` 返回 400。
3. **生成快照**：对配置了 `settlement_account_id=B` 的客户 A，`POST /billing/invoices/generate` 生成结算单；`GET /billing/invoices/<id>` 含 `settlement_account_id=B, settlement_account_name=<B名>`。
4. **详情修改**：对该单（status=draft）`PUT /billing/invoices/<id>/settlement-account {"settlement_account_id": <C>}` 成功；将单推进到 `customer_confirmed` 后再调该接口返回 400。
5. **扣款走结算账户**（端到端核心）：客户 B 充值 `POST /billing/recharge`（real=1000）；客户 A 生成结算单（金额 300，结算账户=B）；走 `confirm` 触发自动扣款 → `GET /billing/customers/<B>/balance` 的 `total_amount` 减 300、`used_total` 增 300；`GET /billing/customers/<A>/balance` 余额**不变**（A 余额未被扣）。
6. **消耗记录被结算客户可见**：`GET /billing/consumption-records?customer_id=<A>` 列表含该笔（`invoice_no` 指向 A 的单，`customer_id=B`）；`GET /billing/consumption-records?customer_id=<B>` 也含该笔。
7. **单元/集成测试**：`cd backend && .venv/bin/python -m pytest tests/unit/test_billing_service.py tests/unit/test_customer_service.py tests/integration/test_billing_api.py tests/integration/test_customers_api.py -q` 全绿；`coverage` 合并 ≥50%。
8. **前端**：`cd frontend && pnpm dev`，客户编辑弹窗可选/清空结算账户；结算单详情抽屉显示「结算账户」并在可改状态可编辑。余额管理页 B 客户行余额下降、A 不变。

## Assumptions & contingencies

- **自引用禁止**：`settlement_account_id == 自身` 视为非法（等价于 null 但易误操作），前后端均拒绝。非用户偏好，为防误操作默认。
- **结算账户为客户主键快照，名称走关系 join**：与现有 `Invoice.customer` 一致，不冗余存名。若结算账户客户后续改名/软删，详情显示当前名/可能空——与现有 `customer` 行为一致，可接受。若需历史名快照，作为后续增强，不在本次范围。
- **批量改结算账户**：不支持（敏感关系，逐个改）。客户导入 Excel 也不含该列（本次不扩展导入模板）。
- **结算账户客户被软删**：扣款时 `_get_customer` 校验存在，不存在则扣款失败返回明确错误（单保持 `customer_confirmed`/`paid` 可改账户后重试）。
- **包年/后付费客户作结算账户**：用户选「任意客户」。`consume` 走 `CustomerBalance`，包年客户年费不进 `CustomerBalance`（与余额管理页口径不同），扣的是其 `CustomerBalance.total_amount`（可能为 0 → 欠费负数）。这是用户明确选择的范围；若运行中出现包年客户作结算账户导致余额语义混淆，**回退**：在 `update_settlement_account` 与客户表单校验中追加 `settlement_type=='prepaid'` 限制——但仅在用户反馈后启用，本次按「任意」实现。
- **消耗记录 `balance_after` 对被结算客户**：代扣笔的 `balance_after` 是结算账户客户扣款后余额，在被结算客户列表中展示可能引起困惑——这是「被结算客户也可见」选择的固有代价，前端靠 `invoice_no`/`customer_id` 列区分。不额外加标记列。
- **`alembic heads` 多分支**：若 `alembic heads` 返回多个，需先合并或确认主线；计划假设单 head。实现时先跑 `alembic heads`，多 head 则停下询问。
