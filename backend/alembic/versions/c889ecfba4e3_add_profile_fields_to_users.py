"""add profile fields to users table

Revision ID: c889ecfba4e3
Revises: ce46b7a9d7bc
Create Date: 2026-05-13 01:12:25.761774

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = 'c889ecfba4e3'
down_revision: Union[str, None] = 'ce46b7a9d7bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('phone', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'phone')
