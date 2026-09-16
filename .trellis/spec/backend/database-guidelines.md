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

## Forbidden Patterns

- ❌ **Raw `DELETE` statements in production** — use soft delete (`deleted_at = datetime.now()`)
- ❌ **Creating sessions with `async_session_maker()` in routes** — always use `request.ctx.db_session`
- ❌ **Committing in routes without understanding service commit behavior** — some services commit internally (e.g., `CustomerService.create_customer`), some expect the caller to commit
- ❌ **Forgetting to close sessions** — the middleware handles this; do not create sessions outside the middleware pattern
- ❌ **`asyncio.gather()` with multiple `session.execute()` on the same AsyncSession** — see AsyncSession Concurrency Constraint above
- ❌ **Passing Python `False` or `True` to `.where()`** — see "Impossible" WHERE Conditions above
