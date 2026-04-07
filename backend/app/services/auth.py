"""JWT 认证服务"""

import jwt
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from ..config import settings


class AuthService:
    """认证服务类"""

    @staticmethod
    def create_access_token(user_id: int, username: str, roles: list[str]) -> str:
        """创建 Access Token"""
        payload = {
            "user_id": user_id,
            "username": username,
            "roles": roles,
            "exp": datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes),
            "iat": datetime.utcnow(),
            "type": "access",
            "jti": str(uuid.uuid4()),  # JWT ID，用于黑名单
        }
        return jwt.encode(
            payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )

    @staticmethod
    def create_refresh_token(user_id: int) -> str:
        """创建 Refresh Token"""
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(days=settings.jwt_refresh_expire_days),
            "iat": datetime.utcnow(),
            "type": "refresh",
        }
        return jwt.encode(
            payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )

    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """验证 Token"""
        try:
            payload = jwt.decode(
                token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    @staticmethod
    def decode_refresh_token(token: str) -> Optional[Dict[str, Any]]:
        """验证 Refresh Token"""
        try:
            payload = jwt.decode(
                token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
            )
            if payload.get("type") != "refresh":
                return None
            return payload
        except jwt.InvalidTokenError:
            return None
