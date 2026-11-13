"""CRM 凭据加密单元测试（无数据库依赖）"""

import pytest
from cryptography.fernet import Fernet

from app.config import settings
from app.utils.crypto import (
    CryptoNotConfigured,
    DecryptFailed,
    decrypt_secret,
    encrypt_secret,
    is_credential_key_configured,
)


@pytest.fixture
def credential_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "crm_credential_key", key)
    return key


class TestEncryptDecrypt:
    def test_roundtrip(self, credential_key):
        cipher = encrypt_secret("p@ssw0rd-中文")
        assert cipher != "p@ssw0rd-中文"
        assert decrypt_secret(cipher) == "p@ssw0rd-中文"

    def test_empty_values(self, credential_key):
        assert encrypt_secret("") == ""
        assert decrypt_secret(None) == ""
        assert decrypt_secret("") == ""

    def test_key_configured_flag(self, credential_key):
        assert is_credential_key_configured() is True

    def test_missing_key_refuses_encrypt(self, monkeypatch):
        monkeypatch.setattr(settings, "crm_credential_key", "")
        assert is_credential_key_configured() is False
        with pytest.raises(CryptoNotConfigured):
            encrypt_secret("secret")

    def test_invalid_key_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "crm_credential_key", "not-a-fernet-key")
        with pytest.raises(CryptoNotConfigured):
            encrypt_secret("secret")

    def test_rotated_key_cannot_decrypt(self, credential_key, monkeypatch):
        cipher = encrypt_secret("secret")
        monkeypatch.setattr(settings, "crm_credential_key", Fernet.generate_key().decode())
        with pytest.raises(DecryptFailed):
            decrypt_secret(cipher)
