"""
Billing API 集成测试

测试覆盖：
1. GET /api/v1/billing/balances - 获取余额列表
2. GET /api/v1/billing/customers/:id/balance - 获取客户余额
3. POST /api/v1/billing/recharge - 充值
4. GET /api/v1/billing/invoices - 结算单列表
5. POST /api/v1/billing/invoices/generate - 生成结算单
6. POST /api/v1/billing/invoices/:id/submit - 提交结算单
7. POST /api/v1/billing/invoices/:id/confirm - 确认结算单
8. POST /api/v1/billing/invoices/:id/pay - 付款
9. POST /api/v1/billing/invoices/:id/complete - 完成结算
"""

import uuid

import pytest
from sqlalchemy import text


def _unique_customer_id(base: int = 90000) -> int:
    """生成唯一的测试客户 ID，避免并行测试冲突"""
    return base + abs(hash(uuid.uuid4().hex[:8])) % 10000


@pytest.fixture
async def auth_token(test_client, test_user):
    """获取认证 Token"""
    login_request, login_response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    assert login_response.status == 200
    return login_response.json["data"]["access_token"]


@pytest.fixture
async def test_customer(db_session, test_user, worker_id):
    """创建测试客户

    使用 worker_id + 随机后缀确保并行测试时客户 ID 唯一，
    避免多个 pytest-xdist worker 互相冲突。
    """
    import random

    # worker_id 由 pytest-xdist 提供（如 gw0, gw1），本地运行为 "master"
    wid = worker_id if worker_id != "master" else "local"
    customer_id = int(f"{hash(wid) % 10000:04d}{random.randint(1000, 9999)}")
    company_id = customer_id
    customer_name = f"测试客户_{customer_id}"

    db_session.execute(
        text("DELETE FROM customers WHERE id = :id"),
        {"id": customer_id},
    )
    db_session.execute(
        text("""
        INSERT INTO customers (id, company_id, name, account_type,
                               settlement_cycle, settlement_type,
                               created_at, updated_at)
        VALUES (:id, :company_id, :name, :account_type,
                :cycle, :type, NOW(), NOW())
        """),
        {
            "id": customer_id,
            "company_id": company_id,
            "name": customer_name,
            "account_type": "enterprise",
            "cycle": "monthly",
            "type": "prepaid",
        },
    )
    db_session.commit()

    yield {"id": customer_id, "name": customer_name}

    # 使用 CASCADE 删除所有关联记录（按外键依赖顺序）
    db_session.execute(
        text(
            "DELETE FROM invoice_items WHERE invoice_id IN (SELECT id FROM invoices WHERE customer_id = :id)"
        ),
        {"id": customer_id},
    )
    db_session.execute(
        text("DELETE FROM consumption_records WHERE customer_id = :id"),
        {"id": customer_id},
    )
    db_session.execute(
        text("DELETE FROM invoices WHERE customer_id = :id"),
        {"id": customer_id},
    )
    db_session.execute(
        text("DELETE FROM recharge_records WHERE customer_id = :id"),
        {"id": customer_id},
    )
    db_session.execute(
        text("DELETE FROM pricing_rules WHERE customer_id = :id"),
        {"id": customer_id},
    )
    db_session.execute(
        text("DELETE FROM daily_consumptions WHERE customer_id = :id"),
        {"id": customer_id},
    )
    db_session.execute(
        text("DELETE FROM customer_balances WHERE customer_id = :id"),
        {"id": customer_id},
    )
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer_id})
    db_session.commit()


@pytest.fixture
async def test_customer_with_balance(db_session, test_customer):
    """创建有余额的测试客户"""
    customer_id = test_customer["id"]

    db_session.execute(
        text("DELETE FROM customer_balances WHERE customer_id = :cid"),
        {"cid": customer_id},
    )
    db_session.execute(
        text("""
        INSERT INTO customer_balances
            (customer_id, total_amount, real_amount, bonus_amount,
             used_total, used_real, used_bonus, created_at, updated_at)
        VALUES (:cid, :total, :real, :bonus, :used_total, :used_real, :used_bonus, NOW(), NOW())
        """),
        {
            "cid": customer_id,
            "total": 50000.00,
            "real": 40000.00,
            "bonus": 10000.00,
            "used_total": 5000.00,
            "used_real": 4000.00,
            "used_bonus": 1000.00,
        },
    )
    db_session.commit()

    yield test_customer

    db_session.execute(
        text("DELETE FROM customer_balances WHERE customer_id = :cid"),
        {"cid": customer_id},
    )
    db_session.commit()


# ==================== 余额管理测试 ====================


@pytest.mark.asyncio
async def test_get_balances_list(test_client, auth_token, test_customer_with_balance):
    """测试获取余额列表 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/balances",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert "list" in data["data"]
    assert "total" in data["data"]


@pytest.mark.asyncio
async def test_get_balances_filter_is_real_estate_true(test_client, auth_token, db_session):
    """测试余额列表筛选 — is_real_estate=true"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid_true = _unique_customer_id(95000)
    cid_false = _unique_customer_id(96000)

    for cid, is_re in [(cid_true, True), (cid_false, False)]:
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type, is_real_estate,
                                   created_at, updated_at)
            VALUES (:id, :company_id, :name, :account_type,
                    :cycle, :type, :is_real_estate, NOW(), NOW())
            """),
            {
                "id": cid,
                "company_id": cid,
                "name": f"测试客户_{cid}",
                "account_type": "enterprise",
                "cycle": "monthly",
                "type": "prepaid",
                "is_real_estate": is_re,
            },
        )
        db_session.execute(
            text("""
            INSERT INTO customer_balances
                (customer_id, total_amount, real_amount, bonus_amount,
                 used_total, used_real, used_bonus, created_at, updated_at)
            VALUES (:cid, 100.0, 100.0, 0, 0, 0, 0, NOW(), NOW())
            """),
            {"cid": cid},
        )

    db_session.commit()

    request, response = await test_client.get(
        "/api/v1/billing/balances?is_real_estate=true",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    customer_ids = [item["customer_id"] for item in data["data"]["list"]]
    assert cid_true in customer_ids
    assert cid_false not in customer_ids
    assert data["data"]["total"] == 1


@pytest.mark.asyncio
async def test_get_balances_filter_is_real_estate_false(test_client, auth_token, db_session):
    """测试余额列表筛选 — is_real_estate=false"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid_true = _unique_customer_id(95000)
    cid_false = _unique_customer_id(96000)

    for cid, is_re in [(cid_true, True), (cid_false, False)]:
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type, is_real_estate,
                                   created_at, updated_at)
            VALUES (:id, :company_id, :name, :account_type,
                    :cycle, :type, :is_real_estate, NOW(), NOW())
            """),
            {
                "id": cid,
                "company_id": cid,
                "name": f"测试客户_{cid}",
                "account_type": "enterprise",
                "cycle": "monthly",
                "type": "prepaid",
                "is_real_estate": is_re,
            },
        )
        db_session.execute(
            text("""
            INSERT INTO customer_balances
                (customer_id, total_amount, real_amount, bonus_amount,
                 used_total, used_real, used_bonus, created_at, updated_at)
            VALUES (:cid, 100.0, 100.0, 0, 0, 0, 0, NOW(), NOW())
            """),
            {"cid": cid},
        )

    db_session.commit()

    request, response = await test_client.get(
        "/api/v1/billing/balances?is_real_estate=false",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    customer_ids = [item["customer_id"] for item in data["data"]["list"]]
    assert cid_true not in customer_ids
    assert cid_false in customer_ids
    assert data["data"]["total"] == 1


@pytest.mark.asyncio
async def test_get_balances_filter_settlement_type_prepaid(test_client, auth_token, db_session):
    """测试余额列表筛选 — settlement_type=prepaid"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid_prepaid = _unique_customer_id(95000)
    cid_postpaid = _unique_customer_id(96000)

    for cid, st in [(cid_prepaid, "prepaid"), (cid_postpaid, "postpaid")]:
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   created_at, updated_at)
            VALUES (:id, :company_id, :name, :account_type,
                    :cycle, :type, NOW(), NOW())
            """),
            {
                "id": cid,
                "company_id": cid,
                "name": f"测试客户_{cid}",
                "account_type": "enterprise",
                "cycle": "monthly",
                "type": st,
            },
        )
        db_session.execute(
            text("""
            INSERT INTO customer_balances
                (customer_id, total_amount, real_amount, bonus_amount,
                 used_total, used_real, used_bonus, created_at, updated_at)
            VALUES (:cid, 100.0, 100.0, 0, 0, 0, 0, NOW(), NOW())
            """),
            {"cid": cid},
        )

    db_session.commit()

    request, response = await test_client.get(
        "/api/v1/billing/balances?settlement_type=prepaid",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    customer_ids = [item["customer_id"] for item in data["data"]["list"]]
    assert cid_prepaid in customer_ids
    assert cid_postpaid not in customer_ids
    assert data["data"]["total"] == 1


@pytest.mark.asyncio
async def test_get_balances_filter_settlement_type_postpaid(test_client, auth_token, db_session):
    """测试余额列表筛选 — settlement_type=postpaid"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid_prepaid = _unique_customer_id(95000)
    cid_postpaid = _unique_customer_id(96000)

    for cid, st in [(cid_prepaid, "prepaid"), (cid_postpaid, "postpaid")]:
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   created_at, updated_at)
            VALUES (:id, :company_id, :name, :account_type,
                    :cycle, :type, NOW(), NOW())
            """),
            {
                "id": cid,
                "company_id": cid,
                "name": f"测试客户_{cid}",
                "account_type": "enterprise",
                "cycle": "monthly",
                "type": st,
            },
        )
        db_session.execute(
            text("""
            INSERT INTO customer_balances
                (customer_id, total_amount, real_amount, bonus_amount,
                 used_total, used_real, used_bonus, created_at, updated_at)
            VALUES (:cid, 100.0, 100.0, 0, 0, 0, 0, NOW(), NOW())
            """),
            {"cid": cid},
        )

    db_session.commit()

    request, response = await test_client.get(
        "/api/v1/billing/balances?settlement_type=postpaid",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    customer_ids = [item["customer_id"] for item in data["data"]["list"]]
    assert cid_prepaid not in customer_ids
    assert cid_postpaid in customer_ids
    assert data["data"]["total"] == 1


@pytest.mark.asyncio
async def test_get_balances_filter_combined(test_client, auth_token, db_session):
    """测试余额列表筛选 — 组合筛选 is_real_estate + settlement_type"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # 四种组合：is_real_estate x settlement_type
    configs = [
        (True, "prepaid"),
        (True, "postpaid"),
        (False, "prepaid"),
        (False, "postpaid"),
    ]
    cids = []
    for is_re, st in configs:
        cid = _unique_customer_id(95000)
        cids.append(cid)
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type, is_real_estate,
                                   created_at, updated_at)
            VALUES (:id, :company_id, :name, :account_type,
                    :cycle, :type, :is_real_estate, NOW(), NOW())
            """),
            {
                "id": cid,
                "company_id": cid,
                "name": f"测试客户_{cid}",
                "account_type": "enterprise",
                "cycle": "monthly",
                "type": st,
                "is_real_estate": is_re,
            },
        )
        db_session.execute(
            text("""
            INSERT INTO customer_balances
                (customer_id, total_amount, real_amount, bonus_amount,
                 used_total, used_real, used_bonus, created_at, updated_at)
            VALUES (:cid, 100.0, 100.0, 0, 0, 0, 0, NOW(), NOW())
            """),
            {"cid": cid},
        )

    db_session.commit()

    request, response = await test_client.get(
        "/api/v1/billing/balances?is_real_estate=true&settlement_type=prepaid",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    customer_ids = [item["customer_id"] for item in data["data"]["list"]]
    assert cids[0] in customer_ids  # True + prepaid
    assert cids[1] not in customer_ids  # True + postpaid
    assert cids[2] not in customer_ids  # False + prepaid
    assert cids[3] not in customer_ids  # False + postpaid
    assert data["data"]["total"] == 1


@pytest.mark.asyncio
async def test_get_customer_balance_exists(test_client, auth_token, test_customer_with_balance):
    """测试获取客户余额 - 余额存在"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer_with_balance["id"]

    request, response = await test_client.get(
        f"/api/v1/billing/customers/{customer_id}/balance",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["real_amount"] == 40000.00
    assert data["data"]["bonus_amount"] == 10000.00
    assert data["data"]["total_amount"] == 50000.00


@pytest.mark.asyncio
async def test_get_customer_balance_not_exists(test_client, auth_token, test_customer):
    """测试获取客户余额 - 余额不存在（返回 0）"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    request, response = await test_client.get(
        f"/api/v1/billing/customers/{customer_id}/balance",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["data"]["real_amount"] == 0
    assert data["data"]["bonus_amount"] == 0
    assert data["data"]["total_amount"] == 0


@pytest.mark.asyncio
async def test_balance_stats_this_month_amount_includes_bonus(
    test_client, auth_token, test_customer
):
    """测试 balance-stats 本月充值金额包含实充+赠送金额"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 充值：实充 1000 + 赠送 200 = 1200
    await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "customer_id": customer_id,
            "real_amount": 1000.00,
            "bonus_amount": 200.00,
        },
        headers=headers,
    )

    # 查询 balance-stats
    request, response = await test_client.get(
        "/api/v1/billing/balance-stats",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    # this_month_amount 应包含 real_amount + bonus_amount = 1200
    assert data["data"]["this_month_amount"] == 1200.00
    # this_month_count 应为 1（一笔充值交易）
    assert data["data"]["this_month_count"] == 1


@pytest.mark.asyncio
async def test_balance_stats_this_month_amount_multiple_recharges(
    test_client, auth_token, test_customer
):
    """测试 balance-stats 本月多笔充值的金额累计"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 第一笔：实充 1000 + 赠送 200 = 1200
    await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "customer_id": customer_id,
            "real_amount": 1000.00,
            "bonus_amount": 200.00,
        },
        headers=headers,
    )

    # 第二笔：实充 500 + 赠送 100 = 600
    await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "customer_id": customer_id,
            "real_amount": 500.00,
            "bonus_amount": 100.00,
        },
        headers=headers,
    )

    request, response = await test_client.get(
        "/api/v1/billing/balance-stats",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    # 总额 = 1200 + 600 = 1800（含赠送金额）
    assert data["data"]["this_month_amount"] == 1800.00
    assert data["data"]["this_month_count"] == 2


@pytest.mark.asyncio
async def test_balance_stats_total_balance(test_client, auth_token, test_customer):
    """测试 balance-stats 总余额计算"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 充值 10000 + 2000 赠送
    await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "customer_id": customer_id,
            "real_amount": 10000.00,
            "bonus_amount": 2000.00,
        },
        headers=headers,
    )

    request, response = await test_client.get(
        "/api/v1/billing/balance-stats",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    # total_balance 应包含 real + bonus
    assert data["data"]["total_balance"] == 12000.00


@pytest.mark.asyncio
async def test_balance_stats_low_balance_count(test_client, auth_token, test_customer):
    """测试 balance-stats 余额不足客户数"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 充值 5000（余额 < 10000 且 > 0 → 余额不足）
    await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "customer_id": customer_id,
            "real_amount": 5000.00,
            "bonus_amount": 0,
        },
        headers=headers,
    )

    request, response = await test_client.get(
        "/api/v1/billing/balance-stats",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    # 该客户余额 5000 > 0 且 < 10000 → 余额不足
    assert data["data"]["low_balance_count"] >= 1


@pytest.mark.asyncio
async def test_recharge_success(test_client, auth_token, test_customer):
    """测试充值 API - 成功"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    request, response = await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "customer_id": customer_id,
            "real_amount": 10000.00,
            "bonus_amount": 2000.00,
            "remark": "测试充值",
        },
        headers=headers,
    )

    assert response.status == 201
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "充值成功"
    assert data["data"]["real_amount"] == 10000.00
    assert data["data"]["bonus_amount"] == 2000.00
    assert data["data"]["total_amount"] == 12000.00


@pytest.mark.asyncio
async def test_recharge_missing_customer_id(test_client, auth_token):
    """测试充值 API - 缺少客户 ID"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "real_amount": 10000.00,
        },
        headers=headers,
    )

    assert response.status == 400
    data = response.json
    assert data["code"] == 40001
    assert "客户 ID" in data["message"]


@pytest.mark.asyncio
async def test_recharge_zero_amount(test_client, auth_token, test_customer):
    """测试充值 API - 金额不能为 0"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    request, response = await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "customer_id": customer_id,
            "real_amount": 0,
        },
        headers=headers,
    )

    assert response.status == 400
    data = response.json
    assert data["code"] == 40001


@pytest.mark.asyncio
async def test_recharge_negative_amount_no_bonus(test_client, auth_token, test_customer):
    """测试充值 API - 负数金额，赠送为 0"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    request, response = await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "customer_id": customer_id,
            "real_amount": -5000.00,
            "bonus_amount": 0,
            "remark": "测试负数充值-无赠送",
        },
        headers=headers,
    )

    assert response.status == 201
    data = response.json
    assert data["code"] == 0
    assert data["data"]["real_amount"] == -5000.00
    assert data["data"]["bonus_amount"] == 0
    assert data["data"]["total_amount"] == -5000.00


@pytest.mark.asyncio
async def test_recharge_negative_amount_negative_bonus(test_client, auth_token, test_customer):
    """测试充值 API - 负数金额，赠送也为负数"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    request, response = await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "customer_id": customer_id,
            "real_amount": -5000.00,
            "bonus_amount": -1000.00,
            "remark": "测试负数充值-赠送也为负数",
        },
        headers=headers,
    )

    assert response.status == 201
    data = response.json
    assert data["code"] == 0
    assert data["data"]["real_amount"] == -5000.00
    assert data["data"]["bonus_amount"] == -1000.00
    assert data["data"]["total_amount"] == -6000.00


@pytest.mark.asyncio
async def test_recharge_negative_amount_positive_bonus(test_client, auth_token, test_customer):
    """测试充值 API - 负数金额，赠送为正数"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    request, response = await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "customer_id": customer_id,
            "real_amount": -5000.00,
            "bonus_amount": 1000.00,
            "remark": "测试负数充值-赠送为正数",
        },
        headers=headers,
    )

    assert response.status == 201
    data = response.json
    assert data["code"] == 0
    assert data["data"]["real_amount"] == -5000.00
    assert data["data"]["bonus_amount"] == 1000.00
    assert data["data"]["total_amount"] == -4000.00


# ==================== 结算单管理测试 ====================


@pytest.mark.asyncio
async def test_get_invoices_list(test_client, auth_token):
    """测试获取结算单列表 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/invoices",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert "list" in data["data"]
    assert "total" in data["data"]


@pytest.mark.asyncio
async def test_get_invoices_sort_by_total_amount_asc(test_client, auth_token):
    """测试结算单列表按总金额升序排序"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/invoices?sort_by=total_amount&sort_order=asc",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    amounts = [item["total_amount"] for item in data["data"]["list"]]
    assert amounts == sorted(amounts)


@pytest.mark.asyncio
async def test_get_invoices_sort_by_total_amount_desc(test_client, auth_token):
    """测试结算单列表按总金额降序排序"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/invoices?sort_by=total_amount&sort_order=desc",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    amounts = [item["total_amount"] for item in data["data"]["list"]]
    assert amounts == sorted(amounts, reverse=True)


@pytest.mark.asyncio
async def test_get_invoices_sort_by_invoice_no(test_client, auth_token):
    """测试结算单列表按结算单号排序"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/invoices?sort_by=invoice_no&sort_order=asc",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    nos = [item["invoice_no"] for item in data["data"]["list"]]
    assert nos == sorted(nos)


@pytest.mark.asyncio
async def test_get_invoices_sort_by_final_amount_desc(test_client, auth_token):
    """测试结算单列表按实付金额降序排序"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/invoices?sort_by=final_amount&sort_order=desc",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    amounts = [item["final_amount"] for item in data["data"]["list"]]
    assert amounts == sorted(amounts, reverse=True)


@pytest.mark.asyncio
async def test_get_invoices_sort_by_created_at_desc(test_client, auth_token):
    """测试结算单列表按创建时间降序排序（默认排序）"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/invoices?sort_by=created_at&sort_order=desc",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    dates = [item["created_at"] for item in data["data"]["list"]]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.asyncio
async def test_get_invoices_invalid_sort_order_fallback(test_client, auth_token):
    """测试无效排序方向回退到默认值"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/invoices?sort_by=total_amount&sort_order=invalid",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0


@pytest.mark.asyncio
async def test_generate_invoice_success(test_client, auth_token, test_customer):
    """测试生成结算单 API - 成功"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    request, response = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 100,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )

    assert response.status == 201
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "生成成功"
    assert "id" in data["data"]
    assert "invoice_no" in data["data"]
    assert data["data"]["total_amount"] == 1000.00

    return data["data"]["id"]


@pytest.mark.asyncio
async def test_generate_invoice_empty_items(test_client, auth_token, test_customer):
    """测试生成结算单 API - 结算项为空"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    request, response = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [],
        },
        headers=headers,
    )

    assert response.status == 400
    data = response.json
    assert data["code"] == 40001
    assert "结算项" in data["message"]


@pytest.mark.asyncio
async def test_invoice_workflow_full(test_client, auth_token, test_customer_with_balance):
    """测试结算单完整工作流：生成 -> 提交 -> 确认 -> 付款 -> 完成"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer_with_balance["id"]

    # 1. 生成结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 50,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    assert gen_res.status == 201
    invoice_id = gen_res.json["data"]["id"]

    # 2. 提交结算单
    submit_req, submit_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/submit",
        headers=headers,
    )
    assert submit_res.status == 200
    assert submit_res.json["code"] == 0

    # 3. 确认结算单
    confirm_req, confirm_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/confirm",
        headers=headers,
    )
    assert confirm_res.status == 200
    assert confirm_res.json["code"] == 0

    # 4. 付款
    pay_req, pay_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/pay",
        json={"payment_proof": "/uploads/proof.png"},
        headers=headers,
    )
    assert pay_res.status == 200
    assert pay_res.json["code"] == 0

    # 5. 完成结算（扣款）
    complete_req, complete_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/complete",
        headers=headers,
    )
    assert complete_res.status == 200
    assert complete_res.json["code"] == 0
    assert complete_res.json["message"] == "结算完成"


@pytest.mark.asyncio
async def test_submit_invoice_invalid_state(test_client, auth_token, test_customer):
    """测试提交结算单 - 状态不允许"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 先生成结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 提交一次（成功）
    submit_req, submit_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/submit",
        headers=headers,
    )
    assert submit_res.status == 200

    # 再次提交（应该失败，因为状态已变更）
    submit_req2, submit_res2 = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/submit",
        headers=headers,
    )
    assert submit_res2.status == 400
    assert submit_res2.json["code"] == 40001


@pytest.mark.asyncio
async def test_confirm_invoice_invalid_state(test_client, auth_token, test_customer):
    """测试确认结算单 - 状态不允许"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 生成结算单后直接确认（不先提交）
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 直接确认（应该失败，因为状态是 draft）
    confirm_req, confirm_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/confirm",
        headers=headers,
    )
    assert confirm_res.status == 400
    assert confirm_res.json["code"] == 40001


@pytest.mark.asyncio
async def test_pay_invoice_invalid_state(test_client, auth_token, test_customer):
    """测试付款 - 状态不允许"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 生成结算单后直接付款
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 直接付款（应该失败）
    pay_req, pay_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/pay",
        json={"payment_proof": "/uploads/proof.png"},
        headers=headers,
    )
    assert pay_res.status == 400
    assert pay_res.json["code"] == 40001


@pytest.mark.asyncio
async def test_complete_invoice_insufficient_balance(
    test_client, auth_token, test_customer_with_balance
):
    """测试完成结算 - 余额不足"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer_with_balance["id"]

    # 生成一个金额很大的结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 100000,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 提交
    await test_client.post(f"/api/v1/billing/invoices/{invoice_id}/submit", headers=headers)
    # 确认
    await test_client.post(f"/api/v1/billing/invoices/{invoice_id}/confirm", headers=headers)
    # 付款
    await test_client.post(f"/api/v1/billing/invoices/{invoice_id}/pay", headers=headers)

    # 完成结算（应该失败，因为客户没有余额）
    complete_req, complete_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/complete",
        headers=headers,
    )
    assert complete_res.status == 400
    assert complete_res.json["code"] == 40001
    assert "余额不足" in complete_res.json["message"]


@pytest.mark.asyncio
async def test_get_invoice_detail(test_client, auth_token, test_customer):
    """测试获取结算单详情 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 先生成结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 获取详情
    detail_req, detail_res = await test_client.get(
        f"/api/v1/billing/invoices/{invoice_id}",
        headers=headers,
    )

    assert detail_res.status == 200
    data = detail_res.json
    assert data["code"] == 0
    assert "data" in data
    assert data["data"]["id"] == invoice_id
    assert "items" in data["data"]
    assert len(data["data"]["items"]) == 1


@pytest.mark.asyncio
async def test_get_invoice_not_found(test_client, auth_token):
    """测试获取结算单详情 - 不存在"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/invoices/999999",
        headers=headers,
    )

    assert response.status == 404
    data = response.json
    assert data["code"] == 40401
    assert "不存在" in data["message"]


@pytest.mark.asyncio
async def test_apply_discount(test_client, auth_token, test_customer):
    """测试应用减免 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 生成结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 100,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 应用减免
    discount_req, discount_res = await test_client.put(
        f"/api/v1/billing/invoices/{invoice_id}/discount",
        json={
            "discount_amount": 100.00,
            "discount_reason": "大客户优惠",
        },
        headers=headers,
    )

    assert discount_res.status == 200
    assert discount_res.json["code"] == 0
    assert discount_res.json["message"] == "减免应用成功"


@pytest.mark.asyncio
async def test_delete_invoice(test_client, auth_token, test_customer):
    """测试删除结算单 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 生成结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 删除
    del_req, del_res = await test_client.delete(
        f"/api/v1/billing/invoices/{invoice_id}",
        headers=headers,
    )

    assert del_res.status == 200
    assert del_res.json["code"] == 0
    assert del_res.json["message"] == "删除成功"


@pytest.mark.asyncio
async def test_cancel_invoice_success(test_client, auth_token, test_customer):
    """测试取消结算单 API - 成功"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 生成结算单（草稿状态）
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 提交到 pending_customer 状态
    await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/submit",
        headers=headers,
    )

    # 取消
    cancel_req, cancel_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/cancel",
        headers=headers,
    )

    assert cancel_res.status == 200
    assert cancel_res.json["code"] == 0
    assert "取消成功" in cancel_res.json["message"]

    # 验证状态已更新
    detail_req, detail_res = await test_client.get(
        f"/api/v1/billing/invoices/{invoice_id}",
        headers=headers,
    )
    assert detail_res.json["data"]["status"] == "cancelled"
    assert detail_res.json["data"]["cancelled_at"] is not None


@pytest.mark.asyncio
async def test_cancel_invoice_wrong_state(test_client, auth_token, test_customer):
    """测试取消结算单 API - 错误状态"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer["id"]

    # 生成结算单
    gen_req, gen_res = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "items": [
                {
                    "device_type": "X",
                    "layer_type": "single",
                    "quantity": 10,
                    "unit_price": 10.00,
                }
            ],
        },
        headers=headers,
    )
    invoice_id = gen_res.json["data"]["id"]

    # 提交并确认，使其进入 customer_confirmed 状态
    submit_req, submit_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/submit",
        headers=headers,
    )
    assert submit_res.status == 200, f"Submit failed: {submit_res.json}"

    confirm_req, confirm_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/confirm",
        headers=headers,
    )
    assert confirm_res.status == 200, f"Confirm failed: {confirm_res.json}"

    # 验证状态已变为 customer_confirmed
    detail_req, detail_res = await test_client.get(
        f"/api/v1/billing/invoices/{invoice_id}",
        headers=headers,
    )
    assert detail_res.json["data"]["status"] == "customer_confirmed"

    # 尝试取消（应该失败）
    cancel_req, cancel_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/cancel",
        headers=headers,
    )

    assert cancel_res.status == 400
    assert cancel_res.json["code"] == 40001
    assert "不能取消" in cancel_res.json["message"]


@pytest.mark.asyncio
async def test_get_recharge_records(test_client, auth_token, test_customer_with_balance):
    """测试获取充值记录 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer_with_balance["id"]

    request, response = await test_client.get(
        f"/api/v1/billing/recharge-records?customer_id={customer_id}",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert "list" in data["data"]


@pytest.mark.asyncio
async def test_get_consumption_records(test_client, auth_token):
    """测试获取消费记录 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/consumption-records",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert "list" in data["data"]


@pytest.mark.asyncio
async def test_get_pricing_rules(test_client, auth_token):
    """测试获取定价规则 API（分页格式）"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/pricing-rules",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert "list" in data["data"]
    assert "total" in data["data"]
    assert isinstance(data["data"]["list"], list)


@pytest.mark.asyncio
async def test_create_pricing_rule(test_client, auth_token):
    """测试创建定价规则 API"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.post(
        "/api/v1/billing/pricing-rules",
        json={
            "device_type": "X",
            "pricing_type": "fixed",
            "unit_price": 10.00,
            "effective_date": "2026-04-01",
            "expiry_date": "2026-12-31",
        },
        headers=headers,
    )

    assert response.status == 201
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "创建成功"
    assert data["data"]["device_type"] == "X"
    assert data["data"]["pricing_type"] == "fixed"


@pytest.mark.asyncio
async def test_unauthorized_access(test_client):
    """测试未授权访问"""
    request, response = await test_client.get("/api/v1/billing/balances")

    assert response.status in [401, 403]


@pytest.mark.asyncio
async def test_invalid_token(test_client):
    """测试无效 Token"""
    headers = {"Authorization": "Bearer invalid_token_xyz123"}

    request, response = await test_client.get(
        "/api/v1/billing/balances",
        headers=headers,
    )

    assert response.status == 401


# ==================== 定价规则冲突检查测试 ====================


@pytest.mark.asyncio
async def test_check_pricing_rule_conflict_has_conflict(test_client, auth_token, db_session):
    """测试冲突检查 API — 有冲突"""
    # 先创建一个客户（使用子查询获取 manager_id）
    from sqlalchemy import text

    # 获取第一个用户的 ID
    result = db_session.execute(text("SELECT id FROM users LIMIT 1"))
    user_row = result.fetchone()
    manager_id = user_row[0] if user_row else 1

    customer_id = _unique_customer_id(99998)
    company_id = customer_id

    # 清理旧数据
    db_session.execute(
        text("DELETE FROM pricing_rules WHERE customer_id = :id"), {"id": customer_id}
    )
    db_session.execute(
        text("DELETE FROM customer_balances WHERE customer_id = :id"), {"id": customer_id}
    )
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer_id})
    db_session.commit()

    # 创建客户
    db_session.execute(
        text("""
        INSERT INTO customers (id, company_id, name, account_type,
                               manager_id, settlement_cycle, settlement_type,
                               created_at, updated_at)
        VALUES (:id, :company_id, :name, :account_type,
                :manager_id, :cycle, :type, NOW(), NOW())
        """),
        {
            "id": customer_id,
            "company_id": company_id,
            "name": f"测试客户_{customer_id}",
            "account_type": "enterprise",
            "manager_id": manager_id,
            "cycle": "monthly",
            "type": "prepaid",
        },
    )
    db_session.commit()

    # 先创建一条规则（指定 customer_id）
    create_req, create_resp = await test_client.post(
        "/api/v1/billing/pricing-rules",
        json={
            "customer_id": customer_id,
            "device_type": "X",
            "layer_type": "single",
            "pricing_type": "fixed",
            "unit_price": 10.0,
            "effective_date": "2026-01-01",
            "expiry_date": "2026-12-31",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert create_resp.status == 201, f"创建规则失败: {create_resp.json}"

    # 检查冲突（使用相同的 customer_id, device_type 和 layer_type，但不同时间段）
    check_req, check_resp = await test_client.get(
        "/api/v1/billing/pricing-rules/check-conflict",
        params={
            "customer_id": customer_id,
            "device_type": "X",
            "layer_type": "single",
            "effective_date": "2026-06-01",
            "expiry_date": "2026-09-30",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert check_resp.status == 200
    data = check_resp.json
    assert data["code"] == 0
    assert data["data"]["has_conflict"] is True
    assert len(data["data"]["conflicting_rules"]) > 0

    # 清理
    db_session.execute(
        text("DELETE FROM pricing_rules WHERE customer_id = :id"), {"id": customer_id}
    )
    db_session.commit()


@pytest.mark.asyncio
async def test_check_pricing_rule_conflict_no_conflict(test_client, auth_token, db_session):
    """测试冲突检查 API — 无冲突"""
    # 先创建一个客户（使用子查询获取 manager_id）
    from sqlalchemy import text

    # 获取第一个用户的 ID
    result = db_session.execute(text("SELECT id FROM users LIMIT 1"))
    user_row = result.fetchone()
    manager_id = user_row[0] if user_row else 1

    customer_id = _unique_customer_id(99997)
    company_id = customer_id

    # 清理旧数据
    db_session.execute(
        text("DELETE FROM pricing_rules WHERE customer_id = :id"), {"id": customer_id}
    )
    db_session.execute(
        text("DELETE FROM customer_balances WHERE customer_id = :id"), {"id": customer_id}
    )
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer_id})
    db_session.commit()

    # 创建客户
    db_session.execute(
        text("""
        INSERT INTO customers (id, company_id, name, account_type,
                               manager_id, settlement_cycle, settlement_type,
                               created_at, updated_at)
        VALUES (:id, :company_id, :name, :account_type,
                :manager_id, :cycle, :type, NOW(), NOW())
        """),
        {
            "id": customer_id,
            "company_id": company_id,
            "name": f"测试客户_{customer_id}",
            "account_type": "enterprise",
            "manager_id": manager_id,
            "cycle": "monthly",
            "type": "prepaid",
        },
    )
    db_session.commit()

    response_req, response_resp = await test_client.get(
        "/api/v1/billing/pricing-rules/check-conflict",
        params={
            "customer_id": customer_id,
            "device_type": "Y",  # 使用不同的 device_type，确保无冲突
            "layer_type": "single",
            "effective_date": "2027-01-01",
            "expiry_date": "2027-12-31",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response_resp.status == 200
    data = response_resp.json
    assert data["code"] == 0
    assert data["data"]["has_conflict"] is False
    assert len(data["data"]["conflicting_rules"]) == 0

    # 清理
    db_session.execute(
        text("DELETE FROM pricing_rules WHERE customer_id = :id"), {"id": customer_id}
    )
    db_session.execute(
        text("DELETE FROM customer_balances WHERE customer_id = :id"), {"id": customer_id}
    )
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer_id})
    db_session.commit()
