# 行业类型字典化改造 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将客户管理"业务类型"筛选项改造为"行业类型"，数据源从硬编码改为数据库字典表。

**Architecture:** 新建 `industry_types` 数据库表 + SQLAlchemy 模型，新增 Alembic 迁移，新增 `GET /api/v1/dicts/industry_types` 路由，前端筛选标签和下拉数据源改为 API 动态加载。

**Tech Stack:** Python 3.12 + Sanic + SQLAlchemy 2.0 + Alembic + Vue 3 + TypeScript + Arco Design

---

## 文件结构总览

| 操作   | 文件路径                                                            |
| ------ | ------------------------------------------------------------------- |
| 新建   | `backend/app/models/industry_type.py`                               |
| 修改   | `backend/app/models/__init__.py`                                    |
| 新建   | `backend/app/services/dict_service.py`                              |
| 新建   | `backend/app/routes/dict_routes.py`                                 |
| 修改   | `backend/app/routes/__init__.py`                                    |
| 新建   | `backend/alembic/versions/XXX_add_industry_types_table.py`          |
| 新建   | `backend/tests/unit/test_dict_service.py`                           |
| 新建   | `backend/tests/integration/test_dict_routes.py`                     |
| 修改   | `frontend/src/api/customers.ts`                                     |
| 修改   | `frontend/src/views/customers/Index.vue`                            |
| 修改   | `frontend/src/views/customers/Detail.vue`                           |
| 修改   | `frontend/src/types/index.ts`                                       |

---

## 任务 1：数据库模型 — industry_types 表

**Files:**
- Create: `backend/app/models/industry_type.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/unit/test_models.py`

### 步骤 1：查看 BaseModel 基类模式

- [ ] **读取** `backend/app/models/base.py`，确认 `BaseModel` 提供的字段（id, created_at, updated_at, deleted_at）

### 步骤 2：创建 IndustryType 模型

- [ ] **创建** `backend/app/models/industry_type.py`，内容如下：

```python
"""行业类型字典模型"""

from sqlalchemy import Column, String, Integer
from .base import BaseModel


class IndustryType(BaseModel):
    """行业类型字典表"""

    __tablename__ = "industry_types"

    name = Column(String(50), nullable=False, unique=True, index=True)
    sort_order = Column(Integer, nullable=False, default=0, index=True)

    def __repr__(self):
        return f"<IndustryType {self.name}>"
```

**说明**: `BaseModel` 已提供 `id`(Integer, PK, autoincrement)、`created_at`、`updated_at`、`deleted_at`。

### 步骤 3：注册模型

- [ ] **读取** `backend/app/models/__init__.py`
- [ ] **修改** `backend/app/models/__init__.py`，添加导入：

```python
from .industry_type import IndustryType
```

### 步骤 4：运行模型测试

- [ ] **运行**: `cd backend && source .venv/bin/activate && pytest tests/unit/test_models.py -v`
- [ ] **确认**: 现有测试仍通过

- [ ] **提交**:
```bash
git add backend/app/models/industry_type.py backend/app/models/__init__.py
git commit -m "feat: add IndustryType model for industry_types dictionary table"
```

---

## 任务 2：字典服务层

**Files:**
- Create: `backend/app/services/dict_service.py`
- Test: `backend/tests/unit/test_dict_service.py`

### 步骤 1：创建 DictService

- [ ] **创建** `backend/app/services/dict_service.py`，内容如下：

```python
"""字典服务 - 行业类型等字典数据查询"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.industry_type import IndustryType


class DictService:
    """字典数据服务"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_industry_types(self) -> list[IndustryType]:
        """获取所有行业类型，按 sort_order 升序排列"""
        stmt = (
            select(IndustryType)
            .where(IndustryType.deleted_at.is_(None))
            .order_by(IndustryType.sort_order.asc())
        )
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())
```

### 步骤 2：编写服务单元测试

- [ ] **创建** `backend/tests/unit/test_dict_service.py`，内容如下：

```python
"""DictService 单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.dict_service import DictService
from app.models.industry_type import IndustryType


@pytest.fixture
def mock_session():
    """创建模拟数据库会话"""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def dict_service(mock_session):
    """创建 DictService 实例"""
    return DictService(mock_session)


@pytest.mark.asyncio
async def test_get_industry_types_returns_sorted_list(dict_service, mock_session):
    """测试获取行业类型按 sort_order 升序返回"""
    # 构造模拟结果
    types = [
        IndustryType(id=2, name="房产经纪", sort_order=2),
        IndustryType(id=1, name="项目", sort_order=1),
    ]
    
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = types
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await dict_service.get_industry_types()

    assert len(result) == 2
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_industry_types_empty_result(dict_service, mock_session):
    """测试空结果返回空列表"""
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await dict_service.get_industry_types()

    assert result == []
    assert len(result) == 0
```

### 步骤 3：运行测试

- [ ] **运行**: `cd backend && source .venv/bin/activate && pytest tests/unit/test_dict_service.py -v`
- [ ] **确认**: 测试通过

- [ ] **提交**:
```bash
git add backend/app/services/dict_service.py backend/tests/unit/test_dict_service.py
git commit -m "feat: add DictService with get_industry_types method and tests"
```

---

## 任务 3：字典路由 — GET /api/v1/dicts/industry_types

**Files:**
- Create: `backend/app/routes/dict_routes.py`
- Modify: `backend/app/routes/__init__.py`
- Test: `backend/tests/integration/test_dict_routes.py`

### 步骤 1：查看现有路由注册模式

- [ ] **读取** `backend/app/routes/__init__.py`，查看 Blueprint 注册模式

### 步骤 2：创建字典路由

- [ ] **创建** `backend/app/routes/dict_routes.py`，内容如下：

```python
"""字典数据路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.dict_service import DictService
from ..middleware.auth import auth_required

dict_bp = Blueprint("dicts", url_prefix="/api/v1/dicts")


@dict_bp.get("/industry_types")
@auth_required
async def get_industry_types(request: Request):
    """
    获取行业类型列表

    Response:
    - data: list of {id, name, sort_order}
    """
    db_session: AsyncSession = request.ctx.db_session
    service = DictService(db_session)

    industry_types = await service.get_industry_types()

    return json({
        "code": 0,
        "message": "success",
        "data": [
            {
                "id": it.id,
                "name": it.name,
                "sort_order": it.sort_order,
            }
            for it in industry_types
        ]
    })
```

### 步骤 3：注册 Blueprint

- [ ] **修改** `backend/app/routes/__init__.py`，添加 dict_bp 的导入和注册。

参照现有模式，例如：
```python
from .dict_routes import dict_bp
# 在注册 Blueprint 的地方添加:
app.blueprint(dict_bp)
```

### 步骤 4：编写集成测试

- [ ] **读取** `backend/tests/integration/conftest.py` 了解测试客户端模式
- [ ] **读取** `backend/tests/integration/test_customers_api.py` 了解集成测试模式

- [ ] **创建** `backend/tests/integration/test_dict_routes.py`，内容如下：

```python
"""字典路由集成测试"""

import pytest


@pytest.mark.asyncio
async def test_get_industry_types_requires_auth(client):
    """测试未认证访问被拒绝"""
    response = await client.get("/api/v1/dicts/industry_types")
    assert response.status in (401, 403)


@pytest.mark.asyncio
async def test_get_industry_types_returns_success(auth_client):
    """测试认证后成功返回行业类型列表"""
    response = await auth_client.get("/api/v1/dicts/industry_types")
    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert "data" in data
    assert isinstance(data["data"], list)
    # 验证返回的字段
    if len(data["data"]) > 0:
        item = data["data"][0]
        assert "id" in item
        assert "name" in item
        assert "sort_order" in item
```

### 步骤 5：运行测试

- [ ] **运行**: `cd backend && source .venv/bin/activate && pytest tests/integration/test_dict_routes.py -v`
- [ ] **确认**: 认证测试通过（如果 fixtures 不可用则调整测试代码）

- [ ] **提交**:
```bash
git add backend/app/routes/dict_routes.py backend/app/routes/__init__.py backend/tests/integration/test_dict_routes.py
git commit -m "feat: add GET /api/v1/dicts/industry_types route with integration tests"
```

---

## 任务 4：Alembic 迁移 — 创建 industry_types 表并插入预置数据

**Files:**
- Create: `backend/alembic/versions/YYYY_MM_DD_HHMMSS_add_industry_types_table.py`

### 步骤 1：生成迁移文件

- [ ] **运行**:
```bash
cd backend && source .venv/bin/activate && python -m alembic revision --autogenerate -m "add industry_types table"
```

### 步骤 2：编辑迁移文件

- [ ] **读取** 生成的迁移文件（位于 `backend/alembic/versions/` 目录下最新文件）
- [ ] **编辑** `upgrade()` 函数，确保包含创建表和插入数据：

```python
def upgrade():
    op.create_table(
        'industry_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_industry_types_name', 'industry_types', ['name'])
    op.create_index('ix_industry_types_sort_order', 'industry_types', ['sort_order'])
    
    # 插入 8 条预置数据
    op.bulk_insert(
        sa.table('industry_types',
            sa.column('id', sa.Integer),
            sa.column('name', sa.String),
            sa.column('sort_order', sa.Integer),
        ),
        [
            {'id': 1, 'name': '项目', 'sort_order': 1},
            {'id': 2, 'name': '房产经纪', 'sort_order': 2},
            {'id': 3, 'name': '房产ERP', 'sort_order': 3},
            {'id': 4, 'name': '房产平台', 'sort_order': 4},
            {'id': 5, 'name': '公共安全', 'sort_order': 5},
            {'id': 6, 'name': '租房', 'sort_order': 6},
            {'id': 7, 'name': '待确认', 'sort_order': 7},
            {'id': 8, 'name': '无', 'sort_order': 8},
        ]
    )


def downgrade():
    op.drop_table('industry_types')
```

### 步骤 3：应用迁移验证

- [ ] **运行**:
```bash
cd backend && source .venv/bin/activate && python -m alembic upgrade head
```
- [ ] **确认**: 迁移成功，表中存在 8 条数据

- [ ] **提交**:
```bash
git add backend/alembic/versions/*_add_industry_types_table.py
git commit -m "migration: add industry_types table with 8 pre-seeded values"
```

---

## 任务 5：前端 API 层 — 新增 getIndustryTypes 方法

**Files:**
- Modify: `frontend/src/api/customers.ts`
- Modify: `frontend/src/types/index.ts`

### 步骤 1：添加 API 方法

- [ ] **读取** `frontend/src/api/customers.ts`，找到合适位置

- [ ] **修改** `frontend/src/api/customers.ts`，在文件末尾添加：

```typescript
// 获取行业类型字典
export function getIndustryTypes() {
  return api.get<{ id: number; name: string; sort_order: number }[]>('/dicts/industry_types')
}
```

### 步骤 2：添加 TypeScript 类型

- [ ] **读取** `frontend/src/types/index.ts`

- [ ] **修改** `frontend/src/types/index.ts`，添加接口：

```typescript
export interface IndustryType {
  id: number
  name: string
  sort_order: number
}
```

### 步骤 3：类型检查

- [ ] **运行**: `cd frontend && npm run type-check`
- [ ] **确认**: 无新增类型错误

- [ ] **提交**:
```bash
git add frontend/src/api/customers.ts frontend/src/types/index.ts
git commit -m "feat: add getIndustryTypes API method and IndustryType interface"
```

---

## 任务 6：前端视图层 — 更新筛选标签和数据源

**Files:**
- Modify: `frontend/src/views/customers/Index.vue`
- Modify: `frontend/src/views/customers/Detail.vue`

### 步骤 1：更新 Index.vue — 筛选标签和数据源

- [ ] **读取** `frontend/src/views/customers/Index.vue`

- [ ] **修改**：找到"业务类型"筛选相关代码，进行以下改动：

1. 将筛选标签文本从"业务类型"改为"行业类型"
2. 将硬编码的行业类型选项改为从 API 加载
3. 在组件的 setup/script 中导入 `getIndustryTypes` 并在 `onMounted` 时加载数据

具体修改模式（参照现有代码风格）：

```vue
<!-- 模板部分：筛选表单中的 Select -->
<a-form-item label="行业类型">
  <a-select v-model="queryParams.business_type" placeholder="请选择行业类型" allow-clear>
    <a-option
      v-for="item in industryTypes"
      :key="item.id"
      :value="item.name"
    >
      {{ item.name }}
    </a-option>
  </a-select>
</a-form-item>
```

```typescript
// Script 部分：导入和数据加载
import { getIndustryTypes } from '@/api/customers'
import type { IndustryType } from '@/types'

// 在 ref 声明区域添加
const industryTypes = ref<IndustryType[]>([])

// 加载行业类型
async function loadIndustryTypes() {
  try {
    const res = await getIndustryTypes()
    industryTypes.value = res.data.data || []
  } catch (error) {
    console.error('Failed to load industry types:', error)
  }
}

// 在 onMounted 中调用
onMounted(() => {
  loadIndustryTypes()
  // ... 其他 onMounted 逻辑
})
```

### 步骤 2：更新 Detail.vue — 详情展示标签

- [ ] **读取** `frontend/src/views/customers/Detail.vue`

- [ ] **修改**：将所有"业务类型"标签文本改为"行业类型"

### 步骤 3：全局搜索确认

- [ ] **搜索**: `frontend/src/` 目录下所有包含"业务类型"的文件
- [ ] **修改**：剩余文件中的"业务类型"标签统一改为"行业类型"

### 步骤 4：前端代码质量检查

- [ ] **运行**: `cd frontend && npm run type-check && npm run lint`
- [ ] **确认**: 无新增错误和警告

- [ ] **提交**:
```bash
git add frontend/src/views/customers/Index.vue frontend/src/views/customers/Detail.vue
git commit -m "feat: change business type filter to industry type with dynamic API data source"
```

---

## 任务 7：全局验证

### 步骤 1：后端全量测试

- [ ] **运行**:
```bash
cd backend && source .venv/bin/activate && pytest tests/ -v --tb=short
```
- [ ] **确认**: 所有测试通过

### 步骤 2：后端覆盖率检查

- [ ] **运行**:
```bash
cd backend && source .venv/bin/activate && pytest --cov=app --cov-report=term-missing
```
- [ ] **确认**: 覆盖率 >= 50%

### 步骤 3：代码质量检查

- [ ] **运行**:
```bash
cd backend && source .venv/bin/activate && black app/ tests/ && flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203
```
- [ ] **确认**: 无 lint 错误

### 步骤 4：前端检查

- [ ] **运行**:
```bash
cd frontend && npm run type-check && npm run lint && npm run format
```
- [ ] **确认**: 无新增错误

### 步骤 5：最终提交

- [ ] **提交**（如有格式化变更）:
```bash
git add -A
git commit -m "chore: code formatting and lint fixes"
```

---

## 验收标准对照

| 标准 | 对应任务 |
| ---- | -------- |
| `GET /api/v1/dicts/industry_types` 返回 8 条预置数据 | 任务 2, 3, 4 |
| 客户管理筛选标签显示为"行业类型" | 任务 6 |
| 筛选下拉选项从 API 动态加载 | 任务 5, 6 |
| 已存在的 business_type 数据正常展示 | 任务 6（不改列名，仅改标签） |
| 所有提及"业务类型"的前端 UI 统一更新 | 任务 6 |
| 所有测试通过 | 任务 7 |
