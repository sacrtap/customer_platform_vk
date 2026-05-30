"""add industry_type foreign key

Revision ID: ce46b7a9d7bc
Revises: 8f6a04467a12
Create Date: 2026-05-11 23:47:50.297490

"""

from typing import Union, Sequence
from alembic import op
import sqlalchemy as sa


revision: str = "ce46b7a9d7bc"
down_revision: Union[str, None] = "8f6a04467a12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: 新增 industry_type_id 列（允许 NULL）
    op.add_column("customer_profiles", sa.Column("industry_type_id", sa.Integer(), nullable=True))

    # Step 2: 数据回填 - 根据 industry 名称匹配 industry_types.id
    op.execute("""
        UPDATE customer_profiles cp
        SET industry_type_id = it.id
        FROM industry_types it
        WHERE cp.industry = it.name
    """)

    # Step 3: 添加外键约束（ON DELETE SET NULL）
    op.create_foreign_key(
        "fk_customer_profiles_industry_type",
        "customer_profiles",
        "industry_types",
        ["industry_type_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Step 4: 删除旧的 industry 列
    op.drop_column("customer_profiles", "industry")


def downgrade() -> None:
    # 反向操作：恢复 industry 列，从 industry_types 回填名称
    op.add_column("customer_profiles", sa.Column("industry", sa.String(length=100), nullable=True))
    op.execute("""
        UPDATE customer_profiles cp
        SET industry = it.name
        FROM industry_types it
        WHERE cp.industry_type_id = it.id
    """)
    op.drop_constraint(
        "fk_customer_profiles_industry_type", "customer_profiles", type_="foreignkey"
    )
    op.drop_column("customer_profiles", "industry_type_id")
