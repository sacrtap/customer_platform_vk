# 批量为 7 个管理页面新增导入/导出功能

## Context

在用户管理、标签管理、角色权限、行业类型、合作状态、ERP系统余额白名单、API-Key 共 7 个页面中，参照客户管理页（`customers/Index.vue` + `routes/customers.py`）已有的导入/导出交互，增加对应的 Excel 导入与导出功能。

交互统一参照客户管理页：导入走「下载模板 → 选文件 → dry_run 预检查（返回 success_count/error_count/errors）→ 确认提交」两段式；导出走「按当前筛选条件（剔除 page/page_size）后端生成 xlsx Blob 下载」。

**已确认决策**：
- 用户管理已有 legacy 导入端点（中文表头、无 dry_run、无模板、无前端接线、单测 `test_user_import.py` 锁定旧格式）→ **升级为新模式**（英文表头+模板+dry_run），同步改写单测。
- API-Key 密钥由服务端生成、key_hash 存储、明文仅创建时展示一次，导入语义不成立 → **API-Key 只做导出，不做导入**。
- 导入冲突策略：重复记录直接报错计入 error_count，不 upsert（与客户页一致）。
- 导出范围：按当前筛选条件导出（剔除分页参数，上限 5 万条），与客户页一致。

**最终态**：6 个页面（用户/标签/角色/行业类型/合作状态/余额白名单）各新增导入+导出；API-Key 仅新增导出。共 6 个导入端点 + 7 个导出端点 + 6 个模板下载端点。前端 7 个页面均加导出按钮，6 个页面加导入按钮并挂载通用导入弹窗。

## 统一架构（所有页面共用，先建后用）

### 复用的现有基建（无需新建）

| 设施 | 路径 | 用途 |
|---|---|---|
| 通用导入弹窗 | `frontend/src/views/billing/components/ImportModal.vue` | props `{visible, title, importApi:(file,dryRun?)=>Promise<{data:ImportResult}>, templateApi:()=>Promise<{data:Blob}>, templateFileName}`，已含预检查/确认/文件校验/状态重置 |
| 导出 composable | `frontend/src/composables/useExportAction.ts` | `{exporting, run}`，Blob 下载+延迟 revoke+异常复位 |
| ImportResult 类型 | `frontend/src/types/index.ts:276` | `{success_count, error_count, errors:string[], dry_run?:boolean}` |
| Excel 解析工具 | `backend/app/utils/excel_import.py` `read_import_dataframe(body, first_column)` | pandas+openpyxl 读取，剥离模板说明行，行号对齐（第 i 行数据=Excel 第 i+2 行） |
| importFile/fetchImportTemplate 助手 | `frontend/src/api/billing.ts:18-27` | 参考写法（不手设 Content-Type、120s 超时、blob 响应） |

### 步骤 0a：提取通用 API 助手到共享位置

`billing.ts` 的 `importFile`/`fetchImportTemplate` 是 `billing` 模块私有。新建 `frontend/src/api/_excel.ts`（下划线前缀表内部共享），将这两个函数与 `LONG_RUNNING_REQUEST_TIMEOUT` 常量迁入，`billing.ts` 改为 `import { importFile, fetchImportTemplate } from './_excel'` 转出（保持 billing.ts 现有导出不变，避免破坏 3 个计费页调用方）。

```ts
// frontend/src/api/_excel.ts（新文件）
import api from './index'

const LONG_RUNNING_REQUEST_TIMEOUT = 120000

export function importFile(url: string, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post(url, formData, { timeout: LONG_RUNNING_REQUEST_TIMEOUT })
}

export function fetchImportTemplate(url: string) {
  return api.get(url, { responseType: 'blob' })
}

export function fetchExport(url: string, params?: Record<string, unknown>) {
  return api.get(url, { params, responseType: 'blob', timeout: LONG_RUNNING_REQUEST_TIMEOUT })
}
```

`billing.ts` 删除原 18-27 行的本地定义，改为 `import { importFile, fetchImportTemplate, fetchExport } from './_excel'` 并 re-export（保持 billing.ts 对外签名不变）。`fetchExport` 新增，统一导出请求（含 120s 超时）。

### 步骤 0b：新增权限码（seed + 测试数据 + 补丁脚本）

在 `backend/scripts/seed.py` 的 `ALL_PERMISSIONS`（:44-149）对应模块段追加权限码（4 元组 `(code, name, description, module)`）：

```
# 标签管理段（:89 后追加）
("tags:import", "导入标签", "批量导入标签", "tags"),
("tags:export", "导出标签", "导出标签数据", "tags"),
# 用户管理段（:97 后追加）
("users:import", "导入用户", "批量导入用户", "users"),
("users:export", "导出用户", "导出用户数据", "users"),
# 角色权限段（:105 后追加）
("roles:import", "导入角色", "批量导入角色", "roles"),
("roles:export", "导出角色", "导出角色数据", "roles"),
# 行业类型段（:119 追加，module 改为 "industry_types" 以便权限页分组）
("industry_types:import", "导入行业类型", "批量导入行业类型", "industry_types"),
("industry_types:export", "导出行业类型", "导出行业类型数据", "industry_types"),
# 合作状态段（:123 追加）
("cooperation_statuses:import", "导入合作状态", "批量导入合作状态", "cooperation_statuses"),
("cooperation_statuses:export", "导出合作状态", "导出合作状态数据", "cooperation_statuses"),
# 余额白名单段（:131 追加）
("balance_whitelist:import", "导入余额白名单", "批量导入余额白名单", "balance_whitelist"),
("balance_whitelist:export", "导出余额白名单", "导出余额白名单数据", "balance_whitelist"),
# API-Key 段（:135 追加，仅导出）
("api_keys:export", "导出API-Key", "导出API-Key列表", "api_keys"),
```

**注意 module 归属**：现有 `industry_types:manage`/`cooperation_statuses:manage`/`balance_whitelist:manage`/`api_keys:manage` 的 module 是 `"system"`。新增的 import/export 权限 module 改为各模块自身名（如 `"industry_types"`），使权限配置页（`frontend/src/views/roles/permissionGroups.ts` 按 module 分组）独立成组。`permissionGroups.ts` 无需改动——它按 `permission.module` 动态分组。

**同步 `backend/tests/_test_data.py`** 的 `PERMISSION_ROWS`（:15-65，3 元组 `(code, name, module)`）追加对应 13 条，module 与 seed.py 一致。这是硬要求——`tests/unit/test_test_data_consistency.py` 会校验 seed.py 与 PERMISSION_ROWS 的 code 集合一致，不同步则 CI 失败。

**新建幂等补丁脚本** `backend/scripts/fix_add_import_export_permissions.py`，仿 `scripts/fix_add_view_all_permission.py`（:1-108）结构：
- 读取上述 13 条权限码（建议从 seed.py import `ALL_PERMISSIONS` 过滤 code 含 `_import`/`_export` 后缀的条目，避免硬编码漂移）
- 对每条 `INSERT ... ON CONFLICT (code) DO NOTHING`
- 全部关联到超级管理员角色（`SUPER_ADMIN_ROLE_NAME`，仿 :66-98 的 role_permissions 幂等关联）
- 预置角色（运营经理/销售经理）默认不授导入权限（导入是管理操作），但授予各模块的 export 权限（与现有 `billing:*_export` 授予运营/销售经理一致）—— 在补丁脚本中对运营经理追加 7 个 export 权限码关联，对销售经理追加 `tags:export`/`users:export`/`roles:export`/`balance_whitelist:export`（与现有销售经理已有 `billing:*_export` 对齐）

### 步骤 0c：后端通用导出响应构造器（可选，减少重复）

客户导出端点（`routes/customers.py:1649-1666`）的 `pd.DataFrame(data).to_excel(...) → raw(output.read(), content_type=XLSX_MIME, headers={Content-Disposition})` 模式会在 7 个导出端点重复。新建 `backend/app/utils/excel_export.py`：

```python
# backend/app/utils/excel_export.py（新文件）
import io
from datetime import datetime
from sanic.response import raw

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

def excel_response(records: list[dict], sheet_name: str, filename_prefix: str):
    """records → DataFrame → xlsx → raw 响应。上限 50000 条，超出截断。"""
    import pandas as pd
    truncated = len(records) > 50000
    df = pd.DataFrame(records[:50000])
    output = io.BytesIO()
    df.to_excel(output, index=False, sheet_name=sheet_name, engine="openpyxl")
    output.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    headers = {"Content-Disposition": f'attachment; filename="{filename_prefix}_{ts}.xlsx"'}
    if truncated:
        headers["X-Truncated"] = "true"
    return raw(output.read(), content_type=XLSX_MIME, headers=headers)
```

客户导出端点不强制改用（保持现状，避免回归），仅新端点使用。

### 步骤 0d：后端通用模板生成器

客户模板端点（`routes/customers.py:1337+`）用 openpyxl 手工建 3 行（英文列名→中文说明→示例）。新建 `backend/app/utils/excel_template.py`：

```python
# backend/app/utils/excel_template.py（新文件）
import io
from openpyxl import Workbook
from sanic.response import raw

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

def template_response(
    columns: list[tuple[str, str, str]],
    filename: str,
    sheet_name: str = "导入模板",
):
    """columns: [(英文字段名, 中文说明含「必填：/可选：」前缀, 示例值), ...]
    生成 3 行：英文列名行 / 中文说明行 / 示例行，列宽 25。"""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    for i, (en, cn, example) in enumerate(columns, start=1):
        ws.cell(row=1, column=i, value=en)
        ws.cell(row=2, column=i, value=cn)
        ws.cell(row=3, column=i, value=example)
        ws.column_dimensions[chr(64 + i) if i <= 26 else None].width = 25
    # 列宽统一设置（避免多字母列名 chr 限制）
    from openpyxl.utils import get_column_letter
    for i in range(1, len(columns) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 25
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return raw(
        output.read(),
        content_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

## 各页面实现步骤

每个页面遵循统一模式，仅数据模型与列映射不同。下面按页面给出：后端端点签名、Excel 列定义（模板+导入+导出共用列序）、列映射逻辑、前端接线。

### 页面 1：行业类型（`industry_type_routes.py` + `system/IndustryTypes.vue`）

**模型字段**（`models/industry_type.py`）：`id`(int PK)、`name`(str unique ≤50)、`sort_order`(int 默认0)。

**后端端点**（`backend/app/routes/industry_type_routes.py`，bp `/api/v1/industry-types`）：
- `GET /export` — `@require_permission("industry_types:export")`。无筛选参数（列表本身无分页/筛选），调 `service.get_all()` 全量，转 dict 列表，`excel_response(records, "行业类型", "industry_types")`。
- `GET /import-template` — `@require_permission("industry_types:import")`。`template_response(columns, "行业类型导入模板.xlsx")`。
- `POST /import` — `@require_permission("industry_types:import")`，支持 `?dry_run=true`。
  - `read_import_dataframe(file.body, "name")`
  - 必填列 `["name"]`；`sort_order` 缺省 0
  - 逐行：`service.get_by_name(name)` 存在则 `errors.append(f"第{row_num}行：行业类型 '{name}' 已存在")`；否则构造 `{name, sort_order}`，`service.create(name, sort_order)`
  - dry_run 返回 `{dry_run, success_count, error_count, errors[:50]}`；正式返回 errors[:10]
  - 全部写入在 `async with db_session.begin():` 内

**Excel 列**（模板 3 行：英文/说明/示例）：
| 英文字段 | 中文说明 | 示例 |
|---|---|---|
| name | 必填：行业类型名称（≤50，不可重复） | 房产经纪 |
| sort_order | 可选：排序序号，缺省 0 | 1 |

**前端**（`system/IndustryTypes.vue`）：
- `PageHeader #actions`（:4-8）内在「新增」按钮前加：
  - `<a-button v-if="can('industry_types:export')" :loading="exporting" @click="handleExport">导出</a-button>`
  - `<a-button v-if="can('industry_types:import')" @click="importVisible = true">导入</a-button>`
- script setup 内：`const { exporting, run } = useExportAction({ exportApi: exportIndustryTypes, filename: () => 'industry_types_'+date+'.xlsx' })`；`handleExport = () => run(undefined)`（无筛选参数）
- 挂载 `<ImportModal v-model:visible="importVisible" title="批量导入行业类型" :import-api="importIndustryTypes" :template-api="fetchIndustryTypeTemplate" template-file-name="行业类型导入模板.xlsx" @success="loadIndustryTypes" />`
- `api/industryTypes.ts` 追加：`exportIndustryTypes()`（`fetchExport('/industry-types/export')`）、`fetchIndustryTypeTemplate()`（`fetchImportTemplate('/industry-types/import-template')`）、`importIndustryTypes(file, dryRun)`（`importFile('/industry-types/import'+(dryRun?'?dry_run=true':''), file)`）

### 页面 2：合作状态（`cooperation_status_routes.py` + `system/CooperationStatuses.vue`）

**模型字段**（`models/cooperation_status.py`）：`id`、`name`(展示名 unique ≤50)、`value`(存储值 unique)、`sort_order`(int 默认0)。

**后端端点**（`backend/app/routes/cooperation_status_routes.py`，bp `/api/v1/cooperation-statuses`）：与行业类型完全对称，三端点 `GET /export`、`GET /import-template`、`POST /import?dry_run=true`。
- 导入必填列 `["name", "value"]`；`sort_order` 缺省 0
- 重复检查：`service.get_by_name(name)` 或按 value 查存在则报错
- 权限码 `cooperation_statuses:export`/`cooperation_statuses:import`

**Excel 列**：
| 英文字段 | 中文说明 | 示例 |
|---|---|---|
| name | 必填：合作状态展示名（≤50，不可重复） | 合作中 |
| value | 必填：合作状态存储值（不可重复） | active |
| sort_order | 可选：排序序号，缺省 0 | 1 |

**前端**（`system/CooperationStatuses.vue`，:4-8 actions）：同行业类型模式。`api/cooperationStatuses.ts` 追加三函数。

### 页面 3：标签管理（`tags.py` + `tags/Index.vue`）

**模型字段**（`models/tags.py`）：`id`、`name`(≤50)、`type`('customer'/'profile')、`category`(≤50 可空)、`created_by`(FK users.id)。唯一约束 `(name, type)`。

**后端端点**（`backend/app/routes/tags.py`，bp `/api/v1/tags`）：
- `GET /export` — `@require_permission("tags:export")`，Query `type`(可选)。调 `service.get_all_tags(page=1, page_size=50000, tag_type=type)`，转 dict 列表（含 type 中文名：customer→客户标签/profile→画像标签），`excel_response`。
- `GET /import-template` — `@require_permission("tags:import")`。模板示例行 type 填 `customer`。
- `POST /import?dry_run=true` — `@require_permission("tags:import")`。
  - 必填列 `["name", "type"]`；type 必须是 `customer`/`profile`，否则报错
  - 重复检查：`service.get_tag_by_name_and_type(name, type)` 存在则报错
  - `category` 可空；`created_by` 取 current_user.id
  - 落库 `service.create_tag(...)` 或直接 `db.add(Tag(...))`，在 `async with db_session.begin():` 内

**Excel 列**：
| 英文字段 | 中文说明 | 示例 |
|---|---|---|
| name | 必填：标签名称（≤50） | 重点客户 |
| type | 必填：标签类型，仅 customer 或 profile | customer |
| category | 可选：标签分类 | 优先级 |

**前端**（`tags/Index.vue`，:4-6 actions 内「新建标签」前加导入/导出按钮）。导出按当前 activeTab 传 `type` 参数（`run({ type: activeTab.value })`）。`api/tags.ts` 追加三函数。导入弹窗 `@success="loadTags"`。

### 页面 4：用户管理（`users.py` + `users/Index.vue`）—— 升级 legacy 导入

**模型字段**（`models/users.py` User）：`username`(unique)、`email`、`real_name`、`is_active`、`phone`、`password_hash`。导入涉及：username、email、real_name、role（按 name 解析）、初始密码。

**后端**（`backend/app/routes/users.py`，bp `/api/v1/users`）：
- **重写 `POST /import`**（:407-636 现有 legacy）：改为英文表头 + dry_run + 模板说明行剥离（`read_import_dataframe(file.body, "username")`）。必填列 `["username", "initial_password"]`；role 按 name 解析（已有逻辑 :526-532）；保留现有校验（密码≥6、邮箱格式、用户名查重 `service.get_user_by_username`）。返回格式改为 `{success_count, error_count, errors[:10/50], dry_run?}`。权限码改为 `users:import`。
- **新增 `GET /import-template`** — `@require_permission("users:import")`，`template_response`。
- **新增 `GET /export`** — `@require_permission("users:export")`，Query `keyword`。调 `service.get_all_users(page=1, page_size=50000, keyword)`，导出列含 id/username/email/real_name/is_active/roles(逗号拼接 name)/phone/created_at。`excel_response`。
- **删除旧 legacy 的中文表头逻辑**（:461-482 openpyxl 直读 + 中文列名 index）。

**Excel 列**：
| 英文字段 | 中文说明 | 示例 |
|---|---|---|
| username | 必填：用户名（唯一） | zhangsan |
| email | 可选：邮箱 | zhang@abc.com |
| real_name | 可选：真实姓名 | 张三 |
| role | 可选：角色名（多个用逗号分隔） | 运营经理 |
| initial_password | 必填：初始密码（≥6 位） | Abc12345 |

**前端**（`users/Index.vue`，:4-17 actions 内搜索框后、「新建用户」前加导入/导出按钮）。导出传 `keyword`。`api/users.ts` 追加 `importUsers`/`exportUsers`/`fetchUserTemplate` 三函数。

**改写单测**：`backend/tests/unit/test_user_import.py`（219 行）从中文表头改为英文表头 + dry_run 断言。保留对用户名查重、密码校验、角色解析的行为断言，仅调整输入文件构造与响应字段名。

### 页面 5：角色权限（`roles.py` + `roles/Index.vue`）

**模型字段**（`models/users.py` Role）：`name`(unique)、`description`(≤200)、`is_system`、`permissions`(M2M via role_permissions)。

**后端**（`backend/app/routes/roles.py`，bp `/api/v1/roles`）：
- `GET /export` — `@require_permission("roles:export")`，Query `keyword`。调 `service.get_all_roles(page=1, page_size=50000)`（需补 keyword 过滤或前端导出不传 keyword 全量导出——本计划取全量导出，因 roles 数据量小）。导出列含 id/name/description/is_system/permissions(逗号拼接 code)。`excel_response`。
- `GET /import-template` — `@require_permission("roles:import")`。
- `POST /import?dry_run=true` — `@require_permission("roles:import")`。
  - 必填列 `["name"]`；`permissions` 列为逗号分隔的 permission code（如 `customers:view,customers:create`）
  - 逐行解析 permission code → 查 Permission.code，不存在则报错 `f"权限码 '{code}' 不存在"`
  - `service.get_role_by_name(name)` 存在则报错；否则 `service.create_role(name, description, permission_ids)`
  - `is_system` 列忽略（导入不可创建系统角色，强制 False）

**Excel 列**：
| 英文字段 | 中文说明 | 示例 |
|---|---|---|
| name | 必填：角色名（唯一） | 客户专员 |
| description | 可选：角色描述 | 负责客户日常维护 |
| permissions | 可选：权限码，逗号分隔 | customers:view,customers:edit |

**前端**（`roles/Index.vue`，:4-17 actions）：导出全量（无参数）。`api/roles.ts` 追加三函数。

### 页面 6：ERP余额白名单（`balance_whitelist_routes.py` + `system/BalanceWhitelist.vue`）

**模型字段**（`models/balance_whitelist.py`）：`customer_id`(unique FK customers.id)、`static_balance`(Decimal(12,2) 默认1000)、`remark`(≤200)。列表 JOIN Customer 展示 company_id/customer_name/erp_system。

**后端**（`backend/app/routes/balance_whitelist_routes.py`，bp `/api/v1/balance-whitelists`）：
- `GET /export` — `@require_permission("balance_whitelist:export")`，Query `keyword`。调 `service.get_all(page=1, page_size=50000, keyword=keyword)`，导出列含 id/company_id/customer_name/erp_system/static_balance/remark/created_at。`excel_response`。
- `GET /import-template` — `@require_permission("balance_whitelist:import")`。
- `POST /import?dry_run=true` — `@require_permission("balance_whitelist:import")`。
  - 必填列 `["company_id"]`；`static_balance` 缺省 1000；`remark` 可空
  - company_id → customer.id 解析（参考 `routes/customers.py:1168-1225` 同款逻辑）：查 `Customer.company_id == company_id and deleted_at is None`，不存在报错
  - 重复检查：按 customer_id 查 BalanceWhitelist 已存在（含软删恢复）→ 报错（不 upsert，与冲突策略一致）
  - 落库 `db.add(BalanceWhitelist(customer_id=..., static_balance=..., remark=...))`，在 `async with db_session.begin():` 内
  - **不替代现有 `POST /batch-import`（按 ERP 批量导入）**——两者并存，Excel 导入按 company_id 精确导入

**Excel 列**：
| 英文字段 | 中文说明 | 示例 |
|---|---|---|
| company_id | 必填：客户编号 | 1001 |
| static_balance | 可选：静态余额，缺省 1000 | 5000.00 |
| remark | 可选：备注 | VIP客户 |

**前端**（`system/BalanceWhitelist.vue`，:8-15 actions，在「按 ERP 批量导入」按钮前加 Excel 导入/导出按钮）。导出传 `keyword`。`api/balanceWhitelist.ts` 追加三函数（`importBalanceWhitelist`/`exportBalanceWhitelist`/`fetchBalanceWhitelistTemplate`）。导入弹窗 `@success="loadList"`。

### 页面 7：API-Key（`api_keys.py` + `system/ApiKeyManagement.vue`）—— 仅导出

**模型字段**（`models/api_key.py`）：`name`(≤100)、`key_prefix`(16)、`key_hash`(unique)、`status`(active/disabled)、`description`、`created_by`、`expires_at`、`last_used_at`。**无导入**（密钥不可逆）。

**后端**（`backend/app/routes/api_keys.py`，bp `/api/v1/api-keys`）：
- `GET /export` — `@require_permission("api_keys:export")`，无筛选（列表仅分页）。调 `service.get_all(page=1, page_size=50000)`，导出列含 id/name/key_prefix（已脱敏，拼接 `****`）/status/description/created_by/expires_at/last_used_at/created_at。`excel_response`。

**前端**（`system/ApiKeyManagement.vue`，:4-8 actions 内「申请 API-Key」前加）：
- `<a-button v-if="can('api_keys:export')" :loading="exporting" @click="handleExport">导出</a-button>`
- script：`useExportAction({ exportApi: exportApiKeys, filename: () => 'api_keys_'+date+'.xlsx' })`
- `api/apiKeys.ts` 追加 `exportApiKeys()`（`fetchExport('/api-keys/export')`）
- **不挂载 ImportModal**，不加导入按钮

## Critical Files & Anchors

1. **`backend/app/routes/customers.py:1474-1666`** — 导出端点完整参考（filters 构造、df.to_excel、raw 响应、X-Truncated 头），所有新导出端点的模板。
2. **`backend/app/utils/excel_import.py`** `read_import_dataframe` — 所有新导入端点必用的 Excel 解析（说明行剥离+行号对齐），参数 `first_column` 传各表主英文字段名。
3. **`frontend/src/views/billing/components/ImportModal.vue:134-144`** — 通用导入弹窗 props 契约，6 个页面直接复用，无需新建组件。
4. **`backend/scripts/seed.py:44-149` + `backend/tests/_test_data.py:15-65`** — 权限码权威定义+测试一致性校验，13 个新权限码必须两处同步。
5. **`backend/app/routes/users.py:407-636`** — 唯一需重写（非新增）的 legacy 导入端点，改写时保留用户名查重/密码校验/角色解析行为，仅换表头格式与返回结构。

## Verification

**前置**：后端 venv 激活（`backend/.venv`），PostgreSQL 运行，执行补丁脚本 `python -m scripts.fix_add_import_export_permissions`（从 backend 目录）。

**1. 权限码一致性**（先跑，阻塞后续）：
```
cd backend && .venv/bin/python -m pytest tests/unit/test_test_data_consistency.py -v
```
预期：通过（seed.py 与 _test_data.py 的 code 集合一致）。

**2. 后端导入/导出端点 smoke**（每个页面一个脚本，以行业类型为例）：
```python
# throwaway: backend/scripts/_smoke_industry_import.py
# 1. 登录获取 token（admin）
# 2. GET /api/v1/industry-types/import-template → 断言 200 + content-type xlsx + body 非空
# 3. 用 openpyxl 构造测试 xlsx（1 行 name=测试行业 sort_order=5）→ POST /import?dry_run=true → 断言 {success_count:1, error_count:0}
# 4. POST /import（正式）→ 断言 success_count:1
# 5. 重复 POST /import 同文件 → 断言 error_count:1, errors 含"已存在"
# 6. GET /api/v1/industry-types/export → 断言 200 + xlsx + 解析含"测试行业"行
# 7. 清理：DELETE 该行业类型
```
对 6 个导入页面（行业类型/合作状态/标签/用户/角色/余额白名单）各跑一遍 smoke；对 API-Key 只跑导出部分。清理测试数据。

**3. 用户导入单测改写**：
```
cd backend && .venv/bin/python -m pytest tests/unit/test_user_import.py -v
```
预期：通过，断言英文表头解析 + dry_run 返回结构。

**4. 前端 UI 验证**（手动，7 个页面逐一）：
- 启动前端 dev server（`frontend/` 下 `npm run dev`）
- 以超管登录（超管已通过补丁脚本获得全部新权限码）
- 每个页面：点「导出」→ 下载 xlsx → 用 Excel/Numbers 打开确认列与数据正确
- 6 个导入页面：点「导入」→ 弹窗出现 → 点「下载模板」→ xlsx 下载 → 填入一行数据 → 选文件 → 点「预检查」→ 显示 success_count=1 → 点「确认导入」→ 列表刷新出现新记录 → 重复导入同文件 → 预检查显示 error_count=1 含"已存在"
- API-Key 页：确认只有「导出」按钮，无「导入」按钮

**5. 全量回归**：
```
cd backend && .venv/bin/python -m pytest --cov-fail-under=50
cd frontend && npm run test
cd frontend && npm run typecheck
```

## Assumptions & Contingencies

- **超管权限授予方式**：补丁脚本对已存在数据库补建权限码+超管关联。若目标库是全新空库，seed.py 初始化时自动建（补丁脚本幂等跳过）。两种情况都覆盖。
- **导出无 keyword 筛选的页面（行业类型/合作状态/API-Key）**：导出端点不接受 keyword 参数，直接全量。若后续需筛选导出，再加 query 参数，不影响当前实现。
- **角色导出的 keyword**：`get_all_roles` 现有签名无 keyword 参数。本计划角色导出取全量（数据量小，合理）。若需 keyword，需先给 `get_all_roles` 补 keyword 参数——但不在本计划范围。
- **余额白名单 Excel 导入与现有 ERP 批量导入并存**：两者不冲突（Excel 按 company_id 精确导入，ERP 批量按 erp_system 批量导入），前端保留两个按钮。
- **权限 module 归属变更**：新增 import/export 权限的 module 用各模块名（如 `industry_types`）而非沿用 manage 的 `system`，使权限配置页独立分组。若产品要求统一归到「系统管理」组，把 module 改回 `system` 即可，不影响功能。
- **若 `read_import_dataframe` 对某页面首列字段名不匹配**：first_column 参数仅用于行号对齐基准，传该表第一个英文字段名即可（如 users 传 `"username"`），不影响其他列解析。
