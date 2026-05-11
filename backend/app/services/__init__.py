"""服务层入口"""

from .auth import AuthService
from .email import EmailService, email_service
from .permissions import get_user_permissions

__all__ = ["AuthService", "get_user_permissions", "EmailService", "email_service"]
