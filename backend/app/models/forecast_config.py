"""预测消费单价配置模型"""

from sqlalchemy import Column, DateTime, Numeric, String, func

from . import Base


class ForecastUnitPrice(Base):
    """预测消费单价配置表

    各设备类型的单价（元/套），可运行时修改。
    表为空时回退到 config.py 的默认值。
    """

    __tablename__ = "forecast_unit_prices"

    device_type = Column(String(10), primary_key=True, comment="设备类型（L/N/X）")
    unit_price = Column(Numeric(10, 2), nullable=False, comment="单价（元/套）")
    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<ForecastUnitPrice {self.device_type}={self.unit_price}>"
