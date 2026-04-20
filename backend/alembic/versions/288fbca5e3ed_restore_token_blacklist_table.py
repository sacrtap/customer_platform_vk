"""restore token_blacklist table

Revision ID: 288fbca5e3ed
Revises: dd4170648c62
Create Date: 2026-04-21 01:14:21.748041

"""
from typing import Union, Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '288fbca5e3ed'
down_revision: Union[str, None] = 'dd4170648c62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('token_blacklist',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('jti', sa.String(length=100), nullable=False),
        sa.Column('token_type', sa.String(length=20), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('blacklisted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name='token_blacklist_pkey')
    )
    op.create_index('ix_token_blacklist_jti', 'token_blacklist', ['jti'], unique=True)
    op.create_index('idx_token_blacklist_jti', 'token_blacklist', ['jti'], unique=False)
    op.create_index('idx_token_blacklist_expires', 'token_blacklist', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_token_blacklist_expires', table_name='token_blacklist')
    op.drop_index('idx_token_blacklist_jti', table_name='token_blacklist')
    op.drop_index('ix_token_blacklist_jti', table_name='token_blacklist')
    op.drop_table('token_blacklist')
