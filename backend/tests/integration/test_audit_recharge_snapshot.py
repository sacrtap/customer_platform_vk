"""充值审计：余额前后快照与中间件去重集成测试"""

import uuid

import pytest
from sqlalchemy import text


@pytest.fixture
async def audit_customer(db_session, worker_id):
    """创建独立测试客户（避免与 billing 测试的 fixture 冲突）"""
    wid = worker_id if worker_id != "master" else "local"
    customer_id = 900000 + abs(hash(f"{wid}-{uuid.uuid4().hex[:6]}")) % 90000

    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": customer_id})
    db_session.execute(
        text("""
        INSERT INTO customers (id, company_id, name, account_type,
                               settlement_cycle, settlement_type,
                               created_at, updated_at)
        VALUES (:id, :id, :name, 'enterprise', 'monthly', 'prepaid', NOW(), NOW())
        """),
        {"id": customer_id, "name": f"审计测试客户_{customer_id}"},
    )
    db_session.commit()

    yield {"id": customer_id}

    for table in (
        "recharge_records",
        "customer_balances",
        "audit_logs",
        "customers",
    ):
        column = "id" if table in ("customers",) else "customer_id"
        if table == "audit_logs":
            continue
        db_session.execute(text(f"DELETE FROM {table} WHERE {column} = :id"), {"id": customer_id})
    db_session.execute(
        text(
            "DELETE FROM audit_logs WHERE record_type = 'recharge' AND changes ->> 'customer_id' = :cid"
        ),
        {"cid": str(customer_id)},
    )
    db_session.commit()


@pytest.mark.asyncio
async def test_recharge_audit_records_balance_transition_once(
    test_client, auth_token, audit_customer
):
    """充值只产生一条业务审计，且 before/after 是真实前后余额"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    customer_id = audit_customer["id"]

    _, response = await test_client.post(
        "/api/v1/billing/recharge",
        json={
            "customer_id": customer_id,
            "real_amount": 1000.00,
            "bonus_amount": 200.00,
        },
        headers=headers,
    )
    assert response.status == 201, response.json
    recharge_id = response.json["data"]["id"]

    _, response = await test_client.get(
        "/api/v1/audit-logs",
        params={"action": "recharge", "module": "billing", "page": 1, "page_size": 50},
        headers=headers,
    )
    assert response.status == 200
    rows = [row for row in response.json["data"]["list"] if row["record_id"] == recharge_id]

    # 中间件不再额外写一条「create + 请求体」的重复审计
    assert len(rows) == 1
    row = rows[0]
    assert row["operation_type"] == "standard"

    changes = row["changes"]
    assert changes["before"] == {"real_amount": 0.0, "bonus_amount": 0.0}
    assert changes["after"]["real_amount"] == 1000.0
    assert changes["after"]["bonus_amount"] == 200.0

    description = row["description"]
    assert description["action_label"] == "客户充值"
    assert any("实充 ¥1,000.00" in line for line in description["summary"])
    assert any("余额合计" in line for line in description["summary"])
