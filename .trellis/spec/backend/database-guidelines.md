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

## PG 会话时区契约（naive 时间列的墙钟基准）

[来源: 2026-10-26 `created_at` 时区锁定修复；`backend/app/main.py:192`、`backend/app/models/base.py:16`]

### 契约

**所有 PG 会话时区必须锁定为 `Asia/Shanghai`。** 引擎创建处统一带：

```python
create_async_engine(
    url,
    connect_args={"server_settings": {"TimeZone": "Asia/Shanghai"}},
)
```

同步引擎（psycopg2）不认 `server_settings`，须用 libpq 的 `options`：

```python
create_engine(url, connect_args={"options": "-c timezone=Asia/Shanghai"})
```

### 为什么必须锁

`TimestampMixin.created_at` / `updated_at` 是 `DateTime`（无 `timezone=True`）
→ PG `timestamp without time zone`，由 `server_default=func.now()` 在
**会话时区**写墙钟。不锁定时，会话时区跟随 PG 服务端 / 容器 `TZ`：

| 环境 | 会话时区 | naive 列写入 | 读出口 `naive_cst_datetime_str()` |
|---|---|---|---|
| 本地（PG 服务端 CST） | Asia/Shanghai | CST 墙钟 ✓ | 正确 |
| staging（容器 TZ=UTC） | UTC | UTC 墙钟 ✗ | 把 UTC 墙钟当 CST → **少 8 小时** |

timestamptz 列（`completed_at` 等）存绝对 UTC 时刻，不受会话时区影响。

### Python 侧取值规则（与列类型严格对应）

| 场景 | 用法 | 反例 |
|---|---|---|
| 与 naive 列比较 / 阈值 | `cst_now().replace(tzinfo=None)` | `datetime.now()`（跟随进程 TZ） |
| 写 timestamptz 列 | `datetime.now(timezone.utc)` | `datetime.now()`（naive 会被按会话时区解释） |
| 业务自然日 | `cst_today()` | `date.today()` / `datetime.utcnow().date()` |

aware 与 naive **不可混算**：`cst_now() - task.created_at` 会抛
`TypeError: can't subtract offset-naive and offset-aware datetimes`
（2026-10-26 修复时踩过，见 `recover_stuck_tasks`）。

### 新增引擎时的 Checklist

- [ ] 是否与 PG 交互？是 → 按驱动加 `server_settings` / `options`
- [ ] 测试引擎必须与生产一致，否则「测试通过但生产偏差」
- [ ] 若该环境 PG 服务端时区非 CST，必须锁定（不能依赖服务端默认值）

### 测试如何证伪（本地无法靠「移除锁定」测出来）

本地 PG 服务端恰好是 `Asia/Shanghai`，无锁定的连接也返回 CST，
所以「移除 `connect_args` 后测试失败」在本地**不成立**。
真正能证伪的做法是连到**服务端时区为 UTC 的库**：

```sql
ALTER DATABASE <probe_db> SET timezone TO 'UTC';
```

参照 `backend/tests/integration/test_sync_task_timezone.py::test_lock_overrides_utc_server_timezone`。

### 已知边界

1. **容器 tzdata**：`deploy/docker/Containerfile` 基于 `python:3.12-slim` 未装
   tzdata，`time.tzset()` 解析 `Asia/Shanghai` 会静默回退 UTC
   （`main.py:_force_cst_timezone()` 有 `tm_gmtoff` 告警兜底）。此时
   `datetime.now()` 退化，故 Python 侧一律用显式工具函数，不依赖进程 TZ。
2. **naive datetime 写 timestamptz 列**会被解释为「会话时区的该墙钟」。
   锁定时区后写 aware UTC 才是等价修复；顺序不能反（先锁时区，再统一口径）。

---

## Model Pattern

[来源: 项目源码 — `backend/app/models/base.py`, `backend/app/models/customers.py`；2026-09-21 全量迁移至 SQLAlchemy 2.0 typed 声明]

Models inherit from `BaseModel` (defined in `models/base.py`) which provides `id`, `created_at`, `updated_at`, and `deleted_at` (soft delete).

- **Soft delete**: queries filter `deleted_at.is_(None)` — never use raw `DELETE` in production code
- **Timestamps**: `created_at` / `updated_at` auto-managed by SQLAlchemy
- **Relationships**: Use `relationship()` with `selectinload` for eager loading when needed

### 字段必须使用 2.0 typed 声明（`Mapped[...] = mapped_column(...)`）

[来源: 2026-09-21 类型治理 — 16 个模型文件的 `Column(...)` 全量迁移，pyright 门禁基线 0 error]

`x = Column(...)` 会让 pyright 把**实例属性**推断为 `Column[T]`（而非 `T`），在全库引发大量类型错误。
所有 ORM 字段必须写成 `x: Mapped[T] = mapped_column(...)`：

```python
# WRONG — pyright 推断 customer.name 的类型是 Column[str]
name = Column(String(100), nullable=False)

# CORRECT — pyright 推断为 str
name: Mapped[str] = mapped_column(String(100), nullable=False)
```

**注解可选性必须与列 nullable 一致**（SQLAlchemy 在映射配置期校验，不一致直接报 `InvalidRequestError`）：

| 列定义 | 注解 |
|---|---|
| `nullable=False` 或 `primary_key=True` | `Mapped[T]` |
| `nullable=True` 或**未写 nullable**（默认可空） | `Mapped[T \| None]` |
| JSON/JSONB 列 | `Mapped[Any]` |

- **仅写 `default=` 不构成非空**：`Column(Integer, default=0)` 默认可空 → `Mapped[int | None]`，业务代码需 `or 0` 防护
- **`relationship` 保持原样**（不加 `Mapped[...]` 注解）
- **core `Table()` 关联表仍用 `Column(...)`**（非 ORM 实例属性，不受影响）
- 本地校验：`cd backend && pyright`（配置 `backend/pyrightconfig.json`，范围 `app/`）

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

## JSON 列不能出现在 GROUP BY / DISTINCT

[来源: 2026-10-14 — 包年套餐余额查询（`balances.py::_build_package_remaining_cte`）]

PostgreSQL 的 `json` 类型**没有相等操作符**，因此把 JSON 列放进 `GROUP BY` / `DISTINCT`
会直接报错（`could not identify an equality operator for type json`）。`JSONB` 有相等操作符，
但项目多数 JSON 列声明为 `json`，不能假设。

典型症状：想「按客户聚合套餐规则」时写出 `group_by(PricingRule.customer_id, PricingRule.package_limits)`
→ 运行期炸；单测用 `MagicMock` 时不会暴露（不经过真实 SQL）。

```python
# WRONG — package_limits 是 json 列，GROUP BY 报错
stmt = (
    select(PricingRule.customer_id, func.sum(...))
    .group_by(PricingRule.customer_id, PricingRule.package_limits)
)

# CORRECT — 需要跨行去重的 JSON 值，改用关联标量子查询，不把 JSON 列拖进 GROUP BY
consumed_subq = (
    select(func.coalesce(func.sum(DailyConsumption.total_cost), 0))
    .where(
        DailyConsumption.pricing_rule_id == PricingRule.id,
        DailyConsumption.deleted_at.is_(None),
    )
    .correlate(PricingRule)
    .scalar_subquery()
)
# 需要「每客户最新一条」时用窗口函数 row_number() OVER (PARTITION BY ...)，而非 GROUP BY
```

> **验证手法**：涉及 JSON 列的聚合/去重 SQL 必须跑到真实 DB（集成测试或本地库冒烟），
> 纯 `MagicMock` 单测无法暴露此类数据库方言错误。

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

## 可空布尔筛选的 NULL 语义（自动发起结算）

[来源: 2026-09-29 — 客户新增 `auto_initiate_settlement`（默认是）]

| 字段 | 模型默认 | NULL 含义 | 筛选「是」 | 筛选「否」 |
|---|---|---|---|---|
| `auto_initiate_settlement` | `True` | 自动发起 | `or_(is_(True), is_(None))` | `is_(False)` |

与 `is_settlement_enabled` 同侧兼容（默认 True 的字段筛「是」兼容 NULL，筛「否」严格 false）；
新增这类「默认是」布尔字段时直接复制该模式，不要在 SQL 里用 `== value`（NULL 行恒不匹配）。

前端表单回填同样用 `?? true` 补齐（`EditCustomerDialog` / `useCustomerDetail` 的
`is_settlement_enabled ?? true` 同款），展示层 NULL 视为「是」（`CustomerBasicTab`）。

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

## 模型新增字段 → 迁移必须应用到运行环境（Schema Drift）

[来源: Bug fix 2026-10-13 — `GET /api/v1/customers` 恒 500 `column customers.balance_warning_level does not exist`]

**症状**：ORM 声明了数据库里不存在的列。查询该实体（`select(Customer)`）在 `.execute()` 时抛
`asyncpg.exceptions.UndefinedColumnError` → `ProgrammingError` → 端点 500，且**所有**触及该实体的
查询（列表/详情/KPI/导出/定时任务）全部失败，而非单点故障。

**根因**：模型改了、迁移也写了，但**迁移没有应用到运行中的数据库**。
`005e5b7` 同时提交了 `Customer.balance_warning_level` 字段与迁移 `w2x3y4z5a6b7`，
但本地/运行环境仍停在 `v1w2x3y4z5a6`，两边脱节。

### Checklist: 修改 ORM 模型字段后（缺一不可）

- [ ] 1. 模型加字段（`Mapped[...] = mapped_column(...)`，注解可空性与列 nullable 一致）
- [ ] 2. 写 Alembic 迁移（`backend/alembic/versions/`）
- [ ] 3. **把迁移应用到运行环境**：`cd backend && python -m alembic upgrade head`
- [ ] 4. **验证无漂移**：`cd backend && python scripts/check_schema_drift.py`（应对齐；缺失会 `❌ FAILED`）
- [ ] 5. 确认本地/测试/预发/生产**各环境**都执行了第 3 步（CI 的 `upgrade head` 只管 CI 库）

> **关键区别于既有 spec**：第 2 步（写迁移）是必要不充分条件。本 bug 证明「有迁移文件」不等于
> 「数据库已升级」——漏掉第 3 步时，**CI 全绿、单测全绿**，只有真实请求路径 500。

> **复发记录（2026-10-13，同一类第二次）**：`balance_whitelists.remark`（迁移 `x3y4z5a6b7c8`）
> 同样只写了迁移、未 `alembic upgrade head`，启动时报「运行库迁移版本落后」（`main.py` 启动校验）。
> 两次的共同点：**改动者跑完测试（全绿）就认为完事**，因为没有任何一步要求「把迁移应用到运行库」。
> 已把该步写入两处主动执行的清单：`.trellis/spec/backend/index.md` Quality Check 第 8 条、
> `trellis-check` skill Step 3。核心口诀：**「写了迁移」≠「升了库」；测试全绿 ≠ 运行库已升级。**

### 为什么 CI 与单测都漏掉了它

| 层 | 为何漏 | 佐证 |
|---|---|---|
| 单测 | `MagicMock(spec=Customer)` 只校验**模型**字段，与 DB 无关 | 15 passed |
| 集成/E2E | conftest 用 `BaseModel.metadata.create_all` 建表，**全新库直接按当前模型建全列** | `integration/conftest.py:109`、`e2e/conftest.py:70` |
| conftest 补列 | 手工维护的 `ALTER TABLE ... ADD COLUMN` 列表**按需增补、易滞后**（本 bug 前） | 修复前 `integration/conftest.py` 补的是 `is_real_estate`/`auto_initiate_settlement`，**没有** `balance_warning_*`；**已改为 `sync_test_schema` 自动同步** |
| CI（本 bug 时） | 只跑 `alembic upgrade head`（建库），**没有**比对模型↔库 | 修复后已加 `scripts/check_schema_drift.py` 步骤（见 `.github/workflows/pr-checks.yml`） |

→ 只有当「用 alembic 增量迁移过的库 + 新模型代码」组合时才会炸，恰好是**开发机与生产**的组合。

### 手工补列列表是反模式 → 已改为 metadata 自动同步

`integration/conftest.py` / `e2e/conftest.py` 里逐个字段写 `if "x" not in columns: ALTER TABLE ...`
**无法自动跟进新字段**——每次模型加列都要记得同步这张手写清单，一旦忘记，测试库就与模型脱节，
本 bug 的字段正是漏加的那个（实测：给 `Customer` 加 `balance_warning_level` 后未同步清单，
`tests/integration/test_customers_api.py` 45 个用例全 500）。

**已实施的修复（方案 A：metadata 驱动自动同步）**：
- 新增 `tests/_test_data.py::sync_test_schema(engine)`：以 **SQLAlchemy metadata 为唯一真相**，
  对已存在的表逐列比对，缺失列用 `CreateColumn(column).compile(dialect)` 渲染定义后
  `ALTER TABLE ... ADD COLUMN`。模型加列后**无需再维护任何手写清单**。
- `integration/conftest.py`、`e2e/conftest.py` 的 `sync_test_engine` 在 `create_all` 之后调用它，
  并打印 `🔧 已按模型自动补齐测试库缺失列: [...]`（幂等，无缺失时返回 `[]`）。

> **为何不直接让测试库 `alembic upgrade head`**：本仓测试库常年用 `create_all` 建全新库
> （含 xdist worker 库 `*_gw0`），改用 alembic 增量迁移是更大范围的改动（需处理 worker 库、
> 备份表噪声等）。方案 A 以最小改动消除「手写清单滞后」这一**具体致因**，且不改变
> 「CI 用真实迁移链」这一真正权威的 drift 探测路径（见下）。

### 双层防护：本地测试库自愈 ≠ 放过迁移缺失

自动同步**只作用于本地/测试库**（`create_all` 之后补列），**不会掩盖「漏写迁移文件」**——
CI 用的是 `alembic upgrade head` 建库，与 conftest 无关，两道独立门禁仍会拦截：

| 门禁 | 位置 | 机制 | 拦截对象 |
|---|---|---|---|
| `scripts/check_schema_drift.py` | CI `pr-checks.yml`（upgrade head 后） | 比对运行库 ↔ 模型，库缺列即 `❌ FAILED` | 模型有、迁移链没有的列/表 |
| `TestModelMigrationParity` | `tests/integration/test_migrations.py` | 在**独立库**上 `upgrade head` 后 `compare_metadata` | 同上（单测级，本地即可跑） |

实测：注入一个无迁移的 `customers.phantom_col` 后，两者均正确 FAILED（见下"快速定位命令"）。

### 快速定位命令

```bash
# 运行库的版本 vs 代码里的 head
cd backend && python -m alembic current && python -m alembic heads

# 模型与库是否存在漂移（本 bug 的精确探测手段）
cd backend && python scripts/check_schema_drift.py
#   会自动忽略 22 个遗留对象/索引差异；关注「运行库缺少列/表」的 ❌ FAILED。
#   2026-10-23 起同时比对**可空性**（modify_nullable）：列两侧都存在但 nullable 不一致
#   同样 FAILED——那会让同一条 INSERT 在测试库与生产库行为分叉（见下节）。
#   等价底层手段（噪声较多）：python -m alembic check —— 手工备份表
#   customer_balances_backup_20260812 会报 remove_table，属预期。

# 单测级守护（本地即可跑，用独立库 upgrade head 后比对）
cd backend && pytest tests/integration/test_migrations.py::TestModelMigrationParity -q

# 直接比对该表实际列
python -c "import asyncio,asyncpg; ..."  # information_schema.columns where table_name='customers'
```

---

## 可空性漂移：列存在 ≠ nullable 一致（Schema Drift 第二维）

[来源: 2026-10-23 — `check_schema_drift.py` 增 `modify_nullable` 比对，一次检出 8 处存量漂移]

**症状**：同一条 INSERT 在两侧行为分叉。测试库由 `tests/_test_data.py::sync_test_schema`
按 **metadata** 建表；生产库由**历史迁移链**建。当模型的可空性推断与迁移链不一致时，
测试库里合法的写法在生产库炸（或反之），而两边的测试都可能是绿的。

**根因（两类）**：
1. `Mapped[Any]` 的 JSON 列——SQLAlchemy 对 `Any` 推断 `nullable=False`，
   而初始迁移写的是 `nullable=True`（如 `pricing_rules.tiers`、`audit_logs.changes`）。
2. 注解 `Mapped[int | None]` 但迁移是 `nullable=False`（如 `sync_tasks.success_count`、
   `invoice_discount_histories.invoice_id`）——模型比库宽松。

**修复基准**：**迁移链是唯一事实来源**（`alembic/versions/*.py` 里该列最终的 `nullable=`）。
模型向迁移对齐，不要反过来改库——除非业务确实要改约束（那要先写迁移）。

**已修复的 8 处（2026-10-23）**：
`audit_logs.changes`、`pricing_rules.tiers`、`pricing_rules.package_limits` → 模型加 `nullable=True`；
`invoice_discount_histories.invoice_id`、`sync_tasks.completed_days/skipped_days/success_count/failed_count`
→ 模型加 `nullable=False`。

### Checklist: 新增/修改 JSON 或 int 列时

- [ ] 迁移里的 `nullable=` 与模型注解一致（`Mapped[Any]` 必须显式写 `nullable=True`，别依赖推断）
- [ ] 跑 `python scripts/check_schema_drift.py`，确认「可空性一致」也是 ✅
- [ ] 测试库与生产库的行为分叉问题：优先怀疑可空性/默认值漂移

---

## 列宽漂移：String(N) 长度不足（Schema Drift 第三维）

[来源: 2026-10-24 — 减免审批节点 `pending_discount_approval`（25 字符）写入 `invoices.status VARCHAR(20)`]

**症状**：单元测试全绿（MagicMock 不校验长度），集成/生产环境写入报
`asyncpg.exceptions.StringDataRightTruncationError: value too long for type character varying(20)`
→ 路由 500。`submit_invoice` 设置新状态值时炸，而同一方法的其他分支测试是绿的——
**只有覆盖到新枚举值的那条路径会暴露**。

**根因**：状态/枚举类 String 列加新成员时，先查新值的字符数是否超出现有列宽。
`pending_discount_approval` 25 字符 > `String(20)`。方案文档里写「status 列为 String(20)
无 DB 级枚举约束，无需 DDL 变更」是错误推断——**无枚举约束 ≠ 无长度约束**。

**修复基准**：模型改 `String(30)` + 迁移写 `op.alter_column(..., type_=sa.String(30))`
+ **对运行库与全部测试库执行同一条 ALTER**。`sync_test_schema` 已扩展为
「按 metadata 修正字符串列长度」（`_test_data.py`），新克隆的测试库会自动补齐。

**类型比较的坑（为什么只比长度）**：SQLAlchemy 通用类型表示与 information_schema
返回的方言表示存在别名差异——`str(column.type)` 给 `DATETIME`/`DECIMAL`，
inspector 给 `TIMESTAMP`/`NUMERIC`；连 `compile(dialect=...)` 都统一不了
（`DECIMAL` 编译后仍是 `DECIMAL`，库里是 `NUMERIC`）。逐字/编译后比较会把全库
金额日期列误报为不一致，每次会话触发 20+ 次无谓 ALTER。**只对 `length` 属性
做比较**：长度是无双义表示的维度，足够覆盖列宽变更，且零误报。

### Checklist: 给状态/枚举 String 列加新成员时

- [ ] 数新值的字符数，与列的 `String(N)` 比较；超了必须扩列（模型 + 迁移 + 运行库/测试库）
- [ ] 扩列迁移写 `op.alter_column("table", "col", existing_type=sa.String(旧), type_=sa.String(新), existing_nullable=...)`
- [ ] 迁移已 apply 过的库：直接对运行库执行 ALTER（`alembic` 不会重跑已 apply 的 revision）
- [ ] 测试库由 `sync_test_schema` 自动修正，无需手工 ALTER；验证：临时还原列宽跑一次 sync 应自动修回
- [ ] 集成测试覆盖「写入新枚举值」的路径——单测的 MagicMock 永远测不出长度问题

---

## Forbidden Patterns

- ❌ **Raw `DELETE` statements in production** — use soft delete (`deleted_at = datetime.now()`)
- ❌ **Soft-delete 主记录后以为物理外键 `ondelete="CASCADE"` 会自动清理关联表** — 外键 CASCADE 只在**物理删除主表行**时触发；软删除（置 `deleted_at`）不触发，所有关联表记录会变成孤儿数据。删除业务实体时必须显式级联软删全部关联表，并排查所有 `ForeignKey("xxx.id")` 引用该实体的表（如 `grep -rn "customer_id" models/`）
- ❌ **删除实体时只删直接关联、漏掉经中间键的关联** — 如 `ProfileTag` 经 `profile_id` 关联客户画像，删除客户软删画像后 `profile_tags` 仍残留；删除时需先取中间键（如 `customer.profile.id`）再级联。删除关联表（`customer_tags`/`profile_tags`）≠ 删除定义表（`tags`），标签定义本身应保留
- ❌ **Creating sessions with `async_session_maker()` in routes** — always use `request.ctx.db_session`
- ❌ **Committing in routes without understanding service commit behavior** — some services commit internally (e.g., `CustomerService.create_customer`), some expect the caller to commit
- ❌ **Forgetting to close sessions** — the middleware handles this; do not create sessions outside the middleware pattern
- ❌ **`asyncio.gather()` with multiple `session.execute()` on the same AsyncSession** — see AsyncSession Concurrency Constraint above
- ❌ **Passing Python `False` or `True` to `.where()`** — see "Impossible" WHERE Conditions above
- ❌ **Orphan column: adding ORM fields without applying the migration to the running DB** — 「有迁移文件」≠「库已升级」；改模型后必须 `alembic upgrade head` 并用 `scripts/check_schema_drift.py` 验证，见上方 Schema Drift 一节
- ❌ **给状态/枚举 String 列加新成员不查字符数** — `pending_discount_approval`（25 字符）写进 `VARCHAR(20)` 直接 500；「无枚举约束」≠「无长度约束」。加成员前数长度，超了必须扩列（模型 + 迁移 `alter_column` + 运行库/测试库 ALTER），见「列宽漂移」一节
- ❌ **在 `sync_test_schema` 里做通用类型字符串比较** — SQLAlchemy 与 information_schema 的类型表示有别名差异（DATETIME/TIMESTAMP、DECIMAL/NUMERIC），逐字或编译后比较都会误报，每次会话触发无谓 ALTER；只比较 `length` 属性
- ❌ **Manually maintaining `ALTER TABLE ... ADD COLUMN` lists in test conftest** — 已废止，改用 `tests/_test_data.py::sync_test_schema` 按 metadata 自动同步；新增字段勿再手写清单
- ❌ **把字段校验放在 `setattr` 赋值之后** — 校验抛 `ValueError` 时 ORM 对象已被改脏，而 session 未 rollback，后续任一请求的 flush 会把非法值落库（例：开对账校验放在赋值后，导致「无经理开对账」被 400 拦截后 `require_reconciliation=True` 仍落库）。凡是抛错前不能留脏对象的校验，必须先于赋值；只依赖 `data` 与 `customer` 现值的校验天然可前置
- ❌ **NOT NULL 的 JSON 列不在 ORM 侧给 `default`** — `mapped_column(JSON)` 无默认时，任何未显式传值的构造都会 INSERT NULL 触发 NotNullViolationError；生产路径普遍用 `data.get("tiers")`（API 不带字段即 None），必须靠 ORM `default=list`/`default=dict` 兜底。新增 JSON 列时先确认 NOT NULL 约束与默认值配对
- ❌ **Mock 数据库 helper 只定义 `.all()` 不定义 `.scalars().first()`** — MagicMock 的链式属性自动生成假对象，被测代码读到 MagicMock 属性而不报错，症状是下游 `TypeError: '<' not supported between MagicMock and int`，根因离现场很远。helper 必须显式定义被测代码用到的每条链（`.first()` / `.scalars().first()` / `.scalar()`）
- ❌ **`side_effect` 列表与被测方法的 execute 次数/顺序不匹配** — 服务方法若有「先查客户资格再查数据」的前置 execute，测试列表漏掉第一项会导致整体错位一位：customer_stmt 拿到用量行、pricing_stmt 拿到余额行。症状同样表现为下游字段是 MagicMock。加/改服务层 execute 时必须同步测试列表长度
- ❌ **在会 DROP/重建自身表的操作后用同一 session 写终态** — `pg_restore --clean` 后 `self.db` 的 greenlet 上下文已死，`_finalize` 连环抛 `StaleDataError` → `PendingRollbackError` → `greenlet_spawn has not been called`。必须先取字段快照，再用 `session_factory` 新开短会话写终态，见「恢复类操作的留痕写入」一节
- ❌ **把 aware datetime（`cst_now()`）写给 `TimestampMixin` 的 naive 列** — asyncpg 在 Cython 层抛 `can't subtract offset-naive and offset-aware datetimes`，堆栈无 Python 帧。写 `created_at/updated_at` 前必须 `.replace(tzinfo=None)`，见「TimestampMixin 列是 naive」一节

---

## 恢复类操作（DROP + 重建全库）的留痕写入

[来源: Feature 2026-10-26 — 数据备份在线恢复 `pg_restore --clean --if-exists`]

`pg_restore --clean --if-exists` 会 **DROP 并重建全库对象**，包括留痕表本身。
在恢复任务里用**同一个 session** 写终态会连环失败，且失败形态极具误导性：

| 现象 | 真实原因 |
|---|---|
| `StaleDataError: UPDATE ... expected to update 1 row(s); 0 were matched` | pending 留痕行随表一起被 DROP，ORM UPDATE 匹配 0 行 |
| `greenlet_spawn has not been called; can't call await_only() here` | 上述异常后 session 进入 `PendingRollbackError`，**该 session 的 greenlet 上下文已死**，再 `await self.db.rollback()` 也救不回来 |
| `asyncpg DataError: ... (can't subtract offset-naive and offset-aware datetimes)` | 见下节 |

**规则**：凡会 DROP/重建自身所在表（或整个库）的操作，`_mark_running` 之后的写入**必须**改用
`session_factory` 新开的短会话（新连接），并在写入前取好字段快照：

```python
# WRONG — 恢复后 self.db 已不可用，finalize 必然连环炸
ok, err = await self._run_pg_restore(path)
return await self._finalize(record, success=ok)   # self.db 的 greenlet 已死

# CORRECT — 先快照，再恢复，最后用短会话写终态
snapshot = self._snapshot(record)          # 在任何 DB 写操作前取完
await self._mark_running(record)
ok, err = await self._run_pg_restore(path)  # 此后 self.db 不可信
await self._write_final_state(snapshot, success=ok, error_message=err if not ok else None)

async def _write_final_state(self, snapshot, *, success, error_message):
    async def _apply(db):
        result = await db.execute(update(BackupRecord).where(BackupRecord.id == snapshot["id"]).values(**values))
        if (result.rowcount or 0) == 0:    # 留痕行已被删 → 按快照重插，保持 id 连续
            await db.execute(insert(BackupRecord).values(**snapshot, **values, ...))
        await db.commit()
    if self.session_factory is not None:
        async with self.session_factory() as fresh_db:
            await _apply(fresh_db)         # 新连接，不受原 session 破坏影响
    else:
        await _apply(self.db)              # 仅测试兜底
```

**Tests Required**：`tests/unit/test_backup_service.py::TestExecuteRestore`
- `test_restore_success` — 断言短会话收到 1 条 `update` 且 `commit`
- `test_restore_reinserts_record_when_table_dropped` — `rowcount=0` 时断言短会话收到 1 条 `insert`，
  且 `insert_stmt.compile().params["id"] == 20`、`params["status"] == "success"`
- 断言必须打在**短会话的 `execute.call_args_list`** 上（`__visit_name__` 筛 insert/update），
  不能断言 `record.status` —— 终态已不在原 ORM 对象上体现

> **Warning**: `pg_dump` 捕获的是 dump 执行时刻的库快照。备份任务若「先 `_mark_running` 再 `pg_dump`」，
> dump 里该留痕行恒为 `running`、`completed_at IS NULL`。恢复后列表显示「执行中」是**快照语义的固有正确行为**，
> 不是 bug —— 排查此类现象时先 `pg_restore --data-only --table=backup_records` 核对 dump 内容再下结论。

---

## TimestampMixin 列是 naive，业务时间列是 aware

[来源: Bug fix 2026-10-26 — 恢复留痕重插时 asyncpg `DataError`]

`TimestampMixin` 的 `created_at/updated_at` 是 `DateTime` **无时区**（PG: `timestamp without time zone`），
而业务时间列（如 `started_at/completed_at`）常声明为 `DateTime(timezone=True)`（PG: `timestamp with time zone`）。
`cst_now()` 返回 **aware** datetime。把 aware 值写给 naive 列，asyncpg 在 Cython 层做减法时报错，
错误信息是 `can't subtract offset-naive and offset-aware datetimes`，**堆栈不含 Python 帧**，极难定位。

```python
# WRONG — completed_at 是 aware（cst_now()），直接写给 naive 列
await db.execute(insert(BackupRecord).values(..., created_at=completed_at, updated_at=completed_at))

# CORRECT — 显式剥离时区
naive_now = completed_at.replace(tzinfo=None)
await db.execute(insert(BackupRecord).values(..., created_at=naive_now, updated_at=naive_now))
```

**判定方法**：`SELECT column_name, data_type FROM information_schema.columns WHERE table_name='...'`，
看是 `timestamp with time zone` 还是 `without time zone`，与 `app/utils/timezone.py` 的 `cst_now()`（aware）对齐。

**Tests Required**：恢复/清理等手写 `insert(...)` 的路径必须覆盖终态落库；
`tests/unit/test_test_data_consistency.py` 已守住 seed 与模型的权限种子一致性。
