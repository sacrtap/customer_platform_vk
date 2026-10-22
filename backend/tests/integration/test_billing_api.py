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
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.utils.timezone import local_date_to_utc_start


def _unique_customer_id(base: int = 90000) -> int:
    """生成唯一的测试客户 ID，避免并行测试冲突"""
    return base + abs(hash(uuid.uuid4().hex[:8])) % 10000


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
@pytest.mark.smoke
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
async def test_get_balances_filter_settlement_group_prepaid_includes_unset(
    test_client, auth_token, db_session
):
    """测试余额列表筛选 — settlement_group=prepaid 包含未设置结算类型的客户"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid_prepaid = _unique_customer_id(95000)
    cid_unset = _unique_customer_id(96000)
    cid_postpaid = _unique_customer_id(97000)

    for cid, st in [(cid_prepaid, "prepaid"), (cid_unset, None), (cid_postpaid, "postpaid")]:
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   created_at, updated_at)
            VALUES (:id, :company_id, :name, 'enterprise', 'monthly', :type, NOW(), NOW())
            """),
            {"id": cid, "company_id": cid, "name": f"测试客户_{cid}", "type": st},
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
        "/api/v1/billing/balances?settlement_group=prepaid",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    customer_ids = [item["customer_id"] for item in data["data"]["list"]]
    assert cid_prepaid in customer_ids
    # 未设置结算类型的客户按业务默认归入预付费
    assert cid_unset in customer_ids
    assert cid_postpaid not in customer_ids
    assert data["data"]["total"] == 2


@pytest.mark.asyncio
async def test_get_balances_filter_settlement_group_postpaid(test_client, auth_token, db_session):
    """测试余额列表筛选 — settlement_group=postpaid 仅返回后付费客户"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid_prepaid = _unique_customer_id(95000)
    cid_unset = _unique_customer_id(96000)
    cid_postpaid = _unique_customer_id(97000)

    for cid, st in [(cid_prepaid, "prepaid"), (cid_unset, None), (cid_postpaid, "postpaid")]:
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   created_at, updated_at)
            VALUES (:id, :company_id, :name, 'enterprise', 'monthly', :type, NOW(), NOW())
            """),
            {"id": cid, "company_id": cid, "name": f"测试客户_{cid}", "type": st},
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
        "/api/v1/billing/balances?settlement_group=postpaid",
        headers=headers,
    )

    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    customer_ids = [item["customer_id"] for item in data["data"]["list"]]
    assert cid_postpaid in customer_ids
    assert cid_prepaid not in customer_ids
    assert cid_unset not in customer_ids
    assert data["data"]["total"] == 1


@pytest.mark.asyncio
async def test_get_balances_filter_settlement_group_invalid(test_client, auth_token):
    """测试余额列表筛选 — settlement_group 非法取值返回 400"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.get(
        "/api/v1/billing/balances?settlement_group=unknown",
        headers=headers,
    )

    assert response.status == 400
    assert "settlement_group" in response.json["message"]


@pytest.mark.asyncio
async def test_balance_stats_burning_soon_includes_unset_settlement(
    test_client, auth_token, db_session
):
    """测试「即将耗尽」统计：未设置结算类型的客户归入预付费，同样参与预警"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # 余额 50 / 近 30 天消费 100 → 预计可支撑 3.5 天（≤7），应命中预警
    for st in (None, "postpaid"):
        cid = _unique_customer_id(98000)
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   created_at, updated_at)
            VALUES (:id, :company_id, :name, 'enterprise', 'monthly', :type, NOW(), NOW())
            """),
            {"id": cid, "company_id": cid, "name": f"燃尽测试_{cid}", "type": st},
        )
        db_session.execute(
            text("""
            INSERT INTO customer_balances
                (customer_id, total_amount, real_amount, bonus_amount,
                 used_total, used_real, used_bonus, created_at, updated_at)
            VALUES (:cid, 50.0, 50.0, 0, 0, 0, 0, NOW(), NOW())
            """),
            {"cid": cid},
        )
        db_session.execute(
            text("""
            INSERT INTO daily_consumptions
                (customer_id, consumption_date, device_type, layer_type,
                 total_cost, created_at, updated_at)
            VALUES (:cid, NOW() - INTERVAL '10 days', 'PC', 'L1', 100.0, NOW(), NOW())
            """),
            {"cid": cid},
        )
    db_session.commit()

    request, response = await test_client.get(
        "/api/v1/billing/balance-stats",
        headers=headers,
    )

    assert response.status == 200
    data = response.json["data"]
    # 仅未设置结算类型的客户（归预付费）计入，后付费客户不计入
    assert data["burning_soon_count"] == 1


@pytest.mark.asyncio
async def test_get_balances_filter_settlement_enabled(test_client, auth_token, db_session):
    """测试余额列表/统计筛选 — is_settlement_enabled 是否结算"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid_on = _unique_customer_id(94000)
    cid_off = _unique_customer_id(94500)

    for cid, enabled in [(cid_on, True), (cid_off, False)]:
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type, is_settlement_enabled,
                                   created_at, updated_at)
            VALUES (:id, :company_id, :name, 'enterprise', 'monthly', 'prepaid', :enabled,
                    NOW(), NOW())
            """),
            {"id": cid, "company_id": cid, "name": f"结算筛选_{cid}", "enabled": enabled},
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

    # 列表只返回开启结算的客户
    request, response = await test_client.get(
        "/api/v1/billing/balances?is_settlement_enabled=true",
        headers=headers,
    )
    assert response.status == 200
    data = response.json
    customer_ids = [item["customer_id"] for item in data["data"]["list"]]
    assert cid_on in customer_ids
    assert cid_off not in customer_ids
    assert data["data"]["total"] == 1

    # 统计跟随筛选：仅开启结算的客户计入预付费总余额
    request, response = await test_client.get(
        "/api/v1/billing/balance-stats?is_settlement_enabled=true",
        headers=headers,
    )
    assert response.status == 200
    stats_data = response.json["data"]
    assert stats_data["prepaid_customers"] == 1
    assert stats_data["total_balance_prepaid"] == 100.00

    # 非法取值返回 400
    request, response = await test_client.get(
        "/api/v1/billing/balances?is_settlement_enabled=yes",
        headers=headers,
    )
    assert response.status == 400
    assert "is_settlement_enabled" in response.json["message"]


@pytest.mark.asyncio
async def test_get_balances_filter_erp_system_and_cooperation_status(
    test_client, auth_token, db_session
):
    """测试余额列表/统计筛选 — erp_system + cooperation_status（字符串精确匹配）"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid_match = _unique_customer_id(96000)
    cid_other = _unique_customer_id(96500)

    for cid, erp, coop in [(cid_match, "yonyou", "active"), (cid_other, "kingdee", "paused")]:
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   erp_system, cooperation_status,
                                   created_at, updated_at)
            VALUES (:id, :company_id, :name, 'enterprise', 'monthly', 'prepaid',
                    :erp, :coop, NOW(), NOW())
            """),
            {"id": cid, "company_id": cid, "name": f"ERP筛选_{cid}", "erp": erp, "coop": coop},
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

    # ERP 系统筛选
    request, response = await test_client.get(
        "/api/v1/billing/balances?erp_system=yonyou",
        headers=headers,
    )
    assert response.status == 200
    customer_ids = [item["customer_id"] for item in response.json["data"]["list"]]
    assert cid_match in customer_ids
    assert cid_other not in customer_ids

    # 合作状态筛选
    request, response = await test_client.get(
        "/api/v1/billing/balances?cooperation_status=active",
        headers=headers,
    )
    assert response.status == 200
    customer_ids = [item["customer_id"] for item in response.json["data"]["list"]]
    assert cid_match in customer_ids
    assert cid_other not in customer_ids

    # 统计跟随筛选
    request, response = await test_client.get(
        "/api/v1/billing/balance-stats?erp_system=yonyou",
        headers=headers,
    )
    assert response.status == 200
    assert response.json["data"]["prepaid_customers"] == 1


@pytest.mark.asyncio
async def test_get_balances_filter_auto_initiate_null_compat(test_client, auth_token, db_session):
    """测试余额列表筛选 — auto_initiate_settlement 历史 NULL 视为「是」"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid_true = _unique_customer_id(97000)
    cid_null = _unique_customer_id(97500)
    cid_false = _unique_customer_id(97800)

    for cid, val in [(cid_true, True), (cid_null, None), (cid_false, False)]:
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   auto_initiate_settlement, created_at, updated_at)
            VALUES (:id, :company_id, :name, 'enterprise', 'monthly', 'prepaid',
                    :val, NOW(), NOW())
            """),
            {"id": cid, "company_id": cid, "name": f"自动结算_{cid}", "val": val},
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

    # 「是」→ True 与 NULL 都命中
    request, response = await test_client.get(
        "/api/v1/billing/balances?auto_initiate_settlement=true",
        headers=headers,
    )
    assert response.status == 200
    customer_ids = [item["customer_id"] for item in response.json["data"]["list"]]
    assert cid_true in customer_ids
    assert cid_null in customer_ids
    assert cid_false not in customer_ids

    # 「否」→ 仅 False 命中
    request, response = await test_client.get(
        "/api/v1/billing/balances?auto_initiate_settlement=false",
        headers=headers,
    )
    assert response.status == 200
    customer_ids = [item["customer_id"] for item in response.json["data"]["list"]]
    assert cid_false in customer_ids
    assert cid_true not in customer_ids
    assert cid_null not in customer_ids

    # 非法取值返回 400
    request, response = await test_client.get(
        "/api/v1/billing/balances?auto_initiate_settlement=maybe",
        headers=headers,
    )
    assert response.status == 400
    assert "auto_initiate_settlement" in response.json["message"]


@pytest.mark.asyncio
async def test_get_balances_filter_is_disabled_null_compat(test_client, auth_token, db_session):
    """测试余额列表筛选 — is_disabled 历史 NULL 视为未停用"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid_true = _unique_customer_id(98000)
    cid_null = _unique_customer_id(98500)
    cid_false = _unique_customer_id(98800)

    for cid, val in [(cid_true, True), (cid_null, None), (cid_false, False)]:
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   is_disabled, created_at, updated_at)
            VALUES (:id, :company_id, :name, 'enterprise', 'monthly', 'prepaid',
                    :val, NOW(), NOW())
            """),
            {"id": cid, "company_id": cid, "name": f"停用筛选_{cid}", "val": val},
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

    # 「是」→ 仅 True 命中
    request, response = await test_client.get(
        "/api/v1/billing/balances?is_disabled=true",
        headers=headers,
    )
    assert response.status == 200
    customer_ids = [item["customer_id"] for item in response.json["data"]["list"]]
    assert cid_true in customer_ids
    assert cid_null not in customer_ids
    assert cid_false not in customer_ids

    # 「否」→ False 与 NULL 都命中
    request, response = await test_client.get(
        "/api/v1/billing/balances?is_disabled=false",
        headers=headers,
    )
    assert response.status == 200
    customer_ids = [item["customer_id"] for item in response.json["data"]["list"]]
    assert cid_false in customer_ids
    assert cid_null in customer_ids
    assert cid_true not in customer_ids


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
@pytest.mark.smoke
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
@pytest.mark.smoke
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
    """测试 balance-stats 预付费总余额计算"""
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
    # 测试客户为预付费，total_balance_prepaid 应包含 real + bonus
    assert data["data"]["total_balance_prepaid"] == 12000.00
    assert data["data"]["prepaid_customers"] == 1
    # 无后付费客户
    assert data["data"]["total_balance_postpaid"] == 0.0
    assert data["data"]["postpaid_customers"] == 0
    assert data["data"]["postpaid_receivable"] == 0.0


@pytest.mark.asyncio
async def test_balance_stats_splits_prepaid_and_postpaid(test_client, auth_token, db_session):
    """测试 balance-stats 按结算类型拆分：未设置结算类型归入预付费，后付费余额为负即应收款"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # (结算类型, 余额)：预付费 5000、未设置 7000、后付费欠款 -3000
    configs: list[tuple[str | None, float]] = [
        ("prepaid", 5000.0),
        (None, 7000.0),
        ("postpaid", -3000.0),
    ]
    for st, amount in configs:
        cid = _unique_customer_id(97000)
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   created_at, updated_at)
            VALUES (:id, :company_id, :name, 'enterprise', 'monthly', :type, NOW(), NOW())
            """),
            {"id": cid, "company_id": cid, "name": f"分组统计_{cid}", "type": st},
        )
        db_session.execute(
            text("""
            INSERT INTO customer_balances
                (customer_id, total_amount, real_amount, bonus_amount,
                 used_total, used_real, used_bonus, created_at, updated_at)
            VALUES (:cid, :amount, :amount, 0, 0, 0, 0, NOW(), NOW())
            """),
            {"cid": cid, "amount": amount},
        )
    db_session.commit()

    request, response = await test_client.get(
        "/api/v1/billing/balance-stats",
        headers=headers,
    )

    assert response.status == 200
    data = response.json["data"]
    # 预付费卡片 = 预付费 + 未设置（NULL）
    assert data["total_balance_prepaid"] == 12000.00
    assert data["prepaid_customers"] == 2
    # 后付费卡片 = 欠款负数，应收款为其相反数
    assert data["total_balance_postpaid"] == -3000.00
    assert data["postpaid_customers"] == 1
    assert data["postpaid_receivable"] == 3000.00
    # 余额不足（<10000）仅统计预付费：5000 与 7000 命中，后付费欠款不计入
    assert data["low_balance_count"] == 2


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
@pytest.mark.smoke
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
async def test_get_invoices_filter_industry_type_and_erp_system(
    test_client, auth_token, db_session
):
    """测试结算单列表筛选 — industry_type（按行业名称）+ erp_system（按 ERP value）"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid_a = _unique_customer_id(96000)
    cid_b = _unique_customer_id(96500)

    # 行业字典（唯一名，避免与其它并行测试冲突）
    industry_a = f"互联网_{uuid.uuid4().hex[:6]}"
    industry_b = f"房地产_{uuid.uuid4().hex[:6]}"
    db_session.execute(
        text("""
        INSERT INTO industry_types (name, sort_order, created_at)
        VALUES (:a, 1, NOW()), (:b, 2, NOW())
        """),
        {"a": industry_a, "b": industry_b},
    )
    db_session.commit()
    industry_map = {
        row.name: row.id
        for row in db_session.execute(
            text("SELECT id, name FROM industry_types WHERE name IN (:a, :b)"),
            {"a": industry_a, "b": industry_b},
        )
    }

    # 客户A：ERP=yonyou + 行业A；客户B：ERP=kingdee + 行业B
    for cid, erp, industry in [(cid_a, "yonyou", industry_a), (cid_b, "kingdee", industry_b)]:
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   erp_system, created_at, updated_at)
            VALUES (:id, :company_id, :name, 'enterprise', 'monthly', 'prepaid',
                    :erp, NOW(), NOW())
            """),
            {"id": cid, "company_id": cid, "name": f"行业ERP筛选_{cid}", "erp": erp},
        )
        db_session.execute(
            text("""
            INSERT INTO customer_profiles (customer_id, industry_type_id, created_at)
            VALUES (:cid, :industry_id, NOW())
            """),
            {"cid": cid, "industry_id": industry_map[industry]},
        )
        db_session.execute(
            text("""
            INSERT INTO invoices (invoice_no, customer_id, period_start, period_end,
                                  total_amount, discount_amount, status, is_auto_generated,
                                  detail_file_status, created_at, updated_at)
            VALUES (:no, :cid, '2026-01-01', '2026-01-31', 100, 0, 'draft', FALSE,
                    'pending', NOW(), NOW())
            """),
            {"no": f"INV-FILTER-{uuid.uuid4().hex[:8]}", "cid": cid},
        )
    db_session.commit()

    async def _fetch(**params):
        query = "&".join(f"{k}={v}" for k, v in params.items())
        _request, response = await test_client.get(
            f"/api/v1/billing/invoices?{query}",
            headers=headers,
        )
        assert response.status == 200
        assert response.json["code"] == 0
        return response.json["data"]

    # 行业筛选（按名称）：仅含客户A
    data = await _fetch(industry_type=industry_a)
    customer_ids = [item["customer_id"] for item in data["list"]]
    assert cid_a in customer_ids
    assert cid_b not in customer_ids

    # ERP 筛选（按 value）：仅含客户B
    data = await _fetch(erp_system="kingdee")
    customer_ids = [item["customer_id"] for item in data["list"]]
    assert cid_b in customer_ids
    assert cid_a not in customer_ids

    # 组合筛选：互斥条件应为空
    data = await _fetch(industry_type=industry_a, erp_system="kingdee")
    assert data["list"] == []

    # 无筛选：两条都在（outerjoin 不产生重复、不遗漏）
    data = await _fetch()
    customer_ids = [item["customer_id"] for item in data["list"]]
    assert cid_a in customer_ids
    assert cid_b in customer_ids

    # total 与列表长度一致（join/where 同时作用于计数）
    assert data["total"] >= 2


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
@pytest.mark.smoke
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
@pytest.mark.smoke
async def test_invoice_workflow_full(test_client, auth_token, test_customer_with_balance):
    """测试结算单完整工作流：生成 -> 提交 -> 确认（自动扣款 -> 完成）

    新流程中 confirm 步骤会自动执行余额扣款，成功后直接进入 completed 状态，
    不再需要单独的 pay 和 complete 步骤。
    """
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

    # 2. 提交结算单（无 manager_id 时回退到 pending_customer）
    submit_req, submit_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/submit",
        headers=headers,
    )
    assert submit_res.status == 200
    assert submit_res.json["code"] == 0

    # 3. 确认结算单（自动扣款 -> completed）
    confirm_req, confirm_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/confirm",
        headers=headers,
    )
    assert confirm_res.status == 200
    assert confirm_res.json["code"] == 0

    # 4. 验证最终状态为 completed（confirm 已自动完成扣款）
    detail_req, detail_res = await test_client.get(
        f"/api/v1/billing/invoices/{invoice_id}",
        headers=headers,
    )
    assert detail_res.status == 200
    assert detail_res.json["data"]["status"] == "completed"


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
@pytest.mark.smoke
async def test_complete_invoice_insufficient_balance(
    test_client, auth_token, test_customer_with_balance
):
    """测试完成结算 - 余额不足时按欠费模式扣款（real_amount 变负）

    业务契约：consume 允许余额不足强制扣款（欠费模式），confirm 自动扣款
    后状态直接变为 completed，不再有独立的 complete 扣款失败路径。
    """
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer_with_balance["id"]

    # 生成一个金额很大的结算单（远超客户余额 45000）
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

    # 提交 → 客户确认（无运营经理时 submit 直接到 pending_customer）
    await test_client.post(f"/api/v1/billing/invoices/{invoice_id}/submit", headers=headers)
    confirm_req, confirm_res = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/confirm",
        headers=headers,
    )
    assert confirm_res.json["code"] == 0
    assert "扣款" in confirm_res.json["message"]

    # 状态应为 completed（confirm 自动扣款完成）
    detail_req, detail_res = await test_client.get(
        f"/api/v1/billing/invoices/{invoice_id}",
        headers=headers,
    )
    assert detail_res.json["data"]["status"] == "completed"

    # 余额应为负（欠费模式：100 万扣款远超 45000 可用余额，real_amount 变负）
    balance_req, balance_res = await test_client.get(
        f"/api/v1/billing/customers/{customer_id}/balance",
        headers=headers,
    )
    assert balance_res.json["code"] == 0
    final_total = Decimal(str(balance_res.json["data"]["total_amount"]))
    assert final_total < 0, f"欠费模式下余额应为负，实际 {final_total}"


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
    # items 由 calculate_items_from_rules 按客户用量 + 定价规则动态计算，
    # 与 generate 时传入的 items 无关；无用量/无规则客户返回空列表
    assert "items" in data["data"]
    assert isinstance(data["data"]["items"], list)
    # 客户与状态字段应存在
    assert data["data"]["customer_id"] == customer_id
    assert data["data"]["status"] in (
        "draft",
        "pending_ops",
        "pending_sales",
        "pending_customer",
        "paid",
        "completed",
    )


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
@pytest.mark.smoke
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
async def test_cancel_invoice_wrong_state(test_client, auth_token, test_customer_with_balance):
    """测试取消结算单 API - 错误状态

    新流程中 confirm 步骤会自动扣款并进入 completed 状态，
    completed 状态不可取消，因此 cancel 应返回 400。
    """
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = test_customer_with_balance["id"]

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

    # 提交并确认（confirm 自动扣款 -> completed）
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

    # 验证状态已变为 completed（confirm 自动完成扣款）
    detail_req, detail_res = await test_client.get(
        f"/api/v1/billing/invoices/{invoice_id}",
        headers=headers,
    )
    assert detail_res.json["data"]["status"] == "completed"

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


@pytest.fixture
def pricing_rule_customer(db_session):
    """创建独立客户供定价规则写入用例使用（返回 customer_id）

    必须真实落库：定价规则对 customers 有外键约束，凭空构造的 id 会在写库时报 500。
    独立客户同时避免与其他用例的规则发生同客户重叠冲突。
    """
    customer_id = _unique_customer_id(99000)
    db_session.execute(
        text("DELETE FROM pricing_rules WHERE customer_id = :id"), {"id": customer_id}
    )
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer_id})
    db_session.execute(
        text(
            """
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   created_at, updated_at)
            VALUES (:id, :cid, :name, 'enterprise', 'monthly', 'prepaid', NOW(), NOW())
            """
        ),
        {"id": customer_id, "cid": customer_id, "name": f"首档校验客户_{customer_id}"},
    )
    db_session.commit()

    try:
        yield customer_id
    finally:
        db_session.execute(
            text("DELETE FROM pricing_rules WHERE customer_id = :id"), {"id": customer_id}
        )
        db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer_id})
        db_session.commit()


@pytest.mark.asyncio
async def test_create_pricing_rule_rejects_non_zero_first_tier_min(
    test_client, auth_token, pricing_rule_customer
):
    """创建定价规则：首档 min 非 0 返回 40001

    首档起点非 0 时计费语义不明确：`cost_calc._calc_tiered` 不减去该偏移，超档用量会落到
    更便宜的下一档（静默少收），单档无上界时 min 更是完全不参与计算。写入侧必须拒绝，
    否则脏规则落库后由结算阶段静默承担。
    """
    headers = {"Authorization": f"Bearer {auth_token}"}

    request, response = await test_client.post(
        "/api/v1/billing/pricing-rules",
        json={
            "customer_id": pricing_rule_customer,
            "device_type": "X",
            "pricing_type": "tiered",
            "tiers": [
                {"min": 5, "max": 100, "price": 10},
                {"min": 101, "max": None, "price": 8},
            ],
            "effective_date": "2026-07-01",
        },
        headers=headers,
    )

    assert response.status == 400
    assert response.json["code"] == 40001
    assert "首档阶梯 min 必须为 0" in response.json["message"]


@pytest.mark.asyncio
async def test_update_pricing_rule_rejects_non_zero_first_tier_min(
    test_client, auth_token, db_session, pricing_rule_customer
):
    """更新定价规则：首档 min 非 0 同样被拒绝，且原规则未被改写"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    _request, created = await test_client.post(
        "/api/v1/billing/pricing-rules",
        json={
            "customer_id": pricing_rule_customer,
            "device_type": "X",
            "layer_type": "single",
            "pricing_type": "tiered",
            "tiers": [
                {"min": 0, "max": 100, "price": 10},
                {"min": 101, "max": None, "price": 8},
            ],
            "effective_date": "2026-08-01",
        },
        headers=headers,
    )
    assert created.status == 201, f"创建规则失败: {created.json}"
    rule_id = created.json["data"]["id"]

    _request, response = await test_client.put(
        f"/api/v1/billing/pricing-rules/{rule_id}",
        json={"tiers": [{"min": 5, "max": None, "price": 10}]},
        headers=headers,
    )

    assert response.status == 400
    assert response.json["code"] == 40001
    assert "首档阶梯 min 必须为 0" in response.json["message"]

    # 拒绝必须发生在落库前：原规则仍保持合法形态
    stored = db_session.execute(
        text("SELECT tiers FROM pricing_rules WHERE id = :id"), {"id": rule_id}
    ).scalar()
    assert stored is not None
    assert stored[0]["min"] == 0
    assert stored[0]["max"] == 100


@pytest.mark.asyncio
async def test_pricing_rule_list_dates_round_trip_to_edit(
    test_client, auth_token, db_session, pricing_rule_customer
):
    """计费规则编辑回填契约：列表输出的日期必须能原样回灌编辑接口

    DB 里 effective_date 存的是 UTC 时刻（CST 当日 00:00 -> UTC 前一日 16:00）。
    列表若用 isoformat() 输出，前端编辑弹窗会把 "2026-03-31T16:00:00+00:00" 回填进
    日期选择器并原样提交，而 check-conflict / PUT 用 date.fromisoformat() 解析（只接受
    "YYYY-MM-DD"），于是改任何字段（如单价）都报「参数格式错误」。列表必须按 CST
    日期串输出，保证「列表 → 编辑提交」往返闭合。
    """
    headers = {"Authorization": f"Bearer {auth_token}"}

    _request, created = await test_client.post(
        "/api/v1/billing/pricing-rules",
        json={
            "customer_id": pricing_rule_customer,
            "device_type": "X",
            "layer_type": "single",
            "pricing_type": "fixed",
            "unit_price": 10.0,
            "effective_date": "2026-04-01",
            "expiry_date": "2026-12-31",
        },
        headers=headers,
    )
    assert created.status == 201, created.json
    rule_id = created.json["data"]["id"]

    _request, listed = await test_client.get(
        "/api/v1/billing/pricing-rules",
        params={"customer_id": pricing_rule_customer},
        headers=headers,
    )
    assert listed.status == 200
    rule = next(r for r in listed.json["data"]["list"] if r["id"] == rule_id)
    assert rule["effective_date"] == "2026-04-01"
    assert rule["expiry_date"] == "2026-12-31"

    # 前端编辑流程：先冲突检查，再提交（单价 10 -> 12.5），日期一律原样回填
    _request, conflict = await test_client.get(
        "/api/v1/billing/pricing-rules/check-conflict",
        params={
            "customer_id": pricing_rule_customer,
            "pricing_type": rule["pricing_type"],
            "device_type": rule["device_type"],
            "layer_type": rule["layer_type"],
            "effective_date": rule["effective_date"],
            "expiry_date": rule["expiry_date"],
            "exclude_id": rule_id,
        },
        headers=headers,
    )
    assert conflict.status == 200, conflict.json
    assert conflict.json["data"]["has_conflict"] is False

    _request, updated = await test_client.put(
        f"/api/v1/billing/pricing-rules/{rule_id}",
        json={
            "customer_id": pricing_rule_customer,
            "device_type": rule["device_type"],
            "layer_type": rule["layer_type"],
            "pricing_type": rule["pricing_type"],
            "unit_price": 12.5,
            "effective_date": rule["effective_date"],
            "expiry_date": rule["expiry_date"],
        },
        headers=headers,
    )
    assert updated.status == 200, updated.json

    # 有效期往返闭合：仍是 CST 2026-04-01（UTC 2026-03-31T16:00）
    stored = db_session.execute(
        text("SELECT unit_price, effective_date FROM pricing_rules WHERE id = :id"),
        {"id": rule_id},
    ).fetchone()
    assert float(stored[0]) == 12.5
    assert stored[1] == local_date_to_utc_start("2026-04-01")


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
@pytest.mark.smoke
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
            "pricing_type": "fixed",
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
@pytest.mark.smoke
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
            "pricing_type": "fixed",
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


# ==================== Settlement Account (代扣余额) Integration ====================


@pytest.fixture
async def test_customers_pair(db_session, test_user, worker_id):
    """创建一对测试客户：被结算客户 A + 结算账户客户 B"""
    import random

    wid = worker_id if worker_id != "master" else "local"
    base = int(f"{hash(wid) % 10000:04d}{random.randint(1000, 9999)}")
    ids = {"a": base, "b": base + 1}

    for key, cid in ids.items():
        db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
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
                "name": f"结算测试客户_{key.upper()}_{cid}",
                "account_type": "enterprise",
                "cycle": "monthly",
                "type": "prepaid",
            },
        )
    db_session.commit()

    yield ids

    for cid in ids.values():
        db_session.execute(
            text(
                "DELETE FROM invoice_items WHERE invoice_id IN "
                "(SELECT id FROM invoices WHERE customer_id = :id)"
            ),
            {"id": cid},
        )
        # 代扣笔的 consumption_records.customer_id 可能是结算账户客户，
        # 须按关联 invoice 删除，否则外键阻塞 invoices 清理
        db_session.execute(
            text(
                "DELETE FROM consumption_records WHERE invoice_id IN "
                "(SELECT id FROM invoices WHERE customer_id = :id)"
            ),
            {"id": cid},
        )
        db_session.execute(
            text("DELETE FROM consumption_records WHERE customer_id = :id"), {"id": cid}
        )
        db_session.execute(text("DELETE FROM invoices WHERE customer_id = :id"), {"id": cid})
        db_session.execute(
            text("DELETE FROM customer_balances WHERE customer_id = :id"), {"id": cid}
        )
        db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
    db_session.commit()


async def _set_balance(db_session, customer_id: int, total: float, real: float, bonus: float):
    """直接写入客户余额（测试专用）"""
    db_session.execute(
        text("DELETE FROM customer_balances WHERE customer_id = :cid"), {"cid": customer_id}
    )
    db_session.execute(
        text("""
        INSERT INTO customer_balances
            (customer_id, total_amount, real_amount, bonus_amount,
             used_total, used_real, used_bonus, created_at, updated_at)
        VALUES (:cid, :total, :real, :bonus, 0, 0, 0, NOW(), NOW())
        """),
        {"cid": customer_id, "total": total, "real": real, "bonus": bonus},
    )
    db_session.commit()


async def _get_balance(test_client, auth_token, customer_id: int) -> dict:
    req, resp = await test_client.get(
        f"/api/v1/billing/customers/{customer_id}/balance",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status == 200
    return resp.json["data"]


@pytest.mark.asyncio
async def test_customer_settlement_account_roundtrip(test_client, auth_token, test_customers_pair):
    """客户配置往返：PUT 成功 + GET 返回 id/name；自引用 400"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    a, b = test_customers_pair["a"], test_customers_pair["b"]

    req, resp = await test_client.put(
        f"/api/v1/customers/{a}",
        json={"settlement_account_id": b},
        headers=headers,
    )
    assert resp.status == 200
    assert resp.json["code"] == 0

    req, resp = await test_client.get(
        f"/api/v1/customers/{a}",
        headers=headers,
    )
    assert resp.status == 200
    data = resp.json["data"]
    assert data["settlement_account_id"] == b
    assert data["settlement_account_name"] is not None

    # 自引用拒绝
    req, resp = await test_client.put(
        f"/api/v1/customers/{a}",
        json={"settlement_account_id": a},
        headers=headers,
    )
    assert resp.status == 400

    # 目标不存在拒绝
    req, resp = await test_client.put(
        f"/api/v1/customers/{a}",
        json={"settlement_account_id": 999999999},
        headers=headers,
    )
    assert resp.status == 400


@pytest.mark.asyncio
async def test_generate_invoice_snapshots_settlement_account(
    test_client, auth_token, db_session, test_customers_pair
):
    """生成快照：客户配置结算账户后，生成的结算单详情/列表均含结算账户字段"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    a, b = test_customers_pair["a"], test_customers_pair["b"]

    db_session.execute(
        text("UPDATE customers SET settlement_account_id = :b WHERE id = :a"),
        {"a": a, "b": b},
    )
    db_session.commit()

    req, resp = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": a,
            "period_start": "2026-05-01",
            "period_end": "2026-05-31",
            "items": [
                {"device_type": "X", "layer_type": "single", "quantity": 5, "unit_price": 10}
            ],
        },
        headers=headers,
    )
    assert resp.status == 201
    invoice_id = resp.json["data"]["id"]

    req, resp = await test_client.get(
        f"/api/v1/billing/invoices/{invoice_id}",
        headers=headers,
    )
    assert resp.status == 200
    data = resp.json["data"]
    assert data["settlement_account_id"] == b
    assert data["settlement_account_name"] is not None

    req, resp = await test_client.get(
        "/api/v1/billing/invoices",
        params={"customer_id": a},
        headers=headers,
    )
    assert resp.status == 200
    row = next(i for i in resp.json["data"]["list"] if i["id"] == invoice_id)
    assert row["settlement_account_id"] == b


@pytest.mark.asyncio
async def test_update_invoice_settlement_account_lock_after_confirm(
    test_client, auth_token, db_session, test_customers_pair
):
    """详情修改：审批流中可改；customer_confirmed 后锁定 400"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    a, b = test_customers_pair["a"], test_customers_pair["b"]

    req, resp = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": a,
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "items": [
                {"device_type": "X", "layer_type": "single", "quantity": 5, "unit_price": 10}
            ],
        },
        headers=headers,
    )
    invoice_id = resp.json["data"]["id"]

    # draft 状态可改
    req, resp = await test_client.put(
        f"/api/v1/billing/invoices/{invoice_id}/settlement-account",
        json={"settlement_account_id": b},
        headers=headers,
    )
    assert resp.status == 200
    assert resp.json["data"]["settlement_account_id"] == b

    # 推进到 customer_confirmed
    await test_client.post(f"/api/v1/billing/invoices/{invoice_id}/submit", headers=headers)
    await test_client.post(f"/api/v1/billing/invoices/{invoice_id}/confirm", headers=headers)

    # 客户确认后锁定
    req, resp = await test_client.put(
        f"/api/v1/billing/invoices/{invoice_id}/settlement-account",
        json={"settlement_account_id": None},
        headers=headers,
    )
    assert resp.status == 400
    assert "不可修改" in resp.json["message"]


@pytest.mark.asyncio
async def test_update_invoice_settlement_account_rejects_self_and_missing(
    test_client, auth_token, test_customers_pair
):
    """详情修改：自引用与目标不存在均 400"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    a = test_customers_pair["a"]

    req, resp = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": a,
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "items": [
                {"device_type": "X", "layer_type": "single", "quantity": 5, "unit_price": 10}
            ],
        },
        headers=headers,
    )
    invoice_id = resp.json["data"]["id"]

    req, resp = await test_client.put(
        f"/api/v1/billing/invoices/{invoice_id}/settlement-account",
        json={"settlement_account_id": a},
        headers=headers,
    )
    assert resp.status == 400

    req, resp = await test_client.put(
        f"/api/v1/billing/invoices/{invoice_id}/settlement-account",
        json={"settlement_account_id": 999999999},
        headers=headers,
    )
    assert resp.status == 400


@pytest.mark.asyncio
async def test_deduction_via_settlement_account_e2e(
    test_client, auth_token, db_session, test_customers_pair
):
    """端到端核心：A（结算账户=B）确认后扣 B 余额，A 余额不变；消耗记录双方可见"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    a, b = test_customers_pair["a"], test_customers_pair["b"]

    await _set_balance(db_session, b, 1000.0, 1000.0, 0.0)
    await _set_balance(db_session, a, 500.0, 500.0, 0.0)

    db_session.execute(
        text("UPDATE customers SET settlement_account_id = :b WHERE id = :a"),
        {"a": a, "b": b},
    )
    db_session.commit()

    req, resp = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": a,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "items": [
                {"device_type": "X", "layer_type": "single", "quantity": 30, "unit_price": 10}
            ],
        },
        headers=headers,
    )
    assert resp.status == 201
    invoice_id = resp.json["data"]["id"]

    await test_client.post(f"/api/v1/billing/invoices/{invoice_id}/submit", headers=headers)
    req, resp = await test_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/confirm", headers=headers
    )
    assert resp.status == 200
    assert resp.json["code"] == 0

    # B 余额减 300，A 余额不变
    bal_b = await _get_balance(test_client, auth_token, b)
    bal_a = await _get_balance(test_client, auth_token, a)
    assert bal_b["total_amount"] == pytest.approx(700.0, abs=0.01)
    assert bal_a["total_amount"] == pytest.approx(500.0, abs=0.01)

    # 消耗记录：被结算客户 A 与结算账户客户 B 均可见该笔
    req, resp = await test_client.get(
        "/api/v1/billing/consumption-records",
        params={"customer_id": a, "page_size": 100},
        headers=headers,
    )
    assert resp.status == 200
    a_records = [r for r in resp.json["data"]["list"] if r["invoice_id"] == invoice_id]
    assert len(a_records) == 1
    assert a_records[0]["customer_id"] == b  # 实际扣款客户是 B

    req, resp = await test_client.get(
        "/api/v1/billing/consumption-records",
        params={"customer_id": b, "page_size": 100},
        headers=headers,
    )
    assert resp.status == 200
    b_records = [r for r in resp.json["data"]["list"] if r["invoice_id"] == invoice_id]
    assert len(b_records) == 1
    assert b_records[0]["customer_id"] == b


@pytest.mark.asyncio
async def test_get_invoices_filter_by_managers(test_client, auth_token, db_session):
    """测试结算单列表按运营/销售经理筛选"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid_a = _unique_customer_id(97000)
    cid_b = _unique_customer_id(97500)
    manager_a, sales_a = _unique_customer_id(97100), _unique_customer_id(97200)
    manager_b, sales_b = _unique_customer_id(97300), _unique_customer_id(97400)

    # 4 个经理用户 + 2 个客户
    for uid in (manager_a, sales_a, manager_b, sales_b):
        db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": uid})
        db_session.execute(
            text("""
            INSERT INTO users (id, username, password_hash, real_name, is_active,
                               created_at, updated_at)
            VALUES (:id, :username, 'x', :name, TRUE, NOW(), NOW())
            """),
            {"id": uid, "username": f"mgr_{uid}", "name": f"经理{uid}"},
        )
    for cid, mgr, sales in [(cid_a, manager_a, sales_a), (cid_b, manager_b, sales_b)]:
        db_session.execute(text("DELETE FROM invoices WHERE customer_id = :id"), {"id": cid})
        db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
        db_session.execute(
            text("""
            INSERT INTO customers (id, company_id, name, account_type,
                                   settlement_cycle, settlement_type,
                                   manager_id, sales_manager_id,
                                   created_at, updated_at)
            VALUES (:id, :company_id, :name, 'enterprise', 'monthly', 'prepaid',
                    :mgr, :sales, NOW(), NOW())
            """),
            {
                "id": cid,
                "company_id": cid,
                "name": f"经理筛选_{cid}",
                "mgr": mgr,
                "sales": sales,
            },
        )
        db_session.execute(
            text("""
            INSERT INTO invoices (invoice_no, customer_id, period_start, period_end,
                                  total_amount, discount_amount, status, is_auto_generated,
                                  detail_file_status, created_at, updated_at)
            VALUES (:no, :cid, '2026-01-01', '2026-01-31', 100, 0, 'draft', FALSE,
                    'pending', NOW(), NOW())
            """),
            {"no": f"INV-MGR-{uuid.uuid4().hex[:8]}", "cid": cid},
        )
    db_session.commit()

    try:

        async def _fetch(**params):
            query = "&".join(f"{k}={v}" for k, v in params.items())
            _request, response = await test_client.get(
                f"/api/v1/billing/invoices?{query}",
                headers=headers,
            )
            assert response.status == 200
            assert response.json["code"] == 0
            return response.json["data"]

        # 运营经理筛选：仅含客户A
        data = await _fetch(manager_id=manager_a)
        customer_ids = [item["customer_id"] for item in data["list"]]
        assert cid_a in customer_ids
        assert cid_b not in customer_ids

        # 销售经理筛选：仅含客户B
        data = await _fetch(sales_manager_id=sales_b)
        customer_ids = [item["customer_id"] for item in data["list"]]
        assert cid_b in customer_ids
        assert cid_a not in customer_ids

        # 组合筛选：互斥条件应为空
        data = await _fetch(manager_id=manager_a, sales_manager_id=sales_b)
        assert data["list"] == []
    finally:
        for cid in (cid_a, cid_b):
            db_session.execute(
                text(
                    "DELETE FROM invoice_items WHERE invoice_id IN "
                    "(SELECT id FROM invoices WHERE customer_id = :id)"
                ),
                {"id": cid},
            )
            db_session.execute(text("DELETE FROM invoices WHERE customer_id = :id"), {"id": cid})
            db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
        for uid in (manager_a, sales_a, manager_b, sales_b):
            db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": uid})
        db_session.commit()


@pytest.mark.asyncio
async def test_batch_submit_cancel_delete_invoices(test_client, auth_token, db_session):
    """测试结算单批量提交/取消/删除端点"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid = _unique_customer_id(98000)
    db_session.execute(text("DELETE FROM invoices WHERE customer_id = :id"), {"id": cid})
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
    db_session.execute(
        text("""
        INSERT INTO customers (id, company_id, name, account_type,
                               settlement_cycle, settlement_type,
                               created_at, updated_at)
        VALUES (:id, :company_id, :name, 'enterprise', 'monthly', 'prepaid', NOW(), NOW())
        """),
        {"id": cid, "company_id": cid, "name": f"批量操作_{cid}"},
    )
    db_session.commit()

    invoice_ids = []
    try:
        # 3 张 draft + 1 张 pending_ops（提交时应被跳过）
        for i, status in enumerate(["draft", "draft", "draft", "pending_ops"]):
            result = db_session.execute(
                text("""
                INSERT INTO invoices (invoice_no, customer_id, period_start, period_end,
                                      total_amount, discount_amount, status, is_auto_generated,
                                      detail_file_status, created_at, updated_at)
                VALUES (:no, :cid, '2026-01-01', '2026-01-31', 100, 0, :status, FALSE,
                        'pending', NOW(), NOW())
                RETURNING id
                """),
                {
                    "no": f"INV-BATCH-{uuid.uuid4().hex[:8]}",
                    "cid": cid,
                    "status": status,
                },
            )
            invoice_ids.append(result.scalar())
        db_session.commit()

        # 批量提交：3 success + 1 skipped
        _req, resp = await test_client.post(
            "/api/v1/billing/invoices/batch-submit",
            json={"ids": invoice_ids},
            headers=headers,
        )
        assert resp.status == 200
        assert resp.json["code"] == 0
        data = resp.json["data"]
        assert data["success_count"] == 3
        assert len(data["skipped"]) == 1
        assert data["skipped"][0]["id"] == invoice_ids[3]

        # 批量取消：3 张已提交的可取消成功
        _req, resp = await test_client.post(
            "/api/v1/billing/invoices/batch-cancel",
            json={"ids": invoice_ids[:3]},
            headers=headers,
        )
        assert resp.status == 200
        assert resp.json["data"]["success_count"] == 3

        # 批量删除：软删全部 4 张
        _req, resp = await test_client.post(
            "/api/v1/billing/invoices/batch-delete",
            json={"ids": invoice_ids},
            headers=headers,
        )
        assert resp.status == 200
        assert resp.json["data"]["success_count"] == 4

        remaining = db_session.execute(
            text("SELECT COUNT(*) FROM invoices WHERE customer_id = :id AND deleted_at IS NULL"),
            {"id": cid},
        ).scalar()
        assert remaining == 0
    finally:
        db_session.execute(
            text(
                "DELETE FROM invoice_items WHERE invoice_id IN "
                "(SELECT id FROM invoices WHERE customer_id = :id)"
            ),
            {"id": cid},
        )
        db_session.execute(text("DELETE FROM invoices WHERE customer_id = :id"), {"id": cid})
        db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
        db_session.commit()


@pytest.mark.asyncio
async def test_get_invoice_detail_logs_counts_and_default_filter(
    test_client, auth_token, db_session
):
    """测试明细文件生成日志：默认过滤 completed + counts 统计 + status 精筛"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid = _unique_customer_id(98500)
    db_session.execute(text("DELETE FROM invoices WHERE customer_id = :id"), {"id": cid})
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
    db_session.execute(
        text("""
        INSERT INTO customers (id, company_id, name, account_type,
                               settlement_cycle, settlement_type,
                               created_at, updated_at)
        VALUES (:id, :company_id, :name, 'enterprise', 'monthly', 'prepaid', NOW(), NOW())
        """),
        {"id": cid, "company_id": cid, "name": f"明细状态_{cid}"},
    )
    db_session.commit()

    try:
        # pending / failed / completed 各一张
        for file_status in ("pending", "failed", "completed"):
            db_session.execute(
                text("""
                INSERT INTO invoices (invoice_no, customer_id, period_start, period_end,
                                      total_amount, discount_amount, status, is_auto_generated,
                                      detail_file_status, created_at, updated_at)
                VALUES (:no, :cid, '2026-01-01', '2026-01-31', 100, 0, 'draft', FALSE,
                        :fs, NOW(), NOW())
                """),
                {
                    "no": f"INV-LOG-{uuid.uuid4().hex[:8]}",
                    "cid": cid,
                    "fs": file_status,
                },
            )
        db_session.commit()

        _req, resp = await test_client.get(
            "/api/v1/billing/invoices/detail-logs",
            params={"customer_id": cid},
            headers=headers,
        )
        assert resp.status == 200
        data = resp.json["data"]
        # 默认过滤：不含 completed
        assert all(item["detail_file_status"] != "completed" for item in data["list"])
        # counts：各状态统计正确（不受 status_filter 影响）
        assert data["counts"]["pending"] == 1
        assert data["counts"]["failed"] == 1
        assert data["counts"]["completed"] == 1

        # status=failed 精筛：仅失败
        _req, resp = await test_client.get(
            "/api/v1/billing/invoices/detail-logs",
            params={"customer_id": cid, "status": "failed"},
            headers=headers,
        )
        assert resp.status == 200
        data = resp.json["data"]
        assert len(data["list"]) == 1
        assert data["list"][0]["detail_file_status"] == "failed"

        # status=completed 显式查看：仅完成
        _req, resp = await test_client.get(
            "/api/v1/billing/invoices/detail-logs",
            params={"customer_id": cid, "status": "completed"},
            headers=headers,
        )
        assert resp.status == 200
        data = resp.json["data"]
        assert len(data["list"]) == 1
        assert data["list"][0]["detail_file_status"] == "completed"
    finally:
        db_session.execute(text("DELETE FROM invoices WHERE customer_id = :id"), {"id": cid})
        db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
        db_session.commit()


@pytest.mark.asyncio
async def test_regenerate_detail_batch(test_client, auth_token, db_session):
    """测试批量重新生成明细文件端点：triggered 计数 + 不存在单条计入 failed"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    cid = _unique_customer_id(99000)
    db_session.execute(text("DELETE FROM invoices WHERE customer_id = :id"), {"id": cid})
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
    db_session.execute(
        text("""
        INSERT INTO customers (id, company_id, name, account_type,
                               settlement_cycle, settlement_type,
                               created_at, updated_at)
        VALUES (:id, :company_id, :name, 'enterprise', 'monthly', 'prepaid', NOW(), NOW())
        """),
        {"id": cid, "company_id": cid, "name": f"批量重生成_{cid}"},
    )
    db_session.commit()

    try:
        result = db_session.execute(
            text("""
            INSERT INTO invoices (invoice_no, customer_id, period_start, period_end,
                                  total_amount, discount_amount, status, is_auto_generated,
                                  detail_file_status, created_at, updated_at)
            VALUES (:no, :cid, '2026-01-01', '2026-01-31', 100, 0, 'draft', FALSE,
                    'failed', NOW(), NOW())
            RETURNING id
            """),
            {"no": f"INV-REGEN-{uuid.uuid4().hex[:8]}", "cid": cid},
        )
        invoice_id = result.scalar()
        db_session.commit()

        missing_id = invoice_id + 100000
        _req, resp = await test_client.post(
            "/api/v1/billing/invoices/regenerate-detail-batch",
            json={"ids": [invoice_id, missing_id]},
            headers=headers,
        )
        assert resp.status == 200
        assert resp.json["code"] == 0
        data = resp.json["data"]
        assert data["triggered"] == 1
        assert len(data["failed"]) == 1
        assert data["failed"][0]["id"] == missing_id

        # 状态被重置为 pending
        status = db_session.execute(
            text("SELECT detail_file_status FROM invoices WHERE id = :id"), {"id": invoice_id}
        ).scalar()
        assert status == "pending"
    finally:
        db_session.execute(text("DELETE FROM invoices WHERE customer_id = :id"), {"id": cid})
        db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
        db_session.commit()


@pytest.mark.asyncio
async def test_generate_batch_triggers_detail_generation(
    test_client, auth_token, db_session, monkeypatch
):
    """批量生成必须为每张结算单触发明细异步生成（回归：key 名误用导致任务从未入队）

    历史 bug：route 从 generated 项取 "id"，而 service 返回的键名是 "invoice_id"，
    inv_id 恒为 None，任务从未 add_job，全部结算单卡在 pending。
    """
    from app.routes.billing import invoices as invoices_route

    headers = {"Authorization": f"Bearer {auth_token}"}

    cid = _unique_customer_id(99500)
    db_session.execute(text("DELETE FROM invoices WHERE customer_id = :id"), {"id": cid})
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
    db_session.execute(
        text("""
        INSERT INTO customers (id, company_id, name, account_type,
                               settlement_cycle, settlement_type,
                               created_at, updated_at)
        VALUES (:id, :company_id, :name, 'enterprise', 'monthly', 'prepaid', NOW(), NOW())
        """),
        {"id": cid, "company_id": cid, "name": f"触发明细_{cid}"},
    )
    db_session.commit()

    triggered_ids: list[int] = []

    async def fake_trigger(request, invoice_id):
        triggered_ids.append(invoice_id)

    monkeypatch.setattr(invoices_route, "_trigger_detail_generation", fake_trigger)

    try:
        # 只验证触发循环：service 层 mock 掉，直接构造两单 generated 返回
        from unittest.mock import AsyncMock, patch

        from app.services.billing import InvoiceService

        fake_result = {
            "success_count": 2,
            "skipped": [],
            "generated": [
                {"customer_id": cid, "name": "A", "invoice_id": 900001, "invoice_no": "INV-A"},
                {"customer_id": cid, "name": "B", "invoice_id": 900002, "invoice_no": "INV-B"},
            ],
        }
        with patch.object(
            InvoiceService, "generate_invoices_batch", AsyncMock(return_value=fake_result)
        ):
            _req, resp = await test_client.post(
                "/api/v1/billing/invoices/generate-batch",
                json={
                    "pricing_type": "fixed",
                    "period_start": "2026-09-01",
                    "period_end": "2026-09-30",
                },
                headers=headers,
            )

        assert resp.status == 200
        assert sorted(triggered_ids) == [900001, 900002]
    finally:
        db_session.execute(text("DELETE FROM invoices WHERE customer_id = :id"), {"id": cid})
        db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
        db_session.commit()
