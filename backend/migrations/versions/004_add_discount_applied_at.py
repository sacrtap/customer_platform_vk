"""add discount_applied_at to invoices

Revision ID: 004
Revises: 003
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    # 添加折扣申请时间字段
    op.add_column('invoices', sa.Column('discount_applied_at', sa.String(50), nullable=True))


def downgrade():
    op.drop_column('invoices', 'discount_applied_at')
