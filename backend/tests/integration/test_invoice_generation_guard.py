"""结算单生成以本地同步快照为准 — 集成测试

背景（用户决策，2026-11-09）：生成时不再做「本地快照 vs 外部实时量」逐日比对
（原 F1 一致性校验已移除），完全以数据库中每日同步入库的
daily_orders / daily_consumptions 快照为准，外部库改期/删除/重复派号等漂移
不再阻塞出账（深圳中原地产 2026-10 实证：3 笔订单外部改期 + 1 个订单号
重复派号导致逐日比对永远差 1 笔，无法出账）。

场景：
- 本地缺 10-31 同步、外部当天 17 笔 → 放行生成，金额取本地快照；
- 本地有外部已无的订单（快照过期）→ 放行生成；
- 外部 MySQL 不可达 / 引擎未配置 → 放行（生成路径不依赖外部库）；
- 批量生成：外部漂移客户正常进 generated，不再进 skipped；
- 周期去重（F5）保留，另行见 test_invoice_period_dedup.py。
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
# 快照计费口径：daily_consumptions 10-15 X/single 5 单 × 10 元 = 50
EXPECTED_TOTAL = 50.00


def _mock_external_engine(counts: dict[str, int]):
    """构造返回 CST 日分桶行的外部 MySQL 引擎 mock（任意 SQL 均返回该结果）"""
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
    """快照即准测试客户：自包含创建，已同步 10-01~10-30（缺 10-31）"""
    import uuid

    customer_id = 91000 + abs(hash(uuid.uuid4().hex[:8])) % 800
    company_id = customer_id
    customer_name = f"快照即准测试客户_{customer_id}"
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


def _external_counts_missing_day() -> dict[str, int]:
    """外部实时量：已同步日与本地一致，缺的 10-31 有 17 笔（旧逻辑会拒绝）"""
    counts = {day: PER_DAY for day in SYNCED_DAYS}
    counts[MISSING_DAY] = MISSING_COUNT
    return counts


def _external_counts_empty() -> dict[str, int]:
    """外部实时量：全部为 0（本地快照全部过期，旧逻辑会拒绝）"""
    return {day: 0 for day in SYNCED_DAYS}


async def _generate(test_client, auth_headers, customer_id: int):
    """调生成接口（不传 items，走计费规则 + 本地快照自动计算）"""
    return await test_client.post(
        "/api/v1/billing/invoices/generate",
        json={
            "customer_id": customer_id,
            "period_start": PERIOD_START,
            "period_end": PERIOD_END,
        },
        headers=auth_headers,
    )


class TestSnapshotWins:
    """生成以本地同步快照为准：外部漂移不再阻塞出账"""

    async def test_generate_succeeds_when_external_has_unsynced_day(
        self, test_client, auth_headers, guard_customer, app
    ):
        """本地缺 10-31 同步、外部当天 17 笔 → 放行生成，金额取本地快照"""
        app.ctx.external_mysql_engine = _mock_external_engine(_external_counts_missing_day())

        _, response = await _generate(test_client, auth_headers, guard_customer["id"])

        assert response.status == 201
        data = response.json
        assert data["code"] == 0
        # 金额来自本地 daily_consumptions 快照（5 单 × 10 元），与外部 17 笔无关
        assert data["data"]["total_amount"] == EXPECTED_TOTAL

    async def test_generate_succeeds_when_snapshot_stale(
        self, test_client, auth_headers, guard_customer, app
    ):
        """本地有外部已无的订单（改期/删除导致快照过期）→ 放行生成"""
        app.ctx.external_mysql_engine = _mock_external_engine(_external_counts_empty())

        _, response = await _generate(test_client, auth_headers, guard_customer["id"])

        assert response.status == 201
        assert response.json["data"]["total_amount"] == EXPECTED_TOTAL

    async def test_generate_succeeds_when_external_unreachable(
        self, test_client, auth_headers, guard_customer, app
    ):
        """外部 MySQL 不可达 → 放行（生成路径不再查询外部库）"""
        app.ctx.external_mysql_engine = _mock_external_engine_unreachable()

        _, response = await _generate(test_client, auth_headers, guard_customer["id"])

        assert response.status == 201
        assert response.json["code"] == 0

    async def test_generate_succeeds_without_external_engine(
        self, test_client, auth_headers, guard_customer, app
    ):
        """外部引擎未配置（None）→ 放行"""
        app.ctx.external_mysql_engine = None

        _, response = await _generate(test_client, auth_headers, guard_customer["id"])

        assert response.status == 201
        assert response.json["code"] == 0


class TestBatchSnapshotWins:
    """批量生成：外部漂移客户正常出账，不再进 skipped"""

    async def test_batch_generates_customer_with_external_drift(
        self, test_client, auth_headers, guard_customer, app
    ):
        """批量生成：缺同步日 + 外部漂移的客户进 generated（旧行为进 skipped）"""
        app.ctx.external_mysql_engine = _mock_external_engine(_external_counts_missing_day())

        _, response = await test_client.post(
            "/api/v1/billing/invoices/generate-batch",
            json={
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
            },
            headers=auth_headers,
        )

        assert response.status == 200
        data = response.json["data"]
        generated_ids = [g["customer_id"] for g in data["generated"]]
        skipped_ids = [s["customer_id"] for s in data["skipped"]]
        assert guard_customer["id"] in generated_ids
        assert guard_customer["id"] not in skipped_ids
