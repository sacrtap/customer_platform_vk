"""Repository 模式实现"""

from .balance_repo import BalanceRepository
from .base import BaseRepository
from .customer_repo import CustomerRepository
from .invoice_repo import InvoiceRepository
from .pricing_repo import PricingRepository
from .protocols import (
    BalanceRepositoryProtocol,
    BaseRepositoryProtocol,
    CustomerRepositoryProtocol,
    InvoiceRepositoryProtocol,
    PricingRepositoryProtocol,
)

__all__ = [
    # Base
    "BaseRepository",
    "BaseRepositoryProtocol",
    # Customer
    "CustomerRepository",
    "CustomerRepositoryProtocol",
    # Invoice
    "InvoiceRepository",
    "InvoiceRepositoryProtocol",
    # Balance
    "BalanceRepository",
    "BalanceRepositoryProtocol",
    # Pricing
    "PricingRepository",
    "PricingRepositoryProtocol",
]
