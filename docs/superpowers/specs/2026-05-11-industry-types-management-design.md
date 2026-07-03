# 行业类型管理模块 - 设计文档

**创建日期**: 2026-05-11
**状态**: 待审查
**作者**: AI Assistant

---

## 1. 背景与目标

### 1.1 问题陈述

当前系统中，`industry_types` 表的数据缺乏管理入口：
- staging 环境部署后该表为空，导致客户管理页面的"行业类型"筛选项无数据
- 本地开发环境有 8 条数据，但来源不明（非 alembic 迁移、非 seed 脚本初始化）
- 没有 UI 界面可以增删改查行业类型

### 1.2 目标

在系统设置模块下新增"行业类型"管理功能，支持完整的增删改查操作，同时解决 staging 环境字典数据缺失问题。

---

## 2. 需求规格

### 2.1 功能需求

| 编号   | 需求           | 说明                                           |
| ------ | -------------- | ---------------------------------------------- |
| FR-01  | 列表展示       | 表格展示所有行业类型，按 sort_order 升序排列   |
| FR-02  | 新增           | 弹窗表单，输入名称和排序号                     |
| FR-03  | 编辑           | 弹窗表单，预填当前值                           |
| FR-04  | 删除           | 软删除（设置 deleted_at），已有客户记录不受影响 |
| FR-05  | 名称唯一性校验 | 新增/编辑时校验名称不重复                      |
| FR-06  | 权限控制       | 需要 `industry_types:manage` 权限              |

### 2.2 非功能需求

| 编号    | 需求         | 说明                           |
| ------- | ------------ | ------------------------------ |
| NFR-01  | 一致性       | UI 风格与现有角色管理页面一致  |
| NFR-02  | 响应式       | 支持不同屏幕尺寸               |
| NFR-03  | 测试覆盖率   | 后端单元测试 + 集成测试 ≥ 50%  |

---

## 3. 架构设计

### 3.1 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend (Vue 3)                    │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Dashboard.vue (侧边栏)                            │   │
│  │  └─ 系统设置 ▾                                     │   │
│  │     ├─ 同步日志                                    │   │
│  │     ├─ 审计日志                                    │   │
│  │     └─ 行业类型 ← 新增                             │   │
│  │                                                    │   │
│  │  views/system/IndustryTypes.vue ← 新增页面         │   │
│  │  api/industryTypes.ts ← 新增 API 封装              │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP REST API
                         ▼
┌─────────────────────────────────────────────────────────┐
│                      Backend (Sanic)                     │
│  ┌──────────────────────────────────────────────────┐   │
│  │  routes/industry_type_routes.py ← 新增            │   │
│  │  ├─ GET    /api/v1/industry-types                 │   │
│  │  ├─ POST   /api/v1/industry-types                 │   │
│  │  ├─ PUT    /api/v1/industry-types/{id}            │   │
│  │  └─ DELETE /api/v1/industry-types/{id}            │   │
│  │                                                    │   │
│  │  services/industry_type_service.py ← 新增          │   │
│  │  ├─ get_all()                                     │   │
│  │  ├─ create()                                      │   │
│  │  ├─ update()                                      │   │
│  │  └─ soft_delete()                                 │   │
│  │                                                    │   │
│  │  middleware/auth.py ← 修改                          │   │
│  │  └─ 新增权限: industry_types:manage               │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │ SQLAlchemy ORM
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  PostgreSQL Database                     │
│  ┌──────────────────────────────────────────────────┐   │
│  │  industry_types 表 (已存在)                        │   │
│  │  ├─ id (PK)                                      │   │
│  │  ├─ name (UNIQUE)                                │   │
│  │  ├─ sort_order                                   │   │
│  │  ├─ created_at                                   │   │
│  │  ├─ updated_at                                   │   │
│  │  └─ deleted_at (软删除)                           │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 3.2 数据流

```
用户操作 → 前端组件 → API 封装 → HTTP 请求 → 后端路由 → 权限校验
                                                          ↓
                                                  Service 层
                                                          ↓
                                                  SQLAlchemy
                                                          ↓
                                                  PostgreSQL
                                                          ↓
                                                  JSON Response
                                                          ↓
                                                  前端更新 UI
```

---

## 4. 详细设计

### 4.1 后端设计

#### 4.1.1 API 路由 (`backend/app/routes/industry_type_routes.py`)

| 方法     | 路径                            | 权限                        | 说明         |
| -------- | ------------------------------- | --------------------------- | ------------ |
| `GET`    | `/api/v1/industry-types`        | `industry_types:manage`     | 获取列表     |
| `POST`   | `/api/v1/industry-types`        | `industry_types:manage`     | 新增         |
| `PUT`    | `/api/v1/industry-types/{id}`   | `industry_types:manage`     | 更新         |
| `DELETE` | `/api/v1/industry-types/{id}`   | `industry_types:manage`     | 软删除       |

**请求/响应格式**:

```
POST /api/v1/industry-types
Request Body: { "name": "制造业", "sort_order": 1 }
Response: { "code": 0, "message": "success", "data": { "id": 1, "name": "制造业", "sort_order": 1 } }

PUT /api/v1/industry-types/1
Request Body: { "name": "制造业", "sort_order": 2 }
Response: { "code": 0, "message": "success", "data": { "id": 1, "name": "制造业", "sort_order": 2 } }

DELETE /api/v1/industry-types/1
Response: { "code": 0, "message": "success" }
```

#### 4.1.2 Service 层 (`backend/app/services/industry_type_service.py`)

```python
class IndustryTypeService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all(self) -> list[IndustryType]:
        """获取所有未删除的行业类型，按 sort_order 升序"""

    async def create(self, name: str, sort_order: int) -> IndustryType:
        """新增行业类型，校验名称唯一性"""

    async def update(self, id: int, name: str, sort_order: int) -> IndustryType:
        """更新行业类型，校验名称唯一性"""

    async def soft_delete(self, id: int) -> bool:
        """软删除行业类型"""
```

#### 4.1.3 权限定义

在 `backend/scripts/seed.py` 的 `ALL_PERMISSIONS` 中新增：

```python
("industry_types:manage", "管理行业类型", "新增/编辑/删除行业类型", "system"),
```

### 4.2 前端设计

#### 4.2.1 路由配置 (`frontend/src/router/index.ts`)

在 `system` 子路由下新增：

```typescript
{
  path: 'industry-types',
  name: 'IndustryTypes',
  component: () => import('@/views/system/IndustryTypes.vue'),
  meta: { requiresPermission: 'industry_types:manage' },
},
```

#### 4.2.2 侧边栏导航 (`frontend/src/views/Dashboard.vue`)

在"系统设置"子菜单中新增"行业类型"链接：

```html
<a v-if="can('industry_types:manage')" class="nav-subitem"
   :class="{ active: $route.name === 'IndustryTypes' }"
   @click="$router.push('/system/industry-types')">
  行业类型
</a>
```

#### 4.2.3 页面组件 (`frontend/src/views/system/IndustryTypes.vue`)

**页面结构**:
- 页面头部：标题 + 新增按钮
- 数据表格：ID、名称、排序号、创建时间、操作列（编辑/删除）
- 弹窗表单：名称（文本输入）、排序号（数字输入）

**交互逻辑**:
- 新增：点击"新增"按钮 → 打开空表单弹窗 → 提交后刷新列表
- 编辑：点击"编辑" → 打开预填表单 → 提交后刷新列表
- 删除：点击"删除" → 确认弹窗 → 调用 API → 刷新列表

#### 4.2.4 API 封装 (`frontend/src/api/industryTypes.ts`)

```typescript
import api from './index'
import { IndustryType } from '@/types'

export function getIndustryTypesList() {
  return api.get('/industry-types')
}

export function createIndustryType(data: { name: string; sort_order: number }) {
  return api.post('/industry-types', data)
}

export function updateIndustryType(id: number, data: { name: string; sort_order: number }) {
  return api.put(`/industry-types/${id}`, data)
}

export function deleteIndustryType(id: number) {
  return api.delete(`/industry-types/${id}`)
}
```

### 4.3 数据库迁移

#### 4.3.1 种子数据迁移

创建新的 alembic 迁移文件，初始化本地环境实际使用的 8 个行业类型（来源于客户画像数据汇总）：

```python
def upgrade():
    op.bulk_insert('industry_types', [
        {'name': '项目', 'sort_order': 1},
        {'name': '房产经纪', 'sort_order': 2},
        {'name': '房产ERP', 'sort_order': 3},
        {'name': '房产平台', 'sort_order': 4},
        {'name': '公共安全', 'sort_order': 5},
        {'name': '租房', 'sort_order': 6},
        {'name': '待确认', 'sort_order': 7},
        {'name': '无', 'sort_order': 8},
    ])

def downgrade():
    op.execute("DELETE FROM industry_types WHERE sort_order BETWEEN 1 AND 8")
```

**数据来源**：从本地数据库 `customer_profiles` 表汇总得出，共 7 个实际使用的行业类型 + 1 个"无"选项：

| 行业类型 | 客户数量 | 占比     |
| -------- | -------: | -------: |
| 项目     | 847      | 68.4%    |
| 房产经纪 | 358      | 28.9%    |
| 房产 ERP | 10       | 0.8%     |
| 公共安全 | 9        | 0.7%     |
| 房产平台 | 5        | 0.4%     |
| 租房     | 3        | 0.2%     |
| 待确认   | 2        | 0.2%     |
| 无       | 0        | 0%       |

---

## 5. 错误处理

| 场景               | 处理方式                                     |
| ------------------ | -------------------------------------------- |
| 名称重复           | 返回 409 Conflict，提示"行业类型名称已存在"  |
| 删除不存在的记录   | 返回 404 Not Found                           |
| 无权限操作         | 返回 403 Forbidden                           |
| 参数校验失败       | 返回 422 Unprocessable Entity                |

---

## 6. 测试策略

### 6.1 后端测试

| 测试文件                              | 测试内容                     |
| ------------------------------------- | ---------------------------- |
| `tests/unit/test_industry_type_service.py` | Service 层单元测试       |
| `tests/integration/test_industry_type_routes.py` | 路由集成测试     |

**测试用例**:
- 获取列表返回排序数据
- 新增成功 + 名称唯一性校验
- 更新成功 + 名称唯一性校验
- 软删除后列表不再返回
- 权限验证

### 6.2 前端测试

当前项目前端只有 E2E 测试（Playwright），新增页面应在 `frontend/tests/` 下添加 E2E 测试用例。

---

## 7. 部署注意事项

1. **数据库迁移**: 部署时自动运行 `alembic upgrade head`
2. **种子数据**: 行业类型种子数据通过 alembic 迁移初始化，幂等执行
3. **权限同步**: 部署后需运行 `python scripts/seed.py` 同步新增权限（或手动插入）

---

## 8. 文件变更清单

### 新增文件
- `backend/app/routes/industry_type_routes.py`
- `backend/app/services/industry_type_service.py`
- `backend/tests/unit/test_industry_type_service.py`
- `backend/tests/integration/test_industry_type_routes.py`
- `frontend/src/views/system/IndustryTypes.vue`
- `frontend/src/api/industryTypes.ts`
- `backend/alembic/versions/<timestamp>_seed_industry_types.py`

### 修改文件
- `backend/scripts/seed.py` - 新增权限定义
- `backend/app/main.py` - 注册新路由
- `frontend/src/router/index.ts` - 新增路由
- `frontend/src/views/Dashboard.vue` - 新增侧边栏菜单项
- `frontend/src/types/index.ts` - 确认 IndustryType 类型是否满足需求
