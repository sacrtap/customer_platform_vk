"""定时同步配置模型"""

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class SyncScheduleConfig(Base, TimestampMixin):
    """定时同步配置表

    管理「每日自动同步」任务的调度配置（单行 daily_sync）：
    - enabled: 是否启用定时同步
    - sync_time: 执行时间（HH:MM，24小时制）
    - sync_mode: 同步模式（skip_existing/force_overwrite）
    """

    __tablename__ = "sync_schedule_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="任务名称（预留多任务扩展）"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", comment="是否启用"
    )
    sync_time: Mapped[str] = mapped_column(
        String(5), nullable=False, default="01:00", server_default="01:00", comment="执行时间 HH:MM"
    )
    sync_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="skip_existing",
        server_default="skip_existing",
        comment="同步模式: skip_existing/force_overwrite",
    )
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="更新人"
    )

    def __repr__(self):
        return f"<SyncScheduleConfig {self.task_name} [{self.enabled}] {self.sync_time}>"
