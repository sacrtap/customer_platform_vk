# 同步任务 created_at 时区锁定修复计划

## Context

在消耗分析页点「手动同步」选日期提交后，同步日志页任务记录的「创建时间」在本地正确、staging 服务器少 8 小时。同时定时同步配置的任务也走同一创建链路。

排查结论（已逐行核实）：

- 手动同步与定时同步**同一条**创建链路：`backend/app/tasks/scheduler.py:361 _run` → `SyncTaskService.create_task`（`backend/app/services/sync_task_service.py:40`），手动同步路由 `backend/app/routes/sync_tasks.py create_sync_task` → 同一 `create_task`。两者 `SyncTask(...)` 实例化时都**未显式设 `created_at`**，统一由模型层 `TimestampMixin`（`backend/app/models/base.py:12`）的 `server_default=func.now()` 在 DB 侧写入。
- `TimestampMixin.created_at` 是 `DateTime`（**无 `timezone=True`**）→ PG `timestamp without time zone`，写入值 = **PG 会话时区**的墙钟。
- `create_async_engine`（`backend/app/main.py:192`，及 `backend/tests/integration/conftest.py:332`、`e2e/conftest.py:283`、`test_repository/conftest.py:39`、`test_audit_helpers_db.py:30`）**均未设 `server_settings`/`connect_args` 时区**，会话时区跟随服务器/容器 `TZ`。本地 `TZ=Asia/Shanghai` → 写入 CST 墙钟；staging 容器 `TZ=UTC` → 写入 UTC 墙钟，少 8 小时。
- 读出口 `_task_to_dict`（`sync_task_service.py:769`）已正确用 `naive_cst_datetime_str(task.created_at)`——**前提是 naive 列已存 CST 墙钟**。staging 因会话时区是 UTC，naive 列存的是 UTC 墙钟，再被 `naive_cst_datetime_str` 当 CST 格式化输出，等价于把 UTC 时刻当 CST 文本，最终显示比真实 CST 少 8 小时。

因此：**创建时间生成规则本身一致**（手动=定时，都靠 `func.now()`），不一致在「naive 列依赖会话时区」与「同表 `completed_at` 用 `datetime.now(timezone.utc)`+timestamptz、审计表 `executed_at` 用 `cst_now()` Python 侧」三套口径混排，而会话时区未被锁定。

目标：锁定 DB 会话时区为 `Asia/Shanghai`，使 naive 时间列在所有环境写入 CST 墙钟，对齐现有读出口假设，staging 显示正确。

## Approach

### 步骤 1：主应用引擎锁定会话时区

`backend/app/main.py:192` 的 `create_async_engine` 调用，新增 `connect_args`：

- 文件：`backend/app/main.py`
- 改动：在 `pool_size=20, max_overflow=10` 之后，增加
  ```python
  connect_args={
      "server_settings": {"TimeZone": "Asia/Shanghai"},
  },
  ```
- 原因：asyncpg 在每条连接建立时执行 `SET TIME ZONE 'Asia/Shanghai'`，`func.now()`（等价 `now()`）写 naive 列时取会话时区墙钟 = CST。timestamptz 列存的是绝对 UTC 时刻，不受影响，行为不变。
- 仅改 `database_engine is None` 分支（即应用自身创建引擎的路径，`backend/app/main.py:192`）；`elif isinstance(database_engine, AsyncEngine)` 分支接收外部传入引擎（测试 fixture 传自己的引擎），由步骤 2/3 一并覆盖。

### 步骤 2：测试 fixture 引擎同步锁定时区

为使集成/e2e 测试在 CI（UTC 容器）下复现与生产一致的会话时区，避免测试通过而生产偏差：

- `backend/tests/integration/conftest.py:332`：`create_async_engine` 增加 `connect_args={"server_settings": {"TimeZone": "Asia/Shanghai"}}`。
- `backend/tests/e2e/conftest.py:283`：同上。
- `backend/tests/test_repository/conftest.py:39`：同上。
- `backend/tests/unit/test_audit_helpers_db.py:30`：同上。
- 不改 `backend/scripts/*`（一次性脚本，无在线展示需求）。

### 步骤 3：新增断言「completed_at >= created_at」的回归测试

按 skill「必须断言相对关系」，新增针对 `list_tasks → _task_to_dict` 的回归测试，防再复发：

- 文件：`backend/tests/services/test_sync_task_service.py`（已存在，`create_task` 测试集所在文件）
- 新增测试 `test_list_tasks_created_at_cst_wallclock_completed_at_not_before`：
  - 构造一个 `SyncTask`（create_task 成功路径已有测试可复用），让其经历 running → completed（或用现有 `test_execute_task_*` 测试的 fixture 构造终态任务）。
  - 调 `service.list_tasks()` 取首条，断言：
    1. `data["list"][0]["created_at"]` 形如 `"YYYY-MM-DD HH:MM:SS"`（无 `T`、无 `+`、无 `Z`），即 naive_cst_datetime_str 输出。
    2. 把该字符串当 CST 解析后，与 `completed_at`（同样 CST 解析）比较满足 `completed_at >= created_at`。
  - 测试必须在 `TZ=UTC` 下也能跑通（CI 默认 UTC），以此证明会话时区锁定的有效性；若步骤 2 未改，本测试在 UTC CI 下会失败——这正是我们要的护栏。

### 不做的事（避免范围蔓延）

- 不改 `TimestampMixin` 列类型（`DateTime` → `DateTime(timezone=True)`）。那需 Alembic 迁移把现有 naive 列转 aware + 排查所有读出口，风险与本次目标不匹配（已与方案选择确认）。
- 不改 `_task_to_dict` 的 `naive_cst_datetime_str` / `utc_to_cst_datetime_str` 分工——会话时区锁定后它们各自行为正确。
- 不改 `executed_at=cst_now().strftime(...)`（Python 侧已正确，不依赖会话时区）。
- 不改定时任务触发器 `timezone=CST`（`scheduler.py:407`，已是 CST，正确）。

## Critical files & anchors

- `backend/app/main.py:192` — 主引擎 `create_async_engine`，加 `connect_args.server_settings.TimeZone`。本计划唯一线上行为改动点。
- `backend/app/models/base.py:12` — `TimestampMixin.created_at` 为 `DateTime`(naive)+`func.now()`，根因所在；本次不改，仅作为锁定时区后行为正确的依据。
- `backend/app/services/sync_task_service.py:742` — `_task_to_dict` 用 `naive_cst_datetime_str` 读 created_at；锁定会话时区后该假设成立。
- `backend/app/tasks/scheduler.py:361` — 定时同步 `_run` 复用 `create_task`，证明手动/定时同链路，无需单独改。
- `backend/tests/integration/conftest.py:332`（+ e2e/repository/audit_helpers 三处）— 测试引擎同步锁时区，保证 CI 与生产行为一致。

## Verification

前置：本地或 staging 可访问的 PostgreSQL（`settings.database_url`），后端 `cd backend && python -m app.main`（或现有启动方式），前端 `cd frontend && pnpm dev`。

1. 单元/集成测试（在 UTC 环境下验证会话时区锁定生效）：
   - `cd backend && TZ=UTC python -m pytest tests/services/test_sync_task_service.py tests/integration -q`
   - 预期：全绿；新增 `test_list_tasks_created_at_cst_wallclock_completed_at_not_before` 通过，证明会话时区被锁成 CST。
   - 反向校验：临时去掉步骤 1+2 的 `server_settings`，重跑该新测试，应失败（`created_at` 被 `naive_cst_datetime_str` 当 CST 但实际是 UTC 墙钟，关系断言仍可能过——此时改断言为「直接比 created_at 字符串解析后的真实 CST 时刻 vs 一个已知 CST 时刻」）。实现时若反向不可靠，改为直接查 DB：用 `psql -tAc "SHOW timezone;"` 在测试用的连接上确认会话时区为 `Asia/Shanghai`。
2. 端到端（staging 服务器复现修复）：
   - 部署改动到 staging 后，在消耗分析页点「手动同步」，选单日，提交。
   - 打开「同步日志」页，看该任务「创建时间」= 当前 CST 时刻（与本地一致），不再少 8 小时。
   - `curl -s 'http://<staging>/api/v1/sync-tasks?page=1&page_size=1'`（带 auth）→ `data.list[0].created_at` 形如 `"2026-10-26 15:30:12"`（CST 墙钟），`completed_at`（若完成）同为 CST 且 `>= created_at`。
3. DB 会话时区直查（staging）：
   - `psql <db> -tAc "SHOW timezone;"` → `Asia/Shanghai`（应用连接）。注意：直连 psql 会话是 psql 客户端时区，需查应用实际连接；可改用 `SELECT now()::text, (SELECT setting FROM pg_settings WHERE name='TimeZone');` 在应用会话执行的 SQL 日志里确认，或加临时日志。
4. 定时同步回归（staging，可选）：
   - 把定时同步配到「下 1 分钟」触发，等任务执行后查 sync_logs 页，确认系统自动任务的 created_at 同样为 CST。

## Assumptions & contingencies

- 假设：staging 容器 `TZ=UTC`（症状「少 8 小时」与之一致）。若 staging 实际 `TZ` 非 UTC 且仍少 8 小时，则根因另在别处（如反代/DB 服务器自身时区），需先 `docker exec ... date` 与 `psql ... SHOW timezone` 核实环境，再决定是否仍走本方案——会话时区锁定仍是对的方向，但需同时检查 PG 服务端 `timezone` 配置。
- 假设：asyncpg `server_settings` 在所用版本可用（asyncpg ≥0.23 支持）。若项目 asyncpg 过旧导致 `server_settings` 不生效，降级方案：在 `create_async_engine` 的 `event.listens_for("connect")` 里执行 `SET TIME ZONE 'Asia/Shanghai'`（同步事件监听器）。
- 假设：本地 `TZ=Asia/Shanghai` 是症状「本地正确」的原因。若开发者机器本地 TZ 非 CST 但仍正确显示，说明本地 PG 服务端 `timezone` 已是 CST，会话时区锁定不改变本地行为（幂等），不影响本方案正确性。
- 失败回退：步骤 1 上线后若出现「非 naive 列」（timestamptz 列如 `completed_at`）展示异常，那不是本改动引入的（timestamptz 与会话时区无关，存绝对时刻），按 skill「读出口裸 isoformat」另查；不在本计划范围。
