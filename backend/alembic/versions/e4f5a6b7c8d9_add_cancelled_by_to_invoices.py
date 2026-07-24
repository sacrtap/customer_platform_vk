"""add cancelled_by to invoices

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-07-20

新增 invoices.cancelled_by 列，记录取消结算单的操作人。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "cancelled_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
            comment="取消操作人",
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "cancelled_by")
