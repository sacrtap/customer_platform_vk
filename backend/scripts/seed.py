#!/usr/bin/env python3
"""
初始化种子数据脚本
创建 admin 超级管理员用户、所有权限定义、以及超级管理员角色。

用法:
    python scripts/seed.py
    python scripts/seed.py --reset   # 清空已有种子数据后重新创建
"""

import argparse
import asyncio
import os
import sys

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
from app.models.users import Permission, Role, User

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
    # 结算管理 (16)
    # ============================================================
    ("billing:view", "查看结算", "查看余额和定价规则", "billing"),
    ("billing:edit", "编辑结算", "修改定价规则", "billing"),
    ("billing:delete", "删除定价", "删除定价规则", "billing"),
    ("billing:recharge", "充值操作", "执行客户充值", "billing"),
    ("billing:balance_import", "导入余额", "批量导入充值数据", "billing"),
    ("billing:balance_export", "导出余额", "导出客户余额数据", "billing"),
    ("billing:pricing_import", "导入计费规则", "批量导入计费规则", "billing"),
    ("billing:pricing_export", "导出计费规则", "导出计费规则数据", "billing"),
    ("billing:package_import", "导入包年套餐", "批量导入包年套餐", "billing"),
    ("billing:package_export", "导出包年套餐", "导出包年套餐数据", "billing"),
    ("billing:invoice_import", "导入结算单", "批量导入外部结算单", "billing"),
    ("billing:invoice_export", "导出结算单", "导出结算单数据", "billing"),
    ("billing:confirm", "确认结算单", "确认客户结算单（限商务/运营经理）", "billing"),
    ("billing:pay", "结算付款", "标记付款和完成结算", "billing"),
    ("billing:ops_approve", "运营经理确认", "运营经理确认结算单（第一步）", "billing"),
    ("billing:sales_approve", "销售经理确认", "销售经理确认结算单（第二步）", "billing"),
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
    # 系统管理 (2)
    # ============================================================
    ("system:view", "查看系统", "查看同步/审计日志", "system"),
    ("system:database_clear", "数据清空", "清空客户及关联数据", "system"),
    # ============================================================
    # 其他模块 (2)
    # ============================================================
    ("files:view", "查看文件", "查看和下载文件", "files"),
    ("files:delete", "删除文件", "删除文件", "files"),
    # ============================================================
    # 行业类型管理 (1)
    # ============================================================
    ("industry_types:manage", "管理行业类型", "新增/编辑/删除行业类型", "system"),
    # ============================================================
    # 合作状态管理 (1)
    # ============================================================
    ("cooperation_statuses:manage", "管理合作状态", "新增/编辑/删除合作状态", "system"),
    # ============================================================
    # ERP 系统管理 (1)
    # ============================================================
    ("erp_systems:manage", "管理ERP系统", "新增/编辑/删除ERP系统", "system"),
    # ============================================================
    # API-Key 管理 (1)
    # ============================================================
    ("api_keys:manage", "管理API-Key", "申请/查看/停用/删除API-Key", "system"),
    # ============================================================
    # 定时同步配置 (1)
    # ============================================================
    ("system:sync_schedule", "配置定时同步", "配置每日自动同步（开启/关闭/时间/模式）", "system"),
]

# 超级管理员角色名称
SUPER_ADMIN_ROLE_NAME = "超级管理员"

# 预置业务角色定义：角色名 → (描述, 权限 code 列表)
PRESET_ROLES = {
    "运营经理": (
        "负责客户日常运营，可确认结算单（第一步）",
        [
            "customers:view",
            "customers:edit",
            "users:view",
            "billing:view",
            "billing:edit",
            "billing:balance_export",
            "billing:pricing_export",
            "billing:package_export",
            "billing:invoice_export",
            "billing:recharge",
            "billing:ops_approve",
            "billing:confirm",
            "analytics:view",
            "tags:view",
        ],
    ),
    "销售经理": (
        "负责客户商务对接，可确认结算单（第二步）",
        [
            "customers:view",
            "billing:view",
            "billing:balance_export",
            "billing:pricing_export",
            "billing:package_export",
            "billing:invoice_export",
            "billing:sales_approve",
            "analytics:view",
        ],
    ),
}


def get_or_create_permission(session: Session, code: str, name: str, description: str, module: str):
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
    engine = create_engine(DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))

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

        # ---- 2.1 创建预置业务角色（运营经理、销售经理）----
        print("\n📋 步骤 2.5/3: 创建预置业务角色...")
        for role_name, (role_desc, perm_codes) in PRESET_ROLES.items():
            result = session.execute(select(Role).where(Role.name == role_name))
            biz_role = result.scalar_one_or_none()
            if biz_role is None:
                biz_role = Role(
                    name=role_name,
                    description=role_desc,
                    is_system=True,
                )
                session.add(biz_role)
                session.flush()
                print(f"  ✅ 创建角色: {role_name}")
            else:
                print(f"  ⏭️  角色已存在: {role_name}")

            # 关联指定权限
            for code in perm_codes:
                perm = permissions.get(code)
                if perm is None:
                    # PRESET_ROLES 引用了 ALL_PERMISSIONS 之外的权限码（映射笔误）。
                    # 若静默跳过，角色会静默缺权限且无任何报错，故显式失败。
                    raise ValueError(f"预置角色 {role_name} 引用了未定义的权限码: {code}")
                if perm not in biz_role.permissions:
                    biz_role.permissions.append(perm)
            print(f"  ✅ {role_name} 已关联 {len(perm_codes)} 个权限")
        session.flush()

        # ---- 2.6 存量权限迁移：旧粗粒度码 → 新细粒度码（等价迁移） ----
        print("\n📋 步骤 2.6/3: 迁移存量权限绑定（旧码 → 新码）...")
        # 旧码 → 新码等价映射（方向内全量授予，保证权限范围不缩水）
        LEGACY_TO_NEW_PERMISSIONS = {
            "billing:export": [
                "billing:balance_export",
                "billing:pricing_export",
                "billing:package_export",
                "billing:invoice_export",
            ],
            # billing:import 历史上仅用于「导入余额」端点，等价语义仅为 balance_import；
            # 其余导入码（pricing/package/invoice）敏感度更高，需角色管理显式授予，避免权限膨胀
            "billing:import": [
                "billing:balance_import",
            ],
        }
        migrated_count = 0
        all_roles = session.execute(select(Role)).scalars().all()
        for legacy_code, new_codes in LEGACY_TO_NEW_PERMISSIONS.items():
            for role in all_roles:
                role_codes = {p.code for p in role.permissions}
                if legacy_code not in role_codes:
                    continue
                for new_code in new_codes:
                    new_perm = permissions.get(new_code)
                    if new_perm is None:
                        # LEGACY_TO_NEW_PERMISSIONS 引用了 ALL_PERMISSIONS 之外的权限码
                        # （映射笔误）。若静默跳过，步骤 2.7 又会无条件删除旧码 → 角色
                        # 权限被静默降权且不可逆，故显式失败。
                        raise ValueError(
                            f"迁移映射引用了未定义的权限码: {new_code}（旧码 {legacy_code}）"
                        )
                    if new_perm not in role.permissions:
                        role.permissions.append(new_perm)
                        migrated_count += 1
        if migrated_count:
            session.flush()
            print(f"  ✅ 迁移完成：为 {migrated_count} 个旧权限绑定授予等价新码")
        else:
            print("  ⏭️  无旧权限码绑定，跳过迁移")

        # ---- 2.7 清理废弃的旧权限码记录（等价授予已完成，避免权限清单出现僵尸权限） ----
        removed_count = 0
        for legacy_code in LEGACY_TO_NEW_PERMISSIONS:
            legacy_perm = session.execute(
                select(Permission).where(Permission.code == legacy_code)
            ).scalar_one_or_none()
            if legacy_perm is None:
                continue
            for role in all_roles:
                if legacy_perm in role.permissions:
                    role.permissions.remove(legacy_perm)
            session.delete(legacy_perm)
            removed_count += 1
        if removed_count:
            session.flush()
            print(f"  ✅ 清理废弃权限码 {removed_count} 个")
        else:
            print("  ⏭️  无废弃权限码，跳过清理")

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

        # ---- 失效 Redis 权限缓存 ----
        # 步骤 2.6/2.7 迁移改变了角色→权限绑定（授新细粒度码、删旧码），但
        # PermissionCache（key `cache:permissions:{user_id}`，TTL 600s）仍缓存旧权限
        # 集合：若不失效，迁移前已登录用户在最长 10 分钟内访问结算导入/导出端点会因
        # 命中旧码集合持续 403。故提交成功后全量失效权限缓存。
        try:
            # cache_service 是 async（底层 redis.asyncio），而本脚本是同步脚本：
            # 用 asyncio.run 临时起一个事件循环执行失效即可，进程随后退出。
            # 延迟导入，避免在测试收集期（import seed.py）引入额外应用栈副作用。
            from app.cache.base import cache_service

            asyncio.run(cache_service.invalidate_pattern("cache:permissions:*"))
            print("  ✅ 已失效权限缓存 cache:permissions:*")
        except Exception as e:
            # Redis 不可用不应阻断种子初始化，仅提示运维手动失效。
            print(
                "  ⚠️  权限缓存失效失败，请手动清理 cache:permissions:* "
                f"（redis-cli --scan --pattern 'cache:permissions:*' | xargs redis-cli DEL）：{e}"
            )

        print("\n✅ 种子数据初始化完成!")
        print("   登录账号: admin")
        print("   登录密码: admin123")
        print(f"   角色: {SUPER_ADMIN_ROLE_NAME}")
        print(f"   权限数: {len(permissions)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="初始化种子数据")
    parser.add_argument("--reset", action="store_true", help="清空已有种子数据后重新创建")
    args = parser.parse_args()

    try:
        seed(reset=args.reset)
    except Exception as e:
        print(f"❌ 错误：{e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
