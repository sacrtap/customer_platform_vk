"""add invoice multi-role approval fields and permissions

Revision ID: a7b8c9d0e1f2
Revises: cfeac70bcd04
Create Date: 2026-07-18

新增结算单多角色协作确认字段：
- ops_confirmed_by / ops_confirmed_at（运营经理确认）
- sales_confirmed_by / sales_confirmed_at（销售经理确认）

新增权限：
- billing:ops_approve（运营经理确认）
- billing:sales_approve（销售经理确认）

注意：权限和角色的插入使用幂等 INSERT ... ON CONFLICT DO NOTHING，
      可重复执行不会报错。需在迁移后运行 `python scripts/seed.py` 来
      创建预置的「运营经理」「销售经理」角色并关联权限。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "cfeac70bcd04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. invoices 表新增多角色确认追踪字段
    op.add_column(
        "invoices",
        sa.Column(
            "ops_confirmed_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
            comment="运营经理确认人",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "ops_confirmed_at",
            sa.String(length=50),
            nullable=True,
            comment="运营经理确认时间",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "sales_confirmed_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
            comment="销售经理确认人",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "sales_confirmed_at",
            sa.String(length=50),
            nullable=True,
            comment="销售经理确认时间",
        ),
    )

    # 2. 插入新权限（幂等，使用 ON CONFLICT DO NOTHING）
    op.execute(
        """
        INSERT INTO permissions (code, name, description, module, created_at, updated_at)
        VALUES
            ('billing:ops_approve', '运营经理确认', '运营经理确认结算单（第一步）', 'billing', now(), now()),
            ('billing:sales_approve', '销售经理确认', '销售经理确认结算单（第二步）', 'billing', now(), now())
        ON CONFLICT (code) DO NOTHING
        """
    )

    # 3. 为超级管理员角色关联新权限（幂等）
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = '超级管理员'
          AND p.code IN ('billing:ops_approve', 'billing:sales_approve')
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          )
        """
    )


def downgrade() -> None:
    # 1. 移除新权限与角色的关联
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE code IN ('billing:ops_approve', 'billing:sales_approve')
        )
        """
    )
    # 2. 删除新权限
    op.execute(
        """
        DELETE FROM permissions WHERE code IN ('billing:ops_approve', 'billing:sales_approve')
        """
    )
    # 3. 删除 invoices 表新增字段
    op.drop_column("invoices", "sales_confirmed_at")
    op.drop_column("invoices", "sales_confirmed_by")
    op.drop_column("invoices", "ops_confirmed_at")
    op.drop_column("invoices", "ops_confirmed_by")
