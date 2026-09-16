# 角色权限配置页权限清单修正

## Context

当前「角色权限」页的「权限配置」对话框展示后端 `permissions` 表（seed 定义的 49 个权限）按 module 分组的内容。但种子权限清单与实际前端（路由 `requiresPermission`、按钮 `can()`、侧边栏 `permission`）和后端（`@require_permission`）使用的权限 code 存在 4 处不一致、9 个孤儿权限（展示却无对应功能）、分组映射 2 处冗余、侧边栏 4 个页面入口缺失。

修正目标：让权限配置页的权限清单与实际功能页面及操作权限一一对应，消除 code 不一致、移除孤儿权限、补全缺失入口。修正后权限总数为 **42 个**（49 − 7 删除）。

## Approach

### 步骤 1：修正后端权限 code（预测编辑，2 处）

后端预测编辑接口使用了不存在的 `analytics:forecast`，种子定义是 `analytics:forecast_edit`，导致分配了「编辑预测」权限的角色仍无法调用接口。

- 编辑 `backend/app/routes/analytics.py`，将两处装饰器 `@require_permission("analytics:forecast")` 改为 `@require_permission("analytics:forecast_edit")`：
  - 第 868 行（`POST /consumption/accuracy`，记录预测准确度）
  - 第 902 行（`PUT /consumption/price-config`，更新消费预测单价配置）
- 两处字符串完全相同，用 `edit` 的 `replace_all: true` 一次替换。后端全局仅此 2 处引用 `analytics:forecast`（已核实），前端无 `forecast_edit` 引用。

### 步骤 2：修正前端权限 code（3 处）

- 编辑 `frontend/src/views/billing/Balance.vue` 第 15 行：`can('balance:import')` → `can('billing:import')`。这是「导入余额」按钮，种子权限是 `billing:import`，写错导致按钮永不显示。
- 编辑 `frontend/src/composables/useAppLayout.ts` 第 96 行：`permission: 'sync:view'` → `permission: 'system:view'`。同步日志菜单路由校验用 `system:view`，写错导致菜单永不显示。
- 编辑 `frontend/src/composables/useAppLayout.ts` 第 101 行：`permission: 'audit:view'` → `permission: 'system:view'`。审计日志菜单同上。

### 步骤 3：接上 `billing:export` 权限（导出结算单）

导出结算单功能完整存在（前端按钮 + 后端接口），但误用 `billing:view` 控制，导致种子里的 `billing:export` 无控制点。

- 编辑 `frontend/src/views/billing/Invoices.vue` 第 6 行导出按钮：`can('billing:view')` → `can('billing:export')`。该行是页面唯一的 `can('billing:view')`（其余为 `billing:edit`/`billing:ops_approve`/`billing:sales_approve`，已核实）。
- 编辑 `backend/app/routes/billing/invoices.py` 第 1147 行：`@require_permission("billing:view")` → `@require_permission("billing:export")`（`GET /billing/invoices/export` 接口）。
- 配套：编辑 `backend/scripts/seed.py` 的 `PRESET_ROLES`，给「运营经理」和「销售经理」的权限列表各追加 `"billing:export"`，保持两者原有导出结算单能力不变（两者原本通过 `billing:view` 可导出）。

### 步骤 4：接上 `analytics:export` 权限（导出健康度报告）

健康度导出接口 `GET /health/export` 只有 `@auth_required`，导致种子里的 `analytics:export` 无控制点。前端当前无导出按钮，接上权限不会改变任何现有用户行为（仅让权限有后端控制点）。

- 编辑 `backend/app/routes/analytics.py` 第 1197 行 `@auth_required` 与第 1198 行 `async def export_health_report` 之间插入一行 `@require_permission("analytics:export")`。

### 步骤 5：删除 7 个孤儿权限（种子定义）

以下权限在种子中定义但前端/后端均无对应功能，从 `backend/scripts/seed.py` 的 `ALL_PERMISSIONS` 删除对应行：

1. `("billing:refund", "退款操作", "执行退款", "billing"),` — 项目无退款功能。
2. `("system:settings", "系统设置", "修改系统配置", "system"),` — 无系统设置功能。
3. `("webhooks:manage", "Webhook 管理", "管理 Webhook 配置", "webhooks"),` — `webhooks.py` 仅有两个外部回调端点，无管理功能/页面。
4. `("profiles:view", "查看画像", "查看客户画像信息", "profiles"),` — 画像分析用 `analytics:view`，客户画像展示属 `customers:view`，无独立画像权限。
5. `("profiles:edit", "编辑画像", "修改客户画像等级", "profiles"),` — 同上。
6. `("system:export", "导出日志", "导出系统日志", "system"),` — 无日志导出功能。
7. `("files:upload", "上传文件", "上传新文件", "files"),` — `/files/upload` 唯一前端调用方是结算单减免附件上传（`uploadDiscountAttachment`，被 `DiscountEditModal.vue` 与 `SubmitModal.vue` 调用，属 `billing:edit` 流程），无独立文件上传功能；接上会破坏运营经理上传减免附件。

同时修正 `ALL_PERMISSIONS` 中因此失效的分组注释：删除「客户画像 (2)」整组；「系统管理」与「其他模块」的计数注释顺带修正（`system` 剩 `system:view`/`system:database_clear` 2 个；`files` 剩 `files:view`/`files:delete` 2 个，`webhooks` 组消失）。

### 步骤 6：扩展清理脚本移除数据库已有记录

seed 的 `get_or_create_permission` 只增不删，需清理脚本删除已存在于数据库的 7 个孤儿权限及其角色关联。

- 编辑 `backend/scripts/cleanup_deprecated_permissions.py` 的 `DEPRECATED_PERMISSIONS` 列表，追加 7 个 code：
  `"billing:refund", "system:settings", "webhooks:manage", "profiles:view", "profiles:edit", "system:export", "files:upload"`。
- 该脚本幂等（重复运行打印「未发现弃用权限」），无需新建脚本。

### 步骤 7：清理权限配置页分组映射（`permissionGroups.ts`）

`MODULE_NAME_MAP`/`MODULE_ORDER` 含两个永不出现的冗余键：`industry_types`（种子中 `industry_types:manage` 的 module 是 `system`）和 `groups`（无任何 `groups` 模块权限及功能页面）。

- 编辑 `frontend/src/views/roles/permissionGroups.ts`：
  - 从 `MODULE_NAME_MAP` 删除键 `industry_types: '行业类型'` 与 `groups: '客户分组'`。
  - 从 `MODULE_ORDER` 数组删除元素 `'industry_types'` 与 `'groups'`。
- `industry_types:manage` 的 module 为 `system`，删除后正确归入「系统管理」分组，不影响展示。`buildPermissionGroups` 仅被 `roles/Index.vue` 调用（已核实），删除冗余键不改变任何现有分组结果（种子无 `industry_types`/`groups` 模块权限）。

### 步骤 8：补全侧边栏缺失的 4 个页面入口（含高亮/展开配套）

以下路由存在但侧边栏无入口，编辑 `frontend/src/composables/useAppLayout.ts`：

**加菜单项**（`navSections`）：
- 「结算管理」children 末尾追加：`{ key: 'package-plans', label: '套餐方案', to: '/billing/package-plans' }`（页面路由用 `billing:view`，父分组已隐式受结算管理可见性约束，不单设 permission）。
- 「系统管理」items 末尾追加两项：
  - `{ key: 'erp-systems', label: 'ERP系统', to: '/system/erp-systems', permission: 'erp_systems:manage' }`
  - `{ key: 'api-keys', label: 'API-Key管理', to: '/system/api-keys', permission: 'api_keys:manage' }`
- 「系统工具」items 末尾追加：`{ key: 'database-management', label: '数据清空', to: '/system/database-management', permission: 'system:database_clear' }`

**同步更新路径判断**（否则新入口导航时父菜单不高亮、子菜单不自动展开）：
- `isSubmenuActive('system')`（第 174–181 行）的返回条件追加 `|| p === '/system/erp-systems' || p === '/system/api-keys'`。
- `watch(route.path, ...)`（第 203–211 行）的 `expandedSubmenu = 'system'` 分支追加 `|| newPath === '/system/erp-systems' || newPath === '/system/api-keys'`。
- `package-plans` 无需改：`isSubmenuActive('billing')` 与 watch 均用 `startsWith('/billing')` 自动覆盖。
- `database-management` 无需改：tools 分组无父菜单高亮逻辑，且 watch 的 system 分支已含 `/system/database-management`（第 209 行）。

### 步骤 9：同步测试种子 `conftest.py`

`backend/tests/integration/conftest.py` 内维护了一份与 seed 对应的权限列表与 mock 权限集合，需同步 4 删除 1 新增，避免测试种子与生产种子漂移：

- 权限插入列表（约 210–248 行）删除 4 行：`("billing:refund", ...)`, `("files:upload", ...)`, `("system:export", ...)`, `("system:settings", ...)`。
- 权限插入列表新增 1 行（接上 billing:export）：`("billing:export", "导出账单", "billing"),`。
- `FULL_PERMISSIONS` 集合（约 436–470 行）删除 4 个元素：`"billing:refund", "files:upload", "system:export", "system:settings"`；新增 `"billing:export",`。
- `analytics:export` 保留（接上后仍使用）；`webhooks:manage`/`profiles:view`/`profiles:edit` 在 conftest.py 中本就不存在，无需处理。

## Critical files & anchors

- `backend/scripts/seed.py` — `ALL_PERMISSIONS`（第 42–123 行）与 `PRESET_ROLES`（第 126–158 行）；权限清单的唯一权威来源。
- `backend/app/routes/analytics.py` — 第 868/902 行 forecast 权限、第 1197–1198 行 health/export 装饰器。
- `backend/app/routes/billing/invoices.py` — 第 1145–1148 行导出接口装饰器。
- `frontend/src/composables/useAppLayout.ts` — `navSections`（第 36–122 行）、`isSubmenuActive`（第 170–183 行）、`watch` 路径判断（第 196–217 行）。
- `frontend/src/views/roles/permissionGroups.ts` — `MODULE_NAME_MAP`/`MODULE_ORDER`（第 23–54 行）分组映射。

## Verification

先决条件：项目根目录 `/Users/sacrtap/Documents/trae_projects/customer_platform_vk`，后端虚拟环境 `backend/.venv`，前端依赖已安装。

1. **静态无残留检查**（应无输出）：
   - `git grep -n "analytics:forecast\"" backend/app` → 应无 `analytics:forecast`（只剩 `forecast_edit`）。
   - `git grep -n "balance:import\|sync:view\|audit:view" frontend/src` → 应无结果。
2. **后端测试**：`cd backend && source .venv/bin/activate && pytest tests/unit/ tests/integration/ -q --tb=short` → 全绿（conftest.py 同步后集成测试不依赖已删孤儿权限）。
3. **前端测试**：`cd frontend && npm test -- --run` → 全绿（含 `permissionGroups.test.ts` 的 MODULE_NAME_MAP/MODULE_ORDER 一致性断言，删除冗余键后仍通过）。
4. **前端构建**：`cd frontend && npm run build` → `vue-tsc` 类型检查 + vite 构建通过。
5. **种子与清理脚本 dry 验证**：`cd backend && source .venv/bin/activate && python scripts/seed.py` 打印 `权限数: 42`；`python scripts/cleanup_deprecated_permissions.py` 成功删除 7 个孤儿权限且不报错。若本地无数据库，此步以静态核对 `ALL_PERMISSIONS` 长度 = 42 代替。
6. **行为验证（人工，需可运行环境）**：以拥有 `billing:view` 但无 `billing:export` 的账号登录，确认结算单管理页「导出」按钮隐藏、后端 `GET /billing/invoices/export` 返回 403；以超管账号确认侧边栏新增「套餐方案 / ERP系统 / API-Key管理 / 数据清空」4 个入口，导航到 `/system/erp-systems`、`/system/api-keys` 时「系统管理」父菜单正确高亮且子菜单展开。

## Assumptions & contingencies

- **`files:upload` 归类调整**：初步归类为「接上」，codegraph 核实后发现 `/files/upload` 唯一调用方 `uploadDiscountAttachment` 被 `DiscountEditModal.vue`/`SubmitModal.vue` 调用（均为结算减免附件上传，属 `billing:edit` 流程），接上会破坏运营经理上传减免附件或需给业务角色补权限造成语义混乱，故改为删除。若产品方未来要独立文件上传功能，届时再新增权限。
- **`analytics:export` 仅接后端**：健康度导出前端无按钮，本次只给后端接口加权限、不补前端按钮（补按钮属新功能开发，超出权限清单修正范围）。若执行中发现需要前端入口，另立任务。
- **`billing:export` 行为变更**：接上后，仅有 `billing:view` 的自定义角色将失去导出结算单能力。已通过给「运营经理」「销售经理」补 `billing:export` 保持预置角色行为不变；自定义角色需管理员在角色权限页手动勾选。
- **数据库清理时机**：删除孤儿权限需在生产库执行 `cleanup_deprecated_permissions.py`。若部署流程不含脚本执行，需人工在迁移/发版时运行一次。
