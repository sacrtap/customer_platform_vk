"""add daily order house level unique key

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-11-09

F8 房源级识别键：daily_orders 唯一键由 (order_code, sync_date) 改为
(order_code, COALESCE(custom_code, ''), sync_date)。

背景：外部平台会把同一订单号派给多个房源（同号两行不同 house_id）。
按订单号判重时，第二房源在同步入口即被丢弃——内存去重 seen_keys、
DB 查重、跨日迁移按 order_code 互删三处都只认订单号——导致该笔业务
不计费，三表数量差 1。实证：深圳中原地产 2026-10，SZZY_1792727229
= 房源 826390（X 设备，upload 10-31）+ 房源 826271（L 设备，
upload 10-23），本地仅存 826390 一行（826271 被 10-31 批次的跨日
迁移按 order_code 删除）。

custom_code 为空（外部无房源编号，全库约 0.6% 行）时 COALESCE 归一为
空串，保持「订单号即唯一」的原语义——PG 唯一索引不约束 NULL，故用
表达式唯一索引而非直接含列。

既有数据不受影响：同号同窗此前最多一行（旧唯一键保证），换键不冲突，
无需回填。

downgrade 注意：若升级期间已产生「同订单号同窗多房源行」，退回
(order_code, sync_date) 唯一约束会因唯一冲突失败，需先手动清理
重复行再 downgrade。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h3i4j5k6l7m8"
down_revision: Union[str, None] = "g2h3i4j5k6l7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 旧唯一约束（i8d9e0f1g2h3 创建）→ 房源级唯一索引
    op.drop_constraint("uq_order_code_sync_date", "daily_orders", type_="unique")
    op.create_index(
        "uq_order_custom_sync_date",
        "daily_orders",
        ["order_code", sa.text("COALESCE(custom_code, '')"), "sync_date"],
        unique=True,
    )


def downgrade() -> None:
    # 注意：存在同订单号同窗多房源行时此步会唯一冲突，需先清理重复行
    op.drop_index("uq_order_custom_sync_date", table_name="daily_orders")
    op.create_unique_constraint(
        "uq_order_code_sync_date", "daily_orders", ["order_code", "sync_date"]
    )
