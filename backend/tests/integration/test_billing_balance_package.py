"""包年套餐余额显示 — 集成测试（真实 SQL 路径）

覆盖 `backend/app/routes/billing/balances.py` 中包年逻辑的端到端行为：
- 无 CustomerBalance 行的包年客户仍出现在余额列表，并返回剩余额度/次数/到期天数
- 限量/不限量/过期三种包年形态的余额与燃尽口径
- 余额范围筛选按套餐剩余额度参与（package_remaining CTE）
- KPI 统计（预付费总余额 / 余额不足 / 即将耗尽）包含包年剩余额度
- 导出 Excel 含包年三列
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

CST = timezone(timedelta(hours=8))


def _unique_customer_id(base: int = 80000) -> int:
    return base + abs(hash(uuid.uuid4().hex[:8])) % 15000


def _uid() -> int:
    """生成唯一自增 ID（pricing_rules / daily_consumptions 等表 id 无默认序列）"""
    return abs(hash(uuid.uuid4().hex[:12])) % 2_000_000_000


def _insert_customer(db, cid: int, *, price_policy: str, settlement_type=None):
    db.execute(
        text(
            """
            INSERT INTO customers (id, company_id, name, account_type, price_policy,
                                   settlement_cycle, settlement_type,
                                   created_at, updated_at)
            VALUES (:id, :cid, :name, 'enterprise', :policy,
                    'yearly', :stype, NOW(), NOW())
            """
        ),
        {
            "id": cid,
            "cid": cid,
            "name": f"包年测试客户_{cid}",
            "policy": price_policy,
            "stype": settlement_type,
        },
    )


def _insert_package_rule(
    db,
    cid: int,
    *,
    base_fee: float,
    effective_days_ago: int,
    expiry_days_ahead: int | None,
    is_unlimited: bool = False,
    limit_count: int | None = None,
) -> int:
    """插入一条包年规则，返回 rule id。expiry_days_ahead 为 None 表示无到期日"""
    limits = {"base_fee": base_fee, "is_unlimited": is_unlimited}
    if limit_count is not None:
        limits["limit_count"] = limit_count
    import json as _json

    expiry = (
        datetime.now(timezone.utc) + timedelta(days=expiry_days_ahead)
        if expiry_days_ahead is not None
        else None
    )
    # tiers 为 NOT NULL（包年规则不使用阶梯，落库为空数组）；id 使用表默认序列
    rule_id = db.execute(
        text(
            """
            INSERT INTO pricing_rules (customer_id, device_type, layer_type, pricing_type,
                                       package_type, package_limits, tiers,
                                       effective_date, expiry_date, created_at, updated_at)
            VALUES (:cid, NULL, NULL, 'package',
                    'A', CAST(:limits AS JSON), CAST('[]' AS JSON),
                    :effective, :expiry, NOW(), NOW())
            RETURNING id
            """
        ),
        {
            "cid": cid,
            "limits": _json.dumps(limits),
            "effective": datetime.now(timezone.utc) - timedelta(days=effective_days_ago),
            "expiry": expiry,
        },
    ).scalar()
    return int(rule_id)


def _insert_consumption(db, cid: int, rule_id: int, *, total_cost: float, order_count: int):
    db.execute(
        text(
            """
            INSERT INTO daily_consumptions (id, customer_id, consumption_date, device_type,
                                            layer_type, order_count, total_floor_count, total_cost,
                                            pricing_rule_id, has_pricing_rule,
                                            created_at, updated_at)
            VALUES (:id, :cid, NOW() - INTERVAL '5 days', 'X', 'single', :oc, :oc, :cost,
                    :rid, TRUE, NOW(), NOW())
            """
        ),
        {"id": _uid(), "cid": cid, "oc": order_count, "cost": total_cost, "rid": rule_id},
    )


@pytest.mark.asyncio
async def test_balance_list_includes_package_customer_without_balance_row(
    test_client, auth_token, db_session
):
    """无 CustomerBalance 行的包年客户出现在列表，且返回剩余额度/次数/燃尽到期天数"""
    cid = _unique_customer_id(80000)
    _insert_customer(db_session, cid, price_policy="yearly")
    rule_id = _insert_package_rule(
        db_session,
        cid,
        base_fee=120000.0,
        effective_days_ago=200,
        expiry_days_ahead=45,
        limit_count=1200,
    )
    _insert_consumption(db_session, cid, rule_id, total_cost=30000.0, order_count=200)
    db_session.commit()

    _req, response = await test_client.get(
        "/api/v1/billing/balances",
        params={"customer_id": cid},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200
    rows = response.json["data"]["list"]
    assert len(rows) == 1
    row = rows[0]
    assert row["is_package"] is True
    assert row["package_expired"] is False
    # 剩余额度 = 120000 - 30000；剩余次数 = 1200 - 200
    assert row["total_amount"] == 90000.0
    assert row["package_remaining_amount"] == 90000.0
    assert row["package_remaining_count"] == 1000.0
    # 「已消耗」= 套餐内累计消耗（实时口径），与余额列同口径：90000 + 30000 = 120000
    assert row["package_consumed_amount"] == 30000.0
    assert row["package_is_unlimited"] is False


@pytest.mark.asyncio
async def test_balance_list_unlimited_package_has_no_count(test_client, auth_token, db_session):
    """不限量包年客户：剩余次数为 null"""
    cid = _unique_customer_id(81000)
    _insert_customer(db_session, cid, price_policy="yearly")
    rule_id = _insert_package_rule(
        db_session,
        cid,
        base_fee=80000.0,
        effective_days_ago=100,
        expiry_days_ahead=200,
        is_unlimited=True,
    )
    _insert_consumption(db_session, cid, rule_id, total_cost=10000.0, order_count=30)
    db_session.commit()

    _req, response = await test_client.get(
        "/api/v1/billing/balances",
        params={"customer_id": cid},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    row = response.json["data"]["list"][0]
    assert row["is_package"] is True
    assert row["package_is_unlimited"] is True
    assert row["package_remaining_count"] is None
    assert row["total_amount"] == 70000.0
    assert row["package_consumed_amount"] == 10000.0


@pytest.mark.asyncio
async def test_balance_list_expired_package_shows_zero(test_client, auth_token, db_session):
    """过期包年客户：total_amount 归 0、package_expired=True、燃尽 0 天"""
    cid = _unique_customer_id(82000)
    _insert_customer(db_session, cid, price_policy="yearly")
    _insert_package_rule(
        db_session,
        cid,
        base_fee=50000.0,
        effective_days_ago=400,
        expiry_days_ahead=-30,
    )
    db_session.commit()

    _req, response = await test_client.get(
        "/api/v1/billing/balances",
        params={"customer_id": cid},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    row = response.json["data"]["list"][0]
    assert row["is_package"] is True
    assert row["package_expired"] is True
    assert row["total_amount"] == 0
    assert row["days_remaining"] == 0
    # 过期包年无实时消耗语义 → null（前端回退 CustomerBalance.used_total）
    assert row["package_consumed_amount"] is None


@pytest.mark.asyncio
async def test_balance_filter_package_remaining_amount(test_client, auth_token, db_session):
    """余额范围筛选按套餐剩余额度参与：剩余额度 5000 命中「1 万以下」，剩余 50000 不命中"""
    cid_low = _unique_customer_id(83000)
    cid_high = _unique_customer_id(84000)
    for cid, base_fee, consumed in [(cid_low, 20000.0, 15000.0), (cid_high, 60000.0, 10000.0)]:
        _insert_customer(db_session, cid, price_policy="yearly")
        rid = _insert_package_rule(
            db_session,
            cid,
            base_fee=base_fee,
            effective_days_ago=100,
            expiry_days_ahead=200,
            limit_count=1000,
        )
        _insert_consumption(db_session, cid, rid, total_cost=consumed, order_count=10)
    db_session.commit()

    _req, response = await test_client.get(
        "/api/v1/billing/balances",
        params={"balance_max": 10000},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200
    ids = [r["customer_id"] for r in response.json["data"]["list"]]
    assert cid_low in ids  # 剩余 5000
    assert cid_high not in ids  # 剩余 50000


@pytest.mark.asyncio
async def test_balance_stats_includes_package_remaining(test_client, auth_token, db_session):
    """KPI：预付费总余额含包年剩余额度；余额不足客户数含剩余额度 < 1 万的包年客户"""
    cid = _unique_customer_id(85000)
    _insert_customer(db_session, cid, price_policy="yearly")
    rid = _insert_package_rule(
        db_session,
        cid,
        base_fee=20000.0,
        effective_days_ago=100,
        expiry_days_ahead=200,
        limit_count=1000,
    )
    _insert_consumption(db_session, cid, rid, total_cost=15000.0, order_count=10)
    db_session.commit()

    _req, response = await test_client.get(
        "/api/v1/billing/balance-stats",
        params={"keyword": f"包年测试客户_{cid}"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200
    data = response.json["data"]
    # 剩余额度 = 20000 - 15000 = 5000 计入预付费总余额
    assert data["total_balance_prepaid"] == 5000.0
    assert data["prepaid_customers"] == 1
    # 剩余 5000 < 10000 → 余额不足
    assert data["low_balance_count"] == 1


@pytest.mark.asyncio
async def test_export_balances_package_columns(test_client, auth_token, db_session):
    """导出 Excel：包年客户行含套餐三列（读取表头验证）"""
    import io

    import pandas as pd

    cid = _unique_customer_id(86000)
    _insert_customer(db_session, cid, price_policy="yearly")
    rid = _insert_package_rule(
        db_session,
        cid,
        base_fee=100000.0,
        effective_days_ago=100,
        expiry_days_ahead=120,
        limit_count=1000,
    )
    _insert_consumption(db_session, cid, rid, total_cost=20000.0, order_count=100)
    db_session.commit()

    _req, response = await test_client.get(
        "/api/v1/billing/balances/export",
        params={"customer_id": cid},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200
    assert response.body[:2] == b"PK"

    df = pd.read_excel(io.BytesIO(response.body))
    for col in ("套餐剩余额度（元）", "套餐剩余次数", "套餐到期日期"):
        assert col in df.columns
    assert df.iloc[0]["套餐剩余额度（元）"] == 80000.0
    assert df.iloc[0]["套餐剩余次数"] == 900
    # 导出「已消耗」列对包年客户取套餐内累计消耗（与列表口径一致）
    assert df.iloc[0]["已消耗（元）"] == 20000.0


@pytest.mark.asyncio
async def test_balance_sort_used_total_uses_package_consumed(test_client, auth_token, db_session):
    """按「已消耗」排序：包年客户以套餐内累计消耗参与（而非 CustomerBalance.used_total）"""
    cid_pkg = _unique_customer_id(87000)
    cid_prepaid = _unique_customer_id(87500)

    # 包年客户：套餐内累计消耗 80000，无 CustomerBalance 行（used_total 缺省 0）
    _insert_customer(db_session, cid_pkg, price_policy="yearly")
    rid = _insert_package_rule(
        db_session,
        cid_pkg,
        base_fee=200000.0,
        effective_days_ago=100,
        expiry_days_ahead=200,
        limit_count=1000,
    )
    _insert_consumption(db_session, cid_pkg, rid, total_cost=80000.0, order_count=100)

    # 预付费客户：CustomerBalance.used_total = 5000
    _insert_customer(db_session, cid_prepaid, price_policy="pricing", settlement_type="prepaid")
    db_session.execute(
        text(
            """
            INSERT INTO customer_balances (customer_id, total_amount, real_amount, bonus_amount,
                                           used_total, used_real, used_bonus,
                                           created_at, updated_at)
            VALUES (:cid, 10000, 10000, 0, 5000, 5000, 0, NOW(), NOW())
            """
        ),
        {"cid": cid_prepaid},
    )
    db_session.commit()

    _req, response = await test_client.get(
        "/api/v1/billing/balances",
        params={
            "keyword": "包年测试客户_",
            "sort_by": "used_total",
            "sort_order": "desc",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status == 200
    ids = [r["customer_id"] for r in response.json["data"]["list"]]
    # 包年客户已消耗 80000 > 预付费 5000 → 包年客户排在前面
    assert ids.index(cid_pkg) < ids.index(cid_prepaid)
