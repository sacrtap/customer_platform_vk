# 结算单明细文件生成链路故障根因与修复

日期：2026-10-21
范围：`backend/app/tasks/invoice_detail_generator.py`、`backend/app/services/invoice_excel.py`、`backend/app/main.py`、`backend/app/routes/billing/invoices.py`

## Context

批量生成结算单（`POST /api/v1/billing/invoices/generate-batch`）时，明细文件异步任务持续报错，大量结算单停在 `failed`/`pending`/`generating`。一次排查共定位 4 个独立根因（含 1 个触发契约 bug），每个都会让任务失败或静默不执行。

## 根因清单与修复

### 1. IllegalCharacterError：外部数据含控制字符

- 现象：`结算单 {id} 明细文件生成异常: 景发-怡景-12C cannot be used in worksheets.`，openpyxl `_bind_value → check_string` 抛错，整个 Excel 生成失败、单置 failed。
- 根因：外部 MySQL 的 `project_name` 等自由文本字段含 C0 控制字符（`\x0c` 等），XML 1.0 不允许，openpyxl 拒绝写入。间歇性失败、无客户共性（相邻客户一成一败），因为是数据驱动。
- 修复（`services/invoice_excel.py`）：
  - 模块级 `_ILLEGAL_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")`（`\t \n \r` 合法保留）；
  - `_clean_cell_text()` 静态方法；
  - `_row_to_dict` 出口对所有 str 字段清洗（外部数据唯一入口，覆盖 Sheet2 全部 26 字段）；
  - `_build_and_save_excel` 的 ws2 写入循环兜底清洗（防御其他构造来源）；
  - Sheet1 标题 `customer_name` 清洗（本地 DB，但客户名是用户可输入）。

### 2. naive/aware datetime 混用（被 except 吞掉的静默数据错误）

- 现象：`查询客户余额失败: can't subtract offset-naive and offset-aware datetimes`，但 Excel 照常生成、状态 completed——「当月充值金额」恒为 0，期初/结算后余额跟着错。
- 根因：`recharge_records.created_at` 是 `timestamp WITHOUT TIME ZONE`（naive 列），`invoices.period_start/period_end` 是 `timestamptz`（aware UTC）。把 aware datetime 直接传给 naive 列比较，asyncpg 抛 DataError；异常被 `_fetch_balance_info` 的 `except Exception` 吞掉只记 error。
- 修复（`services/invoice_excel.py:295-302`）：查询前 `period_start.replace(tzinfo=None)`、`(period_end + timedelta(seconds=1)).replace(tzinfo=None)`，并注释锁定契约。

### 3. QueuePool 连接池耗尽（批量并发超限）

- 现象：`结算单 {id} 明细文件生成异常: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00`，批量 81 张单时后到的任务成片 failed。
- 根因：`generate_invoices_batch` 为每张单 `add_job` 一次性并行触发（81 张瞬间并发）；本地 PG 引擎未配 pool（asyncpg 默认 5+10=15），外部 MySQL 引擎 `pool_size=5`。连接被占满后任务排队等 30s 超时。
- 修复：
  - `tasks/invoice_detail_generator.py`：模块级 `asyncio.Semaphore(5)` 包住任务体（`generate_invoice_detail` 收窄为入口，逻辑移入 `_generate_invoice_detail_inner`）——排队等待而非失败；
  - `main.py:96`：本地引擎 `create_async_engine(pool_size=20, max_overflow=10)`。

### 4. 触发契约 bug：任务从未入队（历史单全部卡 pending 的根因）

- 根因：`routes/billing/invoices.py` 触发循环取 `inv.get("id")`，但 service 返回键名是 `invoice_id`，`inv_id` 恒 None，任务从未入队。
- 修复：取 `invoice_id` 并注释锁定契约；回归测试 `test_generate_batch_triggers_detail_generation`。

### 5. APScheduler misfire 静默丢任务

- 根因：无 trigger 的 `add_job` 默认 `DateTrigger(now)` + `misfire_grace_time=1s`，事件循环繁忙（批量尾部连续 add_job）超 1s 即 `EVENT_JOB_MISSED` 静默丢弃，单永久卡 pending。
- 修复（`routes/billing/invoices.py:83-103`）：`misfire_grace_time=600, coalesce=True`。

## Critical files

- `backend/app/services/invoice_excel.py`：`_ILLEGAL_XML_CHARS_RE`、`_clean_cell_text`、`_row_to_dict`、`_fetch_balance_info`、`_build_and_save_excel`
- `backend/app/tasks/invoice_detail_generator.py`：`_detail_gen_semaphore`、`generate_invoice_detail` / `_generate_invoice_detail_inner`
- `backend/app/main.py`：本地引擎连接池参数
- `backend/app/routes/billing/invoices.py`：`_trigger_detail_generation`（misfire + invoice_id 契约）
- `backend/tests/unit/test_invoice_excel.py`：`TestInvoiceExcel_IllegalCharacters`、`TestInvoiceExcel_BalanceInfoTimezone`

## Verification

- 单测：`tests/unit/test_invoice_excel.py` 14 passed（含 3 个新增回归测试：清洗单测、`_row_to_dict` 字段级清洗、端到端脏数据生成 Excel）
- 端到端：8002 端口服务完整跑 `generate-batch`（81 张）→ 日志 0 ERROR，failed 单重跑后转 completed
- 静态：`ruff check app/`、`pyright` 全过

## 已知边界

- 进程被杀时 except 兜底来不及跑，单会卡在 `generating`——运维级边缘场景，自愈依赖前端「明细生成状态」抽屉的重新生成入口。
- 全库大量 `created_at` 是 naive 列、`invoices` 周期是 timestamptz，同类混用隐患仅修复了实际触发的一处；其他模块若出现 `offset-naive and offset-aware` 报错是同一模式。

---

## 追加：批量生成期间前端卡顿（2026-10-22）

### 现象
结算单明细批量生成过程中，在列表点击任意条目查看详情「或卡顿或点击无反馈」。

### 根因：AsyncIOExecutor + 同步 openpyxl = 事件循环冻结
- `tasks/scheduler.py:25` 用 `AsyncIOScheduler()` 未配 executors → APScheduler 3.x 默认 `AsyncIOExecutor` → async job 经 `create_task` **直接跑在 Web 服务主事件循环上**（与所有 HTTP 请求同一循环）。
- `services/invoice_excel.py` 的 `_build_and_save_excel` 是纯同步函数（29 列 × N 行逐格写 border/alignment + `wb.save` zip 序列化），零 await 点。Semaphore(5) 准入的 job 同步段背靠背独占循环。
- **实测证据**：4 个 job 并发时，正常 13ms 的详情接口被阻塞到 **17.16s**；81 张全量生成期间 20 次请求出现多次秒级阻塞。
- 次要：任务体第 4 步（查询计费项）到第 7 步 commit 之间 PG 连接+事务长挂，覆盖整个构建段（5 并发长占 5 条连接）。

### 修复
1. **主方案**（`invoice_excel.py:generate_detail_file`）：`_build_and_save_excel` 改 `await asyncio.to_thread(...)`——输入是已 fetchall 的纯内存数据、函数内不碰 DB，线程安全；事件循环恢复响应。
2. **配套**（`tasks/invoice_detail_generator.py`）：任务体三段化——① 查询（持主 session）→ commit+close 释放连接；② 构建（不持 DB）；③ 终态更新走 `session_factory` 短会话（`_update_final_status`）。`InvoiceExcelService` 新增可选 `session_factory`，`_fetch_balance_info` 分流到 `_query_balance_info(短会话)`。
3. 触发器传 `session_factory`（`routes/billing/invoices.py:93`）。

### 修复后实测
| 场景 | 修复前 | 修复后 |
|---|---|---|
| 8 张并发生成，25 次详情 | 最高 17.16s | 最高 0.557s |
| 81 张全量，60 次详情（1s 间隔） | 秒级冻结多次 | 最高 2.09s，中位 ~20ms |
| 单张 200 行构建耗时 | — | 0.474s（GIL 竞争下限） |

81 张全量回归：0 ERROR、全部 completed。

### 已知边界
- 剩余 0.5-2s 抖动来自 5 个 openpyxl 线程竞争 GIL（openpyxl 纯 Python，序列化段持 GIL），单张 200 行约 0.47s。若要进一步压缩需换 xlsxwriter 或进程池，当前量级（用户可感知从"无反馈"变为"<2s 响应"）已达成目标，不做过度优化。
