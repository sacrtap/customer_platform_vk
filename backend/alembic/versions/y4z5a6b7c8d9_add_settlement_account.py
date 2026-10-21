"""add settlement account fields to customers and invoices

Revision ID: y4z5a6b7c8d9
Revises: x3y4z5a6b7c8
Create Date: 2026-10-21 10:00:00.000000

客户代扣结算（结算账户）：
- customers.settlement_account_id (Integer, nullable, 自引用 FK)：客户级结算账户配置，
  NULL=用自身余额结算，非空=用所选客户的 CustomerBalance 扣款
- invoices.settlement_account_id (Integer, nullable, FK)：生成结算单时从客户配置快照，
  扣款按快照执行；审批流中可在结算单详情修改

历史行新增列后为 NULL，语义为「用自身余额」，无需 backfill。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "y4z5a6b7c8d9"
down_revision: Union[str, None] = "x3y4z5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column(
            "settlement_account_id",
            sa.Integer(),
            nullable=True,
            comment="结算账户客户ID，NULL=用自身余额结算",
        ),
    )
    op.create_index(
        op.f("ix_customers_settlement_account_id"),
        "customers",
        ["settlement_account_id"],
        unique=False,
    )
    op.add_column(
        "invoices",
        sa.Column(
            "settlement_account_id",
            sa.Integer(),
            nullable=True,
            comment="结算账户客户ID（生成时快照），NULL=用自身余额扣款",
        ),
    )
    op.create_index(
        op.f("ix_invoices_settlement_account_id"),
        "invoices",
        ["settlement_account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_invoices_settlement_account_id"), table_name="invoices")
    op.drop_column("invoices", "settlement_account_id")
    op.drop_index(op.f("ix_customers_settlement_account_id"), table_name="customers")
    op.drop_column("customers", "settlement_account_id")
