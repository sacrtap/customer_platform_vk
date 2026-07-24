"""add package_plans table

Revision ID: d3e4f5a6b7c8
Revises: a7b8c9d0e1f2
Create Date: 2026-07-20

新增包年套餐表 package_plans，管理包年结算的套餐明细。
支持"限量"和"不限量"两种模式，与 PricingRule.package_type 通过
package_type 字段关联。

注意：此迁移替代了原 backend/migrations/versions/005_add_package_plans.py
脚本。如果数据库中已存在 package_plans 表（因误执行 005 脚本），
本迁移会自动跳过建表操作（幂等）。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 幂等处理：如果表已存在（曾误执行 005 脚本），则跳过建表
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "package_plans" in inspector.get_table_names():
        return

    op.create_table(
        "package_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, comment="套餐名称"),
        sa.Column(
            "package_type",
            sa.String(length=20),
            nullable=False,
            comment="套餐类型标识",
        ),
        sa.Column(
            "device_type",
            sa.String(length=20),
            nullable=True,
            comment="设备类型 (X/N/L)，为空表示通用",
        ),
        sa.Column(
            "layer_type",
            sa.String(length=20),
            nullable=True,
            comment="楼层类型 (single/multi)，为空表示通用",
        ),
        sa.Column(
            "is_unlimited",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="是否不限量：true=不限量，false=限量",
        ),
        sa.Column(
            "limit_count",
            sa.Integer(),
            nullable=True,
            comment="限量数量（is_unlimited=false 时必填，否则为空）",
        ),
        sa.Column(
            "base_fee",
            sa.DECIMAL(precision=12, scale=2),
            nullable=False,
            comment="套餐基础费用（年费）",
        ),
        sa.Column("description", sa.Text(), nullable=True, comment="套餐描述"),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
            comment="状态：active/inactive",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("package_type", name="uq_package_plans_package_type"),
    )
    op.create_index("ix_package_plans_package_type", "package_plans", ["package_type"])
    op.create_index("ix_package_plans_status", "package_plans", ["status"])


def downgrade() -> None:
    op.drop_index("ix_package_plans_status", table_name="package_plans")
    op.drop_index("ix_package_plans_package_type", table_name="package_plans")
    op.drop_table("package_plans")
