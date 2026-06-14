"""每日订单数据模型"""

from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .base import BaseModel


class DailyOrder(BaseModel):
    """每日订单数据模型"""

    __tablename__ = "daily_orders"

    order_code = Column(String(50), nullable=False, comment="订单 ID（外部系统）")
    custom_code = Column(String(50), comment="房源编号")
    nest_id = Column(String(50), comment="模型编号")
    company_name = Column(String(200), comment="公司名称")
    group_type = Column(String(50), comment="客户 ID（外部系统）")
    customer_id = Column(Integer, ForeignKey("customers.id"), comment="系统客户 ID")
    create_date = Column(Date, nullable=False, comment="订单创建时间")
    floor_count = Column(Integer, comment="楼层数")
    device_type = Column(String(10), comment="设备类型（X/N/L）")
    sync_date = Column(Date, nullable=False, comment="同步日期")

    # 关系
    customer = relationship("Customer", backref="daily_orders")

    # 索引
    __table_args__ = (
        Index("idx_daily_orders_customer_date", "customer_id", "create_date"),
        Index("idx_daily_orders_sync_date", "sync_date"),
        UniqueConstraint("order_code", "create_date", name="uq_order_code_date"),
    )

    def __repr__(self):
        return f"<DailyOrder(order_code={self.order_code}, create_date={self.create_date})>"
