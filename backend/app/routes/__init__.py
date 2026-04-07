"""路由入口"""

from . import auth
from . import users
from . import roles
from . import permissions

__all__ = ["auth", "users", "roles", "permissions"]
