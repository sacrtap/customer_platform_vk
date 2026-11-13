"""CRM 运行时配置（页面可维护 + 进程内缓存）

设计取舍：
- `CrmClient` / `is_crm_enabled()` / 路由与新配置端点都在同步上下文里读配置，
  而配置来自数据库，所以启动时加载一次到模块级缓存，保存时刷新缓存。
- 数据库没有保存过配置时，回退到环境变量（`CRM_*`），保证既有部署行为不变。
- 密码只在内存与密文中存在，`public_view()` 永不返回明文。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache.base import cache_service
from ..config import settings
from ..models.crm_setting import CrmSetting
from ..utils.crypto import (
    CryptoNotConfigured,
    DecryptFailed,
    decrypt_secret,
    encrypt_secret,
    is_credential_key_configured,
)

logger = logging.getLogger(__name__)

SETTING_NAME = "default"
DEFAULT_BASE_URL = "https://lxcrm.weiwenjia.com"
TOKEN_KEY_PREFIX = "crm:token"


@dataclass(frozen=True)
class CrmConfig:
    """运行期生效的 CRM 配置"""

    enabled: bool
    base_url: str
    corp_id: str
    phone: str
    password: str
    source: str  # database | environment

    @property
    def credentials_complete(self) -> bool:
        return bool(self.corp_id.strip() and self.phone.strip() and self.password)

    @property
    def active(self) -> bool:
        """真正可用：开关打开 + 凭据完整"""
        return self.enabled and self.credentials_complete


def _from_environment() -> CrmConfig:
    return CrmConfig(
        enabled=bool(settings.crm_enabled),
        base_url=(settings.crm_base_url or DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        corp_id=(settings.crm_corp_id or "").strip(),
        phone=(settings.crm_phone or "").strip(),
        password=settings.crm_password or "",
        source="environment",
    )


_runtime: Optional[CrmConfig] = None


def get_crm_config() -> CrmConfig:
    """同步读取生效配置（缓存未加载时回退环境变量）"""
    return _runtime or _from_environment()


def reset_crm_config_cache() -> None:
    """测试辅助：清空进程内缓存"""
    global _runtime
    _runtime = None


def _mask_phone(phone: str) -> str:
    if len(phone) >= 7:
        return f"{phone[:3]}****{phone[-4:]}"
    return "****" if phone else ""


def public_view(cfg: Optional[CrmConfig] = None) -> dict:
    """接口返回的脱敏视图：密码只回布尔，手机号打码"""
    current = cfg or get_crm_config()
    return {
        "enabled": current.enabled,
        "base_url": current.base_url,
        "corp_id": current.corp_id,
        "phone_masked": _mask_phone(current.phone),
        "password_set": bool(current.password),
        "credentials_complete": current.credentials_complete,
        "active": current.active,
        "source": current.source,
        "credential_key_configured": is_credential_key_configured(),
    }


async def load_crm_config(db: AsyncSession | None = None) -> CrmConfig:
    """启动钩子/保存后调用：从数据库加载配置到缓存

    `db` 为空时由调用方提供；这里不做连接管理，避免和请求会话/session_factory 冲突。
    """
    global _runtime
    if db is None:
        _runtime = _from_environment()
        return _runtime

    row = await db.scalar(select(CrmSetting).where(CrmSetting.name == SETTING_NAME))
    if row is None:
        _runtime = _from_environment()
        return _runtime

    password = ""
    if row.password_cipher:
        try:
            password = decrypt_secret(row.password_cipher)
        except CryptoNotConfigured:
            logger.warning("CRM 凭据已加密但未配置 CRM_CREDENTIAL_KEY，独立运行期按无密码处理")
        except DecryptFailed as e:
            logger.warning("%s；请重新保存 CRM 登录密码", e)

    _runtime = CrmConfig(
        enabled=bool(row.enabled),
        base_url=(row.base_url or DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        corp_id=(row.corp_id or "").strip(),
        phone=(row.phone or "").strip(),
        password=password,
        source="database",
    )
    return _runtime


async def _invalidate_tokens(*corp_ids: str) -> None:
    """企业ID/手机号/密码变更后，旧 token 必须立即失效"""
    try:
        redis = await cache_service._get_redis()
    except Exception as e:  # pragma: no cover - 缓存不可用时 token 仍会自然过期
        logger.warning("CRM token 失效失败（Redis 不可用）: %s", e)
        return
    if redis is None:
        return
    for corp_id in {cid.strip() for cid in corp_ids if cid and cid.strip()}:
        try:
            await redis.delete(f"{TOKEN_KEY_PREFIX}:{corp_id}")
        except Exception as e:  # pragma: no cover
            logger.warning("CRM token 失效失败: %s", e)


async def save_crm_config(
    db: AsyncSession,
    *,
    enabled: bool,
    base_url: str,
    corp_id: str,
    phone: str,
    password: str | None = None,
    clear_password: bool = False,
    updated_by: int | None = None,
) -> CrmConfig:
    """保存/更换配置（调用方负责事务）

    密码语义：
    - `password` 为 None/空串且 `clear_password=False` → 保留原密码（前端不展示明文）
    - `password` 非空 → 加密覆盖
    - `clear_password=True` → 清除已保存密码
    """
    row = await db.scalar(select(CrmSetting).where(CrmSetting.name == SETTING_NAME))
    previous = get_crm_config()
    old_cipher = row.password_cipher if row is not None else None

    if clear_password:
        new_cipher: str | None = None
    elif password:
        new_cipher = encrypt_secret(password)
    else:
        new_cipher = old_cipher

    if row is None:
        row = CrmSetting(
            name=SETTING_NAME,
            enabled=enabled,
            base_url=base_url,
            corp_id=corp_id,
            phone=phone,
            password_cipher=new_cipher,
            updated_by=updated_by,
        )
        db.add(row)
    else:
        row.enabled = enabled
        row.base_url = base_url
        row.corp_id = corp_id
        row.phone = phone
        row.password_cipher = new_cipher
        row.updated_by = updated_by
    await db.flush()

    cfg = await load_crm_config(db)
    await _invalidate_tokens(previous.corp_id, cfg.corp_id)
    return cfg
