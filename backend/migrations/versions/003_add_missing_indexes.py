"""add missing indexes for query optimization

Revision ID: 003
Revises: 002
Create Date: 2026-04-04

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加缺失的索引以优化查询性能

    索引添加说明:
    1. recharge_records.created_at - 用于 ORDER BY 排序
    2. invoice_items.device_type - 用于 GROUP BY 聚合
    3. consumption_records.created_at - 用于时间范围查询
    4. customer_tags.customer_id/tag_id - 用于关联查询
    5. profile_tags.profile_id/tag_id - 用于关联查询
    6. daily_usage.device_type - 用于 GROUP BY 聚合
    """

    # === recharge_records ===
    # 用于 ORDER BY created_at DESC 排序
    # 影响查询：get_recharge_records(), get_payment_analysis()
    op.create_index(
        "idx_recharge_records_created_at",
        "recharge_records",
        ["created_at"],
        unique=False,
    )

    # === invoice_items ===
    # 用于 GROUP BY device_type 聚合
    # 影响查询：get_device_type_distribution()
    op.create_index(
        "idx_invoice_items_device_type", "invoice_items", ["device_type"], unique=False
    )

    # === consumption_records ===
    # 用于 WHERE created_at 时间范围查询
    # 影响查询：get_customer_health_stats(), get_inactive_customers()
    op.create_index(
        "idx_consumption_records_created_at",
        "consumption_records",
        ["created_at"],
        unique=False,
    )

    # === customer_tags ===
    # 用于 WHERE customer_id 和 tag_id 查询
    # 影响查询：get_customer_tags(), add_customer_tag(), remove_customer_tag()
    # 注意：customer_id 和 tag_id 是复合主键，但单独索引可优化单列查询
    op.create_index(
        "idx_customer_tags_customer_id", "customer_tags", ["customer_id"], unique=False
    )
    op.create_index(
        "idx_customer_tags_tag_id", "customer_tags", ["tag_id"], unique=False
    )

    # === profile_tags ===
    # 用于 WHERE profile_id 和 tag_id 查询
    # 影响查询：get_profile_tags(), add_profile_tag(), remove_profile_tag()
    op.create_index(
        "idx_profile_tags_profile_id", "profile_tags", ["profile_id"], unique=False
    )
    op.create_index("idx_profile_tags_tag_id", "profile_tags", ["tag_id"], unique=False)

    # === daily_usage ===
    # 添加 device_type 索引用于 GROUP BY
    # 影响查询：get_daily_usage_trend(), get_device_type_distribution()
    op.create_index(
        "idx_daily_usage_device_type", "daily_usage", ["device_type"], unique=False
    )


def downgrade() -> None:
    """回滚索引删除

    注意：生产环境删除索引前请评估对查询性能的影响
    """
    op.drop_index("idx_daily_usage_device_type", "daily_usage")
    op.drop_index("idx_profile_tags_tag_id", "profile_tags")
    op.drop_index("idx_profile_tags_profile_id", "profile_tags")
    op.drop_index("idx_customer_tags_tag_id", "customer_tags")
    op.drop_index("idx_customer_tags_customer_id", "customer_tags")
    op.drop_index("idx_consumption_records_created_at", "consumption_records")
    op.drop_index("idx_invoice_items_device_type", "invoice_items")
    op.drop_index("idx_recharge_records_created_at", "recharge_records")
