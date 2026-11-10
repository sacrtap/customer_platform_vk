"""add daily order detail snapshot columns
Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-11-09
月份明细快照化（F9）：
daily_orders 新增 19 个展示列（project_name/city/department/creator_name/
personal_name/nest_area/produce_status/produce_flag/remarks/editor_account/
editor_name/finish_date/first_send_zb_date/first_edit_time/review_release_date/
device_name/customer_review_result/publisher_name/model_fix_status），均可空、
不回填。
背景：结算单明细 Excel「月份明细」sheet 此前实时查外部 MySQL（nest_model_order
26 列 + nest_user 4 JOIN），与本地冻结计费（invoice_items/daily_orders 快照）存在
时点漂移——外部删单/改期后行数与「计费明细」「合计」对不上（实证 453 vs 452），
且补生成历史单会拿到「当前」外部状态而非出账时状态。改为读本快照后三表严格同源，
Excel 生成零外部依赖。
同步层 ORDER_SYNC_SQL 的 SELECT 同批扩展；create_date/upload_date 由 DATE()
改为原值 datetime（此前时刻丢失，月份明细显示 00:00:00）。
历史行新列为 NULL → 月份明细对应格为空（不回填：外部可能已删单取不回，
且已生成文件是交付物；dev 库可用 backend/scripts/backfill_daily_order_detail_columns.py
回填外部仍在的数据）。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "i4j5k6l7m8n9"
down_revision: Union[str, None] = "h3i4j5k6l7m8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    ("project_name", sa.String(200), "房源名称"),
    ("city", sa.String(50), "城市"),
    ("department", sa.String(100), "业务部门"),
    ("creator_name", sa.String(100), "创建人"),
    ("personal_name", sa.String(100), "所属人"),
    ("nest_area", sa.String(50), "面积"),
    ("produce_status", sa.String(20), "编辑状态码"),
    ("produce_flag", sa.String(20), "编辑标志码"),
    ("remarks", sa.Text, "备注"),
    ("editor_account", sa.String(100), "编辑人账号"),
    ("editor_name", sa.String(100), "编辑人姓名"),
    ("finish_date", sa.DateTime(timezone=True), "上传完成时间"),
    ("first_send_zb_date", sa.DateTime(timezone=True), "第一次分配时间"),
    ("first_edit_time", sa.DateTime(timezone=True), "户型图绘制时间"),
    ("review_release_date", sa.DateTime(timezone=True), "审核发布时间"),
    ("device_name", sa.String(100), "设备编号"),
    ("customer_review_result", sa.Integer, "复审状态码"),
    ("publisher_name", sa.String(100), "发布人"),
    ("model_fix_status", sa.Integer, "户型图修模状态码"),
]


def upgrade() -> None:
    for name, type_, comment in _COLUMNS:
        op.add_column(
            "daily_orders",
            sa.Column(name, type_, nullable=True, comment=comment),
        )


def downgrade() -> None:
    for name, _type, _comment in reversed(_COLUMNS):  # noqa: B007
        op.drop_column("daily_orders", name)
