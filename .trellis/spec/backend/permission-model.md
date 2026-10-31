# 权限模型（Permission Model）

> 权限码的单一事实源、三层引用、上线流程与高危清单。新增/修改权限码前必读。

## 单一事实源

`backend/scripts/seed.py` 的 `ALL_PERMISSIONS`（四元组：`code, name, description, module`）是权限码的**唯一事实源**。数据库 `permissions` 表由它播种。

## 三层引用

| 层 | 位置 | 形式 |
|---|---|---|
| 后端强制 | `backend/app/**/*.py` 路由 | `@require_permission("module:action")`（中间件 `middleware/auth.py:require_permission`，通配规则见下） |
| 前端门控 | 模板/路由/导航 | `v-if="can('module:action')"`、路由 `meta.requiresPermission`、`useAppLayout.ts` navSections 的 `permission` 字段 |
| 测试夹具 | `backend/tests/_test_data.py` | `PERMISSION_ROWS`（测试 mock 用户权限；须 ⊆ seed） |

**防漂移守护**：`backend/tests/unit/test_permission_drift.py` 静态扫描断言「后端引用 ⊆ seed」且「前端引用 ⊆ seed」，失败时列出缺失 code 与 `文件:行号`。改权限码时此测试必须通过。

## 通配匹配语义（`_check_permission`）

- 直接命中：用户权限集合包含所需 code。
- `module:manage` 通配：包含全部细粒度动作 `view / create / edit / delete / read / write / update`。
- 无其他隐式映射（历史上 `system:view → system:audit_read` 的死分支已删除）。

## 新权限码上线流程（唯一入口）

1. `backend/scripts/seed.py` `ALL_PERMISSIONS` 追加条目。
2. 同步测试夹具：`backend/tests/_test_data.py` `PERMISSION_ROWS`（仅当测试场景需要该码）。
3. 应用到数据库（幂等，替代历史上的 fix 脚本）：
   ```bash
   cd backend && .venv/bin/python scripts/seed.py --sync-permissions
   ```
   行为：逐条 upsert（存在则更新 name/description/module）；「超级管理员」角色幂等关联全部权限；不删除、不触碰预置业务角色；提交后失效 `cache:permissions:*`。
4. 若预置业务角色（运营经理/销售经理，`PRESET_ROLES`）需要该码：在同文件 `PRESET_ROLES` 列表追加，再跑一次 `--sync-permissions`。
5. `pytest tests/unit/`（drift + consistency 测试守护三层一致）。

## 有意不设权限码的端点（白名单，防误改）

| 端点 | 理由 |
|---|---|
| `routes/dict_routes.py`、`GET /industry-types`、`/cooperation-statuses`、`/erp-systems` | 共享字典数据源，被无 manage 权限的业务页面下拉消费；管理能力由各写操作端点的 `:manage` 守 |
| `POST /files/upload` | 减免附件上传属 `billing:edit` 流程；`files:*` 只治理文件管理面 |
| `GET /system/updates` | 首页部署公告全员可见 |
| `users.py` 的 `/options`、`/profile`、`/password`、`/avatar`、`/me/preferences` | 自助/共享下拉 |
| `analytics` 的 `/dashboard/stats`、`/dashboard/todos`、`/dashboard/trend`、`/priority-customers` | 首页 KPI/待办/优先跟进客户，全员可见，已有 `customer_scope_user_id` 数据可见性强制 |
| `sync_tasks` 的 `GET /status` | 首页 SyncStatusBar 全员调用，只读同步健康摘要 |

以上如需收紧，应单独设计场景化权限，不允许直接套用现有 `:manage` 码。

## 高危权限清单（授予前需确认业务必要性）

`system:database_clear`、`system:database_backup`、`sync_tasks:manage`、`customers:delete`、`users:delete`、`roles:delete`、`files:delete`、`billing:delete`、`erp_systems:manage`、`api_keys:manage`。

角色权限页（`views/roles/Index.vue`）对命中项有 warning 色标识与 tooltip；预置业务角色默认不授予其中的 `sync_tasks:manage`（破坏性运维操作，与「import 不预授」惯例一致）。

## 权限缓存与失效

- 缓存：`PermissionCache`（Redis，key `cache:permissions:{user_id}`，TTL 600s）。
- 失效点：`POST /roles/{id}/permissions`（assign_permissions，失效角色下全部用户）、`POST /users/{id}/roles`（assign_roles，失效该用户）、`DELETE /users/{id}`、logout、seed 脚本。
- **权限分配唯一入口是 `POST /roles/{id}/permissions`**：`PUT /roles/{id}` 不接受 `permission_ids`（service 层 `update_role` 亦无此参数）——双写入路径必漏缓存失效。
