"""用户与权限模型"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

# 用户 - 角色关联表
user_roles = Table(
    "user_roles",
    BaseModel.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


# 角色 - 权限关联表
role_permissions = Table(
    "role_permissions",
    BaseModel.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class User(BaseModel):
    """用户表"""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100))
    real_name: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool | None] = mapped_column(Boolean, default=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

    # 关联
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    created_tags = relationship("Tag", back_populates="creator")

    def __repr__(self):
        return f"<User {self.username}>"


class Role(BaseModel):
    """角色表"""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))
    is_system: Mapped[bool | None] = mapped_column(Boolean, default=False)

    # 关联
    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")

    def __repr__(self):
        return f"<Role {self.name}>"


class Permission(BaseModel):
    """权限表"""

    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))
    module: Mapped[str] = mapped_column(String(50), nullable=False)

    # 关联
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")

    def __repr__(self):
        return f"<Permission {self.code}>"
