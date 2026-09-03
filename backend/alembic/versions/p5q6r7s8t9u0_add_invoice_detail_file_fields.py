"""add invoice detail file fields

Revision ID: p5q6r7s8t9u0
Revises: o4p5q6r7s8t9
Create Date: 2026-09-02

新增结算单明细文件字段：
- detail_file_path: 生成的 Excel 文件路径
- detail_file_status: 文件生成状态 (pending/generating/completed/failed)
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "p5q6r7s8t9u0"
down_revision: Union[str, None] = "o4p5q6r7s8t9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("detail_file_path", sa.String(255), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "detail_file_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "detail_file_status")
    op.drop_column("invoices", "detail_file_path")
