# Directory Structure

> How backend code is organized in this project.

---

## Overview

The backend is a **Sanic** (async) application using **SQLAlchemy async** ORM. Code lives under `backend/app/` and follows a layered architecture: routes → services → repositories → models.

---

## Directory Layout

```
backend/app/
├── main.py              # create_app() factory + app instance
├── config.py            # Pydantic Settings (env-driven)
├── constants/
│   └── error_codes.py   # ErrorCodes class — 5-digit error code constants
├── middleware/
│   ├── auth.py          # auth_required, require_permission decorators
│   └── audit.py         # Automatic audit logging middleware
├── models/              # SQLAlchemy ORM models (one file per domain)
│   ├── base.py          # BaseModel, TimestampMixin
│   ├── customers.py     # Customer, CustomerProfile
│   ├── billing.py       # Invoice, InvoiceItem, PricingRule, AuditLog, ...
│   └── users.py         # User, Role, Permission
├── repository/          # Repository pattern (data access layer)
│   ├── base.py
│   ├── invoice_repo.py
│   └── customer_repo.py
├── routes/              # Sanic Blueprint route handlers
│   ├── customers.py     # customers_bp = Blueprint("customers", url_prefix="/api/v1/customers")
│   ├── billing/         # Sub-blueprints for billing domain
│   │   ├── __init__.py  # billing_bp parent blueprint
│   │   ├── invoices.py
│   │   └── balances.py
│   └── auth.py
├── services/            # Business logic layer
│   ├── customers.py     # CustomerService(db_session)
│   ├── billing.py       # InvoiceService
│   └── auth.py          # AuthService (JWT)
├── cache/               # Redis cache layer
│   ├── base.py          # cache_service singleton
│   └── permissions.py   # permission_cache singleton
├── utils/
│   └── audit_helpers.py # create_audit_entry(), build_batch_audit_summary()
└── tasks/               # APScheduler background tasks
    └── scheduler.py
```

[来源: 项目源码 — `backend/app/` 目录结构]

---

## API Route Pattern

Every route module follows this exact structure:

1. **Create a Blueprint** with `url_prefix="/api/v1/<module>"`
2. **Decorate every handler** with the route method, then `@auth_required`, then `@require_permission("module:action")` if needed
3. **Get DB session** from `request.ctx.db_session`
4. **Instantiate service** with the session: `service = CustomerService(db_session)`
5. **Return** `json({"code": 0, "message": "...", "data": {...}})` on success

### Example — Standard CRUD route

[来源: 项目源码 — `backend/app/routes/customers.py:26-32`]

```python
from sanic import Blueprint
from sanic.request import Request
from sanic.response import json
from sqlalchemy.ext.asyncio import AsyncSession

from ..middleware.auth import auth_required, require_permission
from ..services.customers import CustomerService

customers_bp = Blueprint("customers", url_prefix="/api/v1/customers")


@customers_bp.get("")
@auth_required
@require_permission("customers:view")
async def list_customers(request: Request):
    db_session: AsyncSession = request.ctx.db_session
    service = CustomerService(db_session)
    # ... business logic ...
    return json({"code": 0, "message": "success", "data": {...}})
```

### Example — Sub-blueprint (billing)

[来源: 项目源码 — `backend/app/routes/billing/invoices.py:20-26`]

```python
from . import billing_bp

@billing_bp.get("/invoices")
@auth_required
@require_permission("billing:view")
async def get_invoices(request: Request):
    ...
```

The parent blueprint `billing_bp` is registered with `url_prefix="/api/v1/billing"` in `__init__.py`.

---

## Module Organization

New features should follow the existing layering:

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **Route** | `routes/<module>.py` | HTTP handling, input validation, response formatting |
| **Service** | `services/<module>.py` | Business logic, orchestration |
| **Repository** | `repository/<module>_repo.py` | Data access, queries (used by billing domain) |
| **Model** | `models/<module>.py` | SQLAlchemy ORM definitions |

> **Note**: Not all modules use the Repository pattern. Customer routes call `CustomerService` directly, which uses the session. Billing routes use `InvoiceRepository` + `InvoiceService`. Follow the pattern of the domain you're extending.

---

## Naming Conventions

- **Blueprints**: `<module>_bp` (e.g., `customers_bp`, `billing_bp`)
- **Services**: `<Domain>Service` class, instantiated with `db_session` (e.g., `CustomerService(db_session)`)
- **Repositories**: `<Domain>Repository` class (e.g., `InvoiceRepository(db)`)
- **Route files**: singular module name (e.g., `customers.py`, `auth.py`)
- **Model files**: singular domain name (e.g., `customers.py`, `billing.py`)

---

## Registering New Blueprints

New blueprints must be registered in `create_app()`:

[来源: 项目源码 — `backend/app/main.py:103-137`]

```python
from .routes.new_module import new_module_bp
app.blueprint(new_module_bp)
```
