"""add invoice_discount_histories table

Revision ID: q6r7s8t9u0v1
Revises: p5q6r7s8t9u0
Create Date: 2026-09-02

新增结算单减免修改历史表：
- invoice_discount_histories: 记录每次减免修改的完整历史
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "q6r7s8t9u0v1"
down_revision: Union[str, None] = "p5q6r7s8t9u0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invoice_discount_histories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("discount_amount", sa.DECIMAL(12, 2), nullable=False),
        sa.Column("discount_reason", sa.Text(), nullable=True),
        sa.Column("discount_attachment", sa.String(255), nullable=True),
        sa.Column("applied_at", sa.String(50), nullable=False),
        sa.Column("applied_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["applied_by"],
            ["users.id"],
        ),
    )
    op.create_index(
        "idx_discount_history_invoice",
        "invoice_discount_histories",
        ["invoice_id", "applied_at"],
    )
    op.create_index(
        "ix_invoice_discount_histories_invoice_id",
        "invoice_discount_histories",
        ["invoice_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invoice_discount_histories_invoice_id",
        table_name="invoice_discount_histories",
    )
    op.drop_index(
        "idx_discount_history_invoice",
        table_name="invoice_discount_histories",
    )
    op.drop_table("invoice_discount_histories")
