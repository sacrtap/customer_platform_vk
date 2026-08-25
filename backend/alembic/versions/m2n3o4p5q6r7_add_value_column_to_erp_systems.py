"""add value column to erp_systems

Revision ID: m2n3o4p5q6r7
Revises: l1m2n3o4p5q6
Create Date: 2026-08-25

为 erp_systems 表添加 value 列（之前表已存在但缺少此列）。
将现有 name 值复制到 value 作为初始值。

注意：l1m2n3o4p5q6 迁移在创建 erp_systems 表时已包含 value 列，
此迁移为兼容本地已存在旧表（无 value 列）而保留，对全新数据库为 no-op。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "m2n3o4p5q6r7"
down_revision: Union[str, None] = "l1m2n3o4p5q6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 检查 value 列是否已存在（全新数据库中 l1m2n3o4p5q6 已包含此列）
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'erp_systems' AND column_name = 'value'"
        )
    )
    if result.fetchone() is not None:
        # value 列已存在，跳过
        return

    # 添加 value 列（先允许 NULL，回填后再设为 NOT NULL）
    op.add_column("erp_systems", sa.Column("value", sa.String(length=100), nullable=True))

    # 回填：将现有 name 复制到 value
    op.execute("UPDATE erp_systems SET value = name WHERE value IS NULL")

    # 设置 NOT NULL 约束
    op.alter_column("erp_systems", "value", nullable=False)

    # 创建唯一索引
    op.create_index(op.f("ix_erp_systems_value"), "erp_systems", ["value"], unique=True)


def downgrade() -> None:
    # 仅在 value 列存在时才删除
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'erp_systems' AND column_name = 'value'"
        )
    )
    if result.fetchone() is None:
        return

    op.drop_index(op.f("ix_erp_systems_value"), table_name="erp_systems")
    op.drop_column("erp_systems", "value")
