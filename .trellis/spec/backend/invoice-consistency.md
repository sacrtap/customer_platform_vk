# Invoice Detail Consistency（结算单明细数据一致性契约）

> 覆盖 F2–F8：Excel 三表同源、subtotal/order_count 冻结、多层计费冻结、详情冻结快照组装、周期去重、同步层当天重拉与跨日迁移、计费明细双口径、房源级识别键。
> **快照即准（2026-11-09 用户决策）**：结算单生成不再做「本地快照 vs 外部实时量」逐日比对（原 F1 已移除，`services/invoice_consistency.py` 删除），完全以数据库中每日同步入库的 `daily_orders`/`daily_consumptions` 为准。实证动因：深圳中原地产 2026-10 有 3 笔订单外部事后改期 + 1 个订单号重复派号（同号两行不同房源），跨日迁移按 order_code 互删导致逐日比对永远差 1 笔、无法出账。
> 关联：[Billing Balance Stats](./billing-balance-stats.md)、[Database Guidelines](./database-guidelines.md)（PG 时区契约）、[Error Handling](./error-handling.md)。

## Scenario: invoice-detail-consistency

### 1. Scope / Trigger
- 触发：结算单「两次打开数字不同」「Excel 三表数字互斥」「同周期重复生成」「当天数据反复漂移」四类缺陷的根治契约。
- 影响层：services（billing/order_sync/invoice_excel）、routes（billing/invoices）、tasks（sync_task_service/invoice_detail_generator）、DB（invoice_items 四列）。

### 2. Signatures
- 新增列（`invoice_items`，迁移 `f1a2b3c4d5e6`）：
  - `subtotal NUMERIC(12,2) NULL` — 递增多层/包年限量等复合小计（旧口径 `quantity × unit_price` 会算错，故必须冻结）
  - `order_count INTEGER NULL` — 计费订单数（VR 等 quantity 语义 ≠ 订单数的场景）
  - `multi_floor_pricing_type VARCHAR(20) NULL`（迁移 `g2h3i4j5k6l7`）— 多层计费类型冻结快照（incremental/unified）
  - `additional_floor_price NUMERIC(10,2) NULL`（迁移 `g2h3i4j5k6l7`）— 附加层单价冻结快照（多层递增第二层起）
- `billing._build_package_limited_breakdown(base_fee: Decimal, package_limits: dict, total_quantity: Decimal) -> dict` — 包年限量分解纯函数，`calculate_items_from_rules` 与 `get_invoice` 组装共用（防两处公式漂移）。返回 `package_type='limited'/base_fee/limit_count/in_package_quantity/over_limit_quantity/over_limit_unit_price/over_limit_cost/usage_cost/unit_price/subtotal`。
- `InvoiceService._check_invoice_period_overlap(customer_id, period_start: date | datetime, period_end: date | datetime)` — 周期去重（本地查询，生成入口唯一的前置校验）。
- `OrderSyncService._migrate_cross_day_orders(sync_date, saved_orders, detail_collector, emit)` — 跨日迁移清理。
- API：`GET /api/v1/billing/invoices/{id}` items 保持 20 字段结构，但 subtotal/order_count/multi_floor_pricing_type/additional_floor_price 改读冻结列（回退 `quantity × unit_price` / `quantity` / 实时 rule）。
- ~~`invoice_consistency.diff_period`~~ / ~~`InvoiceConsistencyError`：**已删除**（F1 移除，2026-11-09）。`InvoiceService` 构造不再接收 `external_engine`。
- `daily_orders` 唯一键（迁移 `h3i4j5k6l7m8`）：`UniqueConstraint("order_code", "sync_date")` → 表达式唯一索引 `uq_order_custom_sync_date (order_code, COALESCE(custom_code,''), sync_date)`；`order_sync` 三处判重键同步为 `(order_code, custom_code, sync_date)`。
- `generate_invoice` 落库 `InvoiceItem` 五冻结列：`subtotal`/`order_count`/`multi_floor_pricing_type`/`additional_floor_price`/`pricing_rule_id`（末列为详情页「计费类型」「计费规则」数据源，2026-11-09 补漏）。
- `daily_orders` 展示快照列（迁移 `i4j5k6l7m8n9`，F9）：19 列可空不回填 + `create_date`/`upload_date` 存原值 datetime（此前 `DATE()` 丢时刻）；`ORDER_SYNC_SQL` SELECT 29 列（索引注释 0-28）+ 4 个 nest_user LEFT JOIN；`_normalize_date` 已删。
- 明细生成链路：`generate_invoice_detail(session, invoice_id, session_factory)`（`external_engine` 参数已删）；`InvoiceExcelService(db, session_factory)`（`external_engine` 已删）；`generate_detail_file(..., order_details=List[Dict])`（`group_type`/`order_codes` 已删）；`DETAIL_SQL`/`_fetch_order_details`/`_row_to_dict` 已删，月份明细数据经 `invoice_detail_generator._order_row_to_dict` 组装。

### 3. Contracts
- **生成入口顺序**：`_check_invoice_period_overlap`（本地，便宜）→ 落库（items 写 `subtotal`/`order_count`/`multi_floor_pricing_type`/`additional_floor_price`，缺省 None）。**不查外部库**：外部改期/删除/重复派号等漂移不阻塞出账；漂移的收敛靠同步任务（`skip_existing` 仅跳历史日、当天强制完整同步；跨日迁移按 `(order_code, custom_code)` 清旧日行，见 F8）。
- **周期重叠判定**：`existing.period_start <= period_end AND existing.period_end >= period_start`，排除 `status='cancelled'` 与软删除行；相接不相交（前单 end < 后单 start）不误伤。
- **date 归一化**：`period_*` 为 `date`（无时刻）时必须转 `local_date_to_utc_start/end`——date 与 timestamptz 列直接比较按 UTC 00:00 解释，与 CST 业务日边界错位 8 小时（F5 已归一化）。
- **Excel 三表同源**（F2）：「合计」「计费明细」「月份明细」均从同一 `invoice.items` 过滤 `order_code ∈ invoice_items.order_codes` 后聚合；「计费明细」小计列读 `item.subtotal`（多层递增真实小计），不再重算 `quantity × unit_price`；「合计」数量口径 = `invoice_items.order_count` 之和（NULL → 0）。
- **月份明细快照化**（F9）：「月份明细」sheet 由 `daily_orders` 本地快照行渲染（detail_generator 查 `select(DailyOrder).where(customer_id, sync_date ∈ [period_start, period_end+1s), deleted_at IS NULL).order_by(create_date DESC, order_code, custom_code)` → `_order_row_to_dict` 26 键），不再实时查外部 MySQL（`DETAIL_SQL`/`_fetch_order_details`/`_row_to_dict` 已删）。三表（合计/月份明细/计费明细）严格同源，补生成历史单幂等（拿到出账时快照而非「当前」外部状态）。`daily_orders` 因此新增 19 个展示列 + `create_date`/`upload_date` 由 `DATE()` 改原值 datetime（迁移 `i4j5k6l7m8n9`，均可空不回填，历史行 NULL → 月份明细对应格空）；同步层 `ORDER_SYNC_SQL` SELECT 同批扩展 + 4 个 nest_user LEFT JOIN（creator/personal×2/publisher）。「合计」备注列差异检测保留为纯展示层防御（同源后恒等，覆盖出账后跨日迁移清理等快照变动场景）。dev 库历史回填脚本：`backend/scripts/backfill_daily_order_detail_columns.py`（外部仍在的数据可补，已删单补不回）。detail_generator 不再接收 `external_engine`/`group_type`（routes 触发 args 同步删）。
- **计费明细双口径**（F7）：「计费明细」订单数列 = `order_count ?? quantity`（订单口径，与「合计」数量列、「月份明细」行数一致），另设「楼层数」列 = `quantity`（保留 incremental 金额验算，如 36×14+(78−36)×11=966）；`multi_floor_pricing_type`/`additional_floor_price` 读 `invoice_items` 冻结列（生成时落库、与 subtotal/order_count 同批不回填），detail_generator 不再 JOIN PricingRule（防规则变更漂移 + 修复 join 恒空）；详情 API 两字段冻结优先，NULL 回退实时 rule。
- **pricing_rule_id 冻结**（F3 同批，2026-11-09 补漏）：`generate_invoice` 落库 `InvoiceItem` 必须传 `pricing_rule_id=item.get("pricing_rule_id")`（`calculate_items_from_rules` 产出的 items 含此键；手工 items 无此键 → None）。曾漏传导致全库 `invoice_items.pricing_rule_id` 恒 NULL → 详情 API `pricing_type`/`tiers`/包年分量取不到值 → 前端「计费类型」「计费规则」两列恒显示「—」（`formatRuleDetail` 首行 `if (!record.pricing_type) return ['—']`）。历史 370 行已按出账时刻（`invoices.created_at`）匹配当时生效规则回填（复刻 `_get_active_pricing_rules` 匹配语义）；VR 结算行（device_type=`VR设备`/`editor`，规则不在 pricing_rules）与无规则手工单保持 NULL，前端显示「—」为正确语义。
- **详情冻结快照**（F4）：`get_invoice` 不再实时调 `calculate_items_from_rules`；包年计算分量经查 `daily_consumptions.sum(order_count)` 还原（`has_package_item` 为假时零查询）；`get_invoice_by_id` 必须 `selectinload(Invoice.items).selectinload(InvoiceItem.pricing_rule)`，否则 async lazy load → MissingGreenlet。
- **同步层当天语义**（F6，易错点）：`skip_existing` 的跳过检查**仅对历史日期**生效；当天订单持续上传、任何快照都残缺，必须走完整同步（订单 + 费用）重拉。即 `if task.sync_mode == "skip_existing" and sync_date != cst_today():`。
- **跨日迁移**（F6）：同一 `(order_code, custom_code)` 在新日期批次落库后，删除其在非当天窗口 `[sync_date, sync_date+1d)` 的旧 `daily_orders` 行 → 按 `(customer_id, 旧日)` 聚合 → 逐旧日 `CostCalcService.calculate_daily_cost` 重算（幂等：先删后建）→ 每单 `SyncDetail(category="order_move", level="warning")`；异常上抛（execute_task 按天记 failed）。删除键**必须**含 `custom_code`（见 F8），否则同号其他房源行被误删。
- **房源级识别键**（F8，2026-11-09）：`daily_orders` 唯一键 = `(order_code, COALESCE(custom_code,''), sync_date)`（迁移 `h3i4j5k6l7m8`，表达式唯一索引——PG 唯一索引不约束 NULL，空 `custom_code` 归一为空串保持「订单号即唯一」原语义）。外部平台会把同一订单号派给多个房源（同号两行不同 house_id，实证：SZZY_1792727229 = 房源 826390/X + 826271/L），旧实现三处判重（`_match_and_save` 内存 `seen_keys`、DB 查重、`_migrate_cross_day_orders` 删除键）都只认 `order_code`，第二房源在同步入口即丢失、不计费。现在三处键统一为 `(order_code, custom_code, sync_date)`，一号多房源各自成行、各自计费。计费链路无需改动：`cost_calc._get_order_groups` 逐行 +1，一行即一笔。

### 4. Validation & Error Matrix
| 条件 | 行为 |
|---|---|
| 同客户已有未取消周期重叠单 | `ValueError("已存在同期结算单 {no}（周期重叠），请勿重复生成")` → 路由 `40001`；批量生成进 `skipped`（reason 含单号） |
| 本地快照与外部实时量有差异 | **不再校验、不阻塞**（快照即准）；外部明细仍按 `order_codes` 过滤进「月份明细」 |
| 外部库未配置/不可达 | 生成不受影响（不查询外部库）；明细 Excel 的「月份明细」查询失败记 error 并放行 |
| `daily_consumptions` 无数据（历史单） | 包年分量全 0；非包年项不受影响 |
| `invoice_items.subtotal` 为 NULL（迁移前历史行） | 详情回退 `quantity × unit_price`；`order_count` 回退 `quantity` |
| `invoice_items.multi_floor_pricing_type`/`additional_floor_price` 为 NULL（迁移前历史行） | Excel「计费明细」显示 '-'/空；详情回退实时 `rule` 两字段 |
| 同步任务范围为当天 | 强制完整同步（不查完整性、不跳过） |
| 订单 upload_date 跨日 | 删**同 (order_code, custom_code)** 旧行 + 重算旧日 + `order_move` warning；同号其他房源行不删（F8） |
| 同一订单号多个房源（外部重复派号） | 各自成行、各自计费（F8）；月份明细仍按外部实时渲染，行数可能与之有差（备注列暴露） |

### 5. Good/Base/Bad Cases
- Good：深圳中原地产 2026-10 在 3 笔外部改期 + 1 个重复订单号下仍可出账（金额取本地快照）；三表订单口径一致。
- Base：手工 items（无 subtotal）生成的单 → 冻结列 NULL，详情回退口径正确。
- Bad：生成前逐日比对外部实时量（旧 F1）→ 外部任何事后改期都能无限期阻塞出账（重复订单号场景下永远差 1 笔）；`get_invoice` 实时重算 → 两次打开中间插同步数字漂移；包年两处公式各写一份 → 改一处漏一处。

### 6. Tests Required
- `tests/unit/test_billing_service.py` — 包年分解（含 over_limit NULL 自动计价）、mock_db_session 默认 `first()→None`（防 F5 查询误伤既有单测）、多层计费两字段冻结落库、`test_generate_invoice_freezes_pricing_rule_id`（pricing_rule_id 冻结落库 + 手工 items 无键回退 None）。
- `tests/unit/test_invoice_excel.py` — 三表同源、subtotal 口径、计费明细双口径（订单数/楼层数列）、空串读回 None；generate_detail_file 经 to_thread 分发 + order_details kwargs 透传（无外部查询 mock）。
- `tests/unit/test_detail_recovery.py` — claim→items→order_codes 三次 execute 的 side_effect 序列（新增查询必须同步补桩）；items 查询必须 `scalars()` 解包 + 冻结列透传；`TestOrderRowToDict.test_maps_all_month_detail_keys` 钉住 26 键集合（快照加列必须同步补映射，否则月份明细对应列静默变空）。
- `tests/integration/test_invoice_generation_guard.py` — 快照即准：缺同步日/快照过期/外部不可达/引擎未配置均放行生成；批量生成漂移客户进 generated。周期去重另见 `test_invoice_period_dedup.py`。
- `tests/integration/test_invoice_period_dedup.py` — 40001 拒绝 + skipped + 相邻周期不误伤。
- `tests/unit/services/test_order_sync.py` — `test_match_and_save_same_code_two_houses_both_saved`（同号两房源两行均落库）、`test_match_and_save_null_custom_code_deduped_by_order_code`（空 custom_code 保持订单号语义）。
- `tests/unit/services/test_order_sync_cross_day.py` — `test_delete_key_includes_custom_code`（残留删除 WHERE 含 custom_code，同号其他房源行不误删）。
- `tests/unit/services/test_cost_calc.py` — 逐行 +1 聚合（一行 daily_orders = 一笔，F8 无需改动即正确）。
- `tests/services/test_sync_task_service.py` — `test_execute_task_today_force_resync`（当天强制重拉）、`test_verify_completeness_covers_today`（校验覆盖当天）。

### 7. Wrong vs Correct
#### Wrong（生成前比对外部实时量，漂移即阻塞）
```python
diffs = await diff_period(...)      # 已删除
if diffs:
    raise InvoiceConsistencyError(...)   # 外部改期 → 永远出不了账
```
#### Correct（快照即准）
```python
await self._check_invoice_period_overlap(...)   # 唯一前置校验（本地）
# 直接按 daily_orders/daily_consumptions 快照落库
```
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
#### Wrong（判重键只认订单号，一号多房源丢行）
```python
dedup_key = (order_code, sync_date)                       # 内存去重：第二房源 skipped
select(DailyOrder).where(DailyOrder.order_code == code)    # DB 查重：同号即重复
delete(DailyOrder).where(DailyOrder.order_code.in_(batch_codes))  # 跨日迁移：同号行全删
```
#### Correct（房源级识别键，F8）
```python
key = (order_code, custom_code or "", sync_date)                       # 三处统一
select(DailyOrder).where(
    DailyOrder.order_code == code,
    func.coalesce(DailyOrder.custom_code, "") == (custom_code or ""),
)
tuple_(DailyOrder.order_code, func.coalesce(DailyOrder.custom_code, "")).in_(batch_keys)
```
