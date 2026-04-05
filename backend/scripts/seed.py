#!/usr/bin/env python3
"""
初始化种子数据脚本
创建 admin 超级管理员用户、所有权限定义、以及超级管理员角色。

用法:
    python scripts/seed.py
    python scripts/seed.py --reset   # 清空已有种子数据后重新创建
"""

import sys
import os
import argparse
import bcrypt

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 加载 .env 文件
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass  # python-dotenv 未安装时跳过

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# 导入模型（在 sys.path 设置之后）
from app.models.users import User, Role, Permission

# 从环境变量读取数据库 URL，默认本地 PostgreSQL（无密码，使用当前系统用户）
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost/customer_platform",
)

# ============================================================
# 权限定义（与前端路由 requiresPermission 和后端 require_permission 保持一致）
# ============================================================
ALL_PERMISSIONS = [
    # 平台账号管理
    ("users:manage", "平台账号管理", "管理平台用户账号的增删改查", "users"),
    # 角色权限管理
    ("roles:manage", "角色权限管理", "管理角色和权限的分配", "roles"),
    # 客户管理
    ("customers:manage", "客户管理", "管理客户信息的增删改查", "customers"),
    # 标签管理
    ("tags:manage", "标签管理", "管理客户标签", "tags"),
    # 结算管理
    ("billing:manage", "结算管理", "管理客户余额和定价规则", "billing"),
    # 系统查看（同步日志、审计日志）
    ("system:view", "系统查看", "查看系统日志和审计记录", "system"),
    # 后端装饰器使用的权限码
    ("billing.recharge", "充值操作", "执行客户充值操作", "billing"),
    ("user.delete", "删除用户", "删除平台用户账号", "users"),
    # 客户分组
    ("groups:manage", "客户分组管理", "管理客户分组", "groups"),
    # 数据分析
    ("analytics:view", "数据分析查看", "查看数据分析报表", "analytics"),
    # 文件管理
    ("files:manage", "文件管理", "管理上传文件", "files"),
    # Webhook 管理
    ("webhooks:manage", "Webhook 管理", "管理 Webhook 配置", "webhooks"),
]

# 超级管理员角色名称
SUPER_ADMIN_ROLE_NAME = "超级管理员"


def get_or_create_permission(
    session: Session, code: str, name: str, description: str, module: str
):
    """获取或创建权限记录"""
    result = session.execute(select(Permission).where(Permission.code == code))
    perm = result.scalar_one_or_none()
    if perm is None:
        perm = Permission(code=code, name=name, description=description, module=module)
        session.add(perm)
        print(f"  ✅ 创建权限: {code} ({name})")
    else:
        print(f"  ⏭️  权限已存在: {code}")
    return perm


def seed(reset: bool = False):
    """执行种子数据初始化"""
    print(f"连接到数据库：{DATABASE_URL}")

    # 使用同步引擎
    engine = create_engine(
        DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    )

    # 在 Session 创建前导入模型（避免在函数顶层引用）
    # 已在模块顶部导入

    with Session(engine) as session:
        # ---- 可选：重置 ----
        if reset:
            print("\n⚠️  重置模式：清理已有种子数据...")
            # 先解除关联
            admin_result = session.execute(select(User).where(User.username == "admin"))
            admin_user = admin_result.scalar_one_or_none()
            if admin_user:
                admin_user.roles.clear()

            super_admin_result = session.execute(
                select(Role).where(Role.name == SUPER_ADMIN_ROLE_NAME)
            )
            super_admin_role = super_admin_result.scalar_one_or_none()
            if super_admin_role:
                super_admin_role.permissions.clear()

            session.execute(Permission.__table__.delete())
            session.execute(Role.__table__.delete())
            session.execute(User.__table__.delete())
            session.commit()
            print("  ✅ 已清理所有种子数据\n")

        # ---- 1. 创建所有权限 ----
        print("📋 步骤 1/3: 创建权限定义...")
        permissions = {}
        for code, name, description, module in ALL_PERMISSIONS:
            perm = get_or_create_permission(session, code, name, description, module)
            permissions[code] = perm
        session.flush()

        # ---- 2. 创建超级管理员角色并关联所有权限 ----
        print("\n📋 步骤 2/3: 创建超级管理员角色...")
        result = session.execute(select(Role).where(Role.name == SUPER_ADMIN_ROLE_NAME))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(
                name=SUPER_ADMIN_ROLE_NAME,
                description="拥有系统所有权限，可管理账号和角色配置",
                is_system=True,
            )
            session.add(role)
            session.flush()
            print(f"  ✅ 创建角色: {SUPER_ADMIN_ROLE_NAME}")
        else:
            print(f"  ⏭️  角色已存在: {SUPER_ADMIN_ROLE_NAME}")

        # 关联所有权限
        for perm in permissions.values():
            if perm not in role.permissions:
                role.permissions.append(perm)
        print(f"  ✅ 已关联 {len(permissions)} 个权限")
        session.flush()

        # ---- 3. 创建 admin 用户并分配超级管理员角色 ----
        print("\n📋 步骤 3/3: 创建 admin 用户...")
        result = session.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()
        if admin is None:
            hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt())
            admin = User(
                username="admin",
                password_hash=hashed.decode(),
                email="admin@platform.com",
                real_name="系统管理员",
                is_active=True,
                is_system=True,
            )
            session.add(admin)
            session.flush()
            admin.roles.append(role)
            print("  ✅ 创建 admin 用户 (admin/admin123)")
            print(f"  ✅ 已分配角色: {SUPER_ADMIN_ROLE_NAME}")
        else:
            print("  ⏭️  admin 用户已存在")
            # 确保 admin 有超级管理员角色
            if role not in admin.roles:
                admin.roles.append(role)
                print(f"  ✅ 已为 admin 补充角色: {SUPER_ADMIN_ROLE_NAME}")
            else:
                print(f"  ⏭️  admin 已有角色: {SUPER_ADMIN_ROLE_NAME}")

        session.commit()
        print("\n✅ 种子数据初始化完成!")
        print(f"   登录账号: admin")
        print(f"   登录密码: admin123")
        print(f"   角色: {SUPER_ADMIN_ROLE_NAME}")
        print(f"   权限数: {len(permissions)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="初始化种子数据")
    parser.add_argument(
        "--reset", action="store_true", help="清空已有种子数据后重新创建"
    )
    args = parser.parse_args()

    try:
        seed(reset=args.reset)
    except Exception as e:
        print(f"❌ 错误：{e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
