"""add multi-floor pricing fields and total_floor_count

Revision ID: h7c8d9e0f1g2
Revises: g6b7c8d9e0f1
Create Date: 2026-08-06 10:00:00.000000

新增多层计费相关字段：
- pricing_rules.multi_floor_pricing_type: 多层计费类型 (unified/incremental)
- pricing_rules.additional_floor_price: 其他层单价（递增模式下使用）
- daily_consumptions.total_floor_count: 总楼层数（供结算单计算使用）

"""

from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h7c8d9e0f1g2"
down_revision: Union[str, None] = "g6b7c8d9e0f1"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # pricing_rules 新增多层计费类型字段
    op.add_column(
        "pricing_rules",
        sa.Column("multi_floor_pricing_type", sa.String(length=20), nullable=True),
    )
    # pricing_rules 新增其他层单价字段
    op.add_column(
        "pricing_rules",
        sa.Column("additional_floor_price", sa.Numeric(precision=10, scale=2), nullable=True),
    )

    # daily_consumptions 新增总楼层数字段
    op.add_column(
        "daily_consumptions",
        sa.Column("total_floor_count", sa.Integer(), nullable=True, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("daily_consumptions", "total_floor_count")
    op.drop_column("pricing_rules", "additional_floor_price")
    op.drop_column("pricing_rules", "multi_floor_pricing_type")
