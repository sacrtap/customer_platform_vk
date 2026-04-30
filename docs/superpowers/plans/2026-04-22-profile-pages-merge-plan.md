# 画像管理与画像分析页面合并实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除冗余的 `/profiles` 画像管理页面，统一使用 `/analytics/profile` 画像分析页面，并将相关后端权限迁移到 `analytics:*` 体系。

**Architecture:** 前端删除 `/profiles` 页面及路由，清理侧边栏导航；后端将 `profiles:*` 权限替换为 `analytics:view` 和新增的 `analytics:profile_tag_edit` 权限，确保画像标签 API 权限连续。

**Tech Stack:** Vue 3 + TypeScript (前端), Python + Sanic (后端), PostgreSQL (权限数据)

---

## 文件结构映射

### 删除的文件
- `frontend/src/views/profiles/Dashboard.vue` — 画像管理页面（整个文件删除）
- `frontend/src/views/profiles/` — 目录（如为空则删除）

### 修改的文件
- `frontend/src/router/index.ts:111-115` — 删除 `/profiles` 路由
- `frontend/src/views/Dashboard.vue:149-172` — 删除侧边栏"画像管理"菜单项
- `backend/scripts/seed.py:71-73` — 删除 `profiles:*` 权限，新增 `analytics:profile_tag_edit`
- `backend/app/routes/tags.py:403,430,452` — 权限装饰器替换
- `backend/tests/integration/conftest.py:152-153,315-316` — 测试权限数据更新

### 无需修改的文件
- `frontend/src/views/analytics/Profile.vue` — 保留不动
- `backend/app/routes/analytics.py` — 画像分析 API，不受影响

---

### Task 1: 删除前端 `/profiles` 页面文件

**Files:**
- Delete: `frontend/src/views/profiles/Dashboard.vue`
- Delete: `frontend/src/views/profiles/` (directory if empty)

- [ ] **Step 1: 删除画像管理页面文件**

```bash
rm /Users/sacrtap/Documents/trae_projects/customer_platform_vk/frontend/src/views/profiles/Dashboard.vue
```

- [ ] **Step 2: 检查目录是否为空，如为空则删除**

```bash
rmdir /Users/sacrtap/Documents/trae_projects/customer_platform_vk/frontend/src/views/profiles/ 2>/dev/null || echo "Directory not empty or already removed"
```

- [ ] **Step 3: 验证文件已删除**

```bash
ls /Users/sacrtap/Documents/trae_projects/customer_platform_vk/frontend/src/views/profiles/ 2>&1 || echo "Directory removed successfully"
```

Expected: "No such file or directory"

- [ ] **Step 4: Commit**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && git add -A && git commit -m "refactor(frontend): remove /profiles dashboard page"
```

---

### Task 2: 删除前端 `/profiles` 路由

**Files:**
- Modify: `frontend/src/router/index.ts:111-115`

- [ ] **Step 1: 读取当前路由配置**

确认要删除的路由代码（行 111-115）：
```typescript
      {
        path: 'profiles',
        name: 'ProfileDashboard',
        component: () => import('@/views/profiles/Dashboard.vue'),
        meta: { requiresPermission: 'profiles:view' },
      },
```

- [ ] **Step 2: 删除路由配置**

使用 sed 删除行 110-116（包含前面的逗号处理）：

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && sed -i '' '110,116d' frontend/src/router/index.ts
```

删除后，确保 `analytics` 路由块的 `children` 数组语法正确（最后一个子路由后面不能有逗号，或者逗号位置正确）。

- [ ] **Step 3: 验证路由文件语法**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/frontend && npx tsc --noEmit src/router/index.ts 2>&1 | head -20
```

Expected: 无错误输出，或仅有与本次修改无关的既有错误。

- [ ] **Step 4: Commit**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && git add frontend/src/router/index.ts && git commit -m "refactor(frontend): remove /profiles route"
```

---

### Task 3: 删除侧边栏"画像管理"菜单项

**Files:**
- Modify: `frontend/src/views/Dashboard.vue:149-172`

- [ ] **Step 1: 定位并删除侧边栏菜单项**

要删除的代码块（行 149-172）：
```vue
          <a
            v-if="can('profiles:view')"
            class="nav-item"
            :class="{ active: $route.path.startsWith('/profiles') }"
            @click="$router.push('/profiles')"
          >
            <div class="nav-item-icon">
              <svg
                aria-hidden="true"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
                />
              </svg>
            </div>
            <span class="nav-item-label">画像管理</span>
          </a>
```

使用 Python 脚本精确删除该代码块：

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && python3 << 'PYEOF'
with open('frontend/src/views/Dashboard.vue', 'r') as f:
    lines = f.readlines()

# 删除行 149-172（0-indexed: 148-171）
del lines[148:172]

with open('frontend/src/views/Dashboard.vue', 'w') as f:
    f.writelines(lines)

print("Deleted lines 149-172 from Dashboard.vue")
PYEOF
```

- [ ] **Step 2: 验证文件无语法错误**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/frontend && npx vue-tsc --noEmit 2>&1 | head -20
```

Expected: 无新增错误。

- [ ] **Step 3: Commit**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && git add frontend/src/views/Dashboard.vue && git commit -m "refactor(frontend): remove profile management sidebar menu"
```

---

### Task 4: 更新后端权限定义（seed.py）

**Files:**
- Modify: `backend/scripts/seed.py`

- [ ] **Step 1: 读取当前 seed.py 权限定义**

当前权限定义（约行 65-73）：
```python
    ("analytics:view", "查看分析", "查看所有分析报表", "analytics"),
    ("analytics:export", "导出报表", "导出分析数据", "analytics"),
    ("analytics:forecast_edit", "编辑预测", "修改预测模型参数", "analytics"),
    # ...
    ("profiles:view", "查看画像", "查看客户画像", "profiles"),
    ("profiles:edit", "编辑画像", "修改画像规则和标签", "profiles"),
    ("profiles:export", "导出画像", "导出画像数据", "profiles"),
```

- [ ] **Step 2: 修改权限定义**

使用 Python 脚本替换：

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && python3 << 'PYEOF'
with open('backend/scripts/seed.py', 'r') as f:
    content = f.read()

# 删除 profiles 相关权限行
content = content.replace(
    '    ("profiles:view", "查看画像", "查看客户画像", "profiles"),\n',
    ''
)
content = content.replace(
    '    ("profiles:edit", "编辑画像", "修改画像规则和标签", "profiles"),\n',
    ''
)
content = content.replace(
    '    ("profiles:export", "导出画像", "导出画像数据", "profiles"),\n',
    ''
)

# 在 analytics:forecast_edit 之后添加新权限
content = content.replace(
    '    ("analytics:forecast_edit", "编辑预测", "修改预测模型参数", "analytics"),',
    '''    ("analytics:forecast_edit", "编辑预测", "修改预测模型参数", "analytics"),
    ("analytics:profile_tag_edit", "编辑画像标签", "管理画像标签关联", "analytics"),'''
)

with open('backend/scripts/seed.py', 'w') as f:
    f.write(content)

print("Updated seed.py permissions")
PYEOF
```

- [ ] **Step 3: 验证修改**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && grep -n "profiles:\|analytics:" backend/scripts/seed.py
```

Expected output:
```
65:    ("analytics:view", "查看分析", "查看所有分析报表", "analytics"),
66:    ("analytics:export", "导出报表", "导出分析数据", "analytics"),
67:    ("analytics:forecast_edit", "编辑预测", "修改预测模型参数", "analytics"),
68:    ("analytics:profile_tag_edit", "编辑画像标签", "管理画像标签关联", "analytics"),
```

不再包含 `profiles:` 开头的权限。

- [ ] **Step 4: Commit**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && git add backend/scripts/seed.py && git commit -m "refactor(backend): migrate profiles:* permissions to analytics:*, add analytics:profile_tag_edit"
```

---

### Task 5: 更新后端 tags.py 权限装饰器

**Files:**
- Modify: `backend/app/routes/tags.py:403,430,452`

- [ ] **Step 1: 读取并确认当前权限装饰器**

当前代码：
- Line 403: `@require_permission("profiles:view")` — get_profile_tags
- Line 430: `@require_permission("profiles:edit")` — add_profile_tag
- Line 452: `@require_permission("profiles:edit")` — remove_profile_tag

- [ ] **Step 2: 替换权限装饰器**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && sed -i '' 's/@require_permission("profiles:view")/@require_permission("analytics:view")/g' backend/app/routes/tags.py && sed -i '' 's/@require_permission("profiles:edit")/@require_permission("analytics:profile_tag_edit")/g' backend/app/routes/tags.py
```

- [ ] **Step 3: 验证替换结果**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && grep -n "profiles:\|analytics:" backend/app/routes/tags.py
```

Expected: 不再包含 `profiles:` 权限，替换为 `analytics:view` 和 `analytics:profile_tag_edit`。

- [ ] **Step 4: Commit**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && git add backend/app/routes/tags.py && git commit -m "refactor(backend): update tags.py permission decorators from profiles:* to analytics:*"
```

---

### Task 6: 更新集成测试权限数据

**Files:**
- Modify: `backend/tests/integration/conftest.py`

- [ ] **Step 1: 定位需要修改的代码行**

当前代码（约行 152-153）：
```python
        ("profiles:view", "查看画像", "profiles"),
        ("profiles:edit", "编辑画像", "profiles"),
```

以及测试角色权限列表（约行 315-316）：
```python
        "profiles:view",
        "profiles:edit",
```

- [ ] **Step 2: 替换权限定义**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && python3 << 'PYEOF'
with open('backend/tests/integration/conftest.py', 'r') as f:
    content = f.read()

# 替换权限定义部分（元组列表）
content = content.replace(
    '        ("profiles:view", "查看画像", "profiles"),\n',
    '        ("analytics:profile_tag_edit", "编辑画像标签", "analytics"),\n'
)
content = content.replace(
    '        ("profiles:edit", "编辑画像", "profiles"),\n',
    ''
)

# 替换角色权限列表中的权限字符串
content = content.replace(
    '"profiles:view",\n',
    ''
)
content = content.replace(
    '"profiles:edit",\n',
    '        "analytics:profile_tag_edit",\n'
)

with open('backend/tests/integration/conftest.py', 'w') as f:
    f.write(content)

print("Updated conftest.py permissions")
PYEOF
```

- [ ] **Step 3: 验证修改**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && grep -n "profiles:\|analytics:" backend/tests/integration/conftest.py | head -20
```

Expected: 不再包含 `profiles:` 权限。

- [ ] **Step 4: Commit**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && git add backend/tests/integration/conftest.py && git commit -m "refactor(tests): update integration test permissions from profiles:* to analytics:*"
```

---

### Task 7: 运行全量测试验证

**Files:**
- Test: All backend tests

- [ ] **Step 1: 运行后端全量测试**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/backend && source .venv/bin/activate && pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests pass. If any test references `profiles:view` or `profiles:edit` 权限字符串，需要额外修复。

- [ ] **Step 2: 检查前端 TypeScript 类型**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/frontend && npm run type-check 2>&1 | tail -20
```

Expected: No new type errors.

- [ ] **Step 3: 检查前端构建**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk/frontend && npm run build 2>&1 | tail -20
```

Expected: Build succeeds without errors.

- [ ] **Step 4: 如果测试失败，修复后重新提交**

根据失败信息定位问题并修复，然后：

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && git add -A && git commit -m "fix: address test failures from profile pages merge"
```

---

### Task 8: 更新 Graphify 知识图谱

**Files:**
- Run: `graphify update .`

- [ ] **Step 1: 更新知识图谱**

```bash
cd /Users/sacrtap/Documents/trae_projects/customer_platform_vk && graphify update .
```

---

## 总结

本计划通过 8 个 Task 完成画像管理与画像分析页面的合并：

| Task | 操作 | 涉及文件 |
|------|------|---------|
| 1 | 删除前端 `/profiles` 页面 | `profiles/Dashboard.vue` |
| 2 | 删除前端 `/profiles` 路由 | `router/index.ts` |
| 3 | 删除侧边栏"画像管理"菜单 | `Dashboard.vue` |
| 4 | 更新后端权限定义 | `seed.py` |
| 5 | 更新标签 API 权限装饰器 | `tags.py` |
| 6 | 更新集成测试权限数据 | `conftest.py` |
| 7 | 全量测试验证 | - |
| 8 | 更新知识图谱 | - |

权限迁移映射：
- `profiles:view` → `analytics:view`
- `profiles:edit` → `analytics:profile_tag_edit`（新增）
- `profiles:export` → 删除（无引用）
