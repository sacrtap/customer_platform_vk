"""add vr settlements

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-11-03

VR编辑费用结算模块：
1. 新增 vr_settlements 表（VR编辑费用结算单主表）
2. 新增 vr_settlement_discount_histories 表（减免修改历史）
3. consumption_records 新增 vr_settlement_id 外键列（关联 VR 扣款消耗记录）
4. 新增 8 个 vr_settlement:* 权限码并关联超级管理员（幂等）

状态机：draft → pending_cs_supervisor → pending_sales → pending_sales_supervisor
→ pending_customer → customer_confirmed → completed；任意非终态可 cancelled。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- 1. VR结算单主表 ----
    op.create_table(
        "vr_settlements",
        sa.Column("settlement_no", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_amount", sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column("discount_amount", sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column("discount_reason", sa.Text(), nullable=True),
        sa.Column("discount_attachment", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("discount_applied_at", sa.String(length=50), nullable=True),
        sa.Column("discount_approver_id", sa.Integer(), nullable=True),
        sa.Column("discount_approved_at", sa.String(length=50), nullable=True),
        sa.Column("discount_approval_comment", sa.Text(), nullable=True),
        sa.Column("cs_supervisor_confirmed_by", sa.Integer(), nullable=True),
        sa.Column("cs_supervisor_confirmed_at", sa.String(length=50), nullable=True),
        sa.Column("sales_confirmed_by", sa.Integer(), nullable=True),
        sa.Column("sales_confirmed_at", sa.String(length=50), nullable=True),
        sa.Column("sales_supervisor_confirmed_by", sa.Integer(), nullable=True),
        sa.Column("sales_supervisor_confirmed_at", sa.String(length=50), nullable=True),
        sa.Column("customer_confirmed_at", sa.String(length=50), nullable=True),
        sa.Column("customer_confirmed_by", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.String(length=50), nullable=True),
        sa.Column("completed_by", sa.Integer(), nullable=True),
        sa.Column("cancelled_at", sa.String(length=50), nullable=True),
        sa.Column("cancelled_by", sa.Integer(), nullable=True),
        sa.Column("detail_file_path", sa.String(length=255), nullable=True),
        sa.Column("detail_file_name", sa.String(length=255), nullable=True),
        sa.Column("is_auto_generated", sa.Boolean(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["discount_approver_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["cs_supervisor_confirmed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["sales_confirmed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["sales_supervisor_confirmed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["customer_confirmed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["completed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["cancelled_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_vr_settlement_customer_period",
        "vr_settlements",
        ["customer_id", "period_start", "period_end"],
        unique=False,
    )
    op.create_index(
        "idx_vr_settlement_status_period",
        "vr_settlements",
        ["status", "period_start"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vr_settlements_settlement_no"), "vr_settlements", ["settlement_no"], unique=True
    )
    op.create_index(
        op.f("ix_vr_settlements_customer_id"), "vr_settlements", ["customer_id"], unique=False
    )
    op.create_index(
        op.f("ix_vr_settlements_period_start"), "vr_settlements", ["period_start"], unique=False
    )
    op.create_index(
        op.f("ix_vr_settlements_period_end"), "vr_settlements", ["period_end"], unique=False
    )
    op.create_index(op.f("ix_vr_settlements_status"), "vr_settlements", ["status"], unique=False)

    # ---- 2. 减免修改历史表 ----
    op.create_table(
        "vr_settlement_discount_histories",
        sa.Column("settlement_id", sa.Integer(), nullable=False),
        sa.Column("discount_amount", sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column("discount_reason", sa.Text(), nullable=True),
        sa.Column("discount_attachment", sa.String(length=255), nullable=True),
        sa.Column("applied_at", sa.String(length=50), nullable=False),
        sa.Column("applied_by", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["applied_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["settlement_id"], ["vr_settlements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_vr_discount_history_settlement",
        "vr_settlement_discount_histories",
        ["settlement_id", "applied_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vr_settlement_discount_histories_settlement_id"),
        "vr_settlement_discount_histories",
        ["settlement_id"],
        unique=False,
    )

    # ---- 3. consumption_records 新增 VR 结算单外键列 ----
    op.add_column(
        "consumption_records",
        sa.Column(
            "vr_settlement_id",
            sa.Integer(),
            nullable=True,
            comment="关联VR结算单",
        ),
    )
    op.create_foreign_key(
        "fk_consumption_records_vr_settlement_id",
        "consumption_records",
        "vr_settlements",
        ["vr_settlement_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_consumption_records_vr_settlement_id"),
        "consumption_records",
        ["vr_settlement_id"],
        unique=False,
    )

    # ---- 4. 插入新权限（幂等，使用 ON CONFLICT DO NOTHING）----
    op.execute(
        """
        INSERT INTO permissions (code, name, description, module, created_at, updated_at)
        VALUES
            ('vr_settlement:view', '查看VR结算', '查看VR编辑费用结算单列表与详情', 'vr_settlement', now(), now()),
            ('vr_settlement:create', '创建VR结算单', '手动创建VR结算单并提交审批', 'vr_settlement', now(), now()),
            ('vr_settlement:edit', '编辑VR结算单', '提交/修改减免、取消VR结算单', 'vr_settlement', now(), now()),
            ('vr_settlement:delete', '删除VR结算单', '删除VR结算单', 'vr_settlement', now(), now()),
            ('vr_settlement:cs_approve', '客服主管审批', '客服主管审批VR结算单（第一步）', 'vr_settlement', now(), now()),
            ('vr_settlement:sales_approve', '销售审批', '客户指定销售审批VR结算单（第二步）', 'vr_settlement', now(), now()),
            ('vr_settlement:sales_supervisor_approve', '销售主管审批', '销售主管审批VR结算单（第三步，含减免一并审批）', 'vr_settlement', now(), now()),
            ('vr_settlement:confirm', '客户确认VR结算单', '客户确认并自动扣款完成结算', 'vr_settlement', now(), now())
        ON CONFLICT (code) DO NOTHING
        """
    )

    # ---- 5. 为超级管理员角色关联新权限（幂等）----
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = '超级管理员'
          AND p.code IN (
              'vr_settlement:view', 'vr_settlement:create', 'vr_settlement:edit',
              'vr_settlement:delete', 'vr_settlement:cs_approve', 'vr_settlement:sales_approve',
              'vr_settlement:sales_supervisor_approve', 'vr_settlement:confirm'
          )
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
            SELECT id FROM permissions
            WHERE code IN (
                'vr_settlement:view', 'vr_settlement:create', 'vr_settlement:edit',
                'vr_settlement:delete', 'vr_settlement:cs_approve', 'vr_settlement:sales_approve',
                'vr_settlement:sales_supervisor_approve', 'vr_settlement:confirm'
            )
        )
        """
    )
    # 2. 删除权限码
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN (
            'vr_settlement:view', 'vr_settlement:create', 'vr_settlement:edit',
            'vr_settlement:delete', 'vr_settlement:cs_approve', 'vr_settlement:sales_approve',
            'vr_settlement:sales_supervisor_approve', 'vr_settlement:confirm'
        )
        """
    )
    # 3. 删除 consumption_records.vr_settlement_id 索引、外键与列
    op.drop_index(op.f("ix_consumption_records_vr_settlement_id"), table_name="consumption_records")
    op.drop_constraint(
        "fk_consumption_records_vr_settlement_id", "consumption_records", type_="foreignkey"
    )
    op.drop_column("consumption_records", "vr_settlement_id")
    # 4. 删除减免历史表（CASCADE 外键随主表删除，显式删除更稳）
    op.drop_index(
        op.f("ix_vr_settlement_discount_histories_settlement_id"),
        table_name="vr_settlement_discount_histories",
    )
    op.drop_index(
        "idx_vr_discount_history_settlement", table_name="vr_settlement_discount_histories"
    )
    op.drop_table("vr_settlement_discount_histories")
    # 5. 删除主表
    op.drop_index(op.f("ix_vr_settlements_status"), table_name="vr_settlements")
    op.drop_index(op.f("ix_vr_settlements_period_end"), table_name="vr_settlements")
    op.drop_index(op.f("ix_vr_settlements_period_start"), table_name="vr_settlements")
    op.drop_index(op.f("ix_vr_settlements_customer_id"), table_name="vr_settlements")
    op.drop_index(op.f("ix_vr_settlements_settlement_no"), table_name="vr_settlements")
    op.drop_index("idx_vr_settlement_status_period", table_name="vr_settlements")
    op.drop_index("idx_vr_settlement_customer_period", table_name="vr_settlements")
    op.drop_table("vr_settlements")
