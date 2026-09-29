"""add auto initiate settlement field

Revision ID: a2b3c4d5e6f7
Revises: u0v1w2x3y4z5
Create Date: 2026-09-29 13:05:38.467494

客户管理新增「自动发起结算」属性：
customers.auto_initiate_settlement（Boolean, nullable, 默认 True = 是）。
历史行新增列后为 NULL，语义视为「是」（与 is_settlement_enabled 的 NULL 处理一致）。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "u0v1w2x3y4z5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column(
            "auto_initiate_settlement",
            sa.Boolean(),
            nullable=True,
            comment="是否自动发起结算（NULL 视为是）",
        ),
    )


def downgrade() -> None:
    op.drop_column("customers", "auto_initiate_settlement")
