"""F3 subtotal/order_count 冻结落库 + F4 详情透传 — 集成测试

- 显式 items 生成结算单 → invoice_items.subtotal/order_count 落库为传入值；
- 详情接口原样透传冻结值（不重算）；
- 历史行（subtotal/order_count NULL）→ 详情回退 quantity × unit_price / quantity。

外部引擎未配置（conftest 默认 None）→ F1 一致性校验放行，不阻塞生成。
"""

import uuid

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

PERIOD_START = "2026-09-01"
PERIOD_END = "2026-09-30"

_ITEMS = [
    {
        "device_type": "X",
        "layer_type": "single",
        "quantity": 100,
        "unit_price": 10.00,
        "subtotal": 1000.00,  # 显式传入（递增多层等场景 ≠ quantity × unit_price）
        "order_count": 95,
    },
    {
        "device_type": "X",
        "layer_type": "multi",
        "quantity": 6,
        "unit_price": 9.00,
        # 不传 subtotal/order_count → 落库 NULL（手工 items 常见形态）
    },
]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
async def subtotal_customer(db_session):
    """自包含测试客户（月度预付费，无历史结算单）"""
    customer_id = 92000 + abs(hash(uuid.uuid4().hex[:8])) % 800
    company_id = customer_id
    customer_name = f"小计冻结测试_{customer_id}"
    db_session.execute(
        text("""
        INSERT INTO customers (id, company_id, name, account_type,
                               settlement_cycle, settlement_type, is_disabled,
                               created_at, updated_at)
        VALUES (:id, :company_id, :name, 'enterprise', 'monthly', 'prepaid', false,
                NOW(), NOW())
        """),
        {"id": customer_id, "company_id": company_id, "name": customer_name},
    )
    db_session.commit()
    yield {"id": customer_id, "name": customer_name}
    db_session.execute(
        text(
            "DELETE FROM invoice_items WHERE invoice_id IN "
            "(SELECT id FROM invoices WHERE customer_id = :cid)"
        ),
        {"cid": customer_id},
    )
    db_session.execute(text("DELETE FROM invoices WHERE customer_id = :cid"), {"cid": customer_id})
    db_session.execute(
        text("DELETE FROM daily_orders WHERE customer_id = :cid"), {"cid": customer_id}
    )
    db_session.execute(
        text("DELETE FROM daily_consumptions WHERE customer_id = :cid"), {"cid": customer_id}
    )
    db_session.execute(text("DELETE FROM customers WHERE id = :cid"), {"cid": customer_id})
    db_session.commit()


async def test_generate_persists_frozen_subtotal_and_order_count(
    test_client, auth_headers, subtotal_customer, db_session
):
    """显式 items 生成 → subtotal/order_count 落库（传了存传入值，没传递 NULL）"""
    _req, response = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": subtotal_customer["id"],
            "period_start": PERIOD_START,
            "period_end": PERIOD_END,
            "items": _ITEMS,
        },
        headers=auth_headers,
    )
    assert response.status == 201, response.text
    body = response.json
    assert body["code"] == 0, body
    invoice_id = body["data"]["id"]

    rows = (
        db_session.execute(
            text("""
            SELECT device_type, layer_type, quantity, unit_price, subtotal, order_count
            FROM invoice_items WHERE invoice_id = :iid ORDER BY id
            """),
            {"iid": invoice_id},
        )
        .mappings()
        .all()
    )
    assert len(rows) == 2
    # 传入值原样冻结
    assert float(rows[0]["subtotal"]) == 1000.00
    assert rows[0]["order_count"] == 95
    # 未传 → NULL（详情层回退）
    assert rows[1]["subtotal"] is None
    assert rows[1]["order_count"] is None


async def test_detail_returns_frozen_values_with_fallback(
    test_client, auth_headers, subtotal_customer, db_session
):
    """详情透传冻结值；NULL 行回退 quantity × unit_price / quantity"""
    _req, gen = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": subtotal_customer["id"],
            "period_start": PERIOD_START,
            "period_end": PERIOD_END,
            "items": _ITEMS,
        },
        headers=auth_headers,
    )
    invoice_id = gen.json["data"]["id"]

    _req, response = await test_client.get(
        f"/api/v1/billing/invoices/{invoice_id}",
        headers=auth_headers,
    )
    assert response.status == 200
    items = response.json["data"]["items"]
    assert len(items) == 2
    # 冻结值透传
    assert items[0]["subtotal"] == 1000.0
    assert items[0]["order_count"] == 95.0
    # NULL 行回退：subtotal = quantity × unit_price = 54，order_count = quantity = 6
    assert items[1]["subtotal"] == 54.0
    assert items[1]["order_count"] == 6.0


async def test_detail_frozen_values_survive_concurrent_sync(
    test_client, auth_headers, subtotal_customer, db_session
):
    """F4 回归：两次打开中间插入同步（daily_orders/consumptions 变动）数字不变"""
    cid = subtotal_customer["id"]
    _req, gen = await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": cid,
            "period_start": PERIOD_START,
            "period_end": PERIOD_END,
            "items": _ITEMS,
        },
        headers=auth_headers,
    )
    invoice_id = gen.json["data"]["id"]

    _req, first = await test_client.get(
        f"/api/v1/billing/invoices/{invoice_id}", headers=auth_headers
    )
    first_items = first.json["data"]["items"]

    # 中间插入「同步」：新增当日消耗与订单（旧实现会经实时重算改变详情数字）
    db_session.execute(
        text("""
        INSERT INTO daily_orders (order_code, customer_id, create_date, sync_date,
                                  created_at, updated_at)
        VALUES (:code, :cid, CAST('2026-09-15' AS date),
                CAST('2026-09-15 06:00:00+00' AS timestamptz), NOW(), NOW())
        """),
        {"code": f"ORD-F3-{cid}", "cid": cid},
    )
    db_session.execute(
        text("""
        INSERT INTO daily_consumptions
            (customer_id, consumption_date, device_type, layer_type,
             order_count, total_floor_count, total_cost, has_pricing_rule,
             created_at, updated_at)
        VALUES (:cid, '2026-09-15 06:00:00+00', 'X', 'single', 5, 5, 50.00, true,
                NOW(), NOW())
        """),
        {"cid": cid},
    )
    db_session.commit()

    _req, second = await test_client.get(
        f"/api/v1/billing/invoices/{invoice_id}", headers=auth_headers
    )
    assert second.json["data"]["items"] == first_items
