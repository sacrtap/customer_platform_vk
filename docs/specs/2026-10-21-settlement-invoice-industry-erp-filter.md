# 结算单管理页面新增「行业类型」「ERP系统」筛选

## Context

结算单管理页面（`结算单管理`，路由 `/billing/invoices`）筛选栏当前只有「客户名称关键词」和「状态」两个筛选项。需在筛选栏新增「行业类型」和「ERP系统」两个下拉筛选项，并支持对结算单列表的服务端筛选。这两个属性归属于客户：`erp_system` 直接存于 `Customer` 表；`industry_type` 存于 `CustomerProfile.industry_type_id`（外键 → `IndustryType.id`，按 `IndustryType.name` 匹配）。结束状态：筛选栏出现两个单选下拉，选中后列表按对应客户属性过滤，「重置」清空。

筛选语义与命名沿用客户列表后端既有约定（`backend/app/services/customers.py:276-284,313-314`）：行业按 `IndustryType.name` 匹配、ERP 按 `Customer.erp_system`（值为 `ErpSystem.value`）精确匹配，避免新建第二套口径。

## Approach

### 后端（先于前端，前端依赖后端参数）

**Step 1 — 扩展 `InvoiceService.get_invoices`**（`backend/app/services/billing.py:1434-1505`）
- 签名新增两个参数（插到 `mine_user_id` 之前或之后，保持关键字参数风格）：
  `industry_type: Optional[str] = None, erp_system: Optional[str] = None`
- 在现有筛选块（`status` 之后、`count_stmt` 之前，约 1463-1475 之间）追加：
  - `if erp_system: stmt = stmt.where(Customer.erp_system == erp_system)`（`Customer` 已在 1455 行 inner join，无需额外 join）
  - `if industry_type:` 追加两个 outerjoin 再 where（完全镜像 `customers.py:276-284`）：
    ```python
    stmt = stmt.outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
    stmt = stmt.outerjoin(IndustryType, CustomerProfile.industry_type_id == IndustryType.id)
    stmt = stmt.where(IndustryType.name == industry_type)
    ```
  - 必须在 `count_stmt = select(func.count()).select_from(stmt.subquery())`（1478 行）之前完成，使 join/where 同时作用于计数与数据查询（与客户列表同一模式）。`CustomerProfile.customer_id` 唯一，outerjoin 不产生重复行；`result.scalars().unique().all()`（1503 行）已去重，双重保险。
- 导入：将 `from ..models.customers import Customer`（31 行）改为 `from ..models.customers import Customer, CustomerProfile`；新增顶层 `from ..models.industry_type import IndustryType`（与 `app.models.industry_type` 已被其它 service 引用一致；测试 `test_industry_type_fk.py:7-8` 证实 `Customer, CustomerProfile` 与 `IndustryType` 均可从这两个模块导入）。
- 不改 `sort_field_map`、不改返回 shape、不改 `mine_user_id` 逻辑。

**Step 2 — 扩展路由 `get_invoices`**（`backend/app/routes/billing/invoices.py:103-132`）
- 在 `status = request.args.get("status")`（110 行）之后读取：
  ```python
  industry_type = request.args.get("industry_type")
  erp_system = request.args.get("erp_system")
  ```
- 在 `invoice_service.get_invoices(...)` 调用（123-132 行）追加 `industry_type=industry_type, erp_system=erp_system`。
- 权限不变（仍 `@auth_required` + `@require_permission("billing:view")`）；`customer_scope_user_id` 数据可见性不变。响应字段不增不减（列表项无需回显这两个字段，仅用于筛选）。

**Step 3 — 后端集成测试**（`backend/tests/integration/test_billing_api.py`）
- 新增 `test_get_invoices_filter_industry_type_and_erp_system`，镜像同文件 `test_get_balances_filter_erp_system_and_cooperation_status`（594 行）与客户 API 测试（`test_customers_api.py:2310-2391`）的造数范式：
  - `TRUNCATE industry_types, customer_profiles CASCADE` 后 `INSERT INTO industry_types (name, sort_order, created_at) VALUES ('互联网',1,NOW()),('房地产',2,NOW())`，取回两个 id。
  - 插入 2 个客户：客户A `erp_system='yonyou'` + profile `industry_type_id=<互联网id>`；客户B `erp_system='kingdee'` + profile `industry_type_id=<房地产id>`。
  - 为每个客户插入 1 条 invoice（`status='draft'`，必要金额字段）。
  - 断言：`GET /api/v1/billing/invoices?industry_type=互联网` → 仅含客户A的结算单；`?erp_system=kingdee` → 仅含客户B的结算单；不带筛选 → 两条都在。
- 这是 load-bearing 测试：证明 industry 按 name 匹配、ERP 按 value 匹配、outerjoin 不产生重复或遗漏。

### 前端

**Step 4 — `getInvoices` 类型签名**（`frontend/src/api/billing.ts:379-387`）
- 参数类型追加 `industry_type?: string` 和 `erp_system?: string`（与既有 `status?: string` 并列）。`exportInvoices`（556 行）不改——导出当前仅传 `status`，与本任务「列表筛选」语义一致，不扩范围。

**Step 5 — composable**（`frontend/src/composables/useInvoice.ts`）
- `defaultFilters()`（20-25 行）新增 `industry_type: ''` 与 `erp_system: ''`（与既有 `status: ''` 同为 string）。
- `loadInvoices`（155-170 行）在 `if (filters.status) params.status = filters.status`（162 行）之后追加：
  ```ts
  if (filters.industry_type) params.industry_type = filters.industry_type
  if (filters.erp_system) params.erp_system = filters.erp_system
  ```
- `handleReset`（207-211 行）`Object.assign(filters, defaultFilters())` 自动覆盖新字段，无需额外改动。

**Step 6 — 筛选组件**（`frontend/src/views/billing/components/InvoiceFilters.vue`）
- `Filters` interface（22-25 行）追加 `industry_type: string` 和 `erp_system: string`。
- script 顶部 import：`ref, computed, onMounted` from `vue`（当前仅 `defineModel`/`defineEmits` 隐式可用，需显式引入）；`getIndustryTypes` from `@/api/customers`；`getErpSystemsList` from `@/api/erpSystems`；`type { IndustryType, ErpSystem }` from `@/types`。
- 新增字典加载，完全镜像 `useCustomerList.loadIndustryTypesData/loadErpSystemsData`（`useCustomerList.ts:243-259`）的防御式解包：
  ```ts
  const industryTypes = ref<IndustryType[]>([])
  const erpSystems = ref<ErpSystem[]>([])
  onMounted(async () => {
    try { const r = await getIndustryTypes(); industryTypes.value = (r.data?.data || r.data || []) as IndustryType[] } catch (e) { console.error('加载行业类型失败:', e) }
    try { const r = await getErpSystemsList(); erpSystems.value = (r.data?.data || r.data || []) as ErpSystem[] } catch (e) { console.error('加载 ERP 系统失败:', e) }
  })
  ```
- 选项映射镜像 `CustomerFilters.vue:188-198`：
  ```ts
  const industryOptions = computed(() => industryTypes.value.map((it) => ({ label: it.name, value: it.name })))
  const erpSystemOptions = computed(() => erpSystems.value.map((es) => ({ label: es.name, value: es.value })))
  ```
  （industry 的 value 用 `name`，与后端按 name 匹配对齐；erp 的 value 用 `es.value`，与后端按 `Customer.erp_system` 精确匹配对齐。）
- 模板：在状态 `FilterDropdown`（5-10 行）之后、筛选按钮（11 行）之前插入两个单选下拉（与 `status` 同构，不带 `multiple`）：
  ```html
  <FilterDropdown v-model="filters.industry_type" label="行业类型" :options="industryOptions" @apply="emit('search')" />
  <FilterDropdown v-model="filters.erp_system" label="ERP系统" :options="erpSystemOptions" @apply="emit('search')" />
  ```
  复用现有 `FilterDropdown`（`@/components/ui/FilterDropdown.vue`）单选模式：选中即触发 `@apply` → `emit('search')` → `handleSearch` 重置到第 1 页并 `loadInvoices`；「全部」选项清空值并触发搜索。

**Step 7 — `Invoices.vue` 无需改动**：已 `v-model:filters="filters"` 绑定 useInvoice 的 reactive filters（现含新字段）；`handleExport` 保持仅传 `status`。

## Critical files & anchors

- `backend/app/services/billing.py:1434` — `get_invoices` 加 `industry_type`/`erp_system` 参数与 outerjoin/where（导入 `CustomerProfile`、`IndustryType`）
- `backend/app/routes/billing/invoices.py:103` — 路由读 `industry_type`/`erp_system` args 并透传
- `backend/tests/integration/test_billing_api.py:594` & `:1209` — 筛选测试范式镜像源
- `frontend/src/composables/useInvoice.ts:20,152` — `defaultFilters` + `loadInvoices` 参数拼装
- `frontend/src/views/billing/components/InvoiceFilters.vue:1` — 模板加两下拉 + script 加字典加载/选项映射
- `frontend/src/api/billing.ts:379` — `getInvoices` 参数类型
- 参照（不改，仅作模式来源）：`backend/app/services/customers.py:276-314`（筛选 join+where 范式）、`frontend/src/views/customers/components/CustomerFilters.vue:188-198`（选项映射范式）

## Verification

1. 后端单元/集成（证明 join+按 name/value 匹配且不重复）：
   `cd backend && .venv/bin/python -m pytest tests/integration/test_billing_api.py::test_get_invoices_filter_industry_type_and_erp_system tests/integration/test_billing_api.py::test_get_invoices_list -x`
2. 后端导入无错（确认新 import 解析）：
   `cd backend && .venv/bin/python -c "import app.services.billing; import app.routes.billing.invoices; print('ok')"`
3. 前端类型检查（确认 Filters interface 与 getInvoices 类型一致）：
   `cd frontend && npm run type-check`
4. 前端既有单测不回归（确认 defaultFilters 扩展未破坏排序逻辑测试）：
   `cd frontend && npx vitest run src/composables/__tests__/useInvoice.test.ts`
5. 端到端冒烟（手动 UI）：启动前后端，打开 `/billing/invoices`；确认「行业类型」「ERP系统」下拉出现且有选项；选「行业类型=互联网」→ 列表仅剩该行业客户的结算单；选「ERP系统=yonyou」→ 仅剩对应客户；点「重置」→ 两个下拉清空、列表恢复全量。无运行环境则报告为冒烟限制，以 1-4 的证据为准。

## Assumptions & contingencies

- **单选下拉**（默认）：两个新筛选用 `FilterDropdown` 单选模式，与该页既有「状态」筛选一致，且一个客户只有一个行业类型/一个 ERP 系统。若需多选：industry 改 `multiple` 并发逗号串，后端按 `IndustryType.name.in_(...)`（`customers.py:283-284` 已有同款）；erp 多选需后端改 `Customer.erp_system.in_(...)`。默认单选，不扩。
- **参数命名**：`industry_type`（值为行业**名称**）与 `erp_system`（值为 `ErpSystem.value`）。与客户列表后端「按 name 匹配 industry、按 value 匹配 erp」的语义一致，复用成熟 join 模式。客户列表的参数名为 `industry`；本结算单端点用 `industry_type` 更直观，两端点无耦合。
- **导出不扩范围**：`exportInvoices`/`handleExport` 当前仅传 `status`（连 keyword 都不传），保持不变与本任务「列表筛选」语义一致。
- **选项接口**：用 `getIndustryTypes()`（`/dicts/industry_types`）与 `getErpSystemsList()`（`/erp-systems`），均为客户页已在用、返回 `IndustryType[]`/`ErpSystem[]`，配合防御式解包 `res.data?.data || res.data || []`。
- **兜底**：若 `/dicts/industry_types` 返回结构使防御式解包取不到数组（运行时下拉为空），改用 `getIndustryTypesList()`（`@/api/industryTypes.ts` → `/industry-types`，返回 `{ data: IndustryType[] }`），`IndustryType[]` 形状一致，映射不变。
