# 角色权限页面权限配置排查与加固计划

## Context

用户要求：详细排查「角色权限」页面背后的权限配置——所有页面及功能权限是否完善、有何优化建议，并用 codegraph 确认影响范围。本计划即排查结论 + 可执行的加固方案。预期终态：后端每个业务端点都有明确权限码（或明确判定为共享字典/自助端点并留注释），前端每个受控入口都有 `can()` 门，权限码在 seed / 后端引用 / 前端引用三处不漂移，角色权限页面支持搜索与高危标识。

### 排查结论（已核实，行号为当前磁盘状态）

权限体系：后端 Sanic `require_permission(code)`（`backend/app/middleware/auth.py:214`，通配匹配见 `_check_permission:255`）；前端路由 `meta.requiresPermission` + `userStore.hasPermission` + 模板 `v-if="can(...)"`；权限数据源 `backend/scripts/seed.py` `ALL_PERMISSIONS`（67 项）→ DB `permissions` 表 → 角色权限页 `GET /api/v1/permissions`（`backend/app/routes/permissions.py:16`，按 module 分组由 `frontend/src/views/roles/permissionGroups.ts` 渲染）。

**已完善的部分**：seed 67 项覆盖后端全部 23 个 `require_permission` 调用点；`customers:view_all` 数据可见性服务端强制（`customer_scope_user_id` fail-closed，`middleware/auth.py:176`）；权限分配后缓存并发失效（`routes/roles.py:258-264`）；主要 CRUD 按钮有 `can()` 控制；`tests/_test_data.py` + `test_test_data_consistency.py` 守护测试夹具 ⊆ seed。

**缺口清单**：

| # | 级别 | 缺口 | 位置 |
|---|------|------|------|
| 1 | P0 | 26 个分析类 GET 端点仅 `@auth_required`，任何登录用户可直调全部分析 API（消耗/回款/健康度/画像/预测/排行），仅 3 个端点有权限（`/dashboard/*` 与 `/priority-customers` 为首页专用，另有 scope 强制，不在此缺口） | `backend/app/routes/analytics.py` |
| 2 | P0 | `POST /analytics/consumption/sync` 无权限码，任何登录用户可触发 force_overwrite 全量同步 | `analytics.py:230` |
| 3 | P0 | sync_tasks 全部 8 端点无权限码，任何登录用户可创建/取消同步任务 | `backend/app/routes/sync_tasks.py` |
| 4 | P0 | sync_logs 2 端点无权限码 | `backend/app/routes/sync_logs.py:16,117` |
| 5 | P0 | 5 个 import-template 下载端点无权限码，与对应 import 权限不一致 | `customers.py:1337`、`billing/imports.py:277`、`billing/invoices.py:2213`、`billing/packages.py:787`、`billing/pricing.py:796` |
| 6 | P0 | 客户详情附属端点无权限码（有 scope 但无权限）：summary/related/balance-forecast GET、follow-up POST | `customers.py:1644,1699,1749,1803` |
| 7 | P0 | `PUT /roles/{id}` 支持 `permission_ids` 改权限但不失效缓存 → 最长 600s 延迟生效（`POST /{id}/permissions` 有失效） | `routes/roles.py:149-186` |
| 8 | P0 | `POST /users/{id}/roles` 分配角色后不 invalidate 权限缓存 | `routes/users.py:345` |
| 9 | P1 | analytics 5 页零按钮级控制；`analytics:export` 前端无入口（后端 `/analytics/health/export` 存在）；Forecast「预测参数」按钮无 `forecast_edit` 门 | `frontend/src/views/analytics/*` |
| 10 | P1 | 侧边栏 billing/analytics 菜单无 `can()` 过滤（系统管理组有） | `AppSidebar.vue`、`useAppLayout.ts` |
| 11 | P1 | users 页「重置密码」按钮无 `users:edit` 门（后端是该权限） | `views/users/Index.vue:73` |
| 12 | P1 | InvoiceLogs 路由用 `billing:view`，后端 API 是 `billing:detail_status_view`，码不匹配 | `router/index.ts` 等 3 处 |
| 13 | P1 | 角色权限页：47 项权限无搜索、不显示 code、高危权限无标识 | `views/roles/Index.vue` |
| 14 | P2 | 权限码三处副本（seed 67 / 测试 62 / 前端引用）只有单向守护（测试⊆seed），后端与前端引用无 drift 检查 | 新增测试 |
| 15 | P2 | `_check_permission` 通配语义与项目动作命名不符（`view/edit` 不在 manage 包含集）；`system:audit_read` 为死分支 | `middleware/auth.py:255-294` |
| 16 | P2 | 新权限码上线依赖 fix 脚本补 DB（历史 2 个 fix 脚本），无幂等同步入口 | `scripts/fix_add_*.py` |

### codegraph 影响范围确认（已执行）

- `require_permission` 23 callers、`auth_required` 25 callers、`get_current_user` 76 callers：中间件是单点，但本计划只加装饰器调用，不改中间件签名（`_check_permission` 语义澄清除外，见步骤 20，零行为变化）。
- `permission_cache.invalidate` 现有调用点：`routes/auth.py:120`（logout）、`routes/users.py:287`（delete_user）、`routes/roles.py:260`（assign_permissions）。本计划在 `routes/users.py` assign_roles 新增一处。
- `assign_permissions` 链路：`routes/roles.py:215` → `services/roles.py:130`（service 方法保留，仅 route 层入口调整）。
- sync 链路：`SyncTaskService.create_task` 13 callers（analytics.py / sync_tasks.py / tasks/scheduler.py）、`execute_task` 7 callers；前端 `SyncDialog`（唯一调用方 `Consumption.vue`）→ `createSyncTask` → `POST /sync-tasks`；`manual_sync_consumption → run_task → execute_task`。权限只加在 HTTP 入口，scheduler 内部调用不受影响。
- `update_role` 的 `permission_ids` 无任何前端传参、无测试覆盖（`test_roles_api.py` 只用 `POST /roles` 与 `POST /{id}/permissions`），删除安全。

## Approach

按 Phase 顺序执行；每 Phase 结束后跑对应验证。所有「加权限」均为在现有 `@auth_required` 下方追加一行 `@require_permission("...")`，与文件内既有端点风格一致。

### Phase 0 — 新权限码与种子同步机制

1. `backend/scripts/seed.py`：在 `ALL_PERMISSIONS` 的「定时同步配置」条目后追加 `("sync_tasks:manage", "管理同步任务", "创建/取消数据同步任务", "system")`（module 用 `system`，同步任务属系统运维操作）。
2. `backend/scripts/seed.py`：新增 `--sync-permissions` 命令行模式（argparse flag）。行为：对 `ALL_PERMISSIONS` 逐条 upsert `permissions` 表——按 `code` 查询，存在则更新 `name/description/module`，不存在则插入（复用文件内已有 `get_or_create_permission` 的模式）；随后查询「超级管理员」角色，将其关联至全部权限（幂等：已关联跳过）。不做任何删除，不触碰预置业务角色关联。该模式是未来新权限码上线的唯一入口，替代 fix 脚本模式。
3. `backend/tests/_test_data.py`：`PERMISSION_ROWS` 追加 `("sync_tasks:manage", "管理同步任务", "system")`（置于 `("system:view", ...)` 之后），使 `test_test_data_consistency.py` 继续通过。

### Phase 1 — 后端 API 权限补齐（P0）

4. `backend/app/routes/analytics.py`：
   - 以下 26 个端点在 `@auth_required` 下追加 `@require_permission("analytics:view")`：`/consumption/trend`(26)、`/consumption/top`(107)、`/consumption/device-distribution`(167)、`/payment/analysis`(330)、`/payment/trend`(388)、`/payment/invoice-status`(443)、`/health/stats`(501)、`/health/warning-list`(525)、`/health/inactive-list`(553)、`/profile/industry`(619)、`/profile/scale`(644)、`/profile/consume-level`(669)、`/profile/real-estate`(694)、`/profile/real-estate-industry`(719)、`/prediction/monthly`(744)、`/prediction/trend`(789)、`/consumption/forecast`(816)、`/consumption/forecast-trend`(888)、`/consumption/data-readiness`(929)、`/consumption/price-config` GET(960)、`/profile/cross-dimension`(1277)、`/profile/tag-usage`(1314)、`/health/risk-trend`(1345)、`/payment/forecast-vs-actual`(1423)、`/payment/top-customers`(1447)、`/forecast/monthly-compare`(1477)。注意 `/priority-customers`(1522) 不在此列——见下条「有意保持」。
   - 3 个客户详情上下文端点追加 `@require_permission("customers:view")`：`/health/customers/<id>/score`(581)、`/billing/trend/<id>`(1152)、`/usage/daily`(1188)。理由：它们渲染在客户详情页（路由守卫即 `customers:view`），用 `analytics:view` 会误伤无分析权限的客户查看者。
   - `POST /consumption/sync`(230) 追加 `@require_permission("sync_tasks:manage")`。
   - **有意保持 `@auth_required` 不变**：`/dashboard/stats`(1010)、`/dashboard/todos`(1031)、`/dashboard/trend`(1082)、`/priority-customers`(1522)——首页 `Home.vue` 调用且首页路由无权限守卫，已有 `scope_user_id` 数据可见性强制（priority-customers 见 1540 行）；加权限会使全员首页「今日优先跟进客户」卡片/KPI 403 渲染失败。
5. `backend/app/routes/sync_tasks.py`：`list`(20)、`stats`(38)、`get_sync_task`(200)、`progress`(240)、`details`(295) 追加 `@require_permission("system:view")`（与同步日志页一致）；`create_sync_task`(92)、`cancel_sync_task`(265) 追加 `@require_permission("sync_tasks:manage")`；`get_sync_status`(52) **保持 `@auth_required`**（首页 `SyncStatusBar` 全员调用，只读同步健康摘要）。
6. `backend/app/routes/sync_logs.py`：`get_sync_logs`(16)、`get_sync_stats`(117) 追加 `@require_permission("system:view")`。
7. import-template 端点补权限：`customers.py:1337`→`customers:import`；`billing/imports.py:277`→`billing:balance_import`；`billing/invoices.py:2213`→`billing:invoice_import`；`billing/packages.py:787`→`billing:package_import`；`billing/pricing.py:796`→`billing:pricing_import`。前端导入按钮均已有对应 `can()` 门，无权限用户无入口，不会误伤。
8. `backend/app/routes/customers.py`：`GET /summary`(1644)、`GET /related`(1699)、`GET /balance-forecast`(1749) 追加 `@require_permission("customers:view")`；`POST /follow-up`(1803) 追加 `@require_permission("customers:edit")`（写操作，与客户编辑同权）。
9. `backend/app/routes/roles.py` `update_role`(149-186)：删除 `permission_ids` 支持——route 内 `data.get("permission_ids")` 传参与 docstring 中该字段说明一并删除。`backend/app/services/roles.py` `update_role`(72-113)：删除 `permission_ids` 参数及「更新权限」分支（98-108 行）。理由：权限分配收敛到唯一入口 `POST /roles/{id}/permissions`（该入口已有缓存失效），双入口必漏失效。`create_role` 的 `permission_ids` **保留**（`routes/roles.py:120` 与 import 使用，新角色无用户关联，无缓存问题）。
10. `backend/app/routes/users.py` `assign_roles`：`success` 判定后、审计日志前，追加 `await permission_cache.invalidate(user_id)`（`permission_cache` 已在文件头 18 行导入）。
11. **有意保持无权限码的端点**（防止实施者误改）：`routes/dict_routes.py`、`GET /industry-types`、`GET /cooperation-statuses`、`GET /erp-systems`（`industry_type_routes.py:26`、`cooperation_status_routes.py:28`、`erp_system_routes.py:15`）——共享字典数据源，被无 manage 权限的业务页面下拉消费（`useCustomerDict`/`useCustomerList`/`useBalance`/`EditCustomerDialog` 等 10+ 处），加 `:manage` 会打断普通运营经理的筛选与表单；管理能力由各写操作端点的 `:manage` 守。`POST /files/upload`（files.py:126）——减免附件上传属 `billing:edit` 流程（`api/billing.ts` `uploadDiscountAttachment`），`files:*` 只治理文件管理面，加权限会打断结算单提交。`GET /system/updates`（system.py:15）——首页部署公告全员可见。`users.py` 的 `/options`、`/profile`、`/password`、`/avatar`、`/me/preferences`——自助/共享下拉。以上如需收紧，应单独设计场景化权限，不在本计划。

### Phase 2 — 前端权限控制补齐（P1）

12. `frontend/src/views/analytics/Forecast.vue`：「预测参数」按钮（约 76 行 `openConfigModal` 的 `a-button`）加 `v-if="can('analytics:forecast_edit')"`；script setup 补 `import { useUserStore } from '@/stores/user'` 与 `const userStore = useUserStore(); const can = (p: string) => userStore.hasPermission(p)`（该文件当前无 can 定义）。
13. `frontend/src/views/analytics/Consumption.vue`：「数据同步」按钮（9 行，`handleSyncButtonClick`）加 `v-if="can('sync_tasks:manage')"`；script 补同样的 `can` 定义（`useUserStore` 是否已导入以实际文件为准，缺则补）。
14. `frontend/src/views/analytics/Health.vue` + `frontend/src/api/analytics.ts`：闭环 `analytics:export`——`api/analytics.ts` 新增 `exportHealthWarningList()`：GET `/analytics/health/export`，按文件内既有导出封装风格返回 blob（参照 `_excel.ts` 的 `fetchExport`）；`Health.vue` 「余额预警客户」table-header（110 行刷新按钮旁）加导出按钮 `v-if="can('analytics:export')"`，点击调用该 API 触发浏览器下载。补 `can` 定义同步骤 12。
15. `frontend/src/components/layout/AppSidebar.vue`：billing 父级 `div.nav-parent` 加 `v-if="can('billing:view')"`，其 subnav 内 4 个按钮各加 `v-if="can('billing:view')"`；analytics 父级 `div.nav-parent` 加 `v-if="can('analytics:view')"`，其 subnav 内 5 个按钮各加 `v-if="can('analytics:view')"`。同步 `frontend/src/composables/useAppLayout.ts` `navSections`：billing 4 个子项与 analytics 5 个子项补 `permission: 'billing:view'` / `'analytics:view'`（该数据的 children 过滤逻辑已存在，父级无可见子项时自动隐藏）。
16. `frontend/src/views/users/Index.vue`：「重置密码」a-button（73 行）加 `v-if="can('users:edit')"`。
17. InvoiceLogs 权限码三处对齐为 `billing:detail_status_view`：`frontend/src/router/index.ts` 路由 meta；`useAppLayout.ts` navSections `invoice-logs` 项 `permission`；`AppSidebar.vue` 对应按钮 `v-if`。预置角色（运营经理/销售经理 seed 均含该码）与超管不受影响。

### Phase 3 — 角色权限页面增强（P1）

18. `frontend/src/views/roles/permissionGroups.ts`：新增纯函数 `filterPermissionsByKeyword(permissions, keyword)`——对 `name` 与 `code` 做大小写不敏感 `includes` 匹配，keyword 为空返回原数组；`buildPermissionGroups` 不变。在 `__tests__/permissionGroups.test.ts` 补用例：空 keyword 返回全量、匹配 code 子串、匹配 name、大小写混合、无匹配返回空。
19. `frontend/src/views/roles/Index.vue` 权限配置弹窗：
    - 弹窗顶部（permission-header 区域）加 `a-input` 搜索框，placeholder「搜索权限名称/编码」，`allow-clear`，v-model 新 `ref` `permissionKeyword`；`permissionGroups` computed 改为先过滤后分组。
    - 权限项在 `permission-name` 下方追加 `<span class="permission-code">{{ permission.code }}</span>`（12px、muted 色，样式加在 `<style scoped>`）。
    - 分组标题旁追加「已选 x/y」计数（`selectedPermissionIds` 与该组交集）。
    - 新增模块级常量 `DANGEROUS_PERMISSION_CODES = ['system:database_clear', 'system:database_backup', 'sync_tasks:manage', 'customers:delete', 'users:delete', 'roles:delete', 'files:delete', 'billing:delete', 'erp_systems:manage', 'api_keys:manage']`，命中项在卡片左边框加 warning 色（`var(--warning)`，项目 CSS 变量已定义）并加 `a-tooltip` 内容「高危权限，请谨慎授予」。
    - 提交时的 `validPermIds` 数字过滤逻辑保持不变。

### Phase 4 — 防漂移与语义澄清（P2）

20. 新增 `backend/tests/unit/test_permission_drift.py`：静态扫描（无 DB、无网络）三个集合并断言包含关系——A = `scripts/seed.py` `ALL_PERMISSIONS` 的 code（延迟 import，同 `test_test_data_consistency.py` 避免模块级副作用）；B = 正则扫描 `backend/app/**/*.py` 中 `require_permission("...")`/`require_permission('...')` 字面量；C = 正则扫描 `frontend/src/**/*.{vue,ts}` 中 `can('...')`/`hasPermission('...')`/`requiresPermission: '...'`。断言 `B ⊆ A`、`C ⊆ A`，失败信息列出缺失 code 与来源文件:行号。路径用相对测试文件定位（`Path(__file__).resolve().parents[2]` 为仓库根）。
21. `backend/app/middleware/auth.py` `_check_permission`(255-294)：manage 包含动作集改为 `["view", "create", "edit", "delete", "read", "write", "update"]`（docstring 218-219 行同步改写）；删除 289-292 行 `system:audit_read` 死分支及 docstring 对应行。全仓无端点 require `system:audit_read`、无端点依赖 manage 通配放大（manage 模块端点均直接 require `:manage`），为零行为变化澄清。
22. `.trellis/spec/backend/` 新增 `permission-model.md`：记录权限码单一事实源（seed.py）、三层引用（后端 require_permission / 前端 can 与路由 meta / 测试夹具）、新权限码上线流程（改 seed.py → 跑 `--sync-permissions` → drift 测试守护）、共享字典端点白名单（步骤 11 清单）与高危权限清单。供后续任务对照。

## Critical files & anchors

- `backend/app/routes/analytics.py` — 改动最密集（26+3+1 个端点加装饰器）；行号为当前磁盘状态，实施前重读确认。`/dashboard/*` 与 `/priority-customers` 是首页专用端点（保持 `@auth_required`），`/consumption/sync` 单独用 `sync_tasks:manage`。
- `backend/app/middleware/auth.py:214-294` — `require_permission` / `_check_permission`，权限判定单点；步骤 21 的语义澄清只动包含集与死分支。
- `backend/app/routes/roles.py:149-266` — `update_role`（删 permission_ids）与 `assign_permissions`（缓存失效唯一入口，保持不动作逻辑）。
- `frontend/src/views/roles/Index.vue:298-321, 429-475` — 权限配置 computed 与提交逻辑；Phase 3 搜索/计数/高危标识均在此区域。
- `backend/scripts/seed.py` ALL_PERMISSIONS 与 PRESET_ROLES — 权限事实源；`--sync-permissions` 新增入口。

## Verification

环境：仓库根目录；后端用 `backend/.venv/bin/python`（pre-commit 规则）。集成测试需 PG/Redis（CI 同款，本地按 `backend/Makefile`/CI 容器方式准备）。

1. 单元与集成回归：`cd backend && .venv/bin/python -m pytest tests/unit/ -q` 全绿；`cd backend && .venv/bin/python -m pytest tests/integration/test_analytics_api.py tests/integration/test_customers_api.py tests/integration/test_roles_api.py tests/integration/test_admin_import_export_api.py -q` 全绿。
2. drift 测试有效性（变异验证）：临时在某路由加 `@require_permission("fake:perm")` → `test_permission_drift.py` 必须失败并指出该文件；撤销。再临时从 `seed.py` 删一个仍被引用的 code → 同样必须失败；撤销。
3. 新行为端到端（起本地后端 + 前端，用两个 token：admin 全量；运营经理预置角色）：
   - 运营经理 token 调 `GET /api/v1/analytics/consumption/trend` → 403（改前为 200）；
   - 运营经理 token 调 `POST /api/v1/analytics/consumption/sync` → 403；admin → 200；
   - 运营经理调 `GET /api/v1/sync-logs/?page=1` → 403；admin → 200；
   - 运营经理调 `GET /api/v1/customers` 列表与下拉（`/dicts/industry_types`、`/cooperation-statuses`、`/erp-systems`）→ 仍 200（步骤 11 白名单未被误伤）；
   - 运营经理调 `GET /api/v1/analytics/dashboard/stats` 与 `GET /api/v1/analytics/priority-customers?limit=10`（首页 KPI 与「今日优先跟进客户」）→ 仍 200（步骤 4 白名单未被误伤，首页对全员可用）。
4. 缓存生效验证：admin 调 `POST /api/v1/users/{运营经理id}/roles` 改角色后，**立即**用运营经理 token 调需新权限端点 → 200（不等 600s TTL）。
5. `PUT /roles/{id}` 带 `permission_ids` → 该角色权限不变（唯一入口为 `POST /{id}/permissions`）。
6. 前端（`cd frontend && npx vitest run` 全绿后，浏览器实操）：运营经理登录——消耗分析页无「数据同步」按钮；Forecast 页无「预测参数」按钮；Health 页有「导出」按钮（预置角色含 `analytics:export`）；侧边栏无「结算管理/客户分析」分组的角色（新建一个只有 customers:view 的角色验证）菜单不显示这两组；角色权限页搜索「view_all」只剩 1 项、`system:database_clear` 有高危标识。

## Assumptions & contingencies

- **运营经理/销售经理不授 `sync_tasks:manage`**（收敛：同步是破坏性运维操作，与 seed 现行「import 不预授」惯例一致）。若产品要求运营经理保留手动同步：在 `seed.py` `PRESET_ROLES["运营经理"]` 列表加一行 `"sync_tasks:manage"` 并跑 `--sync-permissions`，其余步骤不变。
- **客户详情上下文端点用 `customers:view` 而非 `analytics:view`**（步骤 4），避免无分析权限用户详情页用量/健康度/余额趋势 403。若产品要求这些数据也需分析权限，改这 3 个端点的权限码即可，前端无需改动（详情页守卫已是 customers:view，按钮按数据显隐可后续单独处理）。
- **Health.vue 导出按钮为新增前端入口**（闭环 `analytics:export`，否则该权限码持续无入口）。若不接受新增功能，删除步骤 14，其余不受影响。
- **`--sync-permissions` 竞争**：若并发执行报唯一键冲突，改用 select-then-insert 包裹 try/except IntegrityError 后重查（seed.py 已有 `get_or_create` 模式可复用）。
- 集成测试若因新权限出现 403：优先在 `tests/_test_data.py` `PERMISSION_ROWS` 补齐该测试场景需要的权限（与 seed 同步），或该用例改调 admin token；**禁止**通过放宽端点权限让测试通过。
- 全部行号基于当前磁盘状态；实施时若文件已变化，以符号名（装饰器下的函数名）为准定位。
