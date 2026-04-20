"""merge heads

Revision ID: dc8859579c78
Revises: b0ec7f3a8b31, fd0d4d39cef3
Create Date: 2026-04-21 00:44:42.879999

"""
from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence


revision: str = 'dc8859579c78'
down_revision: Union[str, None] = ('b0ec7f3a8b31', 'fd0d4d39cef3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
