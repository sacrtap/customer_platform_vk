# 技术设计 — 同步任务日志页面功能优化

> 任务：`.trellis/tasks/09-18-sync-logs-page-optimization`
> 范围：仅「执行信息明细 Drawer」（`SyncLogDetailDrawer.vue`）+ 明细查询接口。主列表 `SyncLogs.vue` 不动。

## 1. 边界与数据流

```
明细 Drawer (SyncLogDetailDrawer.vue)
  └─ getSyncTaskDetails(task_id, { level, type, is_settled, keyword, page, page_size })
       └─ GET /api/v1/sync-tasks/<task_id>/details
            └─ sync_task_log_details LEFT JOIN customers
                 └─ 筛选 + 分页 + 排序
```

数据来源单一：明细表 `sync_task_log_details`（简称 D），左连客户表 `customers`（简称 C）取结算/账号类型字段。

## 2. 后端改动（`backend/app/routes/sync_tasks.py` 的 `get_sync_task_details`）

### 2.1 新增查询参数

| 参数 | 取值 | 语义 |
|---|---|---|
| `type` | `order` / `cost` | 类型筛选；缺省=全部 |
| `is_settled` | `all` / `true` / `false` | 是否结算筛选；`all`=显示全部（含无客户）；缺省=不筛 |
| `keyword` | 字符串 | 公司ID/名称模糊搜索；缺省=不筛 |

### 2.2 查询改造

- 明细查询 `select(SyncTaskLogDetail).where(task_id == ...)` → 追加 `.outerjoin(Customer, D.customer_id == C.id)`，用 `select(D, C.is_settlement_enabled, C.account_type)` 取关联字段（或直接 `select(D)` + `relationship`，但 Customer 无对应 relationship，用显式 join 更直接）。
- **类型筛选**（category 归类，见 prd R1）：
  - `type=order` → `D.category.in_(("order_fetch", "order_match", "order_save"))`
  - `type=cost` → `D.category.in_(("cost_calc", "data_check"))`
- **是否结算筛选**：`is_settled=true` → `C.is_settlement_enabled == True`；`false` → `C.is_settlement_enabled == False`；`all` 或缺省 → 不筛（含 `customer_id=NULL` 明细）。
- **keyword 搜索**：`or_(D.external_customer_id.ilike(f"%{kw}%"), D.customer_name.ilike(f"%{kw}%"), D.company_name.ilike(f"%{kw}%"))`。
- **排序**：`order_by(D.sync_date.desc(), D.id.desc())`（改为先按日期，保证同一天记录相邻，支撑 R7 当日小计）。
- **summary 不变**：成功/警告/错误计数仍为全量（不受 type/is_settled/keyword 影响），仅受 task_id 约束。
- **分页 total**：`filtered_total` 需同步应用 type/is_settled/keyword 过滤（现有 level 过滤已如此）。

### 2.3 响应新增字段

每条明细 list item 追加：
- `is_settlement_enabled`：`bool | null`（来自 C，无客户为 null）
- `account_type`：`str | null`

## 3. 前端改动

### 3.1 `frontend/src/api/syncTasks.ts`

- `SyncLogDetail` 接口扩展 `is_settlement_enabled: boolean | null`、`account_type: string | null`。
- `getSyncTaskDetails` 参数扩展 `type?: string`、`is_settled?: string`、`keyword?: string`。

### 3.2 `frontend/src/views/system/components/SyncLogDetailDrawer.vue`

- **筛选区**（置于级别 radio 之上，满足 R5）：
  - 「类型」`a-select`：全部 / 费用计算(cost) / 订单匹配(order)
  - 「是否结算」`a-select`：全部(all) / 是(true) / 否(false)，**默认「是」**
  - 「公司ID/名称」`a-input` + 查询/重置按钮
  - 筛选变化 → 重置分页到第 1 页并重新拉取
- **列改造**：
  - `客户ID · 名称` → `公司ID · 名称`：ID 显示 `external_customer_id`，名称显示 `customer_name`（R3）。
  - 删除冗余的独立「外部客户ID」列（其值已并入「公司ID · 名称」；`external_customer_id` 与 `company_id` 数值相同）。
  - 新增「是否结算」列：`is_settlement_enabled === true ? '是' : false ? '否' : '-'`（R6）。
  - 新增「账号类型」列：`account_type || '-'`（R6）。
  - 「日期」列 `width` 从 110 加宽至 ~140（R8）。
- **记录数当日小计（R7）**：按 `sync_date` 分组，日期列 `rowSpan` 合并同组单元格，每组末尾在「记录数」列显示「当日小计 N」（N = 组内 `record_count` 求和）。基于当前页可见数据（分页切断日期组时小计覆盖当前页，属可接受边界）。

## 4. 兼容性 / 迁移

- 无表结构变更，无迁移文件。
- 明细接口为增量参数，旧调用（不传新参数）行为不变，仅响应多两个字段、排序变化。
- `system` 类明细在类型筛选「全部」下仍可见，选「费用计算」或「订单匹配」时隐藏（见 prd R1）。

## 5. 已确认决策

1. **「是否结算」三态**：新增「全部」选项显示无客户关联明细（`customer_id=NULL`），默认仍为「是」。
2. **「记录数当日小计」基于当前页**：分页切断日期组时，小计覆盖当前页，属可接受边界。
3. **删除「外部客户ID」独立列**：该列值已并入「公司ID · 名称」，删除避免重复。

## 6. 回滚

- 前端改动集中在 `SyncLogDetailDrawer.vue` + `syncTasks.ts`，后端集中在 `get_sync_task_details` 单接口，改动面小；回滚即还原这两个文件的相关函数与列定义。
