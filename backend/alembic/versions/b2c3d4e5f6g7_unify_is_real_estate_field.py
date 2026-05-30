"""unify is_real_estate field

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-29 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6g7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove is_real_estate from customer_profiles table.

    Steps:
    1. Synchronize data: Copy non-NULL is_real_estate from Profile to Customer where Customer value is NULL
    2. Drop the is_real_estate column from customer_profiles table
    """

    # 1. Synchronize data from customer_profiles to customers (for safety)
    # This ensures no data loss when removing the column from profiles
    # Note: Based on data stats from 2026-05-29, there are 0 inconsistent values
    op.execute(
        """
        UPDATE customers c
        SET is_real_estate = cp.is_real_estate
        FROM customer_profiles cp
        WHERE cp.customer_id = c.id
          AND c.is_real_estate IS NULL
          AND cp.is_real_estate IS NOT NULL
        """
    )

    # 2. Drop the is_real_estate column from customer_profiles table
    op.drop_column("customer_profiles", "is_real_estate")


def downgrade() -> None:
    """Add is_real_estate back to customer_profiles table.

    Note: Cannot restore original data as it has been moved to Customer table.
    """

    # 1. Add the is_real_estate column back to customer_profiles table
    op.add_column(
        "customer_profiles",
        sa.Column("is_real_estate", sa.Boolean(), nullable=True),
    )

    # Note: Data restoration is not possible in downgrade
    # The column will be added with NULL values
