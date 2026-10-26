"""add backup feature

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-26

数据备份功能：
1. 新增 backup_schedule_configs 定时备份配置表（单行 daily_backup），
   支持页面配置每日自动备份的开启/关闭与执行时间。
2. 新增 backup_records 备份任务留痕表，
   记录备份（daily_backup/manual_backup）、清理（cleanup）、恢复（restore）四类任务轨迹。
3. 新增权限 system:database_backup（数据备份，默认仅超级管理员）并关联超管角色。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- 1. 定时备份配置表 + 默认行 ----
    op.create_table(
        "backup_schedule_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "task_name",
            sa.String(length=50),
            nullable=False,
            comment="任务名称（单行 daily_backup）",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="是否启用每日备份",
        ),
        sa.Column(
            "backup_time",
            sa.String(length=5),
            server_default="02:00",
            nullable=False,
            comment="备份时间 HH:MM",
        ),
        sa.Column("updated_by", sa.Integer(), nullable=True, comment="更新人"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_name"),
    )
    op.bulk_insert(
        sa.table(
            "backup_schedule_configs",
            sa.column("task_name", sa.String),
            sa.column("enabled", sa.Boolean),
            sa.column("backup_time", sa.String),
        ),
        [
            {
                "task_name": "daily_backup",
                "enabled": False,
                "backup_time": "02:00",
            },
        ],
    )

    # ---- 2. 备份任务留痕表 ----
    op.create_table(
        "backup_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "task_type",
            sa.String(length=20),
            nullable=False,
            comment="任务类型: daily_backup/manual_backup/cleanup/restore",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
            comment="任务状态: pending/running/success/failed",
        ),
        sa.Column(
            "file_path",
            sa.String(length=500),
            nullable=True,
            comment="备份文件相对路径（cleanup 为空；restore 为源备份路径）",
        ),
        sa.Column(
            "file_size_bytes", sa.BigInteger(), nullable=True, comment="备份文件大小（字节）"
        ),
        sa.Column(
            "backup_date",
            sa.Date(),
            nullable=True,
            comment="备份对应业务日期（cleanup 为空；restore 取源备份日期）",
        ),
        sa.Column(
            "retention_check_passed",
            sa.Boolean(),
            nullable=True,
            comment="仅 cleanup：保留窗口内备份校验结果",
        ),
        sa.Column(
            "deleted_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="仅 cleanup：删除文件数",
        ),
        sa.Column("duration_seconds", sa.Integer(), nullable=True, comment="耗时（秒）"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="失败原因/详情"),
        sa.Column("operator_id", sa.Integer(), nullable=True, comment="操作人（定时任务为 NULL）"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True, comment="开始时间"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True, comment="完成时间"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_backup_records_type_date", "backup_records", ["task_type", "backup_date"], unique=False
    )
    op.create_index("idx_backup_records_status", "backup_records", ["status"], unique=False)

    # ---- 3. 权限 system:database_backup + 关联超级管理员角色 ----
    op.bulk_insert(
        sa.table(
            "permissions",
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("description", sa.String),
            sa.column("module", sa.String),
        ),
        [
            {
                "code": "system:database_backup",
                "name": "数据备份",
                "description": "配置定时备份与清理、手动备份、下载备份、恢复备份",
                "module": "system",
            },
        ],
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = '超级管理员' AND p.code = 'system:database_backup'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # 权限回退
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'system:database_backup')"
    )
    op.execute("DELETE FROM permissions WHERE code = 'system:database_backup'")

    op.drop_index("idx_backup_records_status", table_name="backup_records")
    op.drop_index("idx_backup_records_type_date", table_name="backup_records")
    op.drop_table("backup_records")
    op.drop_table("backup_schedule_configs")
