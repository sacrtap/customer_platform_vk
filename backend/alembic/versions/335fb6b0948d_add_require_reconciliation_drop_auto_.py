"""add require_reconciliation drop auto_initiate_settlement

Revision ID: 335fb6b0948d
Revises: z5a6b7c8d9e0
Create Date: 2026-10-23 10:12:06.280539

客户管理新增「是否对账」属性，移除死字段「自动发起结算」：
- customers.require_reconciliation（Boolean, nullable, server_default=false）：
  NULL/False=否（结算单 submit 跳过经理确认直达 pending_customer）；
  True=是（走完整确认流程，且保存客户时强制经理非空）。
- 删除 customers.auto_initiate_settlement（死字段，所有结算业务逻辑均不读取）。
历史行迁移后 require_reconciliation 均为 False（否），符合「所有客户默认否」。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "335fb6b0948d"
down_revision: Union[str, None] = "z5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column(
            "require_reconciliation",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
            comment="是否对账（NULL/False=否，跳过经理确认；True=是，走完整确认流程并强制经理非空）",
        ),
    )
    op.drop_column("customers", "auto_initiate_settlement")


def downgrade() -> None:
    op.add_column(
        "customers",
        sa.Column(
            "auto_initiate_settlement",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("true"),
            comment="是否自动发起结算（NULL 视为是）",
        ),
    )
    op.drop_column("customers", "require_reconciliation")
