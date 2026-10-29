"""
Analytics API 集成测试

测试覆盖：
1. GET /api/v1/analytics/dashboard/stats - 获取仪表盘统计
2. GET /api/v1/analytics/dashboard/todos - 获取仪表盘待办（行动中心）
3. GET /api/v1/analytics/consumption/trend - 消耗趋势
4. GET /api/v1/analytics/consumption/top - Top 消耗客户
5. GET /api/v1/analytics/consumption/device-distribution - 设备类型分布
6. GET /api/v1/analytics/payment/analysis - 回款分析
7. GET /api/v1/analytics/payment/invoice-status - 结算单状态统计
8. GET /api/v1/analytics/health/stats - 健康度统计
9. GET /api/v1/analytics/health/warning-list - 余额预警客户列表
10. GET /api/v1/analytics/health/inactive-list - 长期未消耗客户列表
11. GET /api/v1/analytics/profile/industry - 行业分布
12. GET /api/v1/analytics/profile/scale - 客户规模等级统计
13. GET /api/v1/analytics/profile/consume-level - 客户消费等级统计
14. GET /api/v1/analytics/profile/real-estate - 房产客户统计
15. GET /api/v1/analytics/prediction/monthly - 预测月度回款
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session


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
        VALUES ('analytics:view', '查看分析', '查看所有分析报表', 'analytics', NOW())
        ON CONFLICT (code) DO NOTHING
        """)
    )

    # 获取角色 ID 和权限 ID
    result = db_session.execute(text("SELECT id FROM roles WHERE name = '超级管理员'"))
    role_id = result.scalar_one()

    result = db_session.execute(text("SELECT id FROM permissions WHERE code = 'analytics:view'"))
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
        # 必须走 AuthService.create_access_token（内部用 settings.jwt_secret）：
        # 中间件同样按 settings.jwt_secret 验签，自签时若另取 JWT_SECRET 环境变量，
        # 会与 conftest setdefault 的 "test-secret-key" 不一致 → 401 Token 无效。
        from app.services.auth import AuthService

        token = AuthService.create_access_token(
            user_id=user_id, username=username, roles=["超级管理员"]
        )

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
async def test_dashboard_stats_sync_health_counts_only_sync_tasks(
    test_client, auth_token, mock_cache, db_session: Session
):
    """同步健康统计只统计消费同步任务（consumption_sync），与同步日志页口径一致

    场景：check_balance_warning 等业务检查任务即使失败/成功，也不应计入
    同步成功率、异常数与最近同步时间；只有 consumption_sync 任务参与。
    """
    from app.models.billing import SyncTaskLog

    # 清理日志（fixture 事务回滚，不影响其他测试）
    db_session.execute(text("DELETE FROM sync_task_logs"))
    db_session.commit()

    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

    # 消费同步：1 成功（今天）+ 1 失败（昨天）→ 成功率 50%、异常 1
    db_session.add(SyncTaskLog(task_name="consumption_sync", status="success", executed_at=today))
    db_session.add(
        SyncTaskLog(task_name="consumption_sync", status="failed", executed_at=yesterday)
    )
    # 业务检查任务：1 失败 + 1 成功（今天）→ 不应计入任一同步字段
    db_session.add(
        SyncTaskLog(
            task_name="check_balance_warning",
            status="failed",
            executed_at=today,
        )
    )
    db_session.add(
        SyncTaskLog(
            task_name="check_balance_warning",
            status="success",
            executed_at=today,
        )
    )
    db_session.commit()

    request, response = await test_client.get(
        "/api/v1/analytics/dashboard/stats",
        headers=auth_token,
    )
    assert response.status == 200
    data = response.json["data"]
    assert data["sync_success_rate"] == 0.5
    assert data["abnormal_task_count"] == 1
    assert data["last_sync_time"] == today


@pytest.mark.asyncio
async def test_dashboard_stats_no_cartesian_product(
    test_client, auth_token, mock_cache, db_session: Session
):
    """测试仪表盘统计不存在笛卡尔积问题 - 多发票场景下余额不重复计算"""
    from datetime import date

    from app.models.billing import CustomerBalance, Invoice
    from app.models.customers import Customer

    # 清理测试数据
    db_session.execute(
        text(
            "DELETE FROM invoices WHERE customer_id IN (SELECT id FROM customers WHERE name LIKE '笛卡尔积测试客户%')"
        )
    )
    db_session.execute(
        text(
            "DELETE FROM customer_balances WHERE customer_id IN (SELECT id FROM customers WHERE name LIKE '笛卡尔积测试客户%')"
        )
    )
    db_session.execute(text("DELETE FROM customers WHERE name LIKE '笛卡尔积测试客户%'"))
    db_session.commit()

    # 创建测试客户 1：余额 1000 元，5 张发票
    customer1 = Customer(
        name="笛卡尔积测试客户1",
        account_type="enterprise",
        cooperation_status="active",
        company_id=99901,
    )
    db_session.add(customer1)
    db_session.flush()

    balance1 = CustomerBalance(
        customer_id=customer1.id,
        total_amount=1000.00,
        real_amount=800.00,
        bonus_amount=200.00,
    )
    db_session.add(balance1)

    # 创建 5 张发票
    current_month_start = date.today().replace(day=1)
    for i in range(5):
        invoice = Invoice(
            customer_id=customer1.id,
            invoice_no=f"TEST-C1-{i:03d}",
            period_start=current_month_start,
            period_end=current_month_start,
            total_amount=100.00,
            status="pending_customer",
        )
        db_session.add(invoice)

    # 创建测试客户 2：余额 2000 元，3 张发票
    customer2 = Customer(
        name="笛卡尔积测试客户2",
        account_type="enterprise",
        cooperation_status="active",
        company_id=99902,
    )
    db_session.add(customer2)
    db_session.flush()

    balance2 = CustomerBalance(
        customer_id=customer2.id,
        total_amount=2000.00,
        real_amount=1500.00,
        bonus_amount=500.00,
    )
    db_session.add(balance2)

    # 创建 3 张发票
    for i in range(3):
        invoice = Invoice(
            customer_id=customer2.id,
            invoice_no=f"TEST-C2-{i:03d}",
            period_start=current_month_start,
            period_end=current_month_start,
            total_amount=200.00,
            status="pending_customer",
        )
        db_session.add(invoice)

    db_session.commit()

    # 调用 API
    request, response = await test_client.get(
        "/api/v1/analytics/dashboard/stats",
        headers=auth_token,
    )

    assert response.status == 200
    data = response.json["data"]

    # 验证余额不会被重复计算
    # 正确值：1000 + 2000 = 3000（不是 1000*5 + 2000*3 = 11000）
    assert data["total_balance"] == 3000.00, (
        f"总余额计算错误：期望 3000.00，实际 {data['total_balance']}"
    )
    assert data["real_balance"] == 2300.00, (
        f"实充余额计算错误：期望 2300.00，实际 {data['real_balance']}"
    )
    assert data["bonus_balance"] == 700.00, (
        f"赠送余额计算错误：期望 700.00，实际 {data['bonus_balance']}"
    )

    # 验证发票数量正确
    # 正确值：5 + 3 = 8 张
    assert data["month_invoice_count"] == 8, (
        f"发票数量错误：期望 8，实际 {data['month_invoice_count']}"
    )

    # 清理测试数据
    db_session.execute(
        text(
            "DELETE FROM invoices WHERE customer_id IN (SELECT id FROM customers WHERE name LIKE '笛卡尔积测试客户%')"
        )
    )
    db_session.execute(
        text(
            "DELETE FROM customer_balances WHERE customer_id IN (SELECT id FROM customers WHERE name LIKE '笛卡尔积测试客户%')"
        )
    )
    db_session.execute(text("DELETE FROM customers WHERE name LIKE '笛卡尔积测试客户%'"))
    db_session.commit()


@pytest.mark.asyncio
async def test_dashboard_todos_success(test_client, auth_token, mock_cache):
    """测试获取仪表盘待办 - 成功场景"""
    request, response = await test_client.get(
        "/api/v1/analytics/dashboard/todos",
        headers=auth_token,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert isinstance(data["data"], list)
    # 基础待办项（低余额/逾期/临期/流失风险）应始终存在（count 可为 0）
    todo_ids = {item["id"] for item in data["data"]}
    assert {"low_balance", "overdue_invoices", "due_soon", "churn_risk"} <= todo_ids
    for item in data["data"]:
        assert "urgency" in item
        assert "action_url" in item


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


def _seed_erp_consumption(db_session, suffix: str):
    """造两个客户 + 每日消耗，用于 ERP 系统筛选测试

    客户A: erp_system=yonyou，客户B: erp_system=kingdee
    消耗日期取测试当日，落在默认查询窗口内。
    """
    import uuid

    cid_a = 97000 + int(suffix)
    cid_b = 97100 + int(suffix)
    consume_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for cid, erp in [(cid_a, "yonyou"), (cid_b, "kingdee")]:
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   erp_system, created_at, updated_at)
            VALUES (:id, :company_id, :name, 'enterprise', 'monthly', 'prepaid',
                    :erp, NOW(), NOW())
            """),
            {
                "id": cid,
                "company_id": cid,
                "name": f"ERP筛选_{uuid.uuid4().hex[:6]}_{erp}",
                "erp": erp,
            },
        )
        db_session.execute(
            text("""
            INSERT INTO daily_consumptions (customer_id, consumption_date, device_type,
                                            layer_type, order_count, total_cost,
                                            created_at)
            VALUES (:cid, :d, 'camera', 'default', 2, 500.00, NOW())
            """),
            {"cid": cid, "d": consume_date},
        )
    db_session.commit()
    return cid_a, cid_b


@pytest.mark.asyncio
async def test_consumption_trend_filter_erp_system(test_client, auth_token, db_session, mock_cache):
    """测试消耗趋势 ERP 系统筛选 — 按 Customer.erp_system 精确匹配"""
    headers = auth_token
    cid_a, cid_b = _seed_erp_consumption(db_session, "01")

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=7)

    async def _fetch(**params):
        query = "&".join(f"{k}={v}" for k, v in params.items())
        _request, response = await test_client.get(
            f"/api/v1/analytics/consumption/trend?{query}",
            headers=headers,
        )
        assert response.status == 200
        assert response.json["code"] == 0
        return response.json["data"]

    # ERP 筛选：仅命中 yonyou 客户（1000 = 2天×500，取决于窗口内天数）
    data = await _fetch(
        start_date=start_date.isoformat(), end_date=end_date.isoformat(), erp_system="yonyou"
    )
    assert data, "yonyou 筛选应有数据"
    assert all(row["cost"] > 0 for row in data)

    # kingdee 筛选同样有数据
    data = await _fetch(
        start_date=start_date.isoformat(), end_date=end_date.isoformat(), erp_system="kingdee"
    )
    assert data, "kingdee 筛选应有数据"

    # 互斥/不存在的 ERP value：结果为空，非报错
    data = await _fetch(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        erp_system="nonexistent_erp",
    )
    assert data == []

    # 无筛选：两个客户的消耗都在（全量 >= 单个 ERP）
    all_data = await _fetch(start_date=start_date.isoformat(), end_date=end_date.isoformat())
    yonyou_data = await _fetch(
        start_date=start_date.isoformat(), end_date=end_date.isoformat(), erp_system="yonyou"
    )
    assert sum(r["cost"] for r in all_data) > sum(r["cost"] for r in yonyou_data)


@pytest.mark.asyncio
async def test_top_customers_filter_erp_system(test_client, auth_token, db_session, mock_cache):
    """测试 Top 客户 ERP 系统筛选 — 仅命中目标 ERP 客户"""
    headers = auth_token
    cid_a, cid_b = _seed_erp_consumption(db_session, "02")

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=7)

    async def _fetch(**params):
        query = "&".join(f"{k}={v}" for k, v in params.items())
        _request, response = await test_client.get(
            f"/api/v1/analytics/consumption/top?{query}",
            headers=headers,
        )
        assert response.status == 200
        assert response.json["code"] == 0
        return response.json["data"]

    data = await _fetch(
        start_date=start_date.isoformat(), end_date=end_date.isoformat(), erp_system="yonyou"
    )
    customer_ids = {item["customer_id"] for item in data}
    assert cid_a in customer_ids
    assert cid_b not in customer_ids

    data = await _fetch(
        start_date=start_date.isoformat(), end_date=end_date.isoformat(), erp_system="kingdee"
    )
    customer_ids = {item["customer_id"] for item in data}
    assert cid_b in customer_ids
    assert cid_a not in customer_ids


@pytest.mark.asyncio
async def test_device_distribution_filter_erp_system(
    test_client, auth_token, db_session, mock_cache
):
    """测试设备类型分布 ERP 系统筛选 — 仅命中目标 ERP 客户"""
    headers = auth_token
    cid_a, cid_b = _seed_erp_consumption(db_session, "03")

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=7)

    async def _fetch(**params):
        query = "&".join(f"{k}={v}" for k, v in params.items())
        _request, response = await test_client.get(
            f"/api/v1/analytics/consumption/device-distribution?{query}",
            headers=headers,
        )
        assert response.status == 200
        assert response.json["code"] == 0
        return response.json["data"]

    data = await _fetch(
        start_date=start_date.isoformat(), end_date=end_date.isoformat(), erp_system="yonyou"
    )
    assert data, "yonyou 筛选应有设备分布数据"
    assert all(row["cost"] > 0 for row in data)

    data = await _fetch(
        start_date=start_date.isoformat(), end_date=end_date.isoformat(), erp_system="kingdee"
    )
    assert data, "kingdee 筛选应有设备分布数据"

    # 不存在的 ERP value：空列表
    data = await _fetch(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        erp_system="nonexistent_erp",
    )
    assert data == []


@pytest.mark.asyncio
async def test_consumption_trend_erp_system_cache_isolation(test_client, auth_token, db_session):
    """测试 ERP 筛选纳入缓存 key — 不同 ERP 必须产生不同缓存键

    两个关键点：
    1. 不用端到端命中断言：测试环境无 Redis，真实 cache_service.get() 遇连接
       异常会静默返回 None，永远"未命中"，无法暴露 cache_key 漏参缺陷。
    2. 在测试内 patch `app.routes.analytics.cache_service`（而非依赖 mock_cache
       fixture 替换全局 base.cache_service）：routes/analytics.py 是
       `from ..cache.base import cache_service` 的模块级绑定，若该模块在 fixture
       替换全局之后被重新导入，请求会打到未 mock 的真实实例，导致捕获不到调用。
    """
    from unittest.mock import AsyncMock, MagicMock

    import app.routes.analytics as analytics_routes

    headers = auth_token
    cid_a, cid_b = _seed_erp_consumption(db_session, "04")

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=7)
    params = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}

    async def _fetch(**extra):
        query = "&".join(f"{k}={v}" for k, v in {**params, **extra}.items())
        _request, response = await test_client.get(
            f"/api/v1/analytics/consumption/trend?{query}",
            headers=headers,
        )
        assert response.status == 200
        return response.json["data"]

    spy_cache = MagicMock()
    spy_cache.get = AsyncMock(return_value=None)  # 永不命中，确保每次都写缓存
    spy_cache.set = AsyncMock(return_value=True)

    original = analytics_routes.cache_service
    analytics_routes.cache_service = spy_cache
    try:
        yonyou_data = await _fetch(erp_system="yonyou")
        assert yonyou_data, "yonyou 筛选应有数据"

        # cache_service.set(prefix, data, key) → key 是第三个位置参数
        trend_keys = [
            call.args
            for call in spy_cache.set.call_args_list
            if call.args and call.args[0] == "analytics_consumption_trend"
        ]
        assert trend_keys, "应写入 analytics_consumption_trend 缓存"
        yonyou_key = trend_keys[-1]
        assert any("yonyou" in str(a) for a in yonyou_key[2:]), (
            f"cache_key 必须包含 ERP 筛选值，实际 key={yonyou_key!r}"
        )

        kingdee_data = await _fetch(erp_system="kingdee")
        assert kingdee_data, "kingdee 筛选应有数据"

        trend_keys = [
            call.args
            for call in spy_cache.set.call_args_list
            if call.args and call.args[0] == "analytics_consumption_trend"
        ]
        kingdee_key = trend_keys[-1]
        assert yonyou_key != kingdee_key, (
            f"不同 ERP 筛选值必须产生不同缓存键，实际相同：{yonyou_key!r}"
        )
        assert any("kingdee" in str(a) for a in kingdee_key[2:])

        # 无筛选的 key 也必须与带筛选的不同（否则筛选态会串到全量态）
        await _fetch()
        trend_keys = [
            call.args
            for call in spy_cache.set.call_args_list
            if call.args and call.args[0] == "analytics_consumption_trend"
        ]
        assert trend_keys[-1] not in (yonyou_key, kingdee_key)
    finally:
        analytics_routes.cache_service = original


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
    # API 返回格式已变更：data 是包含 predictions 和 summary 的 dict
    assert isinstance(data["data"], dict)
    assert "predictions" in data["data"]
    assert "summary" in data["data"]
    assert isinstance(data["data"]["predictions"], list)


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


class TestBalanceTrendApi:
    """余额趋势 API 集成测试"""

    @pytest.mark.asyncio
    async def test_get_balance_trend_success(self, test_client, auth_token, mock_cache, db_session):
        """测试获取余额趋势 - 成功场景"""
        from sqlalchemy import text

        # 创建测试客户
        db_session.execute(
            text(
                "INSERT INTO customers (company_id, name, email) "
                "VALUES (999001, 'balance_trend_test', 'balance_trend@test.com') "
                "RETURNING id"
            )
        )
        result = db_session.execute(
            text("SELECT id FROM customers WHERE email = 'balance_trend@test.com'")
        )
        customer_id = result.scalar_one()
        db_session.commit()

        try:
            request, response = await test_client.get(
                f"/api/v1/analytics/billing/trend/{customer_id}",
                headers=auth_token,
            )

            assert response.status == 200
            data = response.json
            assert data["code"] == 0
            assert data["message"] == "success"
            assert "data" in data
            assert isinstance(data["data"], list)
            if data["data"]:
                point = data["data"][0]
                assert "month" in point
                assert "total_amount" in point
                assert "real_amount" in point
                assert "bonus_amount" in point
        finally:
            db_session.execute(text("DELETE FROM customers WHERE email = 'balance_trend@test.com'"))
            db_session.commit()

    @pytest.mark.asyncio
    async def test_get_balance_trend_invalid_customer(self, test_client, auth_token, mock_cache):
        """测试获取不存在的客户余额趋势"""
        request, response = await test_client.get(
            "/api/v1/analytics/billing/trend/999999",
            headers=auth_token,
        )

        assert response.status == 200
        data = response.json
        assert data["code"] == 0
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_get_balance_trend_with_months_param(
        self, test_client, auth_token, mock_cache, db_session
    ):
        """测试 months 参数（默认 6，最大 12）"""
        from sqlalchemy import text

        db_session.execute(
            text(
                "INSERT INTO customers (company_id, name, email) "
                "VALUES (999002, 'balance_trend_months', 'balance_trend_m@test.com') "
                "RETURNING id"
            )
        )
        result = db_session.execute(
            text("SELECT id FROM customers WHERE email = 'balance_trend_m@test.com'")
        )
        customer_id = result.scalar_one()
        db_session.commit()

        try:
            # 默认 6 个月
            request, response = await test_client.get(
                f"/api/v1/analytics/billing/trend/{customer_id}",
                headers=auth_token,
            )
            assert response.status == 200
            assert len(response.json["data"]) <= 6

            # 指定 3 个月
            request, response = await test_client.get(
                f"/api/v1/analytics/billing/trend/{customer_id}?months=3",
                headers=auth_token,
            )
            assert response.status == 200
            assert len(response.json["data"]) <= 3

            # 最大 12 个月
            request, response = await test_client.get(
                f"/api/v1/analytics/billing/trend/{customer_id}?months=12",
                headers=auth_token,
            )
            assert response.status == 200
            assert len(response.json["data"]) <= 12

            # 超过最大值应被限制为 12
            request, response = await test_client.get(
                f"/api/v1/analytics/billing/trend/{customer_id}?months=24",
                headers=auth_token,
            )
            assert response.status == 200
            assert len(response.json["data"]) <= 12
        finally:
            db_session.execute(
                text("DELETE FROM customers WHERE email = 'balance_trend_m@test.com'")
            )
            db_session.commit()


class TestCustomerHealthScoreApi:
    """客户健康度评分 API 集成测试"""

    @pytest.mark.asyncio
    async def test_get_health_score_success(self, test_client, auth_token, mock_cache, db_session):
        """测试获取客户健康度评分 - 成功场景"""
        # 创建测试客户
        db_session.execute(
            text(
                "INSERT INTO customers (company_id, name, email) "
                "VALUES (999003, 'health_score_test', 'health_score@test.com') "
                "RETURNING id"
            )
        )
        result = db_session.execute(
            text("SELECT id FROM customers WHERE email = 'health_score@test.com'")
        )
        customer_id = result.scalar_one()
        db_session.commit()

        try:
            request, response = await test_client.get(
                f"/api/v1/analytics/health/customers/{customer_id}/score",
                headers=auth_token,
            )

            assert response.status == 200
            data = response.json
            assert data["code"] == 0
            assert data["message"] == "success"
            assert "data" in data
            score_data = data["data"]
            assert "score" in score_data
            assert "usage_rate" in score_data
            assert "balance_rate" in score_data
            assert "payment_rate" in score_data
            assert "health_level" in score_data
            assert score_data["health_level"] in ["healthy", "normal", "unhealthy"]
        finally:
            db_session.execute(text("DELETE FROM customers WHERE email = 'health_score@test.com'"))
            db_session.commit()

    @pytest.mark.asyncio
    async def test_get_health_score_not_found(self, test_client, auth_token, mock_cache):
        """测试获取不存在客户的健康度评分"""
        request, response = await test_client.get(
            "/api/v1/analytics/health/customers/999999/score",
            headers=auth_token,
        )

        assert response.status == 404
        data = response.json
        assert data["code"] != 0
        assert "message" in data

    @pytest.mark.asyncio
    async def test_get_health_score_unauthorized(self, test_client):
        """测试健康度评分 API - 未授权访问"""
        request, response = await test_client.get(
            "/api/v1/analytics/health/customers/1/score",
        )
        assert response.status in [401, 403]


# ============================================================
# 数据可见性测试（customers:view_all 权限）
# 服务端强制：无 customers:view_all 的用户，分析统计仅覆盖自己负责的客户
# ============================================================


@pytest.mark.asyncio
async def test_analytics_health_stats_mine_scope_only(test_client, db_session, mock_cache):
    """无 customers:view_all 的用户调用 health/stats 仅统计自己负责的客户

    场景：受限用户 A 拥有 analytics:view 但无 customers:view_all；
    创建客户 1（manager_id=A）、客户 2（manager_id=其他用户 B）。
    断言：health/stats 的 total_customers 仅包含客户 1（=1），不包含客户 2。
    """
    import os
    from unittest.mock import AsyncMock

    from app.cache import permissions as perm_module

    # 创建受限用户 A 与用户 B
    username_a = "analytics_scope_a"
    username_b = "analytics_scope_b"
    password = "test123456"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db_session.execute(
        text("DELETE FROM users WHERE username IN (:a, :b)"),
        {"a": username_a, "b": username_b},
    )
    db_session.execute(
        text("""
        INSERT INTO users (username, password_hash, email, is_active, created_at)
        VALUES (:username, :password_hash, :email, :is_active, NOW())
        """),
        {
            "username": username_a,
            "password_hash": password_hash,
            "email": "ascopea@example.com",
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
            "email": "ascopeb@example.com",
            "is_active": True,
        },
    )
    db_session.commit()

    uid_a = db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username_a},
    ).scalar_one()
    uid_b = db_session.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": username_b},
    ).scalar_one()

    # 创建两个客户：客户 1 归 A，客户 2 归 B
    db_session.execute(text("TRUNCATE customers CASCADE"))
    db_session.execute(
        text("""
        INSERT INTO customers (company_id, name, account_type, settlement_type,
            is_key_customer, is_disabled, email, manager_id, created_at)
        VALUES (:company_id, :name, '正式账号', 'prepaid', false, false, :email, :manager_id, NOW())
        """),
        {"company_id": 9101, "name": "分析A客户", "email": "aa@example.com", "manager_id": uid_a},
    )
    db_session.execute(
        text("""
        INSERT INTO customers (company_id, name, account_type, settlement_type,
            is_key_customer, is_disabled, email, manager_id, created_at)
        VALUES (:company_id, :name, '正式账号', 'prepaid', false, false, :email, :manager_id, NOW())
        """),
        {"company_id": 9102, "name": "分析B客户", "email": "ab@example.com", "manager_id": uid_b},
    )
    db_session.commit()

    try:
        # 为受限用户 A 直接签发 JWT（与 auth_token fixture 相同方式）
        jwt_secret = os.environ.get("JWT_SECRET", "test-secret")
        jwt_algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": uid_a,
            "username": username_a,
            "roles": ["运营经理"],
            "exp": now.timestamp() + 86400,
            "iat": now.timestamp(),
            "type": "access",
        }
        token = jwt.encode(payload, jwt_secret, algorithm=jwt_algorithm)
        headers = {"Authorization": f"Bearer {token}"}

        # patch 权限缓存：A 仅有 analytics:view（无 customers:view_all）
        original_get = perm_module.permission_cache.get_permissions
        perm_module.permission_cache.get_permissions = AsyncMock(return_value={"analytics:view"})

        try:
            request, response = await test_client.get(
                "/api/v1/analytics/health/stats",
                headers=headers,
            )
            assert response.status == 200
            data = response.json
            assert data["code"] == 0
            assert data["data"]["total_customers"] == 1, (
                f"受限用户应只统计自己负责的客户，实际 total_customers={data['data']['total_customers']}"
            )
        finally:
            perm_module.permission_cache.get_permissions = original_get
    finally:
        db_session.execute(text("TRUNCATE customers CASCADE"))
        db_session.execute(
            text("DELETE FROM users WHERE username IN (:a, :b)"),
            {"a": username_a, "b": username_b},
        )
        db_session.commit()
