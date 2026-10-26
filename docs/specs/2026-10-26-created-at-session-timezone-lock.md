# created_at 时区锁定修复：naive 列墙钟基准的契约化

**日期**: 2026-10-26
**状态**: 已实施
**触发**: staging 同步日志「创建时间」比本地少 8 小时
**关联**: [2026-10-22 时区口径规范](./2026-10-22-timezone-cst-convention.md) 的「已知边界 1」落地

---

## Context

消耗分析页「手动同步」提交后，同步日志页任务「创建时间」本地正确、staging 少 8 小时。
定时同步走同一条创建链路（`scheduler._run` → `SyncTaskService.create_task`），症状相同。

### 根因（已逐行核实 + 本地 PG 实测复现）

`TimestampMixin.created_at` 是 `DateTime`（无 `timezone=True`）→ PG
`timestamp without time zone`，由 `server_default=func.now()` 在 **PG 会话时区**
写墙钟。`create_async_engine` 未设时区，会话时区跟随服务端/容器 TZ：

| 环境 | 会话时区 | naive 列写入 | 读出口 `naive_cst_datetime_str()` | 前端显示 |
|---|---|---|---|---|
| 本地 | Asia/Shanghai | `21:35` (CST) | `21:35` ✓ | 正确 |
| staging | UTC | `13:35` (UTC) | `13:35` ✗ | 少 8 小时 |

读出口假设「列里已是 CST 墙钟」直接 `strftime`（不再 `astimezone`），
staging 该前提被破坏。实测复现（会话时区设 UTC 后）：

```
func.now() → naive_col = 2026-10-26 13:35:34   (UTC 墙钟)
读出口 created_at   = 2026-10-26 13:35:34      ← 把 UTC 墙钟当 CST 输出
读出口 completed_at = 2026-10-26 21:35:34      ← 正确（timestamptz 转 CST）
```

即：**创建时间生成规则本身一致**（手动=定时都靠 `func.now()`），
不一致在「naive 列依赖会话时区」而会话时区未被锁定。

---

## Approach

### 1. 引擎锁定会话时区（唯一线上行为改动点）

`backend/app/main.py:192` 主引擎加：

```python
connect_args={"server_settings": {"TimeZone": "Asia/Shanghai"}}
```

asyncpg 在每条连接建立时执行 `SET TIME ZONE`，故 recycle/重连都一致。
timestamptz 列存绝对 UTC 时刻，不受影响。

**同步引擎（psycopg2）不认 `server_settings`**（报
`invalid connection option "server_settings"`），须用 libpq 的 `options`：

```python
create_engine(url, connect_args={"options": "-c timezone=Asia/Shanghai"})
```

### 2. 测试 fixture 同步锁定（避免「测试通过但生产偏差）

| 文件 | 引擎 |
|---|---|
| `tests/integration/conftest.py` | 异步 + 同步（两个常量） |
| `tests/e2e/conftest.py` | 异步 + 同步 |
| `tests/test_repository/conftest.py` | 异步 |
| `tests/integration/test_audit_helpers_db.py` | 异步 |

CI 的 `e2e-tests` job 未设 `TZ`（UTC runner），是本次必须覆盖测试引擎的直接原因。

### 3. Python 侧 naive 口径收敛（计划外，但必须做）

锁定使 naive 列语义从「跟随容器 TZ」变为「恒为 CST 墙钟」，
原本依赖「naive 列 == 本地 naive now」的比较点随之改变：

| 位置 | 原 | 改 |
|---|---|---|
| `sync_task_service.py:88` 卡死判定 | `datetime.now() - t.created_at` | `cst_now().replace(tzinfo=None)` |
| `sync_task_service.py:509,523` 运行时长 | `datetime.now()` | 拆 `wallclock_now`（naive CST）+ `utc_now`（aware UTC） |
| `sync_task_service.py:549` 卡死阈值 | `datetime.now() - timedelta(...)` | `cst_now().replace(tzinfo=None) - ...` |
| `sync_task_service.py:565` `completed_at` 写入 | `datetime.now()` | `datetime.now(timezone.utc)` |
| `sync_task_service.py:720` 24h 统计窗口 | `datetime.now()` | `cst_now().replace(tzinfo=None)` |
| `analytics.py:2389` 余额趋势窗口 | `datetime.utcnow().date()` | `cst_today()` |

**关键约束：aware 与 naive 不可混算。** 修复时先把 `now` 改成 `cst_now()`（aware），
`cst_now() - task.created_at`（naive）直接抛
`TypeError: can't subtract offset-naive and offset-aware datetimes`——
被现有单测当场抓住（`test_create_task_recovers_stuck_task_timeout`）。
故比较侧必须取 naive 形态，写 timestamptz 侧必须取 aware UTC，两者分开。

---

## Critical files

| 文件 | 改动 |
|---|---|
| `backend/app/main.py:192` | 主引擎锁定时区（唯一线上行为改动点） |
| `backend/tests/integration/conftest.py` | 新增 `TEST_ENGINE_CONNECT_ARGS` / `TEST_SYNC_ENGINE_CONNECT_ARGS`，两引擎锁定 |
| `backend/tests/e2e/conftest.py` | 同上 |
| `backend/tests/test_repository/conftest.py` | 异步引擎锁定 |
| `backend/tests/integration/test_audit_helpers_db.py` | 异步引擎锁定 |
| `backend/app/services/sync_task_service.py` | 6 处 naive 口径收敛 |
| `backend/app/services/analytics.py:2389` | 余额趋势窗口改 CST |
| `backend/tests/integration/test_sync_task_timezone.py` | 新增 9 个回归测试 |
| `.trellis/spec/backend/database-guidelines.md` | 新增「PG 会话时区契约」章节 |

---

## Verification

### 单元 / 集成（`TZ=UTC`）

| 项 | 结果 |
|---|---|
| `tests/services/test_sync_task_service.py` | 35 passed |
| `tests/integration/test_sync_task_timezone.py` | 9 passed |
| `tests/integration/test_audit_helpers_db.py` | 3 passed |
| `ruff check app/ tests/` | All checks passed |
| `pyright` | 0 errors, 0 warnings |

### 反向校验（证明测试非恒真）

**本地无法靠「移除 `connect_args`」证伪**：本地 PG 服务端时区恰好是
`Asia/Shanghai`，无锁定的连接也返回 CST，移除后测试照样全绿。
（这一点本身是重要发现——见下方「教训」。）

真正可证伪的做法：建一个**服务端时区为 UTC 的专用库**（等同 staging），
清除锁定参数后：

```
FAILED test_lock_overrides_utc_server_timezone
  AssertionError: 引擎未锁定会话时区（实得 UTC，同库无锁定会话为 UTC）...
FAILED test_func_now_writes_cst_wallclock_on_utc_server
  AssertionError: timestamptz 列应为 CST 表示（+08），实得 2026-10-26 13:41:44+00
```

→ 2 failed, 7 passed。恢复参数后回到 9 passed。护栏有效。

### 会话时区直查

```
-- 锁定后
SHOW timezone;        → Asia/Shanghai
SELECT now()::text;   → 2026-10-26 21:20:07+08

-- 未锁定（UTC 服务端库）
SHOW timezone;        → UTC
SELECT now()::text;   → 2026-10-26 13:20:08+00
```

---

## 教训

1. **「测试通过」不等于「锁定了行为」。** 本地 PG 服务端是 CST 时，
   `SHOW timezone == 'Asia/Shanghai'` 这条断言**恒真**，测不到修复。
   要证伪必须把环境的前提也改掉（这里是服务端时区 → UTC）。
   凡是「依赖外部环境默认值恰好正确」的断言，都要问一句：
   *把那个默认值改坏，测试还会绿吗？*
2. **naive 列 + 会话时区 = 隐式部署依赖。** `timestamp without time zone`
   的写入值取决于连接从哪来，与代码无关。跨环境部署时必须显式锁定，
   否则「本地对、线上错」且难以复现。
3. **先锁时区，再统一 Python 口径，顺序不能反。** naive datetime 写
   timestamptz 列会被解释为「会话时区的该墙钟」：锁定时区前把
   `datetime.now()` 改成 `cst_now()` 是**语义变更**，锁定后才是等价修复。
4. **aware / naive 混算会当场抛 `TypeError`**，这其实是好事——
   现有单测立刻抓住了错误的基准选择，比带病上线好。
