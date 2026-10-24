"""add discount approval fields to invoices

Revision ID: b8c9d0e1f2a3
Revises: 335fb6b0948d
Create Date: 2026-10-24 10:00:00.000000

减免审批节点：
- invoices.discount_approver_id (Integer, nullable, FK users.id)：减免审批人
- invoices.discount_approved_at (String(50), nullable)：减免审批时间
- invoices.discount_approval_comment (Text, nullable)：审批意见/驳回理由
- invoices.status 列宽 String(20) → String(30)：新状态值 pending_discount_approval
  为 25 字符，超出原 20 字符限制（DB 层 StringDataRightTruncationError）

历史行新增列后为 NULL，语义为「未发生减免审批」。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "335fb6b0948d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "discount_approver_id",
            sa.Integer(),
            nullable=True,
            comment="减免审批人",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "discount_approved_at",
            sa.String(50),
            nullable=True,
            comment="减免审批时间",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "discount_approval_comment",
            sa.Text(),
            nullable=True,
            comment="审批意见/驳回理由",
        ),
    )
    op.create_foreign_key(
        "fk_invoices_discount_approver_id",
        "invoices",
        "users",
        ["discount_approver_id"],
        ["id"],
    )
    # 新状态值 pending_discount_approval（25 字符）超出 String(20) 限制
    op.alter_column(
        "invoices",
        "status",
        existing_type=sa.String(20),
        type_=sa.String(30),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "invoices",
        "status",
        existing_type=sa.String(30),
        type_=sa.String(20),
        existing_nullable=True,
    )
    op.drop_constraint("fk_invoices_discount_approver_id", "invoices", type_="foreignkey")
    op.drop_column("invoices", "discount_approval_comment")
    op.drop_column("invoices", "discount_approved_at")
    op.drop_column("invoices", "discount_approver_id")
