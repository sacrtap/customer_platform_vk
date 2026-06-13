"""每日消费数据模型"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class DailyConsumption(BaseModel):
    """每日消费数据模型"""

    __tablename__ = "daily_consumptions"

    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, comment="客户 ID")
    consumption_date = Column(Date, nullable=False, comment="消费日期")
    device_type = Column(String(50), nullable=False, comment="设备类型")
    layer_type = Column(String(50), nullable=False, comment="图层类型")
    order_count = Column(Integer, default=0, comment="订单数量")
    total_cost = Column(Numeric(12, 2), default=0, comment="总消费金额")
    pricing_rule_id = Column(
        Integer, ForeignKey("pricing_rules.id"), nullable=True, comment="定价规则 ID"
    )
    has_pricing_rule = Column(Boolean, default=False, comment="是否有定价规则")

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
