"""
Customers API 集成测试

测试覆盖：
1. GET /api/v1/customers - 客户列表（带筛选）
2. GET /api/v1/customers/:id - 客户详情
3. POST /api/v1/customers - 创建客户
4. PUT /api/v1/customers/:id - 更新客户
5. DELETE /api/v1/customers/:id - 删除客户
6. POST /api/v1/customers/import - Excel 导入
7. GET /api/v1/customers/export - Excel 导出
8. GET /api/v1/customers/:id/profile - 获取客户画像
9. PUT /api/v1/customers/:id/profile - 更新客户画像
10. GET /api/v1/customers/import-template - 下载导入模板
"""

import io
from unittest.mock import AsyncMock

import bcrypt
import pytest
from sqlalchemy import text

from app.cache.base import cache_service


@pytest.fixture
async def auth_headers(auth_token):
    """获取认证请求头"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def customer_data(db_session):
    """创建测试客户数据"""
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.commit()

    # 创建行业类型记录（用于测试 industry 字段）
    db_session.execute(text("TRUNCATE industry_types CASCADE"))
    db_session.execute(
        text("""
        INSERT INTO industry_types (name, sort_order, created_at)
        VALUES (:name, :sort_order, NOW())
        """),
        {"name": "互联网", "sort_order": 1},
    )
    db_session.commit()

    customers = [
        {
            "company_id": 1001,
            "name": "测试公司 1",
            "account_type": "正式账号",
            "settlement_type": "prepaid",
            "is_key_customer": True,
            "email": "test1@example.com",
        },
        {
            "company_id": 1002,
            "name": "测试公司 2",
            "account_type": "试用账号",
            "settlement_type": "postpaid",
            "is_key_customer": False,
            "email": "test2@example.com",
        },
        {
            "company_id": 1003,
            "name": "测试公司 3",
            "account_type": "正式账号",
            "settlement_type": "prepaid",
            "is_key_customer": True,
            "email": "test3@example.com",
        },
    ]

    for cust in customers:
        db_session.execute(
            text("""
            INSERT INTO customers (company_id, name, account_type,
                settlement_type, is_key_customer, email, created_at)
            VALUES (:company_id, :name, :account_type,
                :settlement_type, :is_key_customer, :email, NOW())
            """),
            cust,
        )

    db_session.commit()

    result = db_session.execute(text("SELECT id FROM customers WHERE company_id = 1001"))
    customer_id = result.scalar_one()

    yield {"customers": customers, "customer_id": customer_id}

    # 清理：使用 TRUNCATE 替代 LIKE 查询（company_id 是整数类型）
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.commit()


@pytest.mark.asyncio
async def test_list_customers_success(test_client, auth_headers, customer_data):
    """测试获取客户列表 - 成功场景"""
    request, response = await test_client.get(
        "/api/v1/customers",
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "list" in data["data"]
    assert "total" in data["data"]
    assert len(data["data"]["list"]) > 0


@pytest.mark.asyncio
async def test_list_customers_usage_30d_cache_hit(test_client, auth_headers, customer_data):
    """测试获取客户列表 - usage30d 缓存命中时直接复用缓存，不执行查询

    回归测试：commit 2ecdf08f 将 usage_stmt 移入 else 分支但未同步缩进
    execute/写缓存三行，缓存命中时触发 NameError（usage_stmt 未定义）→ 500。
    修复前该测试失败（500），修复后通过（200 且直接复用缓存值）。
    """
    from unittest.mock import patch

    customer_id = customer_data["customer_id"]

    async def fake_get(namespace, key):
        if namespace == "customer_list":
            return None
        if namespace == "customer_usage_30d":
            return {customer_id: {"order_count": 7, "total_cost": 88.5}}
        return None

    # 直接替换路由模块绑定的 cache_service，绕过 conftest 的 mock 注入时机问题
    with patch("app.routes.customers.cache_service") as mock_cache:
        mock_cache.get = AsyncMock(side_effect=fake_get)
        mock_cache.set = AsyncMock(return_value=True)

        request, response = await test_client.get(
            "/api/v1/customers",
            headers=auth_headers,
        )

        # 命中 usage 缓存：应查询 usage 缓存，且不再写 usage 缓存（未走数据库查询分支）
        usage_get_calls = [
            c for c in mock_cache.get.await_args_list if c.args[0] == "customer_usage_30d"
        ]
        assert len(usage_get_calls) == 1
        usage_set_calls = [
            c for c in mock_cache.set.await_args_list if c.args[0] == "customer_usage_30d"
        ]
        assert len(usage_set_calls) == 0

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    item = next(c for c in data["data"]["list"] if c["id"] == customer_id)
    assert item["usage_30d"] == 7
    assert item["usage_30d_amount"] == 88.5


@pytest.mark.asyncio
async def test_list_customers_with_filters(test_client, auth_headers, customer_data):
    """测试获取客户列表 - 带筛选条件"""
    request, response = await test_client.get(
        "/api/v1/customers?is_key_customer=true",
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert len(data["data"]["list"]) >= 2

    for item in data["data"]["list"]:
        assert item["is_key_customer"] is True


@pytest.mark.asyncio
async def test_list_customers_pagination(test_client, auth_headers, customer_data):
    """测试获取客户列表 - 分页"""
    request, response = await test_client.get(
        "/api/v1/customers?page=1&page_size=2",
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["page"] == 1
    assert data["data"]["page_size"] == 2
    assert len(data["data"]["list"]) <= 2


@pytest.mark.asyncio
async def test_get_customer_success(test_client, auth_headers, customer_data):
    """测试获取客户详情 - 成功场景"""
    customer_id = customer_data["customer_id"]

    request, response = await test_client.get(
        f"/api/v1/customers/{customer_id}",
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["company_id"] == 1001
    assert data["data"]["name"] == "测试公司 1"


@pytest.mark.asyncio
async def test_get_customer_not_found(test_client, auth_headers):
    """测试获取客户详情 - 客户不存在"""
    request, response = await test_client.get(
        "/api/v1/customers/999999",
        headers=auth_headers,
    )

    assert response.status == 404
    data = response.json
    assert data["code"] == 40401
    assert data["message"] == "客户不存在"


@pytest.mark.asyncio
async def test_create_customer_success(test_client, auth_headers, db_session):
    """测试创建客户 - 成功场景"""
    new_customer = {
        "company_id": 1000100,
        "name": "新创建测试公司",
        "account_type": "正式账号",
        "settlement_type": "prepaid",
        "is_key_customer": True,
        "email": "create_test@example.com",
    }

    request, response = await test_client.post(
        "/api/v1/customers",
        headers=auth_headers,
        json=new_customer,
    )

    assert response.status == 201
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "创建成功"
    assert data["data"]["company_id"] == 1000100
    assert data["data"]["name"] == "新创建测试公司"

    db_session.execute(text("DELETE FROM customers WHERE company_id = 1000100"))
    db_session.commit()


@pytest.mark.asyncio
async def test_create_customer_missing_required_fields(test_client, auth_headers):
    """测试创建客户 - 缺少必填字段"""
    new_customer = {
        "name": "缺少公司 ID",
    }

    request, response = await test_client.post(
        "/api/v1/customers",
        headers=auth_headers,
        json=new_customer,
    )

    assert response.status == 400
    data = response.json
    assert data["code"] == 40001
    assert "公司 ID 和客户名称不能为空" in data["message"]


@pytest.mark.asyncio
async def test_create_customer_invalid_email(test_client, auth_headers):
    """测试创建客户 - 邮箱格式不正确"""
    new_customer = {
        "company_id": 999999,
        "name": "无效邮箱测试",
        "email": "invalid-email",
    }

    request, response = await test_client.post(
        "/api/v1/customers",
        headers=auth_headers,
        json=new_customer,
    )

    assert response.status == 400
    data = response.json
    assert data["code"] == 40002
    assert "邮箱格式不正确" in data["message"]


@pytest.mark.asyncio
async def test_update_customer_success(test_client, auth_headers, customer_data, db_session):
    """测试更新客户 - 成功场景"""
    customer_id = customer_data["customer_id"]

    update_data = {
        "name": "更新后的公司名称",
        "is_key_customer": False,
    }

    request, response = await test_client.put(
        f"/api/v1/customers/{customer_id}",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "更新成功"

    result = db_session.execute(
        text("SELECT name, is_key_customer FROM customers WHERE id = :id"),
        {"id": customer_id},
    )
    updated = result.fetchone()
    assert updated[0] == "更新后的公司名称"
    assert updated[1] is False


@pytest.mark.asyncio
async def test_create_customer_auto_initiate_settlement_default(
    test_client, auth_headers, db_session
):
    """测试创建客户 - 自动发起结算默认「是」"""
    from sqlalchemy import text

    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.commit()

    new_customer = {
        "company_id": 1000101,
        "name": "默认自动结算公司",
        "account_type": "正式账号",
        "settlement_type": "prepaid",
    }

    request, response = await test_client.post(
        "/api/v1/customers",
        headers=auth_headers,
        json=new_customer,
    )

    assert response.status == 201
    assert response.json["code"] == 0

    result = db_session.execute(
        text("SELECT auto_initiate_settlement FROM customers WHERE company_id = :company_id"),
        {"company_id": 1000101},
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] is True, f"默认自动发起结算应为是，实际为 {row[0]}"

    db_session.execute(text("DELETE FROM customers WHERE company_id = 1000101"))
    db_session.commit()


@pytest.mark.asyncio
async def test_create_customer_auto_initiate_settlement_explicit(
    test_client, auth_headers, db_session
):
    """测试创建客户 - 显式指定自动发起结算为否"""
    from sqlalchemy import text

    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.commit()

    new_customer = {
        "company_id": 1000102,
        "name": "手动结算公司",
        "account_type": "正式账号",
        "settlement_type": "prepaid",
        "auto_initiate_settlement": False,
    }

    request, response = await test_client.post(
        "/api/v1/customers",
        headers=auth_headers,
        json=new_customer,
    )

    assert response.status == 201
    assert response.json["code"] == 0

    result = db_session.execute(
        text("SELECT auto_initiate_settlement FROM customers WHERE company_id = :company_id"),
        {"company_id": 1000102},
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] is False

    db_session.execute(text("DELETE FROM customers WHERE company_id = 1000102"))
    db_session.commit()


@pytest.mark.asyncio
async def test_update_customer_auto_initiate_settlement(
    test_client, auth_headers, customer_data, db_session
):
    """测试更新客户 - 修改自动发起结算字段"""
    from sqlalchemy import text

    customer_id = customer_data["customer_id"]

    update_data = {
        "auto_initiate_settlement": False,
    }

    request, response = await test_client.put(
        f"/api/v1/customers/{customer_id}",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status == 200
    assert response.json["code"] == 0

    result = db_session.execute(
        text("SELECT auto_initiate_settlement FROM customers WHERE id = :id"),
        {"id": customer_id},
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] is False

    # 详情接口应返回该字段
    request, response = await test_client.get(
        f"/api/v1/customers/{customer_id}",
        headers=auth_headers,
    )
    assert response.status == 200
    assert response.json["data"]["auto_initiate_settlement"] is False


@pytest.mark.asyncio
async def test_update_customer_not_found(test_client, auth_headers):
    """测试更新客户 - 客户不存在"""
    update_data = {"name": "不存在的客户"}

    request, response = await test_client.put(
        "/api/v1/customers/999999",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status == 404
    data = response.json
    assert data["code"] == 40401
    assert data["message"] == "客户不存在"


@pytest.mark.asyncio
async def test_delete_customer_success(test_client, auth_headers, customer_data, db_session):
    """测试删除客户 - 成功场景"""
    customer_id = customer_data["customer_id"]

    request, response = await test_client.delete(
        f"/api/v1/customers/{customer_id}",
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "删除成功"

    result = db_session.execute(
        text("SELECT deleted_at FROM customers WHERE id = :id"),
        {"id": customer_id},
    )
    deleted_at = result.scalar_one()
    assert deleted_at is not None


@pytest.mark.asyncio
async def test_delete_customer_not_found(test_client, auth_headers):
    """测试删除客户 - 客户不存在"""
    request, response = await test_client.delete(
        "/api/v1/customers/999999",
        headers=auth_headers,
    )

    assert response.status == 404
    data = response.json
    assert data["code"] == 40401
    assert data["message"] == "客户不存在"


@pytest.mark.asyncio
async def test_get_customer_profile_success(test_client, auth_headers, customer_data):
    """测试获取客户画像 - 成功场景"""
    customer_id = customer_data["customer_id"]

    request, response = await test_client.get(
        f"/api/v1/customers/{customer_id}/profile",
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0


@pytest.mark.asyncio
async def test_get_customer_profile_not_found(test_client, auth_headers):
    """测试获取客户画像 - 客户不存在"""
    request, response = await test_client.get(
        "/api/v1/customers/999999/profile",
        headers=auth_headers,
    )

    assert response.status == 404
    data = response.json
    assert data["code"] == 40401
    assert data["message"] == "客户不存在"


@pytest.mark.asyncio
async def test_update_customer_profile_success(
    test_client, auth_headers, customer_data, db_session
):
    """测试更新客户画像 - 成功场景"""
    customer_id = customer_data["customer_id"]

    # 先创建行业类型，确保 "互联网" 存在（可能已存在，返回 409 也算成功）
    _req, ind_resp = await test_client.post(
        "/api/v1/industry-types",
        json={"name": "互联网", "sort_order": 1},
        headers=auth_headers,
    )
    assert ind_resp.status in (200, 201, 409)

    profile_data = {
        "scale_level": "large",
        "consume_level": "high",
        "industry": "互联网",
        "is_real_estate": False,
        "description": "测试描述",
    }

    request, response = await test_client.put(
        f"/api/v1/customers/{customer_id}/profile",
        headers=auth_headers,
        json=profile_data,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "更新成功"
    assert data["data"]["scale_level"] == "large"
    assert data["data"]["industry"] == "互联网"


@pytest.mark.asyncio
async def test_update_customer_profile_not_found(test_client, auth_headers):
    """测试更新客户画像 - 客户不存在"""
    profile_data = {"scale_level": "large"}

    request, response = await test_client.put(
        "/api/v1/customers/999999/profile",
        headers=auth_headers,
        json=profile_data,
    )

    assert response.status == 404
    data = response.json
    assert data["code"] == 40401
    assert data["message"] == "客户不存在"


@pytest.mark.asyncio
async def test_download_import_template(test_client, auth_headers):
    """测试下载 Excel 导入模板"""
    request, response = await test_client.get(
        "/api/v1/customers/import-template",
        headers=auth_headers,
    )

    assert response.status == 200
    assert (
        response.headers.get("Content-Type")
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "客户导入模板.xlsx" in response.headers.get("Content-Disposition", "")


@pytest.mark.asyncio
async def test_download_import_template_field_structure(test_client, auth_headers):
    """测试下载导入模板 - 验证模板字段结构正确性"""
    from openpyxl import load_workbook

    request, response = await test_client.get(
        "/api/v1/customers/import-template",
        headers=auth_headers,
    )

    assert response.status == 200

    # 解析返回的 Excel 文件
    wb = load_workbook(io.BytesIO(response.body))
    ws = wb.active

    assert ws.title == "客户导入模板"

    # 验证第 1 行：表头字段（22 个字段）
    headers = [cell.value for cell in ws[1]]
    expected_headers = [
        "company_id",
        "name",
        "account_type",
        "industry",
        "price_policy",
        "settlement_type",
        "settlement_cycle",
        "is_key_customer",
        "email",
        "erp_system",
        "first_payment_date",
        "onboarding_date",
        "cooperation_status",
        "is_settlement_enabled",
        "is_disabled",
        "notes",
        "scale_level",
        "consume_level",
        "monthly_avg_shots",
        "monthly_avg_shots_estimated",
        "estimated_annual_spend",
        "actual_annual_spend_2025",
    ]
    assert headers == expected_headers, f"表头不匹配: {headers}"

    # 验证第 2 行：中文说明
    notes = [cell.value for cell in ws[2]]
    assert "必填" in str(notes[0])  # company_id
    assert "必填" in str(notes[1])  # name
    assert "正式账号" in str(notes[2])  # account_type
    assert "定价" in str(notes[4])  # price_policy
    assert "prepaid" in str(notes[5])  # settlement_type

    # 验证第 3 行：示例数据
    example = [cell.value for cell in ws[3]]
    assert example[0] == 100001  # company_id 示例
    assert "示例公司" in str(example[1])  # name 示例
    assert example[4] == "定价"  # price_policy 示例
    assert example[5] == "prepaid"  # settlement_type 示例
    assert "example@" in str(example[8])  # email 示例
    # 验证新增字段
    assert example[10] == "2024-01-15"  # first_payment_date
    assert example[12] == "active"  # cooperation_status
    assert example[16] == "C"  # scale_level
    assert example[17] == "C2"  # consume_level


@pytest.mark.asyncio
async def test_download_import_template_header_count(test_client, auth_headers):
    """测试下载导入模板 - 验证表头数量为 22 个字段"""
    from openpyxl import load_workbook

    request, response = await test_client.get(
        "/api/v1/customers/import-template",
        headers=auth_headers,
    )

    assert response.status == 200

    wb = load_workbook(io.BytesIO(response.body))
    ws = wb.active

    header_count = sum(1 for cell in ws[1] if cell.value is not None)
    assert header_count == 22, f"期望 22 个表头，实际 {header_count} 个"


@pytest.mark.asyncio
async def test_download_import_template_unauthorized(test_client):
    """测试下载导入模板 - 未认证访问应返回 401"""
    request, response = await test_client.get(
        "/api/v1/customers/import-template",
    )

    assert response.status == 401


@pytest.mark.asyncio
async def test_download_import_template_no_import_permission(test_client, db_session):
    """测试下载导入模板 - 无 import 权限的用户仍可下载（权限已放开）"""

    import time

    unique_suffix = int(time.time())
    username = f"template_only_user_{unique_suffix}"
    role_name = f"view_only_{unique_suffix}"
    password = "test123456"

    # 清理旧数据
    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    db_session.commit()

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "template_only@example.com",
            "is_active": True,
        },
    )

    # 创建只有 customers:view 权限的角色
    db_session.execute(text("DELETE FROM roles WHERE name = :role_name"), {"role_name": role_name})
    db_session.execute(
        text("""
        INSERT INTO roles (name, description, created_at)
        VALUES (:name, :description, NOW())
        """),
        {"name": role_name, "description": "仅查看角色"},
    )
    result = db_session.execute(
        text("SELECT id FROM roles WHERE name = :role_name"), {"role_name": role_name}
    )
    role_id = result.scalar_one()

    # 仅赋予 customers:view 权限（不赋予 customers:import）
    # 确保权限存在（test_user fixture 未使用时权限表可能为空）
    result = db_session.execute(text("SELECT id FROM permissions WHERE code = 'customers:view'"))
    perm_row = result.fetchone()
    if perm_row is None:
        db_session.execute(
            text("""
            INSERT INTO permissions (code, name, description, module, created_at)
            VALUES ('customers:view', '查看客户', '查看客户列表和详情', 'customers', NOW())
            ON CONFLICT (code) DO NOTHING
            """)
        )
        db_session.commit()
        # 重新查询获取权限 ID
        perm_result = db_session.execute(
            text("SELECT id FROM permissions WHERE code = 'customers:view'")
        )
        perm_row = perm_result.fetchone()
        if perm_row is None:
            raise RuntimeError("Failed to create or find permission 'customers:view'")
        perm_id = perm_row[0]
    else:
        perm_id = perm_row[0]

    db_session.execute(
        text("DELETE FROM role_permissions WHERE role_id = :role_id"),
        {"role_id": role_id},
    )
    db_session.execute(
        text("""
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES (:role_id, :permission_id)
        """),
        {"role_id": role_id, "permission_id": perm_id},
    )

    # 关联用户到角色
    result = db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username},
    )
    user_id = result.scalar_one()

    db_session.execute(
        text("DELETE FROM user_roles WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    db_session.execute(
        text("""
        INSERT INTO user_roles (user_id, role_id)
        VALUES (:user_id, :role_id)
        """),
        {"user_id": user_id, "role_id": role_id},
    )
    db_session.commit()

    try:
        # 登录
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        # 下载模板 - 应该成功（200），因为不再需要 customers:import 权限
        request, response = await test_client.get(
            "/api/v1/customers/import-template",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status == 200
        assert (
            response.headers.get("Content-Type")
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    finally:
        db_session.execute(
            text(
                "DELETE FROM user_roles WHERE user_id = (SELECT id FROM users WHERE username = :username)"
            ),
            {"username": username},
        )
        db_session.execute(
            text(
                "DELETE FROM role_permissions WHERE role_id = (SELECT id FROM roles WHERE name = :role_name)"
            ),
            {"role_name": role_name},
        )
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.execute(
            text("DELETE FROM roles WHERE name = :role_name"),
            {"role_name": role_name},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_import_customers_success(test_client, auth_headers, db_session):
    """测试 Excel 导入客户 - 成功场景"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "company_id",
            "name",
            "account_type",
            "industry",
            "settlement_type",
            "is_key_customer",
            "email",
        ]
    )
    ws.append(
        [
            1000001,
            "导入测试公司 1",
            "正式账号",
            "互联网",
            "prepaid",
            "false",
            "import1@example.com",
        ]
    )
    ws.append(
        [
            1000002,
            "导入测试公司 2",
            "试用账号",
            "房地产",
            "postpaid",
            "true",
            "import2@example.com",
        ]
    )

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    # 行业名必须已存在于 industry_types：行业映射失败的行会被行级拒绝、不入库
    # （对齐其它导入路径「行级错误 → 该行不入库」的约定），故成功场景须先 seed 行内用到的行业。
    db_session.execute(
        text(
            "INSERT INTO industry_types (name, sort_order, created_at) "
            "VALUES ('互联网', 1, NOW()), ('房地产', 2, NOW()) ON CONFLICT (name) DO NOTHING"
        )
    )
    db_session.commit()

    files = {
        "file": (
            "test_import.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "导入完成"
    assert data["data"]["success_count"] == 2

    db_session.execute(
        text("DELETE FROM customers WHERE company_id >= 1000000 AND company_id < 1000010")
    )
    db_session.commit()


@pytest.mark.asyncio
async def test_import_customers_from_downloaded_template(test_client, auth_headers, db_session):
    """测试下载的模板可直接导入：模板第 2 行中文说明行不被当作数据行"""
    from openpyxl import load_workbook

    request, template = await test_client.get(
        "/api/v1/customers/import-template",
        headers=auth_headers,
    )
    assert template.status == 200

    company_id = 1000021
    wb = load_workbook(io.BytesIO(template.body))
    ws = wb.active
    ws.cell(row=3, column=1).value = company_id
    output = io.BytesIO()
    wb.save(output)

    # 模板示例行的 industry 为「房产经纪」：该行业类型须先存在，否则路由会如实回传
    # 「行业类型 '房产经纪' 不存在」的行级错误（该错误此前被 service 返回值覆盖而
    # 静默丢失，故旧断言在「错误被吞掉」的前提下才成立）。
    db_session.execute(
        text(
            "INSERT INTO industry_types (name, sort_order, created_at) "
            "VALUES ('房产经纪', 2, NOW()) ON CONFLICT (name) DO NOTHING"
        )
    )
    db_session.commit()

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files={
            "file": (
                "template.xlsx",
                output.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    try:
        assert response.status == 200
        data = response.json["data"]
        assert data["errors"] == []
        assert data["success_count"] == 1
    finally:
        db_session.execute(
            text("DELETE FROM customers WHERE company_id = :cid"), {"cid": company_id}
        )
        db_session.execute(text("DELETE FROM industry_types WHERE name = '房产经纪'"))
        db_session.commit()


@pytest.mark.asyncio
async def test_import_customers_missing_file(test_client, auth_headers):
    """测试 Excel 导入客户 - 缺少文件"""
    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
    )

    assert response.status == 400
    data = response.json
    assert data["code"] == 40001
    assert data["message"] == "请上传 Excel 文件"


@pytest.mark.asyncio
async def test_import_customers_wrong_format(test_client, auth_headers):
    """测试 Excel 导入客户 - 文件格式错误"""
    files = {"file": ("test.txt", b"not an excel file", "text/plain")}

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 400
    data = response.json
    assert data["code"] == 40002
    assert data["message"] == "请上传 .xlsx 格式的文件"


@pytest.mark.asyncio
async def test_import_customers_missing_columns(test_client, auth_headers):
    """测试 Excel 导入客户 - 缺少必填列"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["company_id"])
    ws.append(["MISSING_NAME"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    files = {
        "file": (
            "test_missing.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 400
    data = response.json
    assert data["code"] == 40003
    assert "缺少必填列" in data["message"]


@pytest.mark.asyncio
async def test_import_customers_with_template_notes_row(test_client, auth_headers, db_session):
    """测试导入带中文说明行的模板文件（智能跳过逻辑）"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    # 第 1 行：列名
    ws.append(["company_id", "name", "account_type"])
    # 第 2 行：中文说明（模板特征）
    ws.append(["必填", "必填", "可选"])
    # 第 3 行：实际数据
    ws.append([1000010, "模板测试公司", "正式账号"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    files = {
        "file": (
            "test_template.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["success_count"] == 1

    # 清理测试数据
    db_session.execute(
        text("DELETE FROM customers WHERE company_id >= 1000010 AND company_id < 1000020")
    )
    db_session.commit()


@pytest.mark.asyncio
async def test_import_customers_invalid_email_should_fail(test_client, auth_headers, db_session):
    """测试导入 - 邮箱格式错误应返回错误信息"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["company_id", "name", "email"])
    ws.append([1000020, "邮箱错误测试", "not-an-email"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    files = {
        "file": (
            "test_bad_email.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 200
    data = response.json
    assert data["data"]["error_count"] >= 1

    db_session.execute(
        text("DELETE FROM customers WHERE company_id >= 1000020 AND company_id < 1000030")
    )
    db_session.commit()


@pytest.mark.asyncio
async def test_import_customers_empty_required_fields(test_client, auth_headers, db_session):
    """测试导入 - 必填字段为空应返回错误"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["company_id", "name"])
    # Use None (NaN) values - pandas will include these rows
    ws.append([None, "Company with empty company_id"])
    ws.append(["EMPTY_NAME", None])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    files = {
        "file": (
            "test_empty_required.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    # Empty company_id and name should be recorded as errors
    assert data["data"]["error_count"] >= 2
    assert data["data"]["success_count"] == 0


@pytest.mark.asyncio
async def test_import_customers_duplicate_company_id(test_client, auth_headers, db_session):
    """测试导入 - 重复 company_id 应部分成功或报错"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["company_id", "name"])
    ws.append([1000030, "公司 A"])
    ws.append([1000030, "公司 B"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    files = {
        "file": (
            "test_duplicate.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["success_count"] >= 1 or data["data"]["error_count"] >= 1

    db_session.execute(
        text("DELETE FROM customers WHERE company_id >= 1000030 AND company_id < 1000040")
    )
    db_session.commit()


@pytest.mark.asyncio
async def test_import_customers_invalid_price_policy(test_client, auth_headers):
    """测试导入 - 非法 price_policy 值应被正确处理"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["company_id", "name", "price_policy"])
    ws.append(["INVALID_POLICY", "非法策略测试", "非法值"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    files = {
        "file": (
            "test_invalid_policy.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["error_count"] >= 1


@pytest.mark.asyncio
async def test_import_customers_unknown_industry_reports_error(
    test_client, auth_headers, db_session
):
    """测试导入 - 行业类型不存在时须回传行级错误

    回归防护 —— 行业映射阶段的校验错误若被 service 返回的 errors 整体覆盖，
    响应会退化为 error_count=0 / errors=[]，用户误以为全部导入成功。
    """
    from openpyxl import Workbook

    unknown_industry = "绝不存在的行业名ZZZ"
    wb = Workbook()
    ws = wb.active
    ws.append(["company_id", "name", "industry"])
    ws.append([1000050, "未知行业客户", unknown_industry])
    ws.append([1000051, "正常客户", None])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    files = {
        "file": (
            "test_unknown_industry.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    errors = data["data"]["errors"]
    assert any(unknown_industry in e for e in errors), data["data"]
    assert data["data"]["error_count"] == 1
    # M9 回归防护：行业映射失败的行不入库（success_count 仅统计有效行）
    assert data["data"]["success_count"] == 1
    # 直接查库确认无效行（company_id=1000050）未被创建
    created_count = db_session.execute(
        text("SELECT COUNT(*) FROM customers WHERE company_id = 1000050")
    ).scalar()
    assert created_count == 0

    db_session.execute(
        text("DELETE FROM customers WHERE company_id >= 1000050 AND company_id < 1000060")
    )
    db_session.commit()


@pytest.mark.asyncio
async def test_import_customers_without_notes_row(test_client, auth_headers, db_session):
    """测试导入普通用户文件（无说明行，不应跳过）"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["company_id", "name"])
    ws.append([1000040, "普通公司 A"])
    ws.append([1000041, "普通公司 B"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    files = {
        "file": (
            "test_normal.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    request, response = await test_client.post(
        "/api/v1/customers/import",
        headers=auth_headers,
        files=files,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["success_count"] == 2

    # 清理测试数据
    db_session.execute(
        text("DELETE FROM customers WHERE company_id >= 1000040 AND company_id < 1000050")
    )
    db_session.commit()


@pytest.mark.asyncio
async def test_export_customers_success(test_client, auth_headers, customer_data):
    """测试 Excel 导出客户 - 成功场景"""
    request, response = await test_client.get(
        "/api/v1/customers/export",
        headers=auth_headers,
    )

    assert response.status == 200
    assert (
        response.headers.get("Content-Type")
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "customers_" in response.headers.get("Content-Disposition", "")
    assert ".xlsx" in response.headers.get("Content-Disposition", "")


@pytest.mark.asyncio
async def test_export_customers_with_filters(test_client, auth_headers, customer_data):
    """测试 Excel 导出客户 - 带筛选条件"""
    request, response = await test_client.get(
        "/api/v1/customers/export",
        headers=auth_headers,
    )

    assert response.status == 200
    assert (
        response.headers.get("Content-Type")
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@pytest.mark.asyncio
async def test_export_customers_contains_test_data(test_client, auth_headers, customer_data):
    """测试导出 - 验证导出文件包含测试数据"""
    from openpyxl import load_workbook

    request, response = await test_client.get(
        "/api/v1/customers/export",
        headers=auth_headers,
    )

    assert response.status == 200

    wb = load_workbook(io.BytesIO(response.body))
    ws = wb.active

    row_count = ws.max_row
    assert row_count >= 2, f"期望至少 2 行，实际 {row_count} 行"

    # 查找测试数据（company_id 1001/1002/1003 或包含"测试公司"的名称）
    found_test_data = False
    for row in ws.iter_rows(min_row=2, values_only=True):
        # company_id 在第 1 列，name 在第 2 列
        if row[0] in (1001, 1002, 1003) or (row[1] and "测试公司" in str(row[1])):
            found_test_data = True
            break
    assert found_test_data, "导出文件未找到测试数据"


@pytest.mark.asyncio
async def test_export_customers_field_consistency(test_client, auth_headers, customer_data):
    """测试导出 - 验证导出文件字段与导入模板字段一致性"""
    from openpyxl import load_workbook

    request, response = await test_client.get(
        "/api/v1/customers/export",
        headers=auth_headers,
    )

    assert response.status == 200

    wb = load_workbook(io.BytesIO(response.body))
    ws = wb.active

    export_headers = [cell.value for cell in ws[1] if cell.value is not None]

    template_headers = [
        "company_id",
        "name",
        "account_type",
        "industry",
        "price_policy",
        "settlement_type",
        "settlement_cycle",
        "is_key_customer",
        "email",
        "erp_system",
        "first_payment_date",
        "onboarding_date",
        "cooperation_status",
        "is_settlement_enabled",
        "is_disabled",
        "notes",
        "scale_level",
        "consume_level",
        "monthly_avg_shots",
        "monthly_avg_shots_estimated",
        "estimated_annual_spend",
        "actual_annual_spend_2025",
    ]

    for header in template_headers:
        assert header in export_headers, f"导出文件缺少字段: {header}"

    # Verify company_id values are integers
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is not None:
            assert isinstance(row[0], (int, float)), f"company_id 应为整数，实际为 {type(row[0])}"


@pytest.mark.asyncio
async def test_customers_unauthorized(test_client):
    """测试未认证访问"""
    request, response = await test_client.get("/api/v1/customers")

    assert response.status in [401, 403]


@pytest.mark.asyncio
async def test_customers_missing_permission(test_client, db_session):
    """测试缺少权限访问"""

    username = "no_perm_user"
    password = "test123456"
    import bcrypt

    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "noperm@example.com",
            "is_active": True,
        },
    )
    db_session.commit()

    try:
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        # Patch permission cache (now imported lazily inside require_permission)
        from app.cache import permissions as perm_module

        original_get = perm_module.permission_cache.get_permissions
        perm_module.permission_cache.get_permissions = AsyncMock(return_value=set())

        try:
            request, response = await test_client.get(
                "/api/v1/customers",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status == 403
        finally:
            perm_module.permission_cache.get_permissions = original_get
    finally:
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.commit()


# ==================== is_real_estate Filter Tests ====================


@pytest.mark.asyncio
async def test_list_customers_filter_is_real_estate_true(test_client, auth_headers, db_session):
    """测试 is_real_estate=true 筛选 — 预期失败：筛选功能未实现"""
    from sqlalchemy import text

    # 清理已有客户数据
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.commit()

    # 创建测试客户：2个房产客户 + 1个非房产客户
    customers = [
        {
            "company_id": 2001,
            "name": "房产公司 A",
            "account_type": "正式账号",
            "settlement_type": "prepaid",
            "is_key_customer": False,
            "is_real_estate": True,
            "email": "re_a@example.com",
        },
        {
            "company_id": 2002,
            "name": "房产公司 B",
            "account_type": "正式账号",
            "settlement_type": "postpaid",
            "is_key_customer": True,
            "is_real_estate": True,
            "email": "re_b@example.com",
        },
        {
            "company_id": 2003,
            "name": "非房产公司",
            "account_type": "试用账号",
            "settlement_type": "prepaid",
            "is_key_customer": False,
            "is_real_estate": False,
            "email": "non_re@example.com",
        },
    ]

    for cust in customers:
        db_session.execute(
            text("""
            INSERT INTO customers (company_id, name, account_type,
                settlement_type, is_key_customer, is_real_estate, email, created_at)
            VALUES (:company_id, :name, :account_type,
                :settlement_type, :is_key_customer, :is_real_estate, :email, NOW())
            """),
            cust,
        )
    db_session.commit()

    # 筛选 is_real_estate=true
    request, response = await test_client.get(
        "/api/v1/customers?is_real_estate=true",
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0

    # 断言失败：筛选未实现，返回全部3条而非仅2条
    assert len(data["data"]["list"]) == 2, (
        f"Expected 2 real estate customers, got {len(data['data']['list'])}. "
        "is_real_estate filter not implemented in route+service"
    )
    for item in data["data"]["list"]:
        assert item["is_real_estate"] is True


@pytest.mark.asyncio
async def test_list_customers_filter_is_real_estate_false(test_client, auth_headers, db_session):
    """测试 is_real_estate=false 筛选 — 预期失败：筛选功能未实现"""
    from sqlalchemy import text

    # 清理已有客户数据
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.commit()

    # 创建测试客户：1个房产 + 2个非房产（含 NULL）
    customers = [
        {
            "company_id": 2101,
            "name": "房产公司",
            "account_type": "正式账号",
            "settlement_type": "prepaid",
            "is_key_customer": True,
            "is_real_estate": True,
            "email": "re@example.com",
        },
        {
            "company_id": 2102,
            "name": "非房产公司",
            "account_type": "试用账号",
            "settlement_type": "postpaid",
            "is_key_customer": False,
            "is_real_estate": False,
            "email": "non_re@example.com",
        },
        {
            "company_id": 2103,
            "name": "未设置公司",
            "account_type": "正式账号",
            "settlement_type": "prepaid",
            "is_key_customer": False,
            "is_real_estate": None,
            "email": "null_re@example.com",
        },
    ]

    for cust in customers:
        db_session.execute(
            text("""
            INSERT INTO customers (company_id, name, account_type,
                settlement_type, is_key_customer, is_real_estate, email, created_at)
            VALUES (:company_id, :name, :account_type,
                :settlement_type, :is_key_customer, :is_real_estate, :email, NOW())
            """),
            cust,
        )
    db_session.commit()

    # 筛选 is_real_estate=false
    request, response = await test_client.get(
        "/api/v1/customers?is_real_estate=false",
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0

    # 断言失败：筛选未实现，返回全部3条而非仅1条
    assert len(data["data"]["list"]) == 1, (
        f"Expected 1 non-real-estate customer, got {len(data['data']['list'])}. "
        "is_real_estate filter not implemented in route+service"
    )
    for item in data["data"]["list"]:
        assert item["is_real_estate"] is False


@pytest.mark.asyncio
async def test_list_customers_filter_auto_initiate_settlement_true(
    test_client, auth_headers, db_session
):
    """测试 auto_initiate_settlement=true 筛选：NULL 视为是，应包含 true 与 NULL 客户"""
    from sqlalchemy import text

    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.commit()

    customers = [
        {
            "company_id": 2301,
            "name": "自动结算公司 A",
            "account_type": "正式账号",
            "settlement_type": "prepaid",
            "auto_initiate_settlement": True,
            "email": "auto_a@example.com",
        },
        {
            "company_id": 2302,
            "name": "自动结算公司 B",
            "account_type": "正式账号",
            "settlement_type": "postpaid",
            "auto_initiate_settlement": True,
            "email": "auto_b@example.com",
        },
        {
            "company_id": 2303,
            "name": "手动结算公司",
            "account_type": "试用账号",
            "settlement_type": "prepaid",
            "auto_initiate_settlement": False,
            "email": "manual@example.com",
        },
        {
            "company_id": 2304,
            "name": "历史未设置公司",
            "account_type": "正式账号",
            "settlement_type": "prepaid",
            "auto_initiate_settlement": None,
            "email": "null_auto@example.com",
        },
    ]

    for cust in customers:
        db_session.execute(
            text("""
            INSERT INTO customers (company_id, name, account_type,
                settlement_type, auto_initiate_settlement, email, created_at)
            VALUES (:company_id, :name, :account_type,
                :settlement_type, :auto_initiate_settlement, :email, NOW())
            """),
            cust,
        )
    db_session.commit()

    request, response = await test_client.get(
        "/api/v1/customers?auto_initiate_settlement=true&force_refresh=true",
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0

    # 「是」兼容 NULL（默认值是），命中 true×2 + NULL×1
    ids = {item["company_id"] for item in data["data"]["list"]}
    assert ids == {2301, 2302, 2304}, f"Expected true+NULL customers, got {ids}"


@pytest.mark.asyncio
async def test_list_customers_filter_auto_initiate_settlement_false(
    test_client, auth_headers, db_session
):
    """测试 auto_initiate_settlement=false 筛选：严格 false，不含 NULL"""
    from sqlalchemy import text

    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.commit()

    customers = [
        {
            "company_id": 2311,
            "name": "自动结算公司",
            "account_type": "正式账号",
            "settlement_type": "prepaid",
            "auto_initiate_settlement": True,
            "email": "auto@example.com",
        },
        {
            "company_id": 2312,
            "name": "手动结算公司",
            "account_type": "试用账号",
            "settlement_type": "postpaid",
            "auto_initiate_settlement": False,
            "email": "manual@example.com",
        },
        {
            "company_id": 2313,
            "name": "历史未设置公司",
            "account_type": "正式账号",
            "settlement_type": "prepaid",
            "auto_initiate_settlement": None,
            "email": "null_auto@example.com",
        },
    ]

    for cust in customers:
        db_session.execute(
            text("""
            INSERT INTO customers (company_id, name, account_type,
                settlement_type, auto_initiate_settlement, email, created_at)
            VALUES (:company_id, :name, :account_type,
                :settlement_type, :auto_initiate_settlement, :email, NOW())
            """),
            cust,
        )
    db_session.commit()

    request, response = await test_client.get(
        "/api/v1/customers?auto_initiate_settlement=false&force_refresh=true",
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0

    # 「否」严格 false，仅命中 1 条，NULL 不兼容
    ids = {item["company_id"] for item in data["data"]["list"]}
    assert ids == {2312}, f"Expected only manual-settlement customer, got {ids}"


@pytest.mark.asyncio
async def test_export_customers_filter_is_real_estate(test_client, auth_headers, db_session):
    """测试导出接口 is_real_estate 筛选 — 预期失败：筛选功能未实现"""
    from sqlalchemy import text

    # 清理已有客户数据
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.commit()

    customers = [
        {
            "company_id": 2201,
            "name": "房产公司",
            "account_type": "正式账号",
            "settlement_type": "prepaid",
            "is_key_customer": False,
            "is_real_estate": True,
            "email": "re_export@example.com",
        },
        {
            "company_id": 2202,
            "name": "非房产公司",
            "account_type": "试用账号",
            "settlement_type": "postpaid",
            "is_key_customer": False,
            "is_real_estate": False,
            "email": "non_re_export@example.com",
        },
    ]

    for cust in customers:
        db_session.execute(
            text("""
            INSERT INTO customers (company_id, name, account_type,
                settlement_type, is_key_customer, is_real_estate, email, created_at)
            VALUES (:company_id, :name, :account_type,
                :settlement_type, :is_key_customer, :is_real_estate, :email, NOW())
            """),
            cust,
        )
    db_session.commit()

    # 导出接口带 is_real_estate=true 筛选
    request, response = await test_client.get(
        "/api/v1/customers/export?is_real_estate=true",
        headers=auth_headers,
    )

    assert response.status == 200
    # 导出成功，但筛选未实现，所以导出文件会包含非房产客户
    # 这个测试只验证导出接口能响应（不报错），不验证内容
    # 预期：筛选功能缺失，但接口不崩溃
    import io

    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(response.body))
    ws = wb.active

    # 筛选未实现 → 导出全部2条客户；筛选实现后 → 只导出1条房产客户
    row_count = ws.max_row - 1  # 减去表头行
    assert row_count == 1, (
        f"Expected 1 row (real estate only) after filtering, got {row_count}. "
        "is_real_estate filter not implemented in export route"
    )


# ============================================================
# ERP 系统选项来源测试
# 前端 EditCustomerDialog 中「ERP 系统」下拉的选项来源为
# 行业类型为「房产ERP」的客户列表，此处验证该 API 行为
# ============================================================


@pytest.mark.asyncio
async def test_list_customers_by_industry_real_estate_erp(test_client, auth_headers, db_session):
    """测试按行业类型「房产ERP」筛选客户 — ERP 系统选项的数据来源"""
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.execute(text("TRUNCATE industry_types CASCADE"))
    db_session.execute(text("TRUNCATE customer_profiles CASCADE"))
    db_session.commit()
    await cache_service.invalidate_customer_cache()

    # 插入行业类型
    db_session.execute(
        text("""
        INSERT INTO industry_types (name, sort_order, created_at)
        VALUES
            ('房产ERP', 3, NOW()),
            ('房产经纪', 2, NOW()),
            ('互联网', 1, NOW())
        """),
    )
    db_session.commit()

    # 查询行业类型 ID
    result = db_session.execute(
        text("SELECT id, name FROM industry_types WHERE name IN ('房产ERP', '房产经纪')")
    )
    industry_map = {row.name: row.id for row in result}

    # 插入 3 个客户：2 个房产ERP + 1 个房产经纪
    customers = [
        {
            "company_id": 3001,
            "name": "房产ERP客户A",
            "account_type": "正式账号",
            "settlement_type": "prepaid",
            "is_key_customer": False,
            "email": "erp_a@example.com",
        },
        {
            "company_id": 3002,
            "name": "房产ERP客户B",
            "account_type": "正式账号",
            "settlement_type": "postpaid",
            "is_key_customer": False,
            "email": "erp_b@example.com",
        },
        {
            "company_id": 3003,
            "name": "房产经纪客户C",
            "account_type": "试用账号",
            "settlement_type": "prepaid",
            "is_key_customer": False,
            "email": "agent_c@example.com",
        },
    ]

    for cust in customers:
        db_session.execute(
            text("""
            INSERT INTO customers (company_id, name, account_type,
                settlement_type, is_key_customer, email, created_at)
            VALUES (:company_id, :name, :account_type,
                :settlement_type, :is_key_customer, :email, NOW())
            """),
            cust,
        )
    db_session.commit()

    # 为客户创建 profile 并关联行业类型
    cust_rows = db_session.execute(
        text("SELECT id, company_id FROM customers WHERE company_id IN (3001, 3002, 3003)")
    ).fetchall()

    for row in cust_rows:
        if row.company_id in (3001, 3002):
            industry_id = industry_map["房产ERP"]
        else:
            industry_id = industry_map["房产经纪"]
        db_session.execute(
            text("""
            INSERT INTO customer_profiles (customer_id, industry_type_id, created_at)
            VALUES (:customer_id, :industry_type_id, NOW())
            """),
            {"customer_id": row.id, "industry_type_id": industry_id},
        )
    db_session.commit()

    # 测试：按 industry=房产ERP 筛选
    request, response = await test_client.get(
        "/api/v1/customers?industry=房产ERP",
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["total"] == 2, f"Expected 2 房产ERP customers, got {data['data']['total']}"

    names = [item["name"] for item in data["data"]["list"]]
    assert "房产ERP客户A" in names
    assert "房产ERP客户B" in names
    assert "房产经纪客户C" not in names

    # 验证返回的行业字段正确
    for item in data["data"]["list"]:
        assert item["industry"] == "房产ERP"

    # 清理
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.execute(text("TRUNCATE industry_types CASCADE"))
    db_session.execute(text("TRUNCATE customer_profiles CASCADE"))
    db_session.commit()
    await cache_service.invalidate_customer_cache()


@pytest.mark.asyncio
async def test_list_customers_by_industry_erp_empty(test_client, auth_headers, db_session):
    """测试按行业类型「房产ERP」筛选 — 无匹配客户时返回空列表"""
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.execute(text("TRUNCATE industry_types CASCADE"))
    db_session.execute(text("TRUNCATE customer_profiles CASCADE"))
    db_session.commit()
    await cache_service.invalidate_customer_cache()

    # 插入行业类型但不插入房产ERP的任何客户
    db_session.execute(
        text("""
        INSERT INTO industry_types (name, sort_order, created_at)
        VALUES ('房产ERP', 3, NOW())
        """),
    )
    db_session.commit()

    # 插入 1 个不匹配的客户
    db_session.execute(
        text("""
        INSERT INTO customers (company_id, name, account_type,
            settlement_type, is_key_customer, email, created_at)
        VALUES (3004, '非ERP客户', '正式账号', 'prepaid', false, 'no_erp@example.com', NOW())
        """),
    )
    db_session.commit()

    request, response = await test_client.get(
        "/api/v1/customers?industry=房产ERP",
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["total"] == 0
    assert len(data["data"]["list"]) == 0

    # 清理
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.execute(text("TRUNCATE industry_types CASCADE"))
    db_session.commit()
    await cache_service.invalidate_customer_cache()


@pytest.mark.asyncio
async def test_update_customer_erp_system(test_client, auth_headers, db_session):
    """测试更新客户的 erp_system 字段 — 确保字段可写入和读取"""
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.commit()

    # 创建测试客户
    db_session.execute(
        text("""
        INSERT INTO customers (company_id, name, account_type,
            settlement_type, is_key_customer, email, created_at)
        VALUES (3005, 'ERP测试客户', '正式账号', 'prepaid', false, 'erp_test@example.com', NOW())
        """),
    )
    db_session.commit()

    result = db_session.execute(text("SELECT id FROM customers WHERE company_id = 3005"))
    customer_id = result.scalar_one()

    # 更新 erp_system 字段
    request, response = await test_client.put(
        f"/api/v1/customers/{customer_id}",
        json={"erp_system": "房产ERP客户A"},
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0

    # 验证通过 GET 接口读取
    request, response = await test_client.get(
        f"/api/v1/customers/{customer_id}",
        headers=auth_headers,
    )

    assert response.status == 200
    data = response.json
    assert data["data"]["erp_system"] == "房产ERP客户A"

    # 清理
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.commit()


# ============================================================
# 数据可见性测试（customers:view_all 权限）
# 服务端强制：无 customers:view_all 的用户仅能看到自己负责的客户
# ============================================================


@pytest.mark.asyncio
async def test_list_customers_mine_scope_only(test_client, db_session):
    """无 customers:view_all 的用户仅能看到自己负责（运营经理/销售经理）的客户

    场景：受限用户 A 拥有 customers:view 但无 customers:view_all；
    客户 1 的 manager_id=A，客户 2 的 manager_id=其他用户 B。
    断言：列表只包含客户 1；访问客户 2 详情返回 403；访问客户 1 详情成功。
    """
    from app.cache import permissions as perm_module

    # 创建受限用户 A
    username_a = "scope_user_a"
    password = "test123456"
    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username_a},
    )
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username_a,
            "password_hash": password_hash,
            "email": "scopea@example.com",
            "is_active": True,
        },
    )
    db_session.commit()
    uid_a = db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username_a},
    ).scalar_one()

    # 创建另一用户 B（作为「其他经理」）
    username_b = "scope_user_b"
    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username_b},
    )
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username_b,
            "password_hash": password_hash,
            "email": "scopeb@example.com",
            "is_active": True,
        },
    )
    db_session.commit()
    uid_b = db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username_b},
    ).scalar_one()

    # 创建两个客户：客户 1 归 A，客户 2 归 B
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.execute(
        text("""
        INSERT INTO customers (company_id, name, account_type, settlement_type,
            is_key_customer, email, manager_id, created_at)
        VALUES (:company_id, :name, '正式账号', 'prepaid', false, :email, :manager_id, NOW())
        """),
        {
            "company_id": 9001,
            "name": "A负责的客户",
            "email": "a@example.com",
            "manager_id": uid_a,
        },
    )
    db_session.execute(
        text("""
        INSERT INTO customers (company_id, name, account_type, settlement_type,
            is_key_customer, email, manager_id, created_at)
        VALUES (:company_id, :name, '正式账号', 'prepaid', false, :email, :manager_id, NOW())
        """),
        {
            "company_id": 9002,
            "name": "B负责的客户",
            "email": "b@example.com",
            "manager_id": uid_b,
        },
    )
    db_session.commit()
    cust_a_id = db_session.execute(
        text("SELECT id FROM customers WHERE company_id = 9001")
    ).scalar_one()
    cust_b_id = db_session.execute(
        text("SELECT id FROM customers WHERE company_id = 9002")
    ).scalar_one()

    try:
        # 登录受限用户 A
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username_a, "password": password},
        )
        assert login_response.status == 200
        token = login_response.json["data"]["access_token"]

        # patch 权限缓存：A 仅有 customers:view（无 customers:view_all）
        original_get = perm_module.permission_cache.get_permissions
        perm_module.permission_cache.get_permissions = AsyncMock(return_value={"customers:view"})

        try:
            # 列表：应只包含 A 负责的客户
            request, response = await test_client.get(
                "/api/v1/customers",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status == 200
            ids = [item["id"] for item in response.json["data"]["list"]]
            assert cust_a_id in ids
            assert cust_b_id not in ids

            # 详情：A 不能查看 B 负责的客户 → 403
            request, response = await test_client.get(
                f"/api/v1/customers/{cust_b_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status == 403

            # 详情：A 可查看自己负责的客户 → 200
            request, response = await test_client.get(
                f"/api/v1/customers/{cust_a_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status == 200
        finally:
            perm_module.permission_cache.get_permissions = original_get
    finally:
        db_session.execute(text("TRUNCATE customers CASCADE"))
        db_session.execute(
            text("DELETE FROM users WHERE username IN (:a, :b)"),
            {"a": username_a, "b": username_b},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_role_view_all_permission_assignment_flow(test_client, db_session, auth_token):
    """端到端：给角色配置 customers:view_all 前后，用户可见客户范围变化

    场景：
    - 创建角色 R（仅 customers:view，无 customers:view_all），创建用户 U 关联角色 R
    - 客户 1 的 manager_id=U，客户 2 的 manager_id=另一用户 B
    - patch 权限缓存为 None（强制走数据库 get_user_permissions 真实链路）
    - 阶段 1：U 调用 /customers 仅见客户 1（无 view_all → 服务端强制 mine）
    - 阶段 2：admin 调用 POST /roles/{R}/permissions 给角色 R 分配 customers:view_all
    - 阶段 3：U 再次调用 /customers 可见客户 1+2（view_all → 全部）
    """
    from unittest.mock import AsyncMock

    from app.cache import permissions as perm_module

    # 创建用户 U 与用户 B
    username_u = "role_view_all_user"
    username_b = "role_view_all_other"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db_session.execute(
        text("DELETE FROM users WHERE username IN (:u, :b)"),
        {"u": username_u, "b": username_b},
    )
    db_session.execute(
        text("DELETE FROM roles WHERE name = :r"),
        {"r": "view_all_测试角色"},
    )
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username_u,
            "password_hash": password_hash,
            "email": "rvu@example.com",
            "is_active": True,
        },
    )
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username_b,
            "password_hash": password_hash,
            "email": "rvb@example.com",
            "is_active": True,
        },
    )
    # 创建角色 R（仅 customers:view）
    db_session.execute(
        text("""
        INSERT INTO roles (name, description, created_at)
        VALUES (:name, :description, NOW())
        """),
        {"name": "view_all_测试角色", "description": "端到端测试角色"},
    )
    db_session.commit()

    uid_u = db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username_u},
    ).scalar_one()
    uid_b = db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username_b},
    ).scalar_one()
    role_id = db_session.execute(
        text("SELECT id FROM roles WHERE name = :name"),
        {"name": "view_all_测试角色"},
    ).scalar_one()

    # 关联角色 R 与用户 U；给角色 R 授 customers:view
    db_session.execute(
        text("INSERT INTO user_roles (user_id, role_id) VALUES (:uid, :rid)"),
        {"uid": uid_u, "rid": role_id},
    )
    perm_view = db_session.execute(
        text("SELECT id FROM permissions WHERE code = :code"),
        {"code": "customers:view"},
    ).scalar_one()
    db_session.execute(
        text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:rid, :pid)"),
        {"rid": role_id, "pid": perm_view},
    )
    # 创建两个客户
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.execute(
        text("""
        INSERT INTO customers (company_id, name, account_type, settlement_type,
            is_key_customer, is_disabled, email, manager_id, created_at)
        VALUES (:company_id, :name, '正式账号', 'prepaid', false, false, :email, :manager_id, NOW())
        """),
        {
            "company_id": 9201,
            "name": "配置前A客户",
            "email": "cfg_a@example.com",
            "manager_id": uid_u,
        },
    )
    db_session.execute(
        text("""
        INSERT INTO customers (company_id, name, account_type, settlement_type,
            is_key_customer, is_disabled, email, manager_id, created_at)
        VALUES (:company_id, :name, '正式账号', 'prepaid', false, false, :email, :manager_id, NOW())
        """),
        {
            "company_id": 9202,
            "name": "配置后他人客户",
            "email": "cfg_b@example.com",
            "manager_id": uid_b,
        },
    )
    db_session.commit()

    # 查询客户 ID
    cust_u_id = db_session.execute(
        text("SELECT id FROM customers WHERE company_id = 9201")
    ).scalar_one()
    cust_b_id = db_session.execute(
        text("SELECT id FROM customers WHERE company_id = 9202")
    ).scalar_one()

    # 权限缓存强制 None：走真实数据库 get_user_permissions 链路
    original_get = perm_module.permission_cache.get_permissions
    perm_module.permission_cache.get_permissions = AsyncMock(return_value=None)

    try:
        # U 登录
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username_u, "password": password},
        )
        assert login_response.status == 200
        token_u = login_response.json["data"]["access_token"]
        headers_u = {"Authorization": f"Bearer {token_u}"}
        headers_admin = {"Authorization": f"Bearer {auth_token}"}

        # 阶段 1：无 view_all → 仅见客户 1
        request, response = await test_client.get("/api/v1/customers", headers=headers_u)
        assert response.status == 200
        ids = [item["id"] for item in response.json["data"]["list"]]
        assert cust_u_id in ids
        assert cust_b_id not in ids, "无 view_all 时不应看到他人负责的客户"

        # 阶段 2：admin 给角色 R 分配 customers:view_all
        perm_view_all = db_session.execute(
            text("SELECT id FROM permissions WHERE code = :code"),
            {"code": "customers:view_all"},
        ).scalar_one()
        request, response = await test_client.post(
            f"/api/v1/roles/{role_id}/permissions",
            json={"permission_ids": [perm_view, perm_view_all]},
            headers=headers_admin,
        )
        assert response.status == 200
        assert response.json["code"] == 0

        # 阶段 3：重新查询（权限缓存已失效为 None，走数据库）→ 可见全部
        request, response = await test_client.get("/api/v1/customers", headers=headers_u)
        assert response.status == 200
        ids = [item["id"] for item in response.json["data"]["list"]]
        assert cust_u_id in ids
        assert cust_b_id in ids, "配置 customers:view_all 后应能看到全部客户"
    finally:
        perm_module.permission_cache.get_permissions = original_get
        db_session.execute(text("TRUNCATE customers CASCADE"))
        db_session.execute(
            text("DELETE FROM users WHERE username IN (:u, :b)"),
            {"u": username_u, "b": username_b},
        )
        db_session.execute(text("DELETE FROM roles WHERE name = :r"), {"r": "view_all_测试角色"})
        db_session.commit()


@pytest.mark.asyncio
async def test_kpi_stats_mine_scope_only(test_client, db_session, auth_token):
    """无 customers:view_all 的用户，客户总数/重点客户/待完善画像仅统计自己负责的客户

    场景：受限用户 A（无 customers:view_all），客户 1 归 A（重点客户、无画像=待完善），
    客户 2 归 B（重点客户、有完整画像）。
    断言：A 视角 KPI = {total:1, key_customers:1, incomplete_profile:1}；
    admin（含 view_all）视角 = {total:2, key_customers:2, incomplete_profile:1}。
    """
    from app.cache import permissions as perm_module

    # 创建受限用户 A 与用户 B
    username_a = "kpi_scope_user_a"
    username_b = "kpi_scope_user_b"
    password = "test123456"
    for uname in (username_a, username_b):
        db_session.execute(text("DELETE FROM users WHERE username = :u"), {"u": uname})
        db_session.execute(
            text("""
            INSERT INTO users (username, password_hash, email, is_active, created_at)
            VALUES (:username, :password_hash, :email, :is_active, NOW())
            """),
            {
                "username": uname,
                "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                "email": f"{uname}@example.com",
                "is_active": True,
            },
        )
    db_session.commit()
    uid_a = db_session.execute(
        text("SELECT id FROM users WHERE username = :u"), {"u": username_a}
    ).scalar_one()
    uid_b = db_session.execute(
        text("SELECT id FROM users WHERE username = :u"), {"u": username_b}
    ).scalar_one()

    # 两个客户：客户 1 归 A（重点、无画像），客户 2 归 B（重点、画像完善）
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.execute(
        text("""
        INSERT INTO customers (company_id, name, account_type, settlement_type,
            is_key_customer, email, manager_id, is_disabled, created_at)
        VALUES (:company_id, :name, '正式账号', 'prepaid', true, :email, :manager_id, false, NOW())
        """),
        {
            "company_id": 9101,
            "name": "KPI客户1归A",
            "email": "kpi1@example.com",
            "manager_id": uid_a,
        },
    )
    db_session.execute(
        text("""
        INSERT INTO customers (company_id, name, account_type, settlement_type,
            is_key_customer, email, manager_id, is_disabled, created_at)
        VALUES (:company_id, :name, '正式账号', 'prepaid', true, :email, :manager_id, false, NOW())
        """),
        {
            "company_id": 9102,
            "name": "KPI客户2归B",
            "email": "kpi2@example.com",
            "manager_id": uid_b,
        },
    )
    db_session.commit()
    cust2_id = db_session.execute(
        text("SELECT id FROM customers WHERE company_id = 9102")
    ).scalar_one()

    # 客户 2 的画像完善（客户 1 无画像 → 待完善）
    db_session.execute(
        text("""
        INSERT INTO customer_profiles (customer_id, scale_level, consume_level)
        VALUES (:customer_id, '大型', 'C1')
        """),
        {"customer_id": cust2_id},
    )
    db_session.commit()

    try:
        # 登录受限用户 A
        login_request, login_response = await test_client.post(
            "/api/v1/auth/login",
            json={"username": username_a, "password": password},
        )
        assert login_response.status == 200
        token_a = login_response.json["data"]["access_token"]

        # patch 权限缓存：A 仅有 customers:view（无 customers:view_all）
        original_get = perm_module.permission_cache.get_permissions
        perm_module.permission_cache.get_permissions = AsyncMock(return_value={"customers:view"})

        try:
            # A 视角：KPI 仅统计自己负责的客户 1
            request, response = await test_client.get(
                "/api/v1/customers/kpi-stats?force_refresh=true",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert response.status == 200
            data_a = response.json["data"]
            assert data_a["total"] == 1, f"A 客户总数应=1，实际={data_a['total']}"
            assert data_a["key_customers"] == 1, f"A 重点客户应=1，实际={data_a['key_customers']}"
            assert data_a["incomplete_profile"] == 1, (
                f"A 待完善画像应=1，实际={data_a['incomplete_profile']}"
            )
            assert data_a["my_customers"] == 1

            # 受限用户 + mine=true：三个卡片与 my_customers 均按归属统计
            request, response = await test_client.get(
                "/api/v1/customers/kpi-stats?force_refresh=true&mine=true",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert response.status == 200
            data_a_mine = response.json["data"]
            assert data_a_mine["total"] == 1, (
                f"A+mine=true 客户总数应=1，实际={data_a_mine['total']}"
            )
            assert data_a_mine["my_customers"] == 1
        finally:
            perm_module.permission_cache.get_permissions = original_get

        # admin（含 view_all）视角：全量统计（权限缓存已恢复，不受 patch 影响）
        request, response = await test_client.get(
            "/api/v1/customers/kpi-stats?force_refresh=true",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status == 200
        data_admin = response.json["data"]
        assert data_admin["total"] == 2, f"admin 客户总数应=2，实际={data_admin['total']}"
        assert data_admin["key_customers"] == 2, (
            f"admin 重点客户应=2，实际={data_admin['key_customers']}"
        )
        assert data_admin["incomplete_profile"] == 1, (
            f"admin 待完善画像应=1，实际={data_admin['incomplete_profile']}"
        )

        # 回归：前端始终传 mine=true，admin（有 view_all）的全量卡片必须不受影响
        # （此前 mine=true 会把 total/key/incomplete 误过滤为 admin 名下客户数）
        request, response = await test_client.get(
            "/api/v1/customers/kpi-stats?force_refresh=true&mine=true",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status == 200
        data_admin_mine = response.json["data"]
        assert data_admin_mine["total"] == 2, (
            f"admin+mine=true 客户总数应=2，实际={data_admin_mine['total']}"
        )
        assert data_admin_mine["key_customers"] == 2, (
            f"admin+mine=true 重点客户应=2，实际={data_admin_mine['key_customers']}"
        )
        assert data_admin_mine["incomplete_profile"] == 1, (
            f"admin+mine=true 待完善画像应=1，实际={data_admin_mine['incomplete_profile']}"
        )
        # my_customers 卡片语义保留：mine=true 时统计 admin 名下客户（无 → 0）
        assert data_admin_mine["my_customers"] == 0
    finally:
        db_session.execute(text("TRUNCATE customers CASCADE"))
        db_session.execute(
            text("DELETE FROM users WHERE username IN (:a, :b)"),
            {"a": username_a, "b": username_b},
        )
        db_session.commit()
