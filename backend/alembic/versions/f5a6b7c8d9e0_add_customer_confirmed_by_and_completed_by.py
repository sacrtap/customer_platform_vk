"""add customer_confirmed_by and completed_by to invoices

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-07-24

新增 invoices.customer_confirmed_by 和 invoices.completed_by 列，
分别记录客户确认和完成结算的操作人。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "customer_confirmed_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
            comment="客户确认操作人",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "completed_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
            comment="完成结算操作人",
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "completed_by")
    op.drop_column("invoices", "customer_confirmed_by")
