"""F1 结算单生成前一致性校验 — 集成测试

场景（对应 dev 库实证：模型总数实时查外部 233 vs 计费明细冻结快照 228）：
- 只同步部分日期（10-01~10-30）→ 生成被拒 40001，文案含差异日期 2026-10-31；
- 补齐 10-31 同步后 → 生成成功；
- 外部 MySQL 不可达 → 放行不阻塞；
- 批量生成中不一致客户进 skipped（不阻断其它客户）。

外部引擎经 app.ctx.external_mysql_engine 注入 mock（conftest 未配置
external_mysql_url，默认 None = 放行路径由 test_external_engine_unreachable_passes
与单测覆盖）。
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

PERIOD_START = "2026-10-01"
PERIOD_END = "2026-10-31"
SYNCED_DAYS = [f"2026-10-{d:02d}" for d in range(1, 31)]  # 10-01 ~ 10-30
MISSING_DAY = "2026-10-31"
MISSING_COUNT = 17
PER_DAY = 5


def _mock_external_engine(counts: dict[str, int]):
    """构造返回 CST 日分桶行的外部 MySQL 引擎 mock"""
    engine = MagicMock()
    result = MagicMock()
    result.fetchall.return_value = list(counts.items())

    async def _execute(stmt, params):
        return result

    conn = MagicMock()
    conn.execute = AsyncMock(side_effect=_execute)

    @asynccontextmanager
    async def _connect():
        yield conn

    engine.connect = _connect
    engine.dispose = AsyncMock()
    return engine


def _mock_external_engine_unreachable():
    """外部库不可达：connect 即抛异常"""
    engine = MagicMock()

    @asynccontextmanager
    async def _connect():
        raise ConnectionError("外部 MySQL 不可达")
        yield  # pragma: no cover

    engine.connect = _connect
    engine.dispose = AsyncMock()
    return engine


def _insert_daily_orders(db_session, customer_id: int, days: list[str], per_day: int):
    """按天插入 daily_orders（UTC 06:00 = CST 14:00 同日）"""
    for day in days:
        for i in range(per_day):
            db_session.execute(
                text("""
                INSERT INTO daily_orders
                    (order_code, customer_id, create_date, sync_date, created_at, updated_at)
                VALUES (:code, :cid, CAST(:day AS date),
                        CAST(CAST(:day AS text) || ' 06:00:00+00' AS timestamptz),
                        NOW(), NOW())
                """),
                {
                    "code": f"ORD-GUARD-{customer_id}-{day}-{i}",
                    "cid": customer_id,
                    "day": day,
                },
            )


async def _prepare_guard_customer(db_session, customer: dict):
    """造最小计费数据集：fixed 规则 + 日消耗 + 10-01~10-30 每日 5 笔订单快照"""
    cid = customer["id"]
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
        VALUES (:cid, '2026-10-15 06:00:00+00', 'X', 'single',
                5, 5, 50.00, true, NOW(), NOW())
        """),
        {"cid": cid},
    )
    _insert_daily_orders(db_session, cid, SYNCED_DAYS, PER_DAY)
    db_session.commit()


@pytest.fixture
def auth_headers(auth_token):
    """认证头（conftest 提供 session 级 auth_token）"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
async def guard_customer(db_session):
    """一致性门禁测试客户：自包含创建，已同步 10-01~10-30（缺 10-31）"""
    import uuid

    customer_id = 91000 + abs(hash(uuid.uuid4().hex[:8])) % 800
    company_id = customer_id
    customer_name = f"门禁测试客户_{customer_id}"
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
    await _prepare_guard_customer(db_session, {"id": customer_id})
    yield {"id": customer_id, "name": customer_name}
    # 按外键依赖顺序清理
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
    db_session.execute(
        text("DELETE FROM pricing_rules WHERE customer_id = :cid"), {"cid": customer_id}
    )
    db_session.execute(text("DELETE FROM customers WHERE id = :cid"), {"cid": customer_id})
    db_session.commit()


def _external_counts_complete() -> dict[str, int]:
    """外部实时量：已同步日与本地一致，缺的 10-31 有 17 笔"""
    counts = {day: PER_DAY for day in SYNCED_DAYS}
    counts[MISSING_DAY] = MISSING_COUNT
    return counts


def _external_counts_all_synced() -> dict[str, int]:
    """外部实时量：与补齐后的本地完全一致"""
    counts = {day: PER_DAY for day in SYNCED_DAYS}
    counts[MISSING_DAY] = MISSING_COUNT
    return counts


_ITEMS = [
    {
        "device_type": "X",
        "layer_type": "single",
        "quantity": 100,
        "unit_price": 10.00,
    }
]


class TestGenerateGuard:
    async def test_generate_rejected_when_snapshot_incomplete(
        self, test_client, auth_headers, guard_customer, app
    ):
        """部分日期未同步 → 拒绝生成，文案含差异日期与修复动作"""
        app.ctx.external_mysql_engine = _mock_external_engine(_external_counts_complete())

        request, response = await test_client.post(
            "/api/v1/billing/invoices/generate",
            json={
                "customer_id": guard_customer["id"],
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
                "items": _ITEMS,
            },
            headers=auth_headers,
        )

        assert response.status == 400
        data = response.json
        assert data["code"] == 40001
        assert guard_customer["name"] in data["message"]
        assert MISSING_DAY in data["message"]
        assert f"缺 {MISSING_COUNT} 笔" in data["message"]
        assert "强制覆盖" in data["message"]

    async def test_generate_success_after_sync_completed(
        self, test_client, auth_headers, guard_customer, app, db_session
    ):
        """补齐 10-31 同步后 → 生成成功（201）"""
        app.ctx.external_mysql_engine = _mock_external_engine(_external_counts_all_synced())
        _insert_daily_orders(db_session, guard_customer["id"], [MISSING_DAY], MISSING_COUNT)
        db_session.commit()

        request, response = await test_client.post(
            "/api/v1/billing/invoices/generate",
            json={
                "customer_id": guard_customer["id"],
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
                "items": _ITEMS,
            },
            headers=auth_headers,
        )

        assert response.status == 201
        data = response.json
        assert data["code"] == 0
        assert data["data"]["total_amount"] == 1000.00

    async def test_external_engine_unreachable_passes(
        self, test_client, auth_headers, guard_customer, app
    ):
        """外部库不可达 → 放行不阻塞业务（warning 日志）"""
        app.ctx.external_mysql_engine = _mock_external_engine_unreachable()

        request, response = await test_client.post(
            "/api/v1/billing/invoices/generate",
            json={
                "customer_id": guard_customer["id"],
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
                "items": _ITEMS,
            },
            headers=auth_headers,
        )

        assert response.status == 201
        assert response.json["code"] == 0

    async def test_batch_skips_inconsistent_customer(
        self, test_client, auth_headers, guard_customer, app
    ):
        """批量生成：不一致客户进 skipped（reason 含差异日期），不整单失败"""
        app.ctx.external_mysql_engine = _mock_external_engine(_external_counts_complete())

        request, response = await test_client.post(
            "/api/v1/billing/invoices/generate-batch",
            json={
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
            },
            headers=auth_headers,
        )

        assert response.status == 200
        data = response.json["data"]
        skipped = data["skipped"]
        target = [s for s in skipped if s["customer_id"] == guard_customer["id"]]
        assert len(target) == 1
        assert MISSING_DAY in target[0]["reason"]
        assert "强制覆盖" in target[0]["reason"]
        # 不一致客户未生成结算单
        generated_ids = [g["customer_id"] for g in data["generated"]]
        assert guard_customer["id"] not in generated_ids
