# 功能设计缺陷修复计划

**创建日期**: 2026-09-11
**排查方法**: CodeGraph 符号级分析 + 前后端源码逐行比对
**分支**: fix-bug

---

## 一、缺陷总览

| 编号 | 严重程度 | 模块 | 缺陷描述 |
|------|---------|------|---------|
| DF-01 | 🔴 高 | 客户管理 | 「结算周期」字段取值在三个表单中不一致 |
| DF-02 | 🔴 高 | 客户管理 | 「账号类型」字段选项在两个表单中不一致 |
| DF-03 | 🟡 中 | 客户管理 | AddCustomerModal 未传 `industry_type_id` 给后端 create API |
| DF-04 | 🟡 中 | 客户管理 | CustomerFormModal company_id 使用 `a-input` 而非 `a-input-number` |
| DF-05 | 🔴 高 | 结算单 | InvoiceFilters 状态选项缺失 `pending_ops` 和 `pending_sales` |
| DF-06 | 🔴 高 | 结算单 | CustomerInvoicesTab 状态映射缺失多角色协作状态 |
| DF-07 | 🟡 中 | 结算单 | InvoiceFilters 缺少重置事件实现 |
| DF-08 | 🟡 中 | 客户管理 | EditCustomerDialog 规模等级选项与 CustomerBatchEditModal 不一致 |
| DF-09 | 🟡 中 | 客户管理 | EditCustomerDialog `is_real_estate` 使用 `a-switch`（二态）vs AddCustomerModal 使用 `a-switch`（二态）vs CustomerFormModal 使用 `a-select`（三态）不一致 |
| DF-10 | 🟡 中 | 客户管理 | 后端 `create_customer` 未接收 `industry_type_id` 字段传入 Customer 模型（只用于创建 Profile） |
| DF-11 | 🟢 低 | 客户管理 | 三个表单「销售经理」字段标签不一致（"销售经理" vs "商务经理"） |
| DF-12 | 🟡 中 | 结算单 | `price_policy` 前端使用 `pricing/tiered/yearly`，后端 `PricingRule.pricing_type` 使用 `fixed/tiered/package`，命名空间冲突 |
| DF-13 | 🟡 中 | 客户管理 | 后端 `get_customer_summary` 路由直接访问 `customer.industry_type`/`customer.scale_level`/`customer.balance` 等不存在的属性 |
| DF-14 | 🟢 低 | 前端通用 | 多个组件重复定义相同的选项常量（如 settlementCycle 映射），未提取为共享常量 |

---

## 二、详细分析与修复方案

### DF-01: 「结算周期」字段取值不一致 🔴

**影响范围**: 客户新增、编辑、批量编辑

**问题分析**:

| 组件 | 提供的选项 | 缺失项 |
|------|-----------|--------|
| `AddCustomerModal.vue` (L77-79) | monthly, quarterly, yearly | ❌ 缺 daily, weekly |
| `CustomerFormModal.vue` (L90-93) | daily, weekly, monthly, quarterly | ❌ 缺 yearly |
| `CustomerBatchEditModal.vue` (L113-115) | monthly, quarterly, yearly | ❌ 缺 daily, weekly |
| `EditCustomerDialog.vue` (L81-85) | daily, weekly, monthly, quarterly, yearly | ✅ 完整 |
| 后端 `SETTLEMENT_CYCLE_MAP` (L124-130) | daily, weekly, monthly, quarterly, yearly | ✅ 完整 |
| `CustomerBasicTab.vue` (L214-220) 显示映射 | daily, weekly, monthly, quarterly, yearly | ✅ 完整 |

**修复方案**: 将所有表单的结算周期选项统一为 5 项：`daily/weekly/monthly/quarterly/yearly`

**涉及文件**:
- `frontend/src/views/customers/components/AddCustomerModal.vue` — 添加 daily, weekly 选项
- `frontend/src/views/customers/components/CustomerFormModal.vue` — 添加 yearly 选项
- `frontend/src/views/customers/components/CustomerBatchEditModal.vue` — 添加 daily, weekly 选项

---

### DF-02: 「账号类型」字段选项不一致 🔴

**影响范围**: 客户新增、编辑

**问题分析**:

| 组件 | 选项 |
|------|------|
| `AddCustomerModal.vue` (L42-44) | 正式账号, 客户测试账号, 内部账号 |
| `CustomerBatchEditModal.vue` (L154-156) | 正式账号, 客户测试账号, 内部账号 |
| `EditCustomerDialog.vue` (L41-43) | 正式账号, 客户测试账号, 内部账号 |
| `CustomerFormModal.vue` (L39-40) | 正式账号, 测试账号 ❌ |

**修复方案**: 将 `CustomerFormModal.vue` 的账号类型选项统一为：`正式账号, 客户测试账号, 内部账号`

**涉及文件**:
- `frontend/src/views/customers/components/CustomerFormModal.vue`

---

### DF-03: AddCustomerModal 未传 `industry_type_id` 给后端 create API 🟡

**影响范围**: 新增客户时行业类型丢失

**问题分析**:
- `AddCustomerModal.vue` (L222) 的 payload 构建中使用了 `form.industry_type_id`，但 `createCustomer` (customers.ts L47-60) 的函数签名中接受的是 `industry?: string` 而非 `industry_type_id?: number`
- 后端 `CustomerService.create_customer` (L443) 检查 `data.get("industry_type_id")` 来创建 Profile

**修复方案**: 在 `frontend/src/api/customers.ts` 的 `createCustomer` 函数签名中添加 `industry_type_id?: number` 参数

**涉及文件**:
- `frontend/src/api/customers.ts`

---

### DF-04: CustomerFormModal company_id 使用文本输入而非数字输入 🟡

**影响范围**: 新建/编辑客户时的数据校验

**问题分析**:
- `CustomerFormModal.vue` (L21) 使用 `<a-input v-model="customerForm.company_id">` — company_id 是 `number | undefined` 类型，但用了文本输入框
- `AddCustomerModal.vue` (L17-23) 正确使用了 `<a-input-number>`
- `EditCustomerDialog.vue` (L28-34) 正确使用了 `<a-input-number>`

**修复方案**: 将 `CustomerFormModal.vue` 的 company_id 字段从 `a-input` 改为 `a-input-number`

**涉及文件**:
- `frontend/src/views/customers/components/CustomerFormModal.vue`

---

### DF-05: InvoiceFilters 状态选项缺失多角色协作状态 🔴

**影响范围**: 结算单列表页无法按 `pending_ops` 和 `pending_sales` 状态筛选

**问题分析**:

| 组件 | 包含的状态 |
|------|-----------|
| `InvoiceFilters.vue` (L32-38) | draft, pending_customer, customer_confirmed, paid, completed, cancelled |
| `InvoiceStatusBadge.vue` (L15-24) | draft, pending_ops, pending_sales, pending_customer, customer_confirmed, paid, completed, cancelled |
| 后端 `InvoiceStatus` 枚举 (L35-42) | draft, pending_ops, pending_sales, pending_customer, customer_confirmed, paid, completed, cancelled |
| `CustomerInvoicesTab.vue` (L39-58) | draft, pending_customer, customer_confirmed, paid, completed, cancelled |

**修复方案**: 在 `InvoiceFilters.vue` 的 `statusOptions` 中添加 `pending_ops` 和 `pending_sales` 选项

**涉及文件**:
- `frontend/src/views/billing/components/InvoiceFilters.vue`

---

### DF-06: CustomerInvoicesTab 状态映射缺失多角色协作状态 🔴

**影响范围**: 客户详情页结算单列表中，`pending_ops` 和 `pending_sales` 状态的结算单显示为原始英文值

**问题分析**:
- `CustomerInvoicesTab.vue` (L39-58) 的 `getStatusTagClass` 和 `getStatusText` 方法中缺少 `pending_ops` 和 `pending_sales`
- 后端 `InvoiceStatus` 枚举明确包含这两个状态

**修复方案**: 在 `CustomerInvoicesTab.vue` 的两个状态映射中添加 `pending_ops` 和 `pending_sales`

**涉及文件**:
- `frontend/src/views/customers/detail/CustomerInvoicesTab.vue`

---

### DF-07: InvoiceFilters 缺少重置事件实现 🟡

**影响范围**: 结算单列表页筛选器无法重置

**问题分析**:
- `InvoiceFilters.vue` (L27-30) 声明了 `reset` emit 事件，但模板中没有任何按钮或逻辑触发该事件
- 对比 `BalanceFilters.vue` (L167) 有 `handleReset` 函数触发 `reset` 事件

**修复方案**: 在 `InvoiceFilters.vue` 模板中添加重置按钮，触发 `reset` 事件

**涉及文件**:
- `frontend/src/views/billing/components/InvoiceFilters.vue`

---

### DF-08: EditCustomerDialog 规模等级选项与 CustomerBatchEditModal 不一致 🟡

**影响范围**: 客户编辑时的规模等级选项不完整

**问题分析**:

| 组件 | 规模等级选项 |
|------|------------|
| `EditCustomerDialog.vue` (L141-146) | S, A, B, C, D (5项，缺 E) |
| `CustomerBatchEditModal.vue` (L184-189) | S, A, B, C, D, E (6项) |
| 后端 `CustomerProfile` 模型注释 (L72) | S/A/B/C/D/E (6项) |

**修复方案**: 在 `EditCustomerDialog.vue` 的规模等级选项中添加 `E - 微型 (<100人)`

**涉及文件**:
- `frontend/src/views/customers/detail/EditCustomerDialog.vue`

---

### DF-09: `is_real_estate` 字段表单控件类型不一致 🟡

**影响范围**: 客户新增/编辑时房产客户字段的交互体验不一致

**问题分析**:

| 组件 | 控件类型 | 可选值 |
|------|---------|--------|
| `AddCustomerModal.vue` (L70) | `a-switch` | true/false（二态） |
| `CustomerFormModal.vue` (L77-80) | `a-select` | true/false/null（三态） |
| `EditCustomerDialog.vue` (L54) | `a-switch` | true/false（二态） |
| `CustomerBatchEditModal.vue` (L79-87) | `a-select` | true/false/null（三态） |

**修复方案**: 统一为三态 `a-select`（是/否/未设置），因为后端模型 `is_real_estate` 字段为 `nullable=True, default=None`，支持三态语义

**涉及文件**:
- `frontend/src/views/customers/components/AddCustomerModal.vue`
- `frontend/src/views/customers/detail/EditCustomerDialog.vue`

---

### DF-10: 后端 create_customer 未接收部分新增字段 🟡

**影响范围**: 通过 AddCustomerModal/CustomerFormModal 创建客户时，部分字段不会保存

**问题分析**:
- 后端 `CustomerService.create_customer` (L414-426) 只接收: `company_id, name, account_type, price_policy, manager_id, sales_manager_id, settlement_cycle, settlement_type, is_key_customer, is_real_estate, email`
- 缺少: `erp_system, first_payment_date, onboarding_date, cooperation_status, is_settlement_enabled, is_disabled, notes`
- 而 `update_customer` (L477-490) 的 `updatable_fields` 列表包含这些字段

**修复方案**: 在 `create_customer` 方法的 Customer 构造中添加缺失字段

**涉及文件**:
- `backend/app/services/customers.py`

---

### DF-11: 「销售经理」字段标签不一致 🟢

**影响范围**: 用户界面术语不一致

**问题分析**:

| 组件 | 标签文本 |
|------|---------|
| `AddCustomerModal.vue` (L106) | "销售经理" |
| `CustomerFormModal.vue` (L117) | "商务经理" |
| `EditCustomerDialog.vue` (L56) | "销售经理" |
| `CustomerBatchEditModal.vue` (L32) | "商务经理" |
| 后端模型字段名 (L39) | `sales_manager_id` — 注释为"销售负责人" |
| `customers.py` 路由文档 (L45) | "商务经理 ID" |

**修复方案**: 统一标签为「商务经理」（与后端路由文档一致）

**涉及文件**:
- `frontend/src/views/customers/components/AddCustomerModal.vue`
- `frontend/src/views/customers/detail/EditCustomerDialog.vue`

---

### DF-12: `price_policy` 与 `pricing_type` 命名空间冲突 🟡

**影响范围**: 计费策略字段值在客户和计费规则两个维度使用了不同的值域

**问题分析**:

| 维度 | 字段名 | 值域 |
|------|--------|------|
| Customer 模型 | `price_policy` | `pricing/tiered/yearly` |
| PricingRule 模型 | `pricing_type` | `fixed/tiered/package` |
| GenerateInvoiceModal | `batchForm.pricing_type` | `fixed/tiered/package` |
| CustomerBatchEditModal (L169-172) | `price_policy` | `pricing/tiered/yearly` |
| EditCustomerDialog (L90-92) | `price_policy` | `pricing/tiered/yearly` |

**风险**: `yearly` 在 `price_policy` 中表示"包年计费策略"，而在 `PricingRule.pricing_type` 中 `package` 表示"包年结算"，两者语义重叠但命名不同，易造成混淆

**修复方案**: 文档标注两者的区别；长期考虑统一命名

**涉及文件**:
- `backend/app/models/customers.py` — 添加注释说明
- `backend/app/models/billing.py` — 添加注释说明

---

### DF-13: `get_customer_summary` 路由访问不存在的属性 🟡

**影响范围**: 客户 360 预览摘要接口可能返回错误

**问题分析**:
- `backend/app/routes/customers.py` (L1070-1076) 中直接访问 `customer.industry_type`、`customer.scale_level`、`customer.balance`
- 但 `Customer` 模型没有 `industry_type`、`scale_level`、`balance` 属性
- 正确访问方式：`customer.profile.industry_type.name`、`customer.profile.scale_level`、`customer.balance.total_amount`

**修复方案**: 修正属性访问路径

**涉及文件**:
- `backend/app/routes/customers.py`

---

### DF-14: 选项常量重复定义 🟢

**影响范围**: 可维护性

**问题分析**: 以下映射在多个文件中重复定义：
- `settlement_cycle` 映射：后端 `SETTLEMENT_CYCLE_MAP`、`CustomerBasicTab.vue`、各表单组件
- `settlement_type` 映射：后端 `SETTLEMENT_TYPE_MAP`、`BalanceFilters.vue`、各表单组件
- `account_type` 选项：在 4 个表单组件中各自硬编码

**修复方案**: 提取为前端共享常量文件 `frontend/src/constants/customerOptions.ts`

**涉及文件**:
- 新建 `frontend/src/constants/customerOptions.ts`
- 更新所有引用的前端组件

---

## 三、执行计划

### 阶段一：紧急修复（P0 — 当日完成）

| 任务编号 | 缺陷编号 | 任务描述 | 预计工时 |
|---------|---------|---------|---------|
| T1 | DF-01 | 统一三个表单的结算周期选项为 5 项 | 15min |
| T2 | DF-02 | 修正 CustomerFormModal 的账号类型选项 | 5min |
| T3 | DF-05 | InvoiceFilters 添加 pending_ops/pending_sales 状态选项 | 10min |
| T4 | DF-06 | CustomerInvoicesTab 状态映射添加多角色协作状态 | 10min |
| T5 | DF-13 | 修正 get_customer_summary 属性访问路径 | 15min |

### 阶段二：功能完善（P1 — 本周完成）

| 任务编号 | 缺陷编号 | 任务描述 | 预计工时 |
|---------|---------|---------|---------|
| T6 | DF-03 | 修复 createCustomer API 签名添加 industry_type_id | 10min |
| T7 | DF-04 | CustomerFormModal company_id 改为 a-input-number | 10min |
| T8 | DF-07 | InvoiceFilters 添加重置按钮 | 15min |
| T9 | DF-08 | EditCustomerDialog 规模等级添加 E 选项 | 5min |
| T10 | DF-09 | 统一 is_real_estate 为三态 a-select | 20min |
| T11 | DF-10 | 后端 create_customer 添加缺失字段 | 15min |
| T12 | DF-12 | 添加 price_policy vs pricing_type 区别注释 | 10min |

### 阶段三：优化重构（P2 — 下个迭代）

| 任务编号 | 缺陷编号 | 任务描述 | 预计工时 |
|---------|---------|---------|---------|
| T13 | DF-11 | 统一「商务经理」标签 | 10min |
| T14 | DF-14 | 提取共享选项常量文件 | 30min |

---

## 四、验证方案

### 单元测试
- 每个修复完成后运行对应模块的测试
- 后端：`pytest backend/tests/ -k customer`
- 前端：`npm run test -- --filter customer`

### E2E 测试
- 客户管理流程：新增客户 → 选择 daily 结算周期 → 保存 → 验证
- 客户管理流程：编辑客户 → 选择 yearly 结算周期 → 保存 → 验证
- 结算单流程：创建结算单 → 筛选 pending_ops 状态 → 验证列表
- 批量编辑：选择多个客户 → 修改结算周期为 weekly → 验证

### 回归测试
- 运行全量 E2E 测试 `npx playwright test`
- 运行全量后端测试 `pytest backend/tests/`

---

## 五、风险评估

| 风险项 | 概率 | 影响 | 缓解措施 |
|--------|------|------|---------|
| 统一选项后已有数据不匹配 | 低 | 低 | 后端 SETTLEMENT_CYCLE_MAP 已支持全部 5 种值 |
| create_customer 添加字段后影响现有调用 | 低 | 中 | 新字段全部有默认值或 nullable |
| 前端常量提取导致循环依赖 | 低 | 低 | 常量文件不依赖任何业务模块 |

---

## 六、变更记录

| 日期 | 变更内容 | 操作人 |
|------|---------|--------|
| 2026-09-11 | 初始创建，排查出 14 项功能设计缺陷 | CatPaw Agent |
| 2026-09-11 | **全部 14 项缺陷已修复完成**。DF-01~14 全部修复，前端 lint 通过，后端 73 项单元测试通过（customer/billing/industry 模块）。预置排序测试失败（`test_allowed_sort_fields`）非本次引入。Break-Loop 分析完成，spec 已更新：`component-guidelines.md` 新增「选项一致性」章节，`cross-layer-thinking-guide.md` 新增「前后端选项一致性」检查清单。 | CatPaw Agent |
