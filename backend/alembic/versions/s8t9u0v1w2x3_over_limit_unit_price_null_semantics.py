"""over_limit_unit_price NULL semantics

Revision ID: s8t9u0v1w2x3
Revises: r7s8t9u0v1w2
Create Date: 2026-09-12

将 over_limit_unit_price 语义改为: NULL = 自动计算 (base_fee / limit_count),
非 NULL = 用户自定义价格。将存储值恰好等于 base_fee/limit_count 的记录转为 NULL,
使其在 base_fee 或 limit_count 变更后自动跟随。
"""

from typing import Sequence, Union

from alembic import op

revision: str = "s8t9u0v1w2x3"
down_revision: Union[str, None] = "r7s8t9u0v1w2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE package_plans
        SET over_limit_unit_price = NULL
        WHERE is_unlimited = false
          AND deleted_at IS NULL
          AND over_limit_unit_price IS NOT NULL
          AND limit_count IS NOT NULL
          AND limit_count > 0
          AND over_limit_unit_price = ROUND(base_fee::numeric / limit_count, 2)
        """
    )

    op.execute(
        """
        COMMENT ON COLUMN package_plans.over_limit_unit_price IS
        '超额单价: NULL=自动计算(base_fee/limit_count), 非NULL=自定义价格'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE package_plans
        SET over_limit_unit_price = ROUND(base_fee::numeric / limit_count, 2)
        WHERE is_unlimited = false
          AND deleted_at IS NULL
          AND over_limit_unit_price IS NULL
          AND limit_count IS NOT NULL
          AND limit_count > 0
        """
    )

    op.execute(
        """
        COMMENT ON COLUMN package_plans.over_limit_unit_price IS
        '超额单价（限量套餐超出 limit_count 后的每单位用量价格）'
        """
    )
