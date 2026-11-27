"""remove vr sales supervisor node

Revision ID: a6b7c8d9e0f1
Revises: m8n9o0p1q2r3
Create Date: 2026-11-20 10:00:00.000000

下线 VR编辑费用结算的「销售主管审批」节点：
- 状态 pending_sales_supervisor 迁移：有减免 → pending_discount_approval（独立减免审批节点），
  无减免 → pending_customer（与销售审批后的正向分流一致）
- 权限 vr_settlement:sales_supervisor_approve 废弃：解除所有角色绑定并删除权限记录
  （无等价新码；减免审批由既有 billing:discount_approve 承担）
- sales_supervisor_confirmed_by/at 列保留为历史数据（不删列，此后无读写）

回滚不可逆：迁移后无法区分「原本 pending_discount_approval/pending_customer」与
由 pending_sales_supervisor 迁移而来的行，且已删除的角色→权限绑定无法重建，
故 downgrade 留空。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, None] = "m8n9o0p1q2r3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 有减免的在途单先进减免审批节点，否则直接待客户确认
    op.execute(
        sa.text(
            """
            UPDATE vr_settlements
            SET status = 'pending_discount_approval'
            WHERE status = 'pending_sales_supervisor'
              AND discount_amount IS NOT NULL
              AND discount_amount <> 0
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE vr_settlements
            SET status = 'pending_customer'
            WHERE status = 'pending_sales_supervisor'
            """
        )
    )

    # 废弃权限码：先解绑角色，再删权限记录
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions
                WHERE code = 'vr_settlement:sales_supervisor_approve'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE code = 'vr_settlement:sales_supervisor_approve'
            """
        )
    )


def downgrade() -> None:
    # 不可逆：无法区分原始 pending_discount_approval / pending_customer 与
    # 由 pending_sales_supervisor 迁移而来的行，且角色→权限绑定已删除，
    # 无法安全回滚，故不执行任何操作。
    pass
