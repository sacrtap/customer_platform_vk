# 批量为 7 个管理页面新增导入/导出功能

## Goal

参照客户管理页（`customers/Index.vue` + `routes/customers.py`）已有的导入/导出交互，为用户管理、标签管理、角色权限、行业类型、合作状态、ERP系统余额白名单 6 个页面新增 Excel 导入（模板下载 + dry_run 预检查 + 确认提交）与导出（按当前筛选条件生成 xlsx 下载）；API-Key 页因密钥不可逆仅新增导出。

## Requirements

### R1 统一交互（7 个页面）

- 导入走两段式：下载模板 → 选文件 → dry_run 预检查（返回 success_count/error_count/errors）→ 确认提交。
- 导出按当前筛选条件（剔除 page/page_size，上限 5 万条）后端生成 xlsx Blob 下载；超限时响应 `X-Truncated: true`，前端提示。
- 复用既有基建：`ImportModal.vue`（props 契约不变）、`useExportAction` composable、`types/index.ts` 的 `ImportResult`、`read_import_dataframe`。

### R2 通用基建（先建后用）

- `frontend/src/api/_excel.ts`：从 `billing.ts` 迁出 `importFile`/`fetchImportTemplate`，新增 `fetchExport`（120s 超时、blob 响应）；`billing.ts` 转出并 re-export 保持对外签名不变。
- `backend/app/utils/excel_export.py`：`excel_response(records, sheet_name, filename_prefix, total=None)`——DataFrame → xlsx → raw 响应，5 万条截断 + X-Truncated 头，空数据返回 40002。
- `backend/app/utils/excel_template.py`：`template_response(columns, filename)`——3 行模板（英文列名 / 中文说明「必填：/可选：」前缀 / 示例行），列宽 25。

### R3 权限码（13 个新码，四处同步）

- `seed.py` `ALL_PERMISSIONS` 追加 13 条 4 元组（tags/users/roles/industry_types/cooperation_statuses/balance_whitelist 各 import+export，api_keys 仅 export）。
- `tests/_test_data.py` `PERMISSION_ROWS` 同步（一致性测试强制）。
- `tests/integration/conftest.py` 权限注册列表 + `FULL_PERMISSIONS` 同步（否则集成测试 403）。
- 新建幂等补丁脚本 `scripts/fix_add_import_export_permissions.py`：存量库补权限码 + 关联超级管理员；预置角色（运营经理/销售经理）默认不授 import，按既有 export 惯例授予对应模块 export。
- 前端 `permissionGroups.ts` 的 `MODULE_NAME_MAP`/`MODULE_ORDER` 补新 module 中文映射（独立分组的展示前提）。

### R4 六个导入页面（行业类型/合作状态/标签/用户/角色/余额白名单）

- 每页三端点：`GET /export`（`*:export`）、`GET /import-template`（`*:import`，按 PLAN 决策带权限码，严于客户页先例）、`POST /import?dry_run=true`（`*:import`）。
- 统一契约：`read_import_dataframe` 解析（`asyncio.to_thread` 包裹）；行号 `int(idx)+2`；行级错误格式 `第{行号}行：...`；dry_run 返回 `errors[:50]` 且不落库不写审计不动缓存；正式返回 `errors[:10]`。
- 导入冲突策略：重复记录行级报错计入 error_count，不 upsert（与客户页一致）。
- 逐页必填列与列映射（详见 design.md 各节）。

### R5 用户管理 legacy 导入重写

- 中文表头 openpyxl 直读整段删除，改英文表头 + dry_run + `read_import_dataframe(file.body, "username")`。
- 保留行为：用户名查重、密码 ≥6、邮箱格式、角色按 name 解析（支持逗号分隔多角色）。
- 返回结构改为 `{success_count, error_count, errors[:10/50], dry_run?}`；权限码由 `users:create` 改为 `users:import`。
- 同步改写 `tests/unit/test_user_import.py`（英文表头 + dry_run 断言，保留查重/密码/角色解析行为断言）。

### R6 API-Key 仅导出

- `GET /api/v1/api-keys/export`（`api_keys:export`），复用 `_format_api_key` 脱敏；不提供导入（密钥服务端生成、不可逆）。

### R7 前端接线（7 页）

- 每页 `PageHeader #actions` 加导出按钮（`v-if="can(...)"` + `useExportAction`）；6 个导入页加导入按钮并挂载 `ImportModal`；API-Key 页不挂导入。
- 各 api 模块追加对应函数（`exportXxx`/`fetchXxxTemplate`/`importXxx`）。

## Acceptance Criteria

1. **权限一致性**：`pytest tests/unit/test_test_data_consistency.py` 通过；seed/_test_data/conftest 三处 13 个新码一致；补丁脚本对存量库幂等可重跑。
2. **端点行为**（每页 smoke）：模板下载 200 + xlsx；dry_run 预检合法行 `success_count` 正确、不落库；正式导入落库；重复导入报「已存在」行级错误；导出 200 + xlsx 且解析含数据；无权限 403。
3. **用户导入单测**：`pytest tests/unit/test_user_import.py` 通过（英文表头 + dry_run + 查重/密码/角色解析断言）。
4. **前端**：`npm run typecheck` 通过；7 页按钮按权限显隐；导入弹窗预检→确认→列表刷新闭环；API-Key 页无导入按钮。
5. **全量回归**：`pytest --cov-fail-under=50` 与 `npm run test` 通过。
6. **交付留痕**：验收边界与验证结果记录于本任务 `implement.md` 末尾。

## Constraints

- 平台硬规则：写操作在 `async with db_session.begin():` 内；新端点 `@auth_required` + `@require_permission`；Python 3.12.x；禁止 `int(str(x))` 解析 Excel 数值列（pandas float64 陷阱）。
- 不破坏现有调用方：`billing.ts` 对外导出签名不变；客户页端点不改；ERP 批量导入与 Excel 导入并存。
- 用户导入 legacy 端点允许重写（PLAN 已确认），单测同步改写。

## Notes

- 源计划：仓库根 `批量导入导出_PLAN.md`。
- 调研后对 PLAN 的修正见 `design.md`「与 PLAN 的差异处置」。
