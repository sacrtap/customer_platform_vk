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

## Forbidden Patterns

- ❌ **Raw `DELETE` statements in production** — use soft delete (`deleted_at = datetime.now()`)
- ❌ **Creating sessions with `async_session_maker()` in routes** — always use `request.ctx.db_session`
- ❌ **Committing in routes without understanding service commit behavior** — some services commit internally (e.g., `CustomerService.create_customer`), some expect the caller to commit
- ❌ **Forgetting to close sessions** — the middleware handles this; do not create sessions outside the middleware pattern
