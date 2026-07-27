"""add cooperation_statuses table

Revision ID: g6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-07-27 10:00:00.000000

"""

from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g6b7c8d9e0f1"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # 创建合作状态字典表
    op.create_table(
        "cooperation_statuses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("value", sa.String(length=50), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("value"),
    )

    # 创建索引
    op.create_index("ix_cooperation_statuses_name", "cooperation_statuses", ["name"])
    op.create_index("ix_cooperation_statuses_value", "cooperation_statuses", ["value"])
    op.create_index("ix_cooperation_statuses_sort_order", "cooperation_statuses", ["sort_order"])

    # 插入预置数据
    op.execute(
        """
        INSERT INTO cooperation_statuses (name, value, sort_order, created_at, updated_at) VALUES
            ('合作中', 'active', 1, NOW(), NOW()),
            ('暂停', 'suspended', 2, NOW(), NOW()),
            ('终止', 'terminated', 3, NOW(), NOW()),
            ('近一年未使用', 'noused', 4, NOW(), NOW())
        """
    )


def downgrade() -> None:
    op.drop_index("ix_cooperation_statuses_sort_order", table_name="cooperation_statuses")
    op.drop_index("ix_cooperation_statuses_value", table_name="cooperation_statuses")
    op.drop_index("ix_cooperation_statuses_name", table_name="cooperation_statuses")
    op.drop_table("cooperation_statuses")
