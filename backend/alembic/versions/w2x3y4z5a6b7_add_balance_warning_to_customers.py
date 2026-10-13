"""add balance warning fields to customers

Revision ID: w2x3y4z5a6b7
Revises: v1w2x3y4z5a6
Create Date: 2026-10-13 15:30:00.000000

P6-4 余额预警检查：
customers 新增余额预警状态字段，供 check_balance_warning 定时任务每小时维护。

- balance_warning_level (String(20), nullable, 索引)：预警级别 warning/critical，NULL 表示正常
- balance_warning_updated_at (DateTime, nullable)：预警状态最近更新时间

历史行新增列后为 NULL，语义为「正常」。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "w2x3y4z5a6b7"
down_revision: Union[str, None] = "v1w2x3y4z5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column(
            "balance_warning_level",
            sa.String(length=20),
            nullable=True,
            comment="余额预警级别 warning/critical，NULL 为正常",
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "balance_warning_updated_at",
            sa.DateTime(),
            nullable=True,
            comment="余额预警状态最近更新时间",
        ),
    )
    op.create_index(
        op.f("ix_customers_balance_warning_level"),
        "customers",
        ["balance_warning_level"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_customers_balance_warning_level"), table_name="customers")
    op.drop_column("customers", "balance_warning_updated_at")
    op.drop_column("customers", "balance_warning_level")
