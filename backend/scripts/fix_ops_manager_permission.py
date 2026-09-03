"""给运营经理和销售经理角色补上 users:view 权限

修复 bug：运营经理角色编辑客户时，销售经理/运营经理下拉选项不显示。
根因：GET /users 路由需要 users:view 权限，运营经理角色缺少此权限。
"""

import asyncio

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.users import Permission, Role


async def fix():
    engine = create_async_engine(
        settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    session = async_session()
    try:
        # 查找 users:view 权限
        perm = (
            await session.execute(select(Permission).where(Permission.code == "users:view"))
        ).scalar_one_or_none()
        if not perm:
            print("ERROR: users:view permission not found in database")
            return

        # 给运营经理和销售经理角色都补上 users:view
        for role_name in ["运营经理", "销售经理"]:
            role = (
                await session.execute(select(Role).where(Role.name == role_name))
            ).scalar_one_or_none()
            if not role:
                print(f"WARNING: {role_name} role not found, skipping")
                continue

            existing = (
                await session.execute(
                    text(
                        "SELECT 1 FROM role_permissions "
                        "WHERE role_id = :rid AND permission_id = :pid"
                    ),
                    {"rid": role.id, "pid": perm.id},
                )
            ).fetchone()

            if existing:
                print(f"{role_name} already has users:view (role_id={role.id})")
            else:
                await session.execute(
                    text(
                        "INSERT INTO role_permissions (role_id, permission_id) VALUES (:rid, :pid)"
                    ),
                    {"rid": role.id, "pid": perm.id},
                )
                print(f"Added users:view to {role_name} (role_id={role.id})")

        await session.commit()
        print("Done!")
    finally:
        await session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(fix())
