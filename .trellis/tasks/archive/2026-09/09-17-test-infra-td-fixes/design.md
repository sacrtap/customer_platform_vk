# 技术设计：测试基础设施遗留项修复（TD-1/2/4/5）

> 对应 `prd.md` 的 R1–R5 与 AC1–AC9。四条原则：**同一语义只留一份**、**死配置即缺陷**、**测试不得钉死实现**、**改动面与风险相称**。

---

## 1. 总体策略

| 项 | 策略 | 依据 |
|---|---|---|
| TD-1 | 只收敛**逐字重复**的部分（4 份 42 项权限清单） | 相似度实测：`sync_test_engine` 13%、`db_session` 29% → 强抽会引入语义回归 |
| TD-1 附加 | 权限清单与 `seed.py` 之间加**漂移守护** | 二者是同一语义的两个副本，漂移即「测试绿但生产缺权限」 |
| TD-2 | 收敛到根 conftest 的 `setdefault` 基线 | 与已修的 `JWT_SECRET` 401 同型，复用已验证的处置方式 |
| TD-4 | 删除 stdout 探针；错误路径改 `logger.error` | 符合 `logging-guidelines.md`；保留失败可观测性 |
| TD-5 | 建立 `ttl_for()` 单一入口，消除硬编码副本与死条目 | 与上一任务同型：同语义多副本 + 死配置 |

---

## 2. R1：权限清单收敛

### 2.1 新模块 `backend/tests/_test_data.py`

```python
"""测试共享数据常量。

权限清单原先在 integration/e2e 两层 conftest 中各写两遍（共 4 份逐字副本）。
此处收敛为唯一来源；PERMISSION_CODES 由 PERMISSION_ROWS 派生，
使「插入用行数据」与「mock 权限集」在结构上不可能漂移。
"""

# (code, name, module) —— 与 scripts/seed.py 的 ALL_PERMISSIONS 语义一致，此处为测试侧子集/裁剪形态
PERMISSION_ROWS: list[tuple[str, str, str]] = [
    ("customers:view", "查看客户", "customers"),
    ...  # 共 42 条，逐字取自原 integration/conftest.py:214-255
]

# 由行数据派生：mock 权限缓存使用
PERMISSION_CODES: frozenset[str] = frozenset(code for code, _, _ in PERMISSION_ROWS)
```

**命名与收集安全**：`python_files = test_*.py`（`pytest.ini:3`），下划线前缀模块**不会被收集**；亦不匹配 `python_classes = Test*`。

### 2.2 四处替换

| 位置 | 现状 | 改为 |
|---|---|---|
| `tests/integration/conftest.py:213-256` | 字面量 42 元组 | `from tests._test_data import PERMISSION_ROWS`（导入路径见 2.3）；`for code, name, module in PERMISSION_ROWS:` |
| `tests/integration/conftest.py:441-484` | 字面量 42 字符串 | `FULL_PERMISSIONS = PERMISSION_CODES` |
| `tests/e2e/conftest.py:108-151` | 字面量 42 元组 | 同 integration |
| `tests/e2e/conftest.py:264-307` | 字面量 42 字符串 | 同 integration |

### 2.3 导入路径决策

两处 conftest 位于 `tests/integration/` 与 `tests/e2e/`，需导入 `tests/_test_data.py`。`pytest.ini` 使用 `--import-mode=importlib` 且 `testpaths = tests`，rootdir 为 `backend/`；`tests/conftest.py:37-39` 已把 `backend/` 插入 `sys.path`。

**已实测确定（2026-09-17）**：使用 **`from tests._test_data import ...`**。

真实 pytest 探针结果（`pytest tests/integration/_probe_import_test.py -q`，探针用完已删）：

| 写法 | 结果 |
|---|---|
| `from tests._test_data import PERMISSION_ROWS` | ✅ 通过 |
| `from _test_data import PERMISSION_CODES` | ❌ `ModuleNotFoundError: No module named '_test_data'` |

原因：`tests/__init__.py` **不存在**，且 `--import-mode=importlib` **不会**把测试文件所在目录加入 `sys.path`；而 `tests/conftest.py:37-39` 把 `backend/` 插入 `sys.path`，使 `tests/` 作为**命名空间包**可被导入。

> **不得**改用裸模块导入（`from _test_data import ...`）——已实测失败。

### 2.4 明确不做

不抽取 `sync_test_engine` / `db_session` / `mock_cache` / `app` / `test_user` 主体。理由（已实测）：

- `sync_test_engine`：integration 版本额外做「确保库存在 + 建表 + `inspect` 校验」，e2e 仅 `create_all`，**职责不同**；
- `db_session`：integration 版本含更多清理逻辑；
- `mock_cache`：e2e 版本额外注入 `mock_redis`、`check_redis_available` 并覆盖 `sync_tasks_routes.cache_service` 模块级绑定（`e2e/conftest.py:252-262, 320-326`），integration 无 —— **该差异是必要的**，抽取会破坏 e2e 的 sync-tasks 端点隔离。

---

## 3. R2：漂移守护测试

新增 `backend/tests/unit/test_test_data_consistency.py`（或并入既有单测）：

```python
def test_test_permissions_exist_in_seed():
    """测试权限清单必须是种子权限的子集，否则测试全绿而生产角色缺权限。"""
    from scripts.seed import ALL_PERMISSIONS
    from tests._test_data import PERMISSION_CODES

    seed_codes = {code for code, *_ in ALL_PERMISSIONS}
    missing = PERMISSION_CODES - seed_codes
    assert not missing, f"测试权限未在 seed.py 定义：{sorted(missing)}"
```

**可导入性已核实**：`backend/scripts/__init__.py` 存在（0 字节）→ `scripts` 是包；`seed.py` 仅在 `if __name__ == "__main__"`（:352）下执行 → 导入无副作用。

**反向验证（AC2）**：临时把 `_test_data.py` 中一个 code 改为 seed 未定义值 → 该测试必须失败；恢复后通过。（此步为一次性手工验证，不写入套件。）

---

## 4. R3：`WEBHOOK_SECRET` 收敛

**`tests/conftest.py`**：在既有 `JWT_SECRET` 的 `setdefault` 之后追加：

```python
os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret-key")
```

**`tests/integration/conftest.py:19-20`** → 删除「WEBHOOK_SECRET 仅本层需要，保留强制设置。」与强制赋值行，替换为说明：

```python
# WEBHOOK_SECRET 同样由 tests/conftest.py 的 setdefault 提供基线；
# 任一层需要不同值时应在本层测试内 monkeypatch，而非在 conftest 永久覆盖 settings 单例。
```

**`tests/e2e/conftest.py:17`** → 同上（删除强制赋值）。

**保留**两处关于 `JWT_SECRET` 的解释性注释（它们是该缺陷的高价值说明）。

---

## 5. R4：移除 stdout 探针

`tests/integration/conftest.py` 的 `test_user` fixture 内：

| 行 | 处置 |
|---|---|
| 176/180/188/197/209/306/318/331 | 删除 `sys.stdout.write("[DEBUG] ...")` **及其紧邻的 `sys.stdout.flush()`** |
| 314 | `[ERROR]` → `logger.error("test_user: 用户创建后查询不到（username=%s）", username)` |
| 158 | 删除局部 `import sys`（该 fixture 内不再使用；**须核实全函数内无其它 `sys.` 引用**） |

模块顶部新增 `logger = logging.getLogger(__name__)`（若尚无）。

> 注意：`test_user` 内另有 `return` 提前退出的分支（`count > 0`）——删除探针时不得改变控制流。

---

## 6. R5：TTL 配置单一真相

### 6.1 `CacheService.ttl_for()`

```python
def ttl_for(self, prefix: str) -> int:
    """返回指定缓存前缀的 TTL（秒）；未配置时回退 default。

    这是 TTL 配置的唯一读取入口：CacheService 内部与路由层（需自行拼键批量读写时）
    都应经过它，避免同一语义出现硬编码副本。
    """
    return self._ttl_config.get(prefix, self._ttl_config["default"])
```

`set()` 内 `expire = ttl or self._ttl_config.get(prefix, self._ttl_config["default"])` → `expire = ttl or self.ttl_for(prefix)`。

### 6.2 死条目清理

`_ttl_config` 移除 `"billing_pricing_rules": 3600`（全仓零消费）。

### 6.3 硬编码副本修复

`app/routes/billing/balances.py:87`：

```python
# ❌ 现状：与 _ttl_config["billing_consumption"] 同语义的硬编码副本
pipe.setex(key, 300, val)

# ✅ 改为引用同一配置来源
ttl = cache_service.ttl_for("billing_consumption")
pipe.setex(key, ttl, val)
```

> 该处因需 `mget` / `pipeline` 批量操作而未走 `CacheService.set()`，故必须显式经 `ttl_for()` 取配置；`ttl` 在循环外取一次，不引入额外分配。

### 6.4 断言替换

`tests/test_cache.py::test_init_default_ttl_config`（整字典断言）→ **删除**，代之以行为断言：

```python
def test_ttl_for_returns_configured_values(self, cache_service: CacheService):
    assert cache_service.ttl_for("customer_list") == 600
    assert cache_service.ttl_for("tag_list") == 3600

def test_ttl_for_unknown_prefix_falls_back_to_default(self, cache_service: CacheService):
    assert cache_service.ttl_for("nonexistent_prefix") == cache_service.ttl_for("default")
```

**为何这样替换**：原用例钉住 20 条目的内部字典（含死条目）。替换后断言的是**可观察行为**（前缀 → TTL、未知 → 回退），与既有 `setex` 断言（`test_customer_list_ttl` 等）形成互补：后者证明 `set()` 真的把该 TTL 传给 Redis，前者证明 `ttl_for()` 的契约。不重复、不钉实现。

---

## 7. R6：清理零消费的 `settings.cache_ttl_*`

### 7.1 事实

`app/config.py:79-88` 定义 9 个字段：`cache_ttl_dashboard_stats`(300)、`cache_ttl_dashboard_chart`(900)、`cache_ttl_analytics_health`(600)、`cache_ttl_analytics_profile`(3600)、`cache_ttl_analytics_invoice`(300)、`cache_ttl_analytics_warning`(180)、`cache_ttl_analytics_prediction`(1800)、`cache_ttl_pricing_rules`(3600)、`cache_ttl_analytics_trend`(900)。

- 生产代码读取次数：**0**（`grep -rn "settings\.cache_ttl" app/` 无命中）；
- 被 `.env.example:133-157`（9 行注释环境变量）与 `docs/performance/cache-strategy.md:49-57`（配置表）**文档化为运维可配项**；
- 真实生效的 TTL 全在 `app/cache/base.py` 的 `_ttl_config`。

**性质**：这不是「无用字段」，而是**误导性配置**——运维按文档设置 `CACHE_TTL_DASHBOARD_STATS=600` 不会有任何效果。

### 7.2 删除的启动安全性（实测，非推断）

`pydantic-settings 2.1.0` 的 `BaseSettings.model_config['extra'] = 'forbid'`。若该 `extra` 也约束环境变量，则运维 `.env` 中遗留的 `CACHE_TTL_*` 会在删字段后变成非法变量 → **启动崩溃**。

实测结论：**不会**。`extra` 仅约束 init 参数；环境变量由 `EnvSettingsSource` 按字段名映射，未知变量被忽略：

```python
os.environ['UNKNOWN_EXTRA_FIELD'] = 'abc'
S()   # 不报错
```

全仓核实：`.env`、`deploy/`（含 `docker-compose.yml`）均未设置这些变量；`.env.example` 中仅为**注释行**（复制为 `.env` 也不会生效）。

### 7.3 改动

| 文件 | 改动 |
|---|---|
| `app/config.py` | 删除 `# 缓存 TTL 配置 (秒)` 注释与 9 个字段（第 79-88 行） |
| `.env.example` | 删除对应注释块与被注释的 9 行（第 130-157 行区间） |
| `docs/performance/cache-strategy.md` | 删除配置表（49-57 行），改写为：TTL 的唯一来源是 `app/cache/base.py::CacheService._ttl_config`，读取入口为 `ttl_for()`；列出实际条目（含 `billing_consumption`，不含已删的 `billing_pricing_rules`） |

### 7.4 不改动

`docs/party-mode-memories/2026-08-12-consumption-forecast-memory.md:61` 提到 `cache_ttl_analytics_prediction: 1800` —— 该文件是**历史会话记录**（不可变史料），不改写；在技术债文档中说明理由。

### 验证（AC10/AC11）

- `grep -rn "cache_ttl_" backend/app/ --include=*.py` → 0
- `.env.example` / `cache-strategy.md` 不再将 `CACHE_TTL_*` 描述为可配项
- `cache-strategy.md` 的条目清单与 `_ttl_config` 一致



| 项 | 评估 |
|---|---|
| 测试套件 | R1/R3 影响**全部** integration 与 e2e 测试的 fixture 引导；R4 仅影响 `test_user` |
| 生产代码 | 仅 R5：`app/cache/base.py`（新增方法 + 删死条目）、`app/routes/billing/balances.py`（TTL 来源）—— 行为等价（值不变） |
| 生产行为变化 | **无**：`ttl_for` 语义与既有 `get(prefix, default)` 完全一致；`billing_consumption` 仍为 300 |
| 回滚 | R1/R2/R3/R4 互相独立；R5 的两处可单独回退 |
| CI 门禁 | 覆盖率 ≥50%、`ruff check` + `ruff format --check`、`pnpm type-check` |

---

## 8. 实现首步待确认项

1. `backend/tests/__init__.py` 是否存在 → 决定 `_test_data` 的导入写法（2.3）
2. `test_user` 内除探针外是否还有 `sys.` 引用 → 决定 `import sys` 是否可删
3. `tests/integration/conftest.py` 与 `tests/e2e/conftest.py` 是否已有模块级 `logger` → 决定 R4 是否需新增
4. `scripts/seed.py::ALL_PERMISSIONS` 的实际元组形状（4 元组）→ 确认 R2 的 `for code, *_ in ...` 解包正确
