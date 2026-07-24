# 行业类型管理模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在系统设置模块下新增行业类型管理功能（增删改查），并初始化种子数据解决 staging 环境空表问题。

**Architecture:** 后端新增 REST API 路由 + Service 层，前端新增页面组件 + API 封装，通过 alembic 迁移初始化种子数据。

**Tech Stack:** Python 3.12 + Sanic 22.12 + SQLAlchemy 2.0 + Vue 3.4 + Arco Design 2.54 + TypeScript 5.3

---

## 文件结构概览

### 新增文件
| 文件路径 | 职责 |
| -------- | ---- |
| `backend/app/routes/industry_type_routes.py` | 行业类型 CRUD API 路由 |
| `backend/app/services/industry_type_service.py` | 行业类型业务逻辑层 |
| `backend/tests/unit/test_industry_type_service.py` | Service 层单元测试 |
| `backend/tests/integration/test_industry_type_routes.py` | 路由集成测试 |
| `frontend/src/views/system/IndustryTypes.vue` | 行业类型管理页面 |
| `frontend/src/api/industryTypes.ts` | 前端 API 封装 |
| `backend/alembic/versions/<timestamp>_seed_industry_types.py` | 种子数据迁移 |

### 修改文件
| 文件路径 | 改动内容 |
| -------- | -------- |
| `backend/app/main.py:96-125` | 注册新路由蓝图 |
| `backend/scripts/seed.py:42-111` | 新增权限定义 |
| `frontend/src/router/index.ts:117-132` | 新增路由配置 |
| `frontend/src/views/Dashboard.vue:391-406` | 新增侧边栏菜单项 |

---

## Task 1: 后端 Service 层

**Files:**
- Create: `backend/app/services/industry_type_service.py`
- Test: `backend/tests/unit/test_industry_type_service.py`

- [ ] **Step 1: 创建 Service 层实现**

```python
"""行业类型服务 - 行业类型 CRUD 操作"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.industry_type import IndustryType


class IndustryTypeService:
    """行业类型业务逻辑"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all(self) -> list[IndustryType]:
        """获取所有未删除的行业类型，按 sort_order 升序"""
        stmt = (
            select(IndustryType)
            .where(IndustryType.deleted_at.is_(None))
            .order_by(IndustryType.sort_order.asc())
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, id: int) -> IndustryType | None:
        """根据 ID 获取行业类型"""
        stmt = select(IndustryType).where(
            IndustryType.id == id,
            IndustryType.deleted_at.is_(None),
        )
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, name: str, sort_order: int) -> IndustryType:
        """新增行业类型，校验名称唯一性"""
        industry_type = IndustryType(name=name, sort_order=sort_order)
        self.db_session.add(industry_type)
        await self.db_session.commit()
        await self.db_session.refresh(industry_type)
        return industry_type

    async def update(self, id: int, name: str, sort_order: int) -> IndustryType | None:
        """更新行业类型，校验名称唯一性"""
        industry_type = await self.get_by_id(id)
        if industry_type is None:
            return None
        industry_type.name = name
        industry_type.sort_order = sort_order
        await self.db_session.commit()
        await self.db_session.refresh(industry_type)
        return industry_type

    async def soft_delete(self, id: int) -> bool:
        """软删除行业类型"""
        from sqlalchemy import update
        from datetime import datetime

        stmt = (
            update(IndustryType)
            .where(IndustryType.id == id, IndustryType.deleted_at.is_(None))
            .values(deleted_at=datetime.utcnow())
        )
        result = await self.db_session.execute(stmt)
        await self.db_session.commit()
        return result.rowcount > 0
```

- [ ] **Step 2: 创建 Service 层单元测试**

```python
"""行业类型服务单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.industry_type_service import IndustryTypeService
from app.models.industry_type import IndustryType


@pytest.fixture
def mock_db_session():
    """模拟数据库会话"""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def service(mock_db_session):
    """创建 IndustryTypeService 实例"""
    return IndustryTypeService(mock_db_session)


class TestIndustryTypeService_GetAll:
    """测试 get_all 方法"""

    async def test_returns_sorted_list(self, service, mock_db_session):
        """返回按 sort_order 升序排列的行业类型"""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [
            IndustryType(id=1, name="项目", sort_order=1),
            IndustryType(id=2, name="房产经纪", sort_order=2),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        result = await service.get_all()

        assert len(result) == 2
        assert result[0].name == "项目"
        assert result[1].name == "房产经纪"

    async def test_filters_deleted_records(self, service, mock_db_session):
        """过滤已删除的记录"""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        await service.get_all()

        # 验证 SQL 包含 deleted_at.is_(None) 过滤
        call_args = mock_db_session.execute.call_args
        stmt = call_args[0][0]
        assert "deleted_at" in str(stmt)


class TestIndustryTypeService_GetById:
    """测试 get_by_id 方法"""

    async def test_returns_industry_type(self, service, mock_db_session):
        """返回指定 ID 的行业类型"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = IndustryType(
            id=1, name="项目", sort_order=1
        )
        mock_db_session.execute.return_value = mock_result

        result = await service.get_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.name == "项目"

    async def test_returns_none_for_not_found(self, service, mock_db_session):
        """不存在的 ID 返回 None"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await service.get_by_id(999)

        assert result is None


class TestIndustryTypeService_Create:
    """测试 create 方法"""

    async def test_creates_industry_type(self, service, mock_db_session):
        """成功创建行业类型"""
        mock_db_session.refresh = AsyncMock()

        result = await service.create("测试行业", 10)

        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()
        assert result.name == "测试行业"
        assert result.sort_order == 10


class TestIndustryTypeService_Update:
    """测试 update 方法"""

    async def test_updates_industry_type(self, service, mock_db_session):
        """成功更新行业类型"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = IndustryType(
            id=1, name="旧名称", sort_order=1
        )
        mock_db_session.execute.return_value = mock_result
        mock_db_session.refresh = AsyncMock()

        result = await service.update(1, "新名称", 5)

        assert result is not None
        assert result.name == "新名称"
        assert result.sort_order == 5
        mock_db_session.commit.assert_awaited_once()

    async def test_returns_none_for_not_found(self, service, mock_db_session):
        """不存在的 ID 返回 None"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await service.update(999, "新名称", 5)

        assert result is None


class TestIndustryTypeService_SoftDelete:
    """测试 soft_delete 方法"""

    async def test_soft_deletes_industry_type(self, service, mock_db_session):
        """成功软删除行业类型"""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        result = await service.soft_delete(1)

        assert result is True
        mock_db_session.commit.assert_awaited_once()

    async def test_returns_false_for_not_found(self, service, mock_db_session):
        """不存在的 ID 返回 False"""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db_session.execute.return_value = mock_result

        result = await service.soft_delete(999)

        assert result is False
```

- [ ] **Step 3: 运行测试验证**

```bash
cd backend && source .venv/bin/activate
pytest tests/unit/test_industry_type_service.py -v
```

预期：所有测试通过

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/industry_type_service.py
git add backend/tests/unit/test_industry_type_service.py
git commit -m "feat(industry-types): add IndustryTypeService with unit tests"
```

---

## Task 2: 后端 API 路由

**Files:**
- Create: `backend/app/routes/industry_type_routes.py`
- Modify: `backend/app/main.py:96-125`
- Test: `backend/tests/integration/test_industry_type_routes.py`

- [ ] **Step 1: 创建路由文件**

```python
"""行业类型管理路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.industry_type_service import IndustryTypeService
from ..middleware.auth import auth_required

industry_type_bp = Blueprint("industry_types", url_prefix="/api/v1/industry-types")


@industry_type_bp.get("")
@auth_required
async def get_industry_types(request: Request):
    """
    获取行业类型列表

    Response:
    - data: list of {id, name, sort_order, created_at}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    industry_types = await service.get_all()

    return json(
        {
            "code": 0,
            "message": "success",
            "data": [
                {
                    "id": it.id,
                    "name": it.name,
                    "sort_order": it.sort_order,
                    "created_at": it.created_at.isoformat() if it.created_at else None,
                }
                for it in industry_types
            ],
        }
    )


@industry_type_bp.post("")
@auth_required
async def create_industry_type(request: Request):
    """
    新增行业类型

    Request Body:
    - name: str (required)
    - sort_order: int (required)

    Response:
    - data: {id, name, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    data = request.json
    name = data.get("name")
    sort_order = data.get("sort_order")

    if not name or sort_order is None:
        return json(
            {"code": 422, "message": "name 和 sort_order 为必填字段"},
            status=422,
        )

    industry_type = await service.create(name, sort_order)

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": industry_type.id,
                "name": industry_type.name,
                "sort_order": industry_type.sort_order,
            },
        },
        status=201,
    )


@industry_type_bp.put("/<id:int>")
@auth_required
async def update_industry_type(request: Request, id: int):
    """
    更新行业类型

    Request Body:
    - name: str (required)
    - sort_order: int (required)

    Response:
    - data: {id, name, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    data = request.json
    name = data.get("name")
    sort_order = data.get("sort_order")

    if not name or sort_order is None:
        return json(
            {"code": 422, "message": "name 和 sort_order 为必填字段"},
            status=422,
        )

    industry_type = await service.update(id, name, sort_order)

    if industry_type is None:
        return json(
            {"code": 404, "message": "行业类型不存在"},
            status=404,
        )

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "id": industry_type.id,
                "name": industry_type.name,
                "sort_order": industry_type.sort_order,
            },
        }
    )


@industry_type_bp.delete("/<id:int>")
@auth_required
async def delete_industry_type(request: Request, id: int):
    """
    软删除行业类型

    Response:
    - success: true/false
    """
    db_session: AsyncSession = request.ctx.db_session
    service = IndustryTypeService(db_session)

    success = await service.soft_delete(id)

    if not success:
        return json(
            {"code": 404, "message": "行业类型不存在"},
            status=404,
        )

    return json(
        {
            "code": 0,
            "message": "success",
        }
    )
```

- [ ] **Step 2: 注册路由到 main.py**

在 `backend/app/main.py` 的蓝图导入区域（约第 109 行）添加：

```python
from .routes.industry_type_routes import industry_type_bp
```

在蓝图注册区域（约第 125 行）添加：

```python
app.blueprint(industry_type_bp)
```

- [ ] **Step 3: 创建集成测试**

```python
"""行业类型路由集成测试"""

import pytest
from app.main import create_app


@pytest.fixture
async def app(mock_db_engine):
    """创建测试应用"""
    app = create_app("test_app", database_engine=mock_db_engine)
    return app


@pytest.fixture
async def test_client(app):
    """创建测试客户端"""
    return app.test_client


@pytest.fixture
async def auth_headers(test_client):
    """创建认证头"""
    # 先登录获取 token
    _req, login_resp = await test_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


class TestGetIndustryTypes:
    """测试 GET /api/v1/industry-types"""

    async def test_requires_auth(self, test_client):
        """未认证返回 401"""
        _req, response = await test_client.get("/api/v1/industry-types")
        assert response.status == 401

    async def test_returns_success(self, test_client, auth_headers):
        """认证成功返回行业类型列表"""
        _req, response = await test_client.get(
            "/api/v1/industry-types", headers=auth_headers
        )
        assert response.status == 200
        assert response.json["code"] == 0
        assert isinstance(response.json["data"], list)


class TestCreateIndustryType:
    """测试 POST /api/v1/industry-types"""

    async def test_requires_auth(self, test_client):
        """未认证返回 401"""
        _req, response = await test_client.post("/api/v1/industry-types")
        assert response.status == 401

    async def test_creates_success(self, test_client, auth_headers):
        """成功创建行业类型"""
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "测试行业", "sort_order": 100},
            headers=auth_headers,
        )
        assert response.status == 201
        assert response.json["data"]["name"] == "测试行业"

    async def test_validates_required_fields(self, test_client, auth_headers):
        """缺少必填字段返回 422"""
        _req, response = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "测试行业"},
            headers=auth_headers,
        )
        assert response.status == 422


class TestUpdateIndustryType:
    """测试 PUT /api/v1/industry-types/{id}"""

    async def test_requires_auth(self, test_client):
        """未认证返回 401"""
        _req, response = await test_client.put("/api/v1/industry-types/1")
        assert response.status == 401

    async def test_updates_success(self, test_client, auth_headers):
        """成功更新行业类型"""
        # 先创建一个
        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "原始名称", "sort_order": 1},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        # 更新
        _req, response = await test_client.put(
            f"/api/v1/industry-types/{industry_id}",
            json={"name": "新名称", "sort_order": 2},
            headers=auth_headers,
        )
        assert response.status == 200
        assert response.json["data"]["name"] == "新名称"

    async def test_returns_404_for_not_found(self, test_client, auth_headers):
        """不存在的 ID 返回 404"""
        _req, response = await test_client.put(
            "/api/v1/industry-types/99999",
            json={"name": "新名称", "sort_order": 1},
            headers=auth_headers,
        )
        assert response.status == 404


class TestDeleteIndustryType:
    """测试 DELETE /api/v1/industry-types/{id}"""

    async def test_requires_auth(self, test_client):
        """未认证返回 401"""
        _req, response = await test_client.delete("/api/v1/industry-types/1")
        assert response.status == 401

    async def test_deletes_success(self, test_client, auth_headers):
        """成功软删除"""
        # 先创建一个
        _req, create_resp = await test_client.post(
            "/api/v1/industry-types",
            json={"name": "待删除", "sort_order": 1},
            headers=auth_headers,
        )
        industry_id = create_resp.json["data"]["id"]

        # 删除
        _req, response = await test_client.delete(
            f"/api/v1/industry-types/{industry_id}",
            headers=auth_headers,
        )
        assert response.status == 200

        # 验证不再出现在列表中
        _req, list_resp = await test_client.get(
            "/api/v1/industry-types", headers=auth_headers
        )
        ids = [item["id"] for item in list_resp.json["data"]]
        assert industry_id not in ids

    async def test_returns_404_for_not_found(self, test_client, auth_headers):
        """不存在的 ID 返回 404"""
        _req, response = await test_client.delete(
            "/api/v1/industry-types/99999",
            headers=auth_headers,
        )
        assert response.status == 404
```

- [ ] **Step 4: 运行测试验证**

```bash
cd backend && source .venv/bin/activate
pytest tests/integration/test_industry_type_routes.py -v
```

预期：所有测试通过

- [ ] **Step 5: 提交**

```bash
git add backend/app/routes/industry_type_routes.py
git add backend/app/main.py
git add backend/tests/integration/test_industry_type_routes.py
git commit -m "feat(industry-types): add CRUD API routes with integration tests"
```

---

## Task 3: 前端 API 封装

**Files:**
- Create: `frontend/src/api/industryTypes.ts`

- [ ] **Step 1: 创建 API 封装**

```typescript
import api from './index'
import { IndustryType } from '@/types'

/** 获取行业类型列表 */
export function getIndustryTypesList() {
  return api.get<{ data: IndustryType[] }>('/industry-types')
}

/** 新增行业类型 */
export function createIndustryType(data: { name: string; sort_order: number }) {
  return api.post<{ data: IndustryType }>('/industry-types', data)
}

/** 更新行业类型 */
export function updateIndustryType(id: number, data: { name: string; sort_order: number }) {
  return api.put<{ data: IndustryType }>(`/industry-types/${id}`, data)
}

/** 删除行业类型 */
export function deleteIndustryType(id: number) {
  return api.delete(`/industry-types/${id}`)
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/industryTypes.ts
git commit -m "feat(industry-types): add frontend API client"
```

---

## Task 4: 前端页面组件

**Files:**
- Create: `frontend/src/views/system/IndustryTypes.vue`

- [ ] **Step 1: 创建页面组件**

参考 `frontend/src/views/roles/Index.vue` 的风格，创建行业类型管理页面：

```vue
<template>
  <div class="industry-types-page">
    <div class="page-header">
      <div class="header-title">
        <h1>行业类型</h1>
        <p class="header-subtitle">管理系统行业类型字典</p>
      </div>
      <div class="header-actions">
        <a-button v-if="can('industry_types:manage')" type="primary" @click="handleCreate">
          <template #icon>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"
              />
            </svg>
          </template>
          新增行业类型
        </a-button>
      </div>
    </div>

    <div class="table-section">
      <a-table
        :columns="columns"
        :data="industryTypes"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #action="{ record }">
          <a-space>
            <a-button
              v-if="can('industry_types:manage')"
              type="text"
              size="small"
              @click="handleEdit(record)"
            >
              编辑
            </a-button>
            <a-popconfirm
              v-if="can('industry_types:manage')"
              content="确认删除该行业类型？删除后不会影响已关联的客户记录。"
              @ok="handleDelete(record.id)"
            >
              <a-button type="text" size="small" status="danger">
                删除
              </a-button>
            </a-popconfirm>
          </a-space>
        </template>
        <template #empty>
          <EmptyState title="暂无行业类型数据" description="点击「新增行业类型」添加第一个行业类型">
            <template #action>
              <a-button v-if="can('industry_types:manage')" type="primary" @click="handleCreate"
                >新增行业类型</a-button
              >
            </template>
          </EmptyState>
        </template>
        <template #created_at="{ record }">
          {{ formatDateTime(record.created_at) }}
        </template>
      </a-table>
    </div>

    <!-- 新增/编辑对话框 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="isEditMode ? '编辑行业类型' : '新增行业类型'"
      :confirm-loading="submitting"
      width="500px"
      @before-ok="handleSubmit"
      @cancel="handleModalCancel"
    >
      <a-form ref="formRef" :model="form" :rules="formRules" layout="vertical">
        <a-form-item field="name" label="行业类型名称">
          <a-input v-model="form.name" placeholder="请输入行业类型名称" />
        </a-form-item>
        <a-form-item field="sort_order" label="排序号">
          <a-input-number v-model="form.sort_order" placeholder="请输入排序号" :min="0" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { FormInstance } from '@arco-design/web-vue'
import { useUserStore } from '@/stores/user'
import {
  getIndustryTypesList,
  createIndustryType,
  updateIndustryType,
  deleteIndustryType,
} from '@/api/industryTypes'
import type { IndustryType } from '@/types'
import EmptyState from '@/components/EmptyState.vue'
import { formatDateTime } from '@/utils/formatters'

const userStore = useUserStore()
const can = (permission: string) => userStore.hasPermission(permission)

// ========== 状态管理 ==========
const loading = ref(false)
const industryTypes = ref<IndustryType[]>([])

// 分页
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: true,
  showPageSize: true,
})

// 表格列定义
const columns = [
  { title: 'ID', dataIndex: 'id', width: 70, align: 'right' as const },
  { title: '行业类型名称', dataIndex: 'name', width: 200 },
  { title: '排序号', dataIndex: 'sort_order', width: 100, align: 'center' as const },
  { title: '创建时间', slotName: 'created_at', width: 160 },
  { title: '操作', slotName: 'action', width: 150, fixed: 'right' as const },
]

// ========== 表单 ==========
const modalVisible = ref(false)
const isEditMode = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)

const form = reactive({
  name: '',
  sort_order: 0,
})

const formRules = {
  name: [{ required: true, message: '请输入行业类型名称' }],
  sort_order: [{ required: true, message: '请输入排序号' }],
}

// ========== 数据加载 ==========
const loadIndustryTypes = async () => {
  loading.value = true
  try {
    const res = await getIndustryTypesList()
    industryTypes.value = res.data?.data || res.data || []
    pagination.total = industryTypes.value.length
  } catch (error) {
    Message.error('加载行业类型失败')
    console.error('Failed to load industry types:', error)
  } finally {
    loading.value = false
  }
}

// ========== 事件处理 ==========
const handleCreate = () => {
  isEditMode.value = false
  editingId.value = null
  form.name = ''
  form.sort_order = 0
  modalVisible.value = true
}

const handleEdit = (record: IndustryType) => {
  isEditMode.value = true
  editingId.value = record.id
  form.name = record.name
  form.sort_order = record.sort_order
  modalVisible.value = true
}

const handleSubmit = async () => {
  try {
    submitting.value = true
    if (isEditMode.value && editingId.value !== null) {
      await updateIndustryType(editingId.value, {
        name: form.name,
        sort_order: form.sort_order,
      })
      Message.success('更新成功')
    } else {
      await createIndustryType({
        name: form.name,
        sort_order: form.sort_order,
      })
      Message.success('创建成功')
    }
    await loadIndustryTypes()
    return true
  } catch (error) {
    Message.error(isEditMode.value ? '更新失败' : '创建失败')
    console.error('Failed to save industry type:', error)
    return false
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    await deleteIndustryType(id)
    Message.success('删除成功')
    await loadIndustryTypes()
  } catch (error) {
    Message.error('删除失败')
    console.error('Failed to delete industry type:', error)
  }
}

const handlePageChange = (page: number) => {
  pagination.current = page
}

const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize
  pagination.current = 1
}

const handleModalCancel = () => {
  formRef.value?.resetFields()
}

// ========== 生命周期 ==========
onMounted(() => {
  loadIndustryTypes()
})
</script>

<style scoped>
.industry-types-page {
  padding: 0;
  --neutral-1: #f7f8fa;
  --neutral-2: #eef0f3;
  --neutral-3: #e5e6eb;
  --neutral-4: #c9cdd4;
  --neutral-5: #a9aeb8;
  --neutral-6: #86909c;
  --neutral-7: #6b7785;
  --neutral-8: #4e5969;
  --neutral-9: #272e3b;
  --neutral-10: #1d2129;
  --primary-1: #e8f3ff;
  --primary-2: #b9d9ff;
  --primary-3: #8dbefb;
  --primary-4: #6ba3f7;
  --primary-5: #4e88f4;
  --primary-6: #3469ed;
  --primary-7: #2550d1;
  --primary-8: #1a3ab5;
  --primary-9: #112799;
  --primary-10: #0b1780;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header-title h1 {
  font-size: 20px;
  font-weight: 600;
  color: var(--neutral-10);
  margin: 0 0 4px;
}

.header-subtitle {
  font-size: 14px;
  color: var(--neutral-6);
  margin: 0;
}

.table-section {
  background: white;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/system/IndustryTypes.vue
git commit -m "feat(industry-types): add frontend management page"
```

---

## Task 5: 前端路由和导航

**Files:**
- Modify: `frontend/src/router/index.ts:117-132`
- Modify: `frontend/src/views/Dashboard.vue:391-406`

- [ ] **Step 1: 添加路由配置**

在 `frontend/src/router/index.ts` 的 `system` 子路由下新增：

```typescript
{
  path: 'industry-types',
  name: 'IndustryTypes',
  component: () => import('@/views/system/IndustryTypes.vue'),
  meta: { requiresPermission: 'industry_types:manage' },
},
```

修改后 system 路由部分应如下：

```typescript
{
  path: 'system',
  name: 'System',
  children: [
    {
      path: 'sync-logs',
      name: 'SyncLogs',
      component: () => import('@/views/system/SyncLogs.vue'),
      meta: { requiresPermission: 'system:view' },
    },
    {
      path: 'audit-logs',
      name: 'AuditLogs',
      component: () => import('@/views/system/AuditLogs.vue'),
      meta: { requiresPermission: 'system:view' },
    },
    {
      path: 'industry-types',
      name: 'IndustryTypes',
      component: () => import('@/views/system/IndustryTypes.vue'),
      meta: { requiresPermission: 'industry_types:manage' },
    },
  ],
},
```

- [ ] **Step 2: 添加侧边栏菜单项**

在 `frontend/src/views/Dashboard.vue` 的"系统设置"子菜单中添加（约第 391-406 行区域）：

找到以下代码段：

```html
<div v-show="expandedSubmenu === 'system' && !sidebarCollapsed" class="nav-submenu">
  <a
    v-if="can('system:view')"
    class="nav-subitem"
    :class="{ active: $route.name === 'SyncLogs' }"
    @click="$router.push('/system/sync-logs')"
    >同步日志</a
  >
  <a
    v-if="can('system:view')"
    class="nav-subitem"
    :class="{ active: $route.name === 'AuditLogs' }"
    @click="$router.push('/system/audit-logs')"
    >审计日志</a
  >
</div>
```

修改为：

```html
<div v-show="expandedSubmenu === 'system' && !sidebarCollapsed" class="nav-submenu">
  <a
    v-if="can('system:view')"
    class="nav-subitem"
    :class="{ active: $route.name === 'SyncLogs' }"
    @click="$router.push('/system/sync-logs')"
    >同步日志</a
  >
  <a
    v-if="can('system:view')"
    class="nav-subitem"
    :class="{ active: $route.name === 'AuditLogs' }"
    @click="$router.push('/system/audit-logs')"
    >审计日志</a
  >
  <a
    v-if="can('industry_types:manage')"
    class="nav-subitem"
    :class="{ active: $route.name === 'IndustryTypes' }"
    @click="$router.push('/system/industry-types')"
    >行业类型</a
  >
</div>
```

同时需要在收起模式的子菜单预览中也添加（约第 374-389 行区域）：

```html
<div v-if="sidebarCollapsed" class="submenu-popup">
  <a
    v-if="can('system:view')"
    class="nav-subitem"
    :class="{ active: $route.name === 'SyncLogs' }"
    @click="$router.push('/system/sync-logs')"
    >同步日志</a
  >
  <a
    v-if="can('system:view')"
    class="nav-subitem"
    :class="{ active: $route.name === 'AuditLogs' }"
    @click="$router.push('/system/audit-logs')"
    >审计日志</a
  >
  <a
    v-if="can('industry_types:manage')"
    class="nav-subitem"
    :class="{ active: $route.name === 'IndustryTypes' }"
    @click="$router.push('/system/industry-types')"
    >行业类型</a
  >
</div>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/router/index.ts
git add frontend/src/views/Dashboard.vue
git commit -m "feat(industry-types): add route and sidebar navigation"
```

---

## Task 6: 权限定义和种子数据

**Files:**
- Modify: `backend/scripts/seed.py:42-111`
- Create: `backend/alembic/versions/<timestamp>_seed_industry_types.py`

- [ ] **Step 1: 在 seed.py 中添加权限定义**

在 `backend/scripts/seed.py` 的 `ALL_PERMISSIONS` 列表中（约第 110 行附近，`webhooks:manage` 之后）添加：

```python
("industry_types:manage", "管理行业类型", "新增/编辑/删除行业类型", "system"),
```

- [ ] **Step 2: 创建 alembic 迁移文件**

生成新的迁移文件：

```bash
cd backend && source .venv/bin/activate
python -m alembic revision -m "seed industry types"
```

然后编辑生成的迁移文件，内容如下：

```python
"""seed industry types

Revision ID: <auto-generated>
Revises: <previous-revision>
Create Date: 2026-05-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    """初始化行业类型种子数据"""
    op.bulk_insert(
        sa.table(
            'industry_types',
            sa.column('name', sa.String),
            sa.column('sort_order', sa.Integer),
        ),
        [
            {'name': '项目', 'sort_order': 1},
            {'name': '房产经纪', 'sort_order': 2},
            {'name': '房产ERP', 'sort_order': 3},
            {'name': '房产平台', 'sort_order': 4},
            {'name': '公共安全', 'sort_order': 5},
            {'name': '租房', 'sort_order': 6},
            {'name': '待确认', 'sort_order': 7},
            {'name': '无', 'sort_order': 8},
        ],
    )


def downgrade() -> None:
    """回滚行业类型种子数据"""
    op.execute(
        "DELETE FROM industry_types WHERE name IN ('项目', '房产经纪', '房产ERP', '房产平台', '公共安全', '租房', '待确认', '无')"
    )
```

- [ ] **Step 3: 运行迁移验证**

```bash
cd backend && source .venv/bin/activate
python -m alembic upgrade head
```

验证数据已插入：

```bash
python -c "
from sqlalchemy import create_engine, text
from app.config import settings
sync_url = settings.database_url.replace('postgresql+asyncpg://', 'postgresql://')
engine = create_engine(sync_url)
with engine.connect() as conn:
    result = conn.execute(text('SELECT id, name, sort_order FROM industry_types ORDER BY sort_order'))
    for row in result:
        print(row)
"
```

预期输出 8 条行业类型记录。

- [ ] **Step 4: 提交**

```bash
git add backend/scripts/seed.py
git add backend/alembic/versions/<timestamp>_seed_industry_types.py
git commit -m "feat(industry-types): add permission definition and seed data migration"
```

---

## Task 7: 运行完整测试和验证

- [ ] **Step 1: 运行后端测试**

```bash
cd backend && source .venv/bin/activate
pytest tests/unit/test_industry_type_service.py tests/integration/test_industry_type_routes.py -v
```

- [ ] **Step 2: 运行代码质量检查**

```bash
cd backend && source .venv/bin/activate
black app/ tests/ && flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203
```

- [ ] **Step 3: 前端类型检查**

```bash
cd frontend
npm run type-check
```

- [ ] **Step 4: 前端构建验证**

```bash
cd frontend
npm run build
```

- [ ] **Step 5: 最终提交**

```bash
git status
git add .
git commit -m "chore: final verification and cleanup for industry-types feature"
```

---

## 部署后操作

1. **同步权限**：在 staging 服务器运行 `python scripts/seed.py` 同步新增权限
2. **验证 API**：访问 `GET /api/v1/industry-types` 确认返回 8 条数据
3. **验证前端**：登录系统设置，确认"行业类型"菜单项可见且可访问
