"""add_discount_applied_at_to_invoices

Revision ID: cfeac70bcd04
Revises: 6c04c664b261
Create Date: 2026-07-02 02:01:25.824909

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "cfeac70bcd04"
down_revision: Union[str, None] = "6c04c664b261"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("discount_applied_at", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "discount_applied_at")
