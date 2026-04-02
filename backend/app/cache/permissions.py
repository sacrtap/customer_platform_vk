"""权限缓存服务"""

import json
from typing import Set, Optional
from ..config import settings
import aioredis


class PermissionCache:
    """权限缓存类"""

    def __init__(self):
        self.redis_url = settings.redis_url
        self._redis: Optional[aioredis.Redis] = None
        self.default_ttl = 300  # 5 minutes

    async def _get_redis(self) -> aioredis.Redis:
        """获取 Redis 连接"""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )
        return self._redis

    async def get_permissions(self, user_id: int) -> Optional[Set[str]]:
        """
        从缓存获取用户权限

        Args:
            user_id: 用户ID

        Returns:
            权限代码集合，如果缓存不存在返回 None
        """
        redis = await self._get_redis()
        key = f"permissions:user:{user_id}"
        data = await redis.get(key)

        if data is None:
            return None

        return set(json.loads(data))

    async def set_permissions(self, user_id: int, permissions: Set[str]) -> None:
        """
        设置用户权限到缓存

        Args:
            user_id: 用户ID
            permissions: 权限代码集合
        """
        redis = await self._get_redis()
        key = f"permissions:user:{user_id}"
        data = json.dumps(list(permissions))
        await redis.setex(key, self.default_ttl, data)

    async def delete_permissions(self, user_id: int) -> None:
        """
        删除用户权限缓存

        Args:
            user_id: 用户ID
        """
        redis = await self._get_redis()
        key = f"permissions:user:{user_id}"
        await redis.delete(key)

    async def clear_all(self) -> None:
        """清空所有权限缓存"""
        redis = await self._get_redis()
        pattern = "permissions:user:*"
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)


# 全局缓存实例
permission_cache = PermissionCache()
