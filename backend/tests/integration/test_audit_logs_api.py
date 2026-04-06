"""
Audit Logs API 集成测试

测试覆盖：
1. GET /api/v1/audit-logs - 获取审计日志列表、筛选审计日志
2. GET /api/v1/audit-logs/actions - 获取操作类型列表
3. GET /api/v1/audit-logs/modules - 获取模块列表
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_list_audit_logs_success(test_client, db_session: AsyncSession):
    """测试获取审计日志列表 - 成功场景"""
    username = "audit_list_user"
    password = "test123456"
    import bcrypt

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    await db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    await db_session.execute(
        text(
            "DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE username = :username)"
        ),
        {"username": username},
    )
    await db_session.commit()

    # 确保超级管理员角色存在
    await db_session.execute(
        text("""
        INSERT INTO roles (name, description, is_system, created_at)
        VALUES ('超级管理员', '拥有系统所有权限', true, NOW())
        ON CONFLICT (name) DO NOTHING
        """)
    )

    # 确保 system:audit_read 权限存在
    await db_session.execute(
        text("""
        INSERT INTO permissions (code, name, description, module, created_at)
        VALUES ('system:audit_read', '审计日志查看', '查看系统审计日志', 'system', NOW())
        ON CONFLICT (code) DO NOTHING
        """)
    )

    # 获取角色 ID 和权限 ID
    result = await db_session.execute(
        text("SELECT id FROM roles WHERE name = '超级管理员'")
    )
    role_id = result.scalar_one()
    result = await db_session.execute(
        text("SELECT id FROM permissions WHERE code = 'system:audit_read'")
    )
    perm_id = result.scalar_one()

    # 将权限关联到角色
    await db_session.execute(
        text("""
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES (:role_id, :perm_id)
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """),
        {"role_id": role_id, "perm_id": perm_id},
    )
    await db_session.commit()

    # 创建测试用户
    await db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "audit_list@example.com",
            "is_active": True,
        },
    )
    await db_session.commit()

    # 获取用户 ID 并分配角色
    result = await db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username},
    )
    user_id = result.scalar_one()

    await db_session.execute(
        text("""
        INSERT INTO user_roles (user_id, role_id)
        VALUES (:user_id, :role_id)
        ON CONFLICT (user_id, role_id) DO NOTHING
        """),
        {"user_id": user_id, "role_id": role_id},
    )
    await db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        request, response = await test_client.get(
            "/api/v1/audit-logs",
            headers=headers,
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "success"
        assert "data" in data
        assert "list" in data["data"]
        assert "total" in data["data"]
        assert "page" in data["data"]
        assert "page_size" in data["data"]
    finally:
        await db_session.execute(
            text(
                "DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE username = :username)"
            ),
            {"username": username},
        )
        await db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        await db_session.commit()


@pytest.mark.asyncio
async def test_list_audit_logs_with_filters(test_client, db_session: AsyncSession):
    """测试获取审计日志列表 - 带筛选条件"""
    username = "audit_filter_user"
    password = "test123456"
    import bcrypt

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    await db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    await db_session.execute(
        text(
            "DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE username = :username)"
        ),
        {"username": username},
    )
    await db_session.commit()

    # 确保超级管理员角色存在
    await db_session.execute(
        text("""
        INSERT INTO roles (name, description, is_system, created_at)
        VALUES ('超级管理员', '拥有系统所有权限', true, NOW())
        ON CONFLICT (name) DO NOTHING
        """)
    )

    # 确保 system:audit_read 权限存在
    await db_session.execute(
        text("""
        INSERT INTO permissions (code, name, description, module, created_at)
        VALUES ('system:audit_read', '审计日志查看', '查看系统审计日志', 'system', NOW())
        ON CONFLICT (code) DO NOTHING
        """)
    )

    # 获取角色 ID 和权限 ID
    result = await db_session.execute(
        text("SELECT id FROM roles WHERE name = '超级管理员'")
    )
    role_id = result.scalar_one()
    result = await db_session.execute(
        text("SELECT id FROM permissions WHERE code = 'system:audit_read'")
    )
    perm_id = result.scalar_one()

    # 将权限关联到角色
    await db_session.execute(
        text("""
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES (:role_id, :perm_id)
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """),
        {"role_id": role_id, "perm_id": perm_id},
    )
    await db_session.commit()

    # 创建测试用户
    await db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "audit_filter@example.com",
            "is_active": True,
        },
    )
    await db_session.commit()

    # 获取用户 ID 并分配角色
    result = await db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username},
    )
    user_id = result.scalar_one()

    await db_session.execute(
        text("""
        INSERT INTO user_roles (user_id, role_id)
        VALUES (:user_id, :role_id)
        ON CONFLICT (user_id, role_id) DO NOTHING
        """),
        {"user_id": user_id, "role_id": role_id},
    )
    await db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        result = await db_session.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": username},
        )
        filter_user_id = result.scalar_one()

        now = datetime.now()
        start_date = (now - timedelta(days=1)).isoformat()
        end_date = (now + timedelta(days=1)).isoformat()

        headers = {"Authorization": f"Bearer {token}"}
        request, response = await test_client.get(
            "/api/v1/audit-logs",
            headers=headers,
            params={
                "user_id": str(filter_user_id),
                "action": "create",
                "module": "customers",
                "start_date": start_date,
                "end_date": end_date,
                "page": "1",
                "page_size": "10",
            },
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "success"
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 10
    finally:
        await db_session.execute(
            text(
                "DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE username = :username)"
            ),
            {"username": username},
        )
        await db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        await db_session.commit()


@pytest.mark.asyncio
async def test_get_audit_actions_success(test_client, db_session: AsyncSession):
    """测试获取操作类型列表 - 成功场景"""
    username = "audit_actions_user"
    password = "test123456"
    import bcrypt

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    await db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    await db_session.execute(
        text(
            "DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE username = :username)"
        ),
        {"username": username},
    )
    await db_session.commit()

    # 确保超级管理员角色存在
    await db_session.execute(
        text("""
        INSERT INTO roles (name, description, is_system, created_at)
        VALUES ('超级管理员', '拥有系统所有权限', true, NOW())
        ON CONFLICT (name) DO NOTHING
        """)
    )

    # 确保 system:audit_read 权限存在
    await db_session.execute(
        text("""
        INSERT INTO permissions (code, name, description, module, created_at)
        VALUES ('system:audit_read', '审计日志查看', '查看系统审计日志', 'system', NOW())
        ON CONFLICT (code) DO NOTHING
        """)
    )

    # 获取角色 ID 和权限 ID
    result = await db_session.execute(
        text("SELECT id FROM roles WHERE name = '超级管理员'")
    )
    role_id = result.scalar_one()
    result = await db_session.execute(
        text("SELECT id FROM permissions WHERE code = 'system:audit_read'")
    )
    perm_id = result.scalar_one()

    # 将权限关联到角色
    await db_session.execute(
        text("""
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES (:role_id, :perm_id)
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """),
        {"role_id": role_id, "perm_id": perm_id},
    )
    await db_session.commit()

    # 创建测试用户
    await db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "audit_actions@example.com",
            "is_active": True,
        },
    )
    await db_session.commit()

    # 获取用户 ID 并分配角色
    result = await db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username},
    )
    user_id = result.scalar_one()

    await db_session.execute(
        text("""
        INSERT INTO user_roles (user_id, role_id)
        VALUES (:user_id, :role_id)
        ON CONFLICT (user_id, role_id) DO NOTHING
        """),
        {"user_id": user_id, "role_id": role_id},
    )
    await db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        request, response = await test_client.get(
            "/api/v1/audit-logs/actions",
            headers=headers,
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "success"
        assert isinstance(data["data"], list)
    finally:
        await db_session.execute(
            text(
                "DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE username = :username)"
            ),
            {"username": username},
        )
        await db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        await db_session.commit()


@pytest.mark.asyncio
async def test_get_audit_modules_success(test_client, db_session: AsyncSession):
    """测试获取模块列表 - 成功场景"""
    username = "audit_modules_user"
    password = "test123456"
    import bcrypt

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    await db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    await db_session.execute(
        text(
            "DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE username = :username)"
        ),
        {"username": username},
    )
    await db_session.commit()

    # 确保超级管理员角色存在
    await db_session.execute(
        text("""
        INSERT INTO roles (name, description, is_system, created_at)
        VALUES ('超级管理员', '拥有系统所有权限', true, NOW())
        ON CONFLICT (name) DO NOTHING
        """)
    )

    # 确保 system:audit_read 权限存在
    await db_session.execute(
        text("""
        INSERT INTO permissions (code, name, description, module, created_at)
        VALUES ('system:audit_read', '审计日志查看', '查看系统审计日志', 'system', NOW())
        ON CONFLICT (code) DO NOTHING
        """)
    )

    # 获取角色 ID 和权限 ID
    result = await db_session.execute(
        text("SELECT id FROM roles WHERE name = '超级管理员'")
    )
    role_id = result.scalar_one()
    result = await db_session.execute(
        text("SELECT id FROM permissions WHERE code = 'system:audit_read'")
    )
    perm_id = result.scalar_one()

    # 将权限关联到角色
    await db_session.execute(
        text("""
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES (:role_id, :perm_id)
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """),
        {"role_id": role_id, "perm_id": perm_id},
    )
    await db_session.commit()

    # 创建测试用户
    await db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "audit_modules@example.com",
            "is_active": True,
        },
    )
    await db_session.commit()

    # 获取用户 ID 并分配角色
    result = await db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username},
    )
    user_id = result.scalar_one()

    await db_session.execute(
        text("""
        INSERT INTO user_roles (user_id, role_id)
        VALUES (:user_id, :role_id)
        ON CONFLICT (user_id, role_id) DO NOTHING
        """),
        {"user_id": user_id, "role_id": role_id},
    )
    await db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        request, response = await test_client.get(
            "/api/v1/audit-logs/modules",
            headers=headers,
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["message"] == "success"
        assert isinstance(data["data"], list)
    finally:
        await db_session.execute(
            text(
                "DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE username = :username)"
            ),
            {"username": username},
        )
        await db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        await db_session.commit()
