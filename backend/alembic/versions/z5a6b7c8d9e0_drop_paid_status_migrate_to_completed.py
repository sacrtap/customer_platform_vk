"""drop paid status migrate to completed

Revision ID: z5a6b7c8d9e0
Revises: y4z5a6b7c8d9
Create Date: 2026-10-23 10:00:00.000000

废弃 paid 旧流程：
- InvoiceStatus.PAID 枚举与 pay/complete 路由、billing:pay 权限已从代码中移除
- 存量 status='paid' 行迁移为 'completed'，回填完成时间/操作人：
  completed_at 缺省时用 paid_at，completed_by 缺省时用 customer_confirmed_by
- paid_at 列保留为外部支付凭证字段（webhook 仍写入），不删列

回滚不可逆：迁移后无法区分「原本 completed」与「paid 迁移而来」，
故 downgrade 留空。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "z5a6b7c8d9e0"
down_revision: Union[str, None] = "y4z5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE invoices
            SET status = 'completed',
                completed_at = COALESCE(completed_at, paid_at),
                completed_by = COALESCE(completed_by, customer_confirmed_by)
            WHERE status = 'paid'
            """
        )
    )


def downgrade() -> None:
    # 不可逆：迁移后无法区分原始 completed 与由 paid 迁移而来的行，
    # 无法安全回滚，故不执行任何操作。
    pass
