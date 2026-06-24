"""异步同步任务模型"""

import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class SyncTask(Base, TimestampMixin):
    """异步同步任务"""

    __tablename__ = "sync_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="任务ID")
    start_date = Column(Date, nullable=False, comment="同步开始日期")
    end_date = Column(Date, nullable=False, comment="同步结束日期")
    sync_mode = Column(String(20), nullable=False, default="skip_existing", comment="同步模式")
    status = Column(String(20), nullable=False, default="pending", comment="任务状态")
    total_days = Column(Integer, nullable=False, comment="总天数")
    completed_days = Column(Integer, default=0, comment="已完成天数")
    skipped_days = Column(Integer, default=0, comment="跳过天数")
    current_date = Column(Date, nullable=True, comment="当前处理日期")
    success_count = Column(Integer, default=0, comment="成功同步条数")
    failed_count = Column(Integer, default=0, comment="失败条数")
    error_message = Column(Text, nullable=True, comment="失败原因")
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="操作人")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")

    # 关联
    operator = relationship("User", backref="sync_tasks")

    def __repr__(self):
        return f"<SyncTask {self.id} [{self.status}]>"
