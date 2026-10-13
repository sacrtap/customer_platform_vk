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
#   等价底层手段（噪声较多）：python -m alembic check —— 手工备份表
#   customer_balances_backup_20260812 会报 remove_table，属预期。

# 单测级守护（本地即可跑，用独立库 upgrade head 后比对）
cd backend && pytest tests/integration/test_migrations.py::TestModelMigrationParity -q

# 直接比对该表实际列
python -c "import asyncio,asyncpg; ..."  # information_schema.columns where table_name='customers'
```

---

## Forbidden Patterns

- ❌ **Raw `DELETE` statements in production** — use soft delete (`deleted_at = datetime.now()`)
- ❌ **Creating sessions with `async_session_maker()` in routes** — always use `request.ctx.db_session`
- ❌ **Committing in routes without understanding service commit behavior** — some services commit internally (e.g., `CustomerService.create_customer`), some expect the caller to commit
- ❌ **Forgetting to close sessions** — the middleware handles this; do not create sessions outside the middleware pattern
- ❌ **`asyncio.gather()` with multiple `session.execute()` on the same AsyncSession** — see AsyncSession Concurrency Constraint above
- ❌ **Passing Python `False` or `True` to `.where()`** — see "Impossible" WHERE Conditions above
- ❌ **Orphan column: adding ORM fields without applying the migration to the running DB** — 「有迁移文件」≠「库已升级」；改模型后必须 `alembic upgrade head` 并用 `scripts/check_schema_drift.py` 验证，见上方 Schema Drift 一节
- ❌ **Manually maintaining `ALTER TABLE ... ADD COLUMN` lists in test conftest** — 已废止，改用 `tests/_test_data.py::sync_test_schema` 按 metadata 自动同步；新增字段勿再手写清单
