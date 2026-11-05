"""add invoice item subtotal order count

Revision ID: f1a2b3c4d5e6
Revises: e2f3a4b5c6d7
Create Date: 2026-11-05

结算单明细数据一致性修复（F3）：
invoice_items 新增 subtotal / order_count 两列，均可空、不回填。

背景：InvoiceItem 原只存 quantity/unit_price，多层递增（incremental）模式下
真实小计 = order_count × unit_price + (quantity − order_count) × additional_floor_price，
明细层以 quantity × unit_price 重算会与 invoices.total_amount 不符。
历史行两列为 NULL，展示层 COALESCE(subtotal, quantity*unit_price)、
order_count ?? quantity 兜底，历史文件行为不变。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoice_items",
        sa.Column(
            "subtotal",
            sa.DECIMAL(12, 2),
            nullable=True,
            comment="真实小计（多层递增/阶梯/包年下 ≠ quantity×unit_price）",
        ),
    )
    op.add_column(
        "invoice_items",
        sa.Column(
            "order_count",
            sa.Integer(),
            nullable=True,
            comment="计费订单数（多层递增时 quantity 为层数，需此列还原单数）",
        ),
    )


def downgrade() -> None:
    op.drop_column("invoice_items", "order_count")
    op.drop_column("invoice_items", "subtotal")
