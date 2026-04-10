"""文件管理模型"""

from sqlalchemy import Column, String, Integer, BigInteger, ForeignKey, Text
from sqlalchemy.orm import relationship
from .base import BaseModel


class File(BaseModel):
    """文件表"""

    __tablename__ = "files"

    # 文件信息
    filename = Column(String(255), nullable=False, comment="原始文件名")
    stored_filename = Column(
        String(255), nullable=False, unique=True, comment="存储文件名（随机）"
    )
    file_path = Column(String(500), nullable=False, comment="文件相对路径")
    file_size = Column(BigInteger, nullable=False, comment="文件大小（字节）")
    file_type = Column(String(100), nullable=False, comment="文件 MIME 类型")

    # 关联信息
    uploaded_by = Column(
        Integer, ForeignKey("users.id"), nullable=False, comment="上传人 ID"
    )

    # 索引字段
    file_hash = Column(
        String(64), nullable=True, index=True, comment="文件 SHA256 哈希值（用于去重）"
    )

    # 导航路径（可选，用于业务关联）
    business_type = Column(
        String(50),
        nullable=True,
        comment="业务类型：customer_import/profile_image/other",
    )
    business_id = Column(Integer, nullable=True, comment="关联业务 ID")

    # 关系
    uploader = relationship("User", backref="uploaded_files")
