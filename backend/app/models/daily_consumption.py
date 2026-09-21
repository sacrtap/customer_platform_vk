"""每日消费数据模型"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class DailyConsumption(BaseModel):
    """每日消费数据模型"""

    __tablename__ = "daily_consumptions"

    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id"), nullable=False, comment="客户 ID"
    )
    consumption_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="消费日期"
    )
    device_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="设备类型")
    layer_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="图层类型")
    order_count: Mapped[int | None] = mapped_column(Integer, default=0, comment="订单数量")
    total_floor_count: Mapped[int | None] = mapped_column(Integer, default=0, comment="总楼层数")
    total_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), default=0, comment="总消费金额"
    )
    pricing_rule_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pricing_rules.id"), nullable=True, comment="定价规则 ID"
    )
    has_pricing_rule: Mapped[bool | None] = mapped_column(
        Boolean, default=False, comment="是否有定价规则"
    )

    # 关系
    customer = relationship("Customer", back_populates="daily_consumptions")
    pricing_rule = relationship("PricingRule", back_populates="daily_consumptions")

    # 索引和约束
    __table_args__ = (
        Index(
            "idx_daily_consumption_customer_date",
            "customer_id",
            "consumption_date",
        ),
        Index("idx_daily_consumption_date", "consumption_date"),
        UniqueConstraint(
            "customer_id",
            "consumption_date",
            "device_type",
            "layer_type",
            name="uq_consumption_unique",
        ),
    )

    def __repr__(self):
        return f"<DailyConsumption(customer_id={self.customer_id}, date={self.consumption_date})>"
