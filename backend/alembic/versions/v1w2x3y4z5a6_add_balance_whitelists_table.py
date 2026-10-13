"""add balance_whitelists table

Revision ID: v1w2x3y4z5a6
Revises: a2b3c4d5e6f7
Create Date: 2026-10-13

新增 balance_whitelists 表：开放平台 /api/v1/balances 接口的白名单客户静态余额配置。
同时插入权限 balance_whitelist:manage。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "v1w2x3y4z5a6"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 balance_whitelists 表
    op.create_table(
        "balance_whitelists",
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("static_balance", sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_balance_whitelists_customer_id"),
        "balance_whitelists",
        ["customer_id"],
        unique=True,
    )

    # 插入权限
    op.bulk_insert(
        sa.table(
            "permissions",
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("description", sa.String),
            sa.column("module", sa.String),
        ),
        [
            {
                "code": "balance_whitelist:manage",
                "name": "管理余额白名单",
                "description": "新增/编辑/移除余额白名单客户",
                "module": "system",
            },
        ],
    )

    # 将新权限关联到超级管理员角色
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = '超级管理员' AND p.code = 'balance_whitelist:manage'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'balance_whitelist:manage')"
    )
    op.execute("DELETE FROM permissions WHERE code = 'balance_whitelist:manage'")
    op.drop_index(op.f("ix_balance_whitelists_customer_id"), table_name="balance_whitelists")
    op.drop_table("balance_whitelists")
