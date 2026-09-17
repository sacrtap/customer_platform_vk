"""add sync execution details and schedule configs

Revision ID: u0v1w2x3y4z5
Revises: t9u0v1w2x3y4
Create Date: 2026-09-17

同步日志执行信息优化：
1. 新增 sync_task_log_details 执行明细表（level: info/warning/error + 客户维度字段），
   用于同步任务执行过程的预警/错误/成功记录数明细，支持按客户ID/名称排查问题。
2. 新增 sync_schedule_configs 定时同步配置表（单行 daily_sync），
   定时任务合并为单个「每日自动同步」并支持页面配置开启/关闭/时间/模式。
3. sync_tasks.operator_id 改为可空：定时任务以「系统自动」触发（operator_id=NULL）。
4. 新增权限 system:sync_schedule（定时同步配置，默认仅超级管理员）并关联超管角色。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "u0v1w2x3y4z5"
down_revision: Union[str, None] = "t9u0v1w2x3y4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- 1. 执行明细表 ----
    op.create_table(
        "sync_task_log_details",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "task_id",
            sa.UUID(),
            sa.ForeignKey("sync_tasks.id", ondelete="CASCADE"),
            nullable=False,
            comment="任务ID",
        ),
        sa.Column("sync_date", sa.Date(), nullable=False, comment="明细所属同步日期"),
        sa.Column(
            "level", sa.String(length=10), nullable=False, comment="级别: info/warning/error"
        ),
        sa.Column(
            "category",
            sa.String(length=30),
            nullable=False,
            comment="类别: order_fetch/order_match/order_save/cost_calc/data_check/system",
        ),
        sa.Column("message", sa.Text(), nullable=False, comment="描述信息"),
        sa.Column("customer_id", sa.Integer(), nullable=True, comment="内部客户ID"),
        sa.Column("customer_name", sa.String(length=200), nullable=True, comment="内部客户名称"),
        sa.Column(
            "external_customer_id",
            sa.String(length=50),
            nullable=True,
            comment="外部客户ID(group_type)",
        ),
        sa.Column("company_name", sa.String(length=200), nullable=True, comment="外部公司名"),
        sa.Column("order_code", sa.String(length=50), nullable=True, comment="订单号"),
        sa.Column(
            "record_count",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="聚合记录数（成功按客户+日期聚合时>1）",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_sync_detail_task_level", "sync_task_log_details", ["task_id", "level"], unique=False
    )
    op.create_index(
        "idx_sync_detail_task_date", "sync_task_log_details", ["task_id", "sync_date"], unique=False
    )

    # ---- 2. 定时同步配置表 + 默认行 ----
    op.create_table(
        "sync_schedule_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "task_name",
            sa.String(length=50),
            nullable=False,
            comment="任务名称（预留多任务扩展）",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="是否启用",
        ),
        sa.Column(
            "sync_time",
            sa.String(length=5),
            server_default="01:00",
            nullable=False,
            comment="执行时间 HH:MM",
        ),
        sa.Column(
            "sync_mode",
            sa.String(length=20),
            server_default="skip_existing",
            nullable=False,
            comment="同步模式: skip_existing/force_overwrite",
        ),
        sa.Column("updated_by", sa.Integer(), nullable=True, comment="更新人"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_name"),
    )
    op.bulk_insert(
        sa.table(
            "sync_schedule_configs",
            sa.column("task_name", sa.String),
            sa.column("enabled", sa.Boolean),
            sa.column("sync_time", sa.String),
            sa.column("sync_mode", sa.String),
        ),
        [
            {
                "task_name": "daily_sync",
                "enabled": False,
                "sync_time": "01:00",
                "sync_mode": "skip_existing",
            },
        ],
    )

    # ---- 3. sync_tasks.operator_id 改为可空（定时任务以系统触发） ----
    op.alter_column("sync_tasks", "operator_id", existing_type=sa.Integer(), nullable=True)

    # ---- 4. 权限 system:sync_schedule + 关联超级管理员角色 ----
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
                "code": "system:sync_schedule",
                "name": "配置定时同步",
                "description": "配置每日自动同步（开启/关闭/时间/模式）",
                "module": "system",
            },
        ],
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = '超级管理员' AND p.code = 'system:sync_schedule'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # 权限回退
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'system:sync_schedule')"
    )
    op.execute("DELETE FROM permissions WHERE code = 'system:sync_schedule'")

    # operator_id 恢复 NOT NULL 前需确认无 NULL 行（定时任务未启用时均非空）
    op.alter_column("sync_tasks", "operator_id", existing_type=sa.Integer(), nullable=False)

    op.drop_table("sync_schedule_configs")
    op.drop_index("idx_sync_detail_task_date", table_name="sync_task_log_details")
    op.drop_index("idx_sync_detail_task_level", table_name="sync_task_log_details")
    op.drop_table("sync_task_log_details")
