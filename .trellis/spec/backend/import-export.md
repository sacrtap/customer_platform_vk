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
| 行数上限 | ≤ 1000 行（与余额导入先例一致，超限返回 `40004`） |
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

### 模板结构（生成规则）

| 行 | 内容 |
|---|---|
| 1 | 英文列名（与模型字段对齐，如 `company_id` / `period_start` / `total_amount`） |
| 2 | 中文说明，**必须以 `必填：` 或 `可选：` 开头**（如 `必填：客户编号（整数）`） |
| 3 | 示例数据 |

第 2 行的前缀契约是 `_is_template_note_row` 的判定依据，不可随意改文案。

### 导出约定

- 导出复用列表查询逻辑：余额导出必须调用与 `get_balances` 相同的 `_parse_balance_filters` + `_query_balance_rows`，禁止复制第二份筛选/燃尽计算
- 筛选条件透传当前页面的全部筛选参数
- 空数据返回 `40002`（而非空文件）
- 列顺序与前端表格列对齐

### 结算单导入受控字段

仅暴露 `company_id` / `period_start` / `period_end` / `total_amount` / `discount_amount` / `invoice_no`（可选）：

- `status` 固定 `draft`，`is_auto_generated=False`（禁止导入端指定状态，规避绕过审批流程）
- `invoice_no` 缺省按系统规则生成：`INV-YYYYMMDD-{customer_id}-{4位随机码}`
- 明细（`detail_file_*` 等内部字段）不开放

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
| 计费规则冲突（package/single overlap） | 行级错误（由服务层 `create_pricing_rule` 抛出） |
| 导出无匹配数据 | `40002` |

---

## Good/Base/Bad Cases

- **Good**：下载模板 → 填 3 行合法数据 → 导入 → `{success_count: 3, error_count: 0}`，列表出现 3 条新记录
- **Base**：模板原样上传（仅示例行）→ 说明行被跳过，示例行按数据校验（可能 1 条行级错误，绝不出现"说明行"被当成数据的错误）
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
