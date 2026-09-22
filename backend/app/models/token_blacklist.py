# -*- coding: utf-8 -*-
"""Token 黑名单模型"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import BaseModel


class TokenBlacklist(BaseModel):
    """Token 黑名单表"""

    __tablename__ = "token_blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    token_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "access" or "refresh"
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    blacklisted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_token_blacklist_jti", "jti"),
        Index("idx_token_blacklist_expires", "expires_at"),
    )
