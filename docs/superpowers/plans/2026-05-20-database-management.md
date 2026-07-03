# 数据库管理功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在系统设置菜单下新增"数据库管理"模块，提供管理员专用的客户数据级联清空功能，含二次确认和审计日志记录。

**Architecture:** 新增后端路由 `POST /system/database/clear` 处理级联删除，新增前端页面 `DatabaseManagement.vue` 通过二次确认弹框调用 API，权限由 `system:database_clear` 控制。

**Tech Stack:** Python 3.12 + Sanic + SQLAlchemy 2.0 (后端), Vue 3 + TypeScript + Arco Design (前端)

---

### Task 1: 注册新权限 `system:database_clear`

**Files:**
- Modify: `backend/scripts/seed.py` (添加权限定义到 ALL_PERMISSIONS)

- [ ] **Step 1: 在 ALL_PERMISSIONS 系统管理区块添加新权限**

在 `backend/scripts/seed.py` 的 ALL_PERMISSIONS 列表中，系统管理部分（约第 94-98 行）添加：

```python
("system:database_clear", "数据清空", "清空客户及关联数据", "system"),
```

完整系统管理区块应变为：
```python
# ============================================================
# 系统管理 (4)
# ============================================================
("system:view", "查看系统", "查看同步/审计日志", "system"),
("system:export", "导出日志", "导出系统日志", "system"),
("system:settings", "系统设置", "修改系统配置", "system"),
("system:database_clear", "数据清空", "清空客户及关联数据", "system"),
```

- [ ] **Step 2: 验证权限注册**

运行种子脚本验证新权限可以正常创建：
```bash
cd backend && source .venv/bin/activate
python scripts/seed.py
```
期望输出包含 `✅ 创建权限: system:database_clear` 或 `⏭️ 权限已存在: system:database_clear`

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/seed.py
git commit -m "feat(system): add system:database_clear permission for data cleanup"
```

---

### Task 2: 创建后端数据库清空路由

**Files:**
- Create: `backend/app/routes/database_management.py`
- Modify: `backend/app/main.py` (注册蓝图)

- [ ] **Step 1: 创建数据库管理路由文件**

创建 `backend/app/routes/database_management.py`:

```python
"""数据库管理路由"""

from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import auth_required, require_permission
from ..utils.audit_helpers import create_audit_entry

database_bp = Blueprint("database_bp", url_prefix="/api/v1/system/database")


@database_bp.post("/clear")
@auth_required
@require_permission("system:database_clear")
async def clear_customer_data(request: Request):
    """
    级联清空所有客户及关联数据

    仅管理员可用，需要 system:database_clear 权限。
    操作不可逆，会删除以下数据：
    - customers (客户主表)
    - customer_profiles (客户画像)
    - customer_balances (客户余额)
    - customer_tags (客户标签关联)
    - profile_tags (画像标签关联)
    - invoices (结算单)
    - invoice_items (结算单明细)
    - consumption_records (消费流水)
    - daily_usage (每日用量)
    - pricing_rules (计费规则)
    - recharge_records (充值记录)

    操作会记录到 audit_logs 表。
    """
    db_session: AsyncSession = request.ctx.db_session
    user = request.ctx.user

    # 统计即将删除的客户数量
    count_result = await db_session.execute(select(func.count()).select_from("customers"))
    customer_count = count_result.scalar() or 0

    try:
        # 按依赖顺序删除
        # 1. 画像标签关联（通过 profile 关联到 customer）
        await db_session.execute(
            """
            DELETE FROM profile_tags
            WHERE profile_id IN (
                SELECT id FROM customer_profiles WHERE customer_id IN (SELECT id FROM customers)
            )
            """
        )

        # 2. 客户标签关联
        await db_session.execute(
            "DELETE FROM customer_tags WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 3. 结算单明细
        await db_session.execute(
            """
            DELETE FROM invoice_items
            WHERE invoice_id IN (
                SELECT id FROM invoices WHERE customer_id IN (SELECT id FROM customers)
            )
            """
        )

        # 4. 消费流水
        await db_session.execute(
            "DELETE FROM consumption_records WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 5. 每日用量
        await db_session.execute(
            "DELETE FROM daily_usage WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 6. 充值记录
        await db_session.execute(
            "DELETE FROM recharge_records WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 7. 计费规则
        await db_session.execute(
            "DELETE FROM pricing_rules WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 8. 结算单
        await db_session.execute(
            "DELETE FROM invoices WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 9. 客户余额（有 ondelete=CASCADE，但显式删除更安全）
        await db_session.execute(
            "DELETE FROM customer_balances WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 10. 客户画像
        await db_session.execute(
            "DELETE FROM customer_profiles WHERE customer_id IN (SELECT id FROM customers)"
        )

        # 11. 客户主表
        await db_session.execute("DELETE FROM customers")

        # 提交事务
        await db_session.commit()

        # 记录审计日志
        user_id = user.get("user_id")
        if user_id:
            await create_audit_entry(
                db_session=db_session,
                user_id=user_id,
                action="database_clear",
                module="system",
                changes={
                    "deleted_count": customer_count,
                    "tables_affected": [
                        "customers",
                        "customer_profiles",
                        "customer_balances",
                        "customer_tags",
                        "profile_tags",
                        "invoices",
                        "invoice_items",
                        "consumption_records",
                        "daily_usage",
                        "pricing_rules",
                        "recharge_records",
                    ],
                },
                operation_type="sensitive",
            )
            await db_session.commit()

        return json({
            "code": 200,
            "message": f"成功清空 {customer_count} 条客户数据",
            "data": {"deleted_count": customer_count},
        })

    except Exception as e:
        await db_session.rollback()
        return json({
            "code": 50001,
            "message": f"数据清空失败: {str(e)}",
        }, status=500)
```

- [ ] **Step 2: 在 main.py 中注册蓝图**

在 `backend/app/main.py` 中，导入并注册 `database_bp`：

在路由导入区域（约第 102-114 行）添加：
```python
from .routes.database_management import database_bp
```

在蓝图注册区域（约第 126-131 行）添加：
```python
app.blueprint(database_bp)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routes/database_management.py backend/app/main.py
git commit -m "feat(system): add database clear endpoint with cascade delete and audit logging"
```

---

### Task 3: 编写后端单元测试

**Files:**
- Create: `backend/tests/unit/test_database_management.py`

- [ ] **Step 1: 创建测试文件**

创建 `backend/tests/unit/test_database_management.py`:

```python
"""数据库管理路由单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routes.database_management import clear_customer_data


@pytest.fixture
def mock_request():
    """模拟请求上下文"""
    request = MagicMock()
    request.ctx = MagicMock()
    request.ctx.db_session = AsyncMock()
    request.ctx.db_session.execute = AsyncMock()
    request.ctx.db_session.commit = AsyncMock()
    request.ctx.db_session.rollback = AsyncMock()
    request.ctx.user = {"user_id": 1}
    return request


@pytest.fixture
def mock_scalar_result():
    """模拟 count 查询结果"""
    result = MagicMock()
    result.scalar = MagicMock(return_value=5)
    return result


@pytest.mark.asyncio
async def test_clear_customer_data_success(mock_request, mock_scalar_result):
    """测试成功清空客户数据"""
    mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_scalar_result)

    with patch(
        "app.routes.database_management.create_audit_entry", new_callable=AsyncMock
    ) as mock_audit:
        response = await clear_customer_data(mock_request)

    assert response.status == 200
    body = response.body
    assert body["code"] == 200
    assert "成功清空 5 条客户数据" in body["message"]
    assert body["data"]["deleted_count"] == 5

    # 验证审计日志被调用
    mock_audit.assert_called_once()


@pytest.mark.asyncio
async def test_clear_customer_data_rollback_on_error(mock_request):
    """测试异常时事务回滚"""
    mock_request.ctx.db_session.execute = AsyncMock(side_effect=Exception("DB error"))

    response = await clear_customer_data(mock_request)

    assert response.status == 500
    assert "数据清空失败" in response.body["message"]

    # 验证调用了 rollback
    mock_request.ctx.db_session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_clear_customer_data_zero_customers(mock_request, mock_scalar_result):
    """测试没有客户数据时清空"""
    mock_scalar_result.scalar = MagicMock(return_value=0)
    mock_request.ctx.db_session.execute = AsyncMock(return_value=mock_scalar_result)

    with patch(
        "app.routes.database_management.create_audit_entry", new_callable=AsyncMock
    ):
        response = await clear_customer_data(mock_request)

    assert response.status == 200
    assert response.body["data"]["deleted_count"] == 0
```

- [ ] **Step 2: 运行测试验证**

```bash
cd backend && source .venv/bin/activate
pytest tests/unit/test_database_management.py -v
```
期望：全部 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_database_management.py
git commit -m "test(system): add unit tests for database clear endpoint"
```

---

### Task 4: 创建前端数据库管理页面

**Files:**
- Create: `frontend/src/views/system/DatabaseManagement.vue`

- [ ] **Step 1: 创建数据库管理页面组件**

创建 `frontend/src/views/system/DatabaseManagement.vue`:

```vue
<template>
  <div class="database-management">
    <a-card :bordered="false">
      <template #title>
        <div class="card-header">
          <span>数据库管理</span>
        </div>
      </template>

      <a-alert type="warning" style="margin-bottom: 24px">
        以下操作不可逆，请谨慎执行。清空操作将删除所有客户及关联数据（含客户画像、标签、结算记录、发票等）。
      </a-alert>

      <a-descriptions :column="1" bordered style="margin-bottom: 24px">
        <a-descriptions-item label="操作名称">清空客户数据</a-descriptions-item>
        <a-descriptions-item label="影响范围">
          customers、customer_profiles、customer_balances、customer_tags、profile_tags、
          invoices、invoice_items、consumption_records、daily_usage、pricing_rules、recharge_records
        </a-descriptions-item>
        <a-descriptions-item label="权限要求">需具备「数据清空」权限</a-descriptions-item>
      </a-descriptions>

      <a-space>
        <a-button
          status="danger"
          :loading="clearing"
          @click="handleClearConfirm"
        >
          清空客户数据
        </a-button>
      </a-space>

      <div v-if="lastResult" class="result-info">
        <a-alert
          :type="lastResult.success ? 'success' : 'error'"
          style="margin-top: 16px"
        >
          {{ lastResult.message }}
        </a-alert>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import axios from 'axios'

const clearing = ref(false)
const lastResult = ref<{ success: boolean; message: string } | null>(null)

const handleClearConfirm = () => {
  Modal.confirm({
    title: '确认清空客户数据',
    content:
      '此操作将不可恢复地删除所有客户及关联数据（含客户画像、标签、结算记录、发票等），确定继续？',
    okText: '确定清空',
    cancelText: '取消',
    okButtonProps: { status: 'danger' },
    hideCancel: false,
    onBeforeOk: async () => {
      clearing.value = true
      try {
        const response = await axios.post('/api/v1/system/database/clear')
        const { data } = response
        lastResult.value = {
          success: true,
          message: data.message || `成功清空 ${data.data?.deleted_count || 0} 条客户数据`,
        }
        Message.success(lastResult.value.message)
      } catch (error: any) {
        const msg =
          error.response?.data?.message || '数据清空失败，请稍后重试'
        lastResult.value = { success: false, message: msg }
        Message.error(msg)
      } finally {
        clearing.value = false
      }
      // Modal 的 onBeforeOk 返回 false 阻止关闭（让用户看到结果）
      return false
    },
  })
}
</script>

<style scoped>
.database-management {
  padding: 16px;
}

.card-header {
  font-size: 16px;
  font-weight: 600;
}

.result-info {
  margin-top: 16px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/system/DatabaseManagement.vue
git commit -m "feat(system): add database management page with clear data function"
```

---

### Task 5: 配置前端路由和菜单

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/Dashboard.vue`

- [ ] **Step 1: 添加路由配置**

在 `frontend/src/router/index.ts` 的 system 子路由中（约第 138-143 行）添加：

```typescript
{
  path: 'database-management',
  name: 'DatabaseManagement',
  component: () => import('@/views/system/DatabaseManagement.vue'),
  meta: { requiresPermission: 'system:database_clear' },
},
```

- [ ] **Step 2: 添加侧边栏菜单项**

在 `frontend/src/views/Dashboard.vue` 中，系统设置子菜单区域（约第 395-419 行），在"行业类型"菜单项后添加数据库管理入口。

找到收起模式下的子菜单（`v-if="sidebarCollapsed"` 的 `.submenu-popup` 内），在 `行业类型` 后添加：
```html
<a
  v-if="can('system:database_clear')"
  class="nav-subitem"
  :class="{ active: $route.name === 'DatabaseManagement' }"
  @click="$router.push('/system/database-management')"
  >数据库管理</a
>
```

找到展开模式下的子菜单（`v-show="expandedSubmenu === 'system' && !sidebarCollapsed"` 的 `.nav-submenu` 内），在 `行业类型` 后添加：
```html
<a
  v-if="can('system:database_clear')"
  class="nav-subitem"
  :class="{ active: $route.name === 'DatabaseManagement' }"
  @click="$router.push('/system/database-management')"
  >数据库管理</a
>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/views/Dashboard.vue
git commit -m "feat(system): add database management route and sidebar menu"
```

---

### Task 6: 整体验证

- [ ] **Step 1: 后端代码质量检查**

```bash
cd backend && source .venv/bin/activate
ruff format app/routes/database_management.py tests/unit/test_database_management.py
ruff check app/routes/database_management.py tests/unit/test_database_management.py
```

- [ ] **Step 2: 前端构建检查**

```bash
cd frontend
npm run type-check
npm run build
```

- [ ] **Step 3: 运行全部测试**

```bash
cd backend && source .venv/bin/activate
pytest tests/ -v --tb=short
```

- [ ] **Step 4: 提交最终修复（如有）**

```bash
git add -A
git commit -m "chore: final formatting and lint fixes for database management feature"
```
