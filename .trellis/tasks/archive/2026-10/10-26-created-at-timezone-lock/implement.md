# 执行计划：同步任务 created_at 时区锁定修复

## Ordered Checklist

### 阶段 A：引擎锁定（计划步骤 1+2）

- [x] A1 `backend/app/main.py:192` 主引擎加 `connect_args={"server_settings": {"TimeZone": "Asia/Shanghai"}}`，附中文注释说明根因
- [x] A2 `backend/tests/integration/conftest.py:332` 测试异步引擎同步锁定
- [x] A3 `backend/tests/e2e/conftest.py:283` 测试异步引擎同步锁定
- [x] A4 `backend/tests/test_repository/conftest.py:39` 测试引擎同步锁定
- [x] A5 `backend/tests/integration/test_audit_helpers_db.py:30` 测试引擎同步锁定
- [x] A6 `backend/tests/integration/conftest.py:100` + `backend/tests/e2e/conftest.py:69` 同步引擎（psycopg2）同步锁定，统一口径

### 阶段 B：Python 侧 naive 口径收敛（R5，计划外）

- [x] B1 `services/sync_task_service.py:88` `datetime.now()` → `cst_now()`（卡死判定 vs naive `created_at`）
- [x] B2 `services/sync_task_service.py:499,539` 同上（`recover_stuck_tasks` / `check_stuck_tasks`）
- [x] B3 `services/sync_task_service.py:552` `task.completed_at = datetime.now()` → `datetime.now(timezone.utc)`（timestamptz 列）
- [x] B4 `services/sync_task_service.py:700` `datetime.now()` → `cst_now()`（24h 统计 vs naive `created_at`）
- [x] B5 `services/analytics.py:2387` 趋势窗口 `datetime.utcnow()` → `cst_now()`（vs naive `created_at`）

### 阶段 C：回归测试（计划步骤 3）

- [x] C1 新增 `backend/tests/integration/test_sync_task_timezone.py`：
      - `test_app_engine_session_timezone_is_cst`：应用连接 `SHOW timezone` = `Asia/Shanghai`
      - `test_created_at_is_cst_wallclock_under_utc_process`：真实 `create_task` → `list_tasks`，
        `created_at` 与 `cst_now()` naive 形态差 < 60s（证明写的是 CST 墙钟，非 UTC）
      - `test_completed_at_not_before_created_at`：终态任务 `completed_at >= created_at`
- [x] C2 确认 `tests/services/test_sync_task_service.py::TestTaskToDictTimezone` 仍绿（序列化层已有覆盖，不重复）

### 阶段 D：验证

- [x] D1 `cd backend && TZ=UTC python -m pytest tests/services/test_sync_task_service.py tests/integration/test_sync_task_timezone.py -q`
- [x] D2 **反向校验**：临时移除 A1 的 `server_settings` → C1 的 `test_created_at_is_cst_wallclock_under_utc_process` 必须失败；恢复
- [x] D3 `cd backend && ruff check app/ tests/`
- [x] D4 `cd backend && pyright` → 0 error
- [ ] D5 `cd backend && TZ=UTC python -m pytest tests/ -q` 与基线对比，无新增失败

### 阶段 E：收尾

- [x] E1 spec 沉淀（`.trellis/spec/backend/` 新增时区契约条目）
- [x] E2 归档计划文档至 `docs/specs/`
- [ ] E3 提交（遵循 git-commit 规范）

## Review Gates

- A 阶段完成后：先跑 D1 验证引擎锁定本身不破坏现有测试，再进 B 阶段
- B 阶段每改一处：确认该处比较对象的**列类型**（naive vs timestamptz），
  列类型决定用 `cst_now()` 还是 `datetime.now(timezone.utc)`，不可混用
- C 阶段完成后：必须做 D2 反向校验，否则测试可能恒真

## Rollback Points

- A 阶段：移除 5-6 处 `connect_args`，无副作用
- B 阶段：逐处独立回退（每处是纯 Python 侧口径修正）
- C 阶段：删除新增测试文件

## Key Facts (实测，非推断)

| 事实 | 依据 |
|---|---|
| `server_settings` 生效，`SHOW timezone` 返回 `Asia/Shanghai` | 本地 PG 实测 |
| 锁定时区后 `func.now()` 写 naive 列 = CST 墙钟 | 本地 PG 实测 |
| timestamptz 列存绝对时刻，不受会话时区影响 | 本地 PG 实测 |
| naive datetime 写 timestamptz 列 = 「会话时区的该墙钟」 | 本地 PG 实测 |
| asyncpg 0.29.0 `connect()` 支持 `server_settings` 参数 | `inspect.signature` 实测 |
| CI 后端 job 已设 `TZ: Asia/Shanghai`，e2e job 未设（UTC） | `.github/workflows/pr-checks.yml` 实测 |
| `deploy/docker/Containerfile` 基于 `python:3.12-slim` 未装 tzdata | Containerfile 实测 |

## 执行期发现（计划外，已处理）

| 发现 | 处置 |
|---|---|
| **psycopg2 不认 `server_settings`**（`invalid connection option`） | 同步引擎改用 `options="-c timezone=Asia/Shanghai"`，拆分 `TEST_ENGINE_CONNECT_ARGS` / `TEST_SYNC_ENGINE_CONNECT_ARGS` |
| **aware/naive 混算当场抛 TypeError** | 现有单测 `test_create_task_recovers_stuck_task_timeout` 抓住；比较侧取 `cst_now().replace(tzinfo=None)`，写 timestamptz 侧取 `datetime.now(timezone.utc)`，两者分开 |
| **本地 PG 服务端时区就是 CST → 断言恒真** | 「移除 `connect_args` 后测试失败」在本地不成立；改为建服务端时区 UTC 的专用库（`ALTER DATABASE ... SET timezone TO 'UTC'`）做对照，才真正证伪 |
| `test_audit_helpers_db.py` 实际在 `tests/integration/` 下 | 计划文档路径有误，按实际路径改 |
| `get_stats` 的 `datetime` 局部 import 改动后不再使用 | 一并移除，避免死 import |

## 验证结果

| 项 | 结果 |
|---|---|
| `TZ=UTC pytest tests/services/test_sync_task_service.py tests/integration/test_sync_task_timezone.py tests/integration/test_audit_helpers_db.py` | **47 passed** |
| 反向校验（清空 `_LOCKED_CONNECT_ARGS`） | **2 failed, 7 passed**（`test_lock_overrides_utc_server_timezone`、`test_func_now_writes_cst_wallclock_on_utc_server` 精确失败，报「实得 UTC」/「+00」） |
| 恢复参数后 | 回到 9 passed |
| `ruff check app/ tests/` | All checks passed |
| `pyright` | 0 errors, 0 warnings |
| 专用库清理 | fixture teardown 自动 DROP，无残留 |
