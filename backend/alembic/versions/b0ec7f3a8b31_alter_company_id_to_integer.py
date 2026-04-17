"""alter_company_id_to_integer

Revision ID: b0ec7f3a8b31
Revises: 005
Create Date: 2026-04-17

将 customers.company_id 从 VARCHAR(50) 改为 INTEGER 类型。
前提：所有 TEST_* 测试数据已清理，剩余 company_id 均为纯数字。
"""

from typing import Union, Sequence
from alembic import op
import sqlalchemy as sa


revision: str = "b0ec7f3a8b31"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL 需要使用 USING 子句进行类型转换
    # 先删除旧索引（类型改变时会自动处理，但显式声明更清晰）
    op.alter_column(
        "customers",
        "company_id",
        type_=sa.Integer(),
        postgresql_using="company_id::integer",
        existing_type=sa.String(50),
        nullable=False,
    )
    # 重新创建唯一索引（类型改变后需要重建）
    op.create_unique_constraint("uq_customers_company_id", "customers", ["company_id"])


def downgrade() -> None:
    # 回退到字符串类型
    op.drop_constraint("uq_customers_company_id", "customers", type_="unique")
    op.alter_column(
        "customers",
        "company_id",
        type_=sa.String(50),
        existing_type=sa.Integer(),
        nullable=False,
    )
