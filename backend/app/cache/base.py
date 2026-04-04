"""通用 Redis 缓存服务

提供热点数据缓存功能，支持：
- 客户列表缓存
- 标签列表缓存
- 客户详情缓存
- 缓存失效管理
"""

import json
import logging
from typing import Any, Optional
from ..config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """通用缓存服务"""

    def __init__(self):
        self._redis = None
        self._ttl_config = {
            "customer_list": 300,  # 5 分钟
            "customer_detail": 600,  # 10 分钟
            "tag_list": 3600,  # 1 小时
            "tag_stats": 1800,  # 30 分钟
            "analytics": 900,  # 15 分钟
            "analytics_dashboard_stats": 300,  # 5 分钟
            "analytics_dashboard_chart": 900,  # 15 分钟
            "analytics_health_stats": 600,  # 10 分钟
            "analytics_health_warning": 180,  # 3 分钟
            "analytics_health_inactive": 600,  # 10 分钟
            "analytics_profile": 3600,  # 1 小时
            "analytics_invoice_status": 300,  # 5 分钟
            "analytics_consumption_trend": 900,  # 15 分钟
            "analytics_top_customers": 900,  # 15 分钟
            "analytics_device_distribution": 900,  # 15 分钟
            "analytics_payment_analysis": 600,  # 10 分钟
            "analytics_prediction": 1800,  # 30 分钟
            "billing_pricing_rules": 3600,  # 1 小时
            "default": 300,  # 5 分钟
        }

    async def _get_redis(self):
        """懒加载 Redis 连接"""
        if self._redis is None:
            import aioredis

            self._redis = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    def _build_key(self, prefix: str, *parts: Any) -> str:
        """构建缓存键"""
        parts_str = ":".join(str(p) for p in parts)
        return f"cache:{prefix}:{parts_str}"

    async def get(self, prefix: str, *parts: Any) -> Optional[Any]:
        """
        从缓存获取数据

        Args:
            prefix: 缓存前缀
            *parts: 键的组成部分

        Returns:
            缓存的数据，不存在返回 None
        """
        try:
            redis = await self._get_redis()
            key = self._build_key(prefix, *parts)
            data = await redis.get(key)
            if data is not None:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"缓存读取失败 {prefix}:{parts}: {e}")
            return None

    async def set(
        self,
        prefix: str,
        data: Any,
        *parts: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        设置缓存数据

        Args:
            prefix: 缓存前缀
            data: 要缓存的数据
            *parts: 键的组成部分
            ttl: 过期时间（秒），None 则使用默认配置

        Returns:
            是否设置成功
        """
        try:
            redis = await self._get_redis()
            key = self._build_key(prefix, *parts)
            expire = ttl or self._ttl_config.get(prefix, self._ttl_config["default"])
            serialized = json.dumps(data, ensure_ascii=False, default=str)
            await redis.setex(key, expire, serialized)
            return True
        except Exception as e:
            logger.warning(f"缓存写入失败 {prefix}:{parts}: {e}")
            return False

    async def delete(self, prefix: str, *parts: Any) -> bool:
        """
        删除指定缓存

        Args:
            prefix: 缓存前缀
            *parts: 键的组成部分

        Returns:
            是否删除成功
        """
        try:
            redis = await self._get_redis()
            key = self._build_key(prefix, *parts)
            await redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"缓存删除失败 {prefix}:{parts}: {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> bool:
        """
        批量删除匹配模式的缓存

        Args:
            pattern: 匹配模式，如 "cache:customer_list:*"

        Returns:
            是否删除成功
        """
        try:
            redis = await self._get_redis()
            keys = await redis.keys(pattern)
            if keys:
                await redis.delete(*keys)
                logger.info(f"已清除 {len(keys)} 个匹配 '{pattern}' 的缓存")
            return True
        except Exception as e:
            logger.warning(f"缓存模式清除失败 {pattern}: {e}")
            return False

    async def invalidate_customer_cache(
        self, customer_id: Optional[int] = None
    ) -> bool:
        """
        清除客户相关缓存

        Args:
            customer_id: 指定客户 ID 则只清除该客户缓存，None 则清除所有客户缓存
        """
        if customer_id:
            await self.delete("customer_detail", customer_id)
        await self.invalidate_pattern("cache:customer_list:*")
        return True

    async def invalidate_tag_cache(self) -> bool:
        """清除所有标签相关缓存"""
        await self.invalidate_pattern("cache:tag_list:*")
        await self.invalidate_pattern("cache:tag_stats:*")
        return True

    async def invalidate_analytics_cache(self, category: Optional[str] = None) -> bool:
        """
        清除分析相关缓存

        Args:
            category: 指定类别，如 "dashboard", "health", "profile", "invoice", "consumption", "prediction"
                     None 则清除所有分析缓存
        """
        if category:
            await self.invalidate_pattern(f"cache:analytics_{category}_*")
        else:
            await self.invalidate_pattern("cache:analytics_*")
            await self.invalidate_pattern("cache:billing_*")
        return True

    async def invalidate_billing_cache(self) -> bool:
        """清除结算相关缓存"""
        await self.invalidate_pattern("cache:billing_*")
        await self.invalidate_pattern("cache:analytics_*")
        return True


# 全局缓存实例
cache_service = CacheService()
