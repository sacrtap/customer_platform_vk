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
- `tests/e2e/conftest.py` — 同上一组 fixture（e2e 层副本，`test_client` 用 Sanic 自带 `asgi_client`）；`mock_cache` 额外覆盖 `app.routes.sync_tasks.cache_service` 模块级引用
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

### 陷阱：模块级 `from ... import cache_service` 使属性替换失效

[来源: Bug fix 2026-09-16 — e2e `test_full_sync_flow` 在全量会话中恒失败，单独跑却通过]

替换 `base.cache_service` **属性**只对「以 `base.cache_service` 形式访问」的代码生效。若被测模块用 `from app.cache.base import cache_service` **导入时绑定名字**，替换对其无效 —— 端点仍拿到真实 `CacheService` 并连真实 Redis：

```python
# 被测代码（app/routes/sync_tasks.py）
from app.cache.base import cache_service          # 导入时绑定
redis_client = await cache_service._get_redis()   # 属性替换影响不到这里

# 测试 fixture（仅替换属性 → 对上面的引用无效）
base.cache_service = mock_cache
```

**是否暴露取决于导入时机**：若某个测试文件在**收集阶段**提前导入 `app.routes` 包（例如 `from app.routes.users import upload_avatar`），绑定发生在 fixture 替换**之前** → mock 失效；否则绑定在替换之后 → mock 侥幸生效。这正是「单独跑通过、全量跑失败」类隔离问题的典型成因。

**修复**：fixture 必须显式覆盖端点真正引用的模块属性，并在 teardown 还原：

```python
from app.routes import sync_tasks as sync_tasks_routes

original_routes_cache = sync_tasks_routes.cache_service
sync_tasks_routes.cache_service = mock_cache
yield mock_cache
sync_tasks_routes.cache_service = original_routes_cache
```

**排查手法**：二分定位触发文件（`pytest <可疑测试文件> <目标测试>`），再用临时探针打印 `type(模块.cache_service).__name__` 确认 mock 是否生效，最后移除探针。

### 陷阱：子层 conftest 不得强制覆盖 `JWT_SECRET`

[来源: Bug fix 2026-09-16 — 全量会话中 e2e 登录成功但请求仍 401]

`app/config.py` 的 `settings` 是**模块级单例**（`lru_cache`）。`tests/conftest.py` 以 `os.environ.setdefault("JWT_SECRET", "test-secret-key")` 设定基线后，子层 conftest（`integration/`、`e2e/`）**不得**再强制赋值不同密钥：全量会话中两者都会被导入，最后加载者胜出 → 「签发用 A、验证用 B」→ 401。

子层 conftest 只应设置**本层独有**的变量（如 `WEBHOOK_SECRET`）。

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
