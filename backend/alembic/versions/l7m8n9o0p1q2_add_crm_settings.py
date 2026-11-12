"""add crm_settings table for page-managed CRM credentials

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-11-11

新增 `crm_settings`（单行 name='default'）：
- enabled / base_url / corp_id / phone 可由页面维护
- password_cipher 存 Fernet 密文（密钥由部署密钥 CRM_CREDENTIAL_KEY 提供），绝不存明文
- 表为空时运行期回退环境变量 CRM_*，既有部署行为不变

不修改任何既有表或数据。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "l7m8n9o0p1q2"
down_revision: Union[str, None] = "k6l7m8n9o0p1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crm_settings",
        sa.Column("name", sa.String(length=32), nullable=False, comment="配置名，固定 default"),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="是否启用 CRM 同步",
        ),
        sa.Column(
            "base_url",
            sa.String(length=255),
            nullable=False,
            comment="CRM 开放 API 基址（仅官方 HTTPS 域名）",
        ),
        sa.Column(
            "corp_id", sa.String(length=64), nullable=False, server_default="", comment="企业ID"
        ),
        sa.Column(
            "phone", sa.String(length=32), nullable=False, server_default="", comment="登录手机号"
        ),
        sa.Column(
            "password_cipher",
            sa.Text(),
            nullable=True,
            comment="登录密码 Fernet 密文，绝不存明文",
        ),
        sa.Column("updated_by", sa.Integer(), nullable=True, comment="最后修改人"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_crm_settings_name"),
    )


def downgrade() -> None:
    op.drop_table("crm_settings")
