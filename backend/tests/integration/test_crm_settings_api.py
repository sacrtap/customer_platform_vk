"""CRM 配置（开关 + 凭据）API 集成测试

覆盖真实 PG 上的凭据边界：
1. 未保存过配置时回退部署环境变量，接口不泄露密码。
2. 保存后密码只存 Fernet 密文、接口只回 password_set / 打码手机号。
3. 密码留空 = 保留旧密码；clear_password = 清除。
4. 保存前验证：凭据错误拒绝落库，`force=true` 才允许跳过。
5. 配置变更即时影响运行期开关（is_crm_enabled）。
6. 加密密钥更换后旧密文不可解密，配置仍可读取（按无密码处理）。
"""

from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from app.config import settings
from app.services.crm_client import CrmAuthError
from app.services.crm_config import get_crm_config, load_crm_config, reset_crm_config_cache
from app.utils.crypto import decrypt_secret

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def crm_settings_env(monkeypatch, db_session):
    """每个用例独立密钥 + 清空配置表与进程内缓存"""
    db_session.execute(text("DELETE FROM crm_settings"))
    db_session.commit()
    monkeypatch.setattr(settings, "crm_credential_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "crm_enabled", False)
    monkeypatch.setattr(settings, "crm_corp_id", "")
    monkeypatch.setattr(settings, "crm_phone", "")
    monkeypatch.setattr(settings, "crm_password", "")
    monkeypatch.setattr(settings, "crm_base_url", "https://lxcrm.weiwenjia.com")
    reset_crm_config_cache()
    yield
    # 收尾同样清表：配置行会被 app 启动钩子加载，残留会污染后续用例
    db_session.execute(text("DELETE FROM crm_settings"))
    db_session.commit()
    reset_crm_config_cache()


def _headers(auth_token: str) -> dict:
    return {"Authorization": f"Bearer {auth_token}"}


def _payload(**overrides) -> dict:
    data = {
        "enabled": True,
        "base_url": "https://lxcrm.weiwenjia.com",
        "corp_id": "corp-123",
        "phone": "13800001111",
        "password": "S3cret!pass",
        "verify": False,
    }
    data.update(overrides)
    return data


def _cipher(db_session) -> str | None:
    db_session.commit()
    return db_session.execute(text("SELECT password_cipher FROM crm_settings")).scalar()


async def test_get_settings_falls_back_to_environment(test_client, auth_token):
    """未保存过页面配置时，来源为环境变量且不泄露任何密码"""
    _, response = await test_client.get(
        "/api/v1/crm-recharge/settings", headers=_headers(auth_token)
    )
    assert response.status == 200, response.json
    data = response.json["data"]
    assert data["source"] == "environment"
    assert data["enabled"] is False
    assert data["password_set"] is False
    assert "password" not in data
    assert data["phone_masked"] == ""


async def test_save_stores_ciphertext_and_returns_masked_view(test_client, auth_token, db_session):
    """保存后：库里是密文，接口只返回打码手机号与 password_set"""
    _, response = await test_client.put(
        "/api/v1/crm-recharge/settings", json=_payload(), headers=_headers(auth_token)
    )
    assert response.status == 200, response.json
    data = response.json["data"]
    assert data["source"] == "database"
    assert data["password_set"] is True
    assert data["active"] is True
    assert data["phone_masked"] == "138****1111"
    assert "password" not in data

    cipher = _cipher(db_session)
    assert cipher and "S3cret!pass" not in cipher
    assert decrypt_secret(cipher) == "S3cret!pass"
    assert get_crm_config().active is True

    _, again = await test_client.get("/api/v1/crm-recharge/settings", headers=_headers(auth_token))
    assert again.json["data"]["password_set"] is True


async def test_blank_password_keeps_existing_cipher(test_client, auth_token, db_session):
    """留空密码表示「不修改」，只更换其它字段"""
    await test_client.put(
        "/api/v1/crm-recharge/settings", json=_payload(), headers=_headers(auth_token)
    )
    first_cipher = _cipher(db_session)

    _, response = await test_client.put(
        "/api/v1/crm-recharge/settings",
        json=_payload(password="", phone="13900002222", corp_id="corp-456"),
        headers=_headers(auth_token),
    )
    assert response.status == 200, response.json
    assert _cipher(db_session) == first_cipher
    data = response.json["data"]
    assert data["corp_id"] == "corp-456"
    assert data["phone_masked"] == "139****2222"
    assert data["password_set"] is True


async def test_clear_password_removes_cipher(test_client, auth_token, db_session):
    """clear_password=true 明确清除已保存密码"""
    await test_client.put(
        "/api/v1/crm-recharge/settings", json=_payload(), headers=_headers(auth_token)
    )
    _, response = await test_client.put(
        "/api/v1/crm-recharge/settings",
        json=_payload(password="", clear_password=True),
        headers=_headers(auth_token),
    )
    assert response.status == 200, response.json
    assert _cipher(db_session) is None
    data = response.json["data"]
    assert data["password_set"] is False
    assert data["active"] is False


async def test_wrong_credentials_rejected_and_not_persisted(
    test_client, auth_token, db_session, monkeypatch
):
    """保存前验证失败：400 + can_force，且不写库"""
    monkeypatch.setattr(
        "app.services.crm_client.probe_credentials",
        AsyncMock(side_effect=CrmAuthError("CRM 登录失败：账号或密码不正确")),
    )
    payload = _payload(verify=True)
    payload.pop("verify")
    _, response = await test_client.put(
        "/api/v1/crm-recharge/settings", json=payload, headers=_headers(auth_token)
    )
    assert response.status == 400, response.json
    assert response.json["data"]["can_force"] is True
    assert "账号或密码不正确" in response.json["message"]
    db_session.commit()
    assert db_session.execute(text("SELECT COUNT(*) FROM crm_settings")).scalar() == 0


async def test_force_save_skips_verification(test_client, auth_token, db_session, monkeypatch):
    """上游不可用时二次确认后可强制保存"""
    monkeypatch.setattr(
        "app.services.crm_client.probe_credentials",
        AsyncMock(side_effect=CrmAuthError("CRM 登录失败：账号或密码不正确")),
    )
    _, response = await test_client.put(
        "/api/v1/crm-recharge/settings",
        json=_payload(password="Other!pass", force=True),
        headers=_headers(auth_token),
    )
    assert response.status == 200, response.json
    assert response.json["data"]["password_set"] is True
    assert decrypt_secret(_cipher(db_session)) == "Other!pass"


async def test_verification_success_enables_runtime_switch(test_client, auth_token, monkeypatch):
    """验证通过后保存，运行期开关立即生效；关闭后立即失效"""
    from app.services.crm_client import is_crm_enabled

    probe = AsyncMock(return_value={"customer_total": 5032, "corp_id": "corp-123"})
    monkeypatch.setattr("app.services.crm_client.probe_credentials", probe)

    payload = _payload()
    payload.pop("verify")
    _, response = await test_client.put(
        "/api/v1/crm-recharge/settings", json=payload, headers=_headers(auth_token)
    )
    assert response.status == 200, response.json
    assert response.json["data"]["verified_customer_total"] == 5032
    assert probe.await_count == 1
    assert is_crm_enabled() is True

    _, off = await test_client.put(
        "/api/v1/crm-recharge/settings",
        json=_payload(enabled=False),
        headers=_headers(auth_token),
    )
    assert off.status == 200, off.json
    assert is_crm_enabled() is False
    assert off.json["data"]["credentials_complete"] is True


async def test_rotated_key_degrades_without_crash(test_client, auth_token, monkeypatch, app):
    """加密密钥更换后旧密文不可解密：配置仍可读取，密码按未配置处理"""
    await test_client.put(
        "/api/v1/crm-recharge/settings",
        json=_payload(password="S3cret!pass", verify=False),
        headers=_headers(auth_token),
    )
    monkeypatch.setattr(settings, "crm_credential_key", Fernet.generate_key().decode())
    reset_crm_config_cache()

    async with app.ctx.async_session_maker() as session:
        cfg = await load_crm_config(session)

    assert cfg.source == "database"
    assert cfg.corp_id == "corp-123"
    assert cfg.password == ""
    assert cfg.active is False

    _, response = await test_client.get(
        "/api/v1/crm-recharge/settings", headers=_headers(auth_token)
    )
    assert response.status == 200, response.json
    assert response.json["data"]["password_set"] is False
    assert response.json["data"]["credentials_complete"] is False


async def test_clear_password_saves_without_verification(
    test_client, auth_token, db_session, monkeypatch
):
    """清除密码时没有可验证的凭据，保存不应被验证拦截"""
    probe = AsyncMock(return_value={"customer_total": 1, "corp_id": "corp-123"})
    monkeypatch.setattr("app.services.crm_client.probe_credentials", probe)

    await test_client.put(
        "/api/v1/crm-recharge/settings", json=_payload(), headers=_headers(auth_token)
    )
    probe.reset_mock()

    _, response = await test_client.put(
        "/api/v1/crm-recharge/settings",
        json=_payload(password="", clear_password=True),
        headers=_headers(auth_token),
    )
    assert response.status == 200, response.json
    assert probe.await_count == 0
    assert _cipher(db_session) is None
    assert response.json["data"]["password_set"] is False


async def test_verify_reports_warning_when_list_unreadable(test_client, auth_token, monkeypatch):
    """登录凭据有效但客户列表读不出来：验证接口仍 200，附 warning"""
    monkeypatch.setattr(
        "app.services.crm_client.probe_credentials",
        AsyncMock(
            return_value={
                "customer_total": None,
                "corp_id": "corp-123",
                "warning": "CRM 分页响应缺少列表字段（data 键：total_count）",
            }
        ),
    )
    _, response = await test_client.post(
        "/api/v1/crm-recharge/settings/test", json=_payload(), headers=_headers(auth_token)
    )
    assert response.status == 200, response.json
    data = response.json["data"]
    assert data["ok"] is True
    assert data["customer_total"] is None
    assert "缺少列表字段" in data["warning"]


async def test_save_succeeds_with_verification_warning(test_client, auth_token, monkeypatch):
    """分页契约问题不能锁死保存：带 warning 保存成功并回传说明"""
    monkeypatch.setattr(
        "app.services.crm_client.probe_credentials",
        AsyncMock(
            return_value={"customer_total": None, "corp_id": "corp-123", "warning": "列表不可读"}
        ),
    )
    payload = _payload()
    payload.pop("verify")
    _, response = await test_client.put(
        "/api/v1/crm-recharge/settings", json=payload, headers=_headers(auth_token)
    )
    assert response.status == 200, response.json
    data = response.json["data"]
    assert data["password_set"] is True
    assert data["verification_warning"] == "列表不可读"
    assert data["verified_customer_total"] is None
