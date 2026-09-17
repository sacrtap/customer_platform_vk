# 「同步日志执行信息 + 定时同步配置化」— 详细技术设计（修订版）

> 状态：设计稿 v2（已按影响范围分析修订），未修改代码
> 日期：2026-09-17
> 前置调研：`local://sync-execution-info-investigation.md`

---

## 一、目标

1. 同步日志列表「错误信息」列 → 「执行信息」列，按 **警告 / 正常 / 错误** 三态展示，点击查看执行明细（预警/错误/成功记录数，含客户ID、客户名称）。
2. 定时任务（原 01:00 订单同步 + 01:30 费用计算）**合并为单个"每日自动同步"任务**，复用手动任务的完整链路。
3. 定时任务配置**纳入「同步日志」页面**：开启/关闭、执行时间（HH:MM）、同步模式；**单独权限 `system:sync_schedule`，默认仅超级管理员**。
4. 所有同步入口统一产生任务记录与执行明细（含遗留 `/consumption/sync` 接口）。

已确认：成功明细按「客户+日期」聚合；未匹配订单记录外部标识（group_type+公司名+订单号）；历史任务按 status 回退推断三态；旧定时任务文件删除。

---

## 二、整体架构

```
手动触发A:  SyncDialog → POST /api/v1/sync-tasks → create_task + execute_task
手动触发B:  POST /api/v1/consumption/sync（遗留接口）→ 改造为 create_task(昨天) + execute_task
定时触发:   APScheduler(sync_daily_auto, 按配置) → create_task(昨天, operator=NULL) + execute_task
                                                          │
          execute_task 逐天:                                 ▼
    OrderSyncService.sync_orders(detail_collector) ──► SyncDetail 追加到收集器
    CostCalcService.calculate_daily_cost(detail_collector) ──► SyncDetail 追加到收集器
    _verify_data_completeness ──► SyncDetail 追加到收集器
                                                          │
                                   明细统一写入 sync_task_log_details（任务结束一次性落库）
                                                          ▼
前端 SyncLogs.vue: 执行信息列(三态) → 详情 Drawer(明细) + 定时配置区(开关/时间/模式, 权限 system:sync_schedule)
```

**核心原则**：
- 定时任务与手动任务**共用同一条 execute_task 链路**，只差触发入口。
- **明细采集用「注入 detail_collector」而非改返回签名** → `sync_orders`（7 调用方）、`calculate_daily_cost`（6 调用方，含 scripts/analytics 路由/测试）**全部零改动**。

---

## 三、数据层设计

### 3.1 新表 `sync_task_log_details`（执行明细表）

```sql
CREATE TABLE sync_task_log_details (
    id                   SERIAL PRIMARY KEY,
    task_id              UUID REFERENCES sync_tasks(id) ON DELETE CASCADE,  -- NOT NULL（改造后所有任务都有）
    sync_date            DATE NOT NULL,               -- 明细所属同步日期
    level                VARCHAR(10) NOT NULL,        -- info / warning / error
    category             VARCHAR(30) NOT NULL,        -- order_fetch / order_match / order_save / cost_calc / data_check / system
    message              TEXT NOT NULL,               -- 人类可读描述
    customer_id          INTEGER REFERENCES customers(id),   -- 内部客户ID（未匹配时为 NULL）
    customer_name        VARCHAR(200),                -- 内部客户名称
    external_customer_id VARCHAR(50),                 -- 外部 group_type
    company_name         VARCHAR(200),                -- 外部公司名
    order_code           VARCHAR(50),                 -- 订单号
    record_count         INTEGER NOT NULL DEFAULT 1,  -- 聚合记录数（成功按 客户+日期 聚合时 > 1）
    created_at           TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX idx_sync_detail_task_level ON sync_task_log_details (task_id, level);
CREATE INDEX idx_sync_detail_task_date  ON sync_task_log_details (task_id, sync_date);
```

### 3.2 新表 `sync_schedule_configs`（定时同步配置）

```sql
CREATE TABLE sync_schedule_configs (
    id          SERIAL PRIMARY KEY,
    task_name   VARCHAR(50) NOT NULL UNIQUE DEFAULT 'daily_sync',  -- 预留多任务扩展
    enabled     BOOLEAN NOT NULL DEFAULT FALSE,     -- 开启/关闭
    sync_time   VARCHAR(5) NOT NULL DEFAULT '01:00', -- 执行时间 HH:MM（24小时制）
    sync_mode   VARCHAR(20) NOT NULL DEFAULT 'skip_existing',
    updated_by  INTEGER REFERENCES users(id),
    updated_at  TIMESTAMP NOT NULL DEFAULT now()
);
-- 初始化一行: INSERT ... (task_name='daily_sync', enabled=FALSE, sync_time='01:00', sync_mode='skip_existing')
```

### 3.3 `sync_tasks.operator_id` 改为可空

- 定时任务无真实操作人 → `operator_id` DROP NOT NULL。
- 影响点（已核实）：
  - `sync_task_service.create_task()` 参数 operator_id 改可选；
  - `_task_to_dict()` 已处理 `task.operator else None`，无需改；前端 `operator_name || '-'` → 改为「系统自动」兜底；
  - `list_tasks()` 的 `selectinload(SyncTask.operator)` 对 NULL FK 返回 None，无影响；
  - `sync_task_logs.operator_id` 本就可空，无影响。

### 3.4 新权限 `system:sync_schedule`

- 迁移仿照 `l1m2n3o4p5q6`（erp_systems 权限）：bulk_insert permissions + SQL 关联超管角色：
```sql
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = '超级管理员' AND p.code = 'system:sync_schedule'
ON CONFLICT DO NOTHING;
```
- `backend/scripts/seed.py` 的 `ALL_PERMISSIONS` 同步补充该权限（保持脚本一致，超管自动获得全部权限）。
- 前端 `userStore.hasPermission('system:sync_schedule')` 控制配置区显示/编辑。

---

## 四、采集层设计（注入 detail_collector）

### 4.1 新增 DTO：`SyncDetail`（`services/dto.py`）

```python
@dataclass
class SyncDetail:
    sync_date: date
    level: str            # info / warning / error
    category: str         # order_fetch / order_match / order_save / cost_calc / data_check / system
    message: str
    customer_id: int | None = None
    customer_name: str | None = None
    external_customer_id: str | None = None
    company_name: str | None = None
    order_code: str | None = None
    record_count: int = 1
```

### 4.2 `OrderSyncService.sync_orders(sync_date, detail_collector=None)`

- **签名追加可选参数 `detail_collector: Optional[List[SyncDetail]] = None`，默认 None 时行为与现在完全一致**（7 个调用方零改动，仅 execute_task 传入）。
- `_match_and_save(orders, sync_date, detail_collector)` 内部埋点：

| 场景 | level | category | 记录字段 |
|---|---|---|---|
| 外部 MySQL 拉单异常 | error | order_fetch | message=异常信息 |
| 未匹配到内部客户 | warning | order_match | external_customer_id=group_type, company_name, order_code |
| 单条订单处理异常 | error | order_save | order_code, company_name, message=str(e) |
| 成功保存 | info | order_save | customer_id, customer_name(join)，**按客户+日期内存聚合**，record_count=订单数 |
| 批量提交失败 | error | order_save | message=「批量提交 N 条失败」 |

- 性能：成功明细按 customer_id 内存分组聚合（一批订单一次聚合），无额外查询；`company_name` 直接来自拉单结果。

### 4.3 `CostCalcService.calculate_daily_cost(consumption_date, detail_collector=None)`

- 同样追加可选参数，默认 None 零改动（6 个调用方不变）。
- 埋点明细：

| 场景 | level | category | 记录字段 |
|---|---|---|---|
| 客户无计费规则 | warning | cost_calc | customer_id, customer_name, message=「该日期无生效计费规则」 |
| 单客户计算异常 | error | cost_calc | customer_id, customer_name, message=str(e) |
| 成功计算 | info | cost_calc | customer_id, customer_name（按客户聚合） |

- 客户名：`calculate_daily_cost` 主循环前**一次性预取**当日客户 id→name 映射（`select Customer where id in (...)`），避免 N+1。

### 4.4 `SyncTaskService.execute_task()`（`services/sync_task_service.py`）

- 创建 `details: List[SyncDetail] = []`，传入各 service 的 detail_collector；`_verify_data_completeness` 与任务级异常直接 append。
- 追加埋点：数据缺失 → warning(data_check)；任务级异常 → error(system)；跳过天数 → info(data_check)。
- **任务结束（成功或异常分支）一次性批量写入 `sync_task_log_details`**（独立提交；异常分支也写，保证失败任务可查明细）。

### 4.5 定时任务合并改造（`tasks/`）

- **删除** `tasks/order_sync.py`、`tasks/cost_calc.py`（codegraph 确认：两者仅被 `scheduler.py` 引用，无测试、无其他调用）。
- `scheduler.py`：移除 `_sync_daily_orders`、`_calc_daily_cost` 两个 monitored 包装与 job 注册；新增单 job `sync_daily_auto`（见第七章）。
- 目标日期 = 昨天（`local_yesterday_utc_start`）；`create_task(operator_id=None)` → `execute_task`。
- 冲突保护：已有同日期活跃任务 → 捕获异常记 warning，不重复执行。

### 4.6 遗留接口 `POST /api/v1/consumption/sync` 改造（`routes/analytics.py`）

- **codegraph 核实**：前端 `manualSyncConsumption`（analytics.ts:103）**无任何调用方**（Consumption.vue 数据同步走 SyncDialog→sync-tasks），该接口为遗留入口。
- 改造：保留路由与 Redis 锁（防并发），内部逻辑改为 `SyncTaskService.create_task(start=end=昨天, operator_id=当前用户) + execute_task`；响应返回 `{task_id, status}`（与 /sync-tasks 创建一致），原 order_sync/cost_calc 内联逻辑移除。
- 收益：该入口产生的同步也进日志页面、有执行明细，符合「每个同步任务」语义。
- 影响：响应结构变化（无前端调用方，仅潜在外部调用者，文档标注）。

---

## 五、API 设计

### 5.1 列表增强 `GET /api/v1/sync-tasks`

响应 `list[]` 每项新增 `execution_status`（normal/warning/error）、`warning_count`、`error_count`。

- 三态：error>0→error；warning>0→warning；否则 normal。
- 历史任务（无明细）回退：failed→error；partial→warning；completed/cancelled/pending/running→normal。
- 实现：列表页一次 `GROUP BY task_id, level` 聚合本页任务计数（避免 N+1）。

### 5.2 明细查询 `GET /api/v1/sync-tasks/<task_id>/details`

```
Query: level=warning|error|info (可选), page=1, page_size=20
```
```json
{
  "code": 0,
  "data": {
    "summary": { "info_count": 12, "warning_count": 3, "error_count": 1, "total_count": 16 },
    "list": [
      { "id": 1, "sync_date": "2026-09-16", "level": "warning", "category": "order_match",
        "message": "...", "customer_id": null, "customer_name": null,
        "external_customer_id": "10086", "company_name": "XX 公司",
        "order_code": "NEST-...", "record_count": 1, "created_at": "..." }
    ],
    "pagination": { "page": 1, "page_size": 20, "total": 16 }
  }
}
```
- summary 总是全量，list 按 level 过滤。

### 5.3 定时配置 `GET/PUT /api/v1/sync-schedule`

- `GET` 返回：`{task_name, enabled, sync_time, sync_mode, next_run_time, updated_at}`。
- `PUT` 支持部分更新：`{enabled?, sync_time?, sync_mode?}`；校验 HH:MM 与 sync_mode 枚举。
- PUT 后立即动态调整 APScheduler job。
- **权限：GET = `system:view`（查看）；PUT = `system:sync_schedule`（修改，仅超管默认）**。
- 新蓝图 `sync_schedule_bp`（注册进 main.py）。

---

## 六、前端设计（Arco Design Vue）

### 6.1 API 封装

- `api/syncTasks.ts`：`SyncTask` 扩展 `execution_status/warning_count/error_count`；新增 `getSyncTaskDetails(taskId, params)`、`SyncLogDetail` 类型。
- 新 `api/syncSchedule.ts`：`getSyncSchedule()` / `updateSyncSchedule(params)` / `SyncSchedule` 类型。

### 6.2 `SyncLogs.vue` 改造

- 「错误信息」列 → 「执行信息」列（slot `execution_info`）：

| execution_status | 展示 |
|---|---|
| error | `a-tag color=red`「错误」 |
| warning | `a-tag color=gold`「警告」 |
| normal | `a-tag color=green`「正常」 |
| pending/running | 灰字「-」 |

- 点击标签（cursor:pointer）→ `SyncLogDetailDrawer`。
- 操作人列：`operator_id == null` → 「系统自动」。
- 新增「定时同步配置」卡片（**仅 `hasPermission('system:sync_schedule')` 时显示编辑控件**；无权限只读显示状态）：
  - `a-switch` 开启/关闭、`a-time-picker`（HH:mm）、`a-select` 同步模式、保存按钮、下次执行时间展示。

### 6.3 新组件 `SyncLogDetailDrawer.vue`

- `a-drawer`（860px，参考 InvoiceDetailDrawer），title「执行信息 - 任务 ID 前8位」。
- 概览：成功记录数 / 警告数 / 错误数 + 任务状态 tag + 周期 + 模式。
- 明细：`a-tabs`（全部/警告/错误/成功）→ `a-table`：级别 tag、日期、类别(中文映射)、客户ID、客户名称、外部客户ID、公司名、订单号、记录数、信息(ellipsis+tooltip)；分页。
- 空态：无明细时提示「该任务无执行明细记录（历史任务）」。

---

## 七、定时调度设计（APScheduler 动态调度）

### 7.1 启动注册（`tasks/scheduler.py`）

- 启动时读 `sync_schedule_configs`：enabled → `add_job(sync_daily_auto, CronTrigger(hour, minute))`；disabled → 不注册。
- job 执行体（`@monitored_task("sync_daily_auto", "每日自动同步")`）：读配置二次校验 → 目标日期=昨天 → `create_task(operator_id=None)` → `execute_task`。
- 移除 `sync_daily_orders`、`calc_daily_cost` 注册；删除 `tasks/order_sync.py`、`tasks/cost_calc.py`。

### 7.2 配置更新动态调整（PUT /api/v1/sync-schedule）

1. 更新配置行（记录 updated_by）；
2. `remove_job("sync_daily_auto")`（容错不存在）→ enabled 则按新时间 `add_job(replace_existing=True)`；
3. 返回新配置 + `next_run_time`。

### 7.3 边界与失败处理

| 场景 | 处理 |
|---|---|
| 配置 disabled / 不存在 | 不注册 job；执行体二次校验 |
| 目标日期已有活跃任务 | 捕获「已有相同周期」→ 记 warning，不重复执行 |
| execute_task 异常 | monitored_task 记 failed；明细 error 已落库 |
| 修改 sync_time 时正在执行 | remove+add 不影响正在运行的 job 实例（APScheduler 行为） |

---

## 八、影响范围（codegraph 核实）

### 8.1 后端改动文件

| 文件 | 改动 |
|---|---|
| `alembic/versions/`（新） | 建 2 表 + operator_id 可空 + 默认配置行 + 权限 `system:sync_schedule` + 超管关联 |
| `models/billing.py` | + `SyncTaskLogDetail` |
| `models/sync_schedule.py`（新） | `SyncScheduleConfig` |
| `models/sync_task.py` | `operator_id` nullable=True |
| `services/dto.py` | + `SyncDetail` |
| `services/order_sync.py` | `sync_orders/_match_and_save` 追加 detail_collector（默认 None） |
| `services/cost_calc.py` | `calculate_daily_cost` 追加 detail_collector（默认 None）+ 客户名预取 |
| `services/sync_task_service.py` | create_task operator 可选；execute_task 明细收集+落库；list_tasks 计数聚合；_task_to_dict 扩展 |
| `routes/sync_tasks.py` | 列表响应扩展 + details 接口 |
| `routes/sync_schedule.py`（新） | GET/PUT 定时配置（权限：GET system:view / PUT system:sync_schedule） |
| `routes/analytics.py` | `/consumption/sync` 改造为 create_task+execute_task |
| `main.py` | 注册 sync_schedule_bp |
| `tasks/scheduler.py` | 删 2 job + 新增 sync_daily_auto 动态注册 |
| `tasks/order_sync.py`、`tasks/cost_calc.py` | **删除**（仅 scheduler 引用，已核实） |
| `scripts/seed.py` | ALL_PERMISSIONS + `system:sync_schedule` |

### 8.2 调用方影响矩阵（改签名风险规避后）

| 调用方 | sync_orders | calculate_daily_cost | 改动 |
|---|---|---|---|
| `services/sync_task_service.py` | ✅ 传 collector | ✅ 传 collector | 核心改造 |
| `routes/analytics.py` `/consumption/sync` | 移除内联调用 | 移除内联调用 | 改造为任务链路 |
| `tasks/order_sync.py` / `tasks/cost_calc.py` | 删除 | 删除 | 文件删除 |
| `scripts/recalc_daily_consumptions.py` | — | ✅ 默认 None | **零改动** |
| `scripts/recalc_unified_costs.py` | — | ✅ 默认 None | **零改动** |
| 测试 test_order_sync / test_cost_calc / test_sync_task_service / e2e | ✅ 默认 None | ✅ 默认 None | **零改动**（mock 不受影响） |

### 8.3 测试影响与新增

- 零改动：现有 sync_orders / calculate_daily_cost 单测（默认参数路径）。
- 需适配：`test_sync_task_service.py`、`test_sync_task_e2e.py`（execute_task 新增明细落库 → 断言/夹具清理需覆盖新表）；e2e teardown 清理 sync_task_log_details。
- 新增测试：明细落库（warning/error/info 内容）、三态回退逻辑、details 接口分页/过滤、定时配置接口权限（PUT 需 system:sync_schedule）、调度动态注册。

### 8.4 前端改动文件

| 文件 | 改动 |
|---|---|
| `api/syncTasks.ts` | SyncTask 扩展 + getSyncTaskDetails + SyncLogDetail |
| `api/syncSchedule.ts`（新） | 定时配置 API |
| `views/system/SyncLogs.vue` | 执行信息列 + 定时配置区 + 系统自动显示 |
| `views/system/components/SyncLogDetailDrawer.vue`（新） | 明细 Drawer |
| `composables/useAppLayout.ts`（如需） | 侧边栏无变化（页面已存在） |

### 8.5 保留不动（避免误伤）

- `sync_task_logs` 表、`GET /api/v1/sync-logs` 接口、`tasks/monitor.py`、`cache/permissions.py`、`middleware/auth.py`（require_permission 机制）、`DatabaseManagement.clear-sync-logs`。
- `InvoiceLogs.vue`、`AuditLogs.vue`、`ProgressView.vue`、`SyncDialog.vue` 均不改。

---

## 九、实施任务分解

| # | 任务 | 涉及文件 |
|---|---|---|
| 1 | Alembic 迁移（2 新表 + operator_id 可空 + 默认配置行 + 权限与超管关联） | `backend/alembic/versions/` |
| 2 | 模型：SyncTaskLogDetail / SyncScheduleConfig / SyncTask.operator_id | `models/billing.py`, `models/sync_schedule.py`, `models/sync_task.py` |
| 3 | SyncDetail DTO + order_sync detail_collector 埋点 | `services/dto.py`, `services/order_sync.py` |
| 4 | cost_calc detail_collector 埋点 + 客户名预取 | `services/cost_calc.py` |
| 5 | execute_task 明细收集+落库 + 完整性校验埋点 + create_task operator 可选 | `services/sync_task_service.py` |
| 6 | 列表 execution_status + details 接口 | `routes/sync_tasks.py` |
| 7 | 定时配置接口（GET/PUT + 权限）+ 新蓝图注册 | `routes/sync_schedule.py`(新), `main.py` |
| 8 | /consumption/sync 改造为任务链路 | `routes/analytics.py` |
| 9 | 定时调度合并（删 2 任务 + sync_daily_auto 动态注册） | `tasks/scheduler.py`, 删 `tasks/order_sync.py`, `tasks/cost_calc.py` |
| 10 | seed.py 权限补充 | `scripts/seed.py` |
| 11 | 前端 API + SyncLogs.vue + SyncLogDetailDrawer + 配置区 | `api/syncTasks.ts`, `api/syncSchedule.ts`, `views/system/SyncLogs.vue`, `views/system/components/SyncLogDetailDrawer.vue` |
| 12 | 测试适配与新增 | `tests/services/test_sync_task_service.py`, `tests/e2e/test_sync_task_e2e.py` + 新增明细/接口测试 |
| 13 | 验证（见第十章） | — |

## 十、验证清单（实施阶段执行）

1. `alembic upgrade head` 成功；权限 `system:sync_schedule` 出现在权限列表且超管角色已关联；
2. 手动创建同步任务 → 明细落库（warning/error/info，含客户ID/名称或外部标识）；
3. `GET /sync-tasks` 三态正确（含历史回退）；`GET /sync-tasks/<id>/details` 分页/过滤/汇总正确；
4. 定时配置：关闭→job 移除；开启→job 注册且 next_run_time 正确；改时间→动态调整；非超管 PUT 403；
5. 手动触发 sync_daily_auto 执行体 → 自动创建任务并完成（操作人显示「系统自动」）；
6. `/consumption/sync` 改造后返回 task_id 并产生任务记录；
7. 前端：三态标签、详情 Drawer、配置区（超管可编辑、非超管只读/隐藏）；
8. 回归：消耗分析手动同步、费用计算、结算单生成、scheduler-status 接口、`/api/v1/sync-logs` 审计不受影响；
9. 全量测试通过（覆盖率 ≥25% CI 门槛）。
