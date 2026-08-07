"""add upload_date and order_status to daily_orders

Revision ID: i8d9e0f1g2h3
Revises: h7c8d9e0f1g2
Create Date: 2026-08-06 18:00:00.000000

订单同步优化：
- daily_orders 新增 upload_date: 订单上传日期（来自外部 MySQL）
- daily_orders 新增 order_status: 订单状态（来自外部 MySQL）
- 修改唯一约束: (order_code, create_date) → (order_code, sync_date)
- 调整索引: idx_daily_orders_customer_date 从 (customer_id, create_date) → (customer_id, sync_date)

背景：原同步 SQL 使用 DATE(create_date) 进行日期过滤，导致 create_time_idx 索引失效
（全表扫描 450 万行，耗时 10s+）。改为 upload_date 范围查询 + order_status 条件过滤后，
耗时降至 ~2s，同时修正了跨日上传订单的统计偏差（如安溪如是 7月 286→287）。

"""

from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i8d9e0f1g2h3"
down_revision: Union[str, None] = "h7c8d9e0f1g2"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # 1. 新增 upload_date 列（允许为空，兼容历史数据）
    op.add_column(
        "daily_orders",
        sa.Column("upload_date", sa.Date(), nullable=True, comment="订单上传日期（外部系统）"),
    )

    # 2. 新增 order_status 列（允许为空，兼容历史数据）
    op.add_column(
        "daily_orders",
        sa.Column("order_status", sa.Integer(), nullable=True, comment="订单状态（外部系统）"),
    )

    # 3. 删除旧唯一约束 (order_code, create_date)
    op.drop_constraint("uq_order_code_date", "daily_orders", type_="unique")

    # 4. 创建新唯一约束 (order_code, sync_date)
    op.create_unique_constraint(
        "uq_order_code_sync_date", "daily_orders", ["order_code", "sync_date"]
    )

    # 5. 删除旧索引 (customer_id, create_date)
    op.drop_index("idx_daily_orders_customer_date", table_name="daily_orders")

    # 6. 创建新索引 (customer_id, sync_date)
    op.create_index(
        "idx_daily_orders_customer_date",
        "daily_orders",
        ["customer_id", "sync_date"],
    )


def downgrade() -> None:
    # 恢复旧索引
    op.drop_index("idx_daily_orders_customer_date", table_name="daily_orders")
    op.create_index(
        "idx_daily_orders_customer_date",
        "daily_orders",
        ["customer_id", "create_date"],
    )

    # 恢复旧唯一约束
    op.drop_constraint("uq_order_code_sync_date", "daily_orders", type_="unique")
    op.create_unique_constraint("uq_order_code_date", "daily_orders", ["order_code", "create_date"])

    # 删除新增列
    op.drop_column("daily_orders", "order_status")
    op.drop_column("daily_orders", "upload_date")
