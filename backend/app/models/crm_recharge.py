"""CRM 充值管理镜像模型

CRM（weiwenjia）回款只读镜像：同步只写这三张表，不触碰资金与充值记录。
资金写入唯一入口是 `CrmRechargeService.import_payment` → `BalanceService.recharge`。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BIGINT,
    DECIMAL,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class CrmCustomer(BaseModel):
    """CRM 客户目录（仅推荐与绑定所需字段）"""

    __tablename__ = "crm_customers"

    corp_id: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # NFKC + casefold + 去空白标点后的名称，用于本地包含/相似度推荐
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="最近一次同步可见时间(CST)"
    )

    __table_args__ = (
        UniqueConstraint("corp_id", "external_id", name="uq_crm_customers_corp_external"),
        Index("idx_crm_customers_normalized_name", "normalized_name"),
    )

    def __repr__(self):
        return f"<CrmCustomer {self.external_id} {self.name}>"


class CrmPayment(BaseModel):
    """CRM 回款镜像

    `amount` / `receive_date` 允许 NULL：上游金额或日期异常时保留行并写
    `blocked_reason`，不把异常解析成 0 或当前日期。
    """

    __tablename__ = "crm_payments"

    corp_id: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    crm_customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("crm_customers.id"), nullable=True, index=True
    )
    contract_external_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    contract_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_external_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 2), nullable=True)
    receive_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    approve_status: Mapped[str] = mapped_column(String(32), nullable=False)
    industry_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="最近一次同步可见时间(CST)"
    )
    # 导入时的源业务快照（白名单），后续同步与新详情比较判定 source_changed
    imported_snapshot: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    source_changed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    __table_args__ = (
        UniqueConstraint("corp_id", "external_id", name="uq_crm_payments_corp_external"),
        Index("idx_crm_payments_receive_date_eligible", "receive_date", "eligible"),
    )

    def __repr__(self):
        return f"<CrmPayment {self.external_id} {self.amount}>"


class CrmSyncRun(BaseModel):
    """CRM 月度同步执行记录

    单企业同时只允许一个活跃（pending/running）run，靠部分唯一索引兜底，
    跨 worker 互斥不依赖 APScheduler 的 max_instances。
    """

    __tablename__ = "crm_sync_runs"

    corp_id: Mapped[str] = mapped_column(String(64), nullable=False)
    month: Mapped[date] = mapped_column(Date, nullable=False, comment="同步月份月首")
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, comment="scheduled/manual")
    operator_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="pending/running/succeeded/failed"
    )
    phase: Mapped[str] = mapped_column(
        String(24), nullable=False, comment="customers/contracts/payments/completed"
    )
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    customer_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    contract_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    scanned_contract_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    scanned_payment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    payment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    eligible_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "uq_crm_sync_active_corp",
            "corp_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
        Index("idx_crm_sync_runs_month", "month", "status"),
    )

    def __repr__(self):
        return f"<CrmSyncRun {self.month} {self.status}>"
