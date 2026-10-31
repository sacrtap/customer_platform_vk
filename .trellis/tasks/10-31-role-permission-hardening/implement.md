# 角色权限页面权限配置排查与加固 — Implement

> 行号基于 2026-10-31 磁盘状态；实施时以符号名（路由路径/函数名）为准定位。
> 环境：仓库根目录；后端统一用 `backend/.venv/bin/python`。

## Phase 0 — 新权限码与种子同步机制

- [x] 0.1 `backend/scripts/seed.py`：`system:sync_schedule` 条目后追加 `("sync_tasks:manage", "管理同步任务", "创建/取消数据同步任务", "system")`（「定时同步配置」分组内）。
- [x] 0.2 `backend/scripts/seed.py`：新增 `--sync-permissions` 模式（argparse flag + `sync_permissions()` 函数）：ALL_PERMISSIONS upsert（get_or_create_permission 扩展为「存在则更新 name/description/module」）；超级管理员角色幂等关联全部权限；commit 后失效 `cache:permissions:*`（复用文件尾部现有失效代码路径）。
- [x] 0.3 `backend/tests/_test_data.py`：`PERMISSION_ROWS` 的 `("system:view", ...)` 后追加 `("sync_tasks:manage", "管理同步任务", "system")`。
- [x] 0.4 验证：`.venv/bin/python -m pytest tests/unit/test_test_data_consistency.py -q` 绿。

## Phase 1 — 后端 API 权限补齐（P0）

- [x] 1.1 `backend/app/routes/analytics.py`：26 个端点 `@auth_required` 下追加 `@require_permission("analytics:view")`（trend/top/device-distribution/payment:analysis,trend,invoice-status/health:stats,warning-list,inactive-list/profile:industry,scale,consume-level,real-estate,real-estate-industry/prediction:monthly,trend/consumption:forecast,forecast-trend,data-readiness,price-config(GET)/profile:cross-dimension,tag-usage/health:risk-trend/payment:forecast-vs-actual,top-customers/forecast:monthly-compare）。
- [x] 1.2 同文件 3 个客户详情上下文端点追加 `@require_permission("customers:view")`：`/health/customers/<customer_id:int>/score`、`/billing/trend/<customer_id:int>`、`/usage/daily`。
- [x] 1.3 同文件 `POST /consumption/sync` 追加 `@require_permission("sync_tasks:manage")`。
- [x] 1.4 `backend/app/routes/sync_tasks.py`：list/stats/get_sync_task/progress/details → `system:view`；create_sync_task/cancel_sync_task → `sync_tasks:manage`；get_sync_status 保持。
- [x] 1.5 `backend/app/routes/sync_logs.py`：get_sync_logs、get_sync_stats → `system:view`。
- [x] 1.6 import-template 补权限：customers.py `download_import_template`→`customers:import`；billing/imports.py→`billing:balance_import`；billing/invoices.py→`billing:invoice_import`；billing/packages.py→`billing:package_import`；billing/pricing.py→`billing:pricing_import`。
- [x] 1.7 `backend/app/routes/customers.py`：get_customer_summary/get_customer_related/get_balance_forecast → `customers:view`；POST /follow-up → `customers:edit`。
- [x] 1.8 `backend/app/routes/roles.py` update_role：删 `permission_ids` 传参与 docstring 字段说明；`backend/app/services/roles.py` update_role：删 `permission_ids` 参数及「更新权限」分支。
- [x] 1.9 `backend/app/routes/users.py` assign_roles：success 判定后、审计日志前，加 `await permission_cache.invalidate(user_id)`。
- [x] 1.10 验证：`cd backend && .venv/bin/python -m pytest tests/unit/ -q` 全绿；`ruff check app/` 0 error。

## Phase 2 — 前端权限控制补齐（P1）

- [x] 2.1 `frontend/src/views/analytics/Forecast.vue`：「预测参数」按钮加 `v-if="can('analytics:forecast_edit')"`；script 补 useUserStore + can 定义（若缺）。
- [x] 2.2 `frontend/src/views/analytics/Consumption.vue`：10 行与 26 行两个同步按钮加 `v-if="can('sync_tasks:manage')"`；script 补 can 定义（若缺）。
- [x] 2.3 `frontend/src/api/analytics.ts`：新增 `exportHealthWarningList(params?)`（GET `/analytics/health/export`，blob + LONG_RUNNING_REQUEST_TIMEOUT）；`Health.vue` 余额预警 table-header 刷新按钮旁加导出按钮 `v-if="can('analytics:export')"`，点击触发下载；补 can 定义（若缺）。
- [x] 2.4 `AppSidebar.vue`：billing 父级 div.nav-parent + subnav 4 按钮加 `v-if="can('billing:view')"`；analytics 父级 + subnav 5 按钮加 `v-if="can('analytics:view')"`。`useAppLayout.ts` navSections：billing 4 子项与 analytics 5 子项补 permission 字段。
- [x] 2.5 `frontend/src/views/users/Index.vue`：重置密码 a-button 加 `v-if="can('users:edit')"`。
- [x] 2.6 InvoiceLogs 对齐 `billing:detail_status_view`：`router/index.ts:189` meta + `useAppLayout.ts:136` navSections（AppSidebar 无该按钮，见 design 偏差 #4）。
- [x] 2.7 验证：`cd frontend && npx vue-tsc --noEmit`（或 package.json 的 type-check 命令）0 error；`npx vitest run` 全绿。

## Phase 3 — 角色权限页面增强（P1）

- [x] 3.1 `frontend/src/views/roles/permissionGroups.ts`：新增 `filterPermissionsByKeyword(permissions, keyword)`；`__tests__/permissionGroups.test.ts` 补 5 用例（空 keyword 全量 / code 子串 / name 匹配 / 大小写混合 / 无匹配空）。
- [x] 3.2 `frontend/src/views/roles/Index.vue` 权限弹窗：顶部加搜索 a-input（placeholder「搜索权限名称/编码」，allow-clear，v-model permissionKeyword）；permissionGroups computed 先过滤后分组；权限项 name 下方加 `<span class="permission-code">{{ permission.code }}</span>`（12px muted）；分组标题旁「已选 x/y」（现有 count 文案保留或增强为已选视角）；新增 `DANGEROUS_PERMISSION_CODES` 常量，命中项 `permission-item--dangerous`（warning 左边框）+ a-tooltip「高危权限，请谨慎授予」；validPermIds 过滤逻辑不变。
- [x] 3.3 验证：`npx vitest run` 全绿；type-check 0 error。

## Phase 4 — 防漂移与语义澄清（P2）

- [x] 4.1 新增 `backend/tests/unit/test_permission_drift.py`：A=seed ALL_PERMISSIONS codes（延迟 import）；B=正则扫 `backend/app/**/*.py` 的 `require_permission("...")` 字面量；C=正则扫 `frontend/src/**/*.{vue,ts}` 的 `can('...')`/`hasPermission('...')`/`requiresPermission: '...'`；断言 B⊆A、C⊆A，失败列缺失 code + 文件:行号。根路径 `Path(__file__).resolve().parents[2]`。
- [x] 4.2 `backend/app/middleware/auth.py` `_check_permission`：manage 包含集改 `["view", "create", "edit", "delete", "read", "write", "update"]`，docstring（218-219 行附近）同步；删 `system:audit_read` 死分支（289-292 行）及 docstring 对应行。
- [x] 4.3 `.trellis/spec/backend/` 新增 `permission-model.md`（事实源/三层引用/上线流程/白名单/高危清单），并更新 `.trellis/spec/backend/index.md` Pre-Development Checklist 加入该文档链接。
- [x] 4.4 drift 变异验证：临时加 `@require_permission("fake:perm")` → 必须失败并指出文件；撤销。临时从 seed.py 删一个被引用 code → 必须失败；撤销。
- [x] 4.5 全量验证：`cd backend && .venv/bin/python -m pytest tests/unit/ -q`；集成（环境允许时）`tests/integration/test_analytics_api.py tests/integration/test_customers_api.py tests/integration/test_roles_api.py tests/integration/test_admin_import_export_api.py -q`；`ruff check app/`；`cd frontend && npx vitest run`。

## Phase 5 — 端到端与收尾

- [x] 5.1 起本地后端+前端，双 token 验证（PRD 验收 4/5/6 全部条目；环境不允许时明确记录限制与已完成的替代验证）。
- [x] 5.2 浏览器实操（运营经理登录）：消耗分析无「数据同步」/「手动同步」；Forecast 无「预测参数」；Health 有「导出」；仅 customers:view 角色的侧边栏无结算管理/客户分析组；角色权限页搜索「view_all」剩 1 项、system:database_clear 有高危标识。
- [x] 5.3 更新 `.trellis/spec/backend/permission-model.md`（若实施中发现新事实）；journal 记录；commit（按逻辑拆分）；PR。

## 验证记录

（实施中填写）
