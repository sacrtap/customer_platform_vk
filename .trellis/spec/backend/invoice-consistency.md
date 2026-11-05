# Invoice Detail Consistency（结算单明细数据一致性契约）

> 覆盖 F1–F6：生成前一致性校验、Excel 三表同源、subtotal/order_count 冻结、详情冻结快照组装、周期去重、同步层当天重拉与跨日迁移。
> 关联：[Billing Balance Stats](./billing-balance-stats.md)、[Database Guidelines](./database-guidelines.md)（PG 时区契约）、[Error Handling](./error-handling.md)。

## Scenario: invoice-detail-consistency

### 1. Scope / Trigger
- 触发：结算单「两次打开数字不同」「Excel 三表数字互斥」「同周期重复生成」「当天数据反复漂移」四类缺陷的根治契约。
- 影响层：services（billing/order_sync/invoice_excel/invoice_consistency）、routes（billing/invoices）、tasks（sync_task_service/invoice_detail_generator）、DB（invoice_items 两列）。

### 2. Signatures
- 新增列（`invoice_items`，迁移 `f1a2b3c4d5e6`）：
  - `subtotal NUMERIC(12,2) NULL` — 递增多层/包年限量等复合小计（旧口径 `quantity × unit_price` 会算错，故必须冻结）
  - `order_count INTEGER NULL` — 计费订单数（VR 等 quantity 语义 ≠ 订单数的场景）
- `billing._build_package_limited_breakdown(base_fee: Decimal, package_limits: dict, total_quantity: Decimal) -> dict` — 包年限量分解纯函数，`calculate_items_from_rules` 与 `get_invoice` 组装共用（防两处公式漂移）。返回 `package_type='limited'/base_fee/limit_count/in_package_quantity/over_limit_quantity/over_limit_unit_price/over_limit_cost/usage_cost/unit_price/subtotal`。
- `invoice_consistency.diff_period(customer_id, company_id, period_start: datetime, period_end: datetime, external_engine, db_session) -> list[DayDiff] | None` — `None` = 外部不可达/未配置，调用方放行（不阻塞业务）。
- `InvoiceService._check_invoice_period_overlap(customer_id, period_start: date | datetime, period_end: date | datetime)` — 周期去重（本地查询，先于外部校验快速失败）。
- `OrderSyncService._migrate_cross_day_orders(sync_date, saved_orders, detail_collector, emit)` — 跨日迁移清理。
- API：`GET /api/v1/billing/invoices/{id}` items 保持 20 字段结构，但 subtotal/order_count 改读冻结列（回退 `quantity × unit_price` / `quantity`）；生成/批量生成失败返回 `code=40001` + 差异日期文案。

### 3. Contracts
- **生成入口顺序**：`_check_invoice_period_overlap`（本地，便宜）→ `_check_invoice_consistency`（外部 diff，引擎 None 或异常 → warning 放行）→ 落库（items 写 `subtotal`/`order_count`，缺省 None）。
- **周期重叠判定**：`existing.period_start <= period_end AND existing.period_end >= period_start`，排除 `status='cancelled'` 与软删除行；相接不相交（前单 end < 后单 start）不误伤。
- **date 归一化**：`period_*` 为 `date`（无时刻）时必须转 `local_date_to_utc_start/end`——date 与 timestamptz 列直接比较按 UTC 00:00 解释，与 CST 业务日边界错位 8 小时（F5/F1 两方法均已归一化）。
- **Excel 三表同源**（F2）：「合计」「计费明细」「月份明细」均从同一 `invoice.items` 过滤 `order_code ∈ invoice_items.order_codes` 后聚合；「计费明细」小计列读 `item.subtotal`（多层递增真实小计），不再重算 `quantity × unit_price`；「合计」数量口径 = `invoice_items.order_count` 之和（NULL → 0）。
- **详情冻结快照**（F4）：`get_invoice` 不再实时调 `calculate_items_from_rules`；包年计算分量经查 `daily_consumptions.sum(order_count)` 还原（`has_package_item` 为假时零查询）；`get_invoice_by_id` 必须 `selectinload(Invoice.items).selectinload(InvoiceItem.pricing_rule)`，否则 async lazy load → MissingGreenlet。
- **同步层当天语义**（F6，易错点）：`skip_existing` 的跳过检查**仅对历史日期**生效；当天订单持续上传、任何快照都残缺，必须走完整同步（订单 + 费用）重拉。即 `if task.sync_mode == "skip_existing" and sync_date != cst_today():`。
- **跨日迁移**（F6）：同一 `order_code` 在新日期批次落库后，删除其在非当天窗口 `[sync_date, sync_date+1d)` 的旧 `daily_orders` 行 → 按 `(customer_id, 旧日)` 聚合 → 逐旧日 `CostCalcService.calculate_daily_cost` 重算（幂等：先删后建）→ 每单 `SyncDetail(category="order_move", level="warning")`；异常上抛（execute_task 按天记 failed）。

### 4. Validation & Error Matrix
| 条件 | 行为 |
|---|---|
| 同客户已有未取消周期重叠单 | `ValueError("已存在同期结算单 {no}（周期重叠），请勿重复生成")` → 路由 `40001`；批量生成进 `skipped`（reason 含单号） |
| 本地快照 vs 外部实时量有差异日 | `InvoiceConsistencyError`（文案含差异日期 + 「强制覆盖同步后重试」）→ 路由 `40001` |
| 外部库未配置/查询异常 | warning 日志 + 放行（不阻塞生成） |
| `daily_consumptions` 无数据（历史单） | 包年分量全 0；非包年项不受影响 |
| `invoice_items.subtotal` 为 NULL（迁移前历史行） | 详情回退 `quantity × unit_price`；`order_count` 回退 `quantity` |
| 同步任务范围为当天 | 强制完整同步（不查完整性、不跳过） |
| 订单 upload_date 跨日 | 删旧行 + 重算旧日 + `order_move` warning |

### 5. Good/Base/Bad Cases
- Good：11 月单生成后插入 10-31 同步 → 再生成 11 月单被拒（文案含 2026-10-31）；11 月/12 月相邻单互不误伤。
- Base：手工 items（无 subtotal）生成的单 → 冻结列 NULL，详情回退口径正确。
- Bad：`get_invoice` 实时重算（旧行为）→ 两次打开中间插同步数字漂移；包年两处公式各写一份 → 改一处漏一处。

### 6. Tests Required
- `tests/unit/test_invoice_consistency.py` — diff_period 逐日比对、None 放行、DayDiff 结构。
- `tests/unit/test_order_sync_cross_day.py` — 残留行删除 + 旧日重算一次 + order_move 明细；无残留零开销；空批次早退。
- `tests/unit/test_billing_service.py` — 包年分解（含 over_limit NULL 自动计价）、mock_db_session 默认 `first()→None`（防 F5 查询误伤既有单测）。
- `tests/unit/test_detail_recovery.py` — claim→items→order_codes 三次 execute 的 side_effect 序列（新增查询必须同步补桩）。
- `tests/unit/test_invoice_excel.py` — 三表同源、subtotal 口径、空串读回 None。
- `tests/integration/test_invoice_generation_guard.py` / `test_invoice_period_dedup.py` — 40001 拒绝 + skipped + 相邻周期不误伤。
- `tests/services/test_sync_task_service.py` — `test_execute_task_today_force_resync`（当天强制重拉）、`test_verify_completeness_covers_today`（校验覆盖当天）。

### 7. Wrong vs Correct
#### Wrong（实时重算，数字漂移）
```python
recalculated, _ = await invoice_service.calculate_items_from_rules(...)  # 详情再次实时算
```
#### Correct（冻结快照）
```python
for item in invoice.items:          # 读落库冻结值
    subtotal = item.subtotal if item.subtotal is not None else item.quantity * item.unit_price
```
#### Wrong（date 直比 timestamptz）
```python
Invoice.period_start <= period_end   # date 无时刻，UTC 00:00 与 CST 边界错位 8h
```
#### Correct（归一化后比较）
```python
period_end_dt = period_end if isinstance(period_end, datetime) else local_date_to_utc_end(period_end.isoformat())
```
#### Wrong（skip_existing 跳过当天）
```python
if task.sync_mode == "skip_existing":   # 当天快照残缺，跳过=永远不同步最新数据
```
#### Correct（仅历史日可跳）
```python
if task.sync_mode == "skip_existing" and sync_date != cst_today():
```
