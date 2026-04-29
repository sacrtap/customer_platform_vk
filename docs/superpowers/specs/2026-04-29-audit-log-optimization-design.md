# 审计日志全面优化设计文档

**日期**: 2026-04-29  
**状态**: 待审查  
**作者**: AI Assistant  

---

## 1. 背景与目标

### 1.1 当前状态

项目使用 `audit_middleware` 中间件自动记录 POST/PUT/DELETE 请求到 `audit_logs` 表，部分路由（files.py、users.py 导入）手动记录。

### 1.2 已覆盖模块

| 模块 | 覆盖方式 | 说明 |
|------|----------|------|
| 用户管理 (`/api/v1/users`) | 中间件 + 手动 | 导入用户有手动审计 |
| 角色管理 (`/api/v1/roles`) | 中间件 | 模型映射已配置 |
| 权限管理 (`/api/v1/permissions`) | 中间件 | 模型映射已配置 |
| 客户管理 (`/api/v1/customers`) | 中间件 | 含 profile 子路径 |
| 标签管理 (`/api/v1/tags`, `/customer-tags`, `/profile-tags`) | 中间件 | 模型映射已配置 |
| 客户群组 (`/api/v1/customer-groups`) | 中间件 | 模型映射已配置 |
| 文件管理 (`/api/v1/files`) | 手动记录 | 中间件已跳过 |
| 定价规则 (`/api/v1/billing/pricing-rules`) | 中间件 | 模型映射已配置 |
| 发票管理 (`/api/v1/billing/invoices`) | 中间件 | 模型映射已配置 |
| 充值记录 (`/api/v1/billing/recharge`) | 中间件 | 模型映射已配置 |
| 余额管理 (`/api/v1/billing/balances`) | 中间件 | 模型映射已配置 |
| 行业字典 (`/api/v1/dict/industry-types`) | 中间件 | 模型映射已配置 |

### 1.3 未覆盖的问题

| 类别 | 具体功能 | 根本原因 |
|------|----------|----------|
| **批量操作** | 客户导入、用户导入、批量添加/移除标签 | 无单一 record_id，中间件无法提取 |
| **嵌套关系操作** | 客户标签、画像标签、群组成员、用户角色分配 | 路径复杂，module/record_id 提取不准确 |
| **模块映射缺失** | `/api/v1/profiles/*` | `_MODULE_MODEL_MAP` 中无 `profiles` 模块 |
| **外部回调** | Webhook 回调 | 无认证用户，审计日志无意义 |
| **敏感操作** | 密码重置 | 中间件无法区分普通更新与安全操作 |

### 1.4 优化目标

1. 批量操作记录操作概要（总数、成功数、失败数）
2. 嵌套关系操作记录关系 ID 和双方实体信息
3. 补全缺失的模块映射
4. Webhook 回调跳过审计
5. 敏感操作添加特殊标记

---

## 2. 架构设计

### 2.1 核心原则

**混合模式**：中间件负责标准 CRUD，路由负责复杂操作，统一通过辅助函数记录。

```
┌─────────────────────────────────────────────────────────┐
│                    审计日志系统                           │
├─────────────────────┬───────────────────────────────────┤
│   中间件层 (自动)    │      路由层 (手动)                  │
│                     │                                   │
│ • 标准 CRUD 操作     │ • 批量操作 (导入/批量标签)          │
│ • 简单资源修改       │ • 嵌套关系 (标签/成员/角色)         │
│ • 路径可映射的操作   │ • 敏感操作 (密码重置)               │
│                     │ • 特殊业务逻辑 (充值/结算状态)       │
├─────────────────────┴───────────────────────────────────┤
│              统一辅助函数层                               │
│                                                         │
│ • create_audit_entry() - 创建审计记录                    │
│ • build_batch_audit_data() - 构建批量操作数据            │
│ • mask_sensitive_fields() - 敏感字段脱敏                 │
├─────────────────────────────────────────────────────────┤
│              审计日志模型 (AuditLog)                      │
│                                                         │
│ • user_id, action, module, record_id, record_type       │
│ • changes (JSON), ip_address, created_at                │
│ • [新增] operation_type - 操作类型标识                   │
│ • [新增] metadata - 扩展元数据                           │
└─────────────────────────────────────────────────────────┘
```

### 2.2 操作类型定义

| operation_type | 说明 | 示例 |
|----------------|------|------|
| `standard` | 标准 CRUD 操作 | 创建客户、更新角色 |
| `batch` | 批量操作 | Excel 导入、批量添加标签 |
| `relation` | 关系型操作 | 添加客户标签、分配角色 |
| `sensitive` | 敏感安全操作 | 密码重置、权限变更 |

---

## 3. 详细设计

### 3.1 数据库模型扩展

**文件**: `backend/app/models/billing.py`

```python
class AuditLog(BaseModel):
    """审计日志表"""
    
    __tablename__ = "audit_logs"
    
    # 现有字段保持不变
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
        comment="操作类型: standard/batch/relation/sensitive"
    )
    metadata = Column(
        JSON, 
        nullable=True,
        comment="扩展元数据: 批量统计、关系ID列表等"
    )
```

### 3.2 中间件增强

**文件**: `backend/app/middleware/audit.py`

#### 3.2.1 模块映射补全

```python
_MODULE_MODEL_MAP = {
    # ... 现有映射保持不变 ...
    
    # 新增映射
    "profiles": CustomerProfile,  # 画像管理模块
    "webhooks": None,  # Webhook 模块（跳过审计）
}
```

#### 3.2.2 Webhook 路径跳过

```python
skip_paths = [
    "/health",
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/refresh",
    "/api/v1/auth/me",
    # 新增：Webhook 外部回调
    "/api/v1/webhooks/invoice-confirmation",
    "/api/v1/webhooks/payment-notify",
]
```

#### 3.2.3 敏感操作检测

```python
def is_sensitive_operation(path: str) -> bool:
    """检测是否为敏感操作（密码重置、权限变更等）"""
    sensitive_patterns = [
        "/reset-password",
        "/forgot-password",
        "/permissions",  # 权限分配
    ]
    return any(pattern in path for pattern in sensitive_patterns)
```

#### 3.2.4 嵌套路径解析增强

```python
def extract_record_id_from_path(path: str) -> int | None:
    """增强版：支持嵌套路径提取"""
    parts = path.strip("/").split("/")
    
    # 标准路径: /api/v1/users/123
    if len(parts) >= 4:
        try:
            return int(parts[3])
        except ValueError:
            pass
    
    # 嵌套路径: /api/v1/customers/123/tags/456
    if len(parts) >= 6:
        try:
            return int(parts[5])  # 返回关系 ID
        except ValueError:
            pass
    
    # 动作路径: /api/v1/billing/invoices/123/submit
    if len(parts) >= 5:
        try:
            return int(parts[4])
        except ValueError:
            pass
    
    return None
```

### 3.3 辅助函数库

**新建文件**: `backend/app/utils/audit_helpers.py`

```python
"""审计日志辅助函数"""

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
    """统一审计记录创建函数"""
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
    """构建批量操作审计摘要"""
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
    """敏感数据脱敏"""
    if fields is None:
        fields = ["password", "password_hash", "token", "secret"]
    
    masked = data.copy()
    for field in fields:
        if field in masked:
            masked[field] = "***MASKED***"
    return masked
```

### 3.4 路由手动记录点

#### 3.4.1 客户导入 (`customers.py`)

```python
# 在 import_customers 端点中
summary = build_batch_audit_summary(
    operation="customer_import",
    total_count=len(rows),
    success_count=success_count,
    failed_count=failed_count,
    details=error_details,
)

await create_audit_entry(
    db_session=db_session,
    user_id=user_id,
    action="batch_create",
    module="customers",
    operation_type="batch",
    metadata=summary,
    ip_address=ip_address,
)
```

#### 3.4.2 用户导入 (`users.py`)

类似客户导入，记录批量操作摘要。

#### 3.4.3 客户标签 (`tags.py` - customer_tags blueprint)

```python
# 添加客户标签
await create_audit_entry(
    db_session=db_session,
    user_id=user_id,
    action="add_tag",
    module="customer-tags",
    record_id=customer_id,
    record_type="customer-tag",
    changes={"tag_id": tag_id, "customer_id": customer_id},
    operation_type="relation",
    metadata={"tag_name": tag.name, "customer_name": customer.name},
    ip_address=ip_address,
)
```

#### 3.4.4 画像标签 (`tags.py` - profile_tags blueprint)

类似客户标签，module 改为 `profile-tags`。

#### 3.4.5 群组成员 (`groups.py`)

```python
# 添加成员
await create_audit_entry(
    db_session=db_session,
    user_id=user_id,
    action="add_member",
    module="customer-groups",
    record_id=group_id,
    record_type="group-member",
    changes={"customer_id": customer_id},
    operation_type="relation",
    metadata={"group_name": group.name, "customer_name": customer.name},
    ip_address=ip_address,
)
```

#### 3.4.6 用户角色分配 (`users.py`)

```python
# 分配角色
await create_audit_entry(
    db_session=db_session,
    user_id=user_id,
    action="assign_role",
    module="users",
    record_id=user_id,
    record_type="user-role",
    changes={"role_id": role_id},
    operation_type="relation",
    metadata={"role_name": role.name},
    ip_address=ip_address,
)
```

#### 3.4.7 密码重置 (`users.py`)

```python
# 重置密码
await create_audit_entry(
    db_session=db_session,
    user_id=user_id,
    action="reset_password",
    module="users",
    record_id=target_user_id,
    record_type="user",
    operation_type="sensitive",
    ip_address=ip_address,
)
```

#### 3.4.8 充值操作 (`billing.py`)

```python
# 充值
await create_audit_entry(
    db_session=db_session,
    user_id=user_id,
    action="recharge",
    module="billing",
    record_id=recharge_record.id,
    record_type="recharge",
    changes={"amount": amount, "balance_id": balance_id},
    operation_type="standard",
    ip_address=ip_address,
)
```

---

## 4. 数据库迁移

**文件**: `backend/alembic/versions/YYYYMMDD_add_audit_log_fields.py`

```python
def upgrade():
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

def downgrade():
    op.drop_column('audit_logs', 'metadata')
    op.drop_column('audit_logs', 'operation_type')
```

---

## 5. 测试策略

### 5.1 单元测试

**文件**: `backend/tests/unit/test_audit_helpers.py`

- `test_create_audit_entry()` - 验证审计记录创建
- `test_build_batch_audit_summary()` - 验证批量摘要构建
- `test_mask_sensitive_data()` - 验证敏感数据脱敏

### 5.2 集成测试

**文件**: `backend/tests/integration/test_audit_middleware.py`

- `test_standard_crud_audit()` - 标准 CRUD 审计
- `test_sensitive_operation_detection()` - 敏感操作检测
- `test_webhook_skip_audit()` - Webhook 跳过审计
- `test_module_mapping_profiles()` - profiles 模块映射

### 5.3 路由集成测试

在现有测试文件中补充：

- `test_customer_import_audit()` - 客户导入审计
- `test_customer_tag_audit()` - 客户标签审计
- `test_profile_tag_audit()` - 画像标签审计
- `test_group_member_audit()` - 群组成员审计
- `test_user_role_assignment_audit()` - 用户角色分配审计
- `test_password_reset_audit()` - 密码重置审计
- `test_recharge_audit()` - 充值操作审计

---

## 6. 实施顺序

1. **数据库迁移** - 添加 `operation_type` 和 `metadata` 字段
2. **辅助函数库** - 实现 `audit_helpers.py`
3. **中间件增强** - 模块映射、Webhook 过滤、路径解析、敏感检测
4. **路由手动记录** - 逐个添加 8 个手动记录点
5. **测试编写** - 单元测试 + 集成测试 + 路由测试
6. **验证与修复** - 运行测试，修复问题

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 数据库迁移失败 | 审计日志无法写入 | 迁移脚本可回滚，先备份数据 |
| 中间件逻辑错误 | 审计记录不准确 | 充分测试，灰度发布 |
| 手动记录遗漏 | 部分操作无审计 | 代码审查检查 |
| 性能影响 | 审计写入延迟 | 异步写入，批量操作合并 |

---

## 8. 成功标准

- [ ] 所有 5 类遗漏操作均有审计记录
- [ ] 测试覆盖率 ≥ 50%
- [ ] 现有审计功能不受影响
- [ ] Webhook 回调不再产生无意义审计记录
- [ ] 敏感操作可被 `operation_type="sensitive"` 标识
