"""add daily order nest created
Revision ID: j5k6l7m8n9
Revises: f1a2b3c4d5e6
Create Date: 2026-11-10
结算单明细「处理完成时间」取数改造：
daily_orders 新增 nest_created 一列（timestamptz，可空，不回填）。

背景：明细文件「处理完成时间」原取 daily_orders.finish_date，该列在外部
数据中恒为 NULL，示例表真实口径是房源主表 nest.created。同步层新增
LEFT JOIN nest 读取 created 落库。

历史行两列为 NULL：新生成的明细文件对应行「处理完成时间」为空——
即回填改造前的行为（finish_date 本就为空），不构成回退；存量明细文件
内容不变。需要历史单重出明细时跑 backfill/patch_backfill_remain.py（已
扩展该列的回填）后重新生成。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "j5k6l7m8n9"
down_revision: Union[str, None] = "i4j5k6l7m8n9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "daily_orders",
        sa.Column(
            "nest_created",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="处理完成时间(外部 nest.created)",
        ),
    )


def downgrade() -> None:
    op.drop_column("daily_orders", "nest_created")
