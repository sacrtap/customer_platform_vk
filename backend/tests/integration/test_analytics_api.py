"""
Analytics API 集成测试

测试覆盖：
1. GET /api/v1/analytics/dashboard/stats - 获取仪表盘统计
2. GET /api/v1/analytics/dashboard/chart-data - 获取仪表盘图表数据
3. GET /api/v1/analytics/consumption/trend - 消耗趋势
4. GET /api/v1/analytics/consumption/top - Top 消耗客户
5. GET /api/v1/analytics/consumption/device-distribution - 设备类型分布
6. GET /api/v1/analytics/payment/analysis - 回款分析
7. GET /api/v1/analytics/payment/invoice-status - 结算单状态统计
8. GET /api/v1/analytics/health/stats - 健康度统计
9. GET /api/v1/analytics/health/warning-list - 余额预警客户列表
10. GET /api/v1/analytics/health/inactive-list - 长期未消耗客户列表
11. GET /api/v1/analytics/profile/industry - 行业分布
12. GET /api/v1/analytics/profile/level - 客户等级统计
13. GET /api/v1/analytics/profile/scale - 客户规模等级统计
14. GET /api/v1/analytics/profile/consume-level - 客户消费等级统计
15. GET /api/v1/analytics/profile/real-estate - 房产客户统计
16. GET /api/v1/analytics/prediction/monthly - 预测月度回款
"""

import pytest
import bcrypt
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import jwt


@pytest.fixture(scope="function")
def auth_token(test_client, db_session: Session, app):
    """获取认证 Token - 直接创建用户并生成 JWT"""
    username = "analytics_test_user"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # 清理旧数据
    db_session.execute(
        text("DELETE FROM users WHERE username = :username"),
        {"username": username},
    )
    db_session.commit()

    # 确保超级管理员角色存在
    db_session.execute(
        text("""
        INSERT INTO roles (name, description, is_system, created_at)
        VALUES ('超级管理员', '拥有系统所有权限', true, NOW())
        ON CONFLICT (name) DO NOTHING
        """)
    )

    # 确保需要的权限存在
    db_session.execute(
        text("""
        INSERT INTO permissions (code, name, description, module, created_at)
        VALUES ('analytics:read', '分析读取', '读取分析数据的权限', 'analytics', NOW())
        ON CONFLICT (code) DO NOTHING
        """)
    )

    # 获取角色 ID 和权限 ID
    result = db_session.execute(text("SELECT id FROM roles WHERE name = '超级管理员'"))
    role_id = result.scalar_one()

    result = db_session.execute(
        text("SELECT id FROM permissions WHERE code = 'analytics:read'")
    )
    perm_id = result.scalar_one()

    # 将权限关联到角色
    db_session.execute(
        text("""
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES (:role_id, :perm_id)
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """),
        {"role_id": role_id, "perm_id": perm_id},
    )
    db_session.commit()

    # 创建测试用户
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username,
            "password_hash": password_hash,
            "email": "analytics_test@example.com",
            "is_active": True,
        },
    )
    db_session.commit()

    # 获取用户 ID 并分配角色
    result = db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username},
    )
    user_id = result.scalar_one()

    db_session.execute(
        text("""
        INSERT INTO user_roles (user_id, role_id)
        VALUES (:user_id, :role_id)
        ON CONFLICT (user_id, role_id) DO NOTHING
        """),
        {"user_id": user_id, "role_id": role_id},
    )
    db_session.commit()

    try:
        # 直接生成 JWT token
        import os

        jwt_secret = os.environ.get("JWT_SECRET", "test-secret")
        jwt_algorithm = os.environ.get("JWT_ALGORITHM", "HS256")

        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "username": username,
            "roles": ["超级管理员"],
            "exp": now.timestamp() + 86400,  # 24 小时
            "iat": now.timestamp(),
            "type": "access",
        }
        token = jwt.encode(payload, jwt_secret, algorithm=jwt_algorithm)

        yield {"Authorization": f"Bearer {token}"}
    finally:
        # 清理
        db_session.execute(
            text("DELETE FROM user_roles WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        db_session.execute(
            text("DELETE FROM users WHERE username = :username"),
            {"username": username},
        )
        db_session.commit()


@pytest.mark.asyncio
async def test_dashboard_stats_success(test_client, auth_token, mock_cache):
    """测试获取仪表盘统计数据 - 成功场景"""
    request, response = await test_client.get(
        "/api/v1/analytics/dashboard/stats",
        headers=auth_token,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert "total_customers" in data["data"]
    assert "key_customers" in data["data"]
    assert "total_balance" in data["data"]


@pytest.mark.asyncio
async def test_dashboard_chart_data_success(test_client, auth_token, mock_cache):
    """测试获取仪表盘图表数据 - 成功场景"""
    request, response = await test_client.get(
        "/api/v1/analytics/dashboard/chart-data",
        headers=auth_token,
        params={"months": 6},
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert "consumption_trend" in data["data"]
    assert "payment_trend" in data["data"]


@pytest.mark.asyncio
async def test_consumption_trend_success(test_client, auth_token, mock_cache):
    """测试获取消耗趋势 - 成功场景"""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=180)

    request, response = await test_client.get(
        "/api/v1/analytics/consumption/trend",
        headers=auth_token,
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_consumption_trend_default_dates(test_client, auth_token, mock_cache):
    """测试获取消耗趋势 - 使用默认日期（最近 6 个月）"""
    request, response = await test_client.get(
        "/api/v1/analytics/consumption/trend",
        headers=auth_token,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"


@pytest.mark.asyncio
async def test_top_customers_success(test_client, auth_token, mock_cache):
    """测试获取 Top 消耗客户 - 成功场景"""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)

    request, response = await test_client.get(
        "/api/v1/analytics/consumption/top",
        headers=auth_token,
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "limit": 10,
        },
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_device_distribution_success(test_client, auth_token, mock_cache):
    """测试获取设备类型分布 - 成功场景"""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)

    request, response = await test_client.get(
        "/api/v1/analytics/consumption/device-distribution",
        headers=auth_token,
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_payment_analysis_success(test_client, auth_token, mock_cache):
    """测试获取回款分析 - 成功场景"""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)

    request, response = await test_client.get(
        "/api/v1/analytics/payment/analysis",
        headers=auth_token,
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert "total_invoiced" in data["data"]
    assert "total_paid" in data["data"]
    assert "completion_rate" in data["data"]


@pytest.mark.asyncio
async def test_invoice_status_success(test_client, auth_token, mock_cache):
    """测试获取结算单状态统计 - 成功场景"""
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=30)

    request, response = await test_client.get(
        "/api/v1/analytics/payment/invoice-status",
        headers=auth_token,
        params={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_health_stats_success(test_client, auth_token, mock_cache):
    """测试获取健康度统计 - 成功场景"""
    request, response = await test_client.get(
        "/api/v1/analytics/health/stats",
        headers=auth_token,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert "total_customers" in data["data"]
    assert "active_customers" in data["data"]
    assert "active_rate" in data["data"]


@pytest.mark.asyncio
async def test_warning_list_success(test_client, auth_token, mock_cache):
    """测试获取余额预警客户列表 - 成功场景"""
    request, response = await test_client.get(
        "/api/v1/analytics/health/warning-list",
        headers=auth_token,
        params={"threshold": 1000},
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_warning_list_default_threshold(test_client, auth_token, mock_cache):
    """测试获取余额预警客户列表 - 使用默认阈值"""
    request, response = await test_client.get(
        "/api/v1/analytics/health/warning-list",
        headers=auth_token,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"


@pytest.mark.asyncio
async def test_inactive_list_success(test_client, auth_token, mock_cache):
    """测试获取长期未消耗客户列表 - 成功场景"""
    request, response = await test_client.get(
        "/api/v1/analytics/health/inactive-list",
        headers=auth_token,
        params={"days": 90},
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_industry_distribution_success(test_client, auth_token, mock_cache):
    """测试获取行业分布 - 成功场景"""
    request, response = await test_client.get(
        "/api/v1/analytics/profile/industry",
        headers=auth_token,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_level_stats_success(test_client, auth_token, mock_cache):
    """测试获取客户等级统计 - 成功场景"""
    request, response = await test_client.get(
        "/api/v1/analytics/profile/level",
        headers=auth_token,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_scale_stats_success(test_client, auth_token, mock_cache):
    """测试获取客户规模等级统计 - 成功场景"""
    request, response = await test_client.get(
        "/api/v1/analytics/profile/scale",
        headers=auth_token,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_consume_level_stats_success(test_client, auth_token, mock_cache):
    """测试获取客户消费等级统计 - 成功场景"""
    request, response = await test_client.get(
        "/api/v1/analytics/profile/consume-level",
        headers=auth_token,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_real_estate_stats_success(test_client, auth_token, mock_cache):
    """测试获取房产客户统计 - 成功场景"""
    request, response = await test_client.get(
        "/api/v1/analytics/profile/real-estate",
        headers=auth_token,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert "total_customers" in data["data"]
    assert "real_estate_customers" in data["data"]


@pytest.mark.asyncio
async def test_prediction_monthly_success(test_client, auth_token, mock_cache):
    """测试预测月度回款 - 成功场景"""
    now = datetime.utcnow()

    request, response = await test_client.get(
        "/api/v1/analytics/prediction/monthly",
        headers=auth_token,
        params={"year": now.year, "month": now.month},
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_prediction_monthly_default(test_client, auth_token, mock_cache):
    """测试预测月度回款 - 使用默认年月"""
    request, response = await test_client.get(
        "/api/v1/analytics/prediction/monthly",
        headers=auth_token,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"


@pytest.mark.asyncio
async def test_analytics_unauthorized(test_client):
    """测试 Analytics API - 未授权访问"""
    endpoints = [
        "/api/v1/analytics/dashboard/stats",
        "/api/v1/analytics/consumption/trend",
        "/api/v1/analytics/payment/analysis",
        "/api/v1/analytics/health/stats",
        "/api/v1/analytics/profile/industry",
        "/api/v1/analytics/prediction/monthly",
    ]

    for endpoint in endpoints:
        request, response = await test_client.get(endpoint)
        assert response.status in [401, 403]
