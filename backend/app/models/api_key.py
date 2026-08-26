"""API-Key 模型"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import BaseModel


class ApiKey(BaseModel):
    """开放平台 API-Key 表"""

    __tablename__ = "api_keys"

    name = Column(String(100), nullable=False)  # API-Key 名称
    key_prefix = Column(String(16), nullable=False, index=True)  # 前 8 位，用于列表脱敏展示
    key_hash = Column(String(255), nullable=False, unique=True, index=True)  # SHA-256 哈希
    status = Column(String(20), nullable=False, default="active", index=True)  # active/disabled
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=True)  # 可选过期时间
    last_used_at = Column(DateTime, nullable=True)  # 最后使用时间

    __table_args__ = (
        Index("idx_api_keys_status", "status"),
        Index("idx_api_keys_key_hash", "key_hash"),
    )

    # 关联
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<ApiKey {self.name} ({self.key_prefix}****)>"
