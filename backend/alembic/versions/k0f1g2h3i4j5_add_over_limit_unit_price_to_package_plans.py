"""add over_limit_unit_price to package_plans

Revision ID: k0f1g2h3i4j5
Revises: j9e0f1g2h3i4
Create Date: 2026-08-18

新增 package_plans.over_limit_unit_price 字段，用于限量套餐超出
limit_count 后的每单位用量价格。默认为 base_fee / limit_count。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "k0f1g2h3i4j5"
down_revision: Union[str, None] = "j9e0f1g2h3i4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "package_plans",
        sa.Column(
            "over_limit_unit_price",
            sa.DECIMAL(10, 2),
            nullable=True,
            comment="超额单价（限量套餐超出 limit_count 后的每单位用量价格）",
        ),
    )


def downgrade() -> None:
    op.drop_column("package_plans", "over_limit_unit_price")
