"""add CRM recharge mirror tables and recharge business date

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9
Create Date: 2026-11-11

CRM 充值管理基础设施：
1. crm_customers / crm_payments / crm_sync_runs 三张只读镜像表
2. customers.crm_customer_id（一对一绑定，部分唯一索引排除软删除行）
3. recharge_records.recharge_date（业务归期，先 nullable → 用 created_at 回填 → NOT NULL）
   与 crm_payment_id（UNIQUE，覆盖软删除行）

不覆盖任何历史 created_at、余额或金额；历史行 recharge_date 取 created_at::date。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers
revision: str = "k6l7m8n9o0p1"
down_revision: Union[str, None] = "j5k6l7m8n9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- 1. CRM 客户目录镜像 ----
    op.create_table(
        "crm_customers",
        sa.Column("corp_id", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.BIGINT(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("owner_name", sa.String(length=255), nullable=True),
        sa.Column(
            "last_seen_at", sa.DateTime(), nullable=False, comment="最近一次同步可见时间(CST)"
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corp_id", "external_id", name="uq_crm_customers_corp_external"),
    )
    op.create_index(
        "idx_crm_customers_normalized_name", "crm_customers", ["normalized_name"], unique=False
    )

    # ---- 2. CRM 回款镜像 ----
    op.create_table(
        "crm_payments",
        sa.Column("corp_id", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.BIGINT(), nullable=False),
        sa.Column("crm_customer_id", sa.Integer(), nullable=True),
        sa.Column("contract_external_id", sa.BIGINT(), nullable=False),
        sa.Column("contract_title", sa.String(length=255), nullable=True),
        sa.Column("customer_external_id", sa.BIGINT(), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column("receive_date", sa.Date(), nullable=True),
        sa.Column("approve_status", sa.String(length=32), nullable=False),
        sa.Column("industry_path", sa.Text(), nullable=True),
        sa.Column("industry_label", sa.Text(), nullable=True),
        sa.Column("source_updated_at", sa.String(length=64), nullable=True),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column(
            "last_seen_at", sa.DateTime(), nullable=False, comment="最近一次同步可见时间(CST)"
        ),
        sa.Column("imported_snapshot", JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_changed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["crm_customer_id"], ["crm_customers.id"]),
        sa.UniqueConstraint("corp_id", "external_id", name="uq_crm_payments_corp_external"),
    )
    op.create_index(
        "idx_crm_payments_receive_date_eligible",
        "crm_payments",
        ["receive_date", "eligible"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crm_payments_crm_customer_id"), "crm_payments", ["crm_customer_id"], unique=False
    )

    # ---- 3. CRM 同步执行记录 ----
    op.create_table(
        "crm_sync_runs",
        sa.Column("corp_id", sa.String(length=64), nullable=False),
        sa.Column("month", sa.Date(), nullable=False, comment="同步月份月首"),
        sa.Column("trigger", sa.String(length=16), nullable=False, comment="scheduled/manual"),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            comment="pending/running/succeeded/failed",
        ),
        sa.Column(
            "phase",
            sa.String(length=24),
            nullable=False,
            comment="customers/contracts/payments/completed",
        ),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("customer_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("contract_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "scanned_contract_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("payment_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("eligible_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
    )
    op.create_index(
        "uq_crm_sync_active_corp",
        "crm_sync_runs",
        ["corp_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )
    op.create_index("idx_crm_sync_runs_month", "crm_sync_runs", ["month", "status"], unique=False)

    # ---- 4. customers.crm_customer_id（一对一绑定） ----
    op.add_column("customers", sa.Column("crm_customer_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_customers_crm_customer_id", "customers", "crm_customers", ["crm_customer_id"], ["id"]
    )
    op.create_index(
        op.f("ix_customers_crm_customer_id"), "customers", ["crm_customer_id"], unique=False
    )
    op.create_index(
        "uq_customer_active_crm_binding",
        "customers",
        ["crm_customer_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND crm_customer_id IS NOT NULL"),
    )

    # ---- 5. recharge_records 业务归期：回填后置 NOT NULL ----
    op.add_column("recharge_records", sa.Column("recharge_date", sa.Date(), nullable=True))
    op.execute(
        "UPDATE recharge_records SET recharge_date = created_at::date WHERE recharge_date IS NULL"
    )
    op.alter_column(
        "recharge_records",
        "recharge_date",
        existing_type=sa.Date(),
        nullable=False,
        server_default=sa.text("CURRENT_DATE"),
    )
    op.create_index(
        op.f("ix_recharge_records_recharge_date"),
        "recharge_records",
        ["recharge_date"],
        unique=False,
    )

    # ---- 6. recharge_records.crm_payment_id（同源幂等，唯一约束覆盖软删除行） ----
    op.add_column("recharge_records", sa.Column("crm_payment_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_recharge_records_crm_payment_id",
        "recharge_records",
        "crm_payments",
        ["crm_payment_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_recharge_records_crm_payment_id", "recharge_records", ["crm_payment_id"]
    )


def downgrade() -> None:
    # 仅删除本迁移新增对象；有 CRM 已入账数据时生产不执行降级（停用同步并保留表与资金记录）
    op.drop_constraint("uq_recharge_records_crm_payment_id", "recharge_records", type_="unique")
    op.drop_constraint("fk_recharge_records_crm_payment_id", "recharge_records", type_="foreignkey")
    op.drop_index(op.f("ix_recharge_records_recharge_date"), table_name="recharge_records")
    op.drop_column("recharge_records", "crm_payment_id")
    op.drop_column("recharge_records", "recharge_date")

    op.drop_index("uq_customer_active_crm_binding", table_name="customers")
    op.drop_index(op.f("ix_customers_crm_customer_id"), table_name="customers")
    op.drop_constraint("fk_customers_crm_customer_id", "customers", type_="foreignkey")
    op.drop_column("customers", "crm_customer_id")

    op.drop_index("idx_crm_sync_runs_month", table_name="crm_sync_runs")
    op.drop_index("uq_crm_sync_active_corp", table_name="crm_sync_runs")
    op.drop_table("crm_sync_runs")

    op.drop_index(op.f("ix_crm_payments_crm_customer_id"), table_name="crm_payments")
    op.drop_index("idx_crm_payments_receive_date_eligible", table_name="crm_payments")
    op.drop_table("crm_payments")

    op.drop_index("idx_crm_customers_normalized_name", table_name="crm_customers")
    op.drop_table("crm_customers")
