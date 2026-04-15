"""drop customers.business_type, use customer_profiles.industry

Revision ID: 004
Revises: 003
Create Date: 2026-04-15
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: 确保所有客户都有 customer_profiles 记录
    # 为没有 profile 的客户创建空 profile
    op.execute(
        """
        INSERT INTO customer_profiles (customer_id, created_at, updated_at)
        SELECT c.id, NOW(), NOW()
        FROM customers c
        LEFT JOIN customer_profiles cp ON c.id = cp.customer_id
        WHERE cp.id IS NULL AND c.deleted_at IS NULL
        """
    )

    # Step 2: 删除 idx_customer_business_settlement 索引
    op.drop_index("idx_customer_business_settlement", table_name="customers")

    # Step 3: 删除 customers.business_type 列
    op.drop_column("customers", "business_type")


def downgrade() -> None:
    # Step 1: 重新添加 business_type 列
    op.add_column(
        "customers",
        sa.Column("business_type", sa.String(length=50), nullable=True),
    )

    # Step 2: 重新创建索引
    op.create_index(
        "idx_customer_business_settlement",
        "customers",
        ["business_type", "settlement_type"],
        unique=False,
    )
