# Logging Guidelines

> How logging is done in this project.

---

## Overview

The project uses **Python stdlib `logging`** — no structured logging library (e.g., structlog, loguru). Loggers are created per-module with `logging.getLogger(__name__)`. **Middleware and lifecycle hooks follow the same rule** — `Sanic` 实例没有 `logger` 属性，`app.logger.<level>(...)` 会抛 `AttributeError`。

---

## Log Levels

| Level | When to use | Example location |
|-------|-------------|-----------------|
| `debug` | Diagnostic detail, parse failures in audit | `middleware/audit.py:119` |
| `info` | App lifecycle, successful operations | `main.py:185`, `middleware/auth.py:85` |
| `warning` | Recoverable issues (token verification, blacklisted tokens) | `middleware/auth.py:68,166` |
| `error` | Failures that need attention (audit log failure, middleware exceptions) | `middleware/auth.py:94`, `middleware/audit.py:156` |

---

## Logger Creation Pattern

### In middleware and lifecycle hooks

**Use a module-level logger.** `Sanic` 对象没有 `logger` 属性
（`hasattr(Sanic, "logger") is False`，实测 Sanic 22.12），`app.logger.<level>(...)` 必抛 `AttributeError`。

[来源: 项目源码 — `backend/app/middleware/auth.py:21,68`]

```python
import logging

logger = logging.getLogger(__name__)

def auth_middleware(app: Sanic):
    @app.middleware("request")
    async def authenticate(request: Request):
        try:
            payload = AuthService.verify_token(token)
        except Exception as e:
            logger.warning("Token verification failed: %s", e)
```

> **Warning（误用后果分级，均已在 `09-16-runtime-tech-debt-fixes` 中修复并加测试）**：
> - **request 中间件**内抛错 → Sanic 返回 **HTML 500** 而非约定 JSON，前端解析失败；
>   traceback 只剩 `AttributeError`，真实异常（DB/Redis 故障等）彻底丢失。
> - **response 中间件**内抛错 → Sanic 吞掉异常，响应仍正常，但日志同样只留 `AttributeError`，真实原因丢失。
>
> 结论：中间件内**禁止**使用 `app.logger`；异常分支建议带 `exc_info=True`。

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
            logger.error("Audit log failed: %s", e, exc_info=True)
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

---

## Request Correlation (关联标识)

> 为请求链路提供稳定关联标识，日志可借由同一标识串起完整链路。

### 关联标识的注入

- **中间件**: `backend/app/middleware/correlation.py` 的 `correlation_middleware(app)`
  - 每个请求在 request 阶段（priority 1000，最先执行）注入关联标识：
    - 客户端携带合法 `X-Request-Id` 头时**透传**（长度 1-64，仅 ASCII `[A-Za-z0-9._:-]`）
    - 否则生成 32 位 hex（`uuid4().hex`）
  - response 阶段（priority -1000，最后执行）写入响应头 `X-Request-Id`，并复位 contextvar
- **请求对象**: `request.ctx.request_id` 保存当前请求关联标识，路由/服务层可直接读取
- **日志上下文**: contextvar `app.middleware.correlation.request_id_var` 暴露当前关联标识，
  默认值 `"-"`（无请求上下文的后台任务/启动日志）

### 日志记录中的关联标识

`RequestIdFilter`（`app.middleware.correlation`）已挂到 root handlers、各命名 logger
handlers 与 lastResort，为**所有**日志记录附加 `request_id` 字段：

```python
# 日志格式示例（formatter 中引用 %(request_id)s 即可输出）
"%(asctime)s [%(levelname)s] [request_id=%(request_id)s] %(message)s"
# 输出示例
# 2026-09-12 18:27:15 [ERROR] [request_id=3f2a...] 结算单生成失败
```

- **规则**: 每条日志都应能通过 `request_id` 关联到触发它的 HTTP 请求
- **失败排查**: 拿到响应头的 `X-Request-Id` 后，按 `request_id=<值>` 检索日志即可
  串起「中间件 → 路由 → 服务层 → 数据库」的完整链路
- **不记录**: 关联标识本身不包含敏感信息，但禁止把 `request_id` 与完整请求体、
  凭据拼接进同一条消息（遵循上方「What NOT to Log」）

### 关联标识约定的使用

- **手动写入审计/业务记录**: 需要把请求关联标识落库时，读取 `request.ctx.request_id`
  （有请求上下文）或 `request_id_var.get()`（无请求上下文）
- **透传下游**: 调用外部服务时，将 `request.ctx.request_id` 放入 `X-Request-Id` 请求头，
  便于跨服务链路追踪
