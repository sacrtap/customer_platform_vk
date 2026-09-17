# 测试基础设施遗留问题

> 来源：`09-16-test-infrastructure-fix` 任务的独立质量检查（`trellis-check` 代理）结论。
>
> 该任务已修复 5 类问题：pytest 全量收集冲突（`--import-mode=importlib`）、`.trellis` 脚本产物缺尾换行、`tests/` 根目录遗留测试过时、3 处生产缺陷（`customer_repo` cast 误用 / `sync_logs` 返回体缺列 / `get_progress` Redis 键编码）、2 处测试隔离缺陷（`JWT_SECRET` 单例冲突 / `mock_cache` 未覆盖模块级绑定）。
>
> 下列 5 项为检查中**确认存在、但有意未在该任务内修复**的遗留项。判断依据：或属 PRD 明确置于 Out of Scope 的结构调整，或当前无消费方/无实际收益，或属既有技术债而非本次引入。**均不阻塞已完成任务的提交**（提交 `f94e54a`）。
>
> **处置进展（2026-09-17）**：TD-1/2/4/5 已在 `09-17-test-infra-td-fixes` 任务中修复
> （提交 `b60d3cd`，验证命令与逐项说明见文末「附：修复记录」）；TD-3 经用户明确决定排除，仍未修复。

---

## 总览

| 编号 | 严重度 | 位置 | 问题 | 状态 |
|------|--------|------|------|------|
| TD-1 | P2 | `tests/e2e/conftest.py`／`tests/integration/conftest.py` | 两层 conftest 结构性重复（其中 42 项权限清单在 4 处逐字重复） | ✅ 已修复（窄范围）`b60d3cd` |
| TD-2 | P3 | `tests/e2e/conftest.py:17`／`tests/integration/conftest.py:20` | `WEBHOOK_SECRET` 与已修的 `JWT_SECRET` 属同型隐患 | ✅ 已修复 `b60d3cd` |
| TD-3 | P3 | `.trellis/scripts/common/developer.py:62,90,140`／`common/task_store.py:573,590,1000` | 状态文件仍有 6 处绕过 `write_text_atomic` 的直接写入 | ⛔ 未修复（用户明确排除） |
| TD-4 | P3 | `tests/integration/conftest.py:176-331` | `test_user` fixture 内 8 处 `sys.stdout.write("[DEBUG] ...")` 探针 | ✅ 已修复 `b60d3cd` |
| TD-5 | P3 | `tests/test_cache.py:48` `test_init_default_ttl_config` | 断言整个内部 `_ttl_config` 字典（实现钉死型） | ✅ 已修复（范围扩大）`b60d3cd` |

---

## TD-1：e2e 与 integration conftest 结构性重复

**严重度**：P2（结构性重复 / 维护成本）

**问题**：

`backend/tests/e2e/conftest.py`（389 行）基本是 `backend/tests/integration/conftest.py`（510 行）的副本，以下部分逐字重复：

- 模块级引导序列（`sys.modules` 清理 → `app.config.get_settings.cache_clear()` → `app.config.settings` 重建 → `aiosmtplib` mock → `Sanic._app_registry.clear()`）
- `sync_test_engine`（建表 + `BaseModel.metadata.create_all`）
- `test_user`（TRUNCATE + 插入 roles/permissions/role_permissions/users/user_roles，含 38 项权限清单）
- `db_session`（function 级清理 `sync_task_logs` / `sync_tasks`）
- `mock_cache`（`base.cache_service` + `permissions.permission_cache` 替换与还原）
- `mock_scheduler`、`app`、`test_client`、`auth_headers`

两者实质差异仅在 `test_client` 的客户端构造方式。

**为何未修**：修复需把共享 fixture 上提到共同父级 conftest（`tests/conftest.py`）或抽独立模块，而两层的**模块级副作用有顺序依赖**（`sys.modules` 清理、settings 单例重建、Sanic registry 清理、`aiosmtplib` mock）。改动面覆盖整套集成 fixture，风险高于收益；且属该任务 PRD 明确列入 Out of Scope 的「结构调整」。

**建议方案**：

1. 把 DB 建表 / test_user / db_session / mock_cache / mock_scheduler / app / test_client / auth_headers 抽到 `tests/_shared_fixtures.py`，两层 conftest 以 `pytest_plugins` 或 import 方式引入；
2. 两层 conftest **只保留各自的模块级引导与环境差异**（e2e 需 `Sanic._app_registry.clear()` 与独立 app_name）；
3. 验收：`pytest tests/e2e/ -q` 与 `pytest tests/integration/ -q` 均全绿，且**同会话** `pytest tests/e2e/ tests/integration/ -q` 亦全绿（当前为 246 passed，改动后应保持）。

**注意**：本项与「单独跑通过、全量跑失败」类隔离缺陷高度相关 —— 重构时务必显式保留 TD-2 的结论（子层不得强制覆盖模块级 settings 单例）。

---

## TD-2：`WEBHOOK_SECRET` 与 `JWT_SECRET` 同型隐患

**严重度**：P3（潜在陷阱，当前无消费方）

**问题**：

`tests/e2e/conftest.py:17` 与 `tests/integration/conftest.py:20` 仍**各自强制**设置不同的 `WEBHOOK_SECRET`：

```python
# tests/integration/conftest.py
os.environ["WEBHOOK_SECRET"] = "integration_test_webhook_secret_key_fixed_12345678"
# tests/e2e/conftest.py
os.environ["WEBHOOK_SECRET"] = "e2e_test_webhook_secret_key_fixed_12345678"
```

而 `app/config.py` 的 `settings` 是模块级 `lru_cache` 单例 —— 全量会话中**最后加载者胜出**。这与本任务修掉的 `JWT_SECRET` 401 缺陷（`app/config.py:108` + `tests/integration/conftest.py:17` + `tests/e2e/conftest.py:15`）**完全同型**。

**为何未修**：当前无消费方 —— integration/e2e 下无任何 webhook 测试；`app/routes/webhooks.py:151` 仅在请求期读 `settings`，其单元测试自行 mock。改动无行为收益。

**建议方案**：按 `JWT_SECRET` 的处置方式收敛 —— 统一由 `tests/conftest.py` 的 `os.environ.setdefault("WEBHOOK_SECRET", ...)` 提供基线，两层 conftest 删除强制赋值。若某层确需不同值，应在该层的测试内显式 monkeypatch，而非在 conftest 层永久覆盖。

**验证点**：`pytest tests/ --collect-only -q` 无 error；`pytest tests/e2e/ tests/integration/ -q` 同会话全绿。

---

## TD-3：`.trellis` 脚本仍有 6 处直接写入绕过 `write_text_atomic`

**严重度**：P3（论证不实 / 单点保证未落地）

**问题**：

本任务的 REQ-3 修复了 `common/io.py` 的 `write_text_atomic`（写入前补尾换行），design.md D4 据此称「状态文件写入唯一两条路径（`write_json` 与 `add_session.py`）均经 `write_text_atomic`」。独立检查实测该论证**不成立**，仍有 6 处直接 `Path.write_text`：

| 文件:行 | 写入内容 |
|---|---|
| `common/developer.py:62` | 开发者状态 |
| `common/developer.py:90` | journal |
| `common/developer.py:140` | index |
| `common/task_store.py:573` | `prd.md` 等任务文档 |
| `common/task_store.py:590` | `check.jsonl` / `implement.jsonl` |
| `common/task_store.py:1000` | 任务文档 |

**为何未修**：这些内容自身都以 `\n` 结尾（一次性初始化）或为空 jsonl，`end-of-file-fixer` 当前不产生摩擦；贸然改动会碰到初始化路径而收益为零。

**建议方案**：若确要落实「单点保证」，把这 6 处改为 `write_text_atomic`（该函数已实测对已带尾换行的输入**幂等**，不会重复追加）。建议在下次触碰 `.trellis` 脚本时顺带完成。

**验证点**：改动后实跑一轮 `task.py create` → `archive` → `add_session.py`，确认 `git status` 无 hook 改写残留；并全量扫描 `.trellis/tasks/*/task.json`、`.trellis/workspace/*/index.md`、`journal-*.md` 末字节均为 `0a`。

---

## TD-4：`integration/conftest.py` 内既有 `[DEBUG]` stdout 探针

**严重度**：P3（测试噪声 / 既有技术债）

**问题**：

`backend/tests/integration/conftest.py:176-331` 的 `test_user` fixture 内有 8 处 `sys.stdout.write("[DEBUG] ...")` 调试输出。

**为何未修**：**非本任务引入**（不在 `f94e54a` 的 diff 中）；删除会改变该文件既有行为面且无功能收益。

**建议方案**：独立清理任务中移除，或降级为 `logging.debug`（与项目 `logging.getLogger(__name__)` 约定一致，见 `.trellis/spec/backend/logging-guidelines.md`）。注意该文件与 TD-1 重叠 —— 若 TD-1 重构落地，这些输出应随之消失。

---

## TD-5：`test_cache.py` 的实现钉死型断言

**严重度**：P3（测试风格，**判断保留**）

**问题**：

`backend/tests/test_cache.py:48` `test_init_default_ttl_config` 断言**整个内部 `_ttl_config` 字典**。本任务因 TTL 数值漂移（300→600，`app/cache/base.py` 未被改动，属测试过时）以「同步新值 + 补 `billing_consumption`」方式修复 —— 即**重新钉死**。

**为何未修（保守处置）**：项目 PRD（REQ-2）的判定标准是「断言语义是否仍成立」：TTL 策略仍成立，仅数值漂移，故按修复处理。行为面契约已由 `test_customer_list_ttl`、`test_set_with_unknown_prefix_uses_default_ttl` 等覆盖。

**建议方案**：若采纳「断言实现细节的测试应删除」的通用规则，可删除该用例（行为等价覆盖已存在），并**同步更新任务 AC 计数**（AC-2/AC-7 已登记的证据与计数会变化，需重新核对）。这是一个需要单独批准的取舍，不应顺手删除。

---

## 附一：`f94e54a` 的验证基线（历史，供核对）

提交 `f94e54a` 的验证结果：

```bash
cd backend && make test-cov
# → 872 passed, 0 failed；Total coverage: 57.61%（≥50%）

cd backend && .venv/bin/python -m pytest tests/unit/ -q --no-cov          # → 447 passed
cd backend && .venv/bin/python -m pytest tests/integration/ -q --no-cov   # → 243 passed
```

相关约定已沉淀：

- `.trellis/spec/backend/quality-guidelines.md` — 测试隔离两条陷阱（模块级 `from ... import cache_service` 使属性替换失效；**任何经共享 `settings` 单例读取的环境变量只能在 `tests/conftest.py` 设定一次基线**）
- `.trellis/spec/backend/database-guidelines.md` — Redis Hash 键编码（`decode_responses=True` 下必须用 str 键）

---

## 附二：修复记录（2026-09-17，提交 `b60d3cd`）

`09-17-test-infra-td-fixes` 任务修复了 TD-1/2/4/5（TD-3 按用户决定排除）。**核实结论：四项全部属实**；其中 TD-1、TD-5 的原文描述在实施中被核实修正（见下）。

### TD-1 —— 已修复（取窄范围）

**核实修正**：原文称「e2e 基本是 integration 的副本」「实质差异仅在 `test_client`」**不准确**——
逐 fixture 相似度实测 `sync_test_engine` 仅 **13%**、`db_session` 仅 **29%**，本质不同；
另一处原文称 `test_user` 含「38 项权限清单」，实为 **42 项**。

**实际修复**：未做完整 fixture 抽取（差异过大、风险高于收益），而是消除**最大的重复源**——
42 项权限清单在 **4 处逐字重复**（实测四份完全一致、同序）：

| 文件 | 原位置 |
|---|---|
| `tests/integration/conftest.py`（`test_user`） | 214–255 |
| `tests/integration/conftest.py`（`mock_cache.FULL_PERMISSIONS`） | 442–483 |
| `tests/e2e/conftest.py`（`test_user`） | 109–150 |
| `tests/e2e/conftest.py`（`mock_cache.FULL_PERMISSIONS`） | 265–306 |

→ 收敛为 `backend/tests/_test_data.py` 的 `PERMISSION_ROWS`（3 元组）与**由其派生**的
`PERMISSION_CODES`（frozenset）。派生关系使两份数据在**结构上不可能漂移**。

**附加（R2）**：新增种子漂移守护测试 `backend/tests/unit/test_test_data_consistency.py`，
断言 `PERMISSION_CODES ⊆ scripts/seed.py::ALL_PERMISSIONS`，失败信息列出缺失 code ——
防的是「测试全绿但生产角色缺权限」。**反向验证**：将任一 code 改为种子未定义值 → 测试失败；
改回 → 通过。

### TD-2 —— 已修复

按原文建议执行：`tests/conftest.py` 增加
`os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret-key")`；删除 integration/e2e
两层的强制赋值（改为说明性注释）。

**同时修正了 spec 中一条会教出该反模式的表述**：`quality-guidelines.md` 原文末句示例为
「子层 conftest 只应设置**本层独有**的变量（如 `WEBHOOK_SECRET`）」——而 `WEBHOOK_SECRET`
由共享 `settings` 单例读取，与 `JWT_SECRET` 完全同型，**并非「本层独有」**。
已改为以「该变量是否经共享的 `app.config.settings` 单例读取」为判据。

### TD-4 —— 已修复

`test_user` 内 8 处 `[DEBUG]` 的 `sys.stdout.write` + `flush()` 全部删除；
1 处 `[ERROR]` 改为 `logger.error("…（username=%s）", username)`（保留失败可见性，
该分支随后仍 `raise`，不吞异常）；移除 fixture 内因此不再使用的局部 `import sys`。

### TD-5 —— 已修复（范围较原文扩大）

原文只点出「整字典钉死断言」。实施中发现**三层同语义副本**，按用户确认取**彻底处置**：

1. **断言**：`test_init_default_ttl_config`（断言整个字典）删除，替换为 `ttl_for` 行为断言
   （含未知前缀回退 `default`）。
2. **清除零消费/谎值条目**（`_ttl_config` 19 → 18 条）：
   - `billing_pricing_rules`(3600)、`tag_stats`(1800)、`analytics`(900) —— 生产代码**零生产者/消费者**；
   - `analytics_profile` 原配 3600，但 5 个调用点全部显式传 `ttl=300` → **配置值永不生效**；
   - `analytics_prediction` 原配 1800，但 4 个调用点分别传 300/300/1800/1800 → **同前缀两个 TTL 的语义分叉**。
3. **拆分前缀**：新增 `analytics_prediction_forecast`(1800s) 承接 `/consumption/forecast*`，
   `analytics_prediction`(300s) 承接 `/prediction/*` —— 消除语义分叉。
4. **消除硬编码副本**：`app/routes/analytics.py` 9 处、`app/routes/billing/balances.py` 1 处
   硬编码 TTL 改为经 `cache_service.ttl_for()` 读取（`ttl_for` 即 TTL 的唯一读取入口）。

> **本批全部 TTL 取值与原实际生效值逐一相同 → 零行为变更。**

### TD-5 附带（原 R6）：删除零消费的 `settings.cache_ttl_*`

`app/config.py` 的 9 个 `cache_ttl_*` 字段生产读取 **0 次**，却被 `.env.example` 与
`docs/performance/cache-strategy.md` 文档化为「环境变量可覆盖」—— **照文档配置不生效**
（第三份 TTL 语义副本）。已全部删除，并改写两处文档为指向 `CacheService._ttl_config`。

**安全依据（实测，非推断）**：`pydantic-settings 2.1.0` 的 `extra='forbid'` **仅约束 init 参数**；
环境变量由 `EnvSettingsSource` 按字段名映射，未知变量被忽略。实测在
`os.environ['UNKNOWN_EXTRA_FIELD']='abc'` 及遗留 `CACHE_TTL_*` 存在下实例化 `Settings()` **成功**
→ 不破坏既有部署。全仓核实：`.env`、`deploy/` 均未设置这些变量。

> `docs/party-mode-memories/` 下的历史会话记录**有意不改** —— 属不可变史料，非现行文档。

### 验证命令与结果

```bash
cd backend && .venv/bin/python -m pytest tests/ --cov=app --cov-fail-under=50 -q
# → 876 passed, 472 warnings in 328.42s；Total coverage: 57.65%（≥50%）

cd backend && .venv/bin/python -m pytest tests/e2e/ tests/integration/ -q
# → 246 passed（同会话双层，与基线 246 一致）
```

**注意（并发共享测试库）**：单独并行跑 e2e 与 integration 时曾出现 `test_full_sync_flow` 404
（共享测试库冲突），串行/同会话重跑全绿 —— 分层套件请**串行**执行。

### 独立核验

由 `trellis-check` 代理独立复核（按约束未重跑全量）：AC1–AC5、AC8、AC10、AC11 均**独立复现成功**；
R6 安全性经独立实测（`Settings()` + 未知环境变量）；文档 TTL 表与 `_ttl_config` 机械比对
**18/18 全等**。核验另发现并修正 `docs/performance/cache-strategy.md`「相关文件」表中把
`config.py` 描述为「TTL 环境变量配置」的残留矛盾。

### 未收敛面（已知，非缺陷）

`analytics_dashboard_trend`、`analytics_cross_dimension`、`analytics_tag_usage`、
`analytics_priority_customers` 等约 8 个前缀**不在** `_ttl_config` 中，调用点显式传 `ttl=300`
—— 与 `default`(300) 同值，行为无差异，但语义未上收到配置表。
详见 `docs/performance/cache-strategy.md`「不在本表中的 TTL」。
