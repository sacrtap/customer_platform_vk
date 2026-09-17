# 实施计划 — 同步日志执行信息优化与定时同步配置化

> 任务目录：`.trellis/tasks/09-17-sync-execution-info`
> 设计依据：`design.md`（v2，含影响范围分析）；需求：`prd.md`
> 基线分支：`main`；实施分支：`feature/sync-execution-info`（基于 main 创建）

## 执行顺序（依赖序）

### Step 1 分支与迁移
- [ ] 1.1 基于 `main` 创建分支 `feature/sync-execution-info`（`task.py set-branch` 记录）
- [ ] 1.2 编写 Alembic 迁移（单文件）：
  - 建 `sync_task_log_details`（字段/索引见 design.md 3.1）
  - 建 `sync_schedule_configs`（含默认行 daily_sync: disabled, 01:00, skip_existing）
  - `sync_tasks.operator_id` DROP NOT NULL
  - 插入权限 `system:sync_schedule` + 关联超管角色（仿 l1m2n3o4p5q6）
- [ ] 1.3 执行 `alembic upgrade head` 验证迁移成功

### Step 2 模型与 DTO
- [ ] 2.1 `models/billing.py`：+ `SyncTaskLogDetail`
- [ ] 2.2 新建 `models/sync_schedule.py`：`SyncScheduleConfig`
- [ ] 2.3 `models/sync_task.py`：`operator_id` nullable=True
- [ ] 2.4 `services/dto.py`：+ `SyncDetail` dataclass

### Step 3 采集埋点（detail_collector 注入）
- [ ] 3.1 `services/order_sync.py`：`sync_orders(sync_date, detail_collector=None)` + `_match_and_save` 埋点（unmatched→warning / 单条异常→error / 成功按客户聚合→info / 提交失败→error / 拉单异常→error）
- [ ] 3.2 `services/cost_calc.py`：`calculate_daily_cost(consumption_date, detail_collector=None)` + 客户名预取 + no_rule→warning / 计算异常→error / 成功→info
- [ ] 3.3 回归确认：默认 None 路径行为不变（现有单测应全绿）

### Step 4 任务服务
- [ ] 4.1 `services/sync_task_service.py`：
  - `create_task` operator_id 可选（None 时任务记录 operator NULL）
  - `execute_task`：创建 details 收集器 → 传入 sync_orders / calculate_daily_cost → `_verify_data_completeness` 追加（缺失→warning、跳过→info）→ 任务级异常→error → **结束（成功或异常）一次性批量落库** `sync_task_log_details`
  - `list_tasks`：本页任务 `GROUP BY task_id, level` 计数聚合 → `_task_to_dict` 增加 execution_status / warning_count / error_count（含历史回退）

### Step 5 API
- [ ] 5.1 `routes/sync_tasks.py`：列表响应扩展（execution_status/warning_count/error_count）；新增 `GET /sync-tasks/<task_id>/details`（summary 全量 + list level 过滤 + 分页）
- [ ] 5.2 新建 `routes/sync_schedule.py`：`GET`（system:view）+ `PUT`（system:sync_schedule，校验 HH:MM / sync_mode，更新后动态调度）
- [ ] 5.3 `main.py`：注册 `sync_schedule_bp`
- [ ] 5.4 `routes/analytics.py`：`/consumption/sync` 改造为 create_task(昨天, operator=当前用户) + execute_task，返回 task_id/status，移除内联 sync_orders/calculate_daily_cost 调用

### Step 6 定时调度
- [ ] 6.1 `tasks/scheduler.py`：移除 `_sync_daily_orders` / `_calc_daily_cost` 注册；新增 `sync_daily_auto`（启动按配置注册；执行体：读配置二次校验 → 昨天 → create_task(operator=None) → execute_task；同日冲突捕获记 warning）
- [ ] 6.2 删除 `tasks/order_sync.py`、`tasks/cost_calc.py`
- [ ] 6.3 `scripts/seed.py`：ALL_PERMISSIONS + `system:sync_schedule`

### Step 7 前端
- [ ] 7.1 `api/syncTasks.ts`：SyncTask 扩展 execution_status/warning_count/error_count；+ `getSyncTaskDetails`、`SyncLogDetail` 类型
- [ ] 7.2 新建 `api/syncSchedule.ts`：`getSyncSchedule` / `updateSyncSchedule` / `SyncSchedule`
- [ ] 7.3 `views/system/SyncLogs.vue`：执行信息列（三态标签）+ 定时配置区（hasPermission 控制）+ 操作人「系统自动」
- [ ] 7.4 新建 `views/system/components/SyncLogDetailDrawer.vue`：概览 + 明细表格 + 级别过滤 + 分页

### Step 8 测试
- [ ] 8.1 适配：`tests/services/test_sync_task_service.py`、`tests/e2e/test_sync_task_e2e.py`（明细落库后断言与 teardown 清理 sync_task_log_details）
- [ ] 8.2 新增：明细落库内容（warning/error/info）、三态回退、details 接口过滤/分页、定时配置权限（非超管 PUT 403）、调度注册逻辑
- [ ] 8.3 全量测试 + 覆盖率验证（≥25%）

### Step 9 验证（对照 prd.md AC1-AC10）
- [ ] 9.1 迁移/权限/表结构（AC1）
- [ ] 9.2 手动任务明细落库（AC2）
- [ ] 9.3 列表三态 + 历史回退（AC3）
- [ ] 9.4 明细接口（AC4）
- [ ] 9.5 定时配置接口与调度动态调整 + 权限（AC5）
- [ ] 9.6 定时执行体 + 冲突保护（AC6）
- [ ] 9.7 /consumption/sync 统一（AC7）
- [ ] 9.8 前端三态/详情/配置区（AC8）
- [ ] 9.9 回归（AC9）
- [ ] 9.10 测试与覆盖率（AC10）

## 验证命令
- 迁移：`cd backend && alembic upgrade head`
- 后端单测：`cd backend && .venv/bin/python -m pytest tests/unit tests/services -q`
- 全量：`cd backend && .venv/bin/python -m pytest -q`（CI 门槛覆盖率 ≥25%）
- 前端构建：`cd frontend && npm run build`
- 前端类型：`cd frontend && npx vue-tsc --noEmit`（如项目配置）

## 回滚点
- 迁移前：`alembic downgrade -1`（新建表可整体回退；operator_id NOT NULL 恢复需先确认无 NULL 行——定时任务未启用前 operator 均非空）
- 代码：每 Step 独立提交，按提交粒度 revert
- 调度：关闭配置即停用定时任务（不动代码）

## 评审门
- Step 4/5 完成后：执行链路与 API 评审（对照 design.md）
- Step 7 完成后：前端交互评审（对照 prd AC8）
- Step 9 完成后：全量验收（AC1-AC10）→ `trellis-check` 质量门 → 归档
