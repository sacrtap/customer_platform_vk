# Phase 0-7 已实现功能 - 测试补充计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Phase 0-7 已实现但缺少完整测试的功能模块创建单元测试、API 集成测试和 E2E 测试

**Architecture:** 分层测试策略 - 单元测试覆盖 Service 层业务逻辑，API 测试覆盖所有 REST 端点，E2E 测试覆盖关键用户流程

**Tech Stack:** pytest + pytest-asyncio + pytest-cov (后端), Playwright (E2E), Faker (测试数据)

---

## 文件结构规划

```
backend/tests/
├── unit/
│   ├── test_auth_service.py       # ⏳ 待创建 - Auth 服务
│   ├── test_tag_service.py        # ⏳ 待创建 - 标签服务
│   ├── test_user_service.py       # ⏳ 待创建 - 用户服务
│   ├── test_roles_service.py      # ⏳ 待创建 - 角色服务
│   ├── test_analytics_service.py  # ✅ 已有 (33 测试)
│   ├── test_billing_service.py    # ✅ 已有 (51 测试)
│   ├── test_customer_service.py   # ✅ 已有 (16 测试)
│   └── test_cache.py              # ✅ 已有 (45 测试)
├── integration/
│   ├── test_auth_api.py           # ⏳ 待创建
│   ├── test_users_api.py          # ⏳ 待创建
│   ├── test_roles_api.py          # ⏳ 待创建
│   ├── test_customers_api.py      # ⏳ 待创建
│   ├── test_billing_api.py        # ⏳ 待创建
│   ├── test_tags_api.py           # ⏳ 待创建
│   ├── test_analytics_api.py      # ⏳ 待创建
│   ├── test_audit_logs_api.py     # ⏳ 待创建
│   ├── test_files_api.py          # ⏳ 待创建
│   └── test_webhooks_api.py       # ⏳ 待创建
└── performance/
    ├── test_api_load.py           # ⏳ 待创建
    └── test_database_load.py      # ⏳ 待创建

frontend/tests/e2e/
├── test_login_flow.spec.ts        # ⏳ 待创建
├── test_customer_management.spec.ts # ⏳ 待创建
├── test_billing_workflow.spec.ts  # ⏳ 待创建
├── test_analytics_dashboard.spec.ts # ⏳ 待创建
└── test_role_permissions.spec.ts  # ⏳ 待创建
```

---

## Phase 1: 补全后端单元测试

### Task 1.1: Auth Service 单元测试

**Files:**
- Create: `backend/tests/unit/test_auth_service.py`
- Reference: `backend/app/services/auth.py`

- [ ] **Step 1: 创建测试文件框架**

```python
"""Auth Service 单元测试"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from app.services.auth import AuthService
from app.models.users import User


class MockDBSession:
    """Mock 数据库会话"""
    def __init__(self):
        self.execute = MagicMock()
        self.add = MagicMock()
        self.commit = MagicMock()
        self.flush = MagicMock()


def make_mock_execute_result(rows, scalar_value=None):
    """创建 execute 返回结果"""
    result = MagicMock()
    result.all = MagicMock(return_value=rows)
    result.scalar_one_or_none = MagicMock(return_value=rows[0] if rows else None)
    if scalar_value is not None:
        result.scalar = MagicMock(return_value=scalar_value)
    return result


@pytest.fixture
def mock_db():
    return MockDBSession()


@pytest.fixture
def auth_service(mock_db):
    with patch('app.services.auth.jwt'):
        yield AuthService(mock_db)
```

- [ ] **Step 2: 添加用户认证测试**

```python
class TestAuthService_Authenticate:
    """用户认证测试"""
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self, auth_service):
        """测试认证成功"""
        from app.models.users import User
        import bcrypt
        
        mock_user = User(
            id=1,
            username="testuser",
            password_hash=bcrypt.hashpw("password123".encode(), bcrypt.gensalt()),
            is_active=True,
        )
        auth_service.db.execute.return_value = make_mock_execute_result([mock_user])
        
        result = await auth_service.authenticate("testuser", "password123")
        
        assert result is not None
        assert result.id == 1
        assert result.username == "testuser"
    
    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self, auth_service):
        """测试密码错误"""
        from app.models.users import User
        import bcrypt
        
        mock_user = User(
            id=1,
            username="testuser",
            password_hash=bcrypt.hashpw("password123".encode(), bcrypt.gensalt()),
            is_active=True,
        )
        auth_service.db.execute.return_value = make_mock_execute_result([mock_user])
        
        result = await auth_service.authenticate("testuser", "wrongpassword")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, auth_service):
        """测试用户不存在"""
        auth_service.db.execute.return_value = make_mock_execute_result([])
        
        result = await auth_service.authenticate("nonexistent", "password")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self, auth_service):
        """测试非活跃用户"""
        from app.models.users import User
        import bcrypt
        
        mock_user = User(
            id=1,
            username="testuser",
            password_hash=bcrypt.hashpw("password123".encode(), bcrypt.gensalt()),
            is_active=False,
        )
        auth_service.db.execute.return_value = make_mock_execute_result([mock_user])
        
        result = await auth_service.authenticate("testuser", "password123")
        
        assert result is None
```

- [ ] **Step 3: 添加 Token 生成测试**

```python
class TestAuthService_CreateToken:
    """Token 生成测试"""
    
    @pytest.mark.asyncio
    async def test_create_access_token(self, auth_service):
        """测试创建访问令牌"""
        from app.models.users import User
        
        mock_user = User(id=1, username="testuser", is_system=False)
        
        with patch('app.services.auth.jwt.encode') as mock_encode:
            mock_encode.return_value = "mock_token"
            
            token = await auth_service.create_access_token(mock_user)
            
            assert token == "mock_token"
            mock_encode.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_token_for_system_user(self, auth_service):
        """测试系统用户 Token"""
        from app.models.users import User
        
        mock_user = User(id=1, username="admin", is_system=True)
        
        with patch('app.services.auth.jwt.encode') as mock_encode:
            mock_encode.return_value = "system_token"
            
            token = await auth_service.create_access_token(mock_user)
            
            assert token == "system_token"
```

- [ ] **Step 4: 运行测试验证**

```bash
cd backend
pytest tests/unit/test_auth_service.py -v --tb=short
# Expected: 6 tests pass
```

- [ ] **Step 5: 提交**

```bash
git add backend/tests/unit/test_auth_service.py
git commit -m "test: Auth Service 单元测试 (6 个测试)"
```

---

### Task 1.2: Tag Service 单元测试

**Files:**
- Create: `backend/tests/unit/test_tag_service.py`
- Reference: `backend/app/services/tags.py`

- [ ] **Step 1: 创建测试文件框架**

```python
"""Tag Service 单元测试"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from decimal import Decimal
from app.services.tags import TagService
from app.models.tags import Tag, CustomerTag, ProfileTag


class MockDBSession:
    """Mock 数据库会话"""
    def __init__(self):
        self.execute = MagicMock()
        self.add = MagicMock()
        self.add_all = MagicMock()
        self.commit = MagicMock()
        self.flush = MagicMock()
        self.refresh = MagicMock()
        self._new = []
    
    @property
    def new(self):
        return self._new
    
    def add(self, obj):
        self._new.append(obj)


def make_mock_execute_result(rows, scalar_value=None):
    result = MagicMock()
    result.all = MagicMock(return_value=rows)
    result.scalar_one_or_none = MagicMock(return_value=rows[0] if rows else None)
    if scalar_value is not None:
        result.scalar = MagicMock(return_value=scalar_value)
    scalars_result = MagicMock()
    scalars_result.all = MagicMock(return_value=rows)
    result.scalars.return_value = scalars_result
    return result


@pytest.fixture
def mock_db():
    return MockDBSession()


@pytest.fixture
def tag_service(mock_db):
    yield TagService(mock_db)
```

- [ ] **Step 2: 标签 CRUD 测试**

```python
class TestTagService_Create:
    """标签创建测试"""
    
    @pytest.mark.asyncio
    async def test_create_tag_success(self, tag_service):
        """测试创建标签成功"""
        from app.models.tags import Tag
        
        tag_data = {
            "name": "测试标签",
            "type": "customer",
            "category": "重要客户",
        }
        
        mock_tag = Tag(id=1, **tag_data, created_by=1)
        tag_service.db.execute.return_value = make_mock_execute_result([])
        tag_service.db.add = MagicMock()
        tag_service.db.commit = MagicMock()
        tag_service.db.refresh = MagicMock()
        
        with patch.object(TagService, 'get_tag_by_name', return_value=None):
            result = await tag_service.create_tag(tag_data, created_by=1)
            
            assert result is not None
            assert result.name == "测试标签"
            assert result.type == "customer"
    
    @pytest.mark.asyncio
    async def test_create_duplicate_tag(self, tag_service):
        """测试创建重复标签"""
        tag_data = {"name": "重复标签", "type": "customer"}
        
        existing_tag = Tag(id=1, **tag_data)
        
        with patch.object(TagService, 'get_tag_by_name', return_value=existing_tag):
            with pytest.raises(ValueError, match="标签已存在"):
                await tag_service.create_tag(tag_data, created_by=1)
```

- [ ] **Step 3: 客户标签关联测试**

```python
class TestTagService_CustomerTags:
    """客户标签关联测试"""
    
    @pytest.mark.asyncio
    async def test_add_customer_tag_success(self, tag_service):
        """测试给客户添加标签成功"""
        from app.models.tags import CustomerTag
        from app.models.customers import Customer
        
        mock_customer = Customer(id=1, name="客户 A")
        mock_tag = Tag(id=1, name="重要客户", type="customer")
        
        tag_service.db.execute.return_value = make_mock_execute_result([
            mock_customer, mock_tag
        ])
        
        result = await tag_service.add_customer_tag(customer_id=1, tag_id=1)
        
        assert result is True
        tag_service.db.add.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_customer_tag_customer_not_found(self, tag_service):
        """测试客户不存在"""
        tag_service.db.execute.return_value = make_mock_execute_result([])
        
        result = await tag_service.add_customer_tag(customer_id=999, tag_id=1)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_remove_customer_tag(self, tag_service):
        """测试移除客户标签"""
        from app.models.tags import CustomerTag
        
        mock_relation = CustomerTag(customer_id=1, tag_id=1)
        tag_service.db.execute.return_value = make_mock_execute_result([mock_relation])
        
        result = await tag_service.remove_customer_tag(customer_id=1, tag_id=1)
        
        assert result is True
        tag_service.db.commit.assert_called_once()
```

- [ ] **Step 4: 运行测试验证**

```bash
cd backend
pytest tests/unit/test_tag_service.py -v --tb=short
# Expected: 5 tests pass
```

- [ ] **Step 5: 提交**

```bash
git add backend/tests/unit/test_tag_service.py
git commit -m "test: Tag Service 单元测试 (5 个测试)"
```

---

### Task 1.3: User Service 单元测试

**Files:**
- Create: `backend/tests/unit/test_user_service.py`
- Reference: `backend/app/services/users.py`

- [ ] **Step 1: 创建测试文件框架** (参考 Task 1.1 结构)

- [ ] **Step 2: 用户 CRUD 测试**

```python
class TestUserService_Create:
    """用户创建测试"""
    
    @pytest.mark.asyncio
    async def test_create_user_success(self, user_service):
        """测试创建用户成功"""
        user_data = {
            "username": "newuser",
            "password": "password123",
            "email": "user@example.com",
            "real_name": "张三",
        }
        
        result = await user_service.create_user(user_data)
        
        assert result is not None
        assert result.username == "newuser"
        assert result.email == "user@example.com"
    
    @pytest.mark.asyncio
    async def test_create_duplicate_username(self, user_service):
        """测试用户名重复"""
        user_data = {"username": "existing", "password": "pass"}
        
        with patch.object(UserService, 'get_user_by_username', return_value=MagicMock()):
            with pytest.raises(ValueError, match="用户名已存在"):
                await user_service.create_user(user_data)
```

- [ ] **Step 3: 角色关联测试**

```python
class TestUserService_Roles:
    """用户角色关联测试"""
    
    @pytest.mark.asyncio
    async def test_assign_role_to_user(self, user_service):
        """测试给用户分配角色"""
        result = await user_service.assign_role_to_user(user_id=1, role_id=2)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_remove_role_from_user(self, user_service):
        """测试移除用户角色"""
        result = await user_service.remove_role_from_user(user_id=1, role_id=2)
        
        assert result is True
```

- [ ] **Step 4: 运行测试验证**

```bash
cd backend
pytest tests/unit/test_user_service.py -v --tb=short
# Expected: 4 tests pass
```

- [ ] **Step 5: 提交**

```bash
git add backend/tests/unit/test_user_service.py
git commit -m "test: User Service 单元测试 (4 个测试)"
```

---

### Task 1.4: Roles Service 单元测试

**Files:**
- Create: `backend/tests/unit/test_roles_service.py`
- Reference: `backend/app/services/roles.py`

- [ ] **Step 1: 创建测试文件框架**

- [ ] **Step 2: 角色 CRUD 测试**

```python
class TestRolesService_Create:
    """角色创建测试"""
    
    @pytest.mark.asyncio
    async def test_create_role_success(self, roles_service):
        """测试创建角色成功"""
        role_data = {
            "name": "测试角色",
            "description": "测试角色描述",
        }
        
        result = await roles_service.create_role(role_data)
        
        assert result is not None
        assert result.name == "测试角色"
    
    @pytest.mark.asyncio
    async def test_create_duplicate_role(self, roles_service):
        """测试创建重复角色"""
        role_data = {"name": "重复角色"}
        
        with patch.object(RolesService, 'get_role_by_name', return_value=MagicMock()):
            with pytest.raises(ValueError, match="角色已存在"):
                await roles_service.create_role(role_data)
```

- [ ] **Step 3: 权限分配测试**

```python
class TestRolesService_Permissions:
    """角色权限测试"""
    
    @pytest.mark.asyncio
    async def test_assign_permissions_to_role(self, roles_service):
        """测试给角色分配权限"""
        role_id = 1
        permission_ids = [1, 2, 3]
        
        result = await roles_service.assign_permissions_to_role(
            role_id, permission_ids
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_role_permissions(self, roles_service):
        """测试获取角色权限"""
        role_id = 1
        
        result = await roles_service.get_role_permissions(role_id)
        
        assert isinstance(result, list)
```

- [ ] **Step 4: 运行测试验证**

```bash
cd backend
pytest tests/unit/test_roles_service.py -v --tb=short
# Expected: 4 tests pass
```

- [ ] **Step 5: 提交**

```bash
git add backend/tests/unit/test_roles_service.py
git commit -m "test: Roles Service 单元测试 (4 个测试)"
```

---

## Phase 2: API 集成测试

### Task 2.1: Auth API 测试

**Files:**
- Create: `backend/tests/integration/test_auth_api.py`
- Reference: `backend/app/routes/auth.py`

- [ ] **Step 1: 创建测试文件框架**

```python
"""Auth API 集成测试"""
import pytest
from httpx import AsyncClient
from app.main import create_app
from app.models.users import User
import bcrypt


@pytest.fixture
async def test_client(test_engine):
    """创建测试客户端"""
    from app.config import settings
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.models.base import Base
    
    app = create_app()
    
    async_session_maker = async_sessionmaker(
        test_engine, expire_on_commit=False
    )
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def test_user(test_engine):
    """创建测试用户"""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select
    
    async with AsyncSession(test_engine) as session:
        hashed = bcrypt.hashpw(b"password123", bcrypt.gensalt())
        user = User(
            username="testuser",
            password_hash=hashed.decode(),
            email="test@example.com",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
async def auth_headers(test_client, test_user):
    """生成认证头"""
    login_resp = await test_client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "password123",
    })
    token = login_resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 2: 登录 API 测试**

```python
class TestAuthAPI_Login:
    """登录 API 测试"""
    
    @pytest.mark.asyncio
    async def test_login_success(self, test_client, test_user):
        """测试登录成功"""
        response = await test_client.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "password123",
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, test_client, test_user):
        """测试密码错误"""
        response = await test_client.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "wrongpassword",
        })
        
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == 40101
    
    @pytest.mark.asyncio
    async def test_login_user_not_found(self, test_client):
        """测试用户不存在"""
        response = await test_client.post("/api/v1/auth/login", json={
            "username": "nonexistent",
            "password": "password",
        })
        
        assert response.status_code == 404
```

- [ ] **Step 3: Token 刷新测试**

```python
class TestAuthAPI_TokenRefresh:
    """Token 刷新测试"""
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, test_client, test_user):
        """测试刷新 Token 成功"""
        # 先登录获取 token
        login_resp = await test_client.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "password123",
        })
        refresh_token = login_resp.json()["data"]["refresh_token"]
        
        # 刷新 token
        response = await test_client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        
        assert response.status_code == 200
        assert "access_token" in response.json()["data"]
    
    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, test_client):
        """测试无效刷新 Token"""
        response = await test_client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid_token",
        })
        
        assert response.status_code == 401
```

- [ ] **Step 4: 运行测试验证**

```bash
cd backend
pytest tests/integration/test_auth_api.py -v --tb=short
# Expected: 5 tests pass
```

- [ ] **Step 5: 提交**

```bash
git add backend/tests/integration/test_auth_api.py
git commit -m "test: Auth API 集成测试 (5 个测试)"
```

---

### Task 2.2: Users API 测试

**Files:**
- Create: `backend/tests/integration/test_users_api.py`
- Reference: `backend/app/routes/users.py`

- [ ] **Step 1: 用户列表 API 测试**

```python
class TestUsersAPI_List:
    """用户列表 API 测试"""
    
    @pytest.mark.asyncio
    async def test_get_users_success(self, test_client, auth_headers):
        """测试获取用户列表"""
        response = await test_client.get(
            "/api/v1/users?page=1&page_size=20",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "list" in data["data"]
        assert "total" in data["data"]
    
    @pytest.mark.asyncio
    async def test_get_users_with_filters(self, test_client, auth_headers):
        """测试筛选用户"""
        response = await test_client.get(
            "/api/v1/users?keyword=admin&is_active=true",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
```

- [ ] **Step 2: 用户 CRUD 测试**

```python
class TestUsersAPI_CRUD:
    """用户 CRUD API 测试"""
    
    @pytest.mark.asyncio
    async def test_create_user_success(self, test_client, auth_headers):
        """测试创建用户成功"""
        response = await test_client.post(
            "/api/v1/users",
            json={
                "username": "newuser",
                "password": "password123",
                "email": "user@example.com",
                "real_name": "张三",
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["username"] == "newuser"
    
    @pytest.mark.asyncio
    async def test_create_duplicate_user(self, test_client, auth_headers):
        """测试创建重复用户"""
        # 先创建一个
        await test_client.post("/api/v1/users", json={
            "username": "duplicate",
            "password": "password123",
        }, headers=auth_headers)
        
        # 再创建重复的
        response = await test_client.post("/api/v1/users", json={
            "username": "duplicate",
            "password": "password123",
        }, headers=auth_headers)
        
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_update_user_success(self, test_client, auth_headers):
        """测试更新用户"""
        response = await test_client.put(
            "/api/v1/users/1",
            json={"real_name": "新名字", "email": "new@example.com"},
            headers=auth_headers,
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_delete_user_success(self, test_client, auth_headers):
        """测试删除用户"""
        response = await test_client.delete(
            "/api/v1/users/1",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
```

- [ ] **Step 3: 运行测试验证**

```bash
cd backend
pytest tests/integration/test_users_api.py -v --tb=short
# Expected: 7 tests pass
```

- [ ] **Step 4: 提交**

```bash
git add backend/tests/integration/test_users_api.py
git commit -m "test: Users API 集成测试 (7 个测试)"
```

---

### Task 2.3: Audit Logs API 测试

**Files:**
- Create: `backend/tests/integration/test_audit_logs_api.py`
- Reference: `backend/app/routes/audit_logs.py`

- [ ] **Step 1: 审计日志 API 测试**

```python
class TestAuditLogsAPI:
    """审计日志 API 测试"""
    
    @pytest.mark.asyncio
    async def test_get_audit_logs_success(self, test_client, auth_headers):
        """测试获取审计日志列表"""
        response = await test_client.get(
            "/api/v1/audit-logs?page=1&page_size=20",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "list" in data["data"]
        assert "total" in data["data"]
    
    @pytest.mark.asyncio
    async def test_get_audit_logs_with_filters(self, test_client, auth_headers):
        """测试筛选审计日志"""
        response = await test_client.get(
            "/api/v1/audit-logs?action=create&module=customers",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_get_audit_actions(self, test_client, auth_headers):
        """测试获取操作类型列表"""
        response = await test_client.get(
            "/api/v1/audit-logs/actions",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        assert isinstance(response.json()["data"], list)
    
    @pytest.mark.asyncio
    async def test_get_audit_modules(self, test_client, auth_headers):
        """测试获取模块列表"""
        response = await test_client.get(
            "/api/v1/audit-logs/modules",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        assert isinstance(response.json()["data"], list)
```

- [ ] **Step 2: 运行测试验证**

```bash
cd backend
pytest tests/integration/test_audit_logs_api.py -v --tb=short
# Expected: 4 tests pass
```

- [ ] **Step 3: 提交**

```bash
git add backend/tests/integration/test_audit_logs_api.py
git commit -m "test: Audit Logs API 集成测试 (4 个测试)"
```

---

## Phase 3: E2E 测试

### Task 3.1: 登录流程 E2E 测试

**Files:**
- Create: `frontend/tests/e2e/test_login_flow.spec.ts`

- [ ] **Step 1: 创建登录测试**

```typescript
import { test, expect } from '@playwright/test';

test.describe('登录流程', () => {
  test('成功登录', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    
    await expect(page).toHaveURL('/');
    await expect(page.locator('.user-menu')).toBeVisible();
  });

  test('密码错误提示', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');
    
    await expect(page.locator('.arco-message-error')).toBeVisible();
    await expect(page).toHaveURL('/login');
  });

  test('未登录访问受保护页面', async ({ page }) => {
    await page.goto('/customers');
    
    // 应该重定向到登录页
    await expect(page).toHaveURL('/login');
  });

  test('已登录访问登录页重定向', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/');
    
    await page.goto('/login');
    
    // 应该重定向到首页
    await expect(page).toHaveURL('/');
  });
});
```

- [ ] **Step 2: 运行测试验证**

```bash
cd frontend
npx playwright test tests/e2e/test_login_flow.spec.ts --ui
```

- [ ] **Step 3: 提交**

```bash
git add frontend/tests/e2e/test_login_flow.spec.ts
git commit -m "test: 登录流程 E2E 测试 (4 个测试)"
```

---

### Task 3.2: 客户管理 E2E 测试

**Files:**
- Create: `frontend/tests/e2e/test_customer_management.spec.ts`

- [ ] **Step 1: 创建客户管理测试**

```typescript
import { test, expect } from '@playwright/test';

test.describe('客户管理', () => {
  test.beforeEach(async ({ page }) => {
    // 登录
    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/');
  });

  test('访问客户列表页面', async ({ page }) => {
    await page.goto('/customers');
    
    await expect(page.locator('h1')).toContainText('客户管理');
    await expect(page.locator('.arco-table')).toBeVisible();
  });

  test('创建新客户', async ({ page }) => {
    await page.goto('/customers');
    
    // 点击新建按钮
    await page.click('button:has-text("新建客户")');
    
    // 填写表单
    await page.fill('input[name="company_id"]', 'E2E001');
    await page.fill('input[name="name"]', 'E2E 测试公司');
    await page.fill('input[name="email"]', 'e2e@test.com');
    await page.select('select[name="account_type"]', 'formal');
    
    // 提交
    await page.click('button[type="submit"]');
    
    // 验证成功提示
    await expect(page.locator('.arco-message-success')).toBeVisible();
    
    // 验证表格中出现新客户
    await expect(page.locator('tbody')).toContainText('E2E 测试公司');
  });

  test('搜索客户', async ({ page }) => {
    await page.goto('/customers');
    
    // 输入搜索关键词
    await page.fill('input[placeholder*="关键词"]', '测试');
    await page.click('button:has-text("查询")');
    
    // 验证搜索结果
    await expect(page.locator('tbody tr')).toBeVisible();
  });

  test('分页功能', async ({ page }) => {
    await page.goto('/customers');
    
    // 验证分页控件存在
    await expect(page.locator('.arco-pagination')).toBeVisible();
    
    // 点击下一页
    await page.click('.arco-pagination-item-next');
    
    // 验证页码变化
    await expect(page.locator('.arco-pagination-item-active')).toContainText('2');
  });
});
```

- [ ] **Step 2: 提交**

```bash
git add frontend/tests/e2e/test_customer_management.spec.ts
git commit -m "test: 客户管理 E2E 测试 (5 个测试)"
```

---

### Task 3.3: 结算单工作流 E2E 测试

**Files:**
- Create: `frontend/tests/e2e/test_billing_workflow.spec.ts`

- [ ] **Step 1: 创建结算单工作流测试**

```typescript
import { test, expect } from '@playwright/test';

test.describe('结算单工作流', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/');
  });

  test('访问结算单列表', async ({ page }) => {
    await page.goto('/billing/invoices');
    
    await expect(page.locator('h1')).toContainText('结算单管理');
    await expect(page.locator('.arco-table')).toBeVisible();
  });

  test('生成结算单', async ({ page }) => {
    await page.goto('/billing/invoices');
    
    await page.click('button:has-text("生成结算单")');
    
    // 填写结算单信息
    await page.fill('input[name="period_start"]', '2026-03-01');
    await page.fill('input[name="period_end"]', '2026-03-31');
    
    await page.click('button:has-text("生成")');
    
    await expect(page.locator('.arco-message-success')).toBeVisible();
  });

  test('结算单状态流转', async ({ page }) => {
    await page.goto('/billing/invoices');
    
    // 选择草稿状态的结算单
    const draftInvoice = page.locator('tbody tr').first();
    await draftInvoice.click();
    
    // 提交结算单
    await page.click('button:has-text("提交")');
    await expect(page.locator('.arco-message-success')).toBeVisible();
    
    // 确认结算单
    await page.click('button:has-text("确认")');
    await expect(page.locator('.arco-message-success')).toBeVisible();
    
    // 付款
    await page.click('button:has-text("付款")');
    await expect(page.locator('.arco-message-success')).toBeVisible();
    
    // 完成结算
    await page.click('button:has-text("完成")');
    await expect(page.locator('.arco-message-success')).toBeVisible();
    
    // 验证最终状态
    await expect(page.locator('.status-tag')).toHaveText('已完成');
  });
});
```

- [ ] **Step 2: 提交**

```bash
git add frontend/tests/e2e/test_billing_workflow.spec.ts
git commit -m "test: 结算单工作流 E2E 测试 (4 个测试)"
```

---

## Phase 4: 测试统计与报告

### Task 4.1: 生成测试覆盖率报告

**Files:**
- Create: `scripts/generate_coverage_report.sh`

- [ ] **Step 1: 创建报告生成脚本**

```bash
#!/bin/bash
# scripts/generate_coverage_report.sh

echo "📊 生成测试覆盖率报告..."

cd backend

# 运行所有测试并生成覆盖率
pytest \
    --cov=app \
    --cov-report=html:../docs/testing/coverage-reports/html \
    --cov-report=xml:../docs/testing/coverage-reports/coverage.xml \
    --cov-report=term-missing \
    tests/

echo "✅ 报告已生成:"
echo "  - HTML: docs/testing/coverage-reports/html/index.html"
echo "  - XML: docs/testing/coverage-reports/coverage.xml"

# 打开 HTML 报告 (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    open docs/testing/coverage-reports/html/index.html
fi
```

- [ ] **Step 2: 运行脚本生成报告**

```bash
chmod +x scripts/generate_coverage_report.sh
./scripts/generate_coverage_report.sh
```

- [ ] **Step 3: 提交**

```bash
git add scripts/generate_coverage_report.sh
git commit -m "chore: 添加测试覆盖率报告生成脚本"
```

---

## 测试统计总表

| 阶段 | 测试文件 | 测试数 | 类型 |
|------|---------|--------|------|
| **Phase 1** | test_auth_service.py | 6 | 单元 |
| | test_tag_service.py | 5 | 单元 |
| | test_user_service.py | 4 | 单元 |
| | test_roles_service.py | 4 | 单元 |
| **Phase 2** | test_auth_api.py | 5 | 集成 |
| | test_users_api.py | 7 | 集成 |
| | test_audit_logs_api.py | 4 | 集成 |
| **Phase 3** | test_login_flow.spec.ts | 4 | E2E |
| | test_customer_management.spec.ts | 5 | E2E |
| | test_billing_workflow.spec.ts | 4 | E2E |
| **总计** | **9 个文件** | **48 个新测试** | - |

---

## 执行选择

计划已完成并保存到 `docs/testing/phase0-7-test-plan.md`。两个执行选项：

**1. Subagent-Driven (推荐)** - 每个任务分派独立的 subagent 执行，任务间审查，快速迭代

**2. Inline Execution** - 在当前会话中使用 executing-plans 批量执行，设置检查点

**选择哪个方案？**
