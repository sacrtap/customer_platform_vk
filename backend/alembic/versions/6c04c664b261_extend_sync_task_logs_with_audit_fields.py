"""extend sync_task_logs with audit fields

Revision ID: 6c04c664b261
Revises: 59e4cca22335
Create Date: 2026-06-24 15:28:27.354873

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6c04c664b261"
down_revision: Union[str, None] = "59e4cca22335"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sync_task_logs",
        sa.Column("task_id", sa.UUID(), nullable=True, comment="关联任务ID"),
    )
    op.add_column(
        "sync_task_logs",
        sa.Column("operator_id", sa.Integer(), nullable=True, comment="操作人"),
    )
    op.add_column(
        "sync_task_logs",
        sa.Column("start_date", sa.Date(), nullable=True, comment="同步开始日期"),
    )
    op.add_column(
        "sync_task_logs",
        sa.Column("end_date", sa.Date(), nullable=True, comment="同步结束日期"),
    )
    op.add_column(
        "sync_task_logs",
        sa.Column(
            "sync_mode",
            sa.String(length=20),
            nullable=True,
            comment="同步模式: skip_existing/force_overwrite",
        ),
    )
    op.create_foreign_key(
        "fk_sync_task_logs_task_id",
        "sync_task_logs",
        "sync_tasks",
        ["task_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_sync_task_logs_operator_id",
        "sync_task_logs",
        "users",
        ["operator_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_sync_task_logs_operator_id", "sync_task_logs", type_="foreignkey")
    op.drop_constraint("fk_sync_task_logs_task_id", "sync_task_logs", type_="foreignkey")
    op.drop_column("sync_task_logs", "sync_mode")
    op.drop_column("sync_task_logs", "end_date")
    op.drop_column("sync_task_logs", "start_date")
    op.drop_column("sync_task_logs", "operator_id")
    op.drop_column("sync_task_logs", "task_id")
