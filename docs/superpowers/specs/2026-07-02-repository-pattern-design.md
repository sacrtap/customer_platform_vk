# Repository 模式设计文档

**创建日期**: 2026-07-02
**技术债务**: TD-005
**状态**: 待实施

---

## 1. 背景与问题

### 当前问题
- 服务层直接使用 `await db.execute(select(...))` 执行 ORM 查询
- 软删除过滤 `deleted_at.is_(None)` 在多处重复出现
- 相同的查询逻辑（如获取客户余额、统计数量）在多个文件中重复
- 路由层也存在直接数据库查询
- 难以单元测试，需要 mock 数据库

### 目标
- 封装数据访问逻辑，提高代码复用性
- 统一软删除处理
- 提升可测试性（通过 Protocol 便于 mock）
- 为后续代码拆分（TD-001）奠定架构基础

---

## 2. 设计决策

### 决策 1：覆盖范围 - 高频优先
先为查询最密集的 4 个模型创建 Repository：
- `Customer` - 客户信息
- `Invoice` - 结算单
- `CustomerBalance` - 客户余额
- `PricingRule` - 定价规则

**理由**：投入产出比最高，先解决最痛的重复问题，可在实践中验证模式。

### 决策 2：软删除处理 - 显式参数
提供 `include_deleted=False` 参数，默认过滤软删除记录，允许调用方显式包含。

**理由**：
- 默认行为安全（过滤软删除）
- 保留灵活性（审计、恢复场景需要查询已删除记录）
- 接口清晰，不会隐藏重要行为

### 决策 3：接口契约 - 使用 Protocol
定义 `CustomerRepositoryProtocol` 等接口，Repository 实现这些接口。

**理由**：
- 便于单元测试 mock
- 符合依赖倒置原则
- Python 3.12 的 Protocol 支持良好，开销很小

### 决策 4：代码组织 - 经典分层架构
每个 Repository 一个文件，Protocol 集中在 `protocols.py`。

```
backend/app/repository/
├── __init__.py              # 导出所有 Repository 和 Protocol
├── protocols.py             # 所有 Protocol 定义
├── base.py                  # 基础 Repository 类（通用方法）
├── customer_repo.py         # CustomerRepository
├── invoice_repo.py          # InvoiceRepository
├── balance_repo.py          # BalanceRepository
└── pricing_repo.py          # PricingRepository
```

**理由**：文件粒度适中，易于导航，符合常见 Python 项目惯例。

---

## 3. 架构设计

### 依赖关系
```
Route → Service → Repository → Model
                  ↓
              AsyncSession
```

### 注入方式
- Repository 通过构造函数接收 `AsyncSession`
- Service 通过构造函数接收 Repository 实例
- Route 创建 Repository 并注入 Service

### 示例代码
```python
# 在 route 中
customer_repo = CustomerRepository(db_session)
service = CustomerService(customer_repo)
```

---

## 4. Protocol 定义

```python
# repository/protocols.py
from typing import Protocol, Optional, List, TypeVar
from decimal import Decimal
from datetime import date

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

    async def find_by_company_id(self, company_id: int, include_deleted: bool = False) -> Optional["Customer"]: ...
    async def find_by_manager_id(self, manager_id: int, include_deleted: bool = False) -> List["Customer"]: ...
    async def search(self, keyword: str, include_deleted: bool = False) -> List["Customer"]: ...

class InvoiceRepositoryProtocol(BaseRepositoryProtocol["Invoice"], Protocol):
    """结算单 Repository 协议"""

    async def find_by_customer_id(self, customer_id: int, status: Optional[str] = None, include_deleted: bool = False) -> List["Invoice"]: ...
    async def find_pending_invoices(self, customer_id: int) -> List["Invoice"]: ...
    async def get_total_amount(self, customer_id: int, status: Optional[str] = None) -> Decimal: ...

class BalanceRepositoryProtocol(BaseRepositoryProtocol["CustomerBalance"], Protocol):
    """余额 Repository 协议"""

    async def get_by_customer_id(self, customer_id: int) -> Optional["CustomerBalance"]: ...
    async def get_or_create(self, customer_id: int) -> "CustomerBalance": ...

class PricingRepositoryProtocol(BaseRepositoryProtocol["PricingRule"], Protocol):
    """定价规则 Repository 协议"""

    async def find_active_by_customer_id(self, customer_id: int, effective_date: date) -> Optional["PricingRule"]: ...
```

---

## 5. 基础 Repository 实现

```python
# repository/base.py
from typing import Type, TypeVar, Generic, Optional, List
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

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

---

## 6. 具体 Repository 实现示例

```python
# repository/customer_repo.py
from typing import Optional, List
from sqlalchemy import select, or_
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
                Customer.company_id.cast(str).ilike(f"%{keyword}%")
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
```

---

## 7. Service 层集成

### 改造前
```python
# services/customers.py
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
```

### 改造后
```python
# services/customers.py
class CustomerService:
    def __init__(self, customer_repo: CustomerRepositoryProtocol):
        self.customer_repo = customer_repo

    async def get_customer(self, customer_id: int):
        return await self.customer_repo.find_by_id(customer_id)
```

### Route 层集成
```python
# routes/customers.py
@bp.get("/<customer_id:int>")
@auth_required("customer:view")
async def get_customer(request, customer_id: int):
    db_session = request.ctx.db_session
    customer_repo = CustomerRepository(db_session)
    service = CustomerService(customer_repo)

    customer = await service.get_customer(customer_id)
    if not customer:
        return json({"error": "客户不存在"}, status=404)
    return json(customer.to_dict())
```

---

## 8. 测试策略

```python
# tests/test_repository/test_customer_repo.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.customer_repo import CustomerRepository
from app.models.customers import Customer

class TestCustomerRepository:
    @pytest.fixture
    def repo(self, db_session: AsyncSession):
        return CustomerRepository(db_session)

    async def test_find_by_id_excludes_soft_deleted(self, repo: CustomerRepository):
        """验证软删除过滤默认生效"""
        customer = await repo.find_by_id(1)
        assert customer is not None

        await repo.soft_delete(1)
        customer = await repo.find_by_id(1)
        assert customer is None

        # 显式包含已删除
        customer = await repo.find_by_id(1, include_deleted=True)
        assert customer is not None

    async def test_find_by_company_id(self, repo: CustomerRepository):
        """验证业务方法"""
        customer = await repo.find_by_company_id(10001)
        assert customer is not None
        assert customer.company_id == 10001
```

---

## 9. 迁移计划

| 阶段 | 内容 | 工作量 |
|------|------|--------|
| 1 | 创建 Repository 基础设施（base, protocols） | 0.5天 |
| 2 | 实现 4 个高频 Repository | 1天 |
| 3 | 改造 CustomerService 使用 Repository | 1天 |
| 4 | 改造 BillingService 相关类 | 1.5天 |
| 5 | 改造 AnalyticsService | 1天 |
| 6 | 改造路由层直接查询 | 1天 |
| 7 | 编写测试并验证 | 1天 |

**预计总工作量**: 约 1 周（5-7 天）

---

## 10. 风险控制

- 每个阶段独立可测试，不影响其他模块
- 保留旧 Service 方法作为 fallback，逐步替换
- 改造前后运行相同测试用例验证行为一致
- 渐进式迁移，避免大规模重构风险

---

## 11. 成功标准

- [ ] 4 个高频 Repository 实现完成
- [ ] Service 层不再直接使用 ORM 查询
- [ ] 路由层不再直接执行数据库查询
- [ ] 所有 Repository 方法有单元测试覆盖
- [ ] 现有测试全部通过，行为无变化
- [ ] 代码行数减少（消除重复查询逻辑）
