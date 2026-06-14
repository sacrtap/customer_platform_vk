from dataclasses import dataclass


@dataclass
class SyncResult:
    """订单同步结果"""

    success: int = 0
    failed: int = 0
    skipped: int = 0
    unmatched: int = 0
    message: str = ""


@dataclass
class CalcResult:
    """费用计算结果"""

    total_customers: int = 0
    calculated: int = 0
    no_rule: int = 0
    message: str = ""


@dataclass
class CustomerCalcResult:
    """单个客户费用计算结果"""

    customer_id: int
    customer_name: str
    has_rule: bool
    order_count: int = 0
    total_cost: float = 0.0
    message: str = ""
