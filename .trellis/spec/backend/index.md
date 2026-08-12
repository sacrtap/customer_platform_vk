# Backend Development Guidelines

> Coding conventions for the Sanic + SQLAlchemy async backend.

---

## Pre-Development Checklist

Before writing backend code, read and follow:

- [ ] [Directory Structure](./directory-structure.md) — Blueprint pattern, layered architecture (routes → services → repositories → models)
- [ ] [Error Handling](./error-handling.md) — `ErrorCodes` constants, `json({"code": ..., "message": ...})` response format
- [ ] [Logging Guidelines](./logging-guidelines.md) — stdlib `logging.getLogger(__name__)`, what to log / not log
- [ ] [Database Guidelines](./database-guidelines.md) — `request.ctx.db_session`, soft delete, cache invalidation
- [ ] [Quality Guidelines](./quality-guidelines.md) — testing (unit/integration), forbidden patterns

---

## Quick Reference

| Concern | Pattern | Source |
|---------|---------|--------|
| Framework | Sanic (async) + Blueprint | `backend/app/main.py` |
| ORM | SQLAlchemy async (`AsyncSession`) | `backend/app/models/` |
| Auth | `@auth_required` + `@require_permission("module:action")` | `backend/app/middleware/auth.py` |
| Error codes | `ErrorCodes` class (5-digit numeric) | `backend/app/constants/error_codes.py` |
| Response format | `{"code": 0, "message": "...", "data": {...}}` | All routes |
| Testing | pytest + pytest-asyncio (unit/integration/e2e) | `backend/tests/` |
| Migrations | Alembic (`backend/alembic/versions/`) | `backend/alembic/` |
| Cache | Redis via `cache_service` singleton | `backend/app/cache/base.py` |

---

## Quality Check

Before submitting code:

1. **Lint passes**: `cd backend && ruff check app/`
2. **Tests pass**: `cd backend && python -m pytest tests/ -v`
3. **Every new route has `@auth_required`** (or is in the skip-paths list)
4. **Error responses use `ErrorCodes` constants** — no hardcoded numbers
5. **Cache invalidated after mutations** — `cache_service.invalidate_*()`
6. **Test coverage ≥ 50%** for new code

---

**Language**: Specs are written in English. Code comments and user-facing messages are in Chinese.
