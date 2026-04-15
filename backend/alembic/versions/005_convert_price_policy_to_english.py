"""convert price_policy Chinese values to English identifiers

Revision ID: 005
Revises: 004
Create Date: 2026-04-15

Mapping:
- '定价' → 'pricing'
- '阶梯' → 'tiered'
- '包年' → 'yearly'
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 更新现有的中文值为英文标识符
    op.execute(
        """
        UPDATE customers 
        SET price_policy = 'pricing' 
        WHERE price_policy = '定价'
        """
    )

    op.execute(
        """
        UPDATE customers 
        SET price_policy = 'tiered' 
        WHERE price_policy = '阶梯'
        """
    )

    op.execute(
        """
        UPDATE customers 
        SET price_policy = 'yearly' 
        WHERE price_policy = '包年'
        """
    )


def downgrade() -> None:
    # 回滚：将英文标识符恢复为中文
    op.execute(
        """
        UPDATE customers 
        SET price_policy = '定价' 
        WHERE price_policy = 'pricing'
        """
    )

    op.execute(
        """
        UPDATE customers 
        SET price_policy = '阶梯' 
        WHERE price_policy = 'tiered'
        """
    )

    op.execute(
        """
        UPDATE customers 
        SET price_policy = '包年' 
        WHERE price_policy = 'yearly'
        """
    )
