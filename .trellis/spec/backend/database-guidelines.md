# Database Guidelines

> ORM patterns, queries, and migrations for the backend.

---

## Overview

The project uses **SQLAlchemy async** with `AsyncSession`. Database sessions are created per-request by middleware and attached to `request.ctx.db_session`.

---

## Session Management

[来源: 项目源码 — `backend/app/main.py:71-81`]

Sessions are created and closed by middleware:

```python
@app.middleware("request")
async def db_session_middleware(request):
    request.ctx.db_session = async_session_maker()

@app.middleware("response")
async def close_db_session(request, response):
    if hasattr(request.ctx, "db_session"):
        await request.ctx.db_session.close()
```

**In routes**: Always get the session from `request.ctx.db_session`:

```python
db_session: AsyncSession = request.ctx.db_session
service = CustomerService(db_session)
```

---

## Model Pattern

[来源: 项目源码 — `backend/app/models/base.py`, `backend/app/models/customers.py`]

Models inherit from `BaseModel` (defined in `models/base.py`) which provides `id`, `created_at`, `updated_at`, and `deleted_at` (soft delete).

- **Soft delete**: queries filter `deleted_at.is_(None)` — never use raw `DELETE` in production code
- **Timestamps**: `created_at` / `updated_at` auto-managed by SQLAlchemy
- **Relationships**: Use `relationship()` with `selectinload` for eager loading when needed

---

## Query Patterns

### Simple query by ID

[来源: 项目源码 — `backend/app/routes/customers.py:119`]

```python
db_session: AsyncSession = request.ctx.db_session
service = CustomerService(db_session)
customer = await service.get_customer_by_id(customer_id)
```

### Direct query in route (for simple lookups)

[来源: 项目源码 — `backend/app/routes/customers.py:138-150`]

```python
from sqlalchemy import select, func as sa_func
from ..models.daily_consumption import DailyConsumption

usage_stmt = (
    select(
        DailyConsumption.customer_id,
        sa_func.coalesce(sa_func.sum(DailyConsumption.order_count), 0).label("order_count"),
    )
    .where(
        DailyConsumption.customer_id.in_(customer_ids),
        DailyConsumption.consumption_date >= thirty_days_ago,
    )
    .group_by(DailyConsumption.customer_id)
)
usage_result = await db_session.execute(usage_stmt)
```

### Repository pattern (billing domain)

[来源: 项目源码 — `backend/app/routes/billing/invoices.py:28-29`]

```python
from ...repository import InvoiceRepository, PricingRepository
from ...services.billing import InvoiceService

db: AsyncSession = request.ctx.db_session
invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))
```

---

## Migration Pattern

Migrations use **Alembic**. Migration files live in `backend/alembic/versions/`.

> **Important**: Do NOT use `backend/migrations/versions/` — that directory caused dirty `alembic_version` data in the past. The correct migration directory is `backend/alembic/versions/`.

[来源: 项目记忆 — alembic_version 脏数据事件]

---

## Cache Invalidation

After any data mutation, invalidate the relevant cache:

[来源: 项目源码 — `backend/app/routes/customers.py:379`]

```python
# After create
await cache_service.invalidate_customer_cache()

# After update/delete specific record
await cache_service.invalidate_customer_cache(customer_id)

# After billing changes
await cache_service.invalidate_billing_cache()
```

---

## TTL 配置单一真相

[来源: Bug fix 2026-09-17 — `_ttl_config` 存在 5 个零消费/谎值条目；`analytics.py` 9 处与 `billing/balances.py` 1 处硬编码 TTL 副本]

### 1. 契约（唯一读取入口）

`CacheService._ttl_config`（`backend/app/cache/base.py`）是 TTL 的**唯一真实来源**；
唯一读取入口是 `ttl_for()`：

```python
def ttl_for(self, prefix: str) -> int:
    """返回指定缓存前缀的 TTL（秒）；未配置时回退 default。"""
    return self._ttl_config.get(prefix, self._ttl_config["default"])
```

`CacheService.set(prefix, data, *parts, ttl=None)` 的解析顺序：

```python
expire = ttl or self.ttl_for(prefix)   # 显式 ttl 优先；None 才读配置
```

### 2. 规则

1. **新增缓存前缀前，先在 `_ttl_config` 登记**；写缓存时不传 `ttl=`，由 `ttl_for()` 取值。
2. **禁止在调用点硬编码 TTL 副本**（如 `pipe.setex(key, 300, val)`）—— 那是「同一语义两个副本」，
   改配置不会传播。**手工拼键的批量读写同样适用**。
3. **配置条目必须是真值且有真实消费点**：某 key 在生产代码中从不被读取，或值与实际生效值不符，
   即「谎值」。同类条目已于 2026-09-17 清除（`billing_pricing_rules`、`tag_stats`、`analytics`、
   以及 `analytics_profile`(3600→300)、`analytics_prediction`(1800→300) 两个与实际不符的值）。
4. **同一前缀不得承载两个 TTL 语义** —— 需要不同 TTL 时**拆前缀**
   （如 `analytics_prediction`(300s) 与 `analytics_prediction_forecast`(1800s)）。
5. 显式 `ttl=` 仅用于调用点确有独立语义的场景，且该前缀不应再在 `_ttl_config` 登记冲突值。

### 3. 失效联动

新增或拆分前缀后，必须确认失效模式覆盖它。既有模式为通配前缀：

| 方法 | 失效模式 |
|---|---|
| `invalidate_customer_cache()` | `cache:customer_list:*`、`cache:customer_detail:{id}` |
| `invalidate_tag_cache()` | `cache:tag_list:*`、`cache:tag_stats:*` |
| `invalidate_analytics_cache(category)` | `cache:analytics_{category}_*`；category 为空时 `cache:analytics_*` + `cache:billing_*` |
| `invalidate_billing_cache()` | `cache:billing_*`、`cache:analytics_*` |

> **Gotcha**: 失效模式是**前缀通配**，因此拆前缀通常无需改失效代码；但若新前缀不以既有通配开头
> （如不是 `cache:analytics_*`），则必须显式补失效调用，否则该缓存永不过期/永不失效。

### 4. Tests Required

- `tests/test_cache.py::TestTTLConfiguration` —— 断言 `set()` 对**已登记**前缀取配置值、
  对未知前缀回退 `default`、显式 `ttl=` 覆盖配置
- 断言点：`mock_redis.setex.call_args[0][1]`（TTL 实参）

> 不要断言整个 `_ttl_config` 字典 —— 那是实现钉死型断言，配置合法的数值调整都会误报失败。

### 5. Wrong vs Correct

```python
# WRONG —— 硬编码副本：改 _ttl_config 不生效，且同一前缀可长出第二个值
await cache_service.set("analytics_profile", result, key, ttl=300)
pipe.setex(key, 300, val)

# CORRECT —— 单一来源
await cache_service.set("analytics_profile", result, key)   # 取 ttl_for("analytics_profile")
ttl = cache_service.ttl_for("billing_consumption")           # 手工拼键时显式取
pipe.setex(key, ttl, val)
```

**相关**: `docs/performance/cache-strategy.md`（TTL 条目全表与「不在本表中的 TTL」）

---

## Redis Hash Key Encoding

[来源: Bug fix 2026-09-16 — `SyncTaskService.get_progress` 在真实 Redis 路径下所有字段静默取默认值]

`CacheService._get_redis()` 固定以 `decode_responses=True` 创建客户端（`backend/app/cache/base.py`）：

```python
redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
```

因此 `hgetall()` 返回的 dict **键是 `str`、值也是 `str`**。读取时必须用 **str 键**：

```python
# WRONG — 键不匹配，静默返回 None → 所有字段取默认值（不抛异常，最难排查）
data = await redis.hgetall(key)
status = data.get(b"status", "")      # 永远拿不到真实值

# CORRECT — str 键，与 decode_responses=True 一致
status = data.get("status", "")

# 需要兼容两种客户端配置时，显式回退
def raw(name: str):
    return data.get(name, data.get(name.encode()))
```

> **Warning**: 键不匹配**不会抛异常**，只会静默取默认值。若读取端为字段设了默认值（如 `""`、`0`），故障表现是「数据恒为空」而非报错 —— 这类问题只能靠回归测试（如 `tests/services/test_sync_task_service.py::TestGetProgress::test_get_progress_from_redis_str_keys`）守住。

---

## AsyncSession Concurrency Constraint

**CRITICAL**: `AsyncSession` does NOT support concurrent `execute()` calls on the same session instance.

- ❌ **Never use `asyncio.gather()` with multiple `session.execute()` calls on the same session**
- ✅ **Use sequential `await` calls** when querying multiple statements on the same session
- ✅ **If true parallelism is needed**, create separate sessions per query

```python
# WRONG — will raise InvalidRequestError
results = await asyncio.gather(
    session.execute(stmt1),
    session.execute(stmt2),
)

# CORRECT — sequential execution on the same session
result1 = await session.execute(stmt1)
result2 = await session.execute(stmt2)
```

[来源: Bug fix 2026-09-12 — KPI `get_kpi_stats` asyncio.gather caused 500 error]

---

## "Impossible" WHERE Conditions

When you need a WHERE clause that matches zero rows (e.g., user has no ID for "my customers" filter):

- ❌ **Never pass Python `False` to `.where()`** — SQLAlchemy raises `ArgumentError`
- ❌ **Never use `sqlalchemy.literal(False)`** — can cause type issues on some databases
- ✅ **Use an always-false column comparison** like `.where(Model.id < 0)`

```python
# WRONG — raises ArgumentError
stmt = stmt.where(False)

# CORRECT — always false, returns 0 rows
stmt = stmt.where(Customer.id < 0)
```

[来源: Bug fix 2026-09-12 — KPI `get_kpi_stats` `where(False)` caused 500 error]

---

## 关系属性序列化必须预加载

[来源: Bug fix 2026-09-16 — `GET /billing/invoices/detail-logs` 在真实请求下返回 500]

异步会话下访问**未加载**的 `relationship` 属性会触发隐式懒加载；懒加载需要同步 IO，
在 `AsyncSession` 中直接抛 `MissingGreenlet` → 端点 500。

`Invoice.customer = relationship("Customer")` **未**配置 `lazy="selectin"`（对比同一文件里
`PricingRule.customer` 配了 `lazy="selectin"`），因此凡是在**序列化阶段**读 `inv.customer.name`
的查询，都必须在查询处显式预加载：

```python
# WRONG — 序列化时读 inv.customer.name 触发懒加载 → MissingGreenlet → HTTP 500
stmt = select(Invoice).where(Invoice.detail_file_status != "pending")
...
"customer_name": inv.customer.name if inv.customer else None,

# CORRECT — 在同一个查询上显式预加载
from sqlalchemy.orm import selectinload

stmt = (
    select(Invoice)
    .options(selectinload(Invoice.customer))
    .where(Invoice.detail_file_status != "pending")
)
```

> **Warning**: 这类缺陷**只在真实请求路径下暴露**。若测试或调试时关系已被装入实例（或提前访问过），
> 就不会触发懒加载，`MissingGreenlet` 被掩盖。审查口诀：序列化函数里出现
> `obj.<relationship>.<field>`，同一查询就必须有对应的 `selectinload`。

---

## 可空布尔筛选的 NULL 语义（是否结算/是否停用）

[来源: 2026-09-20 — 客户筛选新增 `is_settlement_enabled` / `is_disabled`]

客户表两个可空布尔字段，NULL 语义**必须按「模型默认值」补齐**，且两个字段处理**不对称**：

| 字段 | 模型默认 | NULL 含义 | 筛选「是」 | 筛选「否」 |
|---|---|---|---|---|
| `is_settlement_enabled` | `True` | 结算中 | `or_(is_(True), is_(None))` | `is_(False)` |
| `is_disabled` | `False` | 未停用 | `is_(True)` | `or_(is_(False), is_(None))` |

```python
# 是否结算：NULL = 结算中 → 筛「是」兼容 NULL，筛「否」严格 false
if (is_settlement_enabled := filters.get("is_settlement_enabled")) is not None:
    if is_settlement_enabled:
        conditions.append(or_(Customer.is_settlement_enabled.is_(True), Customer.is_settlement_enabled.is_(None)))
    else:
        conditions.append(Customer.is_settlement_enabled.is_(False))

# 是否停用：NULL = 未停用 → 筛「否」兼容 NULL，筛「是」严格 true
if (is_disabled := filters.get("is_disabled")) is not None:
    if is_disabled:
        conditions.append(Customer.is_disabled.is_(True))
    else:
        conditions.append(or_(Customer.is_disabled.is_(False), Customer.is_disabled.is_(None)))
```

> **Warning**: 迁移里这两个字段都是 `nullable=True` 且无 server_default（见 `05c6bedcf166_initial_schema.py`），历史行可能为 NULL。若不做 NULL 兼容，筛选结果会漏掉历史数据。
>
> 对比：`is_key_customer` / `is_real_estate` 后端既有实现是 `== value` 比较，NULL 行恒不匹配（SQL 三值逻辑），这是既有行为，未改。新增布尔筛选时先查字段默认值与迁移历史，再决定哪一侧兼容 NULL。

**Python 侧实体判断同样用恒等**：读取已加载实体判断「是否结算」用 `customer.is_settlement_enabled is False`
（None=结算中，不排除）；`not customer.is_settlement_enabled` 会把 None 也排除，语义错误。

---

## select(实体) 结果必须用 `.scalars()` 取实体，`.first()` 恒 KeyError

[来源: Bug fix 2026-09-20 — `get_customer_health_score` 对正常客户恒 500 `KeyError: 'tiers'`（既有 bug，旧代码同错，行号差 22 = 插入行数）]

SQLAlchemy 2.0 中 `select(SomeEntity)` 的 `.execute()` 结果 `.first()` 返回的是 `Row`，
该 Row 的键是**实体名**（如 `['PricingRule']`），**不是**展开的列名。
因此 `row.tiers` 访问恒抛 `KeyError: 'tiers'`（经 `Row.__getattr__` 包装为 AttributeError）。

```python
# WRONG — select(实体) 后 .first() 取 Row，row.tiers 恒 KeyError → 500
pricing_result = (await self.db.execute(pricing_stmt)).first()
if pricing_result and pricing_result.tiers:   # AttributeError: tiers

# CORRECT — .scalars().first() 取实体实例，属性访问安全
pricing_result = (await self.db.execute(pricing_stmt)).scalars().first()
if pricing_result and pricing_result.tiers:
```

> **Warning**: 这类缺陷**在 mock 单测下被掩盖**——`MagicMock().first()` 返回任意对象，
> 属性访问不会报错；只有真实查询路径（`.first()` 返回真实 `Row`）才暴露，
> 且只在「有实体记录命中」时触发（无记录返回 None 直接短路）。
> 审查口诀：`select(Model)` 的 execute 结果需要访问列/属性时，**必须** `.scalars().first()`
> （实体查询）或 `select(Model.col1, Model.col2)` 显式选列（列查询）。
> 聚合查询（`select(func.sum(...).label("x"))`）的 Row 键是 label 名，`.first()` 后 `row.x` 是安全的。

---

## Forbidden Patterns

- ❌ **Raw `DELETE` statements in production** — use soft delete (`deleted_at = datetime.now()`)
- ❌ **Creating sessions with `async_session_maker()` in routes** — always use `request.ctx.db_session`
- ❌ **Committing in routes without understanding service commit behavior** — some services commit internally (e.g., `CustomerService.create_customer`), some expect the caller to commit
- ❌ **Forgetting to close sessions** — the middleware handles this; do not create sessions outside the middleware pattern
- ❌ **`asyncio.gather()` with multiple `session.execute()` on the same AsyncSession** — see AsyncSession Concurrency Constraint above
- ❌ **Passing Python `False` or `True` to `.where()`** — see "Impossible" WHERE Conditions above
