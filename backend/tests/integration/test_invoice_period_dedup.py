"""F5 结算单周期去重 — 集成测试

- 同周期二次生成被拒（40001，文案含已有单号）；
- 批量生成中已存在同期单的客户进 skipped（reason 含单号），不阻断其它客户；
- 相邻不相交周期（11 月 / 12 月）不误伤。
"""

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

_ITEMS = [
    {
        "device_type": "X",
        "layer_type": "single",
        "quantity": 100,
        "unit_price": 10.00,
    }
]


def _no_external_engine(app):
    """无外部引擎 → F1 放行，隔离测 F5"""
    app.ctx.external_mysql_engine = None


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
async def dedup_customer(db_session):
    """周期去重测试客户：自带 fixed 规则 + 日消耗（保证批量路径 items 非空）"""
    import uuid

    cid = 93000 + abs(hash(uuid.uuid4().hex[:8])) % 500
    db_session.execute(
        text("""
        INSERT INTO customers (id, company_id, name, account_type,
                               settlement_cycle, settlement_type, is_disabled,
                               created_at, updated_at)
        VALUES (:id, :cid, :name, 'enterprise', 'monthly', 'prepaid', false, NOW(), NOW())
        """),
        {"id": cid, "cid": cid, "name": f"去重测试_{cid}"},
    )
    db_session.execute(
        text("""
        INSERT INTO pricing_rules
            (customer_id, device_type, layer_type, pricing_type, unit_price,
             tiers, package_limits, effective_date, created_at, updated_at)
        VALUES (:cid, 'X', 'single', 'fixed', 10.00,
                CAST('[]' AS json), CAST('[]' AS json),
                '2026-01-01 00:00:00+00', NOW(), NOW())
        """),
        {"cid": cid},
    )
    db_session.execute(
        text("""
        INSERT INTO daily_consumptions
            (customer_id, consumption_date, device_type, layer_type,
             order_count, total_floor_count, total_cost, has_pricing_rule,
             created_at, updated_at)
        VALUES (:cid, '2026-11-15 06:00:00+00', 'X', 'single',
                5, 5, 50.00, true, NOW(), NOW())
        """),
        {"cid": cid},
    )
    db_session.commit()
    yield {"id": cid, "name": f"去重测试_{cid}"}
    db_session.execute(
        text(
            "DELETE FROM invoice_items WHERE invoice_id IN "
            "(SELECT id FROM invoices WHERE customer_id = :cid)"
        ),
        {"cid": cid},
    )
    db_session.execute(text("DELETE FROM invoices WHERE customer_id = :cid"), {"cid": cid})
    db_session.execute(
        text("DELETE FROM daily_consumptions WHERE customer_id = :cid"), {"cid": cid}
    )
    db_session.execute(text("DELETE FROM pricing_rules WHERE customer_id = :cid"), {"cid": cid})
    db_session.execute(text("DELETE FROM customers WHERE id = :cid"), {"cid": cid})
    db_session.commit()


class TestPeriodDedup:
    async def test_duplicate_period_rejected_with_invoice_no(
        self, test_client, auth_headers, dedup_customer, app
    ):
        """同周期二次生成被拒，文案含已有单号"""
        _no_external_engine(app)
        payload = {
            "customer_id": dedup_customer["id"],
            "period_start": "2026-11-01",
            "period_end": "2026-11-30",
            "items": _ITEMS,
        }
        request, response = await test_client.post(
            "/api/v1/billing/invoices/generate", json=payload, headers=auth_headers
        )
        assert response.status == 201
        first_no = response.json["data"]["invoice_no"]

        # 同周期再生成 → 40001 + 已有单号
        request, response = await test_client.post(
            "/api/v1/billing/invoices/generate", json=payload, headers=auth_headers
        )
        assert response.status == 400
        data = response.json
        assert data["code"] == 40001
        assert first_no in data["message"]

    async def test_adjacent_period_not_rejected(
        self, test_client, auth_headers, dedup_customer, app
    ):
        """相邻不相交周期（11 月 / 12 月）不误伤"""
        _no_external_engine(app)
        request, response = await test_client.post(
            "/api/v1/billing/invoices/generate",
            json={
                "customer_id": dedup_customer["id"],
                "period_start": "2026-11-01",
                "period_end": "2026-11-30",
                "items": _ITEMS,
            },
            headers=auth_headers,
        )
        assert response.status == 201

        request, response = await test_client.post(
            "/api/v1/billing/invoices/generate",
            json={
                "customer_id": dedup_customer["id"],
                "period_start": "2026-12-01",
                "period_end": "2026-12-31",
                "items": _ITEMS,
            },
            headers=auth_headers,
        )
        assert response.status == 201
        assert response.json["code"] == 0

    async def test_batch_skips_existing_period(
        self, test_client, auth_headers, dedup_customer, app
    ):
        """批量生成：已存在同期单的客户进 skipped（reason 含单号）"""
        _no_external_engine(app)
        # 先造一张 11 月单
        request, response = await test_client.post(
            "/api/v1/billing/invoices/generate",
            json={
                "customer_id": dedup_customer["id"],
                "period_start": "2026-11-01",
                "period_end": "2026-11-30",
                "items": _ITEMS,
            },
            headers=auth_headers,
        )
        assert response.status == 201
        first_no = response.json["data"]["invoice_no"]

        # 批量再生成 11 月 → 该客户 skipped
        request, response = await test_client.post(
            "/api/v1/billing/invoices/generate-batch",
            json={"period_start": "2026-11-01", "period_end": "2026-11-30"},
            headers=auth_headers,
        )
        assert response.status == 200
        skipped = response.json["data"]["skipped"]
        target = [s for s in skipped if s["customer_id"] == dedup_customer["id"]]
        assert len(target) == 1
        assert first_no in target[0]["reason"]
