"""Repository Protocol 接口定义"""

from datetime import date
from decimal import Decimal
from typing import Any, List, Optional, Protocol, Sequence, TypeVar, runtime_checkable

from ..models.billing import CustomerBalance, Invoice, PricingRule
from ..models.customers import Customer

T = TypeVar("T")


@runtime_checkable
class BaseRepositoryProtocol(Protocol[T]):
    """基础 Repository 协议"""

    async def find_by_id(
        self, id: int, include_deleted: bool = False, options: Optional[Sequence[Any]] = None
    ) -> Optional[T]: ...

    async def find_all(
        self,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
        **filters,
    ) -> List[T]: ...

    async def count(self, include_deleted: bool = False, **filters) -> int: ...

    async def create(self, entity: T) -> T: ...

    async def update(self, entity: T) -> T: ...

    async def soft_delete(self, id: int) -> bool: ...


@runtime_checkable
class CustomerRepositoryProtocol(BaseRepositoryProtocol[Customer], Protocol):
    """客户 Repository 协议"""

    async def find_by_company_id(
        self, company_id: int, include_deleted: bool = False
    ) -> Optional[Customer]: ...

    async def find_by_manager_id(
        self, manager_id: int, include_deleted: bool = False
    ) -> List[Customer]: ...

    async def search(self, keyword: str, include_deleted: bool = False) -> List[Customer]: ...


@runtime_checkable
class InvoiceRepositoryProtocol(BaseRepositoryProtocol[Invoice], Protocol):
    """发票 Repository 协议"""

    async def find_by_customer_id(
        self,
        customer_id: int,
        status: Optional[str] = None,
        include_deleted: bool = False,
    ) -> List[Invoice]: ...

    async def find_pending_invoices(self, customer_id: int) -> List[Invoice]: ...

    async def get_total_amount(self, customer_id: int, status: Optional[str] = None) -> Decimal: ...


@runtime_checkable
class BalanceRepositoryProtocol(BaseRepositoryProtocol[CustomerBalance], Protocol):
    """余额 Repository 协议"""

    async def get_by_customer_id(self, customer_id: int) -> Optional[CustomerBalance]: ...

    async def get_or_create(self, customer_id: int) -> CustomerBalance: ...


@runtime_checkable
class PricingRepositoryProtocol(BaseRepositoryProtocol[PricingRule], Protocol):
    """定价规则 Repository 协议"""

    async def find_active_by_customer_id(
        self, customer_id: int, effective_date: date
    ) -> Optional[PricingRule]: ...
