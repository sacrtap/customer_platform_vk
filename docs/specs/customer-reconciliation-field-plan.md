# 客户「是否对账」属性 — 执行方案

## Context

客户管理页面需要新增「是否对账」属性，控制结算单是否走完整确认流程：
- **默认「否」**：结算单提交时跳过运营经理、商务经理确认，`draft → pending_customer`（直接待客户确认）。
- **「是」**：走完整流程 `draft → pending_ops → pending_sales → pending_customer`，且**强制**运营经理（`manager_id`）与商务经理（`sales_manager_id`）非空，保存客户时即拦截。

排查结论（已核实）：现有 `auto_initiate_settlement`（自动发起结算）字段是**死字段**——`billing.py` 的 `submit_invoice`/`generate_invoice`/`generate_invoices_batch`/`confirm_ops`/`confirm_sales` 等**所有结算业务逻辑均未读取它**；它仅在模型、CRUD、列表筛选、表单展示、导入导出、测试中流转，从不影响结算行为。用户已决策：**移除该死字段，新增独立的 `require_reconciliation`（是否对账）字段**；流程条不改结构（跳过的确认步由 Arco Steps 自动标为已完成）。

## 现有确认流程现状（baseline）

- 状态机（`backend/app/models/billing.py`）：`draft → pending_ops → pending_sales → pending_customer → customer_confirmed → completed`，任意非 completed 可 `cancelled`。
- `submit_invoice`（`billing.py:1637-1669`）当前已按经理配置被动跳过：有 `manager_id`→`pending_ops`；无 manager 有 `sales_manager_id`→`pending_sales`；两者皆无→`pending_customer`。新逻辑在此基础上**前置一个显式开关**：`require_reconciliation` 非 True → 无条件 `pending_customer`。
- `confirm_ops`（1671-1703）/`confirm_sales`（1705-1732）不变。

## Approach

按依赖树有序执行；每步后跑对应测试确保不退化。

### 步骤 1 — 数据层迁移

新建迁移文件 `backend/alembic/versions/<hash>_add_require_reconciliation_drop_auto_initiate.py`（用 `alembic revision -m "add require_reconciliation drop auto_initiate_settlement"` 生成骨架，自动填 `revision`/`down_revision`，再手写 `upgrade`/`downgrade`）：
- `upgrade()`：
  - `op.add_column("customers", sa.Column("require_reconciliation", sa.Boolean(), nullable=True, server_default=sa.text("false"), comment="是否对账（NULL/False=否，跳过经理确认；True=是，走完整确认流程并强制经理非空）"))`
  - `op.drop_column("customers", "auto_initiate_settlement")`
- `downgrade()`：反向（add 回 auto_initiate_settlement nullable default true；drop require_reconciliation）。
- 保留原始迁移 `a2b3c4d5e6f7_add_auto_initiate_settlement_field.py` 不动（alembic 历史不篡改；fresh install 会先建后删，无害）。

### 步骤 2 — 后端模型

`backend/app/models/customers.py:57-58`：
- 删除 `auto_initiate_settlement` 字段（57-58 含注释）。
- 同位置新增：
  ```python
  require_reconciliation: Mapped[bool | None] = mapped_column(
      Boolean, nullable=True, default=False
  )  # 是否对账（NULL 视为否）；是→走完整结算确认流程并强制经理非空，否→跳过经理确认
  ```

### 步骤 3 — 后端服务层：校验 + 业务跳过逻辑

**`backend/app/services/customers.py`**

- `create_customer`（638-673）：构造 `Customer(...)` 时把 `auto_initiate_settlement=data.get("auto_initiate_settlement", True)`（669）替换为 `require_reconciliation=data.get("require_reconciliation", False)`。在 `Customer(...)` 构造**之前**加校验：
  ```python
  if data.get("require_reconciliation") is True:
      if not data.get("manager_id"):
          raise ValueError("开启对账后必须指定运营经理")
      if not data.get("sales_manager_id"):
          raise ValueError("开启对账后必须指定商务经理")
  ```
  （路由层 `create_customer` 已 `except ValueError → 40003`，无需改路由异常处理。）

- `update_customer`（705-805）：`updatable_fields` 把 `"auto_initiate_settlement"`（742）替换为 `"require_reconciliation"`。在可更新字段赋值之后、`commit` 之前加校验（综合本次传入值与客户现有值判断）：
  ```python
  final_recon = data.get("require_reconciliation") if "require_reconciliation" in data else customer.require_reconciliation
  if final_recon is True:
      final_manager = data.get("manager_id") if "manager_id" in data else customer.manager_id
      final_sales = data.get("sales_manager_id") if "sales_manager_id" in data else customer.sales_manager_id
      if not final_manager:
          raise ValueError("开启对账后必须指定运营经理")
      if not final_sales:
          raise ValueError("开启对账后必须指定商务经理")
  ```
  注意 `manager_id` 显式传 `None`（清空）也算未指定 → 报错，符合「开对账不可清空经理」。

- 筛选条件（341-351）：删除整段 `auto_initiate_settlement` 筛选分支。**不新增** `require_reconciliation` 筛选项（需求未提，YAGNI）。

- 导入字段处理（1336-1339）：把 `data["auto_initiate_settlement"] = convert_bool_field(...)` 替换为 `data["require_reconciliation"] = convert_bool_field(data.get("require_reconciliation"))`。

- 导入构造（1405-1406）：`auto_initiate_settlement=data.get(...)` 替换为 `require_reconciliation=data.get("require_reconciliation", False)`。

**`backend/app/services/billing.py` `submit_invoice`（1637-1669）**

替换「按经理配置跳过」分支为「是否对账」开关优先：
```python
customer = await self._get_customer(invoice.customer_id)
require_recon = customer is not None and customer.require_reconciliation is True
if require_recon:
    # 走完整确认流程（开对账时经理非空已由客户保存校验保证）
    if customer and customer.manager_id:
        invoice.status = "pending_ops"
    elif customer and customer.sales_manager_id:
        invoice.status = "pending_sales"
    else:
        # 防御：开对账但经理被清空（不应发生，保存时已拦截）→ 降级直接待客户确认
        invoice.status = "pending_customer"
else:
    # 不对账：跳过运营/商务经理确认，直接待客户确认
    invoice.status = "pending_customer"
```
`confirm_ops`/`confirm_sales`/`generate_invoice`/`generate_invoices_batch` 不变。

### 步骤 4 — 后端路由：响应/筛选/导出

**`backend/app/routes/customers.py`**
- 列表响应字段（262）：`"auto_initiate_settlement": c.auto_initiate_settlement` → `"require_reconciliation": c.require_reconciliation`。
- 详情响应字段（481）：同上替换。
- 列表筛选项（128-131）：删除整段 `auto_initiate_settlement` 筛选。
- 第二列表筛选项（1415-1418）：删除整段。
- 导出列定义（1259-1260）：`"auto_initiate_settlement"` → `"require_reconciliation"`。
- 导出响应字段（1508-1510）：`auto_initiate_settlement` 的「是/否」逻辑改为 `require_reconciliation`（`("是" if c.require_reconciliation else "否") if c.require_reconciliation is not None else None`）。

**`backend/app/routes/billing/balances.py`**
- 删除三处 `auto_initiate_settlement` 筛选（277-280、471-475、1129-1133 整段）。

### 步骤 5 — 前端类型

`frontend/src/types/index.ts:115`：
- 删 `auto_initiate_settlement: boolean | null`。
- 加 `require_reconciliation: boolean | null`。
（`api/customers.ts` 无 auto 引用，无需改。）

### 步骤 6 — 前端客户表单（4 个组件）

统一语义：label `是否对账`，选项 `是(true)/否(false)`，默认 `否(false)`；`require_reconciliation === true` 时 `manager_id`/`sales_manager_id` 必填（动态 `:rules`）。

- **`CustomerFormModal.vue`**（119-126 表单项、167-182 类型、215-219 初始值、244-248 reset、260-264 edit 回填、302-306 payload）：
  - 表单项：`auto_initiate_settlement` → `require_reconciliation`，label 改 `是否对账`，`a-select` 是/否，默认 `false`。
  - `CustomerForm` 接口：删 `auto_initiate_settlement`，加 `require_reconciliation: boolean`。
  - 初始值/reset：`false`；edit 回填：`record.require_reconciliation ?? false`；payload：`require_reconciliation: customerForm.require_reconciliation`。
  - 运营经理（129-140）、商务经理（142-153）`a-form-item` 加 `:rules`：`require_reconciliation` 为 true 时 `[{ required: true, message: '开启对账后必填' }]`，否则空。用 computed 生成 rules 数组绑定。

- **`AddCustomerModal.vue`**（109-125、230-232、251-252、307-308）：同 CustomerFormModal 改法（类型/初始值/payload 对应替换）；经理字段同样加动态 required 规则。

- **`EditCustomerDialog.vue`**（142-145、293-294、322-323、428-429、482-483）：`a-switch` 绑 `require_reconciliation`，label `是否对账`；类型/初始值/回填/payload 对应替换；经理字段动态 required。

- **`CustomerBatchEditModal.vue`**（132-143、364-365、383-384、402-403、523-524）：
  - 批量字段项：`auto_initiate_settlement` → `require_reconciliation`，label `是否对账`，`a-switch`。
  - `batchForm`/`batchFieldsSelected`/reset 初始值改 `require_reconciliation`。
  - `labelMap`（402-403）：`require_reconciliation: '是否对账'`。
  - 批量开对账=是 时**不在前端逐条校验经理**（批量场景各客户经理不同）；依赖后端 `batch-update` 路由逐条调 `update_customer` 时 `ValueError` 逐条报错（见步骤 3 校验）。失败行错误信息回显。

### 步骤 7 — 前端筛选器与详情

- **`CustomerFilters.vue`**（65-69 表单项、140-141 类型、280-287 computed）：删除 `auto_initiate_settlement` 筛选项、类型字段、computed。不新增 `require_reconciliation` 筛选。
- **`BalanceFilters.vue`**（66-70、129-130、237-246）：同上删除。
- **`CustomerBasicTab.vue`**（101-108）：label `自动发起结算` → `是否对账`；绑定 `customer.require_reconciliation`；`tag`：是→green、否→gray（`customer.require_reconciliation ? '是' : '否'`，NULL 视为否）。

### 步骤 8 — 测试

删除/改写 `auto_initiate_settlement` 相关测试，新增 `require_reconciliation` 行为测试：

- `backend/tests/integration/test_customers_api.py`（335-365 默认是、372-411 显式否/更新）：
  - 改为：创建客户 `require_reconciliation` 默认 `False`（否）；显式指定 `True`；更新字段。
  - 新增：`require_reconciliation=True` 但不传 `manager_id`/`sales_manager_id` → 400 + 错误信息；补齐经理后创建成功。
- `backend/tests/unit/test_customer_service.py`（161-163、330-）：`auto_initiate_settlement` 默认 True → `require_reconciliation` 默认 False；更新字段测试改写。
- `backend/tests/unit/test_balance_filters.py`（132-138、235-236）：删除 `auto_initiate_settlement` 筛选语义测试。
- `backend/tests/unit/test_customer_service_batch.py`：相关 auto 断言改/删。
- `backend/tests/unit/test_billing_service.py`（submit 测试 2220-2304）：新增：
  - `require_reconciliation=False` → `submit` 后 `draft → pending_customer`（即使客户有经理）。
  - `require_reconciliation=True` + 有 manager → `draft → pending_ops`。
- `frontend/src/composables/__tests__/useBalance.test.ts`（553-565）：删除 `auto_initiate_settlement` 筛选项默认值断言；filters 不再含该键。

## Critical files & anchors

1. `backend/app/services/billing.py` — `submit_invoice`（1637-1669）：跳过逻辑核心改动点。
2. `backend/app/services/customers.py` — `create_customer`(638-673)/`update_customer`(705-805)：经理非空校验入口；导入字段(1336-1339,1405-1406)。
3. `backend/app/models/customers.py` — 字段定义(57-58)。
4. `frontend/src/views/customers/components/CustomerFormModal.vue` — 表单+动态 required 规则(119-153,302-306)。
5. `backend/app/routes/customers.py` — 响应字段(262,481)/筛选(128-131,1415-1418)/导出(1259-1260,1508-1510)。

（implementer 编辑前重读这些区域确认行号未漂移。）

## Verification

**前置**：`cd backend && source .venv/bin/activate`；`cd frontend`。

1. **迁移**：`cd backend && alembic upgrade head`（确认 require_reconciliation 列建、auto_initiate_settlement 列删；`alembic heads` 显示新 head）。
2. **后端测试**：
   - `pytest backend/tests/unit/test_billing_service.py -k "submit" -v` → 新增跳过逻辑测试通过。
   - `pytest backend/tests/integration/test_customers_api.py -k "reconcil or 对账" -v` → 校验测试通过。
   - 全量回归：`pytest backend/tests/ -q`（覆盖率 ≥50% 不可退化）。
3. **前端**：`cd frontend && npm run type-check`（无 TS 报错）；`npm run test`（useBalance 等）。
4. **端到端 UI 核验**（复用记忆中的本地核验流程：后端 uvicorn :8000 + 前端 npm run dev :5173，登录 admin/admin123 注入 localStorage 四键）：
   - 客户管理页「新增客户」：开「是否对账」=是，**不填**运营/商务经理 → 提交应被前端 required 拦截；填齐经理 → 保存成功。
   - 开「是否对账」=否，不填经理 → 保存成功（默认场景）。
   - 为「否」客户生成结算单并 submit → 详情状态直接 `pending_customer`（流程条运营/销售确认步显示绿色已完成）。
   - 为「是」客户生成结算单并 submit → 状态 `pending_ops`，需运营/商务依次确认。
5. **存量兼容**：现有 `pending_ops`/`pending_sales` 状态结算单不受影响（新逻辑只作用于 submit 分流）。

## Assumptions & contingencies

- **默认值与历史数据**：`require_reconciliation` 新列 `server_default=false`，历史行迁移后均为 `False`（否）→ 历史客户 submit 走跳过路径，符合「所有客户默认否」。无需额外数据回填。
- **不新增筛选项**：需求未要求按是否对账筛选，故客户/余额筛选器删 auto 项后不补 require_reconciliation 项。若后续需要，再单独加。
- **批量编辑开对账**：不在前端逐条校验经理，依赖后端 `batch-update` 路由逐条 `update_customer` 校验。若用户批量开对账但部分客户无经理，失败行返回错误信息，成功行正常更新（沿用 batch 路由现有部分成功/失败聚合行为）。
- **`is_settlement_enabled` 不动**：现有「是否启用结算」独立语义（控制客户是否参与结算），与「是否对账」正交，不在本次范围。
