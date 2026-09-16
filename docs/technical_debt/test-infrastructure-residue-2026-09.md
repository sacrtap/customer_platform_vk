# 测试基础设施遗留问题

> 来源：`09-16-test-infrastructure-fix` 任务的独立质量检查（`trellis-check` 代理）结论。
>
> 该任务已修复 5 类问题：pytest 全量收集冲突（`--import-mode=importlib`）、`.trellis` 脚本产物缺尾换行、`tests/` 根目录遗留测试过时、3 处生产缺陷（`customer_repo` cast 误用 / `sync_logs` 返回体缺列 / `get_progress` Redis 键编码）、2 处测试隔离缺陷（`JWT_SECRET` 单例冲突 / `mock_cache` 未覆盖模块级绑定）。
>
> 下列 5 项为检查中**确认存在、但有意未在该任务内修复**的遗留项。判断依据：或属 PRD 明确置于 Out of Scope 的结构调整，或当前无消费方/无实际收益，或属既有技术债而非本次引入。**均不阻塞已完成任务的提交**（提交 `f94e54a`）。

---

## 总览

| 编号 | 严重度 | 位置 | 问题 | 建议时机 |
|------|--------|------|------|----------|
| TD-1 | P2 | `tests/e2e/conftest.py`（389 行）／`tests/integration/conftest.py`（510 行） | 两层 conftest 大范围结构性重复 | 下次新增 test tier 或改动 fixture 时 |
| TD-2 | P3 | `tests/e2e/conftest.py:17`／`tests/integration/conftest.py:20` | `WEBHOOK_SECRET` 与已修的 `JWT_SECRET` 属同型隐患 | 与 TD-1 同批处理 |
| TD-3 | P3 | `.trellis/scripts/common/developer.py:62,90,140`／`common/task_store.py:573,590,1000` | 状态文件仍有 6 处绕过 `write_text_atomic` 的直接写入 | 下次触碰 `.trellis` 脚本时 |
| TD-4 | P3 | `tests/integration/conftest.py:176-331` | `test_user` fixture 内 8 处 `sys.stdout.write("[DEBUG] ...")` 探针 | 独立清理任务 |
| TD-5 | P3 | `tests/test_cache.py:48` `test_init_default_ttl_config` | 断言整个内部 `_ttl_config` 字典（实现钉死型） | 下次改动 TTL 配置时 |

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

## 附：已完成任务的验证基线（供后续核对）

提交 `f94e54a` 的验证结果：

```bash
cd backend && make test-cov
# → 872 passed, 0 failed；Total coverage: 57.61%（≥50%）

cd backend && .venv/bin/python -m pytest tests/unit/ -q --no-cov          # → 447 passed
cd backend && .venv/bin/python -m pytest tests/integration/ -q --no-cov   # → 243 passed
```

相关约定已沉淀：

- `.trellis/spec/backend/quality-guidelines.md` — 测试隔离两条陷阱（模块级 `from ... import cache_service` 使属性替换失效；子层 conftest 不得覆盖 `JWT_SECRET`）
- `.trellis/spec/backend/database-guidelines.md` — Redis Hash 键编码（`decode_responses=True` 下必须用 str 键）
