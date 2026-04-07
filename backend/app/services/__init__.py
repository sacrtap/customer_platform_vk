"""服务层入口"""

from .auth import AuthService
from .permissions import get_user_permissions
from .email import EmailService, email_service

__all__ = ["AuthService", "get_user_permissions", "EmailService", "email_service"]
