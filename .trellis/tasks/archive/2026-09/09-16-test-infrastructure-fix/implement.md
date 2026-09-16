# 实施计划：测试基础设施修复

## 有序实施清单

### Phase 1：REQ-1 消除同名冲突（单行配置，无行为变更）

1. **`backend/pytest.ini`**
   - `addopts = -v --tb=short` → `addopts = -v --tb=short --import-mode=importlib`
   - 同步更新文件内注释（现注释只说明 CI 追加参数），补一句说明为何使用 `importlib` 模式
   - 不改动 `testpaths` / `norecursedirs` / `markers` / `filterwarnings`

### Phase 2：REQ-3 `.trellis` 产物尾换行（单点修复）

2. **`.trellis/scripts/common/io.py`** — `write_text_atomic`（`f.write(text)` 处，约 143 行）
   - 改为写入前规范化：`f.write(text if text.endswith("\n") else text + "\n")`
   - `write_json` / `add_session.py` 的 `index.md` 重写路径均自动受益，无需分别改动

### Phase 3：REQ-2 修正遗留测试

3. **`backend/tests/test_customers_sorting.py`**
   - `TestSortConstants::test_allowed_sort_fields_contains_expected_fields`（约 96 行）：`expected_fields` 补齐为完整 17 项（10 Customer 原生 + 4 CustomerProfile + 1 CustomerBalance + 2 占位），并保留按类别分组的注释
   - `TestSortEdgeCases::test_all_allowed_sort_fields_are_valid_customer_attributes`（约 465-479 行）：按 4 类分别校验（`Customer` / `CustomerProfile` / `CustomerBalance` / 占位），废弃"非 industry_type_id 一律 hasattr(Customer)"的分支
   - 增补断言：白名单中每个字段在 `get_all_customers` 的排序分派中都有处理分支（防止"白名单加字段但排序未实现"）

4. **`backend/tests/test_repository/conftest.py`**（`sample_pricing_rule`，133-149 行）
   - `name`/`price_type`/`effective_from`/`is_active` → 真实字段：`customer_id`/`device_type`("X")/`layer_type`("single")/`pricing_type`("fixed")/`unit_price`/`effective_date`
   - 修正后 `test_pricing_repo.py` 的 4 个测试应全部通过（当前 3 error + 4 failed 的共同根因）

5. **`backend/tests/test_repository/test_customer_repo.py`**
   - `test_create`（90-101 行）：移除已不存在的 `contact_person`/`phone`，改用 `company_id`/`name`/`account_type`/`manager_id`；断言保持验证 CRUD 语义（`id` 生成、`created_at` 填充）
   - `test_search`（135-145 行）：**测试代码不改**，保留为回归保护（缺陷在生产侧）

6. **`backend/app/repository/customer_repo.py`**（`search` 方法，39 行）
   - `Customer.company_id.cast(str).ilike(...)` → `cast(Customer.company_id, String).ilike(...)`
   - 顶部补充 `from sqlalchemy import String, cast`（与既有 import 风格一致）
   - 移除该行现已失效的 `# pyright: ignore[reportArgumentType]`

### Phase 4：剩余失败清理（依据全量清单）

7. 以全量运行结果为准（`pytest tests/ --import-mode=importlib -q`）逐项处理 Phase 3 未覆盖的失败；每项遵循同一原则：**修引用而非删测试**，若某断言语义确已不成立则改写断言方式并在下方「测试删除登记」说明

### Phase 5：验证

8. 按下方「验证命令」逐条执行并留证
9. 实跑一轮 `.trellis` 脚本（`task.py create` → `archive` → `add_session.py`）验证 AC-6

## 验证命令

```bash
# AC-1：全量收集无 error
cd backend && .venv/bin/python -m pytest tests/ --collect-only -q -p no:warnings

# AC-2：CI 覆盖率门槛（退出码 0）
cd backend && make test-cov

# AC-3 / AC-4：CI 实际命令不得回退
cd backend && .venv/bin/python -m pytest tests/unit/ -q
cd backend && .venv/bin/python -m pytest tests/integration/ -q

# xdist 兼容性（pr-checks.yml 用 -n auto）
cd backend && .venv/bin/python -m pytest tests/unit/ -q -n auto --no-cov

# 本次修正的定点测试
cd backend && .venv/bin/python -m pytest tests/test_customers_sorting.py tests/test_repository/ -q --no-cov

# AC-5：workflow 文件未被改动
git status --short .github/workflows/    # 期望空

# AC-6：.trellis 产物尾换行
for f in .trellis/tasks/*/task.json .trellis/workspace/*/index.md; do
  [ -s "$f" ] && [ "$(tail -c1 "$f" | xxd -p)" != "0a" ] && echo "NO-EOL: $f"
done   # 期望无输出
```

## 风险文件 / 回滚点

| 文件 | 风险 | 回滚 |
|------|------|------|
| `backend/pytest.ini` | 低（模块解析策略变更） | 删 `--import-mode=importlib` |
| `.trellis/scripts/common/io.py` | 低（写入语义不变，仅补 `\n`） | `git revert` 单文件 |
| `backend/tests/test_customers_sorting.py` | 低（仅测试断言） | `git revert` 单文件 |
| `backend/tests/test_repository/conftest.py` | 低（仅 fixture） | `git revert` 单文件 |
| `backend/tests/test_repository/test_customer_repo.py` | 低（仅测试） | `git revert` 单文件 |
| `backend/app/repository/customer_repo.py` | **中（生产查询路径）** | `git revert` 单文件 |

## 测试删除登记（AC-7）

| 删除项 | 数量 | 等价覆盖证据 / 价值论证 | 独立核验 |
|---|---|---|---|
| `tests/test_analytics_service.py::TestCalculatePredictedAmount`（整类） | 9 个测试方法 | 被测目标 `AnalyticsService._calculate_predicted_amount` 已在 commit `1d65776`（全栈重构，2026-07-25）中被删除：`grep -rn "_calculate_predicted_amount" backend/app` **零匹配**，全库无调用者。重构后 `predict_monthly_payment` 改为直接取 `DailyConsumption.total_cost` 聚合值（`app/services/analytics.py:184,269,423`），不再按定价规则计算，故该类覆盖的 fixed/tiered/package 计算分支已无对应实现。新语义由**保留并修正**后的 `TestPredictMonthlyPayment`（5 例：`test_predict_monthly_payment_success` / `_with_customer_filter` / `_empty_pricing` / `_tiered_pricing` / `_package_pricing`）覆盖。 | 主会话已核验：工具 grep 无匹配 + `git log -S _calculate_predicted_amount -- app/services/analytics.py` 指向 1d65776 |

其余失败均为**修正引用**（未删除任何测试）：analytics 的 mock 结构（`side_effect` 次数、行字段）与新查询形状对齐；`test_cache.py` 的 TTL 期望值同步 300→600；`test_customers_api.py` 补 Redis 缓存清理。

## Phase 4 执行结果（30 个剩余失败的处置）

全部 30 个失败已完成处置，分组结果：

| 组 | 失败数 | 判定 | 处置 |
|---|---|---|---|
| analytics（`tests/test_analytics_service.py`） | 20（原报 18） | 全部测试过时 | mock 结构与重构后的单次联合查询形状对齐（`side_effect` 次数、行字段改为 dict）；`TestCalculatePredictedAmount` 整类删除（见上表） |
| sync（`tests/services/test_sync_task_service.py` + `tests/e2e/test_sync_task_e2e.py`） | 6 | 测试过时 + **1 处生产缺陷** | mock 补 `unmatched=0`；终态断言 `completed`→`partial`（实现区分 failed/partial/completed）；e2e 改用 Sanic `asgi_client`（原 `httpx` ASGI transport 与 Sanic 22.12 signals 不兼容）；新建 `tests/e2e/conftest.py` |
| cache + 隔离（`tests/test_cache.py` + `tests/integration/test_customers_api.py`） | 4 | 全部测试过时 | TTL 期望 300→600 同步；集成测试补 `invalidate_customer_cache()`，清理 Redis 缓存跨测试污染 |

**本任务共修复 3 处生产缺陷**（均有测试作为回归保护）：

1. `app/repository/customer_repo.py:40` —— `Customer.company_id.cast(str)` → `cast(Customer.company_id, String)`（`search()` 命中公司 ID 分支必抛 `TypeError`）。
2. `app/routes/sync_logs.py`（`get_sync_logs`）—— 返回的 `log_list` 遗漏 `task_id` 等字段，与 `SyncTaskLog` 模型列不一致。
3. `app/services/sync_task_service.py`（`get_progress`）—— 用 bytes 键（`b"status"`）查询 Redis hash，而生产客户端固定 `decode_responses=True`（`app/cache/base.py` 的 `redis.from_url`）返回 str 键 → 真实 Redis 路径下所有字段静默取默认值，任务进度恒为 `status=''` / `total_days=0`。改为键编码兼容（`raw()` 先查 str 键、回退 bytes 键）；新增回归用例 `test_get_progress_from_redis_str_keys`（修复前断言 `status == "running"` 失败）。

## Phase 6：全量会话隔离缺陷（e2e `test_full_sync_flow` 恒失败）

**症状**：全量 `pytest tests/` 中 `tests/e2e/test_sync_task_e2e.py::TestSyncTaskE2E::test_full_sync_flow` 恒失败（`status='' == 'completed'`），而单独跑 `pytest tests/e2e/` 通过。

**定位过程（二分收敛）**：`tests/unit/` 根目录 → 前 14 个 → 前 7 个 → 前 3 个通过 → 逐文件单测 → **`tests/unit/test_avatar_upload.py`** 为唯一触发文件（`+e2e` = 1 failed；`test_batch_update.py`、`test_correlation_middleware.py` 均全绿）。

**根因（两缺陷叠加，探针实测）**：

| 场景 | `sync_tasks.cache_service` | `/progress` 返回 |
|---|---|---|
| 单独跑 e2e | `MagicMock`（mock 生效） | `status='completed', total_days=4` ✓ |
| avatar + e2e | `CacheService`（真实对象，mock 失效） | 全空 `status='', total_days=0` ✗ |

1. **测试隔离缺陷**：`app/routes/sync_tasks.py:10` 以 `from app.cache.base import cache_service` 在**导入时**完成名字绑定；e2e 的 `mock_cache` 仅替换 `base.cache_service` 属性，对该绑定无效。`test_avatar_upload.py` 在**收集阶段**（`from app.routes.users import upload_avatar`）提前导入 `app.routes` 包，使绑定发生在 mock 替换之前 → 端点连真实 Redis；单独跑 e2e 时该导入发生在 mock 替换之后，故 mock 侥幸生效。
2. **生产缺陷 3**：真实 Redis 分支暴露键编码不匹配（见上表右列）。

**修复**：
- `tests/e2e/conftest.py` 的 `mock_cache` 显式覆盖 `app.routes.sync_tasks.cache_service`（teardown 还原）。
- `app/services/sync_task_service.py` 的 `get_progress` 兼容两种键编码。

**验证**：`pytest tests/unit/test_avatar_upload.py "tests/e2e/test_sync_task_e2e.py::TestSyncTaskE2E::test_full_sync_flow"` → **9 passed in 5.70s**（修复前该组合恒 1 failed，且 e2e 单测耗时 27s+）；探针确认 `sync_tasks.cache_service=MagicMock`。

## task.py start 前检查

- [ ] `prd.md` 需求与验收完整（REQ-1..3 / AC-1..7）
- [ ] `design.md` 覆盖三项决策与备选方案对比
- [ ] `implement.md` 含精确改动点、验证命令与回滚点
- [ ] 用户已 review 并批准本规划（当前待批）
