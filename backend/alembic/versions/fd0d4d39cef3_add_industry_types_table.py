"""add industry_types table

Revision ID: fd0d4d39cef3
Revises: 734bdc29cc5e
Create Date: 2026-04-14 16:58:22.427454

"""

from typing import Union, Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "fd0d4d39cef3"
down_revision: Union[str, None] = "734bdc29cc5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "industry_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_industry_types_name"), "industry_types", ["name"], unique=True
    )
    op.create_index(
        op.f("ix_industry_types_sort_order"),
        "industry_types",
        ["sort_order"],
        unique=False,
    )

    # 插入 8 条预置数据
    op.bulk_insert(
        sa.table(
            "industry_types",
            sa.column("id", sa.Integer),
            sa.column("name", sa.String),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {"id": 1, "name": "项目", "sort_order": 1},
            {"id": 2, "name": "房产经纪", "sort_order": 2},
            {"id": 3, "name": "房产ERP", "sort_order": 3},
            {"id": 4, "name": "房产平台", "sort_order": 4},
            {"id": 5, "name": "公共安全", "sort_order": 5},
            {"id": 6, "name": "租房", "sort_order": 6},
            {"id": 7, "name": "待确认", "sort_order": 7},
            {"id": 8, "name": "无", "sort_order": 8},
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_industry_types_sort_order"), table_name="industry_types")
    op.drop_index(op.f("ix_industry_types_name"), table_name="industry_types")
    op.drop_table("industry_types")
