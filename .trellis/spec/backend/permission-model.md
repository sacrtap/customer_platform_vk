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

**防漂移守护**：`backend/tests/unit/test_permission_drift.py` 静态扫描双向断言：
1. **正向**：后端 `require_permission` 引用 ⊆ seed、前端门控引用 ⊆ seed（防「引用了不存在的码」）；
2. **反向**：`@auth_required` 但无权限码的端点必须在豁免清单登记理由（防「端点裸奔」，见下节）。

失败时列出缺失 code 与 `文件:行号`。改权限码时此测试必须通过。

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
   行为：逐条 upsert（存在则更新 name/description/module）；「超级管理员」角色幂等关联全部权限；`PRESET_ROLES` 预置业务角色幂等补齐关联（只增不删）；不删除、不触碰用户与自定义角色；提交后失效 `cache:permissions:*`。
4. 若预置业务角色（运营经理/销售经理，`PRESET_ROLES`）需要该码：在同文件 `PRESET_ROLES` 列表追加，`--sync-permissions` 会幂等补齐关联（只增不删——管理员可能已手动追加授权，删除属静默降权）。自定义角色由管理员在页面上自行配置，脚本不触碰。
5. `pytest tests/unit/`（drift 双向断言 + consistency 测试守护三层一致）。若新端点有意不挂码，同步在 drift 测试豁免清单登记理由。

## 有意不设权限码的端点（白名单，防误改）

**唯一事实源是 drift 测试的豁免清单**（`backend/tests/unit/test_permission_drift.py` 的 `EXEMPT_READ_ENDPOINTS` / `EXEMPT_WRITE_ENDPOINTS`）：反向断言强制「`@auth_required` 但无权限码的端点必须登记理由」，清单含已删除端点也会失败。下表为当前登记内容：

| 端点 | 理由 |
|---|---|
| `GET /dicts/industry_types` | 字典数据（id/name/sort_order）：客户表单行业类型下拉，全员基础交互数据 |
| `GET /system/updates` | 首页部署公告全员可见（产品设计） |
| `GET /users/options` | 运营经理/销售经理下拉选项（id/username/real_name）：业务模块姓名展示的基础能力，路由 docstring 已声明 |
| `GET/PUT /users/profile`、`GET/PUT /users/me/preferences`、`PUT /users/password`、`POST /users/avatar` | 个人中心：仅操作本人数据 |

历史沿革（2026-10-31 加固，PR #105 之后续提交）：
- `GET /industry-types`、`/cooperation-statuses`、`/erp-systems` **曾**在本表（理由「共享字典数据源」），实测与前端页面门控（均挂 `:manage`）割裂——页面隐藏但 API 登录即可读，已补 `@require_permission(xxx:manage)` 移出白名单。
- `POST /files/upload` **曾**在本表（理由「属 billing:edit 流程」），已新建 `files:upload` 码并仅预授运营经理（减免附件是唯一上传场景），移出白名单。
- `GET /sync-tasks/status` **曾**在本表（理由「首页 SyncStatusBar 全员调用」），实测 SyncStatusBar 为纯 props 组件、前端从未调用该端点（PLAN 描述与实际实现不符），已删除。

以上教训：豁免必须是**验证过调用方后的显式决策**；「规划文档声称的调用关系」不算证据，以代码为准。新增裸端点先查调用方再登记。

## 动态权限码端点（权限随资源状态变化）

**场景**：端点权限码取决于资源当前状态（如审批回退：`pending_ops` 节点要 `billing:ops_approve`、`pending_sales` 节点要 `billing:sales_approve`），静态装饰器无法表达。

**模式**（2026-11-04 审批回退落地）：
1. 路由只挂 `@auth_required`，在 handler 内按当前状态解析权限码后调用 `middleware/auth.py` 的 `ensure_permission(request, code)`（与 `require_permission` 同一 lookup 路径：`permission_cache → get_user_permissions → DB`），不足则 `json({"code": 40301, "message": "权限不足"}, status=403)`。
2. 在 `test_permission_drift.py` 的 `EXEMPT_WRITE_ENDPOINTS` / `EXEMPT_READ_ENDPOINTS` 登记（附理由）。**注意 key 形态**：drift 测试的 AST 扫描只在蓝图定义所在文件收集 `url_prefix`；`billing_bp` 跨文件定义（`routes/billing/__init__.py`），故 `routes/billing/*.py` 的端点扫描路径**无前缀**（如 `/invoices/<invoice_id:int>/rollback`，非 `/api/v1/billing/invoices/...`）。登记时先跑一次 drift 测试，从失败信息复制扫描出的真实 path。
3. 状态→权限码的映射表放在路由 docstring 或 service 附近，与回退目标状态机写在一起，防两处漂移。

## 新权限码漏同步 _test_data.py 的症状

**基线问题**（2026-11-04）：新权限码已注册 seed + 路由已切换，但 `tests/_test_data.py` 漏加对应行 → 集成测试报 `{'code': 40301, 'message': '权限不足'}`，而 `test_test_data_consistency.py` **全绿**。

**根因**：consistency 测试守护的是 `_test_data ⊆ seed`（防测试引用不存在的码），**不反向守护**「seed 有而 _test_data 缺」；集成测试 mock 权限集 = `_test_data.PERMISSION_CODES`，缺码即 403。漏加哪条码，只有挂了该码的集成用例会红，且红在「与权限无关」的业务用例子集里，极易误判为业务回归。

**预期改进**：切换/新增路由权限码后，若集成测试出现成片 `40301`，先 `grep -c "新码" tests/_test_data.py` 核对，再怀疑业务逻辑；「drift + consistency 双绿」不等于测试夹具已含新码。

## module 字段与前端分组

`ALL_PERMISSIONS` 四元组的 `module` 决定权限在角色配置弹窗（`views/roles/permissionGroups.ts` `MODULE_NAME_MAP`/`MODULE_ORDER`）中的分组卡片，**不影响权限判定**。约定：同一业务模块的码必须归同一 module——`industry_types:manage`、`cooperation_statuses:manage`、`erp_systems:manage`、`balance_whitelist:manage`、`api_keys:manage` 历史上误挂 `system`（初始 seed 按「系统管理」归类，后批量导入导出改造新增 `:import`/`:export` 时按模块命名，造成同模块码跨卡片），已于 2026-10-31 修正，部署时 `--sync-permissions` 的 upsert 自动更新。

## 高危权限清单（授予前需确认业务必要性）

`system:database_clear`、`system:database_backup`、`sync_tasks:manage`、`customers:delete`、`users:delete`、`roles:delete`、`files:delete`、`billing:delete`、`erp_systems:manage`、`api_keys:manage`。

角色权限页（`views/roles/Index.vue`）对命中项有 warning 色标识与 tooltip；预置业务角色默认不授予其中的 `sync_tasks:manage`（破坏性运维操作，与「import 不预授」惯例一致）。

## 权限缓存与失效

- 缓存：`PermissionCache`（Redis，key `cache:permissions:{user_id}`，TTL 600s）。
- 失效点：`POST /roles/{id}/permissions`（assign_permissions，失效角色下全部用户）、`POST /users/{id}/roles`（assign_roles，失效该用户）、`DELETE /users/{id}`、logout、seed 脚本。
- **权限分配唯一入口是 `POST /roles/{id}/permissions`**：`PUT /roles/{id}` 不接受 `permission_ids`（service 层 `update_role` 亦无此参数）——双写入路径必漏缓存失效。
