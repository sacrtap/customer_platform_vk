"""add forecast_unit_prices table

Revision ID: t9u0v1w2x3y4
Revises: s8t9u0v1w2x3
Create Date: 2026-09-16

新增预测消费单价配置表 forecast_unit_prices，管理各设备类型（L/N/X）的
单价（元/套），支持运行时修改（预测消费页面"预测参数"弹框）。

背景：模型 ForecastUnitPrice（app/models/forecast_config.py）随提交
3a9b2aa 引入时未附迁移文件，导致远程通过 `alembic upgrade head` 部署时
缺表，预测消费各接口（forecast / price-config 等）500。

注意：本地开发库因曾手动建表已存在该表，本迁移幂等处理——表已存在时
跳过建表（与 d3e4f5a6b7c8 处理 package_plans 的方式一致）。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "t9u0v1w2x3y4"
down_revision: Union[str, None] = "s8t9u0v1w2x3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 幂等处理：如果表已存在（本地开发期手动建过），则跳过建表
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "forecast_unit_prices" in inspector.get_table_names():
        return

    op.create_table(
        "forecast_unit_prices",
        sa.Column(
            "device_type", sa.String(length=10), primary_key=True, comment="设备类型（L/N/X）"
        ),
        sa.Column(
            "unit_price", sa.Numeric(precision=10, scale=2), nullable=False, comment="单价（元/套）"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
    )


def downgrade() -> None:
    op.drop_table("forecast_unit_prices")
