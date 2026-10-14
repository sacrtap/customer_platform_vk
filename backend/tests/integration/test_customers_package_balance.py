"""客户管理页包年余额口径 — 集成测试（真实 SQL 路径）

验证客户管理页（列表 / 详情 / 余额预测 / 360 摘要）对包年客户的余额口径
与余额管理页一致：包年年费不进 `CustomerBalance`，余额取「套餐剩余额度」。

覆盖:
- `GET /api/v1/customers` 列表：`balance` / `health` / `is_package` 按包年口径
- `GET /api/v1/customers/<id>` 详情：`balance.total_amount` = 套餐剩余额度
- `GET /api/v1/billing/customers/<id>/balance`：详情余额 Tab 的独立端点
- `GET /api/v1/customers/<id>/balance-forecast`：修复 ORM 对象当数值返回的 bug
- `GET /api/v1/customers/<id>/summary`：360 摘要余额文案
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

CST = timezone(timedelta(hours=8))


def _uid() -> int:
    """生成唯一 id（pricing_rules / daily_consumptions 无默认序列）"""
    import uuid

    return abs(hash(uuid.uuid4().hex[:12])) % 2_000_000_000


def _insert_package_customer(
    db,
    cid: int,
    *,
    base_fee: float,
    consumed: float,
    expired=False,
    is_unlimited=False,
    limit_count=None,
):
    """插入包年客户 + 一条包年规则（可选一条套餐内消耗）"""
    import json as _json

    db.execute(
        text(
            """
            INSERT INTO customers (id, company_id, name, account_type, price_policy,
                                   settlement_cycle, created_at, updated_at)
            VALUES (:id, :cid, :name, '正式账号', 'yearly', 'yearly', NOW(), NOW())
            """
        ),
        {"id": cid, "cid": cid, "name": f"包年客户_{cid}"},
    )
    limits = {"base_fee": base_fee, "is_unlimited": is_unlimited}
    if limit_count is not None:
        limits["limit_count"] = limit_count
    # 年费不入 CustomerBalance；部分客户显式建 0 余额行，验证仍按套餐口径展示
    db.execute(
        text(
            """
            INSERT INTO customer_balances (customer_id, total_amount, real_amount, bonus_amount,
                                           used_total, used_real, used_bonus, created_at, updated_at)
            VALUES (:cid, 0, 0, 0, 0, 0, 0, NOW(), NOW())
            """
        ),
        {"cid": cid},
    )
    now = datetime.now(timezone.utc)
    expiry = now - timedelta(days=30) if expired else now + timedelta(days=200)
    rule_id = db.execute(
        text(
            """
            INSERT INTO pricing_rules (customer_id, device_type, layer_type, pricing_type,
                                       package_type, package_limits, tiers,
                                       effective_date, expiry_date, created_at, updated_at)
            VALUES (:cid, NULL, NULL, 'package', 'A', CAST(:limits AS JSON),
                    CAST('[]' AS JSON), :effective, :expiry, NOW(), NOW())
            RETURNING id
            """
        ),
        {
            "cid": cid,
            "limits": _json.dumps(limits),
            "effective": now - timedelta(days=300),
            "expiry": expiry,
        },
    ).scalar()
    if consumed:
        db.execute(
            text(
                """
                INSERT INTO daily_consumptions (id, customer_id, consumption_date, device_type,
                                                layer_type, order_count, total_floor_count, total_cost,
                                                pricing_rule_id, has_pricing_rule, created_at, updated_at)
                VALUES (:id, :cid, NOW() - INTERVAL '3 days', 'X', 'single', 10, 10, :cost,
                        :rid, TRUE, NOW(), NOW())
                """
            ),
            {"id": _uid(), "cid": cid, "cost": consumed, "rid": rule_id},
        )
    return rule_id


@pytest.mark.asyncio
async def test_customer_list_package_balance_uses_remaining(test_client, auth_token, db_session):
    """客户列表：包年客户 balance = 套餐剩余额度（非 CustomerBalance 的 0），并标记 is_package"""
    cid = 88001
    _insert_package_customer(db_session, cid, base_fee=120000.0, consumed=30000.0, limit_count=1000)
    db_session.commit()

    _req, resp = await test_client.get(
        "/api/v1/customers",
        params={"keyword": f"包年客户_{cid}"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status == 200
    rows = resp.json["data"]["list"]
    assert len(rows) == 1
    row = rows[0]
    # 120000 - 30000 = 90000；而非 CustomerBalance.total_amount = 0
    assert row["balance"] == 90000.0
    assert row["is_package"] is True
    assert row["package_expired"] is False


@pytest.mark.asyncio
async def test_customer_list_package_health_not_high_risk(test_client, auth_token, db_session):
    """客户列表健康度：包年客户按套餐剩余额度判定，不因 CustomerBalance=0 误报高风险"""
    cid = 88002
    _insert_package_customer(db_session, cid, base_fee=120000.0, consumed=30000.0, limit_count=1000)
    db_session.commit()

    _req, resp = await test_client.get(
        "/api/v1/customers",
        params={"keyword": f"包年客户_{cid}"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    row = resp.json["data"]["list"][0]
    # 剩余 90000 有消耗 → healthy（而非 0 余额导致的 high_risk）
    assert row["health"] == "healthy"


@pytest.mark.asyncio
async def test_customer_detail_package_balance(test_client, auth_token, db_session):
    """客户详情：balance.total_amount 为套餐剩余额度"""
    cid = 88003
    _insert_package_customer(db_session, cid, base_fee=100000.0, consumed=25000.0, limit_count=500)
    db_session.commit()

    _req, resp = await test_client.get(
        f"/api/v1/customers/{cid}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status == 200
    assert resp.json["data"]["balance"]["total_amount"] == 75000.0


@pytest.mark.asyncio
async def test_billing_customer_balance_endpoint_package(test_client, auth_token, db_session):
    """详情余额 Tab 端点：包年客户 total_amount = 套餐剩余额度，并返回包年字段"""
    cid = 88004
    _insert_package_customer(db_session, cid, base_fee=80000.0, consumed=10000.0, limit_count=300)
    db_session.commit()

    _req, resp = await test_client.get(
        f"/api/v1/billing/customers/{cid}/balance",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status == 200
    data = resp.json["data"]
    assert data["total_amount"] == 70000.0
    assert data["is_package"] is True
    assert data["package_remaining_amount"] == 70000.0
    # 限量 300 - 累计订单量 10 = 290
    assert data["package_remaining_count"] == 290.0


@pytest.mark.asyncio
async def test_balance_forecast_returns_numeric_balance(test_client, auth_token, db_session):
    """余额预测：返回数值型 balance（修复把 ORM 对象直接返回的 bug），包年取剩余额度"""
    cid = 88005
    _insert_package_customer(db_session, cid, base_fee=50000.0, consumed=20000.0, limit_count=100)
    db_session.commit()

    _req, resp = await test_client.get(
        f"/api/v1/customers/{cid}/balance-forecast",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status == 200
    data = resp.json["data"]
    assert isinstance(data["balance"], (int, float))
    assert data["balance"] == 30000.0


@pytest.mark.asyncio
async def test_customer_summary_package_balance_text(test_client, auth_token, db_session):
    """360 摘要：包年客户余额文案为套餐剩余额度"""
    cid = 88006
    _insert_package_customer(db_session, cid, base_fee=60000.0, consumed=15000.0, limit_count=100)
    db_session.commit()

    _req, resp = await test_client.get(
        f"/api/v1/customers/{cid}/summary",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status == 200
    assert resp.json["data"]["balance"] == "¥45,000"


@pytest.mark.asyncio
async def test_customer_list_sort_by_balance_package_first(test_client, auth_token, db_session):
    """按余额排序：包年客户以套餐剩余额度参与（而非 CustomerBalance 的 0）"""
    cid_pkg = 88007
    cid_prepaid = 88008
    _insert_package_customer(
        db_session, cid_pkg, base_fee=200000.0, consumed=10000.0, limit_count=1000
    )  # 剩余 190000
    db_session.execute(
        text(
            """
            INSERT INTO customers (id, company_id, name, account_type, price_policy,
                                   settlement_cycle, settlement_type, created_at, updated_at)
            VALUES (:id, :cid, :name, '正式账号', 'pricing', 'monthly', 'prepaid', NOW(), NOW())
            """
        ),
        {"id": cid_prepaid, "cid": cid_prepaid, "name": f"包年客户_{cid_prepaid}"},
    )
    db_session.execute(
        text(
            """
            INSERT INTO customer_balances (customer_id, total_amount, real_amount, bonus_amount,
                                           used_total, used_real, used_bonus, created_at, updated_at)
            VALUES (:cid, 5000, 5000, 0, 0, 0, 0, NOW(), NOW())
            """
        ),
        {"cid": cid_prepaid},
    )
    db_session.commit()

    _req, resp = await test_client.get(
        "/api/v1/customers",
        params={"keyword": "包年客户_", "sort_by": "balance", "sort_order": "desc"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status == 200
    ids = [r["id"] for r in resp.json["data"]["list"]]
    assert ids.index(cid_pkg) < ids.index(cid_prepaid)
