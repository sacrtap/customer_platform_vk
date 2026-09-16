# 导入导出功能优化 — 技术设计

## 架构与边界

按客户管理既有模式扩展 billing 模块，不新增表/列，不改动结算单生成流程。**权限体系细粒度拆分**：废弃 `billing:import`/`billing:export`，新增 8 个按功能区分的权限码，并做存量等价迁移。

```
前端页面 (PageHeader actions)
  │  import/export API (billing.ts)
  ▼
后端 billing_bp 路由（新增 9 个端点 + 权限迁移）
  ├─ GET  /billing/balances/export          [billing:balance_export]
  ├─ POST /billing/pricing-rules/import     [billing:pricing_import]
  ├─ GET  /billing/pricing-rules/import-template
  ├─ GET  /billing/pricing-rules/export     [billing:pricing_export]
  ├─ POST /billing/package-plans/import     [billing:package_import]
  ├─ GET  /billing/package-plans/import-template
  ├─ GET  /billing/package-plans/export     [billing:package_export]
  ├─ POST /billing/invoices/import          [billing:invoice_import]
  └─ GET  /billing/invoices/import-template
  │
  ├─ 服务层：PricingService.create_pricing_rule（复用冲突检查/拆分/package 填充）
  ├─ 服务层：BalanceService（仅查询，余额导出复用现有筛选+燃尽逻辑）
  └─ 审计：create_audit_entry(module=billing)
```

## 权限体系（本次变更核心）

### 新权限码（8 个，module=billing）

| 权限码 | 名称 | 描述 | 对应功能 |
|--------|------|------|----------|
| `billing:balance_import` | 导入余额 | 批量导入充值数据 | 余额导入（存量迁移） |
| `billing:balance_export` | 导出余额 | 导出客户余额数据 | 余额导出（新增） |
| `billing:pricing_import` | 导入计费规则 | 批量导入计费规则 | 计费规则导入（新增） |
| `billing:pricing_export` | 导出计费规则 | 导出计费规则数据 | 计费规则导出（新增） |
| `billing:package_import` | 导入包年套餐 | 批量导入包年套餐 | 包年套餐导入（新增） |
| `billing:package_export` | 导出包年套餐 | 导出包年套餐数据 | 包年套餐导出（新增） |
| `billing:invoice_import` | 导入结算单 | 批量导入外部结算单 | 结算单导入（新增） |
| `billing:invoice_export` | 导出结算单 | 导出结算单数据 | 结算单导出（存量迁移） |

### 使用点迁移清单（grep 已确认全量）

| 文件 | 旧码 | 新码 |
|------|------|------|
| backend/app/routes/billing/imports.py:20 | billing:import | billing:balance_import |
| backend/app/routes/billing/invoices.py:1147 | billing:export | billing:invoice_export |
| frontend/src/views/billing/Balance.vue:15 | billing:import | billing:balance_import |
| frontend/src/views/billing/Invoices.vue:6 | billing:export | billing:invoice_export |
| backend/scripts/seed.py:60-61 | billing:export/import | 8 个新码替换 2 旧码 |
| backend/scripts/seed.py:137,150（运营经理/销售经理 PRESET_ROLES） | billing:export | 全部 4 个导出码 |
| backend/tests/integration/conftest.py:221（权限注册） | billing:export | 8 个新码注册 |
| backend/tests/integration/conftest.py:442（FULL_PERMISSIONS） | billing:export | 8 个新码 |

### 存量等价迁移规则
- 已绑定 `billing:export` 的角色 → 追加 `billing:balance_export` + `billing:pricing_export` + `billing:package_export` + `billing:invoice_export`（权限范围不缩水）
- 已绑定 `billing:import` 的角色 → 追加对应 4 个导入码
- 迁移实现（seed.py 步骤 2.6 / 2.7）：先对存量 role_permissions 中旧码做等价授予（幂等），再**清理废弃的旧权限码记录**（解除角色绑定后删除 Permission 行），避免权限管理页残留僵尸权限；两步顺序保证不丢权限
- 权限管理页按 module 分组（permissionGroups.ts），billing 分组标题不变；前端不用改分组代码

## 数据流与契约

### 导入（统一契约，参照 imports.py）
1. 模板：openpyxl 生成，第 1 行英文列名 + 第 2 行中文说明（与客户/余额模板一致）
2. 解析：`pd.read_excel`；检测到第 2 行中文说明行则 `skiprows=[1]`
3. 校验顺序：文件存在 → .xlsx → 必填列 → 行数 ≤1000 → 逐行字段校验/映射（company_id → customer_id）→ 执行创建
4. 返回：`{code:0, message:"导入完成", data:{success_count, error_count, errors[:10]}}`；`errors` 为字符串数组（与客户/余额导入一致），格式 `第 N 行：原因`
5. 审计：`build_batch_audit_summary(operation=..., module=billing)` + `create_audit_entry`（action=batch_create，operation_type=batch，auto_commit=True）

### 导出（统一契约，参照 customers.py export）
1. 透传当前页面筛选参数；分页参数忽略（全量导出，上限 50000）
2. `pd.DataFrame` → `pd.ExcelWriter(engine="openpyxl")` → `raw(bytes, content_type=..., headers=Content-Disposition attachment)`
3. 无匹配数据时返回 `{code:40002, message:"没有找到符合条件的..."}`（结算单导出先例）

## 各端点设计

### 1. 余额导出 `GET /billing/balances/export`
- 复用 get_balances 的完整筛选链：keyword/industry(逗号分隔)/account_type/manager_id/sales_manager_id/is_key_customer/is_real_estate/settlement_type/balance_min/balance_max/recharge_date_from/to/tag_ids
- **共享辅助函数抽取**（避免两处逻辑漂移）：
  - `_parse_balance_filters(request) -> dict` — 参数解析+校验（含布尔/日期/范围转换）
  - `_query_balance_rows(db, filters, sort_by, sort_order, limit) -> list[dict]` — 执行查询 + `_batch_query_consumption_stats` 燃尽统计 + `_compute_burn_down` 组装行
  - `get_balances` 改为调用上述函数（行为不变，机械提取；导出调用同函数 limit=50000）
- 导出列（与 BalanceTable 对齐）：company_id, customer_name, industry_type, account_type, settlement_type, total_amount, real_amount, bonus_amount, used_total, last_recharge_at, days_remaining, daily_avg_cost, consumption_days

### 2. 计费规则导入 `POST /billing/pricing-rules/import` + 模板
- 模板列：company_id(必填), device_type(X/N/L), layer_type(single/multi/single_and_multi), pricing_type(fixed/tiered/package, 必填), unit_price, additional_floor_price, multi_floor_pricing_type(unified/incremental), tiers(JSON 字符串, 样例 `[{"min":1,"max":null,"price":5}]`), package_type(A/B/C/D), effective_date(必填, YYYY-MM-DD), expiry_date
- 执行：company_id → customer_id（预加载映射）；`local_date_to_utc_start/end` 转换日期（与 pricing.py:100 一致）；逐行调用 `PricingService.create_pricing_rule(data + created_by)`，捕获 `ValueError` → 行错误，成功行继续
- 依赖既有完整性：冲突检查（_check_package_overlap/_check_single_overlap）、single_and_multi 拆分、package 自动填充均由服务层保证
- 成功后 `cache_service.invalidate_billing_cache()`（与 create_pricing_rule 端点一致）

### 3. 计费规则导出 `GET /billing/pricing-rules/export`
- 筛选：keyword（客户名/设备/类型模糊）、device_type、pricing_type（与列表 fetchData 一致）
- 查询：`PricingService.get_pricing_rules(...)` limit 50000（复用现有服务分页接口）
- 导出列：id, customer_id, customer_name, device_type, layer_type, pricing_type, unit_price, multi_floor_pricing_type, additional_floor_price, tiers(JSON 文本), package_type, effective_date, expiry_date

### 4. 包年套餐导入 `POST /billing/package-plans/import` + 模板
- 模板列：name(必填), package_type(必填), device_type, layer_type, is_unlimited(是/否 或 true/false), limit_count, base_fee(必填), over_limit_unit_price, description, status(active/inactive, 默认 active)
- 校验（与 create_package_plan 端点一致）：名称/类型非空、base_fee≥0、限量时 limit_count>0、package_type 唯一（含软删除过滤，`select(PackagePlan).where(package_type==..., deleted_at.is_(None))`）
- 执行：逐行构造 PackagePlan 记录创建；重复 package_type → 行错误 `第 N 行：套餐类型 X 已存在`

### 5. 结算单导入 `POST /billing/invoices/import` + 模板
- 模板列（受控字段集）：company_id(必填), period_start(必填, YYYY-MM-DD), period_end(必填), total_amount(必填, ≥0), discount_amount(可选, 默认0), invoice_no(可选, 缺省自动生成)
- 约束：`status` 固定 `"draft"`，`is_auto_generated=False`（外部录入）；不开放状态流转字段与 detail_file_* 内部字段
- invoice_no：模板缺省时按 `INV-YYYYMMDD-{customer_id}-{4位随机码}` 生成（与 services/billing.py:1344 一致）；模板提供时校验非空唯一
- 明细 items：**第一版仅主表导入**（明细需 device_type/layer_type/quantity 且与计费规则关联，复杂度高；外部历史单核心为主表金额，明细可在详情中后续处理）→ Deferred
- 执行：company_id → customer_id 预加载映射；逐行创建 Invoice(status=draft)，行级错误；成功后缓存失效按需

### 6. 前端
- `frontend/src/api/billing.ts` 新增 9 个 API（exportBalances/importPricingRules/downloadPricingRuleTemplate/exportPricingRules/importPackagePlans/downloadPackagePlanTemplate/exportPackagePlans/importInvoices/downloadInvoiceTemplate），全部 `responseType:'blob'`（导出/模板）或 FormData（导入）
- 新建通用导入弹窗 `frontend/src/views/billing/components/ImportModal.vue`：props { title, importApi, templateApi, templateFileName }，复用 ImportBalanceModal 的拖拽/校验/结果展示样式模式；**三个页面（计费规则/包年套餐/结算单）复用**，避免复制三份
  - 说明：现有 ImportBalanceModal 与 CustomerImportModal 保持不动（样式并入通用组件的话仅取其模式不重构其自身），新组件与其并存，样式一致
- 页面接线：
  - Balance.vue：PageHeader 增加「导出」按钮 `can('billing:balance_export')`，组装当前 filters+advancedFilters+sortState 调 exportBalances（参数映射复用 loadBalances 逻辑，抽 `buildBalanceExportParams()`）；既有「导入」按钮权限码改 `can('billing:balance_import')`
  - PricingRules.vue：增加「导入规则」(`billing:pricing_import`) +「导出」(`billing:pricing_export`) 按钮 + ImportModal
  - PackagePlans.vue：增加「导入套餐」(`billing:package_import`) +「导出」(`billing:package_export`) 按钮 + ImportModal
  - Invoices.vue：增加「导入」(`billing:invoice_import`) 按钮 + ImportModal；既有「导出」按钮权限码改 `can('billing:invoice_export')`

## 兼容性与迁移

- **权限迁移（破坏性）**：改 seed.py ALL_PERMISSIONS（2 旧码 → 8 新码）、PRESET_ROLES（运营/销售经理 billing:export → 4 导出码）、conftest（权限注册与 FULL_PERMISSIONS 用新码）、前后端引用点；存量库执行 seed 迁移逻辑完成等价授予
- 不改动任何现有端点行为（仅声明权限码变更）；get_balances 为机械提取重构，需既有测试守护（conftest 已含 billing 权限与平衡测试辅助）
- 无数据库表结构迁移（仅权限种子数据与 role_permissions 映射）

## 重要权衡

| 决策 | 权衡 |
|------|------|
| 细粒度权限拆分（8 码） | 支持按页面独立授权（如允许导余额但禁止导结算单）；代价是迁移存量角色绑定 + 改动 seed/conftest/前端判断，本次一并完成 |
| 等价迁移（旧码 → 方向全量新码） | 存量角色权限范围不缩水、用户无感；代价是新码初期语义偏宽，后续可手动收窄 |
| 结算单导入仅主表 | 明细导入复杂度高且与计费规则强关联；主表金额为历史单核心，明细可后续处理。若业务需要可迭代加 items 列 |
| 计费规则逐行调服务层 | 复用冲突检查/拆分/package 填充，避免绕过业务规则；1000 行内性能可接受 |
| 通用 ImportModal vs 复制三份 | 消除 3 份重复；与现有两个独立弹窗并存（不重构既有，控制影响面） |
| get_balances 提取共享函数 | 消除筛选逻辑双份漂移风险；机械重构有回归风险，靠既有测试 + 新增导出测试守护 |

## 运营与回滚

- 回滚：前端移除按钮/API 调用；后端移除新端点即可；**权限迁移回滚**：旧码记录已在迁移后清理，如需回退到旧码体系，重新注册旧权限码并绑定即可（映射表保留在 seed.py 中），无数据丢失
- 导入幂等性：计费规则/包年套餐导入依赖唯一性/冲突检查防止重复；结算单依赖 invoice_no 唯一（缺省随机码碰撞概率极低，冲突时该行报错）
- 审计日志在导入端点统一记录，操作可追溯
