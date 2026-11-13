"""CRM 充值管理集成测试

覆盖真实 PG 上的资金边界：
1. 余额/充值记录读点改用业务归期 `recharge_date`（跨月回款不再按入账时刻归期）。
2. CRM 回款导入的幂等（重复提交不重复入账）与冲突拒绝（改金额/改客户）。
3. 数据库清理不得删除 CRM 入账凭据。
4. 导入服务在事务内的资金写入与包年客户拒绝。
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.services.crm_recharge import (
    CrmImportError,
    CrmRechargeImportService,
    CrmRechargeService,
)

CORP_ID = ""
CRM_CUSTOMER_NAME = "CRM集成测试客户"


def _unique_customer_id(base: int = 98000) -> int:
    return base + abs(hash(uuid.uuid4().hex[:10])) % 900


def _insert_customer(db_session, *, cid: int, name: str, price_policy: str = "prepaid") -> int:
    db_session.execute(text("DELETE FROM customers WHERE id = :id"), {"id": cid})
    db_session.execute(
        text("""
        INSERT INTO customers (id, company_id, name, account_type, price_policy,
                               settlement_cycle, settlement_type, created_at, updated_at)
        VALUES (:id, :company_id, :name, '正式账号', :price_policy,
                'monthly', 'prepaid', NOW(), NOW())
        """),
        {"id": cid, "company_id": cid, "name": name, "price_policy": price_policy},
    )
    # 余额列表按 has_balance_row 过滤（非包年客户必须有余额行才出现）
    db_session.execute(
        text("""
        INSERT INTO customer_balances
            (customer_id, total_amount, real_amount, bonus_amount,
             used_total, used_real, used_bonus, created_at, updated_at)
        VALUES (:cid, 0, 0, 0, 0, 0, 0, NOW(), NOW())
        ON CONFLICT (customer_id) DO NOTHING
        """),
        {"cid": cid},
    )
    return cid


def _insert_recharge(
    db_session,
    *,
    customer_id: int,
    real_amount: Decimal,
    bonus_amount: Decimal = Decimal("0"),
    recharge_date: date,
    crm_payment_id: int | None = None,
) -> int:
    # recharge_records.operator_id 是真实外键，必须用库内存在的用户
    operator_id = int(
        db_session.execute(text("SELECT id FROM users WHERE username = 'admin'")).scalar_one()
    )
    return db_session.execute(
        text("""
            INSERT INTO recharge_records
                (customer_id, real_amount, bonus_amount, operator_id, recharge_date,
                 crm_payment_id, created_at)
            VALUES (:customer_id, :real_amount, :bonus_amount, :operator_id, :recharge_date,
                    :crm_payment_id, NOW())
            RETURNING id
            """),
        {
            "customer_id": customer_id,
            "real_amount": real_amount,
            "bonus_amount": bonus_amount,
            "operator_id": operator_id,
            "recharge_date": recharge_date,
            "crm_payment_id": crm_payment_id,
        },
    ).scalar_one()


@pytest.fixture
def crm_env(db_session):
    """构造 CRM 客户 + 一笔可导入回款，并绑定到一个预付费客户"""
    customer_id = _insert_customer(db_session, cid=_unique_customer_id(), name="CRM绑定客户A")
    other_id = _insert_customer(db_session, cid=_unique_customer_id(), name="CRM未绑定客户B")

    crm_customer_id = db_session.execute(
        text("""
        INSERT INTO crm_customers
            (corp_id, external_id, name, normalized_name, owner_name, last_seen_at,
             created_at, updated_at)
        VALUES (:corp_id, :external_id, :name, :normalized_name, '负责人', NOW(), NOW(), NOW())
        RETURNING id
        """),
        {
            "corp_id": CORP_ID,
            "external_id": _unique_customer_id(120000),
            "name": CRM_CUSTOMER_NAME,
            "normalized_name": CRM_CUSTOMER_NAME,
        },
    ).scalar_one()

    db_session.execute(
        text("UPDATE customers SET crm_customer_id = :crm_id WHERE id = :cid"),
        {"crm_id": crm_customer_id, "cid": customer_id},
    )

    amount = Decimal("1200.50")
    payment_id = db_session.execute(
        text("""
        INSERT INTO crm_payments
            (corp_id, external_id, crm_customer_id, contract_external_id, contract_title,
             customer_external_id, customer_name, amount, receive_date, approve_status,
             industry_path, industry_label, eligible, last_seen_at, created_at, updated_at)
        VALUES (:corp_id, :external_id, :crm_customer_id, :contract_external_id, '年度框架合同',
                :customer_external_id, :customer_name, :amount, :receive_date, 'approved',
                '1001/二手房', '房产经纪/二手房', TRUE, NOW(), NOW(), NOW())
        RETURNING id
        """),
        {
            "corp_id": CORP_ID,
            "external_id": _unique_customer_id(130000),
            "crm_customer_id": crm_customer_id,
            "contract_external_id": _unique_customer_id(140000),
            "customer_external_id": 501,
            "customer_name": CRM_CUSTOMER_NAME,
            "amount": amount,
            "receive_date": date(2026, 11, 5),
        },
    ).scalar_one()
    db_session.commit()

    data = {
        "customer_id": customer_id,
        "other_customer_id": other_id,
        "crm_customer_id": crm_customer_id,
        "payment_id": payment_id,
        "amount": amount,
        "receive_date": date(2026, 11, 5),
    }
    yield data

    db_session.rollback()
    for cid in (customer_id, other_id):
        db_session.execute(
            text("DELETE FROM recharge_records WHERE customer_id = :cid"), {"cid": cid}
        )
        db_session.execute(
            text("DELETE FROM customer_balances WHERE customer_id = :cid"), {"cid": cid}
        )
        db_session.execute(text("DELETE FROM customers WHERE id = :cid"), {"cid": cid})
    db_session.execute(text("DELETE FROM crm_payments WHERE id = :id"), {"id": payment_id})
    db_session.execute(text("DELETE FROM crm_customers WHERE id = :id"), {"id": crm_customer_id})
    db_session.commit()


async def _balance_row(test_client, auth_token, customer_id: int, **params):
    headers = {"Authorization": f"Bearer {auth_token}"}
    _, response = await test_client.get(
        "/api/v1/billing/balances", params={"page_size": 200, **params}, headers=headers
    )
    assert response.status == 200, response.json
    rows = response.json["data"]["list"]
    return next((row for row in rows if row["id"] == customer_id), None)


@pytest.mark.asyncio
async def test_balance_date_filter_uses_business_recharge_date(
    test_client, auth_token, db_session, crm_env
):
    """月窗口按业务归期过滤与展示，而不是入账操作时刻"""
    customer_id = crm_env["customer_id"]
    other_id = crm_env["other_customer_id"]
    _insert_recharge(
        db_session,
        customer_id=customer_id,
        real_amount=Decimal("100.00"),
        recharge_date=date(2026, 10, 31),
    )
    _insert_recharge(
        db_session,
        customer_id=customer_id,
        real_amount=Decimal("200.00"),
        recharge_date=date(2026, 11, 2),
    )
    # 仅 10 月回款的客户：验证窗口确实按业务归期落位
    _insert_recharge(
        db_session,
        customer_id=other_id,
        real_amount=Decimal("300.00"),
        recharge_date=date(2026, 10, 20),
    )
    db_session.commit()

    november = await _balance_row(
        test_client,
        auth_token,
        customer_id,
        recharge_date_from="2026-11-01",
        recharge_date_to="2026-11-30",
    )
    assert november is not None
    assert november["last_recharge_at"] == "2026-11-02"

    # 最近一次充值在 11 月 → 不得出现在 10 月窗口（窗口语义是最近充值日期）
    assert (
        await _balance_row(
            test_client,
            auth_token,
            customer_id,
            recharge_date_from="2026-10-01",
            recharge_date_to="2026-10-31",
        )
        is None
    )

    october_only = await _balance_row(
        test_client,
        auth_token,
        other_id,
        recharge_date_from="2026-10-01",
        recharge_date_to="2026-10-31",
    )
    assert october_only is not None, "10 月回款必须按业务归期命中 10 月窗口"
    assert october_only["last_recharge_at"] == "2026-10-20"


@pytest.mark.asyncio
async def test_recharge_records_expose_business_date_and_crm_source(
    test_client, auth_token, db_session, crm_env
):
    """充值记录同时返回业务归期与 CRM 来源，前端可区分归期与入账时刻"""
    record_id = _insert_recharge(
        db_session,
        customer_id=crm_env["customer_id"],
        real_amount=crm_env["amount"],
        recharge_date=crm_env["receive_date"],
        crm_payment_id=crm_env["payment_id"],
    )
    db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    _, response = await test_client.get(
        "/api/v1/billing/recharge-records",
        params={"customer_id": crm_env["customer_id"], "page_size": 50},
        headers=headers,
    )
    assert response.status == 200, response.json
    row = next(item for item in response.json["data"]["list"] if item["id"] == record_id)
    assert row["recharge_date"] == "2026-11-05"
    assert row["crm_payment_id"] == crm_env["payment_id"]
    assert row["crm_payment_external_id"] is not None
    assert row["created_at"] is not None


@pytest.mark.asyncio
async def test_import_same_payment_is_idempotent(test_client, auth_token, db_session, crm_env):
    """同一回款重复提交同客户同金额：幂等返回，不新增充值记录"""
    existing_id = _insert_recharge(
        db_session,
        customer_id=crm_env["customer_id"],
        real_amount=crm_env["amount"],
        recharge_date=crm_env["receive_date"],
        crm_payment_id=crm_env["payment_id"],
    )
    db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {
        "customer_id": crm_env["customer_id"],
        "real_amount": str(crm_env["amount"]),
        "bonus_amount": "0",
    }
    _, first = await test_client.post(
        f"/api/v1/crm-recharge/payments/{crm_env['payment_id']}/import",
        json=payload,
        headers=headers,
    )
    assert first.status == 200, first.json
    assert first.json["data"]["already_imported"] is True
    assert first.json["data"]["recharge_record_id"] == existing_id

    _, second = await test_client.post(
        f"/api/v1/crm-recharge/payments/{crm_env['payment_id']}/import",
        json=payload,
        headers=headers,
    )
    assert second.status == 200, second.json

    count = db_session.execute(
        text("SELECT COUNT(*) FROM recharge_records WHERE crm_payment_id = :pid"),
        {"pid": crm_env["payment_id"]},
    ).scalar_one()
    assert count == 1, "重复提交不得重复入账"


@pytest.mark.asyncio
async def test_import_existing_payment_with_changed_amount_conflicts(
    test_client, auth_token, db_session, crm_env
):
    """已导入回款改金额提交：409，不写资金"""
    _insert_recharge(
        db_session,
        customer_id=crm_env["customer_id"],
        real_amount=crm_env["amount"],
        recharge_date=crm_env["receive_date"],
        crm_payment_id=crm_env["payment_id"],
    )
    db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    _, response = await test_client.post(
        f"/api/v1/crm-recharge/payments/{crm_env['payment_id']}/import",
        json={
            "customer_id": crm_env["customer_id"],
            "real_amount": "999.00",
            "bonus_amount": "0",
        },
        headers=headers,
    )
    assert response.status == 409, response.json


@pytest.mark.asyncio
async def test_import_pending_payment_requires_crm_enabled(test_client, auth_token, crm_env):
    """CRM 未启用时，未入账回款不得导入（400），避免无复核写入资金

    用 400 而非 503：前端 handleError 只把 400/422 的后端 message 原样展示，
    503 会被统一成「系统繁忙」，用户看不到「CRM 未启用」这一真实原因。
    """
    headers = {"Authorization": f"Bearer {auth_token}"}
    _, response = await test_client.post(
        f"/api/v1/crm-recharge/payments/{crm_env['payment_id']}/import",
        json={
            "customer_id": crm_env["customer_id"],
            "real_amount": str(crm_env["amount"]),
            "bonus_amount": "0",
        },
        headers=headers,
    )
    assert response.status == 400, response.json
    assert "CRM 未启用" in response.json["message"]


@pytest.mark.asyncio
async def test_clear_balance_refuses_to_delete_crm_credentials(
    test_client, auth_token, db_session, crm_env
):
    """存在 CRM 来源入账时，数据库清理整次拒绝并保留记录"""
    _insert_recharge(
        db_session,
        customer_id=crm_env["customer_id"],
        real_amount=crm_env["amount"],
        recharge_date=crm_env["receive_date"],
        crm_payment_id=crm_env["payment_id"],
    )
    db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    # 测试权限清单未含 system:database_clear（生产 seed 才有）；本用例只验证清理
    # 保护逻辑，临时把该权限加入缓存，避免 403 掩盖资金约束
    from unittest.mock import AsyncMock

    from app.cache import permissions as permissions_module
    from tests._test_data import PERMISSION_CODES

    permissions_module.permission_cache.get_permissions = AsyncMock(
        return_value=PERMISSION_CODES | {"system:database_clear"}
    )

    _, response = await test_client.post(
        "/api/v1/system/database/clear-balance", json={}, headers=headers
    )
    assert response.status == 409, response.json

    remaining = db_session.execute(
        text("SELECT COUNT(*) FROM recharge_records WHERE crm_payment_id IS NOT NULL")
    ).scalar_one()
    assert remaining >= 1, "拒绝清理后 CRM 入账凭据必须仍在"


@pytest.mark.asyncio
async def test_import_service_writes_balance_and_business_date(app, db_session, crm_env):
    """事务内导入：余额增加、记录归期取回款日、镜像写入快照"""
    operator_id = db_session.execute(text("SELECT id FROM users WHERE username = 'admin'")).scalar()
    crm_env_for_test = dict(crm_env)
    db_session.commit()

    maker = app.ctx.async_session_maker
    async with maker() as session:
        async with session.begin():
            result = await CrmRechargeImportService(session).import_payment(
                payment_id=crm_env_for_test["payment_id"],
                customer_id=crm_env_for_test["customer_id"],
                real_amount=crm_env_for_test["amount"],
                bonus_amount=Decimal("100.00"),
                operator_id=int(operator_id),
                corp_id=CORP_ID,
                source_snapshot=None,
            )
        await session.commit()

    assert result["already_imported"] is False
    assert result["recharge_date"] == "2026-11-05"
    assert result["total_amount"] == "1300.50"
    assert result["balance"]["total_amount"] == "1300.50"

    row = db_session.execute(
        text("""
        SELECT real_amount, bonus_amount, recharge_date
        FROM recharge_records WHERE id = :id
        """),
        {"id": result["recharge_record_id"]},
    ).one()
    assert row[0] == Decimal("1200.50")
    assert row[1] == Decimal("100.00")
    assert row[2] == date(2026, 11, 5)

    snapshot = db_session.execute(
        text("SELECT imported_snapshot, source_changed FROM crm_payments WHERE id = :id"),
        {"id": crm_env_for_test["payment_id"]},
    ).one()
    assert snapshot[0]["receive_date"] == "2026-11-05"
    assert snapshot[1] is False


@pytest.mark.asyncio
async def test_import_service_rejects_package_customer(app, db_session, crm_env):
    """包年客户不支持 CRM 回款充值"""
    operator_id = db_session.execute(text("SELECT id FROM users WHERE username = 'admin'")).scalar()
    db_session.execute(
        text("UPDATE customers SET price_policy = 'yearly' WHERE id = :cid"),
        {"cid": crm_env["customer_id"]},
    )
    db_session.commit()

    maker = app.ctx.async_session_maker
    with pytest.raises(CrmImportError) as exc:
        async with maker() as session:
            async with session.begin():
                await CrmRechargeImportService(session).import_payment(
                    payment_id=crm_env["payment_id"],
                    customer_id=crm_env["customer_id"],
                    real_amount=crm_env["amount"],
                    bonus_amount=Decimal("0"),
                    operator_id=int(operator_id),
                    corp_id=CORP_ID,
                    source_snapshot=None,
                )
    assert "包年" in str(exc.value)

    count = db_session.execute(
        text("SELECT COUNT(*) FROM recharge_records WHERE crm_payment_id = :pid"),
        {"pid": crm_env["payment_id"]},
    ).scalar_one()
    assert count == 0, "拒绝后不得留下充值记录"


@pytest.mark.asyncio
async def test_recover_stale_sync_runs_writes_naive_cst(app, db_session):
    """启动恢复：心跳超时的 run 标记 failed（时间列是 CST 墙钟，不能写 aware）"""
    db_session.execute(
        text("""
        INSERT INTO crm_sync_runs
            (corp_id, month, trigger, status, phase, heartbeat_at, created_at, updated_at)
        VALUES (:corp_id, :month, 'manual', 'running', 'customers',
                TIMESTAMP '2020-01-01 00:00:00', NOW(), NOW())
        """),
        {"corp_id": CORP_ID, "month": date(2026, 11, 1)},
    )
    db_session.commit()

    recovered = await CrmRechargeService.recover_stale_sync_runs(app.ctx.async_session_maker)
    assert recovered >= 1

    status = db_session.execute(
        text("""
        SELECT status, finished_at FROM crm_sync_runs
        WHERE heartbeat_at = TIMESTAMP '2020-01-01 00:00:00'
        """),
    ).one()
    assert status[0] == "failed"
    assert status[1] is not None

    db_session.execute(
        text("DELETE FROM crm_sync_runs WHERE heartbeat_at < TIMESTAMP '2021-01-01 00:00:00'")
    )
    db_session.commit()


@pytest.mark.asyncio
async def test_list_payments_returns_row_with_import_columns(
    test_client, auth_token, db_session, crm_env
):
    """列表接口必须能序列化出行（导入记录是多列子查询，曾按 3 元解包 500）"""
    _insert_recharge(
        db_session,
        customer_id=crm_env["customer_id"],
        real_amount=crm_env["amount"],
        recharge_date=crm_env["receive_date"],
        crm_payment_id=crm_env["payment_id"],
    )
    db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    _, response = await test_client.get(
        "/api/v1/crm-recharge/payments",
        params={"keyword": CRM_CUSTOMER_NAME, "page_size": 50},
        headers=headers,
    )
    assert response.status == 200, response.json
    data = response.json["data"]
    assert data["crm_enabled"] is False
    row = next(item for item in data["list"] if item["id"] == crm_env["payment_id"])
    assert row["status"] == "imported"
    assert Decimal(row["total_amount"]) == crm_env["amount"]
    assert row["recharge_date"] == crm_env["receive_date"].isoformat()
    assert row["bound_customer_id"] == crm_env["customer_id"]


@pytest.mark.asyncio
async def test_list_payments_marks_unbound_row_pending_with_reason(
    test_client, auth_token, db_session, crm_env
):
    """未绑定客户的回款仍是「待导入」（绑定后可导入），但必须给出先绑定的原因"""
    db_session.execute(
        text("UPDATE customers SET crm_customer_id = NULL WHERE id = :cid"),
        {"cid": crm_env["customer_id"]},
    )
    db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    _, response = await test_client.get(
        "/api/v1/crm-recharge/payments",
        params={"keyword": CRM_CUSTOMER_NAME, "page_size": 50},
        headers=headers,
    )
    assert response.status == 200, response.json
    row = next(
        item for item in response.json["data"]["list"] if item["id"] == crm_env["payment_id"]
    )
    assert row["status"] == "pending"
    assert "绑定" in row["blocked_reason"]
    assert row["bound_customer_id"] is None


# ==================== 路由端到端（HTTP stub 上游） ====================

STUB_CORP = "corp-stub"


class _FakeRedis:
    """CrmClient 只用到 set(nx)/get/delete 的内存 Redis

    企业级限流（`crm:rate:*` 的 `set(nx=True, px=1250)`）在契约上由单元测试覆盖；
    这里让锁总是可用，避免集成测试被 1.25s 节流拖成排队超时。
    """

    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def set(self, key, value, nx=False, px=None, ex=None):
        if nx:
            return True
        self.data[key] = value
        return True

    async def get(self, key):
        return self.data.get(key)

    async def delete(self, key):
        self.data.pop(key, None)
        return 1


def _stub_client_factory(handler, fake_redis):
    import httpx

    from app.services.crm_client import CrmClient

    def factory():
        return CrmClient(
            redis=fake_redis,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            base_url="https://lxcrm.weiwenjia.com",
            corp_id=STUB_CORP,
            phone="13800000000",
            password="secret",
        )

    return factory


def _login_response():
    import httpx

    return httpx.Response(
        200, json={"code": 0, "data": {"user_token": "stub-token", "corp_id": STUB_CORP}}
    )


def _industry_metadata():
    return {
        "code": 0,
        "data": [
            {
                "label": "行业分类",
                "name": "text_asset_3565dc",
                "options": [
                    {
                        "label": "房产经纪",
                        "value": "房产经纪",
                        "children": [{"label": "二手房", "value": "房产经纪/二手房"}],
                    },
                    {"label": "新房开发", "value": "新房开发"},
                ],
            }
        ],
    }


@pytest.fixture
def stub_crm_payment(db_session):
    """独立 corp 的 CRM 客户 + 回款 + 已绑定客户（配合 HTTP stub 走真实路由）"""
    customer_id = _insert_customer(db_session, cid=_unique_customer_id(), name="CRM路由客户A")
    crm_customer_id = db_session.execute(
        text("""
        INSERT INTO crm_customers
            (corp_id, external_id, name, normalized_name, owner_name, last_seen_at,
             created_at, updated_at)
        VALUES (:corp_id, :external_id, 'CRM路由测试客户', 'CRM路由测试客户', '负责人',
                NOW(), NOW(), NOW())
        RETURNING id
        """),
        {"corp_id": STUB_CORP, "external_id": _unique_customer_id(220000)},
    ).scalar_one()
    db_session.execute(
        text("UPDATE customers SET crm_customer_id = :crm_id WHERE id = :cid"),
        {"crm_id": crm_customer_id, "cid": customer_id},
    )
    amount = Decimal("1200.50")
    receive_date = date(2026, 11, 5)
    payment_id = db_session.execute(
        text("""
        INSERT INTO crm_payments
            (corp_id, external_id, crm_customer_id, contract_external_id, contract_title,
             customer_external_id, customer_name, amount, receive_date, approve_status,
             industry_path, industry_label, eligible, last_seen_at, created_at, updated_at)
        VALUES (:corp_id, :external_id, :crm_customer_id, :contract_external_id, '年度框架合同',
                501, 'CRM路由测试客户', :amount, :receive_date, 'approved',
                '房产经纪/二手房', '房产经纪/二手房', TRUE, NOW(), NOW(), NOW())
        RETURNING id
        """),
        {
            "corp_id": STUB_CORP,
            "external_id": _unique_customer_id(230000),
            "crm_customer_id": crm_customer_id,
            "contract_external_id": _unique_customer_id(240000),
            "amount": amount,
            "receive_date": receive_date,
        },
    ).scalar_one()
    db_session.commit()

    data = {
        "customer_id": customer_id,
        "crm_customer_id": crm_customer_id,
        "payment_id": payment_id,
        "amount": amount,
        "receive_date": receive_date,
        "external_id": int(
            db_session.execute(
                text("SELECT external_id FROM crm_payments WHERE id = :id"), {"id": payment_id}
            ).scalar_one()
        ),
        "contract_external_id": int(
            db_session.execute(
                text("SELECT contract_external_id FROM crm_payments WHERE id = :id"),
                {"id": payment_id},
            ).scalar_one()
        ),
    }
    yield data

    db_session.rollback()
    db_session.execute(
        text("DELETE FROM recharge_records WHERE customer_id = :cid"), {"cid": customer_id}
    )
    db_session.execute(
        text("DELETE FROM customer_balances WHERE customer_id = :cid"), {"cid": customer_id}
    )
    db_session.execute(text("DELETE FROM customers WHERE id = :cid"), {"cid": customer_id})
    db_session.execute(text("DELETE FROM crm_payments WHERE id = :id"), {"id": payment_id})
    db_session.execute(text("DELETE FROM crm_customers WHERE id = :id"), {"id": crm_customer_id})
    db_session.commit()


@pytest.mark.asyncio
async def test_import_route_writes_funds_once_via_stubbed_upstream(
    test_client, auth_token, db_session, stub_crm_payment, monkeypatch
):
    """路由端到端：上游复核通过 → 资金入账一次；重复提交幂等；余额只加一次"""
    import httpx

    from app import config as config_module
    from app.routes import crm_recharge as crm_routes

    env = stub_crm_payment

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v2/auth/login":
            return _login_response()
        if path == "/api/v2/custom_fields/received_payment/by_group":
            return httpx.Response(200, json=_industry_metadata())
        if path == (
            f"/api/v2/contracts/{env['contract_external_id']}/received_payments/"
            f"{env['external_id']}"
        ):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "id": env["external_id"],
                        "customer_id": 501,
                        "contract_id": env["contract_external_id"],
                        "contract_title": "年度框架合同",
                        "customer_name": "CRM路由测试客户",
                        "amount": str(env["amount"]),
                        "receive_date": env["receive_date"].isoformat(),
                        "approve_status": "approved",
                        "text_asset_3565dc": "房产经纪/二手房",
                        "text_asset_3565dc_display": "房产经纪/二手房",
                    },
                },
            )
        raise AssertionError(f"unexpected CRM path: {path}")

    monkeypatch.setattr(config_module.settings, "crm_enabled", True)
    monkeypatch.setattr(config_module.settings, "crm_corp_id", STUB_CORP)
    monkeypatch.setattr(config_module.settings, "crm_phone", "13800000000")
    monkeypatch.setattr(config_module.settings, "crm_password", "secret")
    monkeypatch.setattr(crm_routes, "CrmClient", _stub_client_factory(handler, _FakeRedis()))

    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {
        "customer_id": env["customer_id"],
        "real_amount": str(env["amount"]),
        "bonus_amount": "100.00",
    }
    _, response = await test_client.post(
        f"/api/v1/crm-recharge/payments/{env['payment_id']}/import",
        json=payload,
        headers=headers,
    )
    assert response.status == 200, response.json
    data = response.json["data"]
    assert data["already_imported"] is False
    assert Decimal(data["total_amount"]) == env["amount"] + Decimal("100.00")
    assert data["recharge_date"] == env["receive_date"].isoformat()

    _, again = await test_client.post(
        f"/api/v1/crm-recharge/payments/{env['payment_id']}/import",
        json=payload,
        headers=headers,
    )
    assert again.status == 200, again.json
    assert again.json["data"]["already_imported"] is True

    rows = db_session.execute(
        text("""
        SELECT real_amount, bonus_amount, recharge_date
        FROM recharge_records WHERE crm_payment_id = :pid
        """),
        {"pid": env["payment_id"]},
    ).all()
    assert len(rows) == 1, rows
    assert rows[0][0] == env["amount"]
    assert rows[0][1] == Decimal("100.00")
    assert rows[0][2] == env["receive_date"]


@pytest.mark.asyncio
async def test_binding_route_validates_upstream_customer(
    test_client, auth_token, db_session, stub_crm_payment, monkeypatch
):
    """绑定走上游实时复核：可见客户可绑定，上游不可见则拒绝且不改本地绑定"""
    import httpx

    from app import config as config_module
    from app.routes import crm_recharge as crm_routes

    env = stub_crm_payment
    visible = {"value": True}
    external_id = int(
        db_session.execute(
            text("SELECT external_id FROM crm_customers WHERE id = :id"),
            {"id": env["crm_customer_id"]},
        ).scalar_one()
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/auth/login":
            return _login_response()
        if not visible["value"]:
            return httpx.Response(200, json={"code": 0, "data": None})
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"id": external_id, "name": "CRM路由测试客户"},
            },
        )

    monkeypatch.setattr(config_module.settings, "crm_enabled", True)
    monkeypatch.setattr(config_module.settings, "crm_corp_id", STUB_CORP)
    monkeypatch.setattr(config_module.settings, "crm_phone", "13800000000")
    monkeypatch.setattr(config_module.settings, "crm_password", "secret")
    monkeypatch.setattr(crm_routes, "CrmClient", _stub_client_factory(handler, _FakeRedis()))

    headers = {"Authorization": f"Bearer {auth_token}"}
    # 先解绑，再走复核重新绑定
    _, unbind = await test_client.put(
        f"/api/v1/crm-recharge/customers/{env['customer_id']}/binding",
        json={"crm_customer_id": None},
        headers=headers,
    )
    assert unbind.status == 200, unbind.json
    assert unbind.json["data"]["crm_customer_id"] is None

    _, bound = await test_client.put(
        f"/api/v1/crm-recharge/customers/{env['customer_id']}/binding",
        json={"crm_customer_id": env["crm_customer_id"]},
        headers=headers,
    )
    assert bound.status == 200, bound.json
    assert bound.json["data"]["crm_customer_id"] == env["crm_customer_id"]

    visible["value"] = False
    _, rejected = await test_client.put(
        f"/api/v1/crm-recharge/customers/{env['customer_id']}/binding",
        json={"crm_customer_id": None},
        headers=headers,
    )
    assert rejected.status == 200, rejected.json
    _, rejected_bind = await test_client.put(
        f"/api/v1/crm-recharge/customers/{env['customer_id']}/binding",
        json={"crm_customer_id": env["crm_customer_id"]},
        headers=headers,
    )
    assert rejected_bind.status == 502, rejected_bind.json
    still_bound = db_session.execute(
        text("SELECT crm_customer_id FROM customers WHERE id = :cid"),
        {"cid": env["customer_id"]},
    ).scalar_one()
    assert still_bound is None, "上游不可见时不得写入本地绑定"


def _payment_stub_handler(env):
    """上游复核与详情 stub（撤销测试复用导入测试的同一份响应）"""
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v2/auth/login":
            return _login_response()
        if path == "/api/v2/custom_fields/received_payment/by_group":
            return httpx.Response(200, json=_industry_metadata())
        if path == (
            f"/api/v2/contracts/{env['contract_external_id']}/received_payments/"
            f"{env['external_id']}"
        ):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "id": env["external_id"],
                        "customer_id": 501,
                        "contract_id": env["contract_external_id"],
                        "contract_title": "年度框架合同",
                        "customer_name": "CRM路由测试客户",
                        "amount": str(env["amount"]),
                        "receive_date": env["receive_date"].isoformat(),
                        "approve_status": "approved",
                        "text_asset_3565dc": "房产经纪/二手房",
                        "text_asset_3565dc_display": "房产经纪/二手房",
                    },
                },
            )
        raise AssertionError(f"unexpected CRM path: {path}")

    return handler


@pytest.mark.asyncio
async def test_revoke_route_rolls_back_funds_and_releases_payment(
    test_client, auth_token, db_session, stub_crm_payment, monkeypatch
):
    """撤销 → 余额回退、充值记录释放、可重新导入；导入期间改绑被硬阻断"""
    from app import config as config_module
    from app.routes import crm_recharge as crm_routes

    env = stub_crm_payment
    monkeypatch.setattr(config_module.settings, "crm_enabled", True)
    monkeypatch.setattr(config_module.settings, "crm_corp_id", STUB_CORP)
    monkeypatch.setattr(config_module.settings, "crm_phone", "13800000000")
    monkeypatch.setattr(config_module.settings, "crm_password", "secret")
    monkeypatch.setattr(
        crm_routes, "CrmClient", _stub_client_factory(_payment_stub_handler(env), _FakeRedis())
    )

    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {
        "customer_id": env["customer_id"],
        "real_amount": str(env["amount"]),
        "bonus_amount": "100.00",
    }
    _, imported = await test_client.post(
        f"/api/v1/crm-recharge/payments/{env['payment_id']}/import",
        json=payload,
        headers=headers,
    )
    assert imported.status == 200, imported.json

    # 已有导入凭据时解绑必须被拦下（改绑不迁移已入账资金）
    _, blocked = await test_client.put(
        f"/api/v1/crm-recharge/customers/{env['customer_id']}/binding",
        json={"crm_customer_id": None},
        headers=headers,
    )
    assert blocked.status == 409, blocked.json
    assert "撤销导入" in blocked.json["message"]

    _, revoked = await test_client.post(
        f"/api/v1/crm-recharge/payments/{env['payment_id']}/import/revoke",
        json={"customer_id": env["customer_id"], "reason": "绑定CRM客户错误"},
        headers=headers,
    )
    assert revoked.status == 200, revoked.json
    data = revoked.json["data"]
    assert data["needs_manual_reconciliation"] is False
    assert Decimal(data["balance"]["real_amount"]) == 0
    assert Decimal(data["balance"]["bonus_amount"]) == 0

    record_count = db_session.execute(
        text("SELECT count(*) FROM recharge_records WHERE crm_payment_id = :pid"),
        {"pid": env["payment_id"]},
    ).scalar_one()
    snapshot = db_session.execute(
        text("SELECT imported_snapshot FROM crm_payments WHERE id = :pid"),
        {"pid": env["payment_id"]},
    ).scalar_one()
    audits = db_session.execute(
        text("SELECT count(*) FROM audit_logs WHERE action = 'crm_recharge_import_revoke'")
    ).scalar_one()
    assert record_count == 0
    assert snapshot is None
    assert audits >= 1

    # 撤销后解绑放行
    _, unbound = await test_client.put(
        f"/api/v1/crm-recharge/customers/{env['customer_id']}/binding",
        json={"crm_customer_id": None},
        headers=headers,
    )
    assert unbound.status == 200, unbound.json


@pytest.mark.asyncio
async def test_revoke_route_requires_reason_and_imported_record(
    test_client, auth_token, stub_crm_payment, monkeypatch
):
    from app import config as config_module

    env = stub_crm_payment
    # 撤销不访问上游，但回款查询按当前企业过滤，需与 fixture 的 corp 对齐
    monkeypatch.setattr(config_module.settings, "crm_corp_id", STUB_CORP)
    headers = {"Authorization": f"Bearer {auth_token}"}

    _, no_reason = await test_client.post(
        f"/api/v1/crm-recharge/payments/{env['payment_id']}/import/revoke",
        json={"customer_id": env["customer_id"]},
        headers=headers,
    )
    assert no_reason.status == 400
    assert "原因必填" in no_reason.json["message"]

    _, not_imported = await test_client.post(
        f"/api/v1/crm-recharge/payments/{env['payment_id']}/import/revoke",
        json={"customer_id": env["customer_id"], "reason": "测试"},
        headers=headers,
    )
    assert not_imported.status == 400
    assert "尚未导入" in not_imported.json["message"]
