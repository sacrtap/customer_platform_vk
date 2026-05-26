"""add is_real_estate to customers

Revision ID: a1b2c3d4e5f6
Revises: c889ecfba4e3
Create Date: 2026-05-26 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c889ecfba4e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add nullable is_real_estate column to customers table
    op.add_column(
        "customers",
        sa.Column("is_real_estate", sa.Boolean(), nullable=True),
    )

    # 2. Copy existing data from customer_profiles.is_real_estate to customers.is_real_estate
    op.execute(
        """
        UPDATE customers c
        SET is_real_estate = cp.is_real_estate
        FROM customer_profiles cp
        WHERE cp.customer_id = c.id
        """
    )


def downgrade() -> None:
    op.drop_column("customers", "is_real_estate")
