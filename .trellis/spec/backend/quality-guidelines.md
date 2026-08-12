# Quality Guidelines

> Code standards, testing, and forbidden patterns for the backend.

---

## Pre-Development Checklist

Before writing backend code, verify:

- [ ] Read the relevant route file (e.g., `routes/customers.py`) to match the existing pattern
- [ ] Use `ErrorCodes` constants from `constants/error_codes.py` — never hardcode error codes
- [ ] Every route handler has `@auth_required` (minimum) or `@auth_required` + `@require_permission("module:action")`
- [ ] DB session comes from `request.ctx.db_session` — never create sessions manually in routes
- [ ] Business logic lives in a service class, not in the route handler

---

## Testing Architecture

[来源: 项目源码 — `backend/tests/` directory]

The project uses **pytest + pytest-asyncio** with three test tiers:

| Tier | Location | Purpose | DB Required |
|------|----------|---------|-------------|
| **Unit** | `tests/unit/` | Service-level logic with mocked DB | No (MagicMock/AsyncMock) |
| **Integration** | `tests/integration/` | API endpoint tests via Sanic ASGI client | Yes (PostgreSQL test DB) |
| **E2E** | `tests/e2e/` | Full workflow tests | Yes |

### Test configuration

- `tests/conftest.py` — sets env vars before any app import, clears module cache
- `tests/integration/conftest.py` — fixtures: `sync_test_engine`, `test_user`, `db_session`, `app`, `test_client`, `mock_cache`
- Test DB: `customer_platform_test` (PostgreSQL), Redis DB index 1

---

## Unit Test Pattern

[来源: 项目源码 — `backend/tests/unit/test_customer_service.py:15-42`]

Mock the `AsyncSession` with `MagicMock` + `AsyncMock`:

```python
from unittest.mock import AsyncMock, MagicMock
import pytest
from app.services.customers import CustomerService

@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.new = set()
    return session

@pytest.fixture
def customer_service(mock_db_session):
    return CustomerService(db_session=mock_db_session)

class TestCustomerService_CreateCustomer:
    @pytest.mark.asyncio
    async def test_create_customer_success(self, mock_db_session_with_flush):
        # ... arrange, act, assert ...
        result = await customer_service.create_customer(customer_data)
        assert result is not None
        assert result.company_id == 1001
```

**Key conventions**:
- Test classes group related tests: `class TestCustomerService_<Method>`
- Test functions: `test_<action>_<condition>` (e.g., `test_create_customer_success`)
- Every async test has `@pytest.mark.asyncio`

---

## Integration Test Pattern

[来源: 项目源码 — `backend/tests/integration/test_customers_api.py:24-38,108-122`]

Use Sanic ASGI client with real DB and auth token:

```python
@pytest.fixture
async def auth_token(test_client, test_user):
    """获取认证 Token"""
    login_request, login_response = await test_client.post(
        "/api/v1/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )
    assert login_response.status == 200
    return login_response.json["data"]["access_token"]

@pytest.fixture
async def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.mark.asyncio
async def test_list_customers_success(test_client, auth_headers, customer_data):
    request, response = await test_client.get(
        "/api/v1/customers",
        headers=auth_headers,
    )
    assert response.status == 200
    data = response.json
    assert data["code"] == 0
    assert data["message"] == "success"
    assert "list" in data["data"]
```

**Key conventions**:
- Test data created via raw SQL `db_session.execute(text("INSERT ..."))` in fixtures
- Cleanup: `db_session.execute(text("DELETE FROM ... WHERE ..."))` or `TRUNCATE ... CASCADE`
- Assertions check both HTTP status and business `code` field
- Unauthenticated tests omit `headers` entirely

---

## Cache Mocking in Tests

[来源: 项目源码 — `backend/tests/integration/conftest.py:418-492`]

Tests mock both `cache_service` and `permission_cache` to avoid Redis dependency:

```python
@pytest.fixture(scope="function")
async def mock_cache():
    from unittest.mock import AsyncMock, MagicMock
    from app.cache import base, permissions

    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock(return_value=True)
    # ... other methods ...

    mock_perm_cache = MagicMock()
    mock_perm_cache.get_permissions = AsyncMock(return_value=FULL_PERMISSIONS)

    # Replace global instances
    base.cache_service = mock_cache
    permissions.permission_cache = mock_perm_cache
    yield mock_cache
    # Restore originals
    base.cache_service = original_cache
    permissions.permission_cache = original_perm_cache
```

---

## Forbidden Patterns

- ❌ **Creating DB sessions manually in routes** — always use `request.ctx.db_session`
- ❌ **Using `print()` for debugging** — use `logging.getLogger(__name__)`
- ❌ **Hardcoding error codes as raw numbers** — import from `ErrorCodes`
- ❌ **Skipping `@auth_required` on any non-public route** — only `/health`, `/`, `/api/v1/auth/login`, `/api/v1/auth/refresh`, and `/uploads/*` skip auth
- ❌ **Returning ORM objects directly** — always serialize to dict in the response
- ❌ **Forgetting cache invalidation** — after mutations, call the appropriate `cache_service.invalidate_*()` method

---

## CI Requirements

- Test coverage ≥ 50% (enforced in CI)
- Pre-commit hooks: ruff (lint), formatting check
- Run tests: `cd backend && python -m pytest tests/ -v`
