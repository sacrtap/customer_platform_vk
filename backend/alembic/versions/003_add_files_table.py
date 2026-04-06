"""add files table

Revision ID: 003
Revises: a5d21c5761aa
Create Date: 2026-04-06

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "003"
down_revision = "a5d21c5761aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 files 表"""
    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        # 文件信息
        sa.Column("filename", sa.String(255), nullable=False, comment="原始文件名"),
        sa.Column(
            "stored_filename",
            sa.String(255),
            nullable=False,
            unique=True,
            comment="存储文件名（随机）",
        ),
        sa.Column("file_path", sa.String(500), nullable=False, comment="文件相对路径"),
        sa.Column(
            "file_size", sa.BigInteger(), nullable=False, comment="文件大小（字节）"
        ),
        sa.Column(
            "file_type", sa.String(100), nullable=False, comment="文件 MIME 类型"
        ),
        # 关联信息
        sa.Column(
            "uploaded_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            comment="上传人 ID",
        ),
        # 索引字段
        sa.Column(
            "file_hash",
            sa.String(64),
            nullable=True,
            comment="文件 SHA256 哈希值（用于去重）",
        ),
        # 导航路径（可选，用于业务关联）
        sa.Column(
            "business_type",
            sa.String(50),
            nullable=True,
            comment="业务类型：customer_import/profile_image/other",
        ),
        sa.Column("business_id", sa.Integer(), nullable=True, comment="关联业务 ID"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 创建索引
    op.create_index("ix_files_file_hash", "files", ["file_hash"])
    op.create_index("ix_files_uploaded_by", "files", ["uploaded_by"])
    op.create_index("ix_files_deleted_at", "files", ["deleted_at"])
    op.create_index("ix_files_business_type", "files", ["business_type"])


def downgrade() -> None:
    """删除 files 表"""
    op.drop_index("ix_files_business_type", table_name="files")
    op.drop_index("ix_files_deleted_at", table_name="files")
    op.drop_index("ix_files_uploaded_by", table_name="files")
    op.drop_index("ix_files_file_hash", table_name="files")
    op.drop_table("files")
