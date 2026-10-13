"""余额白名单模型

开放平台 /api/v1/balances 接口对白名单客户返回静态余额（优先于计算余额）。
"""

from decimal import Decimal

from sqlalchemy import DECIMAL, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class BalanceWhitelist(BaseModel):
    """余额白名单表"""

    __tablename__ = "balance_whitelists"

    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, unique=True
    )  # 白名单客户（同一客户仅一条记录，重复导入幂等跳过）
    static_balance: Mapped[Decimal] = mapped_column(
        DECIMAL(12, 2), nullable=False, default=Decimal("1000.00")
    )  # 静态余额（元），默认 1000

    def __repr__(self):
        return f"<BalanceWhitelist customer_id={self.customer_id} static_balance={self.static_balance}>"
