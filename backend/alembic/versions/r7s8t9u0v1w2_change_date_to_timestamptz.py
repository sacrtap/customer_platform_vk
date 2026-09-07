"""change date columns to timestamptz for UTC storage

Revision ID: r7s8t9u0v1w2
Revises: q6r7s8t9u0v1
Create Date: 2026-09-04

将以下表的 Date 字段改为 timestamptz（带时区的 DateTime）：
- invoices.period_start, period_end
- pricing_rules.effective_date, expiry_date
- daily_consumptions.consumption_date
- daily_orders.sync_date, create_date, upload_date
- consumption_sync_logs.start_date, end_date

历史数据将重新拉取，不做数据转换。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "r7s8t9u0v1w2"
down_revision: Union[str, None] = "q6r7s8t9u0v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- invoices ---
    op.alter_column(
        "invoices",
        "period_start",
        type_=sa.DateTime(timezone=True),
        postgresql_using="period_start::timestamp",
        existing_type=sa.Date(),
    )
    op.alter_column(
        "invoices",
        "period_end",
        type_=sa.DateTime(timezone=True),
        postgresql_using="period_end::timestamp",
        existing_type=sa.Date(),
    )

    # --- pricing_rules ---
    op.alter_column(
        "pricing_rules",
        "effective_date",
        type_=sa.DateTime(timezone=True),
        postgresql_using="effective_date::timestamp",
        existing_type=sa.Date(),
    )
    op.alter_column(
        "pricing_rules",
        "expiry_date",
        type_=sa.DateTime(timezone=True),
        postgresql_using="expiry_date::timestamp",
        existing_type=sa.Date(),
    )

    # --- daily_consumptions ---
    op.alter_column(
        "daily_consumptions",
        "consumption_date",
        type_=sa.DateTime(timezone=True),
        postgresql_using="consumption_date::timestamp",
        existing_type=sa.Date(),
    )

    # --- daily_orders ---
    op.alter_column(
        "daily_orders",
        "sync_date",
        type_=sa.DateTime(timezone=True),
        postgresql_using="sync_date::timestamp",
        existing_type=sa.Date(),
    )
    op.alter_column(
        "daily_orders",
        "create_date",
        type_=sa.DateTime(timezone=True),
        postgresql_using="create_date::timestamp",
        existing_type=sa.Date(),
    )
    op.alter_column(
        "daily_orders",
        "upload_date",
        type_=sa.DateTime(timezone=True),
        postgresql_using="upload_date::timestamp",
        existing_type=sa.Date(),
    )

    # --- sync_task_logs ---
    op.alter_column(
        "sync_task_logs",
        "start_date",
        type_=sa.DateTime(timezone=True),
        postgresql_using="start_date::timestamp",
        existing_type=sa.Date(),
    )
    op.alter_column(
        "sync_task_logs",
        "end_date",
        type_=sa.DateTime(timezone=True),
        postgresql_using="end_date::timestamp",
        existing_type=sa.Date(),
    )


def downgrade() -> None:
    # --- consumption_sync_logs ---
    op.alter_column(
        "sync_task_logs",
        "end_date",
        type_=sa.Date(),
        postgresql_using="end_date::date",
        existing_type=sa.DateTime(timezone=True),
    )
    op.alter_column(
        "sync_task_logs",
        "start_date",
        type_=sa.Date(),
        postgresql_using="start_date::date",
        existing_type=sa.DateTime(timezone=True),
    )

    # --- daily_orders ---
    op.alter_column(
        "daily_orders",
        "upload_date",
        type_=sa.Date(),
        postgresql_using="upload_date::date",
        existing_type=sa.DateTime(timezone=True),
    )
    op.alter_column(
        "daily_orders",
        "create_date",
        type_=sa.Date(),
        postgresql_using="create_date::date",
        existing_type=sa.DateTime(timezone=True),
    )
    op.alter_column(
        "daily_orders",
        "sync_date",
        type_=sa.Date(),
        postgresql_using="sync_date::date",
        existing_type=sa.DateTime(timezone=True),
    )

    # --- daily_consumptions ---
    op.alter_column(
        "daily_consumptions",
        "consumption_date",
        type_=sa.Date(),
        postgresql_using="consumption_date::date",
        existing_type=sa.DateTime(timezone=True),
    )

    # --- pricing_rules ---
    op.alter_column(
        "pricing_rules",
        "expiry_date",
        type_=sa.Date(),
        postgresql_using="expiry_date::date",
        existing_type=sa.DateTime(timezone=True),
    )
    op.alter_column(
        "pricing_rules",
        "effective_date",
        type_=sa.Date(),
        postgresql_using="effective_date::date",
        existing_type=sa.DateTime(timezone=True),
    )

    # --- invoices ---
    op.alter_column(
        "invoices",
        "period_end",
        type_=sa.Date(),
        postgresql_using="period_end::date",
        existing_type=sa.DateTime(timezone=True),
    )
    op.alter_column(
        "invoices",
        "period_start",
        type_=sa.Date(),
        postgresql_using="period_start::date",
        existing_type=sa.DateTime(timezone=True),
    )
