#!/usr/bin/env python3
"""
清理已弃用的权限记录

删除数据库中历史遗留的已弃用粗粒度权限，这些权限
已在 seed.py 中被移除，不再被任何业务逻辑使用。

用法:
    python scripts/cleanup_deprecated_permissions.py
"""

import os
import pathlib
import sys

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

# 代码引用扫描范围：后端 app 与前端 src（容器内无 frontend 时仅扫后端）
BACKEND_APP_DIR = pathlib.Path(__file__).resolve().parent.parent / "app"
FRONTEND_SRC_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend" / "src"

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
    # 2026-09-16 角色权限清单修正：孤儿权限（前端/后端均无对应功能）
    "billing:refund",
    "system:settings",
    "webhooks:manage",
    "profiles:view",
    "profiles:edit",
    "system:export",
    "files:upload",
    # 历史迁移残留：profiles:* 已迁移至 analytics:*（8d87a55），数据库中仍有该孤儿
    "profiles:export",
]

# 扫描代码中仍引用的权限 code，防止误删在用权限
SCAN_EXTENSIONS = {".py", ".ts", ".tsx", ".vue", ".js", ".jsx"}
# 跳过目录（虚拟环境、构建产物、测试辅助缓存）
SKIP_DIR_PARTS = {
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "coverage",
}


def find_code_references(code: str) -> list[pathlib.Path]:
    """在 backend/app 与 frontend/src 中查找仍引用该权限 code 的文件

    匹配后端装饰器 require_permission("code") 与前端 can('code') / hasPermission('code')。
    返回引用文件列表；空列表表示无引用，可安全删除。
    """
    patterns = (
        f'require_permission("{code}")',
        f"require_permission('{code}')",
        f"can('{code}')",
        f'can("{code}")',
        f"hasPermission('{code}')",
        f'hasPermission("{code}")',
    )
    referenced: list[pathlib.Path] = []
    for base_dir in (BACKEND_APP_DIR, FRONTEND_SRC_DIR):
        if not base_dir.is_dir():
            continue
        for path in base_dir.rglob("*"):
            if not path.is_file() or path.suffix not in SCAN_EXTENSIONS:
                continue
            if any(part in SKIP_DIR_PARTS for part in path.parts):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(pattern in content for pattern in patterns):
                referenced.append(path)
    return referenced


def cleanup():
    """执行清理"""
    print(f"连接到数据库：{DATABASE_URL}")

    # 使用同步引擎
    engine = create_engine(DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))

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

        # ---- 1.5 代码引用校验：仍被代码引用的权限跳过删除 ----
        print("\n📋 步骤 1.5: 校验代码引用（防止误删在用权限）...")
        safe_perms = []
        for perm in deprecated_perms:
            refs = find_code_references(perm.code)
            if refs:
                ref_desc = ", ".join(str(p) for p in refs[:5])
                extra = f" 等 {len(refs)} 个文件" if len(refs) > 5 else ""
                print(f"  ⚠️  '{perm.code}' 仍被代码引用: {ref_desc}{extra}")
                print("     ⏭️  跳过删除（请先清理代码引用后再弃用）")
            else:
                safe_perms.append(perm)
                print(f"  ✅ '{perm.code}' 无代码引用，可安全删除")

        deprecated_perms = safe_perms
        if not deprecated_perms:
            print("  ⏭️  所有弃用权限均仍被代码引用，无权限可删除")
            return

        print(
            f"\n  📌 待删除 {len(deprecated_perms)} 个权限: {', '.join(p.code for p in deprecated_perms)}"
        )

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
                role_names = ", ".join(r.name for r in associated_roles)  # pyright: ignore[reportArgumentType, reportCallIssue]
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
            if deleted.rowcount > 0:  # pyright: ignore[reportAttributeAccessIssue]
                print(f"  ✅ 从 {deleted.rowcount} 个角色中移除 '{perm.code}'")  # pyright: ignore[reportAttributeAccessIssue]
            else:
                print(f"  ⏭️  '{perm.code}' 无角色关联，跳过")

        # ---- 4. 删除弃用权限记录 ----
        print("\n📋 步骤 4: 删除权限记录...")
        for perm in deprecated_perms:
            session.delete(perm)
            print(f"  🗑️  已删除 '{perm.code}'")

        # ---- 5. 提交 ----
        session.commit()

        print("\n✅ 清理完成!")
        print(f"   删除权限数: {len(deprecated_perms)}")
        print(f"   权限代码: {', '.join(p.code for p in deprecated_perms)}")  # pyright: ignore[reportArgumentType, reportCallIssue]


if __name__ == "__main__":
    try:
        cleanup()
    except Exception as e:
        print(f"\n❌ 清理失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
