"""add invoice item multi floor freeze

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-11-10

结算单明细多层计费冻结快照：
invoice_items 新增 multi_floor_pricing_type / additional_floor_price 两列，均可空、不回填。

背景：detail_generator 原通过 outerjoin(PricingRule) 读取多层计费字段，规则变更后
已生成结算单的明细文件/详情展示会漂移；且 invoice_items 落库时丢弃 pricing_rule_id
导致 join 恒落空（「计费明细」两列恒空，金额不可验算）。
改为落库时冻结两列（与 subtotal/order_count 同批不回填），展示层 NULL 兜底。
历史行两列为 NULL，行为与现状一致。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "g2h3i4j5k6l7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoice_items",
        sa.Column(
            "multi_floor_pricing_type",
            sa.String(20),
            nullable=True,
            comment="多层计费类型冻结快照（incremental/unified）",
        ),
    )
    op.add_column(
        "invoice_items",
        sa.Column(
            "additional_floor_price",
            sa.DECIMAL(10, 2),
            nullable=True,
            comment="附加层单价冻结快照（多层递增第二层起）",
        ),
    )


def downgrade() -> None:
    op.drop_column("invoice_items", "additional_floor_price")
    op.drop_column("invoice_items", "multi_floor_pricing_type")
