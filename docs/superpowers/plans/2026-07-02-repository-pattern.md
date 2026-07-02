# Repository 模式实施计划

**创建日期**: 2026-07-02  
**关联设计文档**: `docs/superpowers/specs/2026-07-02-repository-pattern-design.md`  
**技术债务**: TD-005  
**预计工作量**: 5-7 天

---

## 目标

引入 Repository 模式，封装数据访问逻辑，提高代码复用性和可测试性，为后续代码拆分（TD-001）奠定基础。

---

## 文件结构

### 新增文件
```
backend/app/repository/
├── __init__.py              # 导出所有 Repository 和 Protocol
├── protocols.py             # 所有 Protocol 定义
├── base.py                  # 基础 Repository 类
├── customer_repo.py         # CustomerRepository
├── invoice_repo.py          # InvoiceRepository
├── balance_repo.py          # BalanceRepository
└── pricing_repo.py          # PricingRepository

backend/tests/test_repository/
├── __init__.py
├── test_customer_repo.py
├── test_invoice_repo.py
├── test_balance_repo.py
└── test_pricing_repo.py
```

### 修改文件
```
backend/app/services/customers.py      # 使用 CustomerRepository
backend/app/services/billing.py        # 使用 InvoiceRepository, BalanceRepository, PricingRepository
backend/app/services/analytics.py      # 使用 Repository
backend/app/routes/customers.py        # 注入 Repository
backend/app/routes/billing.py          # 注入 Repository
```

---

## 任务分解

### 阶段 1: 基础设施搭建（0.5 天）

#### 任务 1.1: 创建目录结构
**目标**: 创建 repository 目录和基础文件

**步骤**:
1. 创建 `backend/app/repository/` 目录
2. 创建 `backend/app/repository/__init__.py`（空文件）
3. 创建 `backend/tests/test_repository/` 目录
4. 创建 `backend/tests/test_repository/__init__.py`（空文件）

**验证**:
```bash
ls -la backend/app/repository/
ls -la backend/tests/test_repository/
```

---

#### 任务 1.2: 实现 BaseRepository
**目标**: 创建基础 Repository 类，提供通用方法

**文件**: `backend/app/repository/base.py`

**代码**:
```python
"""基础 Repository 实现"""

from datetime import datetime
from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """基础 Repository 实现"""

    def __init__(self, db: AsyncSession, model: Type[T]):
        self.db = db
        self.model = model

    def _base_query(self, include_deleted: bool = False):
        """构建基础查询，自动处理软删除过滤"""
        stmt = select(self.model)
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))
        return stmt

    async def find_by_id(self, id: int, include_deleted: bool = False) -> Optional[T]:
        """根据 ID 查询"""
        stmt = self._base_query(include_deleted).where(self.model.id == id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_all(
        self,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
        **filters
    ) -> List[T]:
        """查询所有记录，支持过滤和分页"""
        stmt = self._base_query(include_deleted)

        for key, value in filters.items():
            if value is not None and hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)

        stmt = stmt.offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self, include_deleted: bool = False, **filters) -> int:
        """统计记录数"""
        stmt = select(func.count(self.model.id))
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))

        for key, value in filters.items():
            if value is not None and hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)

        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def create(self, entity: T) -> T:
        """创建记录"""
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def update(self, entity: T) -> T:
        """更新记录"""
        entity.updated_at = datetime.utcnow()
        await self.db.flush()
        return entity

    async def soft_delete(self, id: int) -> bool:
        """软删除记录"""
        stmt = (
            update(self.model)
            .where(self.model.id == id, self.model.deleted_at.is_(None))
            .values(deleted_at=datetime.utcnow())
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0
```

**测试**: 跳过，后续在具体 Repository 测试中覆盖

**提交**: `git commit -m "feat(repository): add BaseRepository with soft delete support"`

---

#### 任务 1.3: 定义 Protocol 接口
**目标**: 创建所有 Repository 的 Protocol 定义

**文件**: `backend/app/repository/protocols.py`

**代码**:
```python
"""Repository Protocol 定义"""

from datetime import date
from decimal import Decimal
from typing import List, Optional, Protocol, TypeVar

T = TypeVar("T")


class BaseRepositoryProtocol(Protocol[T]):
    """基础 Repository 协议"""

    async def find_by_id(self, id: int, include_deleted: bool = False) -> Optional[T]: ...
    async def find_all(self, include_deleted: bool = False, **filters) -> List[T]: ...
    async def count(self, include_deleted: bool = False, **filters) -> int: ...
    async def create(self, entity: T) -> T: ...
    async def update(self, entity: T) -> T: ...
    async def soft_delete(self, id: int) -> bool: ...


class CustomerRepositoryProtocol(BaseRepositoryProtocol["Customer"], Protocol):
    """客户 Repository 协议"""

    async def find_by_company_id(
        self, company_id: int, include_deleted: bool = False
    ) -> Optional["Customer"]: ...
    async def find_by_manager_id(
        self, manager_id: int, include_deleted: bool = False
    ) -> List["Customer"]: ...
    async def search(
        self, keyword: str, include_deleted: bool = False
    ) -> List["Customer"]: ...


class InvoiceRepositoryProtocol(BaseRepositoryProtocol["Invoice"], Protocol):
    """结算单 Repository 协议"""

    async def find_by_customer_id(
        self,
        customer_id: int,
        status: Optional[str] = None,
        include_deleted: bool = False,
    ) -> List["Invoice"]: ...
    async def find_pending_invoices(self, customer_id: int) -> List["Invoice"]: ...
    async def get_total_amount(
        self, customer_id: int, status: Optional[str] = None
    ) -> Decimal: ...


class BalanceRepositoryProtocol(BaseRepositoryProtocol["CustomerBalance"], Protocol):
    """余额 Repository 协议"""

    async def get_by_customer_id(
        self, customer_id: int
    ) -> Optional["CustomerBalance"]: ...
    async def get_or_create(self, customer_id: int) -> "CustomerBalance": ...


class PricingRepositoryProtocol(BaseRepositoryProtocol["PricingRule"], Protocol):
    """定价规则 Repository 协议"""

    async def find_active_by_customer_id(
        self, customer_id: int, effective_date: date
    ) -> Optional["PricingRule"]: ...
```

**验证**: 确保类型提示正确，无语法错误

**提交**: `git commit -m "feat(repository): add Protocol definitions for all repositories"`

---

### 阶段 2: 实现具体 Repository（1 天）

#### 任务 2.1: 实现 CustomerRepository
**目标**: 实现客户 Repository，包含业务特定查询方法

**文件**: `backend/app/repository/customer_repo.py`

**代码**:
```python
"""客户 Repository"""

from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.customers import Customer
from .base import BaseRepository
from .protocols import CustomerRepositoryProtocol


class CustomerRepository(BaseRepository[Customer], CustomerRepositoryProtocol):
    """客户 Repository"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Customer)

    async def find_by_company_id(
        self, company_id: int, include_deleted: bool = False
    ) -> Optional[Customer]:
        """根据公司 ID 查询客户"""
        stmt = self._base_query(include_deleted).where(
            Customer.company_id == company_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_manager_id(
        self, manager_id: int, include_deleted: bool = False
    ) -> List[Customer]:
        """根据客户经理 ID 查询"""
        stmt = self._base_query(include_deleted).where(
            Customer.manager_id == manager_id
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self, keyword: str, include_deleted: bool = False
    ) -> List[Customer]:
        """搜索客户（名称、公司 ID 模糊匹配）"""
        stmt = self._base_query(include_deleted).where(
            or_(
                Customer.name.ilike(f"%{keyword}%"),
                Customer.company_id.cast(str).ilike(f"%{keyword}%"),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
```

**提交**: `git commit -m "feat(repository): implement CustomerRepository"`

---

#### 任务 2.2: 实现 InvoiceRepository
**目标**: 实现结算单 Repository

**文件**: `backend/app/repository/invoice_repo.py`

**代码**:
```python
"""结算单 Repository"""

from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.billing import Invoice
from .base import BaseRepository
from .protocols import InvoiceRepositoryProtocol


class InvoiceRepository(BaseRepository[Invoice], InvoiceRepositoryProtocol):
    """结算单 Repository"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Invoice)

    async def find_by_customer_id(
        self,
        customer_id: int,
        status: Optional[str] = None,
        include_deleted: bool = False,
    ) -> List[Invoice]:
        """根据客户 ID 查询结算单"""
        stmt = self._base_query(include_deleted).where(
            Invoice.customer_id == customer_id
        )
        if status:
            stmt = stmt.where(Invoice.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_pending_invoices(self, customer_id: int) -> List[Invoice]:
        """查询待处理结算单"""
        stmt = self._base_query().where(
            Invoice.customer_id == customer_id,
            Invoice.status.in_(["draft", "pending"]),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_total_amount(
        self, customer_id: int, status: Optional[str] = None
    ) -> Decimal:
        """获取结算单总金额"""
        stmt = select(func.sum(Invoice.total_amount)).where(
            Invoice.customer_id == customer_id,
            Invoice.deleted_at.is_(None),
        )
        if status:
            stmt = stmt.where(Invoice.status == status)
        result = await self.db.execute(stmt)
        return result.scalar() or Decimal("0")
```

**提交**: `git commit -m "feat(repository): implement InvoiceRepository"`

---

#### 任务 2.3: 实现 BalanceRepository
**目标**: 实现余额 Repository

**文件**: `backend/app/repository/balance_repo.py`

**代码**:
```python
"""余额 Repository"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.billing import CustomerBalance
from .base import BaseRepository
from .protocols import BalanceRepositoryProtocol


class BalanceRepository(BaseRepository[CustomerBalance], BalanceRepositoryProtocol):
    """余额 Repository"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, CustomerBalance)

    async def get_by_customer_id(
        self, customer_id: int
    ) -> Optional[CustomerBalance]:
        """根据客户 ID 获取余额"""
        stmt = self._base_query().where(CustomerBalance.customer_id == customer_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, customer_id: int) -> CustomerBalance:
        """获取或创建余额记录"""
        balance = await self.get_by_customer_id(customer_id)
        if not balance:
            balance = CustomerBalance(customer_id=customer_id, balance=0)
            self.db.add(balance)
            await self.db.flush()
        return balance
```

**提交**: `git commit -m "feat(repository): implement BalanceRepository"`

---

#### 任务 2.4: 实现 PricingRepository
**目标**: 实现定价规则 Repository

**文件**: `backend/app/repository/pricing_repo.py`

**代码**:
```python
"""定价规则 Repository"""

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.billing import PricingRule
from .base import BaseRepository
from .protocols import PricingRepositoryProtocol


class PricingRepository(BaseRepository[PricingRule], PricingRepositoryProtocol):
    """定价规则 Repository"""

    def __init__(self, db: AsyncSession):
        super().__init__(db, PricingRule)

    async def find_active_by_customer_id(
        self, customer_id: int, effective_date: date
    ) -> Optional[PricingRule]:
        """查询指定日期生效的定价规则"""
        stmt = self._base_query().where(
            PricingRule.customer_id == customer_id,
            PricingRule.effective_date <= effective_date,
        ).order_by(PricingRule.effective_date.desc()).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
```

**提交**: `git commit -m "feat(repository): implement PricingRepository"`

---

#### 任务 2.5: 更新 __init__.py 导出
**目标**: 在 __init__.py 中导出所有 Repository 和 Protocol

**文件**: `backend/app/repository/__init__.py`

**代码**:
```python
"""Repository 模块"""

from .balance_repo import BalanceRepository
from .customer_repo import CustomerRepository
from .invoice_repo import InvoiceRepository
from .pricing_repo import PricingRepository
from .protocols import (
    BalanceRepositoryProtocol,
    CustomerRepositoryProtocol,
    InvoiceRepositoryProtocol,
    PricingRepositoryProtocol,
)

__all__ = [
    # Repositories
    "CustomerRepository",
    "InvoiceRepository",
    "BalanceRepository",
    "PricingRepository",
    # Protocols
    "CustomerRepositoryProtocol",
    "InvoiceRepositoryProtocol",
    "BalanceRepositoryProtocol",
    "PricingRepositoryProtocol",
]
```

**验证**:
```bash
cd backend && python -c "from app.repository import CustomerRepository, CustomerRepositoryProtocol; print('OK')"
```

**提交**: `git commit -m "feat(repository): export all repositories and protocols"`

---

### 阶段 3: 编写测试（1 天）

#### 任务 3.1: 编写 CustomerRepository 测试
**目标**: 测试 CustomerRepository 的所有方法

**文件**: `backend/tests/test_repository/test_customer_repo.py`

**代码**:
```python
"""CustomerRepository 测试"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customers import Customer
from app.repository.customer_repo import CustomerRepository


@pytest.fixture
async def customer_repo(db_session: AsyncSession):
    """创建 CustomerRepository 实例"""
    return CustomerRepository(db_session)


@pytest.fixture
async def sample_customer(db_session: AsyncSession):
    """创建测试客户"""
    customer = Customer(
        company_id=10001,
        name="测试客户",
        account_type="enterprise",
        manager_id=1,
    )
    db_session.add(customer)
    await db_session.flush()
    return customer


class TestCustomerRepository:
    """CustomerRepository 测试类"""

    async def test_find_by_id(self, customer_repo: CustomerRepository, sample_customer: Customer):
        """测试根据 ID 查询"""
        customer = await customer_repo.find_by_id(sample_customer.id)
        assert customer is not None
        assert customer.id == sample_customer.id
        assert customer.name == "测试客户"

    async def test_find_by_id_not_found(self, customer_repo: CustomerRepository):
        """测试查询不存在的记录"""
        customer = await customer_repo.find_by_id(99999)
        assert customer is None

    async def test_soft_delete_excludes_by_default(
        self, customer_repo: CustomerRepository, sample_customer: Customer
    ):
        """测试软删除后默认排除"""
        # 先确认能查到
        customer = await customer_repo.find_by_id(sample_customer.id)
        assert customer is not None

        # 软删除
        await customer_repo.soft_delete(sample_customer.id)

        # 默认查询应该查不到
        customer = await customer_repo.find_by_id(sample_customer.id)
        assert customer is None

        # 显式包含已删除记录
        customer = await customer_repo.find_by_id(sample_customer.id, include_deleted=True)
        assert customer is not None

    async def test_find_by_company_id(
        self, customer_repo: CustomerRepository, sample_customer: Customer
    ):
        """测试根据公司 ID 查询"""
        customer = await customer_repo.find_by_company_id(10001)
        assert customer is not None
        assert customer.company_id == 10001

    async def test_find_by_company_id_not_found(self, customer_repo: CustomerRepository):
        """测试查询不存在的公司 ID"""
        customer = await customer_repo.find_by_company_id(99999)
        assert customer is None

    async def test_search_by_name(
        self, customer_repo: CustomerRepository, sample_customer: Customer
    ):
        """测试按名称搜索"""
        customers = await customer_repo.search("测试")
        assert len(customers) > 0
        assert any(c.name == "测试客户" for c in customers)

    async def test_search_by_company_id(
        self, customer_repo: CustomerRepository, sample_customer: Customer
    ):
        """测试按公司 ID 搜索"""
        customers = await customer_repo.search("10001")
        assert len(customers) > 0
        assert any(c.company_id == 10001 for c in customers)

    async def test_count(self, customer_repo: CustomerRepository, sample_customer: Customer):
        """测试计数"""
        count = await customer_repo.count()
        assert count >= 1

    async def test_count_with_filter(
        self, customer_repo: CustomerRepository, sample_customer: Customer
    ):
        """测试带过滤条件的计数"""
        count = await customer_repo.count(company_id=10001)
        assert count >= 1

        count = await customer_repo.count(company_id=99999)
        assert count == 0
```

**运行测试**:
```bash
cd backend && pytest tests/test_repository/test_customer_repo.py -v
```

**提交**: `git commit -m "test(repository): add CustomerRepository tests"`

---

#### 任务 3.2: 编写其他 Repository 测试
**目标**: 为 InvoiceRepository、BalanceRepository、PricingRepository 编写测试

**文件**:
- `backend/tests/test_repository/test_invoice_repo.py`
- `backend/tests/test_repository/test_balance_repo.py`
- `backend/tests/test_repository/test_pricing_repo.py`

**测试要点**:
- InvoiceRepository: 测试 `find_by_customer_id`、`find_pending_invoices`、`get_total_amount`
- BalanceRepository: 测试 `get_by_customer_id`、`get_or_create`
- PricingRepository: 测试 `find_active_by_customer_id`

**运行测试**:
```bash
cd backend && pytest tests/test_repository/ -v
```

**提交**: `git commit -m "test(repository): add tests for all repositories"`

---

### 阶段 4: 改造 Service 层（2.5 天）

#### 任务 4.1: 改造 CustomerService
**目标**: 将 CustomerService 中的直接查询替换为 Repository 调用

**文件**: `backend/app/services/customers.py`

**改造步骤**:
1. 修改构造函数，接收 `CustomerRepositoryProtocol` 而非 `AsyncSession`
2. 替换所有 `await self.db.execute(select(...))` 为 Repository 方法调用
3. 移除重复的软删除过滤逻辑

**示例改造**:
```python
# 改造前
class CustomerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_customer(self, customer_id: int):
        result = await self.db.execute(
            select(Customer).where(
                Customer.id == customer_id,
                Customer.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

# 改造后
class CustomerService:
    def __init__(self, customer_repo: CustomerRepositoryProtocol):
        self.customer_repo = customer_repo

    async def get_customer(self, customer_id: int):
        return await self.customer_repo.find_by_id(customer_id)
```

**验证**: 运行现有测试，确保行为不变
```bash
cd backend && pytest tests/test_services/test_customers.py -v
```

**提交**: `git commit -m "refactor(services): migrate CustomerService to use Repository"`

---

#### 任务 4.2: 改造 BillingService 相关类
**目标**: 改造 BalanceService、PricingService、InvoiceService

**文件**: `backend/app/services/billing.py`

**改造步骤**:
1. 修改各 Service 的构造函数，接收对应的 Repository
2. 替换直接查询为 Repository 方法
3. 移除重复逻辑

**示例改造**:
```python
# BalanceService 改造
class BalanceService:
    def __init__(self, balance_repo: BalanceRepositoryProtocol):
        self.balance_repo = balance_repo

    async def get_balance_by_customer_id(self, customer_id: int):
        return await self.balance_repo.get_by_customer_id(customer_id)

    async def get_or_create_balance(self, customer_id: int):
        return await self.balance_repo.get_or_create(customer_id)
```

**验证**: 运行现有测试
```bash
cd backend && pytest tests/test_services/test_billing.py -v
```

**提交**: `git commit -m "refactor(services): migrate billing services to use Repository"`

---

#### 任务 4.3: 改造 AnalyticsService
**目标**: 改造 AnalyticsService 中的查询

**文件**: `backend/app/services/analytics.py`

**改造步骤**:
1. 修改构造函数，接收多个 Repository
2. 替换统计查询为 Repository 方法
3. 保留复杂分析逻辑（Repository 只封装数据访问，不封装业务逻辑）

**验证**: 运行现有测试
```bash
cd backend && pytest tests/test_services/test_analytics.py -v
```

**提交**: `git commit -m "refactor(services): migrate AnalyticsService to use Repository"`

---

### 阶段 5: 改造路由层（1 天）

#### 任务 5.1: 改造客户路由
**目标**: 在路由中创建 Repository 并注入 Service

**文件**: `backend/app/routes/customers.py`

**改造步骤**:
1. 导入 Repository
2. 在路由处理函数中创建 Repository 实例
3. 将 Repository 注入 Service

**示例改造**:
```python
# 改造前
@bp.get("/<customer_id:int>")
@auth_required("customer:view")
async def get_customer(request, customer_id: int):
    db_session = request.ctx.db_session
    service = CustomerService(db_session)
    customer = await service.get_customer(customer_id)
    # ...

# 改造后
@bp.get("/<customer_id:int>")
@auth_required("customer:view")
async def get_customer(request, customer_id: int):
    db_session = request.ctx.db_session
    customer_repo = CustomerRepository(db_session)
    service = CustomerService(customer_repo)
    customer = await service.get_customer(customer_id)
    # ...
```

**验证**: 启动服务，手动测试 API
```bash
cd backend && python app/main.py
# 使用 curl 或 Postman 测试 API
```

**提交**: `git commit -m "refactor(routes): migrate customer routes to inject Repository"`

---

#### 任务 5.2: 改造结算路由
**目标**: 改造 billing 相关路由

**文件**: `backend/app/routes/billing.py`

**改造步骤**:
1. 导入 Repository
2. 创建 Repository 实例并注入 Service
3. 替换路由层的直接查询

**验证**: 测试结算相关 API

**提交**: `git commit -m "refactor(routes): migrate billing routes to inject Repository"`

---

### 阶段 6: 集成测试与验证（1 天）

#### 任务 6.1: 运行全量测试
**目标**: 确保所有测试通过

**命令**:
```bash
cd backend && pytest tests/ -v --cov=app --cov-report=term-missing
```

**验证标准**:
- 所有测试通过
- 覆盖率不低于改造前

---

#### 任务 6.2: 代码审查
**目标**: 检查代码质量

**检查项**:
- [ ] 所有 Repository 方法都有类型提示
- [ ] 软删除过滤逻辑统一
- [ ] 无重复查询代码
- [ ] Service 层不再直接使用 ORM 查询
- [ ] 路由层不再直接执行数据库查询

---

#### 任务 6.3: 性能验证
**目标**: 确保性能无退化

**方法**:
- 对比改造前后的 API 响应时间
- 检查数据库查询计划（EXPLAIN ANALYZE）
- 确认无 N+1 查询问题

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 改造过程中引入 bug | 每个阶段独立测试，保留旧代码作为 fallback |
| 性能退化 | 性能验证阶段对比前后指标 |
| 团队不熟悉新模式 | 代码审查 + 文档说明 |

---

## 验收标准

- [ ] 4 个 Repository 实现完成并通过测试
- [ ] Service 层不再直接使用 ORM 查询
- [ ] 路由层不再直接执行数据库查询
- [ ] 所有现有测试通过
- [ ] 代码覆盖率不低于改造前
- [ ] 性能无退化

---

## 后续工作

完成本计划后，可继续：
1. 为其他模型补充 Repository（User、Tag、DailyConsumption 等）
2. 开始 TD-001（后端大文件拆分）
3. 引入依赖注入框架（如 `dependency-injector`）简化 Repository 注入
