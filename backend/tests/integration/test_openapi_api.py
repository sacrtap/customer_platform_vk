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
        "balance": 3500.0,
    }


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
