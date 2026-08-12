"""make device_type nullable

Revision ID: j9e0f1g2h3i4
Revises: h7c8d9e0f1g2
Create Date: 2026-08-12

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "j9e0f1g2h3i4"
down_revision = "i8d9e0f1g2h3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 包年结算不需要 device_type，改为可选
    op.alter_column(
        "pricing_rules",
        "device_type",
        existing_type=sa.String(20),
        nullable=True,
    )
    # 包年结算明细不区分设备类型，改为可选
    op.alter_column(
        "invoice_items",
        "device_type",
        existing_type=sa.String(20),
        nullable=True,
    )


def downgrade() -> None:
    # 回滚时恢复为必填
    op.alter_column(
        "pricing_rules",
        "device_type",
        existing_type=sa.String(20),
        nullable=False,
    )
    op.alter_column(
        "invoice_items",
        "device_type",
        existing_type=sa.String(20),
        nullable=False,
    )
