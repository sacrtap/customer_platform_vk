# 细粒度权限实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将系统权限从 12 个模块级粗粒度权限，细分为 38 个操作级细粒度权限，覆盖所有功能模块的查看/创建/编辑/删除/导出等操作。

**Architecture:** 采用混合模式方案 C，权限完全独立无隐式继承。后端 seed.py 定义所有权限码，路由装饰器使用细粒度权限校验，前端路由和按钮级权限控制同步更新。超级管理员角色自动获得所有新权限，旧权限码保留向后兼容。

**Tech Stack:** Python 3.12 + Sanic + SQLAlchemy (后端) | Vue 3 + TypeScript + Arco Design (前端)

**权限映射关系:**
- `customers:manage` (旧) → `customers:view`, `customers:create`, `customers:edit`, `customers:delete`, `customers:export`, `customers:import` (新)
- `billing:manage` (旧) → `billing:view`, `billing:edit`, `billing:recharge`, `billing:refund`, `billing:export` (新)
- `users:manage` (旧) → `users:view`, `users:create`, `users:edit`, `users:delete`, `users:role_assign` (新)
- `roles:manage` (旧) → `roles:view`, `roles:create`, `roles:edit`, `roles:delete`, `roles:assign` (新)
- `tags:manage` (旧) → `tags:view`, `tags:create`, `tags:edit`, `tags:delete` (新)
- `analytics:view` (旧) → `analytics:view`, `analytics:export`, `analytics:forecast_edit` (新)
- `system:view` (旧) → `system:view`, `system:export`, `system:settings` (新)
- 新增: `profiles:view`, `profiles:edit`, `profiles:export`
- 新增: `groups:view`, `groups:manage`
- 保留: `files:manage`, `webhooks:manage`

---

### Task 1: 更新后端种子数据 - 定义细粒度权限

**Files:**
- Modify: `backend/scripts/seed.py:42-66` (替换 `ALL_PERMISSIONS` 列表)

- [ ] **Step 1: 替换 ALL_PERMISSIONS 列表**

将 `backend/scripts/seed.py` 中的 `ALL_PERMISSIONS` 从 12 个粗粒度权限替换为 38 个细粒度权限：

```python
ALL_PERMISSIONS = [
    # ============================================================
    # 客户管理 (6)
    # ============================================================
    ("customers:view", "查看客户", "查看客户列表和详情", "customers"),
    ("customers:create", "新建客户", "创建新客户记录", "customers"),
    ("customers:edit", "编辑客户", "修改客户信息", "customers"),
    ("customers:delete", "删除客户", "删除客户记录", "customers"),
    ("customers:export", "导出客户", "导出 Excel 数据", "customers"),
    ("customers:import", "导入客户", "批量导入数据", "customers"),
    # ============================================================
    # 结算管理 (5)
    # ============================================================
    ("billing:view", "查看结算", "查看余额和定价规则", "billing"),
    ("billing:edit", "编辑结算", "修改定价规则", "billing"),
    ("billing:recharge", "充值操作", "执行客户充值", "billing"),
    ("billing:refund", "退款操作", "执行退款", "billing"),
    ("billing:export", "导出账单", "导出结算数据", "billing"),
    # ============================================================
    # 客户分析 (3)
    # ============================================================
    ("analytics:view", "查看分析", "查看所有分析报表", "analytics"),
    ("analytics:export", "导出报表", "导出分析数据", "analytics"),
    ("analytics:forecast_edit", "编辑预测", "修改预测模型参数", "analytics"),
    # ============================================================
    # 画像管理 (3)
    # ============================================================
    ("profiles:view", "查看画像", "查看客户画像", "profiles"),
    ("profiles:edit", "编辑画像", "修改画像规则和标签", "profiles"),
    ("profiles:export", "导出画像", "导出画像数据", "profiles"),
    # ============================================================
    # 标签管理 (4)
    # ============================================================
    ("tags:view", "查看标签", "查看标签列表", "tags"),
    ("tags:create", "新建标签", "创建新标签", "tags"),
    ("tags:edit", "编辑标签", "修改标签", "tags"),
    ("tags:delete", "删除标签", "删除标签", "tags"),
    # ============================================================
    # 用户管理 (5)
    # ============================================================
    ("users:view", "查看用户", "查看用户列表", "users"),
    ("users:create", "新建用户", "创建新用户", "users"),
    ("users:edit", "编辑用户", "修改用户信息", "users"),
    ("users:delete", "删除用户", "删除用户", "users"),
    ("users:role_assign", "分配角色", "给用户分配角色", "users"),
    # ============================================================
    # 角色权限 (5)
    # ============================================================
    ("roles:view", "查看角色", "查看角色列表", "roles"),
    ("roles:create", "新建角色", "创建新角色", "roles"),
    ("roles:edit", "编辑角色", "修改角色信息", "roles"),
    ("roles:delete", "删除角色", "删除自定义角色", "roles"),
    ("roles:assign", "分配权限", "为角色分配权限", "roles"),
    # ============================================================
    # 系统管理 (3)
    # ============================================================
    ("system:view", "查看系统", "查看同步/审计日志", "system"),
    ("system:export", "导出日志", "导出系统日志", "system"),
    ("system:settings", "系统设置", "修改系统配置", "system"),
    # ============================================================
    # 其他模块 (4)
    # ============================================================
    ("groups:view", "查看分组", "查看客户分组", "groups"),
    ("groups:manage", "管理分组", "创建/编辑/删除分组", "groups"),
    ("files:manage", "文件管理", "上传/删除文件", "files"),
    ("webhooks:manage", "Webhook 管理", "管理 Webhook 配置", "webhooks"),
    # ============================================================
    # 向后兼容 (旧权限码，标记 deprecated)
    # ============================================================
    ("customers:manage", "[已弃用] 客户管理", "请使用 customers:view/edit/delete 等细粒度权限", "customers"),
    ("billing:manage", "[已弃用] 结算管理", "请使用 billing:view/edit/recharge 等细粒度权限", "billing"),
    ("users:manage", "[已弃用] 用户管理", "请使用 users:view/edit/delete 等细粒度权限", "users"),
    ("roles:manage", "[已弃用] 角色权限管理", "请使用 roles:view/edit/assign 等细粒度权限", "roles"),
    ("tags:manage", "[已弃用] 标签管理", "请使用 tags:view/edit/delete 等细粒度权限", "tags"),
]
```

- [ ] **Step 2: 验证种子脚本可执行**

```bash
cd backend && source .venv/bin/activate && python scripts/seed.py --reset
```

Expected: 输出显示创建 38 个新权限 + 5 个兼容权限，超级管理员角色关联所有权限。

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/seed.py
git commit -m "feat: 定义 38 个细粒度权限 + 5 个向后兼容权限"
```

---

### Task 2: 更新后端路由权限装饰器 - 客户管理模块

**Files:**
- Modify: `backend/app/routes/customers.py` (所有 `@require_permission` 调用)

- [ ] **Step 1: 查看当前 customers.py 的权限装饰器分布**

当前使用的权限码：
- `customers:read` → 替换为 `customers:view`
- `customers:write` → 替换为 `customers:edit`（创建/更新操作使用 `customers:create` 或 `customers:edit`）
- `customers:delete` → 保持不变

- [ ] **Step 2: 更新权限装饰器**

```python
# 列表/详情/搜索/导出等只读操作
@require_permission("customers:view")  # 替换 customers:read

# 创建操作
@require_permission("customers:create")  # 替换 customers:write

# 更新操作
@require_permission("customers:edit")  # 替换 customers:write

# 删除操作
@require_permission("customers:delete")  # 保持不变

# 导入操作
@require_permission("customers:import")  # 替换 customers:write

# 导出操作
@require_permission("customers:export")  # 替换 customers:read
```

具体路由映射（根据实际路由代码调整）：
- `GET /customers` → `customers:view`
- `GET /customers/<id>` → `customers:view`
- `POST /customers` → `customers:create`
- `PUT /customers/<id>` → `customers:edit`
- `DELETE /customers/<id>` → `customers:delete`
- `POST /customers/import` → `customers:import`
- `GET /customers/export` → `customers:export`

- [ ] **Step 3: Commit**

```bash
git add backend/app/routes/customers.py
git commit -m "refactor: 客户管理路由使用细粒度权限"
```

---

### Task 3: 更新后端路由权限装饰器 - 结算管理模块

**Files:**
- Modify: `backend/app/routes/billing.py`

- [ ] **Step 1: 更新权限装饰器**

```python
# 只读操作（余额查询、定价规则列表、账单列表）
@require_permission("billing:view")  # 替换 billing:read

# 写操作（创建/更新定价规则）
@require_permission("billing:edit")  # 替换 billing:write

# 充值操作
@require_permission("billing:recharge")  # 替换 billing:write

# 删除操作
@require_permission("billing:delete")  # 保持不变（如存在）
```

具体路由映射：
- `GET /billing/balances` → `billing:view`
- `GET /billing/pricing-rules` → `billing:view`
- `POST /billing/pricing-rules` → `billing:edit`
- `PUT /billing/pricing-rules/<id>` → `billing:edit`
- `DELETE /billing/pricing-rules/<id>` → `billing:delete`（如存在）
- `POST /billing/recharge` → `billing:recharge`

- [ ] **Step 2: Commit**

```bash
git add backend/app/routes/billing.py
git commit -m "refactor: 结算管理路由使用细粒度权限"
```

---

### Task 4: 更新后端路由权限装饰器 - 用户管理模块

**Files:**
- Modify: `backend/app/routes/users.py`

- [ ] **Step 1: 更新权限装饰器**

```python
# 只读操作（用户列表、用户详情）
@require_permission("users:view")  # 替换 users:read

# 创建操作
@require_permission("users:create")  # 替换 users:write

# 更新操作
@require_permission("users:edit")  # 替换 users:write

# 删除操作
@require_permission("users:delete")  # 保持不变

# 分配角色操作
@require_permission("users:role_assign")  # 替换 users:write
```

具体路由映射：
- `GET /users` → `users:view`
- `GET /users/<id>` → `users:view`
- `POST /users` → `users:create`
- `PUT /users/<id>` → `users:edit`
- `DELETE /users/<id>` → `users:delete`
- `POST /users/<id>/roles` → `users:role_assign`

- [ ] **Step 2: Commit**

```bash
git add backend/app/routes/users.py
git commit -m "refactor: 用户管理路由使用细粒度权限"
```

---

### Task 5: 更新后端路由权限装饰器 - 角色/标签/其他模块

**Files:**
- Modify: `backend/app/routes/roles.py`
- Modify: `backend/app/routes/tags.py`
- Modify: `backend/app/routes/permissions.py`
- Modify: `backend/app/routes/audit_logs.py`

- [ ] **Step 1: 更新 roles.py**

```python
# 角色列表/详情
@require_permission("roles:view")  # 替换 roles:create/update/delete 中的读操作

# 创建角色
@require_permission("roles:create")

# 更新角色
@require_permission("roles:edit")

# 删除角色
@require_permission("roles:delete")

# 分配权限
@require_permission("roles:assign")  # 替换 roles:update（权限分配操作）
```

- [ ] **Step 2: 更新 tags.py**

```python
# 标签列表/详情
@require_permission("tags:view")  # 替换 tags:read

# 创建标签
@require_permission("tags:create")  # 替换 tags:write

# 更新标签
@require_permission("tags:edit")  # 替换 tags:write

# 删除标签
@require_permission("tags:delete")  # 保持不变
```

注意：tags.py 中还有 `customers:read` 和 `customers:write` 的引用（标签关联客户操作），替换为：
- `customers:read` → `customers:view`
- `customers:write` → `customers:edit`
- `profiles:read` → `profiles:view`
- `profiles:write` → `profiles:edit`

- [ ] **Step 3: 更新 permissions.py**

```python
# 创建权限
@require_permission("roles:assign")  # 替换 permissions:create

# 更新权限
@require_permission("roles:assign")  # 替换 permissions:update

# 删除权限
@require_permission("roles:assign")  # 替换 permissions:delete
```

- [ ] **Step 4: 更新 audit_logs.py**

```python
# 审计日志查看
@require_permission("system:view")  # 替换 system:audit_read
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/roles.py backend/app/routes/tags.py backend/app/routes/permissions.py backend/app/routes/audit_logs.py
git commit -m "refactor: 角色/标签/权限/审计路由使用细粒度权限"
```

---

### Task 6: 更新后端测试中的权限 seed 数据

**Files:**
- Modify: `backend/tests/integration/conftest.py`
- Modify: `backend/tests/integration/test_analytics_api.py`
- Modify: `backend/tests/integration/test_audit_logs_api.py`

- [ ] **Step 1: 更新 conftest.py 中的测试权限 seed**

找到 `conftest.py` 中直接插入 permissions 表的 SQL，更新为细粒度权限：

```python
# 替换原有的单条权限插入
INSERT INTO permissions (code, name, description, module, created_at)
VALUES
    ('customers:view', '查看客户', '查看客户列表和详情', 'customers', NOW()),
    ('customers:create', '新建客户', '创建新客户记录', 'customers', NOW()),
    ('customers:edit', '编辑客户', '修改客户信息', 'customers', NOW()),
    ('analytics:view', '查看分析', '查看所有分析报表', 'analytics', NOW()),
    ('system:view', '查看系统', '查看同步/审计日志', 'system', NOW()),
    -- ... 按需添加测试使用的权限
```

- [ ] **Step 2: 更新 test_analytics_api.py**

```python
# 替换
"SELECT id FROM permissions WHERE code = 'analytics:view'"
# 原为 'analytics:read' 或 'analytics:view'（如果已存在则无需改）
```

- [ ] **Step 3: 更新 test_audit_logs_api.py**

```python
# 替换所有 'system:audit_read' 为 'system:view'
"SELECT id FROM permissions WHERE code = 'system:view'"
```

- [ ] **Step 4: 运行后端测试验证**

```bash
cd backend && source .venv/bin/activate && pytest tests/integration/ -v -x
```

Expected: 所有集成测试通过。

- [ ] **Step 5: Commit**

```bash
git add backend/tests/
git commit -m "test: 更新集成测试中的权限 seed 数据"
```

---

### Task 7: 更新前端路由权限守卫

**Files:**
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 更新路由 meta.requiresPermission**

```typescript
// 用户管理 - 只需 view 权限即可访问页面
{ path: 'users', meta: { requiresPermission: 'users:view' } }

// 角色权限 - 只需 view 权限即可访问页面
{ path: 'roles', meta: { requiresPermission: 'roles:view' } }

// 客户管理 - 只需 view 权限即可访问页面
{ path: 'customers', meta: { requiresPermission: 'customers:view' } }
{ path: 'customers/:id', meta: { requiresPermission: 'customers:view' } }

// 标签管理 - 只需 view 权限即可访问页面
{ path: 'tags', meta: { requiresPermission: 'tags:view' } }

// 结算管理 - 只需 view 权限即可访问页面
{ path: 'billing/balances', meta: { requiresPermission: 'billing:view' } }
{ path: 'billing/pricing-rules', meta: { requiresPermission: 'billing:view' } }

// 客户分析 - 只需 view 权限即可访问页面
{ path: 'analytics/consumption', meta: { requiresPermission: 'analytics:view' } }
{ path: 'analytics/payment', meta: { requiresPermission: 'analytics:view' } }
{ path: 'analytics/health', meta: { requiresPermission: 'analytics:view' } }
{ path: 'analytics/profile', meta: { requiresPermission: 'analytics:view' } }
{ path: 'analytics/forecast', meta: { requiresPermission: 'analytics:view' } }

// 系统管理 - 保持不变
{ path: 'system/sync-logs', meta: { requiresPermission: 'system:view' } }
{ path: 'system/audit-logs', meta: { requiresPermission: 'system:view' } }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/router/index.ts
git commit -m "refactor: 前端路由使用细粒度 view 权限"
```

---

### Task 8: 更新前端侧边栏权限控制

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`

- [ ] **Step 1: 更新侧边栏 v-if 权限检查**

```vue
<!-- 客户管理 -->
v-if="can('customers:view')"

<!-- 画像管理 -->
v-if="can('profiles:view')"

<!-- 用户管理 -->
v-if="can('users:view')"

<!-- 角色权限 -->
v-if="can('roles:view')"

<!-- 标签管理 -->
v-if="can('tags:view')"

<!-- 系统设置子菜单 -->
v-if="can('system:view')"
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/Dashboard.vue
git commit -m "refactor: 侧边栏使用细粒度 view 权限"
```

---

### Task 9: 更新前端页面内按钮级权限控制

**Files:**
- Modify: `frontend/src/views/customers/Index.vue`
- Modify: `frontend/src/views/customers/Detail.vue`
- Modify: `frontend/src/views/billing/Balance.vue`
- Modify: `frontend/src/views/billing/PricingRules.vue`
- Modify: `frontend/src/views/users/Index.vue`
- Modify: `frontend/src/views/roles/Index.vue`
- Modify: `frontend/src/views/tags/Index.vue`

- [ ] **Step 1: 客户管理页面按钮权限**

在 `customers/Index.vue` 中：
```vue
<!-- 新建按钮 -->
<a-button v-if="can('customers:create')" type="primary">新建客户</a-button>

<!-- 编辑按钮 -->
<a-button v-if="can('customers:edit')">编辑</a-button>

<!-- 删除按钮 -->
<a-popconfirm>
  <a-button v-if="can('customers:delete')" status="danger">删除</a-button>
</a-popconfirm>

<!-- 导出按钮 -->
<a-button v-if="can('customers:export')">导出</a-button>

<!-- 导入按钮 -->
<a-button v-if="can('customers:import')">导入</a-button>
```

- [ ] **Step 2: 其他页面类似更新**

按相同模式更新其他页面的按钮权限：
- `billing/Balance.vue`: 充值按钮 → `can('billing:recharge')`
- `billing/PricingRules.vue`: 新建/编辑 → `can('billing:edit')`
- `users/Index.vue`: 新建 → `can('users:create')`, 编辑 → `can('users:edit')`, 删除 → `can('users:delete')`, 分配角色 → `can('users:role_assign')`
- `roles/Index.vue`: 新建 → `can('roles:create')`, 编辑 → `can('roles:edit')`, 删除 → `can('roles:delete')`, 权限配置 → `can('roles:assign')`
- `tags/Index.vue`: 新建 → `can('tags:create')`, 编辑 → `can('tags:edit')`, 删除 → `can('tags:delete')`

- [ ] **Step 3: 验证 can() 函数实现**

检查 `frontend/src/stores/user.ts` 中的 `hasPermission` 方法，确保它正确检查权限：

```typescript
// 确认 hasPermission 方法存在且工作正常
hasPermission(code: string): boolean {
  return this.permissions.some(p => p.code === code)
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/
git commit -m "feat: 页面按钮级细粒度权限控制"
```

---

### Task 10: 运行全量测试验证

**Files:**
- 无修改，仅运行验证命令

- [ ] **Step 1: 后端测试**

```bash
cd backend && source .venv/bin/activate && pytest tests/ -v --tb=short
```

Expected: 所有测试通过。

- [ ] **Step 2: 前端类型检查**

```bash
cd frontend && npm run type-check
```

Expected: 无类型错误。

- [ ] **Step 3: 前端 lint**

```bash
cd frontend && npm run lint
```

Expected: 无 lint 错误。

- [ ] **Step 4: 重新运行种子脚本验证**

```bash
cd backend && source .venv/bin/activate && python scripts/seed.py --reset
```

Expected: 输出显示创建 43 个权限（38 新 + 5 兼容），超级管理员关联所有权限。

- [ ] **Step 5: 最终 Commit（如有测试修复）**

```bash
git add .
git commit -m "fix: 修复测试和类型检查问题"
```

---

## 自审检查

**1. Spec 覆盖检查:**
- ✅ seed.py 权限定义 → Task 1
- ✅ 后端路由权限装饰器 (customers, billing, users, roles, tags, permissions, audit_logs) → Task 2-5
- ✅ 后端测试权限 seed → Task 6
- ✅ 前端路由权限守卫 → Task 7
- ✅ 前端侧边栏权限 → Task 8
- ✅ 前端按钮级权限 → Task 9
- ✅ 全量测试验证 → Task 10

**2. 占位符扫描:** 无 TBD/TODO，所有步骤包含具体代码和命令。

**3. 类型一致性:** 权限码格式统一为 `{module}:{action}`，与 seed.py 定义一致。

**4. 范围检查:** 聚焦于权限细粒度化，不包含无关重构。
