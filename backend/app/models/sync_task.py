"""异步同步任务模型"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class SyncTask(Base, TimestampMixin):
    """异步同步任务"""

    __tablename__ = "sync_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="任务ID"
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, comment="同步开始日期")
    end_date: Mapped[date] = mapped_column(Date, nullable=False, comment="同步结束日期")
    sync_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="skip_existing", comment="同步模式"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", comment="任务状态"
    )
    total_days: Mapped[int] = mapped_column(Integer, nullable=False, comment="总天数")
    completed_days: Mapped[int | None] = mapped_column(Integer, default=0, comment="已完成天数")
    skipped_days: Mapped[int | None] = mapped_column(Integer, default=0, comment="跳过天数")
    current_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="当前处理日期")
    success_count: Mapped[int | None] = mapped_column(Integer, default=0, comment="成功同步条数")
    failed_count: Mapped[int | None] = mapped_column(Integer, default=0, comment="失败条数")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因")
    operator_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="操作人（定时任务为NULL）"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="完成时间"
    )

    # 关联
    operator = relationship("User", backref="sync_tasks")

    def __repr__(self):
        return f"<SyncTask {self.id} [{self.status}]>"
