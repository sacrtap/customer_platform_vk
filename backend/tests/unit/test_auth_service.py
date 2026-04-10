"""Auth Service 单元测试"""

import pytest
from datetime import timedelta
import jwt
from unittest.mock import patch

from app.services.auth import AuthService


# ==================== Fixtures ====================


@pytest.fixture
def mock_jwt_settings():
    """Mock JWT 配置"""
    with patch("app.services.auth.settings") as mock_settings:
        mock_settings.jwt_secret = "test-secret-key"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_expire_minutes = 60
        mock_settings.jwt_refresh_expire_days = 7
        yield mock_settings


# ==================== Test Create Access Token ====================


class TestAuthService_CreateAccessToken:
    """创建 Access Token 测试"""

    def test_create_access_token_success(self, mock_jwt_settings):
        """测试创建访问令牌成功"""
        token = AuthService.create_access_token(
            user_id=1,
            username="testuser",
            roles=["user"],
        )

        assert token is not None
        assert isinstance(token, str)

        # 验证 token 内容
        payload = jwt.decode(
            token,
            mock_jwt_settings.jwt_secret,
            algorithms=[mock_jwt_settings.jwt_algorithm],
        )
        assert payload["user_id"] == 1
        assert payload["username"] == "testuser"
        assert payload["roles"] == ["user"]
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_access_token_with_multiple_roles(self, mock_jwt_settings):
        """测试创建带多个角色的 Token"""
        token = AuthService.create_access_token(
            user_id=1,
            username="admin",
            roles=["admin", "user", "manager"],
        )

        payload = jwt.decode(
            token,
            mock_jwt_settings.jwt_secret,
            algorithms=[mock_jwt_settings.jwt_algorithm],
        )
        assert payload["roles"] == ["admin", "user", "manager"]

    def test_create_access_token_expiry(self):
        """测试 Token 有过期时间"""
        with patch("app.services.auth.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret-key"
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.jwt_expire_minutes = 60

            token = AuthService.create_access_token(
                user_id=1,
                username="testuser",
                roles=[],
            )

            payload = jwt.decode(
                token,
                mock_settings.jwt_secret,
                algorithms=[mock_settings.jwt_algorithm],
            )

            # 验证有过期时间且大于 issued at
            assert "exp" in payload
            assert "iat" in payload
            assert payload["exp"] > payload["iat"]


# ==================== Test Create Refresh Token ====================


class TestAuthService_CreateRefreshToken:
    """创建 Refresh Token 测试"""

    def test_create_refresh_token_success(self, mock_jwt_settings):
        """测试创建刷新令牌成功"""
        token = AuthService.create_refresh_token(user_id=1)

        assert token is not None
        assert isinstance(token, str)

        # 验证 token 内容
        payload = jwt.decode(
            token,
            mock_jwt_settings.jwt_secret,
            algorithms=[mock_jwt_settings.jwt_algorithm],
        )
        assert payload["user_id"] == 1
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_refresh_token_expiry(self):
        """测试 Refresh Token 有过期时间"""
        with patch("app.services.auth.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret-key"
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.jwt_refresh_expire_days = 7

            token = AuthService.create_refresh_token(user_id=1)

            payload = jwt.decode(
                token,
                mock_settings.jwt_secret,
                algorithms=[mock_settings.jwt_algorithm],
            )

            # 验证有过期时间且大于 issued at
            assert "exp" in payload
            assert "iat" in payload
            assert payload["exp"] > payload["iat"]


# ==================== Test Verify Token ====================


class TestAuthService_VerifyToken:
    """验证 Token 测试"""

    def test_verify_token_success(self, mock_jwt_settings):
        """测试验证 Token 成功"""
        # 创建有效 token
        token = AuthService.create_access_token(
            user_id=1,
            username="testuser",
            roles=["user"],
        )

        # 验证 token
        payload = AuthService.verify_token(token)

        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["username"] == "testuser"

    def test_verify_token_expired(self, mock_jwt_settings):
        """测试验证过期 Token"""
        # 创建立即过期的 token
        with patch("app.services.auth.datetime") as mock_datetime:
            from datetime import datetime

            mock_datetime.utcnow.return_value = datetime.utcnow() - timedelta(
                minutes=61
            )
            expired_token = AuthService.create_access_token(
                user_id=1,
                username="testuser",
                roles=[],
            )

        # 验证过期 token
        payload = AuthService.verify_token(expired_token)

        assert payload is None

    def test_verify_token_invalid(self, mock_jwt_settings):
        """测试验证无效 Token"""
        payload = AuthService.verify_token("invalid_token_string")

        assert payload is None

    def test_verify_token_wrong_secret(self, mock_jwt_settings):
        """测试使用错误密钥验证"""
        token = AuthService.create_access_token(
            user_id=1,
            username="testuser",
            roles=[],
        )

        # 使用不同密钥验证
        with patch("app.services.auth.settings.jwt_secret", "wrong-secret"):
            payload = AuthService.verify_token(token)

        assert payload is None


# ==================== Test Decode Refresh Token ====================


class TestAuthService_DecodeRefreshToken:
    """验证 Refresh Token 测试"""

    def test_decode_refresh_token_success(self, mock_jwt_settings):
        """测试验证 Refresh Token 成功"""
        token = AuthService.create_refresh_token(user_id=1)

        payload = AuthService.decode_refresh_token(token)

        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["type"] == "refresh"

    def test_decode_refresh_token_wrong_type(self, mock_jwt_settings):
        """测试验证错误类型的 Token"""
        # 创建 access token 当作 refresh token 验证
        access_token = AuthService.create_access_token(
            user_id=1,
            username="testuser",
            roles=[],
        )

        payload = AuthService.decode_refresh_token(access_token)

        assert payload is None

    def test_decode_refresh_token_invalid(self, mock_jwt_settings):
        """测试验证无效 Refresh Token"""
        payload = AuthService.decode_refresh_token("invalid_token")

        assert payload is None

    def test_decode_refresh_token_expired(self, mock_jwt_settings):
        """测试验证过期 Refresh Token"""
        with patch("app.services.auth.datetime") as mock_datetime:
            from datetime import datetime

            mock_datetime.utcnow.return_value = datetime.utcnow() - timedelta(days=8)
            expired_token = AuthService.create_refresh_token(user_id=1)

        payload = AuthService.decode_refresh_token(expired_token)

        assert payload is None


# ==================== Integration Tests ====================


class TestAuthService_Integration:
    """集成测试"""

    def test_full_token_lifecycle(self, mock_jwt_settings):
        """测试完整 Token 生命周期"""
        # 创建
        access_token = AuthService.create_access_token(
            user_id=1,
            username="testuser",
            roles=["user", "admin"],
        )
        refresh_token = AuthService.create_refresh_token(user_id=1)

        # 验证 access token
        access_payload = AuthService.verify_token(access_token)
        assert access_payload is not None
        assert access_payload["username"] == "testuser"

        # 验证 refresh token
        refresh_payload = AuthService.decode_refresh_token(refresh_token)
        assert refresh_payload is not None
        assert refresh_payload["user_id"] == 1

    def test_token_type_separation(self, mock_jwt_settings):
        """测试 Token 类型隔离"""
        access_token = AuthService.create_access_token(
            user_id=1,
            username="testuser",
            roles=[],
        )
        refresh_token = AuthService.create_refresh_token(user_id=1)

        # access token 不能被 decode_refresh_token 验证
        assert AuthService.decode_refresh_token(access_token) is None

        # refresh token 不能被 verify_token 验证类型（但不会报错，只是类型不对）
        refresh_payload = AuthService.verify_token(refresh_token)
        assert refresh_payload is not None
        assert refresh_payload["type"] == "refresh"
