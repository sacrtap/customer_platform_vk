"""seed industry types

Revision ID: 8f6a04467a12
Revises: cc8c81328d2e
Create Date: 2026-05-11 18:12:29.581988

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "8f6a04467a12"
down_revision: Union[str, None] = "cc8c81328d2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """初始化行业类型种子数据"""
    op.bulk_insert(
        sa.table(
            "industry_types",
            sa.column("name", sa.String),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {"name": "项目", "sort_order": 1},
            {"name": "房产经纪", "sort_order": 2},
            {"name": "房产ERP", "sort_order": 3},
            {"name": "房产平台", "sort_order": 4},
            {"name": "公共安全", "sort_order": 5},
            {"name": "租房", "sort_order": 6},
            {"name": "待确认", "sort_order": 7},
            {"name": "无", "sort_order": 8},
        ],
    )


def downgrade() -> None:
    """回滚行业类型种子数据"""
    op.execute(
        "DELETE FROM industry_types WHERE name IN ('项目', '房产经纪', '房产ERP', '房产平台', '公共安全', '租房', '待确认', '无')"
    )
