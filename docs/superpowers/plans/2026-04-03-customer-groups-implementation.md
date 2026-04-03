# 客户分群功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现客户分群功能，支持动态群组（保存筛选条件）和静态群组（手动管理成员）

**Architecture:** 
- 后端：CustomerGroup 模型 + CustomerGroupMember 模型，CustomerGroupService 服务层，RESTful API
- 前端：左侧边栏群组列表 + 客户列表联动，GroupForm 表单组件，GroupMembers 成员管理组件

**Tech Stack:** Python 3.10+, Sanic 23+, SQLAlchemy 2.0, Vue 3 + TypeScript, Arco Design Vue

---

## 文件结构

### 后端新增文件
- `backend/app/models/groups.py` - 群组和成员模型
- `backend/app/services/groups.py` - 群组服务层
- `backend/app/routes/groups.py` - 群组 API 路由
- `backend/tests/test_group_service.py` - 服务层单元测试
- `backend/tests/integration/test_groups_api.py` - API 集成测试

### 后端修改文件
- `backend/app/main.py` - 注册 groups 蓝图
- `backend/app/models/users.py` - 添加 created_groups 关联
- `backend/app/models/customers.py` - 添加 group_memberships 关联

### 前端新增文件
- `frontend/src/views/customer-groups/Index.vue` - 群组管理主页面
- `frontend/src/views/customer-groups/components/GroupSidebar.vue` - 群组侧边栏
- `frontend/src/views/customer-groups/components/GroupForm.vue` - 群组表单
- `frontend/src/views/customer-groups/components/GroupMembers.vue` - 成员管理
- `frontend/src/api/customer-groups.ts` - API 客户端

### 前端修改文件
- `frontend/src/router/index.ts` - 添加群组路由

---

## Phase 1: 后端实现（动态群组 + 静态群组基础）

### Task 1: 创建数据模型

**Files:**
- Create: `backend/app/models/groups.py`
- Modify: `backend/app/models/users.py`
- Modify: `backend/app/models/customers.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: 编写 CustomerGroup 模型测试**

```python
# backend/tests/test_models.py
def test_customer_group_creation():
    """测试创建群组"""
    group = CustomerGroup(
        name="测试群组",
        description="测试描述",
        group_type="dynamic",
        filter_conditions={"customer_level": "KA"},
        created_by=1
    )
    assert group.name == "测试群组"
    assert group.group_type == "dynamic"
    assert group.filter_conditions == {"customer_level": "KA"}
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend
python3 -m pytest tests/test_models.py::test_customer_group_creation -v
# Expected: FAIL with "NameError: name 'CustomerGroup' is not defined"
```

- [ ] **Step 3: 创建 CustomerGroup 模型**

```python
# backend/app/models/groups.py
"""客户群组模型"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    ForeignKey,
    Text,
    JSON,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from .base import BaseModel


class CustomerGroup(BaseModel):
    """客户群组表"""

    __tablename__ = "customer_groups"

    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    group_type = Column(String(20), nullable=False, index=True)  # 'dynamic' / 'static'
    filter_conditions = Column(JSON)  # 动态群组的筛选条件
    created_by = Column(Integer, ForeignKey("users.id"), index=True)

    __table_args__ = (
        Index("idx_group_type_created_by", "group_type", "created_by"),
    )

    # 关联
    creator = relationship("User", back_populates="created_groups")
    members = relationship(
        "CustomerGroupMember",
        back_populates="group",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CustomerGroup {self.name}>"


class CustomerGroupMember(BaseModel):
    """静态群组成员表"""

    __tablename__ = "customer_group_members"

    group_id = Column(Integer, ForeignKey("customer_groups.id", ondelete="CASCADE"), primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True, index=True)

    # 关联
    group = relationship("CustomerGroup", back_populates="members")
    customer = relationship("Customer", back_populates="group_memberships")

    __table_args__ = (
        Index("idx_member_group_customer", "group_id", "customer_id"),
        Index("idx_member_customer", "customer_id"),
    )

    def __repr__(self):
        return f"<CustomerGroupMember group={self.group_id} customer={self.customer_id}>"
```

- [ ] **Step 4: 添加 User 模型关联**

```python
# backend/app/models/users.py - 在 User 类中添加
# 在 # 关联 部分添加：
created_groups = relationship("CustomerGroup", back_populates="creator")
```

- [ ] **Step 5: 添加 Customer 模型关联**

```python
# backend/app/models/customers.py - 在 Customer 类中添加
# 在 # 关联 部分添加：
group_memberships = relationship("CustomerGroupMember", back_populates="customer")
```

- [ ] **Step 6: 运行测试验证通过**

```bash
cd backend
python3 -m pytest tests/test_models.py::test_customer_group_creation -v
# Expected: PASS
```

- [ ] **Step 7: 创建数据库迁移**

```bash
cd backend
python -m alembic revision --autogenerate -m "Add customer groups tables"
python -m alembic upgrade head
```

- [ ] **Step 8: 提交**

```bash
git add backend/app/models/groups.py backend/app/models/users.py backend/app/models/customers.py backend/tests/test_models.py
git commit -m "feat: 添加客户群组数据模型"
```

---

### Task 2: 实现 CustomerGroupService

**Files:**
- Create: `backend/app/services/groups.py`
- Test: `backend/tests/test_group_service.py`

- [ ] **Step 1: 编写创建群组测试**

```python
# backend/tests/test_group_service.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.groups import CustomerGroupService

class MockDBSession:
    def __init__(self):
        self.execute = AsyncMock()
        self.add = MagicMock()
        self.commit = AsyncMock()

def make_mock_execute_result(rows):
    result = MagicMock()
    result.all = MagicMock(return_value=rows)
    result.scalar = MagicMock(return_value=rows[0][0] if rows else None)
    return result

@pytest.mark.asyncio
async def test_create_dynamic_group():
    """测试创建动态群组"""
    mock_db = MockDBSession()
    mock_db.execute.return_value = make_mock_execute_result([])
    
    service = CustomerGroupService(mock_db)
    
    group = await service.create_group(
        name="Q1 重点客户",
        description="2026 年 Q1 重点客户",
        group_type="dynamic",
        filter_conditions={"customer_level": "KA"},
        created_by=1
    )
    
    assert group.name == "Q1 重点客户"
    assert group.group_type == "dynamic"
    assert mock_db.commit.call_count == 1
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend
python3 -m pytest tests/test_group_service.py::test_create_dynamic_group -v
# Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.groups'"
```

- [ ] **Step 3: 创建 CustomerGroupService 基础框架**

```python
# backend/app/services/groups.py
"""客户群组管理服务"""

from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from ..models.groups import CustomerGroup, CustomerGroupMember
from ..models.customers import Customer


class CustomerGroupService:
    """客户群组服务"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_group(
        self,
        name: str,
        description: Optional[str],
        group_type: str,
        filter_conditions: Optional[Dict[str, Any]],
        created_by: int
    ) -> CustomerGroup:
        """创建群组"""
        group = CustomerGroup(
            name=name,
            description=description,
            group_type=group_type,
            filter_conditions=filter_conditions if group_type == "dynamic" else None,
            created_by=created_by
        )
        self.db.add(group)
        await self.db.commit()
        return group
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend
python3 -m pytest tests/test_group_service.py::test_create_dynamic_group -v
# Expected: PASS
```

- [ ] **Step 5: 添加更多服务方法测试**

```python
# backend/tests/test_group_service.py - 添加测试方法

@pytest.mark.asyncio
async def test_get_user_groups():
    """测试获取用户的群组列表"""
    # TODO: 实现测试

@pytest.mark.asyncio
async def test_update_group():
    """测试更新群组"""
    # TODO: 实现测试

@pytest.mark.asyncio
async def test_delete_group():
    """测试删除群组"""
    # TODO: 实现测试

@pytest.mark.asyncio
async def test_add_member():
    """测试添加成员（静态群组）"""
    # TODO: 实现测试

@pytest.mark.asyncio
async def test_apply_group_filter():
    """测试应用群组筛选（动态群组）"""
    # TODO: 实现测试
```

- [ ] **Step 6: 实现完整服务方法**

```python
# backend/app/services/groups.py - 添加方法

    async def get_user_groups(self, user_id: int) -> List[CustomerGroup]:
        """获取用户的群组列表"""
        stmt = select(CustomerGroup).where(
            CustomerGroup.created_by == user_id,
            CustomerGroup.deleted_at.is_(None)
        ).order_by(CustomerGroup.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_group_detail(self, group_id: int) -> Optional[CustomerGroup]:
        """获取群组详情"""
        stmt = select(CustomerGroup).where(
            CustomerGroup.id == group_id,
            CustomerGroup.deleted_at.is_(None)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_group(self, group_id: int, data: dict) -> Optional[CustomerGroup]:
        """更新群组"""
        group = await self.get_group_detail(group_id)
        if not group:
            return None
        
        for key, value in data.items():
            if hasattr(group, key) and key not in ['id', 'created_by', 'deleted_at']:
                setattr(group, key, value)
        
        await self.db.commit()
        return group

    async def delete_group(self, group_id: int) -> bool:
        """删除群组（软删除）"""
        group = await self.get_group_detail(group_id)
        if not group:
            return False
        
        from datetime import datetime
        group.deleted_at = datetime.utcnow()
        await self.db.commit()
        return True

    async def add_member(self, group_id: int, customer_id: int) -> bool:
        """添加成员（静态群组）"""
        # 检查是否已存在
        stmt = select(CustomerGroupMember).where(
            CustomerGroupMember.group_id == group_id,
            CustomerGroupMember.customer_id == customer_id
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            return False
        
        member = CustomerGroupMember(group_id=group_id, customer_id=customer_id)
        self.db.add(member)
        await self.db.commit()
        return True

    async def remove_member(self, group_id: int, customer_id: int) -> bool:
        """移除成员"""
        stmt = select(CustomerGroupMember).where(
            CustomerGroupMember.group_id == group_id,
            CustomerGroupMember.customer_id == customer_id
        )
        result = await self.db.execute(stmt)
        member = result.scalar_one_or_none()
        
        if not member:
            return False
        
        await self.db.delete(member)
        await self.db.commit()
        return True

    async def get_group_members(
        self, group_id: int, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Customer], int]:
        """获取群组成员列表"""
        # 计数
        count_stmt = select(func.count()).select_from(CustomerGroupMember).where(
            CustomerGroupMember.group_id == group_id
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0
        
        # 查询成员
        stmt = select(Customer).join(CustomerGroupMember).where(
            CustomerGroupMember.group_id == group_id,
            Customer.deleted_at.is_(None)
        ).offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(stmt)
        customers = list(result.scalars().all())
        
        return customers, total

    async def apply_group_filter(
        self, group_id: int, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Customer], int]:
        """应用群组筛选"""
        group = await self.get_group_detail(group_id)
        if not group:
            return [], 0
        
        if group.group_type == "static":
            # 静态群组：返回成员列表
            return await self.get_group_members(group_id, page, page_size)
        else:
            # 动态群组：应用筛选条件
            return await self._apply_dynamic_filter(
                group.filter_conditions, page, page_size
            )

    async def _apply_dynamic_filter(
        self, conditions: Optional[Dict[str, Any]], page: int, page_size: int
    ) -> Tuple[List[Customer], int]:
        """应用动态筛选条件"""
        from ..models.customers import Customer
        
        if not conditions:
            # 无条件：返回所有客户
            count_stmt = select(func.count()).select_from(Customer).where(
                Customer.deleted_at.is_(None)
            )
            total = (await self.db.execute(count_stmt)).scalar() or 0
            
            stmt = select(Customer).where(
                Customer.deleted_at.is_(None)
            ).offset((page - 1) * page_size).limit(page_size)
        else:
            # 构建筛选条件
            filters = []
            for key, value in conditions.items():
                if value is not None and hasattr(Customer, key):
                    filters.append(getattr(Customer, key) == value)
            
            count_stmt = select(func.count()).select_from(Customer).where(
                and_(*filters), Customer.deleted_at.is_(None)
            )
            total = (await self.db.execute(count_stmt)).scalar() or 0
            
            stmt = select(Customer).where(
                and_(*filters), Customer.deleted_at.is_(None)
            ).offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(stmt)
        customers = list(result.scalars().all())
        
        return customers, total

    async def get_group_stats(self, group_id: int) -> dict:
        """获取群组统计信息"""
        group = await self.get_group_detail(group_id)
        if not group:
            return {}
        
        if group.group_type == "static":
            # 静态群组：统计成员数
            count_stmt = select(func.count()).select_from(CustomerGroupMember).where(
                CustomerGroupMember.group_id == group_id
            )
            member_count = (await self.db.execute(count_stmt)).scalar() or 0
        else:
            # 动态群组：实时计算
            _, member_count = await self.apply_group_filter(group_id, 1, 1)
        
        return {
            "id": group.id,
            "name": group.name,
            "group_type": group.group_type,
            "member_count": member_count
        }
```

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/groups.py backend/tests/test_group_service.py
git commit -m "feat: 实现 CustomerGroupService 服务层"
```

---

### Task 3: 实现 API 路由

**Files:**
- Create: `backend/app/routes/groups.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_groups_api.py`

- [ ] **Step 1: 创建 API 路由**

```python
# backend/app/routes/groups.py
"""客户群组管理路由"""

from sanic import Blueprint
from sanic.response import json
from sanic.request import Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.groups import CustomerGroupService
from ..middleware.auth import get_current_user

groups_bp = Blueprint("groups", url_prefix="/api/v1/customer-groups")


@groups_bp.get("")
async def list_groups(request: Request):
    """获取用户的群组列表"""
    current_user = get_current_user(request)
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerGroupService(db_session)
    
    groups = await service.get_user_groups(current_user["user_id"])
    
    return json({
        "code": 0,
        "message": "success",
        "data": {
            "list": [
                {
                    "id": g.id,
                    "name": g.name,
                    "description": g.description,
                    "group_type": g.group_type,
                    "created_at": g.created_at.isoformat() if g.created_at else None,
                }
                for g in groups
            ]
        }
    })


@groups_bp.post("")
async def create_group(request: Request):
    """创建群组"""
    current_user = get_current_user(request)
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerGroupService(db_session)
    
    data = request.json
    name = data.get("name")
    
    if not name:
        return json({"code": 40001, "message": "群组名称不能为空"}, status=400)
    
    group = await service.create_group(
        name=name,
        description=data.get("description"),
        group_type=data.get("group_type", "dynamic"),
        filter_conditions=data.get("filter_conditions"),
        created_by=current_user["user_id"]
    )
    
    return json({
        "code": 0,
        "message": "创建成功",
        "data": {
            "id": group.id,
            "name": group.name,
        }
    }, status=201)


@groups_bp.get("/<group_id:int>")
async def get_group(request: Request, group_id: int):
    """获取群组详情"""
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerGroupService(db_session)
    
    group = await service.get_group_detail(group_id)
    
    if not group:
        return json({"code": 40401, "message": "群组不存在"}, status=404)
    
    return json({
        "code": 0,
        "message": "success",
        "data": {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "group_type": group.group_type,
            "filter_conditions": group.filter_conditions,
            "created_at": group.created_at.isoformat() if group.created_at else None,
        }
    })


@groups_bp.put("/<group_id:int>")
async def update_group(request: Request, group_id: int):
    """更新群组"""
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerGroupService(db_session)
    
    data = request.json
    group = await service.update_group(group_id, data)
    
    if not group:
        return json({"code": 40401, "message": "群组不存在"}, status=404)
    
    return json({
        "code": 0,
        "message": "更新成功",
        "data": {
            "id": group.id,
            "name": group.name,
        }
    })


@groups_bp.delete("/<group_id:int>")
async def delete_group(request: Request, group_id: int):
    """删除群组"""
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerGroupService(db_session)
    
    success = await service.delete_group(group_id)
    
    if not success:
        return json({"code": 40401, "message": "群组不存在"}, status=404)
    
    return json({"code": 0, "message": "删除成功"})


@groups_bp.get("/<group_id:int>/members")
async def get_group_members(request: Request, group_id: int):
    """获取群组成员列表"""
    page = request.args.get("page", 1, int)
    page_size = request.args.get("page_size", 20, int)
    
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerGroupService(db_session)
    
    members, total = await service.get_group_members(group_id, page, page_size)
    
    return json({
        "code": 0,
        "message": "success",
        "data": {
            "list": [
                {
                    "id": m.id,
                    "name": m.name,
                    "company_id": m.company_id,
                }
                for m in members
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    })


@groups_bp.post("/<group_id:int>/members")
async def add_member(request: Request, group_id: int):
    """添加成员（静态群组）"""
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerGroupService(db_session)
    
    data = request.json
    customer_id = data.get("customer_id")
    
    if not customer_id:
        return json({"code": 40001, "message": "客户 ID 不能为空"}, status=400)
    
    success = await service.add_member(group_id, customer_id)
    
    if not success:
        return json({"code": 40002, "message": "添加失败，成员可能已存在"}, status=400)
    
    return json({"code": 0, "message": "添加成功"})


@groups_bp.delete("/<group_id:int>/members/<customer_id:int>")
async def remove_member(request: Request, group_id: int, customer_id: int):
    """移除成员"""
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerGroupService(db_session)
    
    success = await service.remove_member(group_id, customer_id)
    
    if not success:
        return json({"code": 40401, "message": "成员不存在"}, status=404)
    
    return json({"code": 0, "message": "移除成功"})


@groups_bp.post("/<group_id:int>/apply")
async def apply_group_filter(request: Request, group_id: int):
    """应用群组筛选"""
    page = request.args.get("page", 1, int)
    page_size = request.args.get("page_size", 20, int)
    
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerGroupService(db_session)
    
    customers, total = await service.apply_group_filter(group_id, page, page_size)
    
    return json({
        "code": 0,
        "message": "success",
        "data": {
            "list": [
                {
                    "id": c.id,
                    "name": c.name,
                    "company_id": c.company_id,
                }
                for c in customers
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    })


@groups_bp.get("/<group_id:int>/stats")
async def get_group_stats(request: Request, group_id: int):
    """获取群组统计信息"""
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerGroupService(db_session)
    
    stats = await service.get_group_stats(group_id)
    
    if not stats:
        return json({"code": 40401, "message": "群组不存在"}, status=404)
    
    return json({
        "code": 0,
        "message": "success",
        "data": stats
    })
```

- [ ] **Step 2: 注册蓝图**

```python
# backend/app/main.py - 在注册蓝图部分添加
from .routes.groups import groups_bp

app.blueprint(groups_bp)
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/routes/groups.py backend/app/main.py
git commit -m "feat: 实现客户群组 API 路由"
```

---

## Phase 2: 前端实现

### Task 4: 创建 API 客户端

**Files:**
- Create: `frontend/src/api/customer-groups.ts`

- [ ] **Step 1: 创建 API 客户端**

```typescript
// frontend/src/api/customer-groups.ts
import request from './request'

export interface CustomerGroup {
  id: number
  name: string
  description?: string
  group_type: 'dynamic' | 'static'
  filter_conditions?: any
  created_at?: string
}

export interface CreateGroupParams {
  name: string
  description?: string
  group_type: 'dynamic' | 'static'
  filter_conditions?: any
}

/**
 * 获取群组列表
 */
export function getCustomerGroups() {
  return request.get<CustomerGroup[]>('/api/v1/customer-groups')
}

/**
 * 创建群组
 */
export function createCustomerGroup(data: CreateGroupParams) {
  return request.post<{ id: number }>('/api/v1/customer-groups', data)
}

/**
 * 获取群组详情
 */
export function getGroupDetail(id: number) {
  return request.get<CustomerGroup>(`/api/v1/customer-groups/${id}`)
}

/**
 * 更新群组
 */
export function updateCustomerGroup(id: number, data: Partial<CreateGroupParams>) {
  return request.put(`/api/v1/customer-groups/${id}`, data)
}

/**
 * 删除群组
 */
export function deleteCustomerGroup(id: number) {
  return request.delete(`/api/v1/customer-groups/${id}`)
}

/**
 * 获取群组成员列表
 */
export function getGroupMembers(id: number, params: { page?: number; page_size?: number }) {
  return request.get(`/api/v1/customer-groups/${id}/members`, { params })
}

/**
 * 添加成员
 */
export function addGroupMember(id: number, customer_id: number) {
  return request.post(`/api/v1/customer-groups/${id}/members`, { customer_id })
}

/**
 * 移除成员
 */
export function removeGroupMember(id: number, customer_id: number) {
  return request.delete(`/api/v1/customer-groups/${id}/members/${customer_id}`)
}

/**
 * 应用群组筛选
 */
export function applyGroupFilter(id: number, params: { page?: number; page_size?: number }) {
  return request.post(`/api/v1/customer-groups/${id}/apply`, params)
}

/**
 * 获取群组统计
 */
export function getGroupStats(id: number) {
  return request.get(`/api/v1/customer-groups/${id}/stats`)
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/customer-groups.ts
git commit -m "feat: 创建客户群组 API 客户端"
```

---

### Task 5: 创建群组管理页面

**Files:**
- Create: `frontend/src/views/customer-groups/Index.vue`
- Create: `frontend/src/views/customer-groups/components/GroupSidebar.vue`
- Create: `frontend/src/views/customer-groups/components/GroupForm.vue`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 添加路由**

```typescript
// frontend/src/router/index.ts - 在 system 路由下添加
{
  path: 'customer-groups',
  name: 'CustomerGroups',
  component: () => import('@/views/customer-groups/Index.vue'),
  meta: { requiresPermission: 'customers:view' },
}
```

- [ ] **Step 2: 创建主页面**

```vue
<!-- frontend/src/views/customer-groups/Index.vue -->
<template>
  <div class="customer-groups-page">
    <a-page-header title="客户分群" subtitle="管理客户群组" />

    <div class="groups-layout">
      <!-- 左侧边栏 -->
      <GroupSidebar
        v-model:selectedGroupId="selectedGroupId"
        :groups="groups"
        @create="showCreateModal"
        @select="handleGroupSelect"
      />

      <!-- 右侧内容 -->
      <a-card class="groups-content">
        <template #title>
          <a-space>
            <span>{{ currentGroupTitle }}</span>
            <a-tag v-if="selectedGroup" :color="selectedGroup.group_type === 'dynamic' ? 'blue' : 'green'">
              {{ selectedGroup.group_type === 'dynamic' ? '动态群组' : '静态群组' }}
            </a-tag>
          </a-space>
        </template>

        <!-- 客户表格 -->
        <a-table
          :columns="columns"
          :data="customers"
          :loading="loading"
          :pagination="pagination"
          row-key="id"
          @page-change="onPageChange"
        >
          <template #actions="{ record }">
            <a-space>
              <a-button type="text" size="small" @click="handleViewCustomer(record)">
                查看
              </a-button>
              <a-button
                v-if="selectedGroup?.group_type === 'static'"
                type="text"
                size="small"
                status="danger"
                @click="handleRemoveMember(record.id)"
              >
                移除
              </a-button>
            </a-space>
          </template>
        </a-table>
      </a-card>
    </div>

    <!-- 新建群组表单 -->
    <GroupForm
      v-model:visible="formVisible"
      :default-filter="defaultFilter"
      @submit="handleCreateGroup"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import * as groupApi from '@/api/customer-groups'
import GroupSidebar from './components/GroupSidebar.vue'
import GroupForm from './components/GroupForm.vue'

interface CustomerGroup {
  id: number
  name: string
  description?: string
  group_type: 'dynamic' | 'static'
  filter_conditions?: any
}

interface Customer {
  id: number
  name: string
  company_id: string
}

const groups = ref<CustomerGroup[]>([])
const selectedGroupId = ref<number | null>(null)
const selectedGroup = ref<CustomerGroup | null>(null)
const customers = ref<Customer[]>([])
const loading = ref(false)
const formVisible = ref(false)
const defaultFilter = ref<any>(null)

const currentGroupTitle = computed(() => {
  if (!selectedGroup.value) return '全部客户'
  return selectedGroup.value.name
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
})

const columns = [
  { title: 'ID', dataIndex: 'id', width: 80 },
  { title: '公司名称', dataIndex: 'name', width: 200 },
  { title: '公司 ID', dataIndex: 'company_id', width: 120 },
  { title: '操作', slotName: 'actions', width: 150 },
]

const fetchGroups = async () => {
  try {
    const res = await groupApi.getCustomerGroups()
    groups.value = res.data.list || res.data
  } catch (err: any) {
    Message.error(err.message || '加载群组失败')
  }
}

const fetchCustomers = async () => {
  if (!selectedGroupId.value) {
    // 全部客户 - 跳转到客户列表页面
    window.location.href = '/customers'
    return
  }

  loading.value = true
  try {
    const res = await groupApi.applyGroupFilter(selectedGroupId.value, {
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    customers.value = res.data.list
    pagination.total = res.data.total
  } catch (err: any) {
    Message.error(err.message || '加载客户失败')
  } finally {
    loading.value = false
  }
}

const handleGroupSelect = (group: CustomerGroup | null) => {
  selectedGroup.value = group
  selectedGroupId.value = group?.id || null
  pagination.current = 1
  if (group) {
    fetchCustomers()
  }
}

const showCreateModal = (filter?: any) => {
  defaultFilter.value = filter || null
  formVisible.value = true
}

const handleCreateGroup = async (data: any) => {
  try {
    await groupApi.createCustomerGroup(data)
    Message.success('创建成功')
    formVisible.value = false
    await fetchGroups()
  } catch (err: any) {
    Message.error(err.message || '创建失败')
  }
}

const handleRemoveMember = async (customer_id: number) => {
  if (!selectedGroupId.value) return

  try {
    await groupApi.removeGroupMember(selectedGroupId.value, customer_id)
    Message.success('移除成功')
    fetchCustomers()
  } catch (err: any) {
    Message.error(err.message || '移除失败')
  }
}

const handleViewCustomer = (customer: Customer) => {
  window.open(`/customers/${customer.id}`, '_blank')
}

const onPageChange = (page: number) => {
  pagination.current = page
  fetchCustomers()
}

onMounted(() => {
  fetchGroups()
})
</script>

<style scoped>
.customer-groups-page {
  padding: 20px;
}

.groups-layout {
  display: flex;
  gap: 16px;
  margin-top: 16px;
}

GroupSidebar {
  width: 280px;
  flex-shrink: 0;
}

.groups-content {
  flex: 1;
}
</style>
```

- [ ] **Step 3: 创建侧边栏组件**

```vue
<!-- frontend/src/views/customer-groups/components/GroupSidebar.vue -->
<template>
  <a-card class="group-sidebar">
    <template #title>
      <a-space>
        <icon-folder />
        <span>群组</span>
      </a-space>
    </template>

    <a-menu :selected-keys="[selectedGroupId?.toString() || 'all']" @menu-item-click="handleMenuClick">
      <a-menu-item key="all">
        <template #icon><icon-apps /></template>
        全部客户
      </a-menu-item>

      <a-divider style="margin: 8px 0" />

      <a-menu-item key="create">
        <template #icon><icon-plus /></template>
        新建群组
      </a-menu-item>

      <a-divider style="margin: 8px 0" />

      <a-menu-item
        v-for="group in groups"
        :key="group.id.toString()"
        :data-group="group"
      >
        <template #icon>
          <icon-folder v-if="group.group_type === 'dynamic'" />
          <icon-user-group v-else />
        </template>
        {{ group.name }}
      </a-menu-item>
    </a-menu>
  </a-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface CustomerGroup {
  id: number
  name: string
  group_type: 'dynamic' | 'static'
}

const props = defineProps<{
  groups: CustomerGroup[]
  selectedGroupId: number | null
}>()

const emit = defineEmits<{
  (e: 'update:selectedGroupId', value: number | null): void
  (e: 'select', group: CustomerGroup | null): void
  (e: 'create'): void
}>()

const selectedGroupId = ref(props.selectedGroupId)

const handleMenuClick = (key: string, event: any) => {
  if (key === 'create') {
    emit('create')
  } else if (key === 'all') {
    selectedGroupId.value = null
    emit('update:selectedGroupId', null)
    emit('select', null)
  } else {
    const group = props.groups.find(g => g.id.toString() === key)
    if (group) {
      selectedGroupId.value = group.id
      emit('update:selectedGroupId', group.id)
      emit('select', group)
    }
  }
}
</script>

<style scoped>
.group-sidebar {
  height: fit-content;
}

:deep(.arco-menu-item) {
  margin-bottom: 4px;
}
</style>
```

- [ ] **Step 4: 创建表单组件**

```vue
<!-- frontend/src/views/customer-groups/components/GroupForm.vue -->
<template>
  <a-modal
    :visible="visible"
    title="新建群组"
    width="600px"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form :model="form" layout="vertical">
      <a-form-item label="群组名称" required>
        <a-input
          v-model="form.name"
          placeholder="请输入群组名称"
          maxlength="100"
          show-word-limit
        />
      </a-form-item>

      <a-form-item label="群组描述">
        <a-textarea
          v-model="form.description"
          placeholder="请输入群组描述（可选）"
          maxlength="500"
          show-word-limit
          :auto-size="{ minRows: 3, maxRows: 5 }"
        />
      </a-form-item>

      <a-form-item label="群组类型" required>
        <a-radio-group v-model="form.group_type">
          <a-radio value="dynamic">
            <template #icon><icon-folder /></template>
            动态群组（保存筛选条件）
          </a-radio>
          <a-radio value="static">
            <template #icon><icon-user-group /></template>
            静态群组（手动管理成员）
          </a-radio>
        </a-radio-group>
      </a-form-item>

      <a-alert
        v-if="form.group_type === 'dynamic' && defaultFilter"
        type="info"
        style="margin-top: 16px"
      >
        将保存当前筛选条件：{{ JSON.stringify(defaultFilter) }}
      </a-alert>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  defaultFilter?: any
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'submit', data: any): void
}>()

const form = reactive({
  name: '',
  description: '',
  group_type: 'dynamic' as 'dynamic' | 'static',
})

watch(
  () => props.visible,
  (val) => {
    if (val) {
      form.name = ''
      form.description = ''
      form.group_type = 'dynamic'
    }
  }
)

const handleSubmit = () => {
  if (!form.name) {
    return
  }

  emit('submit', {
    ...form,
    filter_conditions: form.group_type === 'dynamic' ? props.defaultFilter : null,
  })
}

const handleCancel = () => {
  emit('update:visible', false)
}
</script>
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/customer-groups/ frontend/src/router/index.ts
git commit -m "feat: 创建客户群组管理页面"
```

---

## 测试与验证

### Task 6: 编写集成测试

**Files:**
- Create: `backend/tests/integration/test_groups_api.py`

- [ ] **Step 1: 创建集成测试**

```python
# backend/tests/integration/test_groups_api.py
"""客户群组 API 集成测试"""

import pytest
from .conftest import client, test_user, test_engine, sync_db_session


class TestCreateGroup:
    """测试创建群组"""

    def test_create_dynamic_group(self, client, test_user):
        """测试创建动态群组"""
        response = client.post(
            "/api/v1/customer-groups",
            json={
                "name": "测试动态群组",
                "description": "测试描述",
                "group_type": "dynamic",
                "filter_conditions": {"customer_level": "KA"},
            },
            headers={"Authorization": f"Bearer {test_user['token']}"},
        )

        assert response.status_code == 201
        data = response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "测试动态群组"

    def test_create_static_group(self, client, test_user):
        """测试创建静态群组"""
        response = client.post(
            "/api/v1/customer-groups",
            json={
                "name": "测试静态群组",
                "group_type": "static",
            },
            headers={"Authorization": f"Bearer {test_user['token']}"},
        )

        assert response.status_code == 201
        data = response.json
        assert data["code"] == 0
        assert data["data"]["name"] == "测试静态群组"

    def test_create_group_missing_name(self, client, test_user):
        """测试创建群组缺少名称"""
        response = client.post(
            "/api/v1/customer-groups",
            json={"description": "测试描述"},
            headers={"Authorization": f"Bearer {test_user['token']}"},
        )

        assert response.status_code == 400
        data = response.json
        assert "不能为空" in data["message"]


class TestListGroups:
    """测试获取群组列表"""

    def test_list_user_groups(self, client, test_user):
        """测试获取用户的群组列表"""
        # 先创建一个群组
        client.post(
            "/api/v1/customer-groups",
            json={"name": "测试群组", "group_type": "dynamic"},
            headers={"Authorization": f"Bearer {test_user['token']}"},
        )

        response = client.get(
            "/api/v1/customer-groups",
            headers={"Authorization": f"Bearer {test_user['token']}"},
        )

        assert response.status_code == 200
        data = response.json
        assert data["code"] == 0
        assert len(data["data"]["list"]) >= 1


class TestDeleteGroup:
    """测试删除群组"""

    def test_delete_group(self, client, test_user):
        """测试删除群组"""
        # 先创建一个群组
        create_response = client.post(
            "/api/v1/customer-groups",
            json={"name": "待删除群组", "group_type": "dynamic"},
            headers={"Authorization": f"Bearer {test_user['token']}"},
        )
        group_id = create_response.json["data"]["id"]

        # 删除群组
        delete_response = client.delete(
            f"/api/v1/customer-groups/{group_id}",
            headers={"Authorization": f"Bearer {test_user['token']}"},
        )

        assert delete_response.status_code == 200
        assert delete_response.json["code"] == 0
```

- [ ] **Step 2: 运行集成测试**

```bash
cd backend
python3 -m pytest tests/integration/test_groups_api.py -v --tb=short
# Expected: All tests pass
```

- [ ] **Step 3: 提交**

```bash
git add backend/tests/integration/test_groups_api.py
git commit -m "test: 添加客户群组 API 集成测试"
```

---

## 完成标准

- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 前端页面可以正常创建、查看、删除群组
- [ ] 动态群组可以正确应用筛选条件
- [ ] 静态群组可以添加/移除成员
- [ ] 代码已推送到远程仓库

---

## 后续扩展（二期）

- Phase 3: 批量操作（打标签、导出、充值）
- Phase 4: 群组报表（消耗统计、对比分析）
