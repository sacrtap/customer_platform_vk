"""每日订单数据模型"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class DailyOrder(BaseModel):
    """每日订单数据模型"""

    __tablename__ = "daily_orders"

    order_code: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="订单 ID（外部系统）"
    )
    custom_code: Mapped[str | None] = mapped_column(String(50), comment="房源编号")
    nest_id: Mapped[str | None] = mapped_column(String(50), comment="模型编号")
    company_name: Mapped[str | None] = mapped_column(String(200), comment="公司名称")
    group_type: Mapped[str | None] = mapped_column(String(50), comment="客户 ID（外部系统）")
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id"), comment="系统客户 ID"
    )
    create_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="订单创建时间（外部系统）"
    )
    upload_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="订单上传日期（外部系统）"
    )
    order_status: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="订单状态（外部系统）"
    )
    floor_count: Mapped[int | None] = mapped_column(Integer, comment="楼层数")
    device_type: Mapped[str | None] = mapped_column(String(10), comment="设备类型（X/N/L）")
    sync_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="同步日期"
    )

    # 关系
    customer = relationship("Customer", backref="daily_orders")

    # 索引
    __table_args__ = (
        Index("idx_daily_orders_customer_date", "customer_id", "sync_date"),
        Index("idx_daily_orders_sync_date", "sync_date"),
        UniqueConstraint("order_code", "sync_date", name="uq_order_code_sync_date"),
    )

    def __repr__(self):
        return f"<DailyOrder(order_code={self.order_code}, sync_date={self.sync_date})>"
