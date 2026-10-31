# 角色权限页面权限配置排查与加固 — PRD

## 背景

「角色权限」页面背后的权限配置存在系统性缺口：后端多个业务端点无权限码（任何登录用户可直调），前端多个受控入口无 `can()` 门，权限码在 seed / 后端 / 前端三处存在漂移风险，角色权限页面缺少搜索与高危标识。本任务完成排查结论中的加固方案。

## 需求范围

来源：`角色权限页面权限配置排查与加固计划_PLAN.md`（已归档至 `docs/specs/`）。

### R1 新权限码与种子同步机制（Phase 0）

- seed.py 新增权限码 `("sync_tasks:manage", "管理同步任务", "创建/取消数据同步任务", "system")`。
- seed.py 新增 `--sync-permissions` 命令行模式：对 ALL_PERMISSIONS 逐条 upsert（存在则更新 name/description/module，不存在则插入），并将「超级管理员」角色关联至全部权限（幂等）。不删除、不触碰预置业务角色关联。作为未来新权限码上线的唯一入口，替代 fix 脚本模式。
- `tests/_test_data.py` PERMISSION_ROWS 同步追加该码，使 `test_test_data_consistency.py` 继续通过。

### R2 后端 API 权限补齐（Phase 1，P0）

- analytics.py 26 个分析类 GET 端点追加 `@require_permission("analytics:view")`。
- 3 个客户详情上下文端点追加 `@require_permission("customers:view")`：`/health/customers/<id>/score`、`/billing/trend/<id>`、`/usage/daily`。
- `POST /analytics/consumption/sync` 追加 `@require_permission("sync_tasks:manage")`。
- sync_tasks.py：list/stats/get/progress/details 追加 `system:view`；create/cancel 追加 `sync_tasks:manage`；`get_sync_status` 保持 `@auth_required`（首页 SyncStatusBar 全员调用）。
- sync_logs.py 2 端点追加 `system:view`。
- 5 个 import-template 下载端点补权限：customers→`customers:import`，billing/imports→`billing:balance_import`，invoices→`billing:invoice_import`，packages→`billing:package_import`，pricing→`billing:pricing_import`。
- customers.py：`/summary`、`/related`、`/balance-forecast` 追加 `customers:view`；`POST /follow-up` 追加 `customers:edit`。
- roles.py `update_role`：删除 `permission_ids` 支持（route 传参 + docstring + service 参数及分支），权限分配收敛到唯一入口 `POST /roles/{id}/permissions`（已有缓存失效）。`create_role` 的 `permission_ids` 保留。
- users.py `assign_roles`：success 判定后追加 `await permission_cache.invalidate(user_id)`。
- 有意保持无权限码（防误改）：dict_routes.py、industry-types/cooperation-statuses/erp-systems GET、`POST /files/upload`、`GET /system/updates`、users 的 /options /profile /password /avatar /me/preferences；analytics 的 /dashboard/stats /dashboard/todos /dashboard/trend /priority-customers。

### R3 前端权限控制补齐（Phase 2，P1）

- Forecast.vue「预测参数」按钮加 `v-if="can('analytics:forecast_edit')"`（补 can 定义）。
- Consumption.vue「数据同步」「手动同步」两个按钮加 `v-if="can('sync_tasks:manage')"`（补 can 定义）。
- Health.vue「余额预警客户」table-header 加导出按钮 `v-if="can('analytics:export')"`，调用新增 `exportHealthWarningList()` API（GET `/analytics/health/export`，blob 下载，参照 `_excel.ts` fetchExport 风格）。
- AppSidebar.vue：billing 父级 + 4 个子按钮加 `v-if="can('billing:view')"`；analytics 父级 + 5 个子按钮加 `v-if="can('analytics:view')"`。useAppLayout.ts navSections 对应子项补 `permission` 字段（children 过滤逻辑已存在）。
- users/Index.vue「重置密码」按钮加 `v-if="can('users:edit')"`。
- InvoiceLogs 权限码对齐 `billing:detail_status_view`：router meta + useAppLayout navSections。

### R4 角色权限页面增强（Phase 3，P1）

- permissionGroups.ts 新增纯函数 `filterPermissionsByKeyword(permissions, keyword)`：对 name 与 code 大小写不敏感 includes 匹配，空 keyword 返回原数组；补单测（空 keyword、code 子串、name 匹配、大小写混合、无匹配空结果）。
- roles/Index.vue 权限弹窗：顶部加搜索框（placeholder「搜索权限名称/编码」，allow-clear）；`permissionGroups` computed 改为先过滤后分组；权限项在 name 下方展示 `permission.code`（12px muted）；分组标题旁「已选 x/y」计数（已有类似计数则增强）；高危权限卡片 warning 左边框 + tooltip「高危权限，请谨慎授予」（`DANGEROUS_PERMISSION_CODES` 常量：system:database_clear、system:database_backup、sync_tasks:manage、customers:delete、users:delete、roles:delete、files:delete、billing:delete、erp_systems:manage、api_keys:manage）；提交时 validPermIds 数字过滤逻辑不变。

### R5 防漂移与语义澄清（Phase 4，P2）

- 新增 `backend/tests/unit/test_permission_drift.py`：静态扫描断言 B（后端 require_permission 字面量）⊆ A（seed ALL_PERMISSIONS codes）、C（前端 can/hasPermission/requiresPermission 字面量）⊆ A；失败信息列出缺失 code 与来源文件:行号。
- middleware/auth.py `_check_permission`：manage 包含动作集改为 `["view", "create", "edit", "delete", "read", "write", "update"]`（docstring 同步）；删除 `system:audit_read` 死分支及 docstring 对应行。
- `.trellis/spec/backend/` 新增 `permission-model.md`：权限码单一事实源、三层引用、新权限码上线流程、共享字典端点白名单、高危权限清单。

## 验收标准

1. `cd backend && .venv/bin/python -m pytest tests/unit/ -q` 全绿（含新 drift 测试与 consistency 测试）。
2. `cd backend && .venv/bin/python -m pytest tests/integration/test_analytics_api.py tests/integration/test_customers_api.py tests_roles_api.py test_admin_import_export_api.py -q` 全绿（实际以环境可跑的集成测试为准；因新权限 403 的用例按 PLAN Assumptions 处理：补 PERMISSION_ROWS 或改 admin token，禁止放宽端点权限）。
3. drift 测试变异验证：临时加 `@require_permission("fake:perm")` 必须失败并指出文件；临时从 seed.py 删一个被引用 code 必须失败；均撤销。
4. 端到端（本地后端+前端，运营经理/超管双 token）：26 个分析端点运营经理 403、超管 200；consumption/sync 运营经理 403、超管 200；sync-logs 运营经理 403、超管 200；customers 列表与 3 个字典下拉仍 200；dashboard/stats 与 priority-customers 仍 200。
5. admin 调 `POST /users/{id}/roles` 后立即用新 token 调需新权限端点 → 200（不等 600s TTL）。
6. `PUT /roles/{id}` 带 permission_ids → 权限不变。
7. `cd frontend && npx vitest run` 全绿（含 permissionGroups 新用例）；浏览器实操验证按钮门控/侧边栏/搜索/高危标识（视本地环境可行性，不可行则说明限制）。
8. deploy 无破坏性影响：seed 幂等；不触碰预置角色关联；集成测试与单测全绿；`--sync-permissions` 为增量 upsert。

## 非目标

- 不改变中间件签名与认证机制（仅语义澄清）。
- 不给共享字典端点、files/upload、system/updates、users 自助端点加权限（PLAN 明确白名单）。
- 不做「场景化权限」细化设计。
