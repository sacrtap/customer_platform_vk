"""add remark to balance_whitelists

Revision ID: x3y4z5a6b7c8
Revises: w2x3y4z5a6b7
Create Date: 2026-10-13

余额白名单新增备注字段：

- remark (String(200), nullable)：白名单静态余额的业务备注；NULL 表示无备注。
  历史行迁移后为 NULL，语义为「无备注」。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "x3y4z5a6b7c8"
down_revision: Union[str, None] = "w2x3y4z5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "balance_whitelists",
        sa.Column(
            "remark",
            sa.String(length=200),
            nullable=True,
            comment="备注（最长 200 字符）",
        ),
    )


def downgrade() -> None:
    op.drop_column("balance_whitelists", "remark")
