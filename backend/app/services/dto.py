"""数据传输对象"""

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class SyncDetail:
    """同步任务执行明细

    由同步链路各环节（订单同步/费用计算/数据校验/任务级）产生，
    通过 detail_collector 收集后统一写入 sync_task_log_details。
    """

    sync_date: date
    level: str  # info / warning / error
    category: str  # order_fetch / order_match / order_save / cost_calc / data_check / system
    message: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    external_customer_id: Optional[str] = None
    company_name: Optional[str] = None
    order_code: Optional[str] = None
    record_count: int = 1


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
