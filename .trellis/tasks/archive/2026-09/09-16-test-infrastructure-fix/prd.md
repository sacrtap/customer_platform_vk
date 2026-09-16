# 测试基础设施修复：同名文件冲突、遗留测试字段过时与 pre-commit 摩擦

## Goal

让「全量后端测试」重新可用：修复三个互相独立、共同导致 `make test-cov`（`pytest tests/ --cov=app --cov-fail-under=50`）失效的问题，并消除 `.trellis` 脚本 auto-commit 反复被 pre-commit 阻断的摩擦。

- **A** 同名测试文件跨目录共存 → `pytest tests/` 收集阶段中断（2 个 `import file mismatch`）
- **B** `tests/` 根目录遗留测试引用已变更的模型接口 → 全量运行 34 failed + 3 errors
- **C** `.trellis` 脚本写出的状态文件缺末尾换行 → pre-commit `end-of-file-fixer` 每次改写并阻断 auto-commit

## Background（实测证据）

### A. 同名测试文件跨目录共存

`cd backend && .venv/bin/python -m pytest tests/` → 收集中断：

```
import file mismatch:
imported module 'test_analytics_service' has this __file__ attribute:
  .../backend/tests/test_analytics_service.py
which is not the same as the test file we want to collect:
  .../backend/tests/unit/services/test_analytics_service.py
```

两组冲突对（均已核实为**互补而非重复**，实测统计）：

| 冲突对 | 规模 | 内容关系 |
|---|---|---|
| `tests/test_analytics_service.py` | 20 个测试类 / **64 个测试方法**（消费趋势、Top 客户、健康分、预测回款、dashboard、边界用例…） | 覆盖广度大 |
| `tests/unit/services/test_analytics_service.py` | 2 个测试类 / 6 个测试方法 | 含 root 版**没有**的回归点：`get_unit_prices` 表缺失/空表兜底、`get_inactive_customers` 的 datetime/date 混合相减 |
| `tests/unit/test_correlation_middleware.py` | 278 行 / 15 用例 | 单元层：request-id normalize、`RequestIdFilter` 幂等、uvicorn formatter 回归 |
| `tests/integration/test_correlation_middleware.py` | 107 行 / 5 用例 | 集成层：真实 app 中间件栈顺序、日志共享、认证先后 |

**根因**：`backend/pytest.ini` 未设 `--import-mode`，默认 `prepend` 以 basename 注册测试模块；`tests/` 下无 `__init__.py`（仅 `tests/test_repository/__init__.py` 存在）。

**影响面（重要修正）**：CI **不跑**全量 —— `ci.yml` 与 `pr-checks.yml` 分别只跑 `pytest tests/unit/`（实测 447 passed）与 `pytest tests/integration/`。因此受影响的仅是开发者本地的 `make test-cov` 与任何 `pytest tests/` 调用，CI 门槛未被击穿。

### B. `tests/` 根目录遗留测试引用过时接口

`pytest tests/ --import-mode=importlib` → `34 failed, 843 passed, 3 errors`。已定位子集（`tests/test_customers_sorting.py` + `tests/test_repository/` 单独运行 = 4 failed / 40 passed / 3 errors）：

| 失败/错误 | 位置 | 根因 |
|---|---|---|
| `test_allowed_sort_fields_contains_expected_fields` | `tests/test_customers_sorting.py` | 断言期望 10 项字段，而 `app/services/customers.py:19-41` 的 `ALLOWED_SORT_FIELDS` 实为 **17 项**（10 Customer 原生 + 4 CustomerProfile + 1 CustomerBalance + 2 占位） |
| `test_all_allowed_sort_fields_are_valid_customer_attributes` | 同上 | `hasattr(Customer, field)` 对 `consume_level` 等为 False —— 该字段实际在 `CustomerProfile`；此类 JOIN/派生字段（`industry`/`balance`/`usage_30d`/`health`）本就不在 `Customer` 类上，断言方式不成立 |
| `TestCustomerRepository::test_create` | `tests/test_repository/test_customer_repo.py` | `Customer(contact_person=…, phone=…)` —— 两字段已从模型移除（`app/models/customers.py:17-61` 无此列） |
| `TestCustomerRepository::test_search` | 同上 | 查询构造报 `Object '' associated with '.type' attribute is not a TypeEngine class` |
| `TestPricingRepository` ×3（error） | `tests/test_repository/test_pricing_repo.py` | fixture `sample_pricing_rule`（`tests/test_repository/conftest.py:133-149`）传入 `name`/`price_type`/`effective_from`/`is_active` —— `PricingRule` 真实字段为 `pricing_type`/`effective_date`/`expiry_date`（`app/models/billing.py:85-113`） |

**规范定位**：`.omp/rules/testing.md` 与 `.trellis/spec/backend/quality-guidelines.md` 的测试分层为 `unit` / `integration` / `services` / `e2e` / `performance`，**不含 `tests/` 根目录** —— 该层为历史遗留，但其中多数文件仍有效（`test_cache.py`、`test_email_service.py`、`test_repository/test_balance_repo.py`、`test_repository/test_invoice_repo.py`、`test_analytics_service.py` 均通过）。

### C. `.trellis` 脚本产物缺末尾换行

现象：`task.py archive` / `add_session.py` 报 `Archive moved on disk, but git auto-commit did not complete`，pre-commit 输出 `hook id: end-of-file-fixer / files were modified by this hook / Fixing .trellis/.../task.json`（本次会话连续发生 3 次，均需手动补提交）。

根因（已定位到写入端）：`.trellis/scripts/common/io.py` 的 `write_json` 用 `json.dumps(...)`（输出不以 `\n` 结尾）后交给 `write_text_atomic` 原样写入；`add_session.py:1059` 以 `"\n".join(new_lines)` 重写 `index.md`（同样无尾换行）。`.pre-commit-config.yaml` 的 `end-of-file-fixer` 未设 `files`/`exclude`，覆盖全部 tracked 文件，故每次改写。

## Requirements

- **REQ-1** `pytest tests/` 全量可收集、可运行（消除 2 个 collection error），且**不得牺牲任何现有测试覆盖**：两组同名文件的互补内容均须纳入执行。
- **REQ-2** `tests/` 下因模型重构而失效的测试，修正到当前真实接口；仅当某测试的断言语义已不成立（而非可修正）时，改写其断言方式或删除，删除须附等价覆盖证据或价值论证。
- **REQ-3** `.trellis` 脚本写出的状态文件（`task.json`、`index.md`、journal）以换行结尾，使 `end-of-file-fixer` 不再改写它们；修复须落在写入端（生成时即合规），不得依赖 pre-commit 排除。

## Acceptance Criteria

- [x] **AC-1** `pytest tests/ --collect-only -q` → **0 errors，872 collected**（修复前 prepend 模式实测 `857 collected, 2 errors`；同一 HEAD 树改用 `importlib` 收集 880 项 = 857 + 被同名冲突遮蔽的 23 项；当前树 872 = 880 − 删除 9（`TestCalculatePredictedAmount`） + 新增 1（`test_get_progress_from_redis_str_keys`））。
- [x] **AC-2** `cd backend && make test-cov` **退出码 0** —— 实测 **872 passed / 0 failed**，`Total coverage: 57.53%`（≥ 50%）。修复过程中额外消除 3 处生产缺陷与 2 处测试隔离缺陷（见 Notes）。
- [x] **AC-3** `cd backend && .venv/bin/python -m pytest tests/unit/ -q` → **447 passed**（`ci.yml` 实际命令，无回退）。
- [x] **AC-4** `cd backend && .venv/bin/python -m pytest tests/integration/ -q` → **243 passed**（`pr-checks.yml` 实际命令，全通过）。
- [x] **AC-5** 未修改 `.github/workflows/` 下任何文件。
- [x] **AC-6** `.trellis` 产物末尾换行已实测（`task.json`／`index.md`／`journal-1.md` 末字节均为 `0a`）；修复落在写入端 `io.py:write_text_atomic`。
- [x] **AC-7** 删除 9 个测试（`TestCalculatePredictedAmount` 整类），等价覆盖证据与独立核验已登记于 `implement.md`「测试删除登记」。

## Out of Scope

- `tests/` 根目录遗留测试向规范分层目录（`tests/unit/`、`tests/integration/`、`tests/services/`）的**迁移**（属结构调整，价值独立，可在后续任务评估）。
- `tests/performance_test.py`（Locust 脚本；实测 `collected 0 items`，因文件名不匹配 `python_files = test_*.py` 而根本未被收集，无需处理）。
- 任何 CI workflow 变更（`ci.yml` / `pr-checks.yml` / `backend-integration.yml`）。
- 新增测试覆盖（本次目标是让既有套件恢复健康，非扩充）。

## Notes

- 本次修复的**主体**是测试基础设施（`pytest.ini`、测试文件、`.trellis` 脚本）；但在「把遗留测试修正到当前接口」的过程中暴露出并修复了 **3 处生产缺陷**（均以测试作为回归保护）：
  1. `app/repository/customer_repo.py:40` —— `Customer.company_id.cast(str)` → `cast(Customer.company_id, String)`（`search()` 命中公司 ID 分支必抛 `TypeError`）。
  2. `app/routes/sync_logs.py`（`get_sync_logs`）—— 返回体遗漏 `task_id`/`operator_id`/`start_date`/`end_date`，与 `SyncTaskLog` 模型列不一致。
  3. `app/services/sync_task_service.py`（`get_progress`）—— 用 **bytes 键**（`b"status"`）查询 Redis hash，而生产客户端固定 `decode_responses=True`（`app/cache/base.py` 的 `redis.from_url`）返回 **str 键**，导致真实 Redis 路径下**所有字段静默取默认值**：任务进度恒为 `status=''`、`total_days=0`。已改为兼容两种键编码，并补 str 键回归用例 `test_get_progress_from_redis_str_keys`（修复前该用例断言失败）。
- 另修复两处**测试隔离缺陷**：
  1. `tests/integration/conftest.py` 与 `tests/e2e/conftest.py` 各自强制设置不同的 `JWT_SECRET`，而 `app/config.py:108` 的 settings 是模块级单例（`lru_cache`）—— 全量会话中最后加载者胜出，导致 e2e 登录成功后请求仍 401。现统一由 `tests/conftest.py` 的 `setdefault` 提供。
  2. `tests/e2e/conftest.py` 的 `mock_cache` 只替换 `base.cache_service` 属性，而 `app/routes/sync_tasks.py` 以 `from app.cache.base import cache_service` 在**导入时**完成名字绑定 —— 替换对其无效，端点绕过 mock 直连真实 Redis。该失效仅在「先导入 `app.routes` 的测试文件（如 `tests/unit/test_avatar_upload.py`）与本 e2e 同会话」时才显现：真实 Redis 分支被走到，叠加缺陷 3 使 `test_full_sync_flow` 恒失败。现由 `mock_cache` 显式覆盖该模块引用。
- CI 未被击穿（其命令为分目录执行），但本地 `make test-cov` 与全量收集的失效会持续掩盖 B 类问题，故仍需修复。
