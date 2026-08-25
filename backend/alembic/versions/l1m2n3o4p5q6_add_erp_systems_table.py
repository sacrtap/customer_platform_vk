"""add erp_systems table

Revision ID: l1m2n3o4p5q6
Revises: k0f1g2h3i4j5
Create Date: 2026-08-25

新增 erp_systems 字典表，用于管理客户关联的 ERP 系统类型。
同时插入权限 erp_systems:manage。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "l1m2n3o4p5q6"
down_revision: Union[str, None] = "k0f1g2h3i4j5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 erp_systems 表
    op.create_table(
        "erp_systems",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_erp_systems_name"), "erp_systems", ["name"], unique=True)
    op.create_index(op.f("ix_erp_systems_value"), "erp_systems", ["value"], unique=True)
    op.create_index(op.f("ix_erp_systems_sort_order"), "erp_systems", ["sort_order"], unique=False)

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
                "code": "erp_systems:manage",
                "name": "管理ERP系统",
                "description": "新增/编辑/删除ERP系统",
                "module": "system",
            },
        ],
    )

    # 插入种子数据
    op.bulk_insert(
        sa.table(
            "erp_systems",
            sa.column("name", sa.String),
            sa.column("value", sa.String),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {"name": "ERP云", "value": "erp_cloud", "sort_order": 1},
            {"name": "ERP本地", "value": "erp_local", "sort_order": 2},
            {"name": "无ERP", "value": "none", "sort_order": 3},
        ],
    )

    # 将新权限关联到超级管理员角色
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = '超级管理员' AND p.code = 'erp_systems:manage'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'erp_systems:manage')"
    )
    op.execute("DELETE FROM permissions WHERE code = 'erp_systems:manage'")
    op.drop_index(op.f("ix_erp_systems_sort_order"), table_name="erp_systems")
    op.drop_index(op.f("ix_erp_systems_value"), table_name="erp_systems")
    op.drop_index(op.f("ix_erp_systems_name"), table_name="erp_systems")
    op.drop_table("erp_systems")
