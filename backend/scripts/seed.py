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

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

# 导入模型（在 sys.path 设置之后）
from app.models.users import User, Role, Permission
from app.models.billing import AuditLog
from app.models.customers import Customer

# 从环境变量读取数据库 URL，默认本地 PostgreSQL（无密码，使用当前系统用户）
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost/customer_platform",
)

# ============================================================
# 权限定义（与前端路由 requiresPermission 和后端 require_permission 保持一致）
# ============================================================
ALL_PERMISSIONS = [
    # ============================================================
    # 客户管理 (6)
    # ============================================================
    ("customers:view", "查看客户", "查看客户列表和详情", "customers"),
    ("customers:create", "新建客户", "创建新客户记录", "customers"),
    ("customers:edit", "编辑客户", "修改客户信息", "customers"),
    ("customers:delete", "删除客户", "删除客户记录", "customers"),
    ("customers:export", "导出客户", "导出 Excel 数据", "customers"),
    ("customers:import", "导入客户", "批量导入数据", "customers"),
    # ============================================================
    # 结算管理 (8)
    # ============================================================
    ("billing:view", "查看结算", "查看余额和定价规则", "billing"),
    ("billing:edit", "编辑结算", "修改定价规则", "billing"),
    ("billing:delete", "删除定价", "删除定价规则", "billing"),
    ("billing:recharge", "充值操作", "执行客户充值", "billing"),
    ("billing:refund", "退款操作", "执行退款", "billing"),
    ("billing:export", "导出账单", "导出结算数据", "billing"),
    ("billing:confirm", "确认结算单", "确认客户结算单（限商务/运营经理）", "billing"),
    ("billing:pay", "结算付款", "标记付款和完成结算", "billing"),
    # ============================================================
    # 客户分析 (4)
    # ============================================================
    ("analytics:view", "查看分析", "查看所有分析报表", "analytics"),
    ("analytics:export", "导出报表", "导出分析数据", "analytics"),
    ("analytics:forecast_edit", "编辑预测", "修改预测模型参数", "analytics"),
    ("analytics:profile_tag_edit", "编辑画像标签", "管理画像标签关联", "analytics"),
    # ============================================================
    # 标签管理 (4)
    # ============================================================
    ("tags:view", "查看标签", "查看标签列表", "tags"),
    ("tags:create", "新建标签", "创建新标签", "tags"),
    ("tags:edit", "编辑标签", "修改标签", "tags"),
    ("tags:delete", "删除标签", "删除标签", "tags"),
    # ============================================================
    # 用户管理 (5)
    # ============================================================
    ("users:view", "查看用户", "查看用户列表", "users"),
    ("users:create", "新建用户", "创建新用户", "users"),
    ("users:edit", "编辑用户", "修改用户信息", "users"),
    ("users:delete", "删除用户", "删除用户", "users"),
    ("users:role_assign", "分配角色", "给用户分配角色", "users"),
    # ============================================================
    # 角色权限 (5)
    # ============================================================
    ("roles:view", "查看角色", "查看角色列表", "roles"),
    ("roles:create", "新建角色", "创建新角色", "roles"),
    ("roles:edit", "编辑角色", "修改角色信息", "roles"),
    ("roles:delete", "删除角色", "删除自定义角色", "roles"),
    ("roles:assign", "分配权限", "为角色分配权限", "roles"),
    # ============================================================
    # 系统管理 (3)
    # ============================================================
    ("system:view", "查看系统", "查看同步/审计日志", "system"),
    ("system:export", "导出日志", "导出系统日志", "system"),
    ("system:settings", "系统设置", "修改系统配置", "system"),
    # ============================================================
    # 客户画像 (2)
    # ============================================================
    ("profiles:view", "查看画像", "查看客户画像信息", "profiles"),
    ("profiles:edit", "编辑画像", "修改客户画像等级", "profiles"),
    # ============================================================
    # 其他模块 (4)
    # ============================================================
    ("groups:view", "查看分组", "查看客户分组", "groups"),
    ("groups:manage", "管理分组", "创建/编辑/删除分组", "groups"),
    ("files:view", "查看文件", "查看和下载文件", "files"),
    ("files:upload", "上传文件", "上传新文件", "files"),
    ("files:delete", "删除文件", "删除文件", "files"),
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
            # 使用 TRUNCATE CASCADE 一次性清理所有关联数据
            session.execute(
                text(
                    "TRUNCATE users, user_roles, roles, role_permissions, permissions, audit_logs, customers CASCADE"
                )
            )
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
