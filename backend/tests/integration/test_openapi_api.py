"""开放平台接口集成测试

覆盖:
1. GET /api/v1/balances（全量客户余额）— 认证失败 / 成功 / 过滤语义
2. GET /api/v1/erp/balances（渠道版）— 回归：erp_channel 必填、仅返回该渠道客户
"""

import hashlib
from datetime import datetime

import pytest
from sqlalchemy import text


def _insert_customer(
    db_session,
    *,
    company_id,
    name,
    erp_system=None,
    is_disabled=False,
    deleted_at=None,
    balance=None,
):
    """插入客户（可选余额记录），返回客户 id"""
    customer_id = db_session.execute(
        text("""
            INSERT INTO customers
                (company_id, name, erp_system, is_disabled, deleted_at, created_at, updated_at)
            VALUES (:company_id, :name, :erp_system, :is_disabled, :deleted_at, NOW(), NOW())
            RETURNING id
        """),
        {
            "company_id": company_id,
            "name": name,
            "erp_system": erp_system,
            "is_disabled": is_disabled,
            "deleted_at": deleted_at,
        },
    ).scalar()

    if balance is not None:
        total, used = balance
        db_session.execute(
            text("""
                INSERT INTO customer_balances
                    (customer_id, total_amount, real_amount, bonus_amount,
                     used_total, used_real, used_bonus, created_at, updated_at)
                VALUES (:cid, :total, :total, 0, :used, :used, 0, NOW(), NOW())
            """),
            {"cid": customer_id, "total": total, "used": used},
        )
    db_session.commit()
    return customer_id


@pytest.fixture
def valid_api_key(db_session) -> str:
    """创建有效 API-Key（api_keys 不在 db_session TRUNCATE 列表，需自行清理）"""
    raw_key = "vk_" + "a" * 32  # vk_ + 32 字符随机串
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    db_session.execute(
        text("""
            INSERT INTO api_keys (name, key_prefix, key_hash, status, created_at, updated_at)
            VALUES (:name, :prefix, :hash, 'active', NOW(), NOW())
        """),
        {"name": "集成测试Key", "prefix": raw_key[:8], "hash": key_hash},
    )
    db_session.commit()
    yield raw_key
    db_session.execute(text("DELETE FROM api_keys WHERE key_hash = :hash"), {"hash": key_hash})
    db_session.commit()


@pytest.mark.asyncio
async def test_all_balances_requires_api_key(test_client):
    """无 API-Key → 401 + 40104"""
    _request, response = await test_client.get("/api/v1/balances")
    assert response.status == 401
    assert response.json["code"] == 40104


@pytest.mark.asyncio
async def test_all_balances_invalid_api_key(test_client):
    """无效 API-Key → 401 + 40104"""
    _request, response = await test_client.get(
        "/api/v1/balances",
        headers={"Authorization": "Bearer vk_invalid_key_for_test"},
    )
    assert response.status == 401
    assert response.json["code"] == 40104


@pytest.mark.asyncio
async def test_all_balances_success(test_client, valid_api_key, db_session):
    """有效 Key → 返回全部有效客户（多渠道 + 无 ERP + 无余额记录），按 company_id 升序"""
    _insert_customer(
        db_session,
        company_id=200,
        name="巧房客户A",
        erp_system="qiaofang",
        balance=(100000.0, 0.0),
    )
    _insert_customer(db_session, company_id=210, name="巧房客户B", erp_system="qiaofang")
    _insert_customer(db_session, company_id=300, name="无ERP客户", balance=(5000.0, 1500.0))
    # 不应返回的客户
    _insert_customer(
        db_session,
        company_id=400,
        name="停用客户",
        erp_system="qiaofang",
        is_disabled=True,
        balance=(999.0, 0.0),
    )
    _insert_customer(db_session, company_id=500, name="删除客户", deleted_at=datetime(2026, 1, 1))

    _request, response = await test_client.get(
        "/api/v1/balances",
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    items = data["data"]
    assert [i["customer_id"] for i in items] == ["200", "210", "300"]
    by_id = {i["customer_id"]: i for i in items}
    assert by_id["200"] == {
        "customer_id": "200",
        "customer_name": "巧房客户A",
        "balance": 100000.0,
    }
    assert by_id["210"] == {
        "customer_id": "210",
        "customer_name": "巧房客户B",
        "balance": 0.0,
    }
    assert by_id["300"] == {
        "customer_id": "300",
        "customer_name": "无ERP客户",
        # total_amount 即当前可用余额（used_total 是累计消耗统计量，不再二次扣减）
        "balance": 5000.0,
    }


@pytest.mark.asyncio
async def test_all_balances_no_double_deduction(test_client, valid_api_key, db_session):
    """回归：余额 = total_amount，不减 used_total（2026-10-26 双重扣减修复）

    实测背景：客户 1322 充值 66.80、扣款 150.30 → total_amount=-83.50（正确余额），
    旧口径 `total - used` 返回 -233.80（把同一笔消耗扣两遍）。used_total 只是统计量，
    扣款时已同步体现在 real_amount/total_amount 上。
    """
    # total=-83.50, used=150.30：口径正确时应返回 -83.50，旧口径会返回 -233.80
    _insert_customer(db_session, company_id=1322, name="负余额客户", balance=(-83.50, 150.30))
    # 正常正值客户：total=3010, used=0 → 两口径相同（旧 bug 被 0 消耗掩盖）
    _insert_customer(db_session, company_id=1528, name="正常客户", balance=(3010.00, 0.0))

    _request, response = await test_client.get(
        "/api/v1/balances",
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status == 200
    by_id = {i["customer_id"]: i for i in response.json["data"]}
    assert by_id["1322"]["balance"] == -83.50
    assert by_id["1528"]["balance"] == 3010.0


@pytest.mark.asyncio
async def test_erp_balances_regression(test_client, valid_api_key, db_session):
    """渠道版接口回归：erp_channel 仍必填，且仅返回该渠道客户"""
    _insert_customer(
        db_session,
        company_id=100,
        name="巧房客户",
        erp_system="qiaofang",
        balance=(10.0, 0.0),
    )
    _insert_customer(
        db_session,
        company_id=101,
        name="鼎尖客户",
        erp_system="dingjian",
        balance=(20.0, 0.0),
    )

    # 缺少 erp_channel → 400 + 40004
    _request, response = await test_client.get(
        "/api/v1/erp/balances",
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status == 400
    assert response.json["code"] == 40004

    # 指定渠道 → 仅返回该渠道客户
    _request, response = await test_client.get(
        "/api/v1/erp/balances",
        params={"erp_channel": "qiaofang"},
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status == 200
    assert response.json["code"] == 0
    assert [i["customer_id"] for i in response.json["data"]] == ["100"]


@pytest.mark.asyncio
async def test_all_balances_whitelist_overrides(test_client, valid_api_key, db_session):
    """余额白名单客户优先返回静态余额，非白名单返回 total_amount"""
    whitelist_cid = _insert_customer(
        db_session,
        company_id=1000,
        name="白名单客户",
        erp_system="qiaofang",
        balance=(100000.0, 60000.0),  # 白名单应返回静态值（与 total/used 无关）
    )
    _insert_customer(
        db_session,
        company_id=1001,
        name="普通客户",
        erp_system="qiaofang",
        balance=(5000.0, 1500.0),  # 非白名单：返回 total_amount 5000
    )
    # 白名单静态余额 2000
    db_session.execute(
        text("""
            INSERT INTO balance_whitelists (customer_id, static_balance, created_at, updated_at)
            VALUES (:cid, 2000, NOW(), NOW())
        """),
        {"cid": whitelist_cid},
    )
    db_session.commit()

    _request, response = await test_client.get(
        "/api/v1/balances",
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status == 200
    items = response.json["data"]
    by_id = {i["customer_id"]: i for i in items}
    assert by_id["1000"]["balance"] == 2000.0
    assert by_id["1001"]["balance"] == 5000.0  # total_amount（不减 used_total）


@pytest.mark.asyncio
async def test_all_balances_whitelist_soft_deleted_ignored(test_client, valid_api_key, db_session):
    """软删除（已移出）的白名单记录不生效，返回 total_amount"""
    cid = _insert_customer(
        db_session,
        company_id=1100,
        name="移出客户",
        balance=(10000.0, 4000.0),  # total_amount 10000
    )
    db_session.execute(
        text("""
            INSERT INTO balance_whitelists
                (customer_id, static_balance, deleted_at, created_at, updated_at)
            VALUES (:cid, 9999, NOW(), NOW(), NOW())
        """),
        {"cid": cid},
    )
    db_session.commit()

    _request, response = await test_client.get(
        "/api/v1/balances",
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status == 200
    items = response.json["data"]
    assert items[0]["customer_id"] == "1100"
    assert items[0]["balance"] == 10000.0


@pytest.mark.asyncio
async def test_erp_balances_unaffected_by_whitelist(test_client, valid_api_key, db_session):
    """ERP 渠道接口不受白名单影响（仅全量接口生效，回归）"""
    cid = _insert_customer(
        db_session,
        company_id=1200,
        name="渠道客户",
        erp_system="qiaofang",
        balance=(8000.0, 2000.0),  # total_amount 8000
    )
    db_session.execute(
        text("""
            INSERT INTO balance_whitelists (customer_id, static_balance, created_at, updated_at)
            VALUES (:cid, 777, NOW(), NOW())
        """),
        {"cid": cid},
    )
    db_session.commit()

    _request, response = await test_client.get(
        "/api/v1/erp/balances",
        params={"erp_channel": "qiaofang"},
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status == 200
    assert response.json["data"][0]["balance"] == 8000.0


# ==================== 包年客户余额口径 ====================


def _insert_package_customer(
    db_session,
    *,
    company_id,
    name,
    erp_system=None,
    base_fee,
    consumed=0.0,
    limit_count=100,
    expired=False,
):
    """插入包年客户 + 一条包年规则（可选套餐内消耗），返回 (customer_id, rule_id)

    包年客户年费不写入 `customer_balances`（合同式预收），故刻意不建余额行，
    验证开放平台接口不会因缺余额记录而返回 0。
    """
    import json
    from datetime import datetime, timedelta, timezone

    customer_id = db_session.execute(
        text("""
            INSERT INTO customers
                (company_id, name, erp_system, price_policy, settlement_cycle,
                 created_at, updated_at)
            VALUES (:company_id, :name, :erp_system, 'yearly', 'yearly', NOW(), NOW())
            RETURNING id
        """),
        {"company_id": company_id, "name": name, "erp_system": erp_system},
    ).scalar()

    now = datetime.now(timezone.utc)
    expiry = now - timedelta(days=30) if expired else now + timedelta(days=200)
    rule_id = db_session.execute(
        text("""
            INSERT INTO pricing_rules
                (customer_id, device_type, layer_type, pricing_type, package_type,
                 package_limits, tiers, effective_date, expiry_date, created_at, updated_at)
            VALUES (:cid, NULL, NULL, 'package', 'A', CAST(:limits AS JSON),
                    CAST('[]' AS JSON), :effective, :expiry, NOW(), NOW())
            RETURNING id
        """),
        {
            "cid": customer_id,
            "limits": json.dumps(
                {"base_fee": base_fee, "is_unlimited": False, "limit_count": limit_count}
            ),
            "effective": now - timedelta(days=300),
            "expiry": expiry,
        },
    ).scalar()

    if consumed:
        db_session.execute(
            text("""
                INSERT INTO daily_consumptions
                    (id, customer_id, consumption_date, device_type, layer_type,
                     order_count, total_floor_count, total_cost, pricing_rule_id,
                     has_pricing_rule, created_at, updated_at)
                VALUES (:id, :cid, NOW() - INTERVAL '5 days', 'X', 'single',
                        5, 5, :cost, :rid, TRUE, NOW(), NOW())
            """),
            {
                "id": abs(hash(f"{company_id}-{rule_id}")) % 2_000_000_000,
                "cid": customer_id,
                "cost": consumed,
                "rid": rule_id,
            },
        )
    db_session.commit()
    return customer_id, rule_id


@pytest.mark.asyncio
async def test_all_balances_package_customer_uses_remaining_amount(
    test_client, valid_api_key, db_session
):
    """包年客户（无余额行）→ balance = 套餐剩余额度（而非 0）"""
    _insert_package_customer(
        db_session,
        company_id=1300,
        name="包年客户A",
        base_fee=2980.0,
        consumed=99.32,
        limit_count=120,
    )

    _request, response = await test_client.get(
        "/api/v1/balances",
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status == 200
    items = {i["customer_id"]: i for i in response.json["data"]}
    # 2980 - 99.32 = 2880.68（而非 CustomerBalance 缺失导致的 0.0）
    assert items["1300"]["balance"] == 2880.68


@pytest.mark.asyncio
async def test_all_balances_non_package_unchanged(test_client, valid_api_key, db_session):
    """非包年客户口径：balance = CustomerBalance.total_amount（不减 used_total）"""
    _insert_customer(
        db_session,
        company_id=1310,
        name="预付费客户",
        balance=(5000.0, 1500.0),
    )
    _insert_package_customer(db_session, company_id=1311, name="包年客户B", base_fee=1000.0)

    _request, response = await test_client.get(
        "/api/v1/balances",
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    items = {i["customer_id"]: i for i in response.json["data"]}
    assert items["1310"]["balance"] == 5000.0  # 非包年：total_amount（used_total 不二次扣减）
    assert items["1311"]["balance"] == 1000.0  # 包年：base_fee - 0


@pytest.mark.asyncio
async def test_all_balances_package_whitelist_still_wins(test_client, valid_api_key, db_session):
    """包年客户命中白名单 → 静态余额优先于套餐剩余额度"""
    cid, _rule = _insert_package_customer(
        db_session, company_id=1320, name="包年白名单客户", base_fee=2980.0, consumed=99.32
    )
    db_session.execute(
        text("""
            INSERT INTO balance_whitelists (customer_id, static_balance, created_at, updated_at)
            VALUES (:cid, 1234.56, NOW(), NOW())
        """),
        {"cid": cid},
    )
    db_session.commit()

    _request, response = await test_client.get(
        "/api/v1/balances",
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    items = {i["customer_id"]: i for i in response.json["data"]}
    assert items["1320"]["balance"] == 1234.56


@pytest.mark.asyncio
async def test_erp_balances_package_customer_uses_remaining_amount(
    test_client, valid_api_key, db_session
):
    """ERP 渠道接口同样接入包年口径（与全量接口一致）"""
    _insert_package_customer(
        db_session,
        company_id=1330,
        name="渠道包年客户",
        erp_system="qiaofang",
        base_fee=2000.0,
        consumed=500.0,
    )

    _request, response = await test_client.get(
        "/api/v1/erp/balances",
        params={"erp_channel": "qiaofang"},
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status == 200
    items = {i["customer_id"]: i for i in response.json["data"]}
    assert items["1330"]["balance"] == 1500.0  # 2000 - 500
