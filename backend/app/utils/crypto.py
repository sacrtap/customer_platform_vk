"""对称加密工具（CRM 凭据落库）

CRM 登录密码必须可逆（要回传给上游登录接口），不能像 API-Key 那样只存哈希。
因此使用 Fernet（AES-128-CBC + HMAC-SHA256）加密，密钥来自部署密钥
`CRM_CREDENTIAL_KEY`，绝不落库、不写日志。

密钥生成：
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from cryptography.fernet import Fernet, InvalidToken

from ..config import settings


class CryptoNotConfigured(Exception):
    """未注入加密密钥（或密钥格式非法），无法安全保存/读取密文"""


class DecryptFailed(Exception):
    """密文无法用当前密钥解开（密钥被更换或密文损坏）"""


def is_credential_key_configured() -> bool:
    """部署是否已注入可用的加密密钥"""
    return bool(settings.crm_credential_key.strip())


def _fernet() -> Fernet:
    key = settings.crm_credential_key.strip()
    if not key:
        raise CryptoNotConfigured(
            "未配置 CRM_CREDENTIAL_KEY，无法加密保存 CRM 凭据；请先注入该部署密钥"
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as e:
        raise CryptoNotConfigured("CRM_CREDENTIAL_KEY 格式非法，必须是 Fernet 密钥") from e


def encrypt_secret(plain: str) -> str:
    """加密明文（空串返回空串，避免存无意义密文）"""
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(cipher: str | None) -> str:
    """解密；密文为空返回空串，密钥不匹配时抛 DecryptFailed（调用方决定降级策略）"""
    if not cipher:
        return ""
    try:
        return _fernet().decrypt(cipher.encode()).decode()
    except InvalidToken as e:
        raise DecryptFailed("CRM 凭据密文无法解密：CRM_CREDENTIAL_KEY 可能已更换") from e
