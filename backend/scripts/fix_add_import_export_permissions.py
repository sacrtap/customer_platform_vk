"""给存量库补 13 个管理页导入/导出权限码并关联角色

背景：seed.py 的 ALL_PERMISSIONS 已追加用户/标签/角色/行业类型/合作状态/
余额白名单的 import+export 与 API-Key 的 export 共 13 个权限码，但 seed 只在
空库初始化时插入权限；已存在的数据库不会自动补建，导致：
1. 角色权限配置页（GET /permissions 查库）看不到新权限码；
2. 超级管理员/预置角色的 role_permissions 也未关联（seed 的关联同样只在初始化时执行）。

本脚本幂等：权限已存在则跳过插入；角色已关联则跳过关联，可重复执行。
授权策略（与 seed.py PRESET_ROLES 一致）：
- 超级管理员关联全部 13 个新权限码；
- 运营经理关联 7 个模块的 export（与既有 billing:*_export 惯例对齐）；
- 销售经理关联 tags/users/roles/balance_whitelist 的 export；
- import 属管理操作，预置角色一律不预授，由角色管理页按需显式授予。

权限码清单从 seed.ALL_PERMISSIONS 按 module + 后缀派生，不硬编码，避免与 seed 漂移。
"""

import asyncio
import sys
from pathlib import Path

# 支持从仓库根或 backend 目录直接运行：backend/ 需在 import 路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from scripts.seed import ALL_PERMISSIONS

SUPER_ADMIN_ROLE_NAME = "超级管理员"

# 本次新增 import/export 权限所属的 module（用于从 ALL_PERMISSIONS 过滤，排除 customers/billing 既有码）
NEW_MODULES = {
    "tags",
    "users",
    "roles",
    "industry_types",
    "cooperation_statuses",
    "balance_whitelist",
    "api_keys",
}

# 预置角色默认授予的导出权限（import 不预授，属管理操作）
PRESET_ROLE_EXPORTS: dict[str, list[str]] = {
    "运营经理": [
        "tags:export",
        "users:export",
        "roles:export",
        "industry_types:export",
        "cooperation_statuses:export",
        "balance_whitelist:export",
        "api_keys:export",
    ],
    "销售经理": ["tags:export", "users:export", "roles:export", "balance_whitelist:export"],
}


def new_import_export_permissions() -> list[tuple[str, str, str, str]]:
    """从 seed 权威清单派生本次新增的 13 个导入/导出权限码（4 元组）。

    后缀匹配 `:import` / `:export`（权限码为 module:action 格式，如 tags:import）；
    module 限定 NEW_MODULES，排除 customers/billing/analytics 等既有的 import/export 码。
    """
    return [
        p for p in ALL_PERMISSIONS if p[0].endswith((":import", ":export")) and p[3] in NEW_MODULES
    ]


async def fix():
    engine = create_async_engine(
        settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    session = async_session()
    try:
        # 1. 插入权限码（幂等）
        perm_ids: dict[str, int] = {}
        for code, name, description, module in new_import_export_permissions():
            perm = (
                (
                    await session.execute(
                        select(text("*"))
                        .select_from(text("permissions"))
                        .where(text("code = :code")),
                        {"code": code},
                    )
                )
                .mappings()
                .first()
            )
            if perm:
                print(f"⏭️  权限已存在: {code} (id={perm['id']})")
                perm_ids[code] = perm["id"]
            else:
                result = await session.execute(
                    text(
                        "INSERT INTO permissions (code, name, description, module, created_at, updated_at) "
                        "VALUES (:code, :name, :description, :module, NOW(), NOW()) "
                        "RETURNING id"
                    ),
                    {"code": code, "name": name, "description": description, "module": module},
                )
                perm_ids[code] = result.scalar_one()
                print(f"✅ 已创建权限: {code} ({name}) id={perm_ids[code]}")

        # 2. 角色关联（幂等）：超级管理员全量 + 预置角色的 export 子集
        role_grants: dict[str, list[str]] = {
            SUPER_ADMIN_ROLE_NAME: list(perm_ids.keys()),
            **PRESET_ROLE_EXPORTS,
        }
        for role_name, codes in role_grants.items():
            role = (
                (
                    await session.execute(
                        select(text("*")).select_from(text("roles")).where(text("name = :name")),
                        {"name": role_name},
                    )
                )
                .mappings()
                .first()
            )
            if not role:
                print(f"⚠️  未找到角色「{role_name}」，跳过关联")
                continue
            for code in codes:
                perm_id = perm_ids.get(code)
                if perm_id is None:
                    continue
                existing = (
                    await session.execute(
                        text(
                            "SELECT 1 FROM role_permissions "
                            "WHERE role_id = :rid AND permission_id = :pid"
                        ),
                        {"rid": role["id"], "pid": perm_id},
                    )
                ).fetchone()
                if existing:
                    print(f"⏭️  {role_name}已关联 {code} (role_id={role['id']})")
                else:
                    await session.execute(
                        text(
                            "INSERT INTO role_permissions (role_id, permission_id) "
                            "VALUES (:rid, :pid)"
                        ),
                        {"rid": role["id"], "pid": perm_id},
                    )
                    print(f"✅ {role_name}已关联 {code} (role_id={role['id']})")

        await session.commit()
        print("Done!")
    finally:
        await session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(fix())
