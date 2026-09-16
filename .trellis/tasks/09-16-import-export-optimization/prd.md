# 导入导出功能优化

## Goal

1. 检查客户管理页面中的导出、导入功能是否正常可用
2. 为结算管理下 4 个子页面补齐导入、导出功能
3. 使用 codegraph 排查影响范围，避免遗漏

## Background

客户管理已有完整的前后端导入导出实现，可作为参照模式；结算管理（billing）为父级菜单，下含 4 个子页面，导入导出能力不完整。本次按客户管理成熟模式补齐短板，统一交互与错误反馈；**权限按功能细粒度拆分**，支持按页面独立授权。

## Confirmed Facts（代码调研）

### 客户管理（参照模式，已有完整实现）
- 前端：`frontend/src/api/customers.ts` — `importCustomers`(POST /customers/import)、`downloadImportTemplate`(GET /customers/import-template)、`exportCustomers`(GET /customers/export, blob)
- 前端组件：`CustomerImportModal.vue`（模板下载、文件拖拽/校验、结果展示 success/error_count + errors）
- 前端页面：`customers/Index.vue` 按钮「导入客户」`can('customers:import')`、「导出」`can('customers:export')`
- 后端：`backend/app/routes/customers.py` — `POST /customers/import`(权限 customers:import, 行级错误)、`GET /customers/import-template`、`GET /customers/export`(权限 customers:export, 上限 50000 条, 按当前筛选条件透传)
- 服务层：`CustomerService.batch_create_customers` — 返回 `{success_count, error_count, errors[:10]}`
- 审计：导入操作记录 audit entry（batch_create / customers）

### 结算页面现状（billing 菜单）
侧边栏「结算管理」是父级菜单（无独立页面），子页面共 4 个：
- `/billing/balance` 余额管理 — **已有导入**（ImportBalanceModal + POST /billing/import + GET /billing/import-template，权限 billing:import）；**导出缺失**（Balance.vue `handleBatchAction('export')` 仅占位提示）
- `/billing/pricing-rules` 计费规则 — **无导入导出**
- `/billing/package-plans` 包年套餐（菜单名「套餐方案」）— **无导入导出**
- `/billing/invoices` 结算单管理 — **已有导出**（exportInvoices + GET /billing/invoices/export，权限 billing:export，按筛选条件导出）；**导入缺失**

### 模型字段
- `PricingRule`（models/billing.py:79）：customer_id, device_type(X/N/L), layer_type(single/multi), pricing_type(fixed/tiered/package), unit_price, multi_floor_pricing_type, additional_floor_price, tiers(JSON), package_type, package_limits(JSON), effective_date, expiry_date, created_by
- `PackagePlan`（models/billing.py:251）：name, package_type, device_type, layer_type, is_unlimited, limit_count, base_fee, over_limit_unit_price, description, status(active/inactive)
- `Invoice`（models/billing.py:107）：invoice_no(unique), customer_id, period_start, period_end, total_amount, discount_amount, status(枚举: draft/pending_ops/pending_sales/pending_customer/customer_confirmed/paid/completed/cancelled), is_auto_generated, created_by
  - 发票号规则（services/billing.py:1344）：`INV-YYYYMMDD-{customer_id}-{4位随机码}`
- `CustomerBalance`（models/billing.py:45）：customer_id, total_amount, real_amount, bonus_amount, used_total, used_real, used_bonus
- 余额列表查询（routes/billing/balances.py:148 `get_balances`）：筛选参数 keyword/industry/account_type/manager_id/sales_manager_id/is_key_customer/is_real_estate/settlement_type/balance_range/recharge_date/tag_ids；燃尽计算 `_compute_burn_down`（balances.py:109）

### 权限体系（本次变更核心）
- **现状**：billing 模块已有 `billing:import`（导入余额）、`billing:export`（导出账单）两个粗粒度权限码，前后端均已注册使用（seed.py:60-61、conftest.py:221，前端 Balance.vue:15 / Invoices.vue:6）
- **决策**：拆分为 8 个细粒度权限码（见 Key Decisions #4/#5），覆盖 balance/pricing/package/invoice × import/export；原 2 个粗粒度码废弃并等价迁移
- 权限分组：billing 模块标题「结算管理」（permissionGroups.ts，按 module 分组，无需改）
- 导入限制先例：余额导入单次 ≤1000 行（imports.py:40004）；客户导出上限 50000 条

## Requirements

- REQ-1 检查客户管理导入导出：前端按钮权限、后端端点、模板下载、导入错误反馈、导出文件内容，确认可用性；发现问题则修复
- REQ-2 余额管理补「导出」：按当前筛选条件导出匹配的全部客户余额（含燃尽信息），权限 `billing:balance_export`，上限 50000 条
- REQ-3 计费规则补「导入 + 导出」：
  - 导出按当前筛选（keyword/device_type/pricing_type），权限 `billing:pricing_export`
  - 导入支持模板下载，权限 `billing:pricing_import`；走服务层 `create_pricing_rule`（含冲突检查与 single_and_multi 拆分、package 自动填充），行级错误反馈
- REQ-4 包年套餐补「导入 + 导出」：
  - 导出按当前筛选（keyword/status/is_unlimited），权限 `billing:package_export`
  - 导入支持模板下载，权限 `billing:package_import`；按 `package_type` 唯一性校验，行级错误反馈
- REQ-5 结算单管理补「导入」：外部/历史结算单批量录入（按 Invoice 模型字段对齐），导入后 `status=draft`，权限 `billing:invoice_import`；`invoice_no` 缺省时按系统规则自动生成；仅主表导入（明细 Deferred）
- REQ-6 存量权限迁移：废弃 `billing:import`/`billing:export`，现有使用点全部迁移到新码；已绑定旧码的角色等价获得对应方向全部新码
- REQ-7 导入交互统一：弹窗含「下载模板」、文件拖拽/点击选择、仅 .xlsx、≤10MB、结果展示 成功/失败/错误行明细
- REQ-8 导入操作记录审计日志（module=billing，参照 import_balance）

## Acceptance Criteria

- [ ] AC-1 客户管理：导入导出按钮显示/隐藏跟随 `customers:import`/`customers:export` 权限；导入模板可下载、文件可导入并正确反馈成功/失败；导出文件列与客户列表字段一致
- [ ] AC-2 余额管理：头部「导出」按钮仅 `billing:balance_export` 权限可见；返回 xlsx 内容 = 当前筛选条件下全部匹配客户余额（含燃尽天数），列与 BalanceTable 对齐
- [ ] AC-3 计费规则：头部「导入规则」「导出」按钮分别按 `billing:pricing_import`/`billing:pricing_export` 显示；导出列对齐列表；导入模板可下载；上传成功创建三种类型规则，错误行逐行报错不阻塞其他行
- [ ] AC-4 包年套餐：头部「导入套餐」「导出」按钮按 `billing:package_import`/`billing:package_export` 显示；导出列对齐列表；导入成功创建套餐，`package_type` 重复/必填缺失明确报错
- [ ] AC-5 结算单管理：头部「导入」按钮仅 `billing:invoice_import` 权限可见；导入后结算单为 draft 状态且出现在列表中；`company_id` 不存在/金额非法等错误行明确提示
- [ ] AC-6 权限迁移完成：代码中无 `billing:import`/`billing:export` 引用（前后端+grep 验证）；seed.py/conftest 注册 8 个新码；PRESET_ROLES 与测试夹具使用新码；运营经理/销售经理等既有角色保持等价权限（全导出码）
- [ ] AC-7 后端新增端点均带 `@auth_required` + `@require_permission`；导入返回 `{success_count, error_count, errors[:10]}`；审计日志落库
- [ ] AC-8 单测/集成测试覆盖新增端点关键路径（成功、必填缺失、行级错误、权限拦截）；整体覆盖率 ≥50% 维持

## Out of Scope

- 不改动客户管理现有导入导出实现（除非检查发现问题）
- 不新增数据库表与列；不改动结算单生成/确认流程本身
- balances 的批量选择导出（BalanceBatchToolbar 中 export 占位）不实现，导出统一在头部按钮按筛选条件进行
- 不改动 ImportBalanceModal 已有导入（仅其权限码随迁移改为 `billing:balance_import`）
- 不做导入进度条/异步任务化（≤1000 行同步处理，先例一致）

## Key Decisions（用户已确认）

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 页面范围 | 结算管理是父级菜单；实际操作其下 4 个子页面：余额管理补导出、结算单管理补导入、计费规则与包年套餐补齐导入+导出 |
| 2 | 结算单导入含义 | 支持导入外部/历史结算单，按 Invoice 模型字段对齐，导入后置为 draft(草稿/待确认) 状态 |
| 3 | 导出范围 | 按当前筛选条件导出全部匹配数据（与客户管理/结算单导出一致），上限 50000 条 |
| 4 | 权限粒度 | 细粒度拆分：废弃 `billing:import`/`billing:export`，新增 8 个码 `billing:{balance,pricing,package,invoice}_{import,export}` |
| 5 | 存量迁移 | 等价迁移：旧 `billing:export` 绑定者 → 全部 4 个导出码；旧 `billing:import` 绑定者 → 全部 4 个导入码；权限范围不缩水 |

## Risks / Deferred

- **权限迁移是破坏性变更**：需同步改 seed.py（ALL_PERMISSIONS + PRESET_ROLES）、conftest（权限注册 + FULL_PERMISSIONS）、前端 can()、后端 require_permission；存量库中旧权限码记录与新码的映射需在 seed 脚本或迁移说明中处理（等价授予，避免角色权限丢失）。生产环境的既有角色（如运营经理/销售经理）在新码体系下需重新获得等价权限，属部署注意事项
- 计费规则导入涉及 conflict 检查（_check_package_overlap/_check_single_overlap）与拆分逻辑（single_and_multi → 两条），逐行调用 `create_pricing_rule` 时需复用完整校验，避免绕过冲突检测；若模板含 `tiers` JSON 列，需在模板说明中给出样例格式
- 结算单导入字段较多（含状态流转字段），模板仅暴露受控字段集（company_id/period/金额/invoice_no），禁止导入端自由指定状态，规避绕过流程；`detail_file_*` 等内部字段不开放
- 余额导出复用 get_balances 的筛选与燃尽计算逻辑，注意抽成共享辅助函数以免两份逻辑漂移
- ImportBalanceModal 与 CustomerImportModal 模板近似但为独立组件；本次新建结算三页导入弹窗时复用其样式模式，暂不合并（避免扩大影响面）
