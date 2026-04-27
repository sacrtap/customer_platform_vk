"""add layer_type to pricing_rules

Revision ID: 006_layer_type
Revises: 288fbca5e3ed
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "006_layer_type"
down_revision = "288fbca5e3ed"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pricing_rules", sa.Column("layer_type", sa.String(20), nullable=True))


def downgrade():
    op.drop_column("pricing_rules", "layer_type")
