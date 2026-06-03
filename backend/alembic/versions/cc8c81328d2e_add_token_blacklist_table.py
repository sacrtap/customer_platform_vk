"""add token_blacklist table

Revision ID: cc8c81328d2e
Revises: 05c6bedcf166
Create Date: 2026-05-09 14:07:51.669630

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "cc8c81328d2e"
down_revision: Union[str, None] = "05c6bedcf166"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "token_blacklist",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("jti", sa.String(length=100), nullable=False),
        sa.Column("token_type", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blacklisted_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti"),
    )
    op.create_index("idx_token_blacklist_jti", "token_blacklist", ["jti"], unique=False)
    op.create_index("idx_token_blacklist_expires", "token_blacklist", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_token_blacklist_expires", table_name="token_blacklist")
    op.drop_index("idx_token_blacklist_jti", table_name="token_blacklist")
    op.drop_table("token_blacklist")
