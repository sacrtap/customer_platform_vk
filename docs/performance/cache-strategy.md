# 缓存策略文档

**最后更新**: 2026-07-20
**适用范围**: 后端服务层与 API 路由

---

## 一、架构概述

### 缓存技术栈
- **缓存引擎**: Redis 7.x
- **客户端**: `redis.asyncio`（异步）
- **封装层**: `backend/app/cache/base.py` → `CacheService` 单例
- **权限缓存**: `backend/app/cache/permissions.py` → `PermissionCache` 单例

### 缓存服务核心 API

| 方法 | 说明 | 示例 |
|------|------|------|
| `get(prefix, *parts)` | 读取缓存 | `await cache_service.get("customer_list", page, pageSize)` |
| `set(prefix, data, *parts, ttl=None)` | 写入缓存 | `await cache_service.set("customer_list", data, page, pageSize, ttl=600)` |
| `delete(prefix, *parts)` | 删除单个缓存 | `await cache_service.delete("customer_detail", customer_id)` |
| `invalidate_pattern(pattern)` | 批量删除匹配缓存 | `await cache_service.invalidate_pattern("cache:customer_list:*")` |
| `invalidate_customer_cache(customer_id)` | 清除客户相关缓存 | 清除客户详情 + 列表缓存 |
| `invalidate_tag_cache()` | 清除标签缓存 | 清除 tag_list + tag_stats |
| `invalidate_analytics_cache(category)` | 清除分析缓存 | category 可选: dashboard/health/profile 等 |
| `invalidate_billing_cache()` | 清除结算缓存 | 清除 billing_* + analytics_* |

### 缓存键命名规范

```
cache:{prefix}:{part1}:{part2}:...
```

**示例**:
- `cache:customer_list:1:20` — 第1页，每页20条
- `cache:customer_detail:42` — 客户ID=42的详情
- `cache:analytics_dashboard_stats:2026-07-20` — 按日期分区的仪表盘统计
- `cache:permissions:5` — 用户ID=5的权限列表

---

## 二、TTL 配置表

### 核心配置（`config.py` 环境变量可覆盖）

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `cache_ttl_dashboard_stats` | `CACHE_TTL_DASHBOARD_STATS` | 300s (5min) | 仪表盘统计数据 |
| `cache_ttl_dashboard_chart` | `CACHE_TTL_DASHBOARD_CHART` | 900s (15min) | 仪表盘图表数据 |
| `cache_ttl_analytics_health` | `CACHE_TTL_ANALYTICS_HEALTH` | 600s (10min) | 健康度分析 |
| `cache_ttl_analytics_profile` | `CACHE_TTL_ANALYTICS_PROFILE` | 3600s (1h) | 画像分析 |
| `cache_ttl_analytics_invoice` | `CACHE_TTL_ANALYTICS_INVOICE` | 300s (5min) | 结算单分析 |
| `cache_ttl_analytics_warning` | `CACHE_TTL_ANALYTICS_WARNING` | 180s (3min) | 预警数据 |
| `cache_ttl_analytics_prediction` | `CACHE_TTL_ANALYTICS_PREDICTION` | 1800s (30min) | 预测数据 |
| `cache_ttl_pricing_rules` | `CACHE_TTL_PRICING_RULES` | 3600s (1h) | 定价规则 |
| `cache_ttl_analytics_trend` | `CACHE_TTL_ANALYTICS_TREND` | 900s (15min) | 趋势数据 |

### 代码内 TTL 配置（`cache/base.py` `_ttl_config`）

| Prefix | TTL | 说明 |
|--------|-----|------|
| `customer_list` | 600s (10min) | 客户列表 |
| `customer_detail` | 600s (10min) | 客户详情 |
| `tag_list` | 3600s (1h) | 标签列表 |
| `tag_stats` | 1800s (30min) | 标签统计 |
| `analytics` | 900s (15min) | 通用分析 |
| `analytics_dashboard_stats` | 300s (5min) | 仪表盘统计 |
| `analytics_dashboard_chart` | 900s (15min) | 仪表盘图表 |
| `analytics_health_stats` | 600s (10min) | 健康度统计 |
| `analytics_health_warning` | 180s (3min) | 健康预警 |
| `analytics_health_inactive` | 600s (10min) | 不活跃客户 |
| `analytics_profile` | 3600s (1h) | 画像分析 |
| `analytics_invoice_status` | 300s (5min) | 结算单状态 |
| `analytics_consumption_trend` | 900s (15min) | 消耗趋势 |
| `analytics_top_customers` | 900s (15min) | Top 客户 |
| `analytics_device_distribution` | 900s (15min) | 设备分布 |
| `analytics_payment_analysis` | 600s (10min) | 回款分析 |
| `analytics_prediction` | 1800s (30min) | 预测数据 |
| `billing_pricing_rules` | 3600s (1h) | 定价规则 |
| `permissions` | 600s (10min) | 用户权限 |
| `default` | 300s (5min) | 默认 TTL |

---

## 三、缓存使用模式

### 标准缓存模式（Cache-Aside）

```python
from ..cache.base import cache_service

async def get_data(request: Request):
    # 1. 构建缓存键
    cache_key = f"metric:{param1}:{param2}"

    # 2. 尝试读取缓存
    cached = await cache_service.get("analytics_prefix", cache_key)
    if cached is not None:
        return json(cached)

    # 3. 缓存未命中，查询数据库
    service = MyService(request.ctx.db_session)
    data = await service.get_data(param1, param2)

    result = {"code": 0, "message": "success", "data": data}

    # 4. 写入缓存
    await cache_service.set("analytics_prefix", result, cache_key, ttl=300)

    return json(result)
```

### 支持 force_refresh 的模式

```python
async def get_data(request: Request):
    force_refresh = request.args.get("force_refresh", "").lower() == "true"

    cached = await cache_service.get("prefix", cache_key) if not force_refresh else None
    if cached is not None:
        return json(cached)

    # ... 查询数据 ...

    if not force_refresh:
        await cache_service.set("prefix", result, cache_key, ttl=300)

    return json(result)
```

### 按时间分区的缓存模式

```python
# 适用于按小时粒度缓存的统计数据
hour_bucket = int(time.time() // 3600)
cached_key = f"industry:{hour_bucket}"

cached = await cache_service.get("analytics_profile", cached_key)
```

---

## 四、缓存失效策略

### 主动失效场景

| 业务操作 | 失效范围 | 方法 |
|----------|----------|------|
| 创建/更新/删除客户 | `customer_list:*` + `customer_detail:{id}` | `invalidate_customer_cache(id)` |
| 创建/更新/删除标签 | `tag_list:*` + `tag_stats:*` | `invalidate_tag_cache()` |
| 生成/支付结算单 | `billing_*` + `analytics_*` | `invalidate_billing_cache()` |
| 更新定价规则 | `billing_pricing_rules:*` | `invalidate_billing_cache()` |
| 用户角色变更 | `permissions:{user_id}` | `permission_cache.invalidate(user_id)` |

### 被动失效（TTL 过期）

所有缓存均设置 TTL，过期后自动删除。无需手动管理。

### 全量缓存清理

```python
# 清除所有分析缓存
await cache_service.invalidate_analytics_cache()

# 清除特定类别的分析缓存
await cache_service.invalidate_analytics_cache("dashboard")
await cache_service.invalidate_analytics_cache("health")
```

---

## 五、最佳实践

### ✅ 应该做的

1. **为高频读取、低频变更的数据添加缓存** — 仪表盘统计、列表查询、分析报表
2. **使用合理的 TTL** — 数据变更频率越低，TTL 可以越长
3. **在数据变更时主动失效缓存** — 避免脏数据
4. **缓存键包含查询参数** — 不同参数的查询结果不应共享缓存
5. **使用 force_refresh 参数** — 允许用户手动刷新数据
6. **序列化时使用 `default=str`** — 处理 datetime 等不可直接 JSON 序列化的类型

### ❌ 不应该做的

1. **不要缓存用户敏感数据** — 密码、token 等
2. **不要缓存实时性要求极高的数据** — 如余额扣款后的实时余额
3. **不要使用过长的 TTL** — 超过 1 小时的缓存需要评估数据一致性风险
4. **不要在缓存键中包含用户 session 信息** — 会导致缓存命中率下降
5. **不要忽略缓存写入失败** — 虽然有 try/except，但应关注日志中的警告

---

## 六、监控建议

### 关键指标

| 指标 | 获取方式 | 告警阈值 |
|------|----------|----------|
| 缓存命中率 | Redis INFO stats (keyspace_hits / (keyspace_hits + keyspace_misses)) | < 80% |
| 缓存内存使用 | Redis INFO memory (used_memory_human) | > 80% maxmemory |
| 缓存键总数 | Redis DBSIZE | 异常增长 |
| 慢查询 | Redis SLOWLOG GET | > 10ms |

### 日志关键字

- `缓存读取失败` — Redis 连接问题
- `缓存写入失败` — Redis 连接或内存问题
- `已清除 N 个匹配` — 缓存失效操作
- `获取用户权限缓存失败` — 权限缓存异常

---

## 七、相关文件

| 文件 | 说明 |
|------|------|
| `backend/app/cache/base.py` | CacheService 核心实现 |
| `backend/app/cache/permissions.py` | PermissionCache 权限缓存 |
| `backend/app/cache/__init__.py` | 缓存模块导出 |
| `backend/app/config.py` | TTL 环境变量配置 |
| `docs/performance/redis-cache-analysis.md` | 缓存优化分析报告 |
