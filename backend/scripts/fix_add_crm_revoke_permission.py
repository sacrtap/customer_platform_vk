"""给存量库补 `crm_recharge:revoke` 权限并关联超级管理员（幂等）

背景：撤销 CRM 充值导入是新增权限点，`seed.py` 只在空库初始化时插入权限；
存量库不会自动补建，导致角色权限配置页看不到该权限码、超级管理员也无法调用
`POST /crm-recharge/payments/<id>/import/revoke`（后端按 DB 中的 role_permissions 判定）。

授权策略：**只关联超级管理员**。强制撤销涉及资金回退与线下核对，不预授给预置业务角色，
由管理员在角色管理页显式授予。

用法：
    cd backend && .venv/bin/python scripts/fix_add_crm_revoke_permission.py
"""

import asyncio
import sys
from pathlib import Path

# 支持从仓库根或 backend 目录直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.constants.roles import SUPER_ADMIN_ROLE_NAME
from scripts.seed import ALL_PERMISSIONS

PERMISSION_CODE = "crm_recharge:revoke"


def permission_meta() -> tuple[str, str, str, str]:
    for item in ALL_PERMISSIONS:
        if item[0] == PERMISSION_CODE:
            return item
    raise SystemExit(f"seed.ALL_PERMISSIONS 缺少 {PERMISSION_CODE}，请先更新 seed")


async def fix():
    engine = create_async_engine(
        settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    session = async_session()
    try:
        code, name, description, module = permission_meta()

        row = (
            (
                await session.execute(
                    select(text("*")).select_from(text("permissions")).where(text("code = :code")),
                    {"code": code},
                )
            )
            .mappings()
            .first()
        )
        if row:
            perm_id = row["id"]
            print(f"⏭️  权限已存在: {code} (id={perm_id})")
        else:
            result = await session.execute(
                text(
                    "INSERT INTO permissions "
                    "(code, name, description, module, created_at, updated_at) "
                    "VALUES (:code, :name, :description, :module, NOW(), NOW()) RETURNING id"
                ),
                {"code": code, "name": name, "description": description, "module": module},
            )
            perm_id = result.scalar_one()
            print(f"✅ 已创建权限: {code} ({name}) id={perm_id}")

        role = (
            (
                await session.execute(
                    select(text("*")).select_from(text("roles")).where(text("name = :name")),
                    {"name": SUPER_ADMIN_ROLE_NAME},
                )
            )
            .mappings()
            .first()
        )
        if not role:
            print(f"⚠️  未找到角色「{SUPER_ADMIN_ROLE_NAME}」，跳过关联")
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
                print(f"⏭️  {SUPER_ADMIN_ROLE_NAME}已关联 {code}")
            else:
                await session.execute(
                    text(
                        "INSERT INTO role_permissions (role_id, permission_id) VALUES (:rid, :pid)"
                    ),
                    {"rid": role["id"], "pid": perm_id},
                )
                print(f"✅ {SUPER_ADMIN_ROLE_NAME}已关联 {code}")

        await session.commit()

        # 权限缓存按用户维度缓存，改权限后必须失效，否则最长要等 TTL 才生效
        try:
            from app.cache.permissions import permission_cache

            user_ids = (
                (
                    await session.execute(
                        text(
                            "SELECT u.id FROM users u "
                            "JOIN user_roles ur ON ur.user_id = u.id "
                            "JOIN roles r ON r.id = ur.role_id "
                            "WHERE r.name = :name AND u.deleted_at IS NULL"
                        ),
                        {"name": SUPER_ADMIN_ROLE_NAME},
                    )
                )
                .scalars()
                .all()
            )
            for user_id in user_ids:
                await permission_cache.invalidate(user_id)
            print(f"✅ 已失效 {len(user_ids)} 个超级管理员的权限缓存")
        except Exception as exc:  # pragma: no cover - Redis 不可用不影响数据修正
            print(f"⚠️  权限缓存失效失败（重启或等 TTL 后生效）: {exc}")

        print("Done!")
    finally:
        await session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(fix())
