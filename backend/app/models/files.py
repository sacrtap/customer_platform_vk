"""文件管理模型"""

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class File(BaseModel):
    """文件表"""

    __tablename__ = "files"

    # 文件信息
    filename: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名")
    stored_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, comment="存储文件名（随机）"
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="文件相对路径")
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="文件大小（字节）")
    file_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="文件 MIME 类型")

    # 关联信息
    uploaded_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, comment="上传人 ID"
    )

    # 索引字段
    file_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="文件 SHA256 哈希值（用于去重）"
    )

    # 导航路径（可选，用于业务关联）
    business_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="业务类型：customer_import/profile_image/other",
    )
    business_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="关联业务 ID")

    # 关系
    uploader = relationship("User", backref="uploaded_files")
