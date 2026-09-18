# Code Review：三分支合并进 main（import-export-optimization / sync-execution-info / dashboard-visual-fixes）

- **审查范围**：`1a576b6..HEAD`（三个功能分支合并带来的全部变更，172 文件 / +16385 行）
- **审查工具**：open-code-review（`ocr review --from 1a576b6 --to HEAD`，provider: bifrost / deepseek-v4-flash，effort: low）
- **审查日期**：2026-09-18
- **文件数**：55 文件纳入审查（排除 .trellis/tests/scripts/docs/alembic 等），分批完成
- **结果**：有效发现 **21 条**（2 critical 等价处理为 high、5 medium、14 low），**全部已修复或说明**；提交前验证：后端语法+ruff、相关测试 151 passed、前端 type-check 通过

---

## 审查过程说明

由于 provider 限制（HTTP 524/429/502 波动），审查分 3 批执行：

| 批次 | 范围 | 结果 |
|---|---|---|
| 1 | 生产代码 55 文件（backend/app + frontend/src） | 22 条评论；29 文件组失败 |
| 2 | 重试失败文件组（31 文件） | 3 条评论；24 文件组仍失败 |
| 3 | 聚焦同步模块（34 文件，并发 4） | 6 条评论；sync 核心组最终成功 |

三批共获取有效发现 21 条（含 2 条确认的误报），未覆盖到的文件组（customers 路由、billing 部分路由）因 provider 连续失败未能产出评论，已在「遗留风险」中说明。

---

## Critical

无。

## High（1 条）

### 1. `frontend/src/views/system/SyncLogs.vue:41-47` [bug] — a-time-picker 未设置 value-format

**问题**：用户选择时间后 `v-model` 绑定为 dayjs 对象而非 `"HH:mm"` 字符串，保存时经 JSON 序列化为 ISO 时间串（如 `2026-09-18T15:30:00.000Z`），无法通过后端 `TIME_PATTERN（HH:MM）` 校验，导致修改执行时间后保存必然返回 400。

**修复**：补充 `value-format="HH:mm"`，保持字符串绑定，与项目其他日期选择器约定一致。

## Medium（5 条）

### 2. `frontend/src/views/system/SyncLogs.vue:370-375` [bug] — 执行信息兜底盲区

**问题**：后端 `_execution_status` 仅对 failed→error、partial→warning 回退，`cancelled` 状态以及历史 `completed 且 failed_count>0` 的任务会回退为绿色"正常"，与状态列展示矛盾；且历史失败任务无明细记录时，任务级 `error_message` 完全不可达。

**修复**：
- 前端 `getExecutionColor/getExecutionText`：`cancelled` 显示灰色"已取消"，`completed + failed_count>0` 兜底为金色"警告"；
- 抽屉空态：无明细时展示 `task.error_message`（历史失败任务错误信息可达）。

### 3. `frontend/src/utils/tiers.ts:38` [bug] — parseTiers 静默丢弃缺字段条目

**问题**：新实现 `.filter((t) => t.min != null && t.price != null)` 会**静默丢弃**缺 min/price 的条目，且不对字符串数字做收敛。后端注释明确「存量脏数据不做迁移」，用户编辑含缺字段 tier 的规则时该档会被永久删除。

**修复**：改为 map 内收敛 `Number(t.min) || 0` / `Number(t.price) || 0`（与旧实现 `Number(x)||0` 语义一致），保留所有条目。

### 4. `backend/app/routes/analytics.py:280` [bug] — 后台同步任务无异常处理

**问题**：`request.app.add_task(run_task())` 直接调度且未持有 Task 句柄、无 done 回调：若 `execute_task` 在其内部 try/finally 之外失败（session 创建/连接异常），异常仅被 asyncio 默认处理器记录，调用方无从感知；任务状态停留在 pending/running，Redis 锁只能等 30 分钟 TTL 兜底。

**修复**：`run_task` 内包 try/except，记录 `logger.error(..., exc_info=True)`，便于排查。

### 5. `backend/app/services/analytics.py:2674-2675` [bug] — 风险客户预取窗口与风险程度无关

**问题**：`ORDER BY Customer.id LIMIT limit*3` 预取再内存筛选：窗口按客户 id 排序，与风险程度无关。当窗口内余额充足的客户占比高时，真正的高风险客户（如无余额记录客户）会被系统性漏报，返回数量常小于 limit，且结果不按风险严重度排序。

**修复**：余额过滤与排序下沉 SQL——`risk_score = case((balance_missing, 50), else_=30)`，`WHERE or_(balance_missing, remaining < 1000)`，`ORDER BY risk_score DESC, Customer.id`，`LIMIT limit`；补充流失客户时对 `get_inactive_customers` 传 `limit`（新增参数，SQL 加 LIMIT，避免全量物化历史流失客户）。

### 6. `backend/app/routes/billing/invoices.py:1460` [other] — 损坏 Excel 解析失败返回 500

**问题**：上传文件通过扩展名校验后若内容损坏（伪 xlsx、加密工作簿等），`pd.read_excel` 抛出的 `BadZipFile/InvalidFileException` 冒泡到 catch-all 返回 500，前端误判为服务故障。文件内容是客户端可控输入，解析失败应返回 400。

**修复**：`to_thread(read_import_dataframe, ...)` 单独 try/except，返回 400 `INVALID_FILE`「文件无法解析，请确认是有效的 .xlsx 文件」；并增加 `df.empty` 检查（仅表头无数据行时拒绝，避免虚假成功反馈）。

---

## Low（14 条，均已处理）

| # | 位置 | 类别 | 问题 → 处理 |
|---|---|---|---|
| 7 | SyncLogs.vue:68-74 | style | 嵌套三元 → 提取 `getNextRunText()` 方法 |
| 8 | SyncLogs.vue:184 | style | `==` → `===`（coreference 严格相等） |
| 9 | SyncLogDetailDrawer.vue:248-257 | bug | watch 仅监听 visible，task 变化不刷新 → 改监听 `[visible, task?.task_id]` |
| 10 | SyncLogDetailDrawer.vue:221-223 | other | 请求失败误报"无明细" → 增加 `loadError` 标志，空态区分「加载失败」与「历史任务」 |
| 11 | SyncLogDetailDrawer.vue:27 | maintainability | summary 初始 0 使 `?? task 兜底` 死代码 → 初始化为 `null`，加载前展示任务自带计数 |
| 12 | SyncLogDetailDrawer.vue:21 | style | `==` → `===` |
| 13 | SyncLogDetailDrawer.vue:84-85 | style | 冗余 v-else-if 分支（与 v-else 相同）→ 合并 |
| 14 | tiers.ts:39-43 | style | 宽松 `!=` / 冗余 `??` → map 内直接收敛，`max ?? null` 保留 |
| 15 | PackagePlans.vue:358-361 | bug | 导出立即 revokeObjectURL，Safari/Firefox 可能下载失败 → `setTimeout` 延迟回收（与 ImportModal.vue 约定一致） |
| 16 | PricingRules.vue:299-302 | bug | 同上 → 延迟回收 |
| 17 | PricingRules.vue:417 | style | `r.max == null` → `r.max === null` |
| 18 | analytics.py:293 | maintainability | 异常消息字符串匹配 409 → 定义 `DuplicateSyncTaskError` 异常类，analytics.py / sync_tasks.py / scheduler.py 三处按类型捕获 |
| 19 | analytics.py:295 | style | f-string 日志 → 惰性占位符 `%s`（sync_schedule.py 同批修复 3 处） |
| 20 | sync_schedule.py:87-88 | maintainability | `request.json` 未校验类型 → `isinstance(data, dict)` 校验返回 400 |

## 已评估不动（2 条）

### `backend/app/routes/billing/balances.py:696-698` [low] — ORM 实例跨线程隐患

当前实现通过 selectinload 三级预加载（Customer → profile → industry_type）保证线程内属性访问不触发懒加载，且代码注释明确写出了两个安全前提。属「未来新增属性访问才会触发」的理论隐患，重构导出核心路径（5 万行）风险大于收益，**暂不重构**，保留现状与注释。

### `backend/app/routes/customers.py:790` — pandas 死代码（**误报**）

OCR 判断 `import pandas as pd` 无引用，但实际 `pd.DataFrame`（L1144）与 `pd.ExcelWriter`（L1148）仍在使用，import 有效，**不处理**。

---

## 验证结果

| 检查 | 结果 |
|---|---|
| 后端 py_compile（全部修改文件） | ✅ |
| ruff check（全部修改文件） | ✅ All checks passed |
| 相关后端测试（order_sync / cost_calc / tiers / sync_schedule / sync_task_details / import_field_mapping / analytics） | ✅ 151 passed |
| 前端 type-check（vue-tsc --noEmit） | ✅ 无错误 |

> 注：余额导出（balances.py）、invoices 导入的端到端行为未做浏览器级验证；相关单元/集成测试覆盖了核心逻辑。

---

## 遗留风险

- **billing 部分文件未获审查评论**：`customers.py` 路由、`billing.py` service、`packages.py/pricing.py`（cost_calc 已由 sync 批覆盖）、`imports.py/excel_import.py` 等因 provider 连续 524/502/429 未能产出有效评论。其中 `cost_calc.py` 的双 import（tiers + SyncDetail）已通过 ruff/导入测试验证无循环导入。
- **时区统一是本次修复的关键项**：`order_sync.py` 与 `cost_calc.py` 的明细 `sync_date` 已统一为 CST 本地日期（`astimezone(CST).date()`），与任务级明细（本地 date）一致。建议后续在 `SyncDetail` 源头统一类型约束（date vs datetime），防止回归。

---

## 修改文件清单（17 个）

**后端（11）**：`app/models/billing.py`、`app/routes/analytics.py`、`app/routes/billing/invoices.py`、`app/routes/database_management.py`、`app/routes/sync_schedule.py`、`app/routes/sync_tasks.py`、`app/services/analytics.py`、`app/services/cost_calc.py`、`app/services/order_sync.py`、`app/services/sync_task_service.py`、`app/tasks/scheduler.py`

**前端（6）**：`src/utils/tiers.ts`、`src/views/Home.vue`、`src/views/billing/PackagePlans.vue`、`src/views/billing/PricingRules.vue`、`src/views/system/SyncLogs.vue`、`src/views/system/components/SyncLogDetailDrawer.vue`
