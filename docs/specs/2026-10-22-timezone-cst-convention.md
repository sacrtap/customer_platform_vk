# 时区口径规范：服务器本地时区固定 CST

**日期**: 2026-10-22
**状态**: 已实施
**触发**: nightly CI `assert 46 == 45` 失败 → 全量审计 `app/` 下时钟调用

---

## Context

系统从未显式声明时间基准，但全链路**隐式依赖「服务器本地时区 == CST」**：

| 环节 | 实际语义 | 证据 |
|---|---|---|
| DB 列 `created_at`/`updated_at` | `timestamp without time zone`，存 PG 会话时区的墙钟时间 | `app/models/base.py:15` |
| Python 写 String 字段（`approved_at` 等 9 个） | `datetime.now().isoformat()` 裸本地时间 | `app/services/billing.py:1662` 等 |
| 前端解析 | `new Date(str)` 把无时区后缀字符串当本地时间 | `frontend/src/utils/formatters.ts:24-26` |
| APScheduler cron | `CronTrigger(hour=2)` 不传 timezone 时用 `get_localzone()` | apscheduler 3.10.4 源码 |

三方能对齐的唯一原因是本地/生产时区恰好是 CST。**CI runner 默认 UTC**，于是「取日期」的代码全部断裂，「取时刻」的代码只偏移 8 小时（不产生错误日期，故长期未暴露）。

### 已发生的事故

nightly CI（UTC 18:00 = CST 次日 02:00）`test_burn_down_valid_package_uses_expiry_days` 失败：`date.today()` 返回 CST 次日，包年燃尽天数多算一天。

---

## Approach

### 1. 显式工具函数（`app/utils/timezone.py`）

| 函数 | 用途 |
|---|---|
| `cst_today() -> date` | 业务口径「今天」。**替代所有 `date.today()`** |
| `cst_now() -> datetime` | CST 墙钟时刻。与 DB `timestamp without time zone` 列做算术时用 |
| `utc_now() -> datetime` | UTC 截止时间戳（绝对比较，如 `completed_at`） |
| `local_date_range_to_utc()` | 前端日期范围 → UTC（既有，不变） |

选择规则：
- 统计窗口 / 业务自然日 / 月份边界 / 单号日期 → `cst_today()`
- 与 DB 墙钟时间比较或拼接 String 字段 → `cst_now()`
- 纯截止时间、跨时区绝对比较 → `utc_now()`
- SQL 层的「今天」 → `func.cast(func.timezone("Asia/Shanghai", func.now()), Date)`（**禁用 `func.current_date()`**，它跟随 PG 会话时区）

### 2. 进程级兜底（`app/main.py:_force_cst_timezone()`）

import 期执行 `os.environ["TZ"]="Asia/Shanghai"; time.tzset()`。

作用范围（这些代码因此自动变得时区无关）：
- 所有 `datetime.now()` / `date.today()`（P2 那批「截止时间」类代码）
- APScheduler `get_localzone()` → cron 触发时刻
- 数据库连接 PG 会话时区由 PG 服务器决定，**不受此影响**（见「已知边界」）

**这是兜底，不是替代。** 新代码仍必须用显式工具函数——兜底让旧代码安全，显式函数让新代码可测（不依赖进程全局状态）。

### 3. 修复清单

#### P0 — 业务日期错误

| 位置 | 修复 |
|---|---|
| `app/tasks/invoice_generator.py:31` 月度结算周期 | `date.today()` → `cst_today()` |
| `app/tasks/scheduler.py:285` 每日同步目标日 | `date.today()` → `cst_today()` |
| `app/routes/analytics.py:268` 手动同步昨日 | `date.today()` → `cst_today()` |
| `app/routes/customers.py:370` 本月新增客户 | `date.today()` → `cst_today()` |
| `app/services/analytics.py:3082` 仪表盘本月待办 | `datetime.now().date()` → `cst_today()` |
| `app/routes/billing/invoices.py:1850,1983` 单号日期前缀 | `datetime.now().strftime()` → `cst_today().strftime()` |
| `app/services/billing.py:1397` 单创建单号 | 同上 |

#### P1 — 统计/展示偏差

| 位置 | 修复 |
|---|---|
| `app/services/analytics.py:1963` 预测当前月 | `datetime.now().month` → `cst_today().month` |
| `app/routes/customers.py:208` 30 天消耗窗口 | `date.today()` → `cst_today()` |
| `app/services/analytics.py:3012` 近 7 天异常 | `datetime.now()` → `cst_now()` |
| `app/services/analytics.py:3050-3053` 下次同步时间 | `datetime.now()` → `cst_now()` |

#### cron 时区

`app/tasks/scheduler.py` 全部 5 处 `CronTrigger` 加 `timezone=CST`（月度结算 02:00、逾期邮件 09:00、临时文件 03:00、webhook 04:00、每日同步按配置）。

#### SQL 层

`app/routes/billing/balances.py` 两处 `func.current_date()` → `func.cast(func.timezone("Asia/Shanghai", func.now()), Date)`（PR #57）。

### 4. CI 时区对齐

| Workflow | Job | 方式 |
|---|---|---|
| `pr-checks.yml` | `backend-tests` | job 级 `env: TZ` |
| `pr-checks.yml` | `backend-integration-tests` | job 级 `env: TZ` |
| `pr-checks.yml` | `backend-integration-full` | job 级 `env: TZ` |
| `ci.yml` | `backend-smoke` | job 级 `env: TZ` |
| `e2e-full.yml` | `Start backend server` | step 级 `env: TZ` |

**必须加**：否则「只在 UTC 特定时段触发」的时区缺陷在 CI 继续隐形——本地过、生产挂。

---

## Critical files

| 文件 | 改动 |
|---|---|
| `backend/app/utils/timezone.py` | 新增 `cst_today()` / `cst_now()` |
| `backend/app/main.py` | 新增 `_force_cst_timezone()` + import 期调用 |
| `backend/app/tasks/invoice_generator.py` | 月度周期日期 |
| `backend/app/tasks/scheduler.py` | 每日同步目标日 + 5 处 cron `timezone=CST` |
| `backend/app/routes/analytics.py` | 手动同步昨日 |
| `backend/app/routes/customers.py` | 本月新增 + 30 天窗口 |
| `backend/app/routes/billing/invoices.py` | 单号日期前缀（2 处） |
| `backend/app/services/billing.py` | 单创建单号日期 |
| `backend/app/services/analytics.py` | 4 处（当前月/近7天/下次同步/本月待办） |
| `backend/tests/unit/test_timezone_utils.py` | `cst_today()` 契约测试 |
| `.github/workflows/{pr-checks,ci,e2e-full}.yml` | TZ 环境变量 |

---

## Verification

### 单元/集成

| 项 | 结果 |
|---|---|
| 单测（本地 CST） | 655 passed |
| 单测（`TZ=UTC`） | 655 passed |
| 集成测试 | 76 passed |
| ruff / pyright | 全过 |

### 功能验证（UTC 环境实测）

| 场景 | 验证方式 | 结果 |
|---|---|---|
| 月度结算周期 | `TZ=UTC` 下 import `invoice_generator` 并 monkeypatch session，断言周期为 CST 上月 | 见 `test_invoice_generator_cst.py` |
| 每日同步目标日 | 同上，断言 `start_date == cst_today() - 1` | 同上 |
| 单号日期前缀 | `TZ=UTC` 下生成单号，断言前缀 == CST 日期 | 同上 |
| cron 触发时刻 | `TZ=UTC` 下 `CronTrigger(hour=2).get_next_fire_time()` | `2026-11-01 02:00:00+08:00` |
| 时区兜底 | `TZ=UTC` 下 import `app.main` 后 `date.today()`/`tzname`/`get_localzone()` | 均为 CST |

### 数据验证（UTC vs CST 结果一致性）

| 对比项 | CST 环境 | UTC 环境 | 一致 |
|---|---|---|---|
| `cst_today()` | 2026-10-22 | 2026-10-22 | ✅ |
| 月度结算周期 | 2026-09-01 ~ 09-30 | 2026-09-01 ~ 09-30 | ✅ |
| 每日同步目标日 | 2026-10-21 | 2026-10-21 | ✅ |
| 单号前缀 | INV-20261022- | INV-20261022- | ✅ |
| cron 下次触发 | 02:00+08:00 | 02:00+08:00 | ✅ |

---

## 已知边界（未在本次范围）

> **2026-10-26 更新**：边界 1 已落地，见「已解决」小节。边界 2/3 仍开放。

### 已解决：边界 1 — PG 会话时区

**2026-10-26 已修复**（`fix/created-at-session-timezone-lock`）。所有引擎
（`app/main.py` + 4 处测试 fixture）锁定 `TimeZone=Asia/Shanghai`，
naive 列在所有环境写 CST 墙钟。契约与 Python 侧取值规则已写入
`.trellis/spec/backend/database-guidelines.md`「PG 会话时区契约」；
可证伪的回归测试见 `backend/tests/integration/test_sync_task_timezone.py`。

同次修复连带收敛的 Python 侧口径（原本依赖进程 TZ 恰好为 CST）：

| 位置 | 改动 |
|---|---|
| `services/sync_task_service.py:88` 卡死判定 | `datetime.now()` → `cst_now().replace(tzinfo=None)` |
| `services/sync_task_service.py:509` 运行时长基准 | 同上，并拆出独立的 UTC 基准写 `completed_at` |
| `services/sync_task_service.py:549` 卡死阈值 | 同上 |
| `services/sync_task_service.py:565` `completed_at` 写入 | `datetime.now()` → `datetime.now(timezone.utc)` |
| `services/sync_task_service.py:720` 24h 统计窗口 | 同上 naive CST 基准 |
| `services/analytics.py:2389` 余额趋势窗口 | `datetime.utcnow().date()` → `cst_today()` |

仍开放的边界：

1. ~~**PG 会话时区不受 `tzset()` 影响**~~ → 已解决，见上。
2. **`approved_at` 等 String 字段的 naive 时间戳歧义**（方案 C，未做）。改为 `datetime.now(CST).isoformat()` 是行为变更：前端 `new Date()` 解析语义变化 + 存量数据是 naive 值，新旧混排会显示跳变 8 小时。需前端配合 + 数据迁移评估，独立 PR。
3. **`email_tasks.py:70` 的 `due_date` 渲染失败**（与时区无关的既有 bug）。`Invoice` 模型无 `due_date` 字段，模板 `{{ (today - invoice.due_date).days }}` 抛 `UndefinedError`，被 `render_template` 的 `except` 捕获 → 逾期提醒邮件正文实际是「模板渲染失败」。需产品确认逾期口径后单独修。
4. **容器 tzdata 缺失**（2026-10-26 新记录）。`deploy/docker/Containerfile` 基于 `python:3.12-slim` 未装 tzdata，`time.tzset()` 解析 `Asia/Shanghai` 静默回退 UTC。`_force_cst_timezone()` 已告警兜底、代码层已普遍用显式工具函数，但 `executed_at` 等 String 字段仍走 `datetime.now()`。建议部署面加装 tzdata（需 staging 验证，未在本次范围）。
5. **`api_key` / `token_blacklist` 的 naive 列口径混乱**（2026-10-26 新记录，预先存在）。`ApiKey.expires_at` 是 `DateTime` naive 列，写入取用户输入 `datetime.fromisoformat(...)`、比较用 `datetime.utcnow()`，两端都不经 `func.now()`，故不受本次锁定影响；但同一列混用「用户输入的本地时间」与「UTC」两种语义，属独立隐患。

---

## 规则（写入约定）

1. **禁止新增 `date.today()` / `datetime.now()` 于业务日期计算**。用 `cst_today()` / `cst_now()` / `utc_now()`。
2. **禁止 `func.current_date()`**。SQL 层「今天」用 `func.cast(func.timezone("Asia/Shanghai", func.now()), Date)`。
3. **新增 cron 必须传 `timezone=CST`**。
4. **部署环境必须设 `TZ=Asia/Shanghai`**（`main.py` 会兜底，但显式设置便于排查；CI 已在 5 个 job 显式声明）。
5. **新增 DB 时间戳列优先 `DateTime(timezone=True)`**（存 UTC），从根上避免墙钟时间歧义。既有列不动。
