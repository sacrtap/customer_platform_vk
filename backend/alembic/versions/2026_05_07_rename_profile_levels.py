"""rename profile levels: consume S/A/B/C/D/E→C1-C6, scale numbers→S/A/B/C/D/E

Revision ID: 2026_05_07_rename_levels
Revises: 2026_04_29_audit_fields
Create Date: 2026-05-07
"""

from typing import Sequence, Union
from alembic import op

revision: str = "2026_05_07_rename_levels"
down_revision: Union[str, None] = "2026_04_29_audit_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 消费等级迁移: S→C1, A→C2, B→C3, C→C4, D→C5, E→C6
    op.execute("UPDATE customer_profiles SET consume_level = 'C1' WHERE consume_level = 'S'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C2' WHERE consume_level = 'A'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C3' WHERE consume_level = 'B'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C4' WHERE consume_level = 'C'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C5' WHERE consume_level = 'D'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C6' WHERE consume_level = 'E'")

    # 规模等级迁移: 5000→S, 2000→A, 1000→B, 500→C, 100→D
    op.execute("UPDATE customer_profiles SET scale_level = 'S' WHERE scale_level = '5000'")
    op.execute("UPDATE customer_profiles SET scale_level = 'A' WHERE scale_level = '2000'")
    op.execute("UPDATE customer_profiles SET scale_level = 'B' WHERE scale_level = '1000'")
    op.execute("UPDATE customer_profiles SET scale_level = 'C' WHERE scale_level = '500'")
    op.execute("UPDATE customer_profiles SET scale_level = 'D' WHERE scale_level = '100'")


def downgrade() -> None:
    # 消费等级回滚
    op.execute("UPDATE customer_profiles SET consume_level = 'S' WHERE consume_level = 'C1'")
    op.execute("UPDATE customer_profiles SET consume_level = 'A' WHERE consume_level = 'C2'")
    op.execute("UPDATE customer_profiles SET consume_level = 'B' WHERE consume_level = 'C3'")
    op.execute("UPDATE customer_profiles SET consume_level = 'C' WHERE consume_level = 'C4'")
    op.execute("UPDATE customer_profiles SET consume_level = 'D' WHERE consume_level = 'C5'")
    op.execute("UPDATE customer_profiles SET consume_level = 'E' WHERE consume_level = 'C6'")

    # 规模等级回滚
    op.execute("UPDATE customer_profiles SET scale_level = '5000' WHERE scale_level = 'S'")
    op.execute("UPDATE customer_profiles SET scale_level = '2000' WHERE scale_level = 'A'")
    op.execute("UPDATE customer_profiles SET scale_level = '1000' WHERE scale_level = 'B'")
    op.execute("UPDATE customer_profiles SET scale_level = '500' WHERE scale_level = 'C'")
    op.execute("UPDATE customer_profiles SET scale_level = '100' WHERE scale_level = 'D'")
