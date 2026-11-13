"""add crm_sync_runs.scanned_payment_count

`GET /api/v2/received_payments` 在 CRM 服务端抛 `no_method_error`（上游 bug），
但 `/api/v2/received_payments/list?approve_status=approved` 可用（实测 1536 条 / 16 页 ≈ 22s），
同步因此新增「全局回款列表」主路径替代逐合同枚举（7118 个合同 ≈ 2.4h）。

该路径没有合同扫描进度，需要独立的「已检查回款数」，
避免前端把回款条数误读成合同数（`scanned_contract_count` 保留给回退路径）。

仅新增一列，不改动既有列与数据。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "m8n9o0p1q2r3"
down_revision: Union[str, None] = "l7m8n9o0p1q2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "crm_sync_runs",
        sa.Column(
            "scanned_payment_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="回款列表路径已检查的回款条数",
        ),
    )


def downgrade() -> None:
    op.drop_column("crm_sync_runs", "scanned_payment_count")
