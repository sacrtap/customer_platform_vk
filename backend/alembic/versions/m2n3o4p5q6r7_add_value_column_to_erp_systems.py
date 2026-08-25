"""add value column to erp_systems

Revision ID: m2n3o4p5q6r7
Revises: l1m2n3o4p5q6
Create Date: 2026-08-25

为 erp_systems 表添加 value 列（之前表已存在但缺少此列）。
将现有 name 值复制到 value 作为初始值。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "m2n3o4p5q6r7"
down_revision: Union[str, None] = "l1m2n3o4p5q6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 value 列（先允许 NULL，回填后再设为 NOT NULL）
    op.add_column("erp_systems", sa.Column("value", sa.String(length=100), nullable=True))

    # 回填：将现有 name 复制到 value
    op.execute("UPDATE erp_systems SET value = name WHERE value IS NULL")

    # 设置 NOT NULL 约束
    op.alter_column("erp_systems", "value", nullable=False)

    # 创建唯一索引
    op.create_index(op.f("ix_erp_systems_value"), "erp_systems", ["value"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_erp_systems_value"), table_name="erp_systems")
    op.drop_column("erp_systems", "value")
