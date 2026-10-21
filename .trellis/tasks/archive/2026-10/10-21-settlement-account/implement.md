# 执行计划：客户结算账户（代扣余额）

顺序执行，每步完成后跑对应验证。基线分支：`feat/customer-withholding-settlement`。

## A. 数据模型与迁移

- [ ] A1 `backend/app/models/customers.py`：`Customer` 加 `settlement_account_id`（自引用 FK，nullable，index）
- [ ] A2 `backend/app/models/billing.py`：`Invoice` 加 `settlement_account_id` + `settlement_account` 关系（`foreign_keys` 消歧，`lazy="selectin"`）
- [ ] A3 新迁移 `backend/alembic/versions/y4z5a6b7c8d9_add_settlement_account.py`（down_revision=`x3y4z5a6b7c8`）
- [ ] 验证：`.venv/bin/alembic upgrade head` + `.venv/bin/alembic downgrade -1` + 再 upgrade

## B. 客户管理

- [ ] B1 `services/customers.py`：`create_customer` 构造加字段；`update_customer` 白名单 + 自引用/存在校验；`batch_update_customers` 拒绝
- [ ] B2 `routes/customers.py`：docstring 补字段说明（透传不改）
- [ ] B3 前端：`types/index.ts`、`api/customers.ts` 类型
- [ ] B4 前端表单：AddCustomerModal / EditCustomerDialog / CustomerFormModal / useCustomerDetail（含前端自引用校验）
- [ ] B5 前端详情展示：结算账户：{name} 或「自身」

## C. 生成快照

- [ ] C1 `services/billing.py generate_invoice`：经 `_get_customer` 取 `settlement_account_id` 写入 Invoice

## D. 扣款走结算账户

- [ ] D1 `_execute_deduction`：consume 传参改 `invoice.settlement_account_id or invoice.customer_id` + 存在校验
- [ ] D2 `complete_invoice`：同上

## E. 结算单详情查看/修改

- [ ] E1 service：`get_invoice_by_id` / `get_invoices` 加 `selectinload(Invoice.settlement_account)`
- [ ] E2 service：新增 `update_settlement_account`
- [ ] E3 路由：`PUT /invoices/<id>/settlement-account`（`@auth_required` + `billing:edit`）；列表/详情 dict 加两字段
- [ ] E4 前端：`api/billing.ts` 类型 + `updateInvoiceSettlementAccount`；`useInvoice.ts` `doUpdateSettlementAccount`
- [ ] E5 前端：`InvoiceDetailDrawer.vue` 结算账户行 + 编辑入口

## F. 消耗记录可见性

- [ ] F1 `routes/billing/balances.py get_consumption_records`：OR 查询 + scope 放宽

## G. 测试

- [ ] G1 `tests/unit/test_billing_service.py`：快照、扣款走结算账户、update_settlement_account 锁定/自引用
- [ ] G2 `tests/unit/test_customer_service.py`：往返、自引用拒绝、目标不存在拒绝
- [ ] G3 `tests/integration/test_billing_api.py`：详情修改各状态、扣款、消耗记录可见
- [ ] G4 `tests/integration/test_customers_api.py`：字段往返
- [ ] G5 `tests/integration/test_migrations.py`：新迁移 upgrade/downgrade
- [ ] G6 全量：`ruff check app/`、`pyright`、pytest 相关文件、coverage ≥50%
- [ ] G7 前端：`pnpm type-check`

## H. 端到端验证（spec Verification 1-6,8）

- [ ] H1 迁移应用到运行库 + `scripts/check_schema_drift.py` 无漂移
- [ ] H2 起后端 API 验证：客户配置往返/自引用 400、生成快照、详情改/锁定、扣款走结算账户（B 减 A 不变）、消耗记录双方可见
- [ ] H3 前端 dev 冒烟：客户编辑弹窗、结算单详情抽屉显示/编辑

## 检查门

- 每阶段完成跑对应单测；全部完成后跑 ruff + pyright + 全量 pytest + coverage
- schema drift 检查必须通过（防「写了迁移≠运行库已升级」）
