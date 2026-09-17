# 同步日志执行信息优化与定时同步配置化

## Goal

1. 「同步日志」页面：每个同步任务执行完成后，列表「错误信息」列改为「执行信息」列，按 **警告 / 正常 / 错误** 三态展示；点击后查看该任务执行过程中的预警/错误/成功记录数明细，**警告和错误信息必须完善，含客户ID、客户名称等字段**，便于排查具体问题。
2. 定时同步（原 01:00 订单同步 + 01:30 费用计算）**合并为单个「每日自动同步」任务**，与手动同步共用同一执行链路（订单→费用→数据完整性校验）。
3. 定时任务配置纳入「同步日志」页面：可**随时开启/关闭**、**配置执行时间（HH:MM）与同步模式**；配置操作有**独立权限 `system:sync_schedule`，默认仅超级管理员**。

## Requirements

### R1 执行信息列（列表）
- 列表「错误信息」列 → 「执行信息」列，每行显示三态标签：**错误（红）/ 警告（金）/ 正常（绿）**。
- 三态判定：有 error 级明细 → 错误；有 warning 级明细 → 警告；否则 → 正常。
- 历史任务（无明细数据）按 status 回退：failed→错误、partial→警告、completed/cancelled/pending/running→正常。
- 执行中（pending/running）不显示三态（显示占位）。

### R2 执行明细（详情查看）
- 点击执行信息标签打开详情视图（Drawer），展示：
  - 概览：成功记录数、警告数、错误数；
  - 明细列表：级别、日期、类别、客户ID、客户名称、外部客户ID、公司名、订单号、记录数、信息描述；
  - 支持按级别（全部/警告/错误/成功）过滤与分页。
- 明细采集内容：
  - **成功**：按「客户+日期」聚合，record_count = 该客户成功订单数（含 customer_id、customer_name）；
  - **警告**：订单未匹配到内部客户（记外部 group_type、公司名、订单号）、客户无生效计费规则（记 customer_id、customer_name）、数据完整性缺失（某天无订单/无消费）；
  - **错误**：订单拉取异常、单条订单处理异常（记 order_code、公司名）、费用计算异常（记 customer_id、customer_name）、任务级异常。
- 定时任务产生的明细与手动任务一致（同一链路）。

### R3 定时任务合并与配置化
- 删除独立定时任务 `sync_daily_orders`（01:00）、`calc_daily_cost`（01:30）及其文件，合并为单个「每日自动同步」job。
- 定时同步复用 `SyncTaskService.create_task + execute_task` 完整链路（目标日期=昨天），操作人显示「系统自动」（operator_id=NULL）。
- 配置项：enabled（开启/关闭）、sync_time（HH:MM）、sync_mode（skip_existing/force_overwrite），持久化到 `sync_schedule_configs` 表（单行 daily_sync）。
- 应用启动按配置注册/不注册调度；配置变更后 APScheduler 动态调整（next_run_time 随之更新）。
- 与手动任务冲突保护：目标日期已有活跃任务时跳过本次执行并记录 warning，不重复执行。

### R4 权限
- 新增权限 `system:sync_schedule`（模块 system），通过迁移插入 permissions 表并关联「超级管理员」角色。
- `GET /api/v1/sync-schedule`：`system:view`（查看）；`PUT /api/v1/sync-schedule`：`system:sync_schedule`（修改）。
- 前端配置区：有 `system:sync_schedule` 权限才显示编辑控件；无权限只读显示状态。
- `seed.py` 的 ALL_PERMISSIONS 同步补充该权限。

### R5 统一同步入口
- 遗留接口 `POST /api/v1/consumption/sync`（当前直接调 service、不产生任务记录，且前端无调用方）改造为：创建「昨天」单日同步任务（operator=当前用户）+ 后台 execute_task，响应返回 task_id/status，与 `/sync-tasks` 创建一致。

### R6 兼容性
- `sync_task_logs` 表与 `GET /api/v1/sync-logs` 接口**保留不动**（审计用途，数据库清空功能依赖）。
- 成功明细按客户+日期聚合（用户已确认）；未匹配订单记录外部标识（用户已确认）；历史任务按 status 回退三态（用户已确认）。
- `tasks/order_sync.py`、`tasks/cost_calc.py` 文件删除（已核实仅被 scheduler.py 引用）。

## Acceptance Criteria

- [ ] AC1 迁移升级成功：`sync_task_log_details`、`sync_schedule_configs` 建表，`sync_tasks.operator_id` 可空，默认配置行存在，权限 `system:sync_schedule` 存在且已关联超级管理员角色
- [ ] AC2 手动创建同步任务执行完成后：明细表有 info/warning/error 记录（未匹配订单→warning 含外部ID/公司名/订单号；无规则客户→warning 含 customer_id/name；成功→按客户聚合含 customer_id/name）
- [ ] AC3 列表接口每项返回 execution_status（normal/warning/error）+ warning_count/error_count；历史任务回退正确
- [ ] AC4 明细接口 `GET /sync-tasks/<id>/details`：summary 全量计数 + list 按 level 过滤 + 分页正确
- [ ] AC5 定时配置接口：GET 返回配置+next_run_time；PUT 校验（HH:MM、sync_mode）并动态调整 APScheduler job；非超管 PUT 返回 403
- [ ] AC6 定时执行体：开启后到点自动创建任务（operator 显示「系统自动」）并完成，明细可查；与手动任务同日冲突时跳过并记 warning
- [ ] AC7 `/consumption/sync` 返回 task_id 且产生可查任务记录与明细
- [ ] AC8 前端：执行信息列三态标签正确；点击打开详情 Drawer（概览+明细+级别过滤+分页）；定时配置区（超管可编辑、非超管只读/隐藏）；操作人为空显示「系统自动」
- [ ] AC9 回归：消耗分析手动同步（SyncDialog）、费用计算、结算单生成、scheduler-status、/sync-logs 审计不受影响
- [ ] AC10 全量测试通过（覆盖率 ≥25% CI 门槛），新增明细/接口/权限测试

## Notes

- 成功明细按「客户+日期」聚合（用户确认）；未匹配订单无内部 customer_id，记录外部 group_type+公司名+订单号（用户确认）；历史任务按 status 回退三态（用户确认）。
- 明细采集通过「注入 detail_collector 可选参数」实现，不改 sync_orders / calculate_daily_cost 返回签名（7+6 个调用方零改动）。
- 技术细节见 design.md；执行顺序见 implement.md。
