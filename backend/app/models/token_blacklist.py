# -*- coding: utf-8 -*-
"""Token 黑名单模型"""

from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func
from .base import BaseModel


class TokenBlacklist(BaseModel):
    """Token 黑名单表"""

    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String(100), unique=True, nullable=False, index=True)
    token_type = Column(String(20), nullable=False)  # "access" or "refresh"
    expires_at = Column(DateTime(timezone=True), nullable=False)
    blacklisted_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_token_blacklist_jti", "jti"),
        Index("idx_token_blacklist_expires", "expires_at"),
    )
