# 执行计划：结算单管理页面新增行业类型/ERP系统筛选

按 spec `docs/specs/2026-10-21-settlement-invoice-industry-erp-filter.md` 的 Approach 顺序执行。后端先于前端。

## 1. 后端 — 扩展 `InvoiceService.get_invoices`

文件 `backend/app/services/billing.py`（锚点约 1434-1505）

- [ ] 导入：`from ..models.customers import Customer` → `Customer, CustomerProfile`；新增 `from ..models.industry_type import IndustryType`
- [ ] 签名新增 `industry_type: Optional[str] = None, erp_system: Optional[str] = None`（关键字参数风格，置于 `mine_user_id` 附近）
- [ ] 筛选块（`status` 之后、`count_stmt` 之前）追加：
  - `if erp_system: stmt = stmt.where(Customer.erp_system == erp_system)`
  - `if industry_type:` 两个 outerjoin（`CustomerProfile`、`IndustryType`）+ `where(IndustryType.name == industry_type)`，镜像 `backend/app/services/customers.py:276-284`
- [ ] 不改 `sort_field_map`、返回 shape、`mine_user_id` 逻辑

## 2. 后端 — 扩展路由

文件 `backend/app/routes/billing/invoices.py`（锚点约 103-132）

- [ ] `status = request.args.get("status")` 之后读 `industry_type` / `erp_system`
- [ ] `invoice_service.get_invoices(...)` 调用透传两个新参数

## 3. 后端 — 集成测试

文件 `backend/tests/integration/test_billing_api.py`

- [ ] 新增 `test_get_invoices_filter_industry_type_and_erp_system`，镜像 `test_get_balances_filter_erp_system_and_cooperation_status`（594 行附近）与 `test_customers_api.py:2310-2391` 造数范式
- [ ] 断言：`?industry_type=互联网` 仅含客户A；`?erp_system=kingdee` 仅含客户B；无筛选两条都在

## 4. 前端 — `getInvoices` 类型签名

文件 `frontend/src/api/billing.ts`（锚点约 379-387）

- [ ] 参数类型追加 `industry_type?: string` 和 `erp_system?: string`
- [ ] `exportInvoices`（556 行附近）不改

## 5. 前端 — composable

文件 `frontend/src/composables/useInvoice.ts`

- [ ] `defaultFilters()`（20-25 行）新增 `industry_type: ''` 与 `erp_system: ''`
- [ ] `loadInvoices`（155-170 行）在 status 拼参后追加两个 if 拼参
- [ ] `handleReset` 无需改动（`Object.assign(filters, defaultFilters())` 自动覆盖）

## 6. 前端 — 筛选组件

文件 `frontend/src/views/billing/components/InvoiceFilters.vue`

- [ ] `Filters` interface 追加 `industry_type: string` 和 `erp_system: string`
- [ ] import：`ref, computed, onMounted` from `vue`；`getIndustryTypes` from `@/api/customers`；`getErpSystemsList` from `@/api/erpSystems`；`type { IndustryType, ErpSystem }` from `@/types`
- [ ] 字典加载镜像 `useCustomerList.ts:243-259` 防御式解包
- [ ] 选项映射镜像 `CustomerFilters.vue:188-198`（industry value=name；erp value=es.value）
- [ ] 模板：状态 `FilterDropdown` 之后、筛选按钮之前插入两个单选下拉

## 7. 前端 — `Invoices.vue` 无需改动

确认 `v-model:filters` 绑定与 `handleExport` 行为不变即可。

## 验证命令（按 spec Verification）

1. `cd backend && .venv/bin/python -m pytest tests/integration/test_billing_api.py::test_get_invoices_filter_industry_type_and_erp_system tests/integration/test_billing_api.py::test_get_invoices_list -x`
2. `cd backend && .venv/bin/python -c "import app.services.billing; import app.routes.billing.invoices; print('ok')"`
3. `cd frontend && npm run type-check`
4. `cd frontend && npx vitest run src/composables/__tests__/useInvoice.test.ts`
5. 端到端 UI 冒烟（有运行环境则执行；无则报告冒烟限制，以 1-4 为准）

## Rollback

每步独立可回退；未提交前直接 checkout 改动文件即可。提交后 revert 单次提交。
