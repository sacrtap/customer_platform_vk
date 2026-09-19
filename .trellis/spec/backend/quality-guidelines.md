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

正确判据不是「哪一层需要」，而是「该变量是否经共享的 `app.config.settings` 单例读取」。**任何**经该单例读取的变量（`JWT_SECRET`、`WEBHOOK_SECRET` 等）都**只能在 `tests/conftest.py` 设定一次基线**（`setdefault`）；子层需要不同值时，应在本层测试内 `monkeypatch`，而不是在子层 conftest 里永久覆盖 settings 单例——否则同样落入「最后加载者胜出」。

> 本次修复依据：integration 与 e2e 两层曾各自强制设置**不同**的 `WEBHOOK_SECRET`（与已修的 `JWT_SECRET` 401 同型，`settings.webhook_secret` 由 `os.getenv("WEBHOOK_SECRET")` 读取），已于 2026-09-17 收敛为仅 `tests/conftest.py` 一处 `setdefault`。

### 陷阱：脚本中循环变量遮蔽外层「主对象」变量

[来源: Bug fix 2026-09-18 — CI E2E 客户管理测试 403，本地却正常]

**症状**：全新数据库（CI）上 `POST /api/v1/customers` 返回 `403 权限不足`，但本地（历史库）正常。`scripts/seed.py` 日志显示「已分配角色: 超级管理员」，数据库里 admin 却只有「销售经理」角色（8 权限，缺 `customers:create`）。

**根因**：Python **无块级作用域**，`for` 循环变量在循环结束后仍存活并覆盖同名外层变量：

```python
# seed.py 步骤 2：role = 「超级管理员」
role = session.execute(select(Role).where(Role.name == SUPER_ADMIN_ROLE_NAME)).scalar_one_or_none()
...
# 步骤 2.6/2.7：同名循环变量覆盖 role
for legacy_code, new_codes in LEGACY_TO_NEW_PERMISSIONS.items():
    for role in all_roles:          # ← 覆盖外层 role！
        ...
# 循环结束后 role 指向 all_roles 最后一个角色（按 id 排序 =「销售经理」）
# 步骤 3：
admin.roles.append(role)            # ← 把 admin 绑到「销售经理」而非「超级管理员」
```

**掩盖因素**：日志 `print(f"✅ 已分配角色: {SUPER_ADMIN_ROLE_NAME}")` 打印的是**常量**，与实际 append 的变量无关 → 输出永远「正确」，掩盖了绑定错误。

**修复**：主对象与遍历变量用**不同名字**：

```python
super_admin_role = session.execute(...).scalar_one_or_none()
...
for iter_role in all_roles:         # 遍历用独立名，不遮蔽 super_admin_role
...
admin.roles.append(super_admin_role)
```

**排查手法**：怀疑「seed 成功但权限缺失」时，不要在本地历史库验证（历史数据可能恰好正确），应建**全新库**完整模拟 CI 流程（`alembic upgrade head` + `python scripts/seed.py --reset`），再查 `user_roles` 绑定：`SELECT u.username, r.name FROM users u JOIN user_roles ur ON u.id=ur.user_id JOIN roles r ON ur.role_id=r.id WHERE u.username='admin';`。

**预防**：脚本/长函数中，先声明的「主对象」变量与后续遍历变量**禁止同名**；断言「分配成功」的日志/断言应打印**实际变量内容**而非常量。

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
