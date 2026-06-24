"""路由入口"""

from . import auth, permissions, roles, users, sync_tasks

__all__ = ["auth", "users", "roles", "permissions", "sync_tasks"]

