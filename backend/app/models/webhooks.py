"""Webhook 相关模型"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class WebhookSignature(BaseModel):
    """Webhook 签名记录表 - 用于防止重放攻击"""

    __tablename__ = "webhook_signatures"

    signature: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, comment="请求签名"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True, comment="请求时间戳"
    )
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False, comment="Webhook 端点")
    is_consumed: Mapped[bool | None] = mapped_column(Boolean, default=False, comment="是否已使用")

    # 复合索引加速查询
    __table_args__ = (Index("idx_webhook_sig_timestamp", "signature", "timestamp"),)

    def __repr__(self):
        return f"<WebhookSignature {self.signature[:16]}... at {self.timestamp}>"
