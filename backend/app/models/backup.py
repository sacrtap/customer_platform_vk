"""数据备份模型"""

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class BackupScheduleConfig(Base, TimestampMixin):
    """定时备份配置表

    管理「每日数据库自动备份」任务的调度配置（单行 daily_backup）：
    - enabled: 是否启用每日备份
    - backup_time: 备份时间（HH:MM，24小时制）
    """

    __tablename__ = "backup_schedule_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="任务名称（单行 daily_backup）"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", comment="是否启用每日备份"
    )
    backup_time: Mapped[str] = mapped_column(
        String(5), nullable=False, default="02:00", server_default="02:00", comment="备份时间 HH:MM"
    )
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="更新人"
    )

    def __repr__(self):
        return f"<BackupScheduleConfig {self.task_name} [{self.enabled}] {self.backup_time}>"


class BackupRecord(Base, TimestampMixin):
    """备份任务留痕表

    记录备份（daily_backup/manual_backup）、清理（cleanup）、恢复（restore）四类任务的执行轨迹。
    """

    __tablename__ = "backup_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="任务类型: daily_backup/manual_backup/cleanup/restore",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="任务状态: pending/running/success/failed",
    )
    file_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="备份文件相对路径（cleanup 为空；restore 为源备份路径）"
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="备份文件大小（字节）"
    )
    backup_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="备份对应业务日期（cleanup 为空；restore 取源备份日期）"
    )
    retention_check_passed: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, comment="仅 cleanup：保留窗口内备份校验结果"
    )
    deleted_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="仅 cleanup：删除文件数"
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="耗时（秒）"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因/详情")
    operator_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="操作人（定时任务为 NULL）"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="开始时间"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="完成时间"
    )

    def __repr__(self):
        return f"<BackupRecord {self.id} [{self.task_type}/{self.status}]>"
