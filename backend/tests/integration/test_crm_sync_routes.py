"""CRM 回款同步路由集成测试（真实 PG，上游全部打桩）

回归重点：`POST /sync-runs` 曾在真实链路返回 500 —— 权限校验/当前用户读取可能已在
session 上开启 SQLAlchemy autobegin 隐式事务，路由体再 `db.begin()` 抛
`InvalidRequestError: A transaction is already begun`，前端只能看到「系统繁忙」。

因此这里同时锁定：
1. 显式写事务前的隐式事务必须被结束（`begin_write` 语义）；
2. 同步任务创建的 202 / 409 / 400 分支；
3. 后台任务不在测试进程里真发 HTTP（monkeypatch 执行入口）。
"""

from datetime import date
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from app.config import settings
from app.services.crm_config import reset_crm_config_cache
from app.utils.crypto import encrypt_secret
from app.utils.db import begin_write

pytestmark = pytest.mark.asyncio


def _today_first_day() -> date:
    return date.today().replace(day=1)


@pytest.fixture(autouse=True)
def crm_enabled_config(monkeypatch, db_session):
    """写入一份可用的 CRM 配置（凭据为假，不会真的发请求）"""
    db_session.execute(text("DELETE FROM crm_settings"))
    db_session.execute(text("DELETE FROM crm_sync_runs"))
    db_session.commit()
    monkeypatch.setattr(settings, "crm_credential_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "crm_enabled", False)
    monkeypatch.setattr(settings, "crm_corp_id", "")
    monkeypatch.setattr(settings, "crm_phone", "")
    monkeypatch.setattr(settings, "crm_password", "")
    reset_crm_config_cache()
    db_session.execute(
        text(
            """
            INSERT INTO crm_settings
                (name, enabled, base_url, corp_id, phone, password_cipher, created_at, updated_at)
            VALUES ('default', TRUE, 'https://lxcrm.weiwenjia.com', :corp,
                    '13800000000', :pwd, NOW(), NOW())
            """
        ),
        {"corp": "corp-sync-test", "pwd": encrypt_secret("sync-test-pass")},
    )
    db_session.commit()
    reset_crm_config_cache()
    yield
    db_session.execute(text("DELETE FROM crm_settings"))
    db_session.execute(text("DELETE FROM crm_sync_runs"))
    db_session.commit()
    reset_crm_config_cache()


@pytest.fixture(autouse=True)
def no_background_sync(monkeypatch):
    """后台执行入口打桩：断言创建逻辑，不真去访问上游"""
    monkeypatch.setattr(
        "app.routes.crm_recharge.CrmRechargeService.execute_sync_run",
        AsyncMock(return_value=None),
    )


def _headers(auth_token: str) -> dict:
    return {"Authorization": f"Bearer {auth_token}"}


async def test_begin_write_ends_implicit_transaction(app):
    """结构性锚点：begin_write 必须先结束请求级隐式事务

    这类 500 的根因是「前面发生过查询 → session 已在事务中」；helper 一旦被改成
    裸 `db.begin()`，本用例立刻失败。
    """
    session = app.ctx.async_session_maker()
    try:
        await session.execute(text("SELECT 1"))
        assert session.in_transaction() is True

        async with begin_write(session):
            assert session.in_transaction() is True

        assert session.in_transaction() is False
    finally:
        await session.close()


async def test_create_sync_run_returns_202(test_client, auth_token, db_session):
    _, response = await test_client.post(
        "/api/v1/crm-recharge/sync-runs",
        json={"month": _today_first_day().strftime("%Y-%m")},
        headers=_headers(auth_token),
    )
    assert response.status == 202, response.json
    assert response.json["data"]["status"] == "pending"

    row = db_session.execute(
        text("SELECT status, trigger, corp_id FROM crm_sync_runs ORDER BY id DESC LIMIT 1")
    ).one()
    assert row.status == "pending"
    assert row.trigger == "manual"
    assert row.corp_id == "corp-sync-test"


async def test_second_create_while_pending_returns_409(test_client, auth_token):
    payload = {"month": _today_first_day().strftime("%Y-%m")}
    _, first = await test_client.post(
        "/api/v1/crm-recharge/sync-runs", json=payload, headers=_headers(auth_token)
    )
    assert first.status == 202, first.json

    _, second = await test_client.post(
        "/api/v1/crm-recharge/sync-runs", json=payload, headers=_headers(auth_token)
    )
    assert second.status == 409, second.json
    assert "正在执行" in second.json["message"]
    assert second.json["data"]["run_id"] == first.json["data"]["id"]


async def test_future_month_rejected(test_client, auth_token):
    future = (_today_first_day().replace(year=_today_first_day().year + 1)).strftime("%Y-%m")
    _, response = await test_client.post(
        "/api/v1/crm-recharge/sync-runs",
        json={"month": future},
        headers=_headers(auth_token),
    )
    assert response.status == 400
    assert "未来" in response.json["message"]


async def test_bad_month_format_rejected(test_client, auth_token):
    _, response = await test_client.post(
        "/api/v1/crm-recharge/sync-runs",
        json={"month": "2026-13"},
        headers=_headers(auth_token),
    )
    assert response.status == 400
    assert "YYYY-MM" in response.json["message"]


async def test_disabled_config_rejected(test_client, auth_token, db_session):
    db_session.execute(text("UPDATE crm_settings SET enabled = FALSE"))
    db_session.commit()
    reset_crm_config_cache()

    _, response = await test_client.post(
        "/api/v1/crm-recharge/sync-runs",
        json={"month": _today_first_day().strftime("%Y-%m")},
        headers=_headers(auth_token),
    )
    assert response.status == 400
    assert "未启用" in response.json["message"]
