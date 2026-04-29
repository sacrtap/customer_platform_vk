# 审计日志全面优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展审计日志系统，覆盖批量操作、嵌套关系、敏感操作、Webhook 过滤和缺失模块映射

**Architecture:** 混合模式 - 中间件负责标准 CRUD，路由负责复杂操作，统一通过辅助函数记录。新增 `operation_type` 和 `metadata` 字段区分操作类型。

**Tech Stack:** Python 3.12, Sanic, SQLAlchemy 2.0, Alembic, pytest

---

### Task 1: 数据库迁移 - 扩展 AuditLog 模型

**Files:**
- Modify: `backend/app/models/billing.py:192-203`
- Create: `backend/alembic/versions/2026_04_29_add_audit_log_fields.py`

- [ ] **Step 1: 扩展 AuditLog 模型**

修改 `backend/app/models/billing.py` 中的 `AuditLog` 类，添加两个新字段：

```python
class AuditLog(BaseModel):
    """审计日志表"""

    __tablename__ = "audit_logs"

    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(50), nullable=False)
    module = Column(String(50), nullable=False)
    record_id = Column(Integer)
    record_type = Column(String(50))
    changes = Column(JSON)  # {"before": {...}, "after": {...}}
    ip_address = Column(String(45))
    # 新增字段
    operation_type = Column(
        String(20),
        default="standard",
        comment="操作类型: standard/batch/relation/sensitive",
    )
    metadata = Column(
        JSON,
        nullable=True,
        comment="扩展元数据: 批量统计、关系ID列表等",
    )
```

- [ ] **Step 2: 创建 Alembic 迁移脚本**

创建文件 `backend/alembic/versions/2026_04_29_add_audit_log_fields.py`：

```python
"""add audit log operation_type and metadata fields

Revision ID: 2026_04_29_audit_fields
Revises: 
Create Date: 2026-04-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2026_04_29_audit_fields'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'audit_logs',
        sa.Column('operation_type', sa.String(20), server_default='standard',
                  comment='操作类型: standard/batch/relation/sensitive')
    )
    op.add_column(
        'audit_logs',
        sa.Column('metadata', sa.JSON(), nullable=True,
                  comment='扩展元数据: 批量统计、关系ID列表等')
    )


def downgrade() -> None:
    op.drop_column('audit_logs', 'metadata')
    op.drop_column('audit_logs', 'operation_type')
```

- [ ] **Step 3: 运行迁移验证**

```bash
cd backend && alembic upgrade head
```

Expected: 迁移成功，`audit_logs` 表新增 `operation_type` 和 `metadata` 列

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/billing.py backend/alembic/versions/2026_04_29_add_audit_log_fields.py
git commit -m "feat(audit): add operation_type and metadata fields to AuditLog model"
```

---

### Task 2: 创建审计辅助函数库

**Files:**
- Create: `backend/app/utils/__init__.py`
- Create: `backend/app/utils/audit_helpers.py`
- Test: `backend/tests/unit/test_audit_helpers.py`

- [ ] **Step 1: 创建 utils 包**

创建文件 `backend/app/utils/__init__.py`：

```python
"""工具函数包"""
```

- [ ] **Step 2: 创建审计辅助函数**

创建文件 `backend/app/utils/audit_helpers.py`：

```python
"""审计日志辅助函数

提供统一的审计记录创建、批量操作摘要构建、敏感数据脱敏等功能。
"""

from sqlalchemy.ext.asyncio import AsyncSession
from ..models.billing import AuditLog


async def create_audit_entry(
    db_session: AsyncSession,
    user_id: int,
    action: str,
    module: str,
    record_id: int | None = None,
    record_type: str | None = None,
    changes: dict | None = None,
    ip_address: str | None = None,
    operation_type: str = "standard",
    metadata: dict | None = None,
) -> AuditLog:
    """统一审计记录创建函数

    Args:
        db_session: 数据库会话
        user_id: 操作用户 ID
        action: 操作类型 (create/update/delete/batch_create 等)
        module: 模块名 (users/customers/billing 等)
        record_id: 记录 ID
        record_type: 记录类型
        changes: 变更数据 {"before": {...}, "after": {...}}
        ip_address: IP 地址
        operation_type: 操作类型 (standard/batch/relation/sensitive)
        metadata: 扩展元数据

    Returns:
        AuditLog: 创建的审计日志对象
    """
    audit_entry = AuditLog(
        user_id=user_id,
        action=action,
        module=module,
        record_id=record_id,
        record_type=record_type,
        changes=changes,
        ip_address=ip_address,
        operation_type=operation_type,
        metadata=metadata,
    )
    db_session.add(audit_entry)
    await db_session.commit()
    return audit_entry


def build_batch_audit_summary(
    operation: str,
    total_count: int,
    success_count: int,
    failed_count: int | None = None,
    details: list | None = None,
) -> dict:
    """构建批量操作审计摘要

    Args:
        operation: 操作名称 (customer_import/user_import 等)
        total_count: 总数量
        success_count: 成功数量
        failed_count: 失败数量（可选，默认 total - success）
        details: 错误详情列表

    Returns:
        dict: 批量操作摘要
    """
    if failed_count is None:
        failed_count = total_count - success_count

    return {
        "operation": operation,
        "total_count": total_count,
        "success_count": success_count,
        "failed_count": failed_count,
        "details": details or [],
    }


def mask_sensitive_data(data: dict, fields: list | None = None) -> dict:
    """敏感数据脱敏

    Args:
        data: 原始数据
        fields: 需要脱敏的字段列表

    Returns:
        dict: 脱敏后的数据
    """
    if fields is None:
        fields = ["password", "password_hash", "token", "secret"]

    masked = data.copy()
    for field in fields:
        if field in masked:
            masked[field] = "***MASKED***"
    return masked
```

- [ ] **Step 3: 编写单元测试**

创建文件 `backend/tests/unit/test_audit_helpers.py`：

```python
"""审计辅助函数单元测试"""

import pytest
from app.utils.audit_helpers import (
    create_audit_entry,
    build_batch_audit_summary,
    mask_sensitive_data,
)


class TestBuildBatchAuditSummary:
    """测试 build_batch_audit_summary 函数"""

    def test_basic_summary(self):
        """测试基本批量操作摘要"""
        result = build_batch_audit_summary(
            operation="customer_import",
            total_count=10,
            success_count=8,
        )

        assert result["operation"] == "customer_import"
        assert result["total_count"] == 10
        assert result["success_count"] == 8
        assert result["failed_count"] == 2
        assert result["details"] == []

    def test_custom_failed_count(self):
        """测试自定义失败数量"""
        result = build_batch_audit_summary(
            operation="user_import",
            total_count=5,
            success_count=3,
            failed_count=1,
        )

        assert result["failed_count"] == 1

    def test_with_details(self):
        """测试带错误详情的摘要"""
        details = [
            {"row": 3, "error": "用户名已存在"},
            {"row": 5, "error": "邮箱格式错误"},
        ]

        result = build_batch_audit_summary(
            operation="user_import",
            total_count=5,
            success_count=3,
            details=details,
        )

        assert len(result["details"]) == 2
        assert result["details"][0]["row"] == 3


class TestMaskSensitiveData:
    """测试 mask_sensitive_data 函数"""

    def test_default_fields(self):
        """测试默认字段脱敏"""
        data = {
            "username": "test",
            "password": "secret123",
            "password_hash": "abc123",
            "email": "test@example.com",
        }

        result = mask_sensitive_data(data)

        assert result["username"] == "test"
        assert result["password"] == "***MASKED***"
        assert result["password_hash"] == "***MASKED***"
        assert result["email"] == "test@example.com"

    def test_custom_fields(self):
        """测试自定义字段脱敏"""
        data = {
            "api_key": "key123",
            "token": "tok_abc",
            "name": "Test",
        }

        result = mask_sensitive_data(data, fields=["api_key", "token"])

        assert result["api_key"] == "***MASKED***"
        assert result["token"] == "***MASKED***"
        assert result["name"] == "Test"

    def test_missing_fields(self):
        """测试不存在的字段不影响"""
        data = {"username": "test"}

        result = mask_sensitive_data(data)

        assert result["username"] == "test"

    def test_does_not_modify_original(self):
        """测试不修改原始数据"""
        data = {"password": "secret"}
        original = data.copy()

        mask_sensitive_data(data)

        assert data == original


class TestCreateAuditEntry:
    """测试 create_audit_entry 函数"""

    @pytest.mark.asyncio
    async def test_create_standard_audit_entry(self, db_session):
        """测试创建标准审计日志"""
        audit = await create_audit_entry(
            db_session=db_session,
            user_id=1,
            action="create",
            module="customers",
            record_id=123,
            record_type="customer",
            ip_address="127.0.0.1",
        )

        assert audit.user_id == 1
        assert audit.action == "create"
        assert audit.module == "customers"
        assert audit.record_id == 123
        assert audit.operation_type == "standard"
        assert audit.metadata is None

    @pytest.mark.asyncio
    async def test_create_batch_audit_entry(self, db_session):
        """测试创建批量操作审计日志"""
        metadata = build_batch_audit_summary(
            operation="customer_import",
            total_count=10,
            success_count=8,
        )

        audit = await create_audit_entry(
            db_session=db_session,
            user_id=1,
            action="batch_create",
            module="customers",
            operation_type="batch",
            metadata=metadata,
            ip_address="127.0.0.1",
        )

        assert audit.operation_type == "batch"
        assert audit.metadata["total_count"] == 10
        assert audit.metadata["success_count"] == 8

    @pytest.mark.asyncio
    async def test_create_sensitive_audit_entry(self, db_session):
        """测试创建敏感操作审计日志"""
        audit = await create_audit_entry(
            db_session=db_session,
            user_id=1,
            action="reset_password",
            module="users",
            record_id=123,
            record_type="user",
            operation_type="sensitive",
            ip_address="127.0.0.1",
        )

        assert audit.operation_type == "sensitive"
        assert audit.action == "reset_password"
```

- [ ] **Step 4: 运行测试验证**

```bash
cd backend && python -m pytest tests/unit/test_audit_helpers.py -v
```

Expected: 所有测试通过

- [ ] **Step 5: 提交**

```bash
git add backend/app/utils/__init__.py backend/app/utils/audit_helpers.py backend/tests/unit/test_audit_helpers.py
git commit -m "feat(audit): add audit helper functions with unit tests"
```

---

### Task 3: 中间件增强

**Files:**
- Modify: `backend/app/middleware/audit.py` (全文)
- Test: `backend/tests/integration/test_audit_middleware.py`

- [ ] **Step 1: 增强中间件**

修改 `backend/app/middleware/audit.py`，进行以下改动：

**3.1 添加 Webhook 路径到跳过列表**

```python
# 在 log_write_operations 函数中，修改 skip_paths 列表
skip_paths = [
    "/health",
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/refresh",
    "/api/v1/auth/me",
    # Webhook 外部回调（无认证用户，审计无意义）
    "/api/v1/webhooks/invoice-confirmation",
    "/api/v1/webhooks/payment-notify",
]
```

**3.2 添加 profiles 模块映射**

```python
# 在 _MODULE_MODEL_MAP 中添加
_MODULE_MODEL_MAP = {
    # ... 现有映射保持不变 ...
    
    # 新增映射
    "profiles": CustomerProfile,  # 画像管理模块
}
```

完整的映射表更新（替换第 199-222 行）：

```python
_MODULE_MODEL_MAP = {
    # 直接匹配
    "users": User,
    "roles": Role,
    "permissions": Permission,
    "customers": Customer,
    "tags": Tag,
    "customer-tags": CustomerTag,
    "profile-tags": ProfileTag,
    "groups": CustomerGroup,
    "files": File,
    "industry-types": IndustryType,
    # billing 子路径特殊处理
    "billing-pricing-rules": PricingRule,
    "billing-invoices": Invoice,
    "billing-recharge": RechargeRecord,
    "billing-balances": CustomerBalance,
    "billing": CustomerBalance,  # fallback
    # dict 子路径
    "dict-industry-types": IndustryType,
    "dict": IndustryType,  # fallback
    # customer profile 子路径
    "customers-profile": CustomerProfile,
    # 新增：画像管理模块
    "profiles": CustomerProfile,
}
```

**3.3 增强 extract_record_id_from_path 函数**

替换第 284-299 行的 `extract_record_id_from_path` 函数：

```python
def extract_record_id_from_path(path: str) -> int | None:
    """从路径提取记录 ID

    支持多种路径格式:
    - 标准路径: /api/v1/users/123
    - 嵌套路径: /api/v1/customers/123/tags/456
    - 动作路径: /api/v1/billing/invoices/123/submit
    """
    parts = path.strip("/").split("/")

    # 嵌套路径: /api/v1/customers/123/tags/456
    # 提取关系 ID (456)
    if len(parts) >= 6:
        try:
            return int(parts[5])
        except ValueError:
            pass

    # 动作路径: /api/v1/billing/invoices/123/submit
    # 提取实体 ID (123)
    if len(parts) >= 5:
        try:
            return int(parts[4])
        except ValueError:
            pass

    # 标准路径: /api/v1/users/123
    if len(parts) >= 4:
        try:
            return int(parts[3])
        except ValueError:
            pass

    return None
```

**3.4 添加敏感操作检测函数**

在文件末尾添加新函数：

```python
def is_sensitive_operation(path: str) -> bool:
    """检测是否为敏感操作（密码重置、权限变更等）

    Args:
        path: 请求路径

    Returns:
        bool: 是否为敏感操作
    """
    sensitive_patterns = [
        "/reset-password",
        "/forgot-password",
    ]
    return any(pattern in path for pattern in sensitive_patterns)
```

**3.5 在 AuditLog 创建时添加 operation_type**

修改 `log_write_operations` 函数中创建 AuditLog 的部分（第 119-128 行）：

```python
# 检测敏感操作
operation_type = "sensitive" if is_sensitive_operation(request.path) else "standard"

# 记录审计日志
db_session: AsyncSession = request.ctx.db_session
audit_entry = AuditLog(
    user_id=user_id,
    action=action,
    module=module,
    record_id=record_id,
    record_type=record_type,
    changes=changes,
    ip_address=ip_address,
    operation_type=operation_type,
)
db_session.add(audit_entry)
await db_session.commit()
```

- [ ] **Step 2: 编写集成测试**

创建文件 `backend/tests/integration/test_audit_middleware.py`：

```python
"""审计中间件集成测试"""

import pytest
from app.middleware.audit import (
    extract_record_id_from_path,
    extract_module_from_path,
    is_sensitive_operation,
    get_model_for_module,
)


class TestExtractRecordIdFromPath:
    """测试 extract_record_id_from_path 函数"""

    def test_standard_path(self):
        """测试标准路径"""
        assert extract_record_id_from_path("/api/v1/users/123") == 123

    def test_nested_path(self):
        """测试嵌套路径（关系 ID）"""
        assert extract_record_id_from_path("/api/v1/customers/123/tags/456") == 456

    def test_action_path(self):
        """测试动作路径"""
        assert extract_record_id_from_path("/api/v1/billing/invoices/123/submit") == 123

    def test_no_id_path(self):
        """测试无 ID 路径"""
        assert extract_record_id_from_path("/api/v1/billing/recharge") is None

    def test_import_path(self):
        """测试导入路径"""
        assert extract_record_id_from_path("/api/v1/customers/import") is None


class TestExtractModuleFromPath:
    """测试 extract_module_from_path 函数"""

    def test_users_module(self):
        assert extract_module_from_path("/api/v1/users/123") == "users"

    def test_customers_module(self):
        assert extract_module_from_path("/api/v1/customers/123") == "customers"

    def test_billing_module(self):
        assert extract_module_from_path("/api/v1/billing/recharge") == "billing"

    def test_profiles_module(self):
        assert extract_module_from_path("/api/v1/profiles/123") == "profiles"


class TestIsSensitiveOperation:
    """测试 is_sensitive_operation 函数"""

    def test_reset_password(self):
        assert is_sensitive_operation("/api/v1/users/123/reset-password") is True

    def test_forgot_password(self):
        assert is_sensitive_operation("/api/v1/auth/forgot-password") is True

    def test_normal_update(self):
        assert is_sensitive_operation("/api/v1/users/123") is False

    def test_create_customer(self):
        assert is_sensitive_operation("/api/v1/customers") is False


class TestModuleMapping:
    """测试模块映射"""

    def test_profiles_mapping(self):
        """测试 profiles 模块映射"""
        from app.models.customers import CustomerProfile

        model = get_model_for_module("profiles")
        assert model == CustomerProfile

    def test_billing_invoices_mapping(self):
        """测试 billing-invoices 映射"""
        from app.models.billing import Invoice

        model = get_model_for_module("billing", "/api/v1/billing/invoices/123")
        assert model == Invoice
```

- [ ] **Step 3: 运行测试验证**

```bash
cd backend && python -m pytest tests/integration/test_audit_middleware.py -v
```

Expected: 所有测试通过

- [ ] **Step 4: 提交**

```bash
git add backend/app/middleware/audit.py backend/tests/integration/test_audit_middleware.py
git commit -m "feat(audit): enhance middleware with webhook skip, profiles mapping, sensitive detection"
```

---

### Task 4: 批量操作审计 - 客户/用户导入

**Files:**
- Modify: `backend/app/routes/customers.py` (import_customers 端点)
- Modify: `backend/app/routes/users.py` (import_users 端点)
- Test: `backend/tests/integration/test_customers_api.py` (补充导入审计测试)
- Test: `backend/tests/integration/test_users_api.py` (补充导入审计测试)

- [ ] **Step 1: 客户导入审计记录**

在 `backend/app/routes/customers.py` 的 `import_customers` 函数中（第 530 行 `success_count, errors = ...` 之后，第 535 行 `return json(...)` 之前）添加审计记录：

首先添加导入（在文件顶部，第 18 行后）：

```python
from ..utils.audit_helpers import create_audit_entry, build_batch_audit_summary
```

然后在第 533 行（`await cache_service.invalidate_customer_cache()` 之后，`return json` 之前）添加：

```python
        # 记录批量导入审计日志
        summary = build_batch_audit_summary(
            operation="customer_import",
            total_count=len(customers_data),
            success_count=success_count,
            failed_count=len(errors),
            details=errors[:10],  # 只记录前 10 个错误
        )

        from ..middleware.auth import get_current_user
        current_user = get_current_user(request)

        await create_audit_entry(
            db_session=db_session,
            user_id=current_user.get("user_id") if current_user else None,
            action="batch_create",
            module="customers",
            operation_type="batch",
            metadata=summary,
            ip_address=request.headers.get(
                "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
            ),
        )
```查看 `import_customers` 函数的实现，这些变量应该已经存在。

- [ ] **Step 2: 用户导入审计记录**

**注意**：用户导入已有逐条审计记录（第 442-457 行，每个成功导入的用户都记录一条）。我们需要在函数末尾添加**批量汇总审计**，与现有逐条审计并存。

在 `backend/app/routes/users.py` 的 `import_users` 函数末尾（第 489 行 `return json(...)` 之前）添加汇总审计：

首先添加导入（在文件顶部）：

```python
from ..utils.audit_helpers import create_audit_entry, build_batch_audit_summary
```

然后在第 488 行（`return json` 之前）添加：

```python
        # 记录批量导入汇总审计日志（与逐条审计并存）
        summary = build_batch_audit_summary(
            operation="user_import",
            total_count=imported_count + failed_count,
            success_count=imported_count,
            failed_count=failed_count,
            details=errors[:10],  # 只记录前 10 个错误，避免元数据过大
        )

        await create_audit_entry(
            db_session=db_session,
            user_id=current_user.get("user_id") if current_user else None,
            action="batch_create",
            module="users",
            operation_type="batch",
            metadata=summary,
            ip_address=request.headers.get(
                "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
            ),
        )

        return json(
```

- [ ] **Step 3: 运行测试验证**

```bash
cd backend && python -m pytest tests/integration/test_customers_api.py tests/integration/test_users_api.py -v -k import
```

Expected: 导入相关测试通过

- [ ] **Step 4: 提交**

```bash
git add backend/app/routes/customers.py backend/app/routes/users.py
git commit -m "feat(audit): add batch audit logging for customer and user import"
```

---

### Task 5: 嵌套关系审计 - 标签/成员/角色

**Files:**
- Modify: `backend/app/routes/tags.py` (customer_tags 和 profile_tags blueprint)
- Modify: `backend/app/routes/groups.py` (群组成员操作)
- Modify: `backend/app/routes/users.py` (角色分配)
- Test: 对应测试文件

- [ ] **Step 1: 客户标签审计**

在 `backend/app/routes/tags.py` 中，找到 customer_tags blueprint 的端点。

首先添加导入：

```python
from ..utils.audit_helpers import create_audit_entry
```

**添加标签端点**（POST `/api/v1/customers/<customer_id>/tags/<tag_id>`）：

在端点函数末尾添加：

```python
# 记录审计日志
await create_audit_entry(
    db_session=db_session,
    user_id=current_user.get("user_id") if current_user else None,
    action="add_tag",
    module="customer-tags",
    record_id=customer_id,
    record_type="customer-tag",
    changes={"tag_id": tag_id, "customer_id": customer_id},
    operation_type="relation",
    metadata={"tag_id": tag_id},
    ip_address=request.headers.get(
        "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
    ),
)
```

**移除标签端点**（DELETE `/api/v1/customers/<customer_id>/tags/<tag_id>`）：

在端点函数末尾添加：

```python
# 记录审计日志
await create_audit_entry(
    db_session=db_session,
    user_id=current_user.get("user_id") if current_user else None,
    action="remove_tag",
    module="customer-tags",
    record_id=customer_id,
    record_type="customer-tag",
    changes={"tag_id": tag_id, "customer_id": customer_id},
    operation_type="relation",
    metadata={"tag_id": tag_id},
    ip_address=request.headers.get(
        "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
    ),
)
```

- [ ] **Step 2: 画像标签审计**

在 profile_tags blueprint 中添加类似的审计记录，module 改为 `profile-tags`。

- [ ] **Step 3: 群组成员审计**

在 `backend/app/routes/groups.py` 中添加导入：

```python
from ..utils.audit_helpers import create_audit_entry
```

**添加成员端点**（POST `/api/v1/customer-groups/<group_id>/members`）：

```python
# 记录审计日志
await create_audit_entry(
    db_session=db_session,
    user_id=current_user.get("user_id") if current_user else None,
    action="add_member",
    module="customer-groups",
    record_id=group_id,
    record_type="group-member",
    changes={"customer_id": customer_id},
    operation_type="relation",
    metadata={"group_id": group_id, "customer_id": customer_id},
    ip_address=request.headers.get(
        "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
    ),
)
```

**移除成员端点**（DELETE `/api/v1/customer-groups/<group_id>/members/<customer_id>`）：

```python
# 记录审计日志
await create_audit_entry(
    db_session=db_session,
    user_id=current_user.get("user_id") if current_user else None,
    action="remove_member",
    module="customer-groups",
    record_id=group_id,
    record_type="group-member",
    changes={"customer_id": customer_id},
    operation_type="relation",
    metadata={"group_id": group_id, "customer_id": customer_id},
    ip_address=request.headers.get(
        "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
    ),
)
```

- [ ] **Step 4: 用户角色分配审计**

在 `backend/app/routes/users.py` 中，找到分配角色的端点（POST `/api/v1/users/<user_id>/roles`）。

添加导入（如果还没有）：

```python
from ..utils.audit_helpers import create_audit_entry
```

在端点函数末尾添加：

```python
# 记录审计日志
await create_audit_entry(
    db_session=db_session,
    user_id=current_user.get("user_id") if current_user else None,
    action="assign_role",
    module="users",
    record_id=user_id,
    record_type="user-role",
    changes={"role_id": role_id},
    operation_type="relation",
    metadata={"role_id": role_id},
    ip_address=request.headers.get(
        "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
    ),
)
```

- [ ] **Step 5: 运行测试验证**

```bash
cd backend && python -m pytest tests/integration/test_groups_api.py tests/integration/test_roles_api.py -v
```

Expected: 所有测试通过

- [ ] **Step 6: 提交**

```bash
git add backend/app/routes/tags.py backend/app/routes/groups.py backend/app/routes/users.py
git commit -m "feat(audit): add relation audit for tags, group members, and role assignment"
```

---

### Task 6: 敏感操作审计 - 密码重置

**Files:**
- Modify: `backend/app/routes/users.py` (reset_password 端点)
- Test: `backend/tests/integration/test_users_api.py` (补充密码重置审计测试)

- [ ] **Step 1: 密码重置审计**

在 `backend/app/routes/users.py` 中，找到密码重置端点（POST `/api/v1/users/<user_id>/reset-password`）。

添加导入（如果还没有）：

```python
from ..utils.audit_helpers import create_audit_entry, mask_sensitive_data
```

在端点函数末尾添加：

```python
# 记录敏感操作审计日志
await create_audit_entry(
    db_session=db_session,
    user_id=current_user.get("user_id") if current_user else None,
    action="reset_password",
    module="users",
    record_id=user_id,
    record_type="user",
    operation_type="sensitive",
    ip_address=request.headers.get(
        "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
    ),
)
```

**注意**：不要在 changes 中记录密码相关数据，即使是脱敏的。

- [ ] **Step 2: 运行测试验证**

```bash
cd backend && python -m pytest tests/integration/test_users_api.py -v -k reset
```

Expected: 密码重置测试通过

- [ ] **Step 3: 提交**

```bash
git add backend/app/routes/users.py
git commit -m "feat(audit): add sensitive audit logging for password reset"
```

---

### Task 7: 充值操作审计

**Files:**
- Modify: `backend/app/routes/billing.py` (recharge 端点)
- Test: `backend/tests/integration/test_billing_api.py` (补充充值审计测试)

- [ ] **Step 1: 充值审计**

在 `backend/app/routes/billing.py` 中，找到充值端点（POST `/api/v1/billing/recharge`）。

添加导入：

```python
from ..utils.audit_helpers import create_audit_entry
```

在端点函数末尾（return json 之前）添加：

```python
# 记录充值审计日志
await create_audit_entry(
    db_session=db,
    user_id=user.get("user_id") if user else None,
    action="recharge",
    module="billing",
    record_id=record.id,
    record_type="recharge",
    changes={
        "customer_id": customer_id,
        "real_amount": float(real_amount),
        "bonus_amount": float(bonus_amount),
    },
    operation_type="standard",
    ip_address=request.headers.get(
        "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
    ),
)
```

- [ ] **Step 2: 运行测试验证**

```bash
cd backend && python -m pytest tests/integration/test_billing_api.py -v -k recharge
```

Expected: 充值测试通过

- [ ] **Step 3: 提交**

```bash
git add backend/app/routes/billing.py
git commit -m "feat(audit): add audit logging for recharge operation"
```

---

### Task 8: 批量标签操作审计

**Files:**
- Modify: `backend/app/routes/tags.py` (batch_add_tags, batch_remove_tags 端点)
- Test: `backend/tests/integration/test_tags_api.py`

- [ ] **Step 1: 批量添加标签审计**

在 `backend/app/routes/tags.py` 中，找到批量添加标签端点（POST `/api/v1/customers/tags/batch-add`）。

添加导入（如果还没有）：

```python
from ..utils.audit_helpers import create_audit_entry, build_batch_audit_summary
```

在端点函数末尾添加：

```python
# 记录批量操作审计日志
summary = build_batch_audit_summary(
    operation="batch_add_tags",
    total_count=len(customer_ids),
    success_count=success_count,
    failed_count=failed_count,
)

await create_audit_entry(
    db_session=db_session,
    user_id=current_user.get("user_id") if current_user else None,
    action="batch_add_tags",
    module="customer-tags",
    operation_type="batch",
    metadata=summary,
    ip_address=request.headers.get(
        "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
    ),
)
```

- [ ] **Step 2: 批量移除标签审计**

在批量移除标签端点（POST `/api/v1/customers/tags/batch-remove`）中添加类似的审计记录。

- [ ] **Step 3: 运行测试验证**

```bash
cd backend && python -m pytest tests/integration/test_tags_api.py -v -k batch
```

Expected: 批量标签测试通过

- [ ] **Step 4: 提交**

```bash
git add backend/app/routes/tags.py
git commit -m "feat(audit): add batch audit logging for tag operations"
```

---

### Task 9: 运行完整测试套件并验证

**Files:**
- 所有测试文件

- [ ] **Step 1: 运行所有审计相关测试**

```bash
cd backend && python -m pytest tests/unit/test_audit_helpers.py tests/integration/test_audit_middleware.py tests/integration/test_audit_logs_api.py -v
```

Expected: 所有审计相关测试通过

- [ ] **Step 2: 运行完整测试套件**

```bash
cd backend && make test-parallel
```

Expected: 测试覆盖率 ≥ 50%，所有测试通过

- [ ] **Step 3: 代码检查**

```bash
cd backend && black app/ tests/ && flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203
```

Expected: 无代码风格问题

- [ ] **Step 4: 提交**

```bash
git add .
git commit -m "test(audit): verify all audit log tests pass and coverage meets requirements"
```

---

## 实施顺序总结

1. ✅ Task 1: 数据库迁移
2. ✅ Task 2: 辅助函数库
3. ✅ Task 3: 中间件增强
4. ✅ Task 4: 批量操作审计（导入）
5. ✅ Task 5: 嵌套关系审计（标签/成员/角色）
6. ✅ Task 6: 敏感操作审计（密码重置）
7. ✅ Task 7: 充值操作审计
8. ✅ Task 8: 批量标签操作审计
9. ✅ Task 9: 完整测试验证

## 成功标准

- [ ] 所有 5 类遗漏操作均有审计记录
- [ ] 测试覆盖率 ≥ 50%
- [ ] 现有审计功能不受影响
- [ ] Webhook 回调不再产生无意义审计记录
- [ ] 敏感操作可被 `operation_type="sensitive"` 标识
