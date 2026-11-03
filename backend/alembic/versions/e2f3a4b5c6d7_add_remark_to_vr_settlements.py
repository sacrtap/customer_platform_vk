"""add remark to vr settlements

Revision ID: e2f3a4b5c6d7
Revises: d0e1f2a3b4c5
Create Date: 2026-11-03

VR结算单创建弹窗新增「备注说明」多行文本字段：
vr_settlements 新增 remark 列（Text, nullable），仅创建时填写、全链路只读展示。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("vr_settlements", sa.Column("remark", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("vr_settlements", "remark")
