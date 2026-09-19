# 同步任务日志页面功能优化

## Goal

在「同步任务日志」页面（`system/sync-logs`）的任务执行信息明细 Drawer 中，增强筛选、搜索、客户字段展示与小计，提升排查效率。

用户价值：运维/运营在排查同步问题时，能按「类型」「是否结算」快速过滤、按「公司ID/名称」定位客户、直接在明细列表看到客户的结算与账号类型信息、按日期看到记录数小计。

## Background（已核实的现状）

- 页面链路：`system/sync-logs` 列表页 `SyncLogs.vue` → 点击「执行信息」标签 → 明细 Drawer `SyncLogDetailDrawer.vue`（`frontend/src/views/system/components/SyncLogDetailDrawer.vue`）。
- 明细数据源：`sync_task_log_details` 表（`backend/app/models/billing.py` `SyncTaskLogDetail`），查询接口 `GET /api/v1/sync-tasks/<task_id>/details`（`backend/app/routes/sync_tasks.py`）。
- 明细表字段：`level`（info/warning/error）、`sync_date`（明细日期）、`category`（order_fetch/order_match/order_save/cost_calc/data_check/system）、`customer_id`（内部客户 ID，FK customers.id）、`customer_name`、`external_customer_id`（外部客户 ID = group_type）、`company_name`、`order_code`、`record_count`（聚合记录数）。
- 客户表 `Customer`（`backend/app/models/customers.py`）字段：`company_id`（公司ID，Integer unique）、`name`、`account_type`（账号类型）、`is_settlement_enabled`（是否启用结算，Boolean default True）。
- 订单匹配逻辑 `_match_customer`（`backend/app/services/order_sync.py`）：`Customer.company_id == group_type` → **「公司ID」（company_id）与「外部客户ID」（external_customer_id/group_type）数值相同**，故需求 3 中「公司ID = 外部客户ID」成立。
- 客户管理页面字段显示标签：「是否结算」= `is_settlement_enabled`（`CustomerBasicTab.vue`）；「账号类型」= `account_type`。
- 当前明细 Drawer 列：级别、日期、类别、客户ID·名称、外部客户ID、公司名、订单号、记录数、信息。

## Requirements

- **R1 类型筛选**：明细 Drawer 新增「类型」筛选项，选项「费用计算」「订单匹配」，默认「全部」。
  - 「订单匹配」= category in (order_fetch, order_match, order_save)
  - 「费用计算」= category in (cost_calc, data_check)
  - `system`（任务级异常）仅在「全部」下显示。
- **R2 是否结算筛选**：明细 Drawer 新增「是否结算」筛选项，选项「全部」「是」「否」，默认「是」。数据来源为客户表 `customers.is_settlement_enabled`。「全部」显示所有明细（含 `customer_id=NULL` 的无客户记录）；「是」/「否」仅筛选有客户关联的记录。
- **R3 客户ID·名称列改名**：明细表「客户ID · 名称」列改为「公司ID · 名称」，ID 部分改显示外部客户 ID（`external_customer_id`），名称保留 `customer_name` 不变。因 `external_customer_id` 与 `company_id` 数值相同，等同「公司ID」。
- **R4 公司ID/名称搜索**：明细 Drawer 新增「公司ID/名称」搜索输入项，对明细列表按公司ID（external_customer_id）或名称（customer_name/company_name）过滤，默认空。
- **R5 筛选项位置**：所有新增筛选项（类型、是否结算、公司ID/名称搜索）位于分类标签（全部/警告/错误/成功）**之上**。
- **R6 警告列补充**：明细列表中，对 `level=warning` 的记录（及全部记录）显示客户表的「是否结算」（是/否）与「账号类型」两个字段。
- **R7 记录数当日小计**：明细表「记录数」列按 `sync_date` 分组，展示当日记录数小计（该日期下所有明细 `record_count` 之和）。
- **R8 日期列加宽**：明细表「日期」列宽度加大，避免时间折行显示。

## Acceptance Criteria

- [ ] AC1：明细 Drawer 顶部出现「类型」「是否结算」「公司ID/名称」筛选项，且位于「全部/警告/错误/成功」分类标签上方；类型默认「全部」、是否结算默认「是」、搜索默认空。
- [ ] AC2：类型选「订单匹配」仅显示 order_fetch/order_match/order_save 类明细；选「费用计算」仅显示 cost_calc/data_check 类明细。
- [ ] AC3：是否结算选「是」仅显示对应客户 `is_settlement_enabled=true` 的明细；选「否」仅显示 `=false` 的明细；选「全部」显示所有明细（含无客户记录）。
- [ ] AC4：「客户ID · 名称」列标题变为「公司ID · 名称」，ID 显示外部客户 ID，名称显示不变。
- [ ] AC5：公司ID/名称搜索按外部客户 ID 或名称模糊过滤明细。
- [ ] AC6：明细列表新增「是否结算」「账号类型」两列（来自客户表），警告级别记录正确显示。
- [ ] AC7：明细表按日期分组显示当日记录数小计（各明细 record_count 按 sync_date 求和）。
- [ ] AC8：日期列加宽后，日期内容不折行。
- [ ] AC9：筛选/搜索/分页组合正确（筛选后分页 total 正确）；summary（成功/警告/错误计数）不受筛选影响仍显示全量。

## Out of Scope

- 主列表页 `SyncLogs.vue` 的任务级筛选与列（本任务仅针对执行信息明细 Drawer）。
- 定时同步配置、任务取消、统计卡片等既有功能。
- 明细数据的写入逻辑（`order_sync.py` / `cost_calc.py` / `sync_task_service.py` 的落库），除非为满足 R6 需要补字段。

## Key Decisions（已与用户确认）

- R1：`data_check`（数据完整性校验）归入「费用计算」；`system`（任务级异常）仅在「全部」下显示。
- R2：「是否结算」为三态（全部/是/否），默认「是」；「全部」显示含 `customer_id=NULL` 的无客户记录。
- R3：删除冗余的「外部客户ID」独立列（值已并入「公司ID · 名称」）。
- R7：「记录数当日小计」基于当前页数据按 `sync_date` 分组求和。
