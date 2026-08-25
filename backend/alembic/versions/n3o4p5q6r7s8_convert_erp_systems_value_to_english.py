"""convert erp_systems value to english identifiers

Revision ID: n3o4p5q6r7s8
Revises: m2n3o4p5q6r7
Create Date: 2026-08-25

将 erp_systems.value 从中文名转换为英文标识符。
同时更新 customers.erp_system 字段以保持数据一致性。
"""

from typing import Sequence, Union

from alembic import op

revision: str = "n3o4p5q6r7s8"
down_revision: Union[str, None] = "m2n3o4p5q6r7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 中文名 → 英文标识符映射
NAME_TO_VALUE = {
    "鼎尖": "dingjian",
    "易遨": "yiao",
    "房信": "fangxin",
    "房管家": "fangguanjia",
    "好房通": "haofangtong",
    "上海梵讯": "shanghaifanxun",
    "巧房": "qiaofang",
    "房融": "fangrong",
    "云享": "yunxiang",
    "房在线": "fangzaixian",
    "ERP云": "erp_cloud",
    "ERP本地": "erp_local",
    "无ERP": "none",
}


def upgrade() -> None:
    # 1. 更新 erp_systems 表的 value 列
    for cn_name, en_value in NAME_TO_VALUE.items():
        op.execute(
            f"UPDATE erp_systems SET value = '{en_value}' WHERE name = '{cn_name}' AND deleted_at IS NULL"
        )

    # 2. 更新 customers 表的 erp_system 字段（将中文值替换为英文标识符）
    for cn_name, en_value in NAME_TO_VALUE.items():
        op.execute(f"UPDATE customers SET erp_system = '{en_value}' WHERE erp_system = '{cn_name}'")


def downgrade() -> None:
    # 回滚：将英文标识符恢复为中文名
    for cn_name, en_value in NAME_TO_VALUE.items():
        op.execute(
            f"UPDATE erp_systems SET value = '{cn_name}' WHERE value = '{en_value}' AND deleted_at IS NULL"
        )
        op.execute(f"UPDATE customers SET erp_system = '{cn_name}' WHERE erp_system = '{en_value}'")
