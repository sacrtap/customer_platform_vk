"""
客户运营中台 - Redis 缓存服务单元测试
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio

from app.cache.base import CacheService


# ==================== 测试夹具 ====================


@pytest.fixture
def cache_service() -> CacheService:
    """创建缓存服务实例"""
    return CacheService()


@pytest.fixture
def mock_redis() -> AsyncMock:
    """创建 Mock Redis 对象"""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock()
    redis_mock.setex = AsyncMock()
    redis_mock.delete = AsyncMock()
    redis_mock.keys = AsyncMock()
    return redis_mock


@pytest_asyncio.fixture
async def cache_with_mock_redis(mock_redis: AsyncMock) -> CacheService:
    """创建带有 Mock Redis 的缓存服务"""
    service = CacheService()
    service._redis = mock_redis
    return service


# ==================== 初始化测试 ====================


class TestCacheServiceInit:
    """缓存服务初始化测试"""

    def test_init_default_ttl_config(self, cache_service: CacheService):
        """测试初始化时 TTL 配置正确"""
        assert cache_service._ttl_config == {
            "customer_list": 300,  # 5 分钟
            "customer_detail": 600,  # 10 分钟
            "tag_list": 3600,  # 1 小时
            "tag_stats": 1800,  # 30 分钟
            "analytics": 900,  # 15 分钟
            "default": 300,  # 5 分钟
            # 分析数据细分 TTL
            "analytics_consumption_trend": 900,  # 15 分钟
            "analytics_top_customers": 900,  # 15 分钟
            "analytics_device_distribution": 900,  # 15 分钟
            "analytics_dashboard_stats": 300,  # 5 分钟
            "analytics_dashboard_chart": 900,  # 15 分钟
            "analytics_health_stats": 600,  # 10 分钟
            "analytics_health_warning": 180,  # 3 分钟
            "analytics_health_inactive": 600,  # 10 分钟
            "analytics_invoice_status": 300,  # 5 分钟
            "analytics_payment_analysis": 600,  # 10 分钟
            "analytics_profile": 3600,  # 1 小时
            "analytics_prediction": 1800,  # 30 分钟
            # 结算数据 TTL
            "billing_pricing_rules": 3600,  # 1 小时
        }

    def test_init_redis_none(self, cache_service: CacheService):
        """测试初始化时 Redis 连接为 None"""
        assert cache_service._redis is None


# ==================== 键构建测试 ====================


class TestBuildKey:
    """缓存键构建测试"""

    def test_build_key_simple(self, cache_service: CacheService):
        """测试简单键构建"""
        key = cache_service._build_key("customer_list", "all")
        assert key == "cache:customer_list:all"

    def test_build_key_multiple_parts(self, cache_service: CacheService):
        """测试多部分键构建"""
        key = cache_service._build_key("customer_detail", 123, "profile")
        assert key == "cache:customer_detail:123:profile"

    def test_build_key_with_string_parts(self, cache_service: CacheService):
        """测试字符串部分键构建"""
        key = cache_service._build_key("tag_list", "customer", "active")
        assert key == "cache:tag_list:customer:active"

    def test_build_key_with_mixed_types(self, cache_service: CacheService):
        """测试混合类型键构建"""
        key = cache_service._build_key("analytics", "dashboard", 2024, "Q1")
        assert key == "cache:analytics:dashboard:2024:Q1"

    def test_build_key_no_parts(self, cache_service: CacheService):
        """测试无额外部分的键构建"""
        key = cache_service._build_key("default")
        assert key == "cache:default:"


# ==================== Get 方法测试 ====================


class TestGet:
    """缓存获取测试"""

    @pytest.mark.asyncio
    async def test_get_cache_hit(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试缓存命中"""
        # 准备测试数据
        test_data = {"id": 1, "name": "测试客户"}
        mock_redis.get.return_value = json.dumps(test_data, ensure_ascii=False)

        # 执行测试
        result = await cache_with_mock_redis.get("customer_detail", 123)

        # 验证结果
        assert result == test_data
        mock_redis.get.assert_called_once_with("cache:customer_detail:123")

    @pytest.mark.asyncio
    async def test_get_cache_miss(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试缓存未命中"""
        mock_redis.get.return_value = None

        result = await cache_with_mock_redis.get("customer_detail", 999)

        assert result is None
        mock_redis.get.assert_called_once_with("cache:customer_detail:999")

    @pytest.mark.asyncio
    async def test_get_redis_connection_failure(self, cache_service: CacheService):
        """测试 Redis 连接失败时的错误处理"""
        with patch.object(
            cache_service, "_get_redis", new_callable=AsyncMock
        ) as mock_get_redis:
            mock_get_redis.side_effect = Exception("Redis connection failed")

            result = await cache_service.get("customer_list", "all")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_json_decode_error(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试 JSON 解码错误时的处理"""
        mock_redis.get.return_value = "invalid json{"

        result = await cache_with_mock_redis.get("customer_detail", 123)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_with_complex_data(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试获取复杂数据结构"""
        test_data = {
            "customers": [
                {"id": 1, "name": "客户 1", "tags": ["A", "B"]},
                {"id": 2, "name": "客户 2", "tags": ["C"]},
            ],
            "total": 2,
            "page": 1,
        }
        mock_redis.get.return_value = json.dumps(test_data, ensure_ascii=False)

        result = await cache_with_mock_redis.get("customer_list", "page_1")

        assert result == test_data
        assert len(result["customers"]) == 2


# ==================== Set 方法测试 ====================


class TestSet:
    """缓存设置测试"""

    @pytest.mark.asyncio
    async def test_set_with_default_ttl(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试使用默认 TTL 设置缓存"""
        test_data = {"id": 1, "name": "测试"}
        mock_redis.setex.return_value = True

        result = await cache_with_mock_redis.set("customer_list", test_data, "all")

        assert result is True
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "cache:customer_list:all"
        assert call_args[0][1] == 300  # customer_list 的默认 TTL
        assert json.loads(call_args[0][2]) == test_data

    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试使用自定义 TTL 设置缓存"""
        test_data = {"data": "test"}
        custom_ttl = 600

        result = await cache_with_mock_redis.set(
            "customer_list", test_data, "all", ttl=custom_ttl
        )

        assert result is True
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == custom_ttl

    @pytest.mark.asyncio
    async def test_set_with_unknown_prefix_uses_default_ttl(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试未知前缀使用默认 TTL"""
        test_data = {"data": "test"}

        await cache_with_mock_redis.set("unknown_prefix", test_data, "key")

        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 300  # default TTL

    @pytest.mark.asyncio
    async def test_set_serializes_complex_data(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试复杂数据的 JSON 序列化"""
        from datetime import datetime, date

        test_data = {
            "datetime_field": datetime(2024, 1, 1, 12, 0, 0),
            "date_field": date(2024, 1, 1),
            "nested": {"list": [1, 2, 3], "dict": {"a": 1}},
        }

        result = await cache_with_mock_redis.set("analytics", test_data, "stats")

        assert result is True
        # 验证序列化后的数据可以被反序列化
        serialized = mock_redis.setex.call_args[0][2]
        deserialized = json.loads(serialized)
        assert deserialized["nested"]["list"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_set_redis_failure(self, cache_service: CacheService):
        """测试 Redis 写入失败时的错误处理"""
        with patch.object(
            cache_service, "_get_redis", new_callable=AsyncMock
        ) as mock_get_redis:
            mock_get_redis.side_effect = Exception("Redis write failed")

            result = await cache_service.set("customer_list", {"data": "test"}, "all")

            assert result is False

    @pytest.mark.asyncio
    async def test_set_json_serialization_error(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试 JSON 序列化错误时的处理"""

        # 创建一个无法序列化的对象
        class UnserializableClass:
            pass

        test_data = {"obj": UnserializableClass()}

        # json.dumps 默认使用 str 转换器，应该能处理大多数类型
        # 这里测试正常情况
        mock_redis.setex.side_effect = Exception("Serialization error")

        result = await cache_with_mock_redis.set("customer_list", test_data, "all")

        assert result is False

    async def test_set_json_serialization_error(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试 JSON 序列化错误时的处理"""

        # 创建一个无法序列化的对象
        class UnserializableClass:
            pass

        test_data = {"obj": UnserializableClass()}

        # json.dumps 默认使用 str 转换器，应该能处理大多数类型
        # 这里测试正常情况
        mock_redis.setex.side_effect = Exception("Serialization error")

        result = await cache_with_mock_redis.set("customer_list", test_data, "all")

        assert result is False


# ==================== Delete 方法测试 ====================


class TestDelete:
    """缓存删除测试"""

    @pytest.mark.asyncio
    async def test_delete_success(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试删除缓存成功"""
        mock_redis.delete.return_value = 1

        result = await cache_with_mock_redis.delete("customer_detail", 123)

        assert result is True
        mock_redis.delete.assert_called_once_with("cache:customer_detail:123")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试删除不存在的键（仍然返回成功）"""
        mock_redis.delete.return_value = 0

        result = await cache_with_mock_redis.delete("customer_detail", 999)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_redis_failure(self, cache_service: CacheService):
        """测试 Redis 删除失败时的错误处理"""
        with patch.object(
            cache_service, "_get_redis", new_callable=AsyncMock
        ) as mock_get_redis:
            mock_get_redis.side_effect = Exception("Redis delete failed")

            result = await cache_service.delete("customer_list", "all")

            assert result is False


# ==================== Invalidate Pattern 测试 ====================


class TestInvalidatePattern:
    """模式匹配批量删除测试"""

    @pytest.mark.asyncio
    async def test_invalidate_pattern_success(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试模式匹配删除成功"""
        mock_redis.keys.return_value = [
            "cache:customer_list:page_1",
            "cache:customer_list:page_2",
            "cache:customer_list:page_3",
        ]
        mock_redis.delete.return_value = 3

        result = await cache_with_mock_redis.invalidate_pattern("cache:customer_list:*")

        assert result is True
        mock_redis.keys.assert_called_once_with("cache:customer_list:*")
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_pattern_no_matches(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试模式匹配无结果时"""
        mock_redis.keys.return_value = []

        result = await cache_with_mock_redis.invalidate_pattern("cache:nonexistent:*")

        assert result is True
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate_pattern_redis_failure(self, cache_service: CacheService):
        """测试 Redis 模式删除失败时的错误处理"""
        with patch.object(
            cache_service, "_get_redis", new_callable=AsyncMock
        ) as mock_get_redis:
            mock_get_redis.side_effect = Exception("Redis pattern delete failed")

            result = await cache_service.invalidate_pattern("cache:*")

            assert result is False


# ==================== Invalidate Customer Cache 测试 ====================


class TestInvalidateCustomerCache:
    """客户缓存失效测试"""

    @pytest.mark.asyncio
    async def test_invalidate_customer_cache_single(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试清除单个客户缓存"""
        mock_redis.delete.return_value = True
        mock_redis.keys.return_value = []

        result = await cache_with_mock_redis.invalidate_customer_cache(customer_id=123)

        assert result is True
        # 验证删除了这个客户的详情缓存
        mock_redis.delete.assert_any_call("cache:customer_detail:123")
        # 验证清除了客户列表缓存
        mock_redis.keys.assert_called_once_with("cache:customer_list:*")

    @pytest.mark.asyncio
    async def test_invalidate_customer_cache_all(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试清除所有客户缓存"""
        mock_redis.keys.return_value = []

        result = await cache_with_mock_redis.invalidate_customer_cache(customer_id=None)

        assert result is True
        # 没有指定 customer_id 时，不应该调用 delete 删除详情缓存
        # 只清除客户列表缓存
        mock_redis.keys.assert_called_once_with("cache:customer_list:*")

    @pytest.mark.asyncio
    async def test_invalidate_customer_cache_error_recovery(
        self, cache_service: CacheService
    ):
        """测试客户缓存清除错误时的恢复"""
        with patch.object(
            cache_service, "_get_redis", new_callable=AsyncMock
        ) as mock_get_redis:
            mock_get_redis.side_effect = Exception("Redis failure")

            # 即使 Redis 失败，也应该返回 True（错误在内部处理）
            result = await cache_service.invalidate_customer_cache(customer_id=123)

            assert result is True


# ==================== Invalidate Tag Cache 测试 ====================


class TestInvalidateTagCache:
    """标签缓存失效测试"""

    @pytest.mark.asyncio
    async def test_invalidate_tag_cache_success(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试清除标签缓存成功"""
        mock_redis.keys.side_effect = [
            ["cache:tag_list:customer", "cache:tag_list:product"],
            ["cache:tag_stats:summary"],
        ]
        mock_redis.delete.return_value = True

        result = await cache_with_mock_redis.invalidate_tag_cache()

        assert result is True
        # 验证清除了 tag_list 和 tag_stats 缓存
        assert mock_redis.keys.call_count == 2
        mock_redis.keys.assert_any_call("cache:tag_list:*")
        mock_redis.keys.assert_any_call("cache:tag_stats:*")

    @pytest.mark.asyncio
    async def test_invalidate_tag_cache_no_tags(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试没有标签缓存时"""
        mock_redis.keys.return_value = []

        result = await cache_with_mock_redis.invalidate_tag_cache()

        assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_tag_cache_error_recovery(
        self, cache_service: CacheService
    ):
        """测试标签缓存清除错误时的恢复"""
        with patch.object(
            cache_service, "_get_redis", new_callable=AsyncMock
        ) as mock_get_redis:
            mock_get_redis.side_effect = Exception("Redis failure")

            result = await cache_service.invalidate_tag_cache()

            assert result is True


# ==================== TTL 配置测试 ====================


class TestTTLConfiguration:
    """TTL 配置测试"""

    @pytest.mark.asyncio
    async def test_customer_list_ttl(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试客户列表 TTL 为 5 分钟"""
        await cache_with_mock_redis.set("customer_list", {"data": "test"}, "all")
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 300

    @pytest.mark.asyncio
    async def test_customer_detail_ttl(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试客户详情 TTL 为 10 分钟"""
        await cache_with_mock_redis.set("customer_detail", {"data": "test"}, 123)
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 600

    @pytest.mark.asyncio
    async def test_tag_list_ttl(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试标签列表 TTL 为 1 小时"""
        await cache_with_mock_redis.set("tag_list", {"data": "test"}, "customer")
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 3600

    @pytest.mark.asyncio
    async def test_tag_stats_ttl(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试标签统计 TTL 为 30 分钟"""
        await cache_with_mock_redis.set("tag_stats", {"data": "test"}, "summary")
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 1800

    @pytest.mark.asyncio
    async def test_analytics_ttl(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试分析数据 TTL 为 15 分钟"""
        await cache_with_mock_redis.set("analytics", {"data": "test"}, "stats")
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 900

    @pytest.mark.asyncio
    async def test_custom_ttl_overrides_default(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试自定义 TTL 覆盖默认配置"""
        await cache_with_mock_redis.set(
            "customer_list", {"data": "test"}, "all", ttl=1200
        )
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 1200  # 自定义 TTL 优先


# ==================== 集成场景测试 ====================


class TestIntegrationScenarios:
    """集成场景测试"""

    @pytest.mark.asyncio
    async def test_cache_workflow(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试完整的缓存工作流：设置 -> 获取 -> 删除"""
        test_data = {"id": 1, "name": "测试客户", "level": "KA"}

        # 设置缓存
        mock_redis.setex.return_value = True
        set_result = await cache_with_mock_redis.set("customer_detail", test_data, 1)
        assert set_result is True

        # 获取缓存
        mock_redis.get.return_value = json.dumps(test_data, ensure_ascii=False)
        get_result = await cache_with_mock_redis.get("customer_detail", 1)
        assert get_result == test_data

        # 删除缓存
        mock_redis.delete.return_value = 1
        delete_result = await cache_with_mock_redis.delete("customer_detail", 1)
        assert delete_result is True

    @pytest.mark.asyncio
    async def test_batch_invalidation_workflow(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试批量失效工作流"""
        # 模拟存在多个缓存键
        mock_redis.keys.return_value = [
            "cache:customer_list:page_1",
            "cache:customer_list:page_2",
        ]
        mock_redis.delete.return_value = 2

        # 清除客户缓存
        result = await cache_with_mock_redis.invalidate_customer_cache()

        assert result is True
        assert mock_redis.keys.called
        assert mock_redis.delete.called

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, cache_service: CacheService):
        """测试错误恢复工作流"""
        with patch.object(
            cache_service, "_get_redis", new_callable=AsyncMock
        ) as mock_get_redis:
            mock_get_redis.side_effect = Exception("Connection lost")

            # 所有操作都应该优雅失败
            get_result = await cache_service.get("customer_list", "all")
            set_result = await cache_service.set("customer_list", {}, "all")
            delete_result = await cache_service.delete("customer_list", "all")

            assert get_result is None
            assert set_result is False
            assert delete_result is False


# ==================== 边界条件测试 ====================


class TestEdgeCases:
    """边界条件测试"""

    @pytest.mark.asyncio
    async def test_get_empty_string_value(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试获取空字符串值"""
        mock_redis.get.return_value = '""'

        result = await cache_with_mock_redis.get("test", "key")

        assert result == ""

    @pytest.mark.asyncio
    async def test_get_zero_value(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试获取零值"""
        mock_redis.get.return_value = "0"

        result = await cache_with_mock_redis.get("test", "key")

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_false_value(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试获取 False 值"""
        mock_redis.get.return_value = "false"

        result = await cache_with_mock_redis.get("test", "key")

        assert result is False

    @pytest.mark.asyncio
    async def test_set_none_data(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """测试设置 None 数据"""
        mock_redis.setex.return_value = True

        result = await cache_with_mock_redis.set("test", None, "key")

        assert result is True
        # 验证 None 被序列化为 "null"
        call_args = mock_redis.setex.call_args
        assert call_args[0][2] == "null"

    @pytest.mark.asyncio
    async def test_build_key_with_special_characters(self, cache_service: CacheService):
        """测试包含特殊字符的键构建"""
        key = cache_service._build_key("test", "key-with-dash", "key_with_underscore")
        assert key == "cache:test:key-with-dash:key_with_underscore"

    @pytest.mark.asyncio
    async def test_concurrent_access_simulation(
        self, cache_with_mock_redis: CacheService, mock_redis: AsyncMock
    ):
        """模拟并发访问场景"""
        mock_redis.get.return_value = json.dumps({"data": "test"})
        mock_redis.setex.return_value = True

        # 模拟多个并发请求
        tasks = [
            cache_with_mock_redis.get("customer_list", "page_1"),
            cache_with_mock_redis.get("customer_list", "page_2"),
            cache_with_mock_redis.set("customer_detail", {"id": 1}, 1),
            cache_with_mock_redis.delete("customer_list", "page_1"),
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 4
        assert results[0] == {"data": "test"}
        assert results[1] == {"data": "test"}
        assert results[2] is True
        assert results[3] is True


if __name__ == "__main__":
    pytest.main(["-v", __file__])
