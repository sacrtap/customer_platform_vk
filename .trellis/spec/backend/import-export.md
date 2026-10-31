# Excel 批量导入 / 导出端点规范

> 批量导入/导出的技术契约。记录端点签名、模板结构、行级错误约定与已知陷阱。

## Scope / Trigger

- 触发：为 billing 4 个子页面补齐导入导出、抽取共享模板解析（`090-16-import-export-optimization` 任务）
- 适用范围：所有 `POST /*/import`、`GET /*/import-template`、`GET /*/export` 端点
- 强制深度理由：新 API 签名 + 跨层契约（前端弹窗依赖固定响应结构）+ 权限码体系变更

---

## Signatures

### 共享模板读取（`backend/app/utils/excel_import.py`）

```python
def read_import_dataframe(body: bytes, first_column: str) -> "pd.DataFrame"
def _is_template_note_row(df: "pd.DataFrame", first_column: str) -> bool
```

- `first_column`：模板第 1 列的英文列名（如 `company_id` / `name`），用于判定第 1 行是否为中文说明行
- 返回的 DataFrame **保留原始索引标签**：第 `i` 行数据的真实 Excel 行号为 `i + 2`

### 端点清单（`backend/app/routes/`）

```
POST /api/v1/customers/import              @require_permission("customers:import")
GET  /api/v1/customers/import-template
GET  /api/v1/customers/export              @require_permission("customers:export")   limit=50000

POST /api/v1/billing/import                @require_permission("billing:balance_import")
GET  /api/v1/billing/import-template
GET  /api/v1/billing/balances/export       @require_permission("billing:balance_export")   limit=50000

POST /api/v1/billing/pricing-rules/import  @require_permission("billing:pricing_import")
GET  /api/v1/billing/pricing-rules/import-template
GET  /api/v1/billing/pricing-rules/export  @require_permission("billing:pricing_export")

POST /api/v1/billing/package-plans/import  @require_permission("billing:package_import")
GET  /api/v1/billing/package-plans/import-template
GET  /api/v1/billing/package-plans/export  @require_permission("billing:package_export")

POST /api/v1/billing/invoices/import       @require_permission("billing:invoice_import")
GET  /api/v1/billing/invoices/import-template
```

- 导入与导出端点必须同时具备 `@auth_required` + `@require_permission`；`import-template` 按既有先例仅 `@auth_required`
- 导出响应为 `raw`（xlsx 字节流），`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

---

## Contracts

### 导入请求

| 项 | 约定 |
|---|---|
| 方法 | `POST`，`multipart/form-data`，字段名 `file` |
| 文件类型 | 仅 `.xlsx` |
| 行数上限 | **余额充值导入 ≤ 2000 行**（2026-10-13 提高：余额导出回灌可达 1274 行，1000 会拦截真实工作流；超限返回 `40004`）；计费规则/套餐/结算单 ≤ 1000 行；客户导入无后端强制，仅前端提示「单次建议不超过 1000 条」，避免阻断全量导出回灌 |
| 数据行起点 | 模板第 3 行（第 1 行英文列名、第 2 行中文说明、第 3 行示例） |

### 导入响应（`data`）

```json
{
  "success_count": 3,
  "error_count": 1,
  "errors": ["第 4 行：客户编号 999999 不存在"]
}
```

- `errors` 最多返回 10 条（`errors[:10]`），完整错误仅落日志/审计
- **行级错误不阻塞其他行**：逐行 try/except，成功行照常提交
- 导入必须写审计：`create_audit_entry(module="billing", action="batch_create", operation_type="batch")`

### 预检查（dry_run，二次确认契约）
`POST /import?dry_run=true`：**5 个导入端点全覆盖**（客户/余额/计费规则/套餐/结算单；
2026-10-13 余额、计费规则、套餐、结算单依次补齐，与客户导入同模式）——**完整行级
校验但不落库**，返回：

```json
{ "code": 0, "message": "预检查完成",
  "data": { "dry_run": true, "success_count": 2, "error_count": 1,
            "errors": ["第 3 行：…", ...] } }
```

- **dry_run 分支必须先于 `valid_rows` 空分支判断**：全部行有错误时也应返回
  「预检查完成」而非「导入完成」（2026-10-13 踩坑修正）
- 预检查返回 `errors[:50]`（足够确认）；真实导入仍 `errors[:10]`
- 套餐/结算单 dry_run 在循环内**同样维护判重集合**（`existing_types` /
  `existing_invoice_nos`），保证预检查与真实导入的去重结果一致
- dry_run 分支先于 commit/缓存失效/审计——**请求不产生任何副作用**
- 不写库、不写审计、不动缓存；前端两步流程：上传 → **预检查** → 展示
  「可导入 N 条 / 错误 M 条 + 行号明细」→ **确认导入** 才真正落库

### 事务结构：autobegin 陷阱（2026-10-31 起强制）

预检查阶段的只读 `db_session.execute(...)` 会触发 SQLAlchemy 2.0 的 **autobegin**
隐式事务；此后直接 `async with db_session.begin():` 抛
`InvalidRequestError: A transaction is already begun on this Session.`（落库 500）。
单测用 AsyncMock  mock 掉 session 不会暴露，只有集成测试能抓到。

正确结构（预检查询与落库之间显式断开事务）：

```python
if dry_run:
    return json(...)  # 预检只读查询后的隐式事务随请求回滚，无副作用

await db_session.commit()  # 断开 autobegin 隐式事务（只读查询无副作用）

async with db_session.begin():
    ...  # 所有写操作在 begin 块内（硬规则）
```

替代方案：把预检查询也放进同一个 `async with db_session.begin():` 块。
禁止用 `begin_nested()` 绕开外层 `begin()`——savepoint 仍要求外层有事务，
且掩盖了「预检无副作用」的语义。

### 模板结构（生成规则）

| 行 | 内容 |
|---|---|
| 1 | 英文列名（与模型字段对齐，如 `company_id` / `period_start` / `total_amount`） |
| 2 | 中文说明，**必须以 `必填：` 或 `可选：` 开头**（如 `必填：客户编号（整数）`） |

**禁止第 3 行示例数据**（2026-10-31 起强制）：`read_import_dataframe` 只丢弃第 2 行
中文说明行，第 3 行示例数据会被当作真实数据导入。用户下载模板后通常直接在示例行
下方续写，示例行会被静默创建成一条记录（示例客户编号不存在时还会整行报错，
干扰用户判断）。示例值并入第 2 行说明文字（如「必填：用户名（唯一），如 zhangsan」）。
`template_response` 的 columns 为二元组 `[(英文字段名, 中文说明), ...]`。

第 2 行的前缀契约是 `_is_template_note_row` 的判定依据，不可随意改文案。

### 导出约定

- 导出复用列表查询逻辑：余额导出必须调用与 `get_balances` 相同的 `_parse_balance_filters` + `_query_balance_rows`，禁止复制第二份筛选/燃尽计算
- 筛选条件透传当前页面的全部筛选参数
- 空数据返回 `40002`（而非空文件）
- 列顺序与前端表格列对齐

### 客户导入/导出字段对称（27 列，禁止单侧增删）

`customers/import` 与 `customers/export`、`customers/import-template` **三处列名与列序必须一致**
（2026-09-29 起强制；此前模板缺 `auto_initiate_settlement` 导致导出回灌时该列与
`scale_level` 静默丢失；2026-09-30 追加运营/销售经理列 23→25；2026-10-13 追加
`is_real_estate`（房产客户）25→26；**2026-10-25 追加 `settlement_account_id`
（结算账户，代扣余额）26→27**——此前 PRD 明确「Excel 导入不支持该字段」，而导出
侧同样没有该列，导致客户在页面配置的结算账户在文件链路中完全不可见、导出→回灌后
静默退回「用自身余额」）：

```
company_id, name, manager, sales_manager, account_type, industry, price_policy,
settlement_type, settlement_cycle, is_key_customer, is_real_estate, email,
erp_system, first_payment_date, onboarding_date, cooperation_status,
is_settlement_enabled, auto_initiate_settlement, is_disabled, notes,
settlement_account_id, scale_level, consume_level, monthly_avg_shots,
monthly_avg_shots_estimated, estimated_annual_spend, actual_annual_spend_2025
```

导入侧转换规则（`CustomerService.batch_create_customers`，不得静默丢列）：

| 字段 | 规则 |
|---|---|
| `industry` | 名称 → `industry_type_id`；不存在 → 行级错误；**解析失败整行剔除** |
| `manager` | **运营经理中文姓名/用户名 → `manager_id`**（`real_name` 优先、`username` 兜底；仅匹配启用用户）；不存在或已停用 → 行级错误「运营经理 'x' 不存在或已停用」，**整行剔除**（与 industry 同语义：填了但无法解析则不入库，而非静默留空）。**real_name 重名规则（2026-09-30 起）**：`User.real_name` 无唯一约束，同名多个启用用户时按姓名**不自动映射**，行级报错「对应多个启用用户，请改用用户名填写」并整行剔除（防静默错配——manager_id 驱动数据可见性，错配污染归属） |
| `sales_manager` | 销售经理中文姓名/用户名 → `sales_manager_id`，规则同 `manager` |
| `price_policy` | 中文「定价/阶梯/包年」→ 英文 `pricing/tiered/yearly` |
| `settlement_type` | 中文「预付费/后付费」→ 英文 `prepaid/postpaid`（`convert_settlement_type_to_storage`） |
| `settlement_cycle` | 中文「日结/周结/月结/季结/年结」→ 英文 `daily/weekly/monthly/quarterly/yearly` |
| `is_key_customer` / `is_settlement_enabled` / `auto_initiate_settlement` / `is_disabled` / `is_real_estate` | 「是/否」/`true/false` → 布尔；`convert_bool_field` |
| `cooperation_status` | **实时取 `cooperation_statuses` 字典表**（`deleted_at IS NULL`，与「合作状态」管理页面同源）：`value` 直接匹配 + `name` 中文映射；均不命中 → 行级错误（不静默置空）。**禁止硬编码白名单**——页面可增删改枚举，硬编码会让导入与页面脱节（2026-10-13：页面新增 `bding/拓展中` 后校验仍报「无效的合作状态」） |
| `scale_level` / `consume_level` | 写入 `customer_profiles`（`scale_level` 必须进 profile_fields） |
| `settlement_account_id` | **结算账户客户编号（`company_id`）→ `customers.id`**（2026-10-25 起；此前导入完全不支持该字段）。解析在**路由层**完成（与 `manager`/`sales_manager` 姓名解析同层同模式：批量查 `company_id → id` 映射，避免 N+1），服务层 `optional_fields` 做 NaN 清洗、`Customer` 构造传参落库。校验语义与 `update_customer` 一致：**自引用拒绝**（结算账户 == 本行 company_id）、**目标必须存在且未软删**；填了但无法解析 → 行级错误并**整行剔除**（不静默留空——用户以为设了结算账户，实际扣款会走错余额）。导出侧输出 `c.settlement_account.company_id`（用户可读主键，与 `company_id` 列同一命名空间），两侧互逆 |
| `first_payment_date` / `onboarding_date` | 统一 `parse_date_to_object`（date 对象，非字符串） |

**字典驱动字段（2026-10-13 起）**：`cooperation_status` 的有效值集**实时查询
`cooperation_statuses` 表**（过滤软删，与「合作状态」页面同源），禁止在服务层硬编码
白名单——该表由页面动态增删改，「页面有但校验不认」即契约脱节。模板第 2 行提示
与错误信息里的可选值均由同一查询动态生成，保持与页面一致。

导出侧（`GET /customers/export`）：`manager` / `sales_manager` 列输出 user 的
`real_name`（空则 `username`）——与导入侧解析**互逆**，导出文件可直接回灌导入。
批量映射 user_id → 姓名（一次性查询 `User.id.in_(manager_ids)`，避免 N+1）。

### 客户导入预检查（dry_run，二次确认契约）

`POST /customers/import?dry_run=true`：**完整行级校验但不落库**（含行业/枚举/经理
姓名/重复 company_id 等全部规则），返回：

```json
{ "code": 0, "message": "预检查完成",
  "data": { "dry_run": true, "success_count": 5, "error_count": 2, "errors": ["行3: ...", ...] } }
```

- `success_count` = 通过全部校验、将入库的行数；`errors` 含真实 Excel 行号
- 不写库、不写审计、不动缓存；重复提交同文件（不带 dry_run）才真正入库
- dry_run 返回 `errors[:50]`（足够确认）；真实导入仍 `errors[:10]`
- 前端流程：上传文件 → **预检查** → 展示「可入库 N 条 / 错误 M 条 + 行号明细」→
  **确认导入** 才落库（`CustomerImportModal` 两步按钮）；更换文件后须重新预检查
- 服务层 `batch_create_customers(customers_data, dry_run=True)` 同一校验路径复用，
  保证预检结果与实际入库一致（不出现「预检通过但落库失败」偏差）

**结算单导入 `discount_amount` 允许负值（2026-10-26 起）**：减免金额的业务语义
与 `apply_discount`、前端 `SubmitModal`/`DiscountEditModal` 完全一致——**正数从
总额扣除、负数为加价**（`final_amount = total_amount - discount_amount`）。导入端
此前单独写了一条 `if discount_amount < 0: 行级报错`，与其余三个入口（页面设置减免、
提交审批、批量导入）脱节，导致「负减免=加价」的合法数据被预检查拦下、报
「减免金额不能为负」——而用户在 `DiscountEditModal` 的 help 文案里明明看到
「正值为减免（从总额扣除），负值为加价」。**同一字段的跨入口校验规则必须同源**，
凡页面/服务层允许的值，导入侧一律放行（导入是补录通道，不是更严的第二套规则）。
保留的约束只有：非有限值（NaN/Inf）拒绝、`> total_amount` 上限越界拒绝。导入
模板第 2 行说明同步为「可选：减免金额（元），负值为加价」。

### 数值列解析：pandas float64 提升陷阱（2026-10-30 起）

**基线问题**：用户用全量导出备份 `customers_2026-10-27.xlsx`（1450 行）做导入预检查，
`settlement_account_id` 列 15 个非空行全部误报「结算账户客户编号 '547.0' 不是有效整数」、
被整行剔除——而用户在 Excel 里看到的就是整数 `547`。

**根因**：该列既有整数又有空单元格，`pd.read_excel` 把整列提升为 **float64**
（`547 → 547.0`，空单元格为 NaN）。解析处写成 `int(str(raw).strip())`：
`str(547.0)` = `"547.0"`，`int("547.0")` 抛 ValueError。同处上方的
`is_integer()` 守卫虽通过却无意义——真正执行转换的是先字符串化再 int 的那一步。

**修复**（`customers.py` 路由层 settlement_account_id 解析）：按值类型分支——
float 先过 `is_integer()` 守卫（拒绝 `547.9`，语义不变）再直接 `int(raw)`；
int 原样透传；字符串才走 `str().strip()` + `int()`（兼容手填 `"547"`）。
回归测试 `test_import_customers_settlement_account_float_column`：构造该列
「20 行空 + 少量整数」的 xlsx 强制 float64，断言合法行落库、小数行仍被拒。

**约定（全仓导入端点适用）**：凡解析 Excel 数值列，**禁止 `int(str(x))`**——
混合空单元格的整数列必被 pandas 提升为 float64，字符串化中转必炸。必须按
`isinstance` 分支：float→守卫后 `int(x)`、int→透传、str→strip 后 `int()`。
同理注意：模板第 2 行说明行若在某列填了中文，会把该列拖成 object dtype
（数值保持 int，不触发本 bug 但也不复现它）——写回归测试时说明行的目标列必须留空。

### 结算单导入受控字段

仅暴露 `company_id` / `period_start` / `period_end` / `total_amount` / `discount_amount` / `invoice_no`（可选）：

- `status` 固定 `draft`，`is_auto_generated=False`（禁止导入端指定状态，规避绕过审批流程）
- `invoice_no` 缺省按系统规则生成：`INV-YYYYMMDD-{customer_id}-{4位随机码}`
- 明细（`detail_file_*` 等内部字段）不开放

**结算单导出列必须含 `company_id`（2026-10-25 起）**：导出表头为
`结算单号, company_id, 客户名称, 周期开始, 周期结束, 总金额, 减免金额, 最终金额, 状态, 创建时间`
——此前导出只有中文列、**缺导入主键列 `company_id`**，用户拿导出文件回灌必然报
「缺少必填列：company_id, period_start, period_end, total_amount」（文件其实没问题，
误导性极强）。与 balances/pricing-rules 导出的 `company_id` 约定保持一致；
统计行（共 N 条记录/总金额/最终总额）的列号随新列右移（第 6/8 列）。

**结算单导入列名别名归一（2026-10-25 起）**：导出是中文展示列、导入期待英文存储列，
导入端做 `df.rename` 别名映射后按同一行级校验路径处理（与余额导入 2026-10-13 同模式）：

| 导出中文列 | 导入英文列 |
|---|---|
| 客户编号 | `company_id` |
| 周期开始 | `period_start` |
| 周期结束 | `period_end` |
| 总金额 | `total_amount` |
| 减免金额 | `discount_amount` |
| 结算单号 | `invoice_no` |

无法对齐的展示列（客户名称/最终金额/状态/创建时间）不参与导入——`status` 固定
`draft`、`invoice_no` 缺省自动生成，属受控字段。**软回灌不改变导入语义**（加的是
列兼容，不是「以快照覆盖结算单」的新功能）。

**旧版导出文件回灌（2026-10-25 起）**：升级前导出的结算单文件只有中文列且**无
`company_id`**，用户手里已有一批，不能因为升级就被判「缺少必填列」作废。契约：

1. `company_id` **允许缺列**——必填列降为 `period_start`/`period_end`/`total_amount`；
   客户标识列只要 `company_id` 或「客户名称」二者有其一即可，两者全无才报缺列。
2. `company_id` 为空或整列缺失时，**回退按「客户名称」解析** `customer.id`
   （新文件有 company_id 则优先走编号）。
3. 名称解析**重名拒绝**：同名多个启用客户时行级报错「客户名称 'x' 对应多个客户，
   请改用 company_id（客户编号）列」并整行剔除——**不静默挂到任意同名人名下**
   （结算单归属/扣款错配不可逆）。名称不存在 → 行级错误；无权访问（无
   `customers:view_all` 且非自己负责）→ 行级错误。
4. **丢弃导出追加的统计行**：`_build_invoices_excel` 末行是「共 N 条记录」（结算单号
   列填统计文案、其余 NaN），回灌时必须剔除，否则产生一条「客户名称为空」的虚假
   行级错误干扰用户判断。判定：客户标识列为空且首列含「条记录」。

**变更传播后置成本（2026-10-25 教训）**：给导出端加列时，别忘了**用户手里已有
旧导出文件**——新列是给未来用的，但回灌兼容是给存量用的。加主键列的同时必须保留
按名称/别名的降级解析路径，否则升级当天用户的存量文件全部报错。

---

## 四端点字段对称核验表（2026-09-29 扩散排查）

正则：**模板列 == 服务解析列**（不许静默丢列）；**导出 ⊇ 模板**（实体型端点须可回灌）。

| 端点 | 导出列 | 模板列 | 性质 | 回灌 | 结论 |
|---|---|---|---|---|---|
| 客户 customers | 27 列（含 auto_initiate_settlement、is_real_estate、settlement_account_id） | 27 列 | 实体型 | ✅ 可行 | 已修复（模板缺列/服务丢 scale_level、auto_initiate_settlement；2026-10-13 补 is_real_estate 三处；**2026-10-25 补 settlement_account_id 三处**——此前导入/导出/模板均无该列，页面配置的结算账户在文件链路中完全丢失） |
| 计费规则 pricing-rules | 13 列（⊇ 模板，多 id/customer_name） | 11 列 | 实体型 | ✅ 可行 | 已核验，有回灌测试 `test_export_pricing_rules_date_round_trip`；**2026-10-13 用户 228 行导出文件回灌 dry_run 全过（success 228 / error 0）** |
| 包年套餐 package-plans | 13 列（⊇ 模板，多 id/created_at/updated_at） | 10 列 | 实体型 | ✅ 可行 | 已补回灌测试 `test_export_package_plans_reimport_round_trip` |
| 余额 recharge | 13 列中文快照（查询视图） | 4 列（充值操作） | 操作型 | ✅ 列别名软回灌 | 模板==解析（4 键全消费）；**2026-10-13 起导出文件列名自动归一**（客户ID/实充余额（元）/赠送余额（元）→ company_id/real_amount/bonus_amount），快照按充值入账；0 元与负金额（后付费应收）均允许导入 |
| 结算单 invoices | 10 列（含 company_id） | 6 列（受控 draft） | 操作型 | ✅ 列别名软回灌 | **2026-10-25 修复**：导出曾缺 `company_id` 且为纯中文列，回灌报「缺少必填列」；现导出含 `company_id`，导入端别名归一（周期开始/周期结束/总金额/减免金额/结算单号 → period_start/period_end/total_amount/discount_amount/invoice_no），有回灌测试 `test_import_invoices_accepts_export_file_columns` |

操作型端点（余额/结算单）**默认不强制导出回灌**——导入是补录动作、导出是查询视图，
列集合天然不同；实体型端点（客户/计费规则/套餐）**必须导出⊇模板且可回灌**。
**列别名软回灌例外（余额 2026-10-13、结算单 2026-10-25）**：导入端 `df.rename`
中文展示列 → 英文存储列，导出文件可直接上传、不再报「缺少必填列」，之后按同一行级
校验路径处理。语义边界：余额快照按「本次充值」入账（0 元与负金额均允许导入，用于
批量初始化/迁移与后付费应收余额快照；负值按充值记录入账并扣减余额）；结算单按
补录处理（`status` 固定 `draft`、`invoice_no` 缺省自动生成）——**软回灌不改变导入
语义**，不是「以快照覆盖既有数据」的新功能。

**导出缺主键列 = 回灌必断（2026-10-25 教训）**：结算单导出曾只有「客户名称」而缺
`company_id`，且其余列全是中文展示名——两侧列名根本不是同一套。**凡导入以
`company_id` 为主键列，导出就必须包含 `company_id`**（balances/pricing-rules 均如此），
否则用户拿导出文件回灌必然撞列级 40003。

### 枚举转换函数方向契约（`backend/app/services/customers.py`）

所有 `convert_*_to_storage` 必须满足（2026-09-29 起强制，方向性单测 `tests/unit/test_enum_conversions.py`）：

1. 中文 → 英文存储值（`定价`→`pricing`、`预付费`→`prepaid`、`月结`→`monthly`）
2. 已是英文存储值 → **原样透传（幂等）**
3. 未知值 → **返回 None**，由调用方报行级错误（**禁止 `.get(k, k)` 透传脏值落库**——曾导致「无效计费模式」校验形同虚设）

调用方契约：`price_policy` / `settlement_type` / `settlement_cycle` / `cooperation_status` 四个字段
未知值一律行级报错并 `continue`，绝不静默置空。
**空白字符串（2026-09-30 起）**：`strip()` 后为空的单元格按「未填写」处理，不报无效值——
`settlement_type` 走 prepaid 默认值，`price_policy` / `settlement_cycle` 跳过转换（用户误输空格不应报错）。

### 行业类型共享主数据规则（`industry_type_routes.py` / `industry_type_service.py`）

- **改名/删除审计由全局中间件 `middleware/audit.py` 自动记录**（可追溯「_编辑_编辑」式脏名责任人）；
  **禁止在路由内再写手动审计**（2026-09-30 起：原 PUT/DELETE 手动审计已删除，否则每条操作落两条日志）。
  中间件命名规则：`module` = 路径段原样（`industry-types`），`record_type` = 模型类名小写
  （`industrytype`），`before` 快照由 request 中间件序列化完整记录——写断言/查询审计时按此命名
- **删除引用保护**：被 `customer_profiles.industry_type_id` 引用的行业返回 409 禁止删除
  （行业删除会连锁导致：客户列表行业列悬空、导出文件回灌时行业名失配报错——本次 1242 行
  导入失败的直接根因之一）
- 客户导入侧行业映射查询（`customers.py:966 select(IndustryType)`）不过滤软删除——若需
  严格禁止回罐已删行业，改为 `where(deleted_at.is_(None))` 并配套错误提示

### 行业类型 ID 管理规则（2026-09-29 起）

- **新增可指定 id**（body `id` 可选，正整数；缺省自增）。指定 id 已占用——**含软删记录**——
  返回 409「行业类型 ID n 已存在」（主键唯一约束对软删记录仍生效）
- **同名软删记录自动恢复**：新增时若存在软删除的同名记录，**恢复原记录**（undelete，保留
  原 id 与 sort_order 更新），而非新建。必要原因：`name` UNIQUE 索引被软删记录占位，
  若只查 `deleted_at IS NULL` 会漏掉占用 → INSERT 撞数据库唯一约束 → 500（实测无法新增
  「项目」：id=1 软删但仍占用 name 唯一索引，849 个客户画像引用其 id）。恢复即让客户
  引用重新生效，列表行业列不悬空
- **update 名称唯一校验必须含软删（2026-09-30 起）**：与 create 一致用 `get_any_by_name`
  全量匹配（仅查 `deleted_at IS NULL` 会漏掉软删占用 → 改名撞唯一索引 → 500）；改为
  软删同名 → 409「行业类型名称 'x' 已存在」（与 create 恢复语义不同：update 是改名，
  不允许借道软删占位）
- **编辑可修改 id**（body `id` 可选作新主键）：目标 id 被其他记录占用（含软删）→ 409；
  **被 customer_profiles 引用的行业禁止修改 id** → 409「正被 N 个客户使用，不能修改 ID」
  （改 id 会使外键引用悬空，与删除引用保护同理）
- **显式 id 必须同步序列**：指定 id 高于当前自增序列时，执行
  `SELECT setval(pg_get_serial_sequence('industry_types','id'), max_id)`，否则后续自增
  撞主键（`_sync_id_sequence`）
- 审计：update 记录 `changes.before.id`（旧 id）与 `changes.after.id`（新 id），
  `record_id` 用新 id；改名/删除审计留痕规则不变

---

## Validation & Error Matrix

| 条件 | 结果 |
|---|---|
| 未认证 | `40101` |
| 缺少对应权限码 | `40301` |
| 非 `.xlsx` / 空文件 | `40003` |
| 超过 1000 行 | `40004`（`"单次导入不超过 1000 行"`） |
| `company_id` 非整数 | 行级错误：`第 N 行：客户编号 'x' 不是有效整数` |
| `company_id` 不存在 | 行级错误：`第 N 行：客户编号 999999 不存在` |
| 金额列非数字 | 行级错误：`第 N 行：结算金额格式错误`（不得回显 Python 异常类名） |
| 必填字段缺失 | 行级错误：`第 N 行：<字段名> 不能为空` |
| 非包年计费规则（`pricing_type != package`）缺 `device_type` / `layer_type` | 行级错误：`第 N 行：设备类型不能为空（非包年结算必填）`；`layer_type` 对应 `第 N 行：楼层类型不能为空（非包年结算必填）` |
| 非包年规则取值越界：`device_type` ∉ {`X`,`N`,`L`}、`layer_type` ∉ {`single`,`multi`,`single_and_multi`} | 行级错误：`第 N 行：设备类型必须为 X/N/L` / `第 N 行：楼层类型必须为 single/multi/single_and_multi` |
| `package_type` 重复（含软删除比对） | 行级错误 |
| 计费规则 `tiers` 形态非法（非数组 / 元素缺字段） | 行级错误：`第 N 行：阶梯配置 JSON 格式错误：…` |
| 计费规则 `tiers` 语义非法（首档 `min` ≠ 0、相邻档区间不连续、非末档无上界） | 行级错误：`第 N 行：阶梯配置不合法：…`；
创建/编辑规则（`POST`/`PUT /pricing-rules`）同约束 → `400` / `40001` |
| 计费规则冲突（package/single overlap） | 行级错误（由服务层 `create_pricing_rule` 抛出） |
| 导出无匹配数据 | `40002` |

---

## Good/Base/Bad Cases

- **Good**：下载模板 → 填 3 行合法数据 → 导入 → `{success_count: 3, error_count: 0}`，列表出现 3 条新记录
- **Base**：模板原样上传（仅表头 + 说明行，无数据行）→ 说明行被跳过，`success_count == 0, error_count == 0`，绝不出现「说明行被当成数据」的虚假错误
- **Bad**：导入端点自行 `pd.read_excel` 而不调用 `read_import_dataframe` → 说明行被当数据，用户首次导入必然看到虚假错误行

---

## Tests Required

集成测试（`backend/tests/integration/test_billing_import_export_api.py`）必须覆盖：

| 断言点 | 说明 |
|---|---|
| 成功导入 | `success_count` 与落库条数一致；结算单导入断言 `status == "draft"` |
| 模板回灌 | 下载模板 → 写入数据 → 上传：断言说明行未计入错误、错误行号指向真实 Excel 行（如 `第 4 行`） |
| 必填缺失 | 行级错误文案包含字段名 |
| 行级错误不阻塞 | 1 合法 + 1 非法 → `success_count == 1 and error_count == 1` |
| 权限拦截 | 无 `*_import` / `*_export` 权限 → `403` |
| 导出行数上限 | 超过 50000 → 明确错误 |
| 导出内容 | 有数据时读回 xlsx 断言列名与行值（不能只测空数据 `40002` 分支） |
| **导出含主键列** | 凡导入以 `company_id` 为主键列，导出文件必须含 `company_id` 列且值为客户编号（结算单 2026-10-25 起；断言 `"company_id" in columns` 及数据行取值） |
| **导出文件回灌** | 用导出列结构（中文展示列）组装文件上传 → 不得报列级「缺少必填列」，进入行级校验并正确落库（余额 `test_import_balances_accepts_export_file_columns`、结算单 `test_import_invoices_accepts_export_file_columns`） |
| **旧版导出文件回灌** | 无 `company_id` 列 + 含统计行的旧结构上传 → 按「客户名称」解析、统计行被剔除、`error_count == 0`（`test_import_invoices_accepts_legacy_export_file_without_company_id`） |
| **重名客户名拒绝** | 旧结构按名称解析遇到重名 → 行级错误「对应多个客户」且整行剔除，`success_count == 0`（`test_import_invoices_ambiguous_customer_name_rejected`） |
| **导出列含新字段** | 客户导出须含 `settlement_account_id`，值为结算账户客户的 `company_id`、未配置为空（`test_export_customers_contains_settlement_account_column`） |
| **新字段导入往返** | 导入 `settlement_account_id` → 落库为 `customers.id`；自引用/目标不存在 → 行级错误且整行剔除（`test_import_customers_settlement_account_roundtrip`） |
| **正式导入落库** | 真实导入（非 dry_run）必须走集成测试：单测 mock 掉 session 后 `db.begin()` 不抛错，**autobegin 事务冲突只有集成测试能抓到**（2026-10-31 六个路由集体踩坑，全 500） |
| **集成测试缓存 mock** | 导入端点调用 `cache_service.invalidate_*_cache()` 时，`tests/integration/conftest.py` 的 `mock_cache` 必须 AsyncMock 对应方法（漏 `invalidate_tag_cache` 会 500） |

---

## Wrong vs Correct

### 1. 模板说明行判定

```python
# ❌ Wrong：模板文案是「必填：客户编号（整数）」，等值比较永不成立
if str(df.iloc[0].get(col)) in ("必填", "可选"):
    df = df.iloc[1:]

# ✅ Correct：用前缀判定，且切片保留索引标签（行号 = i + 2）
return str(df.iloc[0].get(first_column, "")).strip().startswith(("必填", "可选"))
```

### 2. 日期列写入

```python
# ❌ Wrong：convert_date_field 返回 "YYYY-MM-DD" 字符串 → asyncpg DataError
#    ("'str' object has no attribute 'toordinal'") → 整个请求 500
customer.first_payment_date = convert_date_field(row.get("first_payment_date"))

# ✅ Correct：写 Date 列必须用返回 datetime.date 的解析函数
customer.first_payment_date = parse_date_to_object(row.get("first_payment_date"))
```

### 3. 金额解析异常捕获

```python
# ❌ Wrong：Decimal(str(x)) 抛 InvalidOperation（ArithmeticError 子类，不是 ValueError），
#    被兜底 except 捕获后原文回显 "[<class 'decimal.ConversionSyntax'>]"
try:
    base_fee = Decimal(str(row.get("base_fee")))
except ValueError:
    errors.append(f"第 {idx + 2} 行：基础费用格式错误")

# ✅ Correct：显式纳入 InvalidOperation，输出用户可读文案
from decimal import Decimal, InvalidOperation

try:
    base_fee = Decimal(str(row.get("base_fee")))
except (ValueError, TypeError, InvalidOperation):
    errors.append(f"第 {idx + 2} 行：基础费用格式错误")
```

### 4. 阶梯配置（`tiers`）写入

```python
# ❌ Wrong：只做形态归一化就落库 → 首档 min>0 / 区间缺口/重叠的脏规则进入结算
#    _calc_tiered 不减去首档 min 偏移：超档用量落到更便宜的下一档（静默少收，
#    实测 [5..100 @10, 101..∞ @8] 用量 100 得 992，等价 min=0 应为 1000）；
#    单档无上界时 min 完全不参与计算
data["tiers"] = normalize_tiers(data["tiers"])

# ✅ Correct：规则创建/编辑走 validate_tiers_or_raise（归一化 + 覆盖完整性，None 保持 None）
from app.utils.tiers import validate_tiers_or_raise

data["tiers"] = validate_tiers_or_raise(data["tiers"])
```

Excel 导入路径用 `parse_tiers_or_raise(parsed, row_num=...)`（同样校验，并翻译为行级文案）。
前端 `PricingRuleModal.getTierError` 已强制首档 `min=0`，后端只是把该约束下沉统一把关；
**存量脏数据不迁移、历史金额不重算**（改口径需单独排期）。

---

## 权限码变更检查清单

新增/废弃权限码时，以下位置必须同步（遗漏任一处会导致"按钮可见但 403"或"权限丢失"）：

| 位置 | 内容 |
|---|---|
| `backend/app/routes/**` | `@require_permission("模块:动作")` |
| `backend/scripts/seed.py` | `ALL_PERMISSIONS` 注册；`PRESET_ROLES` 预置角色授权 |
| `backend/scripts/seed.py` 步骤 2.6/2.7 | `LEGACY_TO_NEW_PERMISSIONS` 等价迁移 + 旧码记录清理（幂等） |
| `backend/tests/integration/conftest.py` | 权限注册列表 + `FULL_PERMISSIONS` |
| `frontend/src/views/**` | `can("模块:动作")` |
| `frontend/src/views/roles/permissionGroups.ts` | 权限分组展示（按 module 自动分组，通常无需改） |

> **Warning**：废弃旧码时必须在 seed 中先做**等价授予**再清理记录，否则存量角色的权限会静默丢失。
