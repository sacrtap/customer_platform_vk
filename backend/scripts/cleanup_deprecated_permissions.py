#!/usr/bin/env python3
"""
清理已弃用的权限记录

删除数据库中历史遗留的已弃用粗粒度权限，这些权限
已在 seed.py 中被移除，不再被任何业务逻辑使用。

用法:
    python scripts/cleanup_deprecated_permissions.py
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 加载 .env 文件
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

# 从环境变量读取数据库 URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost/customer_platform",
)

# 已弃用的权限码列表
DEPRECATED_PERMISSIONS = [
    "customers:manage",
    "billing:manage",
    "users:manage",
    "roles:manage",
    "tags:manage",
]


def cleanup():
    """执行清理"""
    print(f"连接到数据库：{DATABASE_URL}")

    # 使用同步引擎
    engine = create_engine(
        DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    )

    with Session(engine) as session:
        from app.models.users import Permission, Role, role_permissions

        # ---- 1. 查找仍存在的弃用权限 ----
        print("\n📋 步骤 1: 查找弃用权限...")
        result = session.execute(
            select(Permission).where(Permission.code.in_(DEPRECATED_PERMISSIONS))
        )
        deprecated_perms = list(result.scalars().all())

        if not deprecated_perms:
            print("  ✅ 未发现任何弃用权限，数据库已是最新状态")
            return

        print(f"  ⚠️  发现 {len(deprecated_perms)} 个弃用权限:")
        for perm in deprecated_perms:
            print(f"     - {perm.code} ({perm.name})")

        # ---- 2. 检查关联角色 ----
        print("\n📋 步骤 2: 检查关联角色...")
        for perm in deprecated_perms:
            # 查询哪些角色关联了此权限
            roles_query = session.execute(
                select(Role)
                .join(role_permissions, Role.id == role_permissions.c.role_id)
                .where(role_permissions.c.permission_id == perm.id)
            )
            associated_roles = list(roles_query.scalars().all())
            if associated_roles:
                role_names = ", ".join(r.name for r in associated_roles)
                print(f"  ⚠️  '{perm.code}' 被以下角色关联: {role_names}")
            else:
                print(f"  ✅ '{perm.code}' 无角色关联")

        # ---- 3. 从角色中移除弃用权限 ----
        print("\n📋 步骤 3: 清理角色关联...")
        for perm in deprecated_perms:
            # 删除 role_permissions 关联记录
            deleted = session.execute(
                text("DELETE FROM role_permissions WHERE permission_id = :perm_id"),
                {"perm_id": perm.id},
            )
            if deleted.rowcount > 0:
                print(f"  ✅ 从 {deleted.rowcount} 个角色中移除 '{perm.code}'")
            else:
                print(f"  ⏭️  '{perm.code}' 无角色关联，跳过")

        # ---- 4. 删除弃用权限记录 ----
        print("\n📋 步骤 4: 删除权限记录...")
        for perm in deprecated_perms:
            session.delete(perm)
            print(f"  🗑️  已删除 '{perm.code}'")

        # ---- 5. 提交 ----
        session.commit()

        print(f"\n✅ 清理完成!")
        print(f"   删除权限数: {len(deprecated_perms)}")
        print(f"   权限代码: {', '.join(p.code for p in deprecated_perms)}")


if __name__ == "__main__":
    try:
        cleanup()
    except Exception as e:
        print(f"\n❌ 清理失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
