# 删除 customers.business_type 改用 profile.industry 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除 `customers.business_type` 列，客户列表和 API 通过 LEFT JOIN `customer_profiles.industry` 获取行业类型，API 返回字段名保持 `business_type` 以兼容前端。

**Architecture:** 通过 Alembic 迁移确保所有客户都有 profile 记录后删除 customers.business_type 列；后端列表查询改为 JOIN customer_profiles；新建/编辑客户时行业类型写入 profile 而非 customer；API 响应字段名保持 business_type。

**Tech Stack:** Python 3.12 + Sanic + SQLAlchemy 2.0 + Alembic + pytest

---

## File Structure

| 文件 | 操作 | 职责 |
| ---- | ---- | ---- |
| `backend/alembic/versions/004_drop_business_type.py` | 创建 | 迁移脚本：确保 profile 存在、删除列和索引 |
| `backend/app/models/customers.py` | 修改 | 删除 `business_type` 列和 `idx_customer_business_settlement` 索引 |
| `backend/app/services/customers.py` | 修改 | 列表查询 JOIN profile、筛选用 profile.industry、create/batch 写 profile |
| `backend/app/routes/customers.py` | 修改 | 列表/详情响应 `business_type` 改为从 profile 取、导入模板列调整 |
| `backend/tests/unit/test_customer_service.py` | 修改 | 测试改用 CustomerProfile.industry |
| `backend/tests/unit/test_models.py` | 修改 | 测试改用 profile.industry |
| `backend/tests/integration/test_customers_api.py` | 修改 |  fixture 中 INSERT 改用 profile.industry |
| `backend/tests/integration/test_billing_api.py` | 修改 | fixture 中 INSERT 改用 profile.industry |
| `backend/tests/unit/test_customer_service_batch.py` | 修改 | 测试数据改用 profile.industry |

---

### Task 1: Alembic 迁移脚本

**Files:**
- Create: `backend/alembic/versions/004_drop_business_type.py`

- [ ] **Step 1: 创建迁移脚本**

```python
"""drop customers.business_type, use customer_profiles.industry

Revision ID: 004
Revises: 003
Create Date: 2026-04-15
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: 确保所有客户都有 customer_profiles 记录
    # 为没有 profile 的客户创建空 profile
    op.execute(
        """
        INSERT INTO customer_profiles (customer_id, created_at, updated_at)
        SELECT c.id, NOW(), NOW()
        FROM customers c
        LEFT JOIN customer_profiles cp ON c.id = cp.customer_id
        WHERE cp.id IS NULL AND c.deleted_at IS NULL
        """
    )

    # Step 2: 删除 idx_customer_business_settlement 索引
    op.drop_index("idx_customer_business_settlement", table_name="customers")

    # Step 3: 删除 customers.business_type 列
    op.drop_column("customers", "business_type")


def downgrade() -> None:
    # Step 1: 重新添加 business_type 列
    op.add_column(
        "customers",
        sa.Column("business_type", sa.String(length=50), nullable=True),
    )

    # Step 2: 重新创建索引
    op.create_index(
        "idx_customer_business_settlement",
        "customers",
        ["business_type", "settlement_type"],
        unique=False,
    )
```

- [ ] **Step 2: 验证迁移脚本语法**

运行: `cd backend && python -m py_compile alembic/versions/004_drop_business_type.py`
期望: 无输出（编译成功）

- [ ] **Step 3: 提交**

```bash
git add backend/alembic/versions/004_drop_business_type.py
git commit -m "feat: add migration to drop customers.business_type and use profile.industry"
```

---

### Task 2: 更新 Customer 模型

**Files:**
- Modify: `backend/app/models/customers.py`

- [ ] **Step 1: 删除 business_type 列定义和索引**

修改 `backend/app/models/customers.py`，删除第 26 行的 `business_type` 列：

```python
# 删除这一行：
business_type = Column(String(50), index=True)
```

同时删除 `__table_args__` 中的 `idx_customer_business_settlement` 索引：

```python
__table_args__ = (
    Index("idx_customer_manager_level", "manager_id", "customer_level"),
    # 删除这一行: Index("idx_customer_business_settlement", "business_type", "settlement_type"),
    Index("idx_customer_sales_manager", "sales_manager_id"),
    Index("idx_customer_cooperation_status", "cooperation_status"),
    Index("idx_customer_disabled", "is_disabled"),
)
```

修改后 `__table_args__` 应为：

```python
__table_args__ = (
    Index("idx_customer_manager_level", "manager_id", "customer_level"),
    Index("idx_customer_sales_manager", "sales_manager_id"),
    Index("idx_customer_cooperation_status", "cooperation_status"),
    Index("idx_customer_disabled", "is_disabled"),
)
```

- [ ] **Step 2: 验证模型导入**

运行: `cd backend && python -c "from app.models.customers import Customer; print([c.key for c in Customer.__table__.columns])"`
期望: 输出中不含 `business_type`

- [ ] **Step 3: 提交**

```bash
git add backend/app/models/customers.py
git commit -m "refactor: remove business_type column from Customer model"
```

---

### Task 3: 更新 CustomerService 列表查询

**Files:**
- Modify: `backend/app/services/customers.py`

- [ ] **Step 1: 修改 get_all_customers 方法，添加 LEFT JOIN**

将 `get_all_customers` 方法中的基础查询从：

```python
stmt = select(Customer).where(Customer.deleted_at.is_(None))
```

改为：

```python
stmt = (
    select(Customer, CustomerProfile.industry.label("industry"))
    .outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
    .where(Customer.deleted_at.is_(None))
)
```

- [ ] **Step 2: 修改 business_type 筛选条件**

将：

```python
# 业务类型筛选
if business_type := filters.get("business_type"):
    conditions.append(Customer.business_type == business_type)
```

改为：

```python
# 业务类型筛选（使用 profile.industry）
if business_type := filters.get("business_type"):
    conditions.append(CustomerProfile.industry == business_type)
```

- [ ] **Step 3: 修改返回类型注解**

将方法签名从：

```python
async def get_all_customers(
    self,
    page: int = 1,
    page_size: int = 20,
    filters: Optional[dict] = None,
) -> Tuple[List[Customer], int]:
```

改为：

```python
async def get_all_customers(
    self,
    page: int = 1,
    page_size: int = 20,
    filters: Optional[dict] = None,
) -> Tuple[List[Tuple[Customer, Optional[str]]], int]:
```

- [ ] **Step 4: 修改返回结果处理**

由于查询现在返回 `(Customer, industry)` 元组而非 `Customer`，但 route 层已经通过 `selectinload` 加载了 profile，所以这里保持 `selectinload` 不变。实际上，我们需要调整策略：使用 `selectinload` 已经加载了 profile，route 层可以直接从 `customer.profile.industry` 获取。

修正方案：不改变 `get_all_customers` 的返回结构，继续使用 `selectinload(Customer.profile)`，筛选条件改用 `CustomerProfile.industry`。

最终 `get_all_customers` 方法完整代码：

```python
async def get_all_customers(
    self,
    page: int = 1,
    page_size: int = 20,
    filters: Optional[dict] = None,
) -> Tuple[List[Customer], int]:
    """
    获取客户列表（支持筛选和分页）

    Args:
        page: 页码
        page_size: 每页数量
        filters: 筛选条件字典
            - keyword: 公司名称/公司 ID 关键词
            - account_type: 账号类型
            - business_type: 业务类型（筛选 customer_profiles.industry）
            - customer_level: 客户等级
            - manager_id: 运营经理 ID
            - settlement_type: 结算方式
            - is_key_customer: 是否重点客户

    Returns:
        (customers, total)
    """
    filters = filters or {}

    # 构建基础查询
    stmt = select(Customer).where(Customer.deleted_at.is_(None))

    # 应用筛选条件
    conditions = []

    # 关键词筛选（公司名称或公司 ID）
    if keyword := filters.get("keyword"):
        conditions.append(
            or_(
                Customer.name.ilike(f"%{keyword}%"),
                Customer.company_id.ilike(f"%{keyword}%"),
            )
        )

    # 账号类型筛选
    if account_type := filters.get("account_type"):
        conditions.append(Customer.account_type == account_type)

    # 业务类型筛选（使用 profile.industry）
    if business_type := filters.get("business_type"):
        stmt = stmt.outerjoin(CustomerProfile, Customer.id == CustomerProfile.customer_id)
        conditions.append(CustomerProfile.industry == business_type)

    # 客户等级筛选
    if customer_level := filters.get("customer_level"):
        conditions.append(Customer.customer_level == customer_level)

    # 运营经理筛选
    if manager_id := filters.get("manager_id"):
        conditions.append(Customer.manager_id == manager_id)

    # 结算方式筛选
    if settlement_type := filters.get("settlement_type"):
        conditions.append(Customer.settlement_type == settlement_type)

    # 重点客户筛选
    if (is_key_customer := filters.get("is_key_customer")) is not None:
        conditions.append(Customer.is_key_customer == is_key_customer)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    # 获取总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    if self._is_async:
        total = (await self.db.execute(count_stmt)).scalar()
    else:
        total = self.db.execute(count_stmt).scalar()

    # 分页排序
    stmt = stmt.order_by(Customer.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    # 加载关联数据
    stmt = stmt.options(selectinload(Customer.profile), selectinload(Customer.balance))

    if self._is_async:
        result = await self.db.execute(stmt)
    else:
        result = self.db.execute(stmt)
    customers = result.scalars().all()

    return list(customers), total
```

关键变更：
- business_type 筛选时先 outerjoin CustomerProfile，然后用 `CustomerProfile.industry` 筛选
- 其他逻辑不变，返回结构不变（仍返回 `List[Customer]`）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/customers.py
git commit -m "refactor: use profile.industry for business_type filtering in list query"
```

---

### Task 4: 更新 CustomerService 创建/批量创建方法

**Files:**
- Modify: `backend/app/services/customers.py`

- [ ] **Step 1: 修改 create_customer 方法**

将 `create_customer` 方法改为不再传递 `business_type`，同时如果数据中包含 `industry` 字段，则创建对应的 profile：

```python
async def create_customer(self, data: dict) -> Customer:
    """创建客户"""
    customer = Customer(
        company_id=data["company_id"],
        name=data["name"],
        account_type=data.get("account_type"),
        customer_level=data.get("customer_level"),
        price_policy=data.get("price_policy"),
        manager_id=data.get("manager_id"),
        settlement_cycle=data.get("settlement_cycle"),
        settlement_type=data.get("settlement_type"),
        is_key_customer=data.get("is_key_customer", False),
        email=data.get("email"),
    )

    self.db.add(customer)
    await self.db.flush()

    # 创建初始余额记录
    balance = CustomerBalance(customer_id=customer.id)
    self.db.add(balance)

    # 如果提供了 industry，创建 profile 记录
    if data.get("industry"):
        profile = CustomerProfile(
            customer_id=customer.id,
            industry=data["industry"],
        )
        self.db.add(profile)

    await self.db.commit()
    await self.db.refresh(customer)

    return customer
```

- [ ] **Step 2: 修改 update_customer 方法**

从 `updatable_fields` 列表中删除 `"business_type"`：

```python
updatable_fields = [
    "company_id",
    "name",
    "account_type",
    # 删除 "business_type",
    "customer_level",
    "price_policy",
    "manager_id",
    "settlement_cycle",
    "settlement_type",
    "is_key_customer",
    "email",
    # 新增字段
    "erp_system",
    "first_payment_date",
    "onboarding_date",
    "sales_manager_id",
    "cooperation_status",
    "is_settlement_enabled",
    "is_disabled",
    "notes",
]
```

同时，如果请求中包含 `industry` 字段，需要同步更新 profile：

在 `update_customer` 方法末尾（`await self.db.refresh(customer)` 之前）添加：

```python
# 如果提供了 industry，更新 profile
if "industry" in data:
    profile = await self.get_customer_profile(customer.id)
    if profile:
        profile.industry = data["industry"]
    else:
        profile = CustomerProfile(customer_id=customer.id, industry=data["industry"])
        self.db.add(profile)
```

- [ ] **Step 3: 修改 batch_create_customers 方法**

删除 `Customer()` 构造中的 `business_type` 参数：

```python
customer = Customer(
    company_id=company_id,
    name=name,
    account_type=data.get("account_type"),
    # 删除 business_type=data.get("business_type"),
    customer_level=data.get("customer_level"),
    price_policy=data.get("price_policy"),
    manager_id=data.get("manager_id"),
    settlement_cycle=data.get("settlement_cycle"),
    settlement_type=data.get("settlement_type"),
    is_key_customer=data.get("is_key_customer", False),
    email=data.get("email"),
)
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/customers.py
git commit -m "refactor: move industry handling from Customer to CustomerProfile in create/update/batch"
```

---

### Task 5: 更新路由层响应

**Files:**
- Modify: `backend/app/routes/customers.py`

- [ ] **Step 1: 修改 list_customers 响应**

将列表响应中的 `business_type` 从 `c.business_type` 改为从 profile 获取：

```python
"business_type": c.profile.industry if c.profile else None,
```

完整 list 响应代码段：

```python
result = {
    "code": 0,
    "message": "success",
    "data": {
        "list": [
            {
                "id": c.id,
                "company_id": c.company_id,
                "name": c.name,
                "account_type": c.account_type,
                "business_type": c.profile.industry if c.profile else None,
                "customer_level": c.customer_level,
                "price_policy": c.price_policy,
                "manager_id": c.manager_id,
                "settlement_cycle": c.settlement_cycle,
                "settlement_type": c.settlement_type,
                "is_key_customer": c.is_key_customer,
                "email": c.email,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in customers
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    },
}
```

- [ ] **Step 2: 修改 get_customer 详情响应**

将详情响应中的 `business_type` 从 `customer.business_type` 改为从 profile 获取：

```python
"business_type": customer.profile.industry if customer.profile else None,
```

- [ ] **Step 3: 修改 export_customers 导出**

将导出中的 `business_type` 从 `c.business_type` 改为：

```python
"business_type": c.profile.industry if c.profile else None,
```

- [ ] **Step 4: 更新 create_customer 路由文档注释**

将路由 docstring 中的 `business_type` 改为 `industry`：

```python
"""
创建客户

Body:
{
    "company_id": "string (required)",
    "name": "string (required)",
    "account_type": "string (optional)",
    "industry": "string (optional)",  <-- 原 business_type
    ...
}
"""
```

- [ ] **Step 5: 更新 update_customer 路由文档注释**

同样将 `business_type` 改为 `industry`。

- [ ] **Step 6: 修改导入模板**

Excel 导入模板的 headers 中，将 `business_type` 改为 `industry`：

```python
headers = [
    "company_id",
    "name",
    "account_type",
    "industry",  # 原 business_type
    "customer_level",
    "price_policy",
    "settlement_cycle",
    "settlement_type",
    "is_key_customer",
    "email",
]
```

对应的中文说明行也调整：

```python
notes = [
    "必填",
    "必填",
    "可选",
    "可选",  # industry
    "可选",
    "可选：定价/阶梯/包年",
    "可选",
    "可选：prepaid/postpaid",
    "可选：true/false",
    "可选",
]
```

示例数据行也调整：

```python
example_data = [
    "COMP001",
    "示例公司 1",
    "正式账号",
    "项目",  # industry 示例值
    "KA",
    "定价",
    "月结",
    "prepaid",
    "false",
    "example@company.com",
]
```

- [ ] **Step 7: 更新导入路由文档注释**

将 `import_customers` 路由 docstring 中的 `business_type` 改为 `industry`。

- [ ] **Step 8: 更新导出路由文档注释**

将 `export_customers` 路由 docstring 中的 `business_type` 改为 `industry`。

- [ ] **Step 9: 提交**

```bash
git add backend/app/routes/customers.py
git commit -m "refactor: use profile.industry for business_type in API responses and templates"
```

---

### Task 6: 更新单元测试

**Files:**
- Modify: `backend/tests/unit/test_customer_service.py`
- Modify: `backend/tests/unit/test_models.py`

- [ ] **Step 1: 修改 test_customer_service.py**

将 `test_create_customer_success` 中的 `business_type` 改为 `industry`，并调整测试断言：

```python
# 准备测试数据
customer_data = {
    "company_id": "COMP001",
    "name": "测试公司",
    "account_type": "enterprise",
    "industry": "technology",  # 原 business_type
    "customer_level": "gold",
    ...
}
```

删除 Mock 中的 `business_type` 构造参数：

```python
created_customer = Customer(
    id=1,
    company_id=customer_data["company_id"],
    name=customer_data["name"],
    account_type=customer_data["account_type"],
    # 删除 business_type=...
    customer_level=customer_data["customer_level"],
    ...
)
```

- [ ] **Step 2: 修改 test_models.py**

找到引用 `business_type="retail"` 的测试，改为创建 profile 并设置 `industry`：

```python
# 原代码：
customer = Customer(..., business_type="retail", ...)

# 改为：
customer = Customer(...)  # 不含 business_type
customer.profile = CustomerProfile(industry="retail")
```

- [ ] **Step 3: 提交**

```bash
git add backend/tests/unit/test_customer_service.py backend/tests/unit/test_models.py
git commit -m "test: update unit tests to use profile.industry instead of customer.business_type"
```

---

### Task 7: 更新集成测试

**Files:**
- Modify: `backend/tests/integration/test_customers_api.py`
- Modify: `backend/tests/integration/test_billing_api.py`
- Modify: `backend/tests/unit/test_customer_service_batch.py`

- [ ] **Step 1: 修改 test_customers_api.py 的 customer_data fixture**

删除 fixture 中 SQL INSERT 的 `business_type` 列：

```python
# 原 SQL：
INSERT INTO customers (company_id, name, account_type, business_type,
    customer_level, settlement_type, is_key_customer, email, created_at)
VALUES (...)

# 改为（删除 business_type）：
INSERT INTO customers (company_id, name, account_type,
    customer_level, settlement_type, is_key_customer, email, created_at)
VALUES (:company_id, :name, :account_type, :customer_level,
    :settlement_type, :is_key_customer, :email, NOW())
```

同时删除 Python 字典中的 `business_type` 键：

```python
customers = [
    {
        "company_id": "TEST001",
        "name": "测试公司 1",
        "account_type": "正式账号",
        # 删除 "business_type": "A",
        "customer_level": "KA",
        ...
    },
    ...
]
```

在 fixture 清理后，创建 profile 记录（可选，因为迁移会确保 profile 存在）：

```python
# 为测试客户创建 profile
for cust in customers:
    cust_id = db_session.execute(
        text("SELECT id FROM customers WHERE company_id = :cid"),
        {"cid": cust["company_id"]},
    ).scalar_one()
    db_session.execute(
        text("INSERT INTO customer_profiles (customer_id, industry, created_at, updated_at) VALUES (:cid, :industry, NOW(), NOW())"),
        {"cid": cust_id, "industry": cust.get("industry")},
    )
db_session.commit()
```

- [ ] **Step 2: 修改 test_customers_api.py 中 list_customer 筛选测试**

找到使用 `business_type` 参数筛选的测试，确认参数名仍为 `business_type`（API 向后兼容），但实际筛选的是 `profile.industry`。无需修改测试参数，因为 service 层已处理转换。

- [ ] **Step 3: 修改 test_customers_api.py 中 import 测试**

将 Excel 导入测试中的 `business_type` 列改为 `industry`：

```python
ws.append(
    [
        "company_id",
        "name",
        "account_type",
        "industry",  # 原 business_type
        "customer_level",
        "settlement_type",
        "is_key_customer",
        "email",
    ]
)
```

- [ ] **Step 4: 修改 test_billing_api.py**

删除 fixture 中 SQL INSERT 的 `business_type`：

```python
# 原 SQL 删除 business_type 列
INSERT INTO customers (id, company_id, name, account_type,
    customer_level, ...)
VALUES (:id, :company_id, :name, :account_type, :customer_level, ...)
```

- [ ] **Step 5: 修改 test_customer_service_batch.py**

删除测试数据中的 `business_type` 键：

```python
# 原数据
{
    ...
    "business_type": "互联网",
    ...
}

# 改为
{
    ...
    # 删除 business_type
    ...
}
```

- [ ] **Step 6: 提交**

```bash
git add backend/tests/integration/test_customers_api.py backend/tests/integration/test_billing_api.py backend/tests/unit/test_customer_service_batch.py
git commit -m "test: update integration tests to remove business_type references"
```

---

### Task 8: 运行测试验证

**Files:** 无

- [ ] **Step 1: 运行后端测试**

运行: `cd backend && python -m pytest tests/ -v --tb=short`
期望: 所有测试通过

- [ ] **Step 2: 运行代码质量检查**

运行: `cd backend && black app/ tests/ && flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203`
期望: 无错误

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "chore: run black + flake8 after business_type removal"
```

---

### Task 9: 更新设计文档状态

**Files:**
- Modify: `docs/superpowers/specs/2026-04-15-delete-business-type-use-profile-industry-design.md`

- [ ] **Step 1: 更新文档状态**

将文档开头的 `**状态**: 待批准` 改为 `**状态**: 已完成`。

- [ ] **Step 2: 最终提交**

```bash
git add docs/superpowers/specs/2026-04-15-delete-business-type-use-profile-industry-design.md
git commit -m "docs: mark business_type removal design as completed"
```
