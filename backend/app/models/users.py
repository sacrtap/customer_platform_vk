"""用户与权限模型"""

from sqlalchemy import Column, String, Boolean, ForeignKey, Table, Integer
from sqlalchemy.orm import relationship
from .base import BaseModel


# 用户 - 角色关联表
user_roles = Table(
    "user_roles",
    BaseModel.metadata,
    Column(
        "user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    ),
)


# 角色 - 权限关联表
role_permissions = Table(
    "role_permissions",
    BaseModel.metadata,
    Column(
        "role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    ),
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

    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100))
    real_name = Column(String(50))
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)

    # 关联
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    created_tags = relationship("Tag", back_populates="creator")

    def __repr__(self):
        return f"<User {self.username}>"


class Role(BaseModel):
    """角色表"""

    __tablename__ = "roles"

    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(200))
    is_system = Column(Boolean, default=False)

    # 关联
    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship(
        "Permission", secondary=role_permissions, back_populates="roles"
    )

    def __repr__(self):
        return f"<Role {self.name}>"


class Permission(BaseModel):
    """权限表"""

    __tablename__ = "permissions"

    code = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(200))
    module = Column(String(50), nullable=False)

    # 关联
    roles = relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )

    def __repr__(self):
        return f"<Permission {self.code}>"
