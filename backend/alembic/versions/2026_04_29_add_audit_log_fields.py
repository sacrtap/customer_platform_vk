"""add audit log operation_type and metadata fields

Revision ID: 2026_04_29_audit_fields
Revises: 
Create Date: 2026-04-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '2026_04_29_audit_fields'
down_revision: Union[str, None] = 'c09e8906c00d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        'audit_logs',
        sa.Column('operation_type', sa.String(20), server_default='standard',
                  comment='操作类型: standard/batch/relation/sensitive')
    )
    op.add_column(
        'audit_logs',
        sa.Column('extra_metadata', sa.JSON(), nullable=True,
                  comment='扩展元数据: 批量统计、关系ID列表等')
    )

def downgrade() -> None:
    op.drop_column('audit_logs', 'extra_metadata')
    op.drop_column('audit_logs', 'operation_type')
