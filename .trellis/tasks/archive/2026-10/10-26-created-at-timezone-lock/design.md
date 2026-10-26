# 技术设计：同步任务 created_at 时区锁定修复

## 1. 问题模型

```
                写入（DB 侧）
SyncTask.created_at (timestamp without time zone)
    ← server_default=func.now() = now()
    ← 取 **PG 会话时区** 的墙钟
                 ↑
        create_async_engine 未设时区 → 跟随容器 TZ
        本地 TZ=Asia/Shanghai → CST 墙钟 ✓
        staging TZ=UTC         → UTC 墙钟 ✗

                读出（Python 侧）
_task_to_dict → naive_cst_datetime_str(created_at)
    ← 假设「naive 列已是 CST 墙钟」，直接 strftime（不再 astimezone）
    ← staging：UTC 墙钟被当 CST 输出 → 少 8 小时
```

结论：**创建时间生成规则一致**（手动=定时都靠 `func.now()`），不一致在
「naive 列依赖会话时区」而会话时区未被锁定。

## 2. 实证验证（本地 PG 实测，非推断）

用 `server_settings` 在本地库实测两种会话时区：

| 场景 | `SHOW timezone` | `func.now()` → naive 列 | `func.now()` → timestamptz 列 |
|---|---|---|---|
| 锁定 `Asia/Shanghai` | Asia/Shanghai | `2026-10-26 21:20:07` (CST) | `21:20:07+08` |
| 未锁定（UTC） | UTC | `2026-10-26 13:20:08` (UTC) | `13:20:08+00` |

→ 证实 R1：锁定时区后 naive 列恒写 CST 墙钟，timestamptz 列存绝对时刻不受影响。

**另一项关键实证**（决定改动影响面）：

| Python 侧写入值 | 会话 tz=CST 时 timestamptz 列存 | 会话 tz=UTC 时 timestamptz 列存 |
|---|---|---|
| naive `17:00` | `17:00+08` | `09:00+00` |
| aware UTC `17:00` | `次日 01:00+08` | `17:00+00` |

→ **naive datetime 写 timestamptz 列会被解释为「会话时区的 17:00」**。
因此：把某处从 `datetime.now()`（naive）改成 `cst_now()`（aware）写入
timestamptz 列，**在锁定时区前**是语义变更，**在锁定时区后**才是等价修复。
顺序不能反——必须先锁时区，再统一 Python 侧口径。

## 3. 改动范围

### 3.1 引擎锁定（计划步骤 1+2）

| 文件 | 锚点 | 改动 |
|---|---|---|
| `backend/app/main.py:192` | 主引擎 `create_async_engine` | 加 `connect_args={"server_settings": {"TimeZone": "Asia/Shanghai"}}` |
| `backend/tests/integration/conftest.py:332` | 测试异步引擎 | 同上 |
| `backend/tests/e2e/conftest.py:283` | 测试异步引擎 | 同上 |
| `backend/tests/test_repository/conftest.py:39` | 测试引擎 | 同上 |
| `backend/tests/integration/test_audit_helpers_db.py:30` | 测试引擎 | 同上（计划写的路径 `backend/tests/test_audit_helpers_db.py` 有误，实际在 `integration/`） |

不改 `backend/app/main.py:327` 的 `external_engine`（外部 MySQL，非 PG，无时区语义）。
不改 `backend/scripts/*`（一次性脚本，无在线展示需求）。

**同步引擎**（`create_engine` + psycopg2）：`integration/conftest.py:100`、
`e2e/conftest.py:69` 只用于 `create_all` 建表和 `test_user` 插入，不产生
面向用户的 `created_at` 读出口；但为口径一致也一并锁定（低成本，消除
「同库两套会话时区」的困惑）。

### 3.2 计划未覆盖的影响面（R5，本次必须处理）

锁定会话时区后，naive 列的语义从「跟随容器 TZ」变为「恒为 CST 墙钟」。
所有 **Python 侧 naive 时间 vs naive 列** 的比较点，其正确性依赖
「Python naive now == 列语义」：

| 位置 | 表达式 | 锁定时区后的行为 |
|---|---|---|
| `services/sync_task_service.py:88` | `datetime.now() - t.created_at`（卡死判定） | 容器 UTC 时少算 8h |
| `services/sync_task_service.py:499,539` | `datetime.now()` / `datetime.now() - timedelta(...)` vs `created_at` | 同上 |
| `services/sync_task_service.py:552` | `task.completed_at = datetime.now()`（timestamptz 列写 naive） | 见 §2 表：CST 会话下存 17:00+08（正确），UTC 会话下存 09:00+00（偏 8h） |
| `services/sync_task_service.py:700` | `datetime.now()` vs `created_at`（24h 统计） | 容器 UTC 时窗口偏移 |
| `services/backup_service.py:269,342` | `_NAIVE_NOW()` = `cst_now().replace(tzinfo=None)` | **已正确**（显式 CST），锁定后从「恰好对」变为「必然对」 |
| `services/analytics.py:2387` | `datetime.utcnow()` 推导趋势窗口，再 vs naive `created_at` | UTC 16:00-24:00 窗口偏 1 天 |

**处置原则**：
- 与 naive 列比较 → Python 侧一律显式取 CST 口径（`cst_now()` 或其 naive 形态），
  不依赖容器 TZ。这与 `_force_cst_timezone()` + `backup_service._NAIVE_NOW()`
  的既有约定一致，是收敛而非新约定。
- 写 timestamptz 列 → 用 `datetime.now(timezone.utc)`（`sync_task_service.py`
  已完成 7/9 处），剩余 `:552` 的 `datetime.now()` 一并修正。
- **不动**：`api_key.py` 的 `expires_at` 是 `DateTime` naive 列，但其写入侧
  `datetime.fromisoformat(...)` 取用户输入、比较用 `datetime.utcnow()`——
  这是**预先存在的口径混乱**，与本次改动无关（锁定时区不影响它，因为两端
  都不经 `func.now()`）。按「不扩范围」原则不在本次修，仅在 spec 记录待办。

### 3.3 回归测试（计划步骤 3）

计划要求的 `list_tasks → _task_to_dict` 断言在**纯 mock 测试里无法证明会话时区**：
`tests/services/test_sync_task_service.py` 全程 mock db，`created_at` 是手写的
naive 值，与 PG 会话时区无关。因此拆成两层：

1. **DB 层（真正锁定会话时区）**：新增 `tests/integration/test_sync_task_timezone.py`
   - 断言应用连接 `SHOW timezone` = `Asia/Shanghai`
   - 走真实 `create_task` → `list_tasks`，断言 `created_at` 是 CST 墙钟
     （与 `cst_now()` 的 naive 形态差 < 60s）
   - 断言 `completed_at >= created_at`（计划要求的相对关系）
   - 在 `TZ=UTC` 下运行；移除 `server_settings` 即失败（非恒真）
2. **序列化层（已有）**：`tests/services/test_sync_task_service.py::TestTaskToDictTimezone`
   已覆盖 `_task_to_dict` 的 CST 墙钟/相对关系断言，不重复。

## 4. 容器 tzdata 隐患（连带发现，需在 spec 记录）

`deploy/docker/Containerfile` 基于 `python:3.12-slim`，**未装 tzdata**。
`main.py:_force_cst_timezone()` 依赖 `time.tzset()` 解析 `Asia/Shanghai`；
无 tzdata 时 tzset 静默回退 UTC，`datetime.now()` 退化。

该函数已内置 `tm_gmtoff != 28800` 的 critical 告警兜底，且代码层已普遍改用
`cst_now()`，但 `executed_at`/`approved_at` 等 String 字段仍走 `datetime.now()`。
**本任务不装 tzdata**（属部署面改动，需 staging 验证），但这是「少 8 小时」
类问题的第二根因，必须沉淀到 spec 供后续排查。

## 5. 不做的事

- 不改 `TimestampMixin` 列类型（`DateTime` → `DateTime(timezone=True)`）：
  需 Alembic 迁移 + 排查全部读出口，风险与目标不匹配。
- 不改 `_task_to_dict` 读出口分工；不改 `executed_at=cst_now()` 写入侧。
- 不改 `scheduler.py:407` 的 `timezone=CST` 触发器（已正确）。
- 不改 `api_key` / `token_blacklist` 的 naive 列口径（预先存在，见 §3.2）。

## 6. Rollback

单点回退：移除 5 处 `connect_args` 即回到「跟随容器 TZ」原状，
无数据迁移、无 schema 变更、无读出口变更。风险仅在于回退后 staging 复现原症状。
