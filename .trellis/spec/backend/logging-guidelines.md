# Logging Guidelines

> How logging is done in this project.

---

## Overview

The project uses **Python stdlib `logging`** — no structured logging library (e.g., structlog, loguru). Loggers are created per-module with `logging.getLogger(__name__)`. Sanic's built-in `app.logger` is used inside middleware and app lifecycle hooks.

---

## Log Levels

| Level | When to use | Example location |
|-------|-------------|-----------------|
| `debug` | Diagnostic detail, parse failures in audit | `middleware/audit.py:119` |
| `info` | App lifecycle, successful operations | `main.py:185`, `middleware/auth.py:71` |
| `warning` | Recoverable issues (token verification, blacklisted tokens) | `middleware/auth.py:54,71` |
| `error` | Failures that need attention (audit log failure, middleware exceptions) | `middleware/auth.py:80`, `middleware/audit.py:156` |

---

## Logger Creation Pattern

### In middleware and lifecycle hooks

Use Sanic's `app.logger`:

[来源: 项目源码 — `backend/app/middleware/auth.py:54`]

```python
@app.middleware("request")
async def authenticate(request: Request):
    try:
        payload = AuthService.verify_token(token)
    except Exception as e:
        app.logger.warning(f"Token verification failed: {e}")
```

### In services and standalone modules

Create a module-level logger:

[来源: 项目源码 — `backend/app/middleware/audit.py:22`]

```python
import logging

logger = logging.getLogger(__name__)

def audit_middleware(app: Sanic):
    @app.middleware("response")
    async def log_write_operations(request: Request, response):
        try:
            # ... audit logic ...
        except Exception as e:
            app.logger.error(f"Audit log failed: {e}")
```

### In app startup

[来源: 项目源码 — `backend/app/main.py:181-185`]

```python
@app.before_server_start
async def on_start(app, loop):
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🚀 {settings.app_name} 启动在 {settings.host}:{settings.port}")
```

---

## What to Log

- **Auth events**: token verification failures, blacklisted token usage
- **App lifecycle**: startup, shutdown, stuck task recovery
- **Audit failures**: when audit log write fails (non-blocking — caught and logged, doesn't break the request)
- **Background task recovery**: sync task recovery results on startup

---

## What NOT to Log

- ❌ **Passwords, password hashes, JWT tokens** — never log raw credentials
- ❌ **Full request bodies** — may contain PII (email, phone numbers)
- ❌ **User personal data** — use `mask_sensitive_data()` from `audit_helpers.py` if needed

[来源: 项目源码 — `backend/app/utils/audit_helpers.py:62-71`]

```python
def mask_sensitive_data(data: dict, fields: list | None = None) -> dict:
    """敏感数据脱敏"""
    if fields is None:
        fields = ["password", "password_hash", "token", "secret"]
    masked = data.copy()
    for field in fields:
        if field in masked:
            masked[field] = "***MASKED***"
    return masked
```

---

## Audit Logging (separate from app logging)

Audit logging records **who did what** for compliance. It is NOT the same as application logging.

- **Automatic**: The audit middleware (`middleware/audit.py`) intercepts POST/PUT/DELETE and writes `AuditLog` records
- **Manual**: Some routes skip the middleware and call `create_audit_entry()` directly (e.g., billing invoice status changes)

[来源: 项目源码 — `backend/app/routes/billing/invoices.py:558-574`]

```python
await create_audit_entry(
    db_session=db,
    user_id=user.get("user_id") if user else None,
    action="submit",
    module="billing",
    record_id=invoice_id,
    record_type="invoice",
    changes={"before": {"status": status_before}, "after": {"status": ...}},
    operation_type="standard",
    ip_address=request.headers.get("x-real-ip", request.headers.get("x-forwarded-for", request.ip)),
    auto_commit=True,
)
```

**When to use manual audit**: when the route needs to capture before/after status changes that the generic middleware cannot infer, or when the middleware skip list excludes the path.
