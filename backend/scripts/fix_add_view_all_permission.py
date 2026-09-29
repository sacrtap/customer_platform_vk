"""给数据库补上 customers:view_all 权限并同步到超级管理员角色

背景：seed.py 的 ALL_PERMISSIONS 已包含 customers:view_all（查看全部客户），
但 seed 只在空库初始化时插入权限；已存在的数据库不会自动补建，导致：
1. 角色权限配置页（GET /permissions 查库）看不到「查看全部客户」；
2. 超级管理员角色的 role_permissions 也未关联该权限（seed 关联「所有权限」同样只在初始化时执行）。

本脚本幂等：权限已存在则跳过插入；超级管理员已关联则跳过关联。
预置角色（运营经理/销售经理）默认不授 customers:view_all，保持数据可见性约束。
"""

import asyncio
import sys
from pathlib import Path

# 支持从仓库根或 backend 目录直接运行：backend/ 需在 import 路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

PERMISSION = ("customers:view_all", "查看全部客户", "不受经理可见性约束，查看全部客户", "customers")


async def fix():
    engine = create_async_engine(
        settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    session = async_session()
    try:
        # 1. 插入权限（幂等）
        perm = (
            (
                await session.execute(
                    select(text("*")).select_from(text("permissions")).where(text("code = :code")),
                    {"code": PERMISSION[0]},
                )
            )
            .mappings()
            .first()
        )
        if perm:
            print(f"⏭️  权限已存在: {PERMISSION[0]} (id={perm['id']})")
            perm_id = perm["id"]
        else:
            result = await session.execute(
                text(
                    "INSERT INTO permissions (code, name, description, module, created_at, updated_at) "
                    "VALUES (:code, :name, :description, :module, NOW(), NOW()) "
                    "RETURNING id"
                ),
                {
                    "code": PERMISSION[0],
                    "name": PERMISSION[1],
                    "description": PERMISSION[2],
                    "module": PERMISSION[3],
                },
            )
            perm_id = result.scalar_one()
            print(f"✅ 已创建权限: {PERMISSION[0]} ({PERMISSION[1]}) id={perm_id}")

        # 2. 超级管理员角色关联该权限（幂等）
        role = (
            (
                await session.execute(
                    select(text("*")).select_from(text("roles")).where(text("name = :name")),
                    {"name": "超级管理员"},
                )
            )
            .mappings()
            .first()
        )
        if not role:
            print("⚠️  未找到超级管理员角色，跳过角色关联")
        else:
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
                print(f"⏭️  超级管理员已关联 {PERMISSION[0]} (role_id={role['id']})")
            else:
                await session.execute(
                    text(
                        "INSERT INTO role_permissions (role_id, permission_id) VALUES (:rid, :pid)"
                    ),
                    {"rid": role["id"], "pid": perm_id},
                )
                print(f"✅ 超级管理员已关联 {PERMISSION[0]} (role_id={role['id']})")

        await session.commit()
        print("Done!")
    finally:
        await session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(fix())
