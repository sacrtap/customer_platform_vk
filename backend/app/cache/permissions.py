"""权限缓存服务

提供用户权限缓存功能，支持：
- 用户权限列表缓存
- 权限缓存失效
"""

import logging
from typing import List, Optional
from .base import cache_service

logger = logging.getLogger(__name__)


class PermissionCache:
    """权限缓存管理类"""

    def __init__(self):
        self._prefix = "permissions"
        self._ttl = 600  # 10 分钟

    async def get_permissions(self, user_id: int) -> Optional[List[str]]:
        """
        获取用户权限列表

        Args:
            user_id: 用户 ID

        Returns:
            权限列表，不存在返回 None
        """
        try:
            return await cache_service.get(self._prefix, user_id)
        except Exception as e:
            logger.warning(f"获取用户权限缓存失败 user_id={user_id}: {e}")
            return None

    async def set_permissions(self, user_id: int, permissions: List[str]) -> bool:
        """
        设置用户权限缓存

        Args:
            user_id: 用户 ID
            permissions: 权限列表

        Returns:
            是否设置成功
        """
        try:
            await cache_service.set(self._prefix, permissions, user_id, ttl=self._ttl)
            return True
        except Exception as e:
            logger.warning(f"设置用户权限缓存失败 user_id={user_id}: {e}")
            return False

    async def invalidate(self, user_id: int) -> bool:
        """
        失效用户权限缓存

        Args:
            user_id: 用户 ID

        Returns:
            是否失效成功
        """
        try:
            await cache_service.delete(self._prefix, user_id)
            return True
        except Exception as e:
            logger.warning(f"失效用户权限缓存失败 user_id={user_id}: {e}")
            return False


# 全局单例
permission_cache = PermissionCache()
