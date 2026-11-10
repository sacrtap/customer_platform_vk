# 结算单明细数据一致性修复 — PRD

> 来源：`结算单明细数据一致性修复_技术方案_续_PLAN.md`（2026-11-05 与用户确认定稿）
> 范围 = 一致性 + 同步层根治；快照与外部不一致时**拒绝生成并提示重新同步**；历史脏数据本次不动。

## 背景与问题

生产两张结算单（1448 / 1650，常州我爱我家 customer 27544）出现三处数据不一致：

1. **计数不一致**：Excel「合计」sheet 模型数 233（11-02 实时查外部 MySQL）vs「计费明细」228（10-31 冻结快照），差额 = +10 漏算 −4 过期 −1 重复。
2. **金额不一致**：`InvoiceItem` 不存 subtotal，多层递增（incremental）模式下明细小计合计 ≠ `invoices.total_amount`（实证 2 张，差 −126.00 = 3 ×(120−78)）。
3. **详情抽屉实时重算**：`get_invoice` 每次打开重算 `calculate_items_from_rules`，中间插入同步即数字变化，与冻结快照漂移。

根因链：每日自动同步关闭（`daily_sync.enabled=f`）；`skip_existing` 当天数据持续上传仍整体跳过；生成/明细全链路无「冻结快照 vs 外部实时量」比对。

## 需求（F1–F6）

### F1 生成前一致性校验（核心，阻断）
- 新服务 `invoice_consistency.py`：逐日比对外部 MySQL 实时可结算订单数 vs 本地 `daily_orders` 快照行数（CST 日分桶，与 `local_date_to_utc_start()` 同窗）。
- 不一致时抛 `InvoiceConsistencyError`（`ValueError` 子类），文案给出客户名 + 差异日期清单 + 可执行修复动作（「对上述日期执行强制覆盖模式同步后重新生成」）。
- 外部库不可达（含引擎未配置）→ 返回 None，调用方记 warning 放行，不因基础设施故障阻塞业务。
- 接入：`InvoiceService.generate_invoice()` 开头、`generate_invoices_batch()` 循环内（不一致进 `skipped`，不阻断其它客户）；`generate` 路由捕获 → 40001；`regenerate-detail` 不跑校验（备注列兜底）。

### F2 明细 Excel 三表同源
- `_fetch_order_details()` 增 `order_codes` 参数，非 None 时 Python 侧按 `order_code` 过滤（不改 SQL）。
- `invoice_detail_generator` 查询该客户该周期 `daily_orders.order_code` 集合传入；空集合 → 月份明细空表。
- 「合计」sheet 模型总数量/计费模型数量均取 `sum(invoice_items.order_count)`；与外部实时量不一致时差异写「备注」列（兜底，正常链路已被 F1 拦住）。
- 「计费明细」sheet 小计列由 `quantity * unit_price` 改为 `item["subtotal"]`。

### F3 `invoice_items` 增加 `subtotal` / `order_count`
- 两列均可空、**不回填**；Alembic 迁移接当前 head，`downgrade()` 删两列。
- `generate_invoice()` 落库时从 `item["subtotal"]` / `item["order_count"]` 写入（`calculate_items_from_rules` 六分支已全部产出这两键，无需改计算）。
- 展示层 `COALESCE(subtotal, quantity*unit_price)`、`order_count ?? quantity`，历史文件行为不变。

### F4 详情抽屉读冻结快照
- `get_invoice` 删除 `calculate_items_from_rules` 实时重算块（含 `TierFormatError` 分支），改为 `selectinload(Invoice.items).selectinload(InvoiceItem.pricing_rule)` 组装响应。
- 响应字段结构与现状完全一致（20 字段）；`order_count`/`subtotal` 有兜底；前端零改动，既有 `InvoiceDetailDrawer.usageTotal.test.ts` 必须继续通过。
- 包年计算字段（`usage_cost`/`over_limit_*`/`period_days` 等，前端 `invoiceFormatters.formatRuleDetail` 在消费）见 design.md「包年字段还原」决策。

### F5 结算单周期去重
- `_check_invoice_period_overlap(customer_id, period_start, period_end)`：同客户未删除、非 cancelled、周期重叠 → 抛 `ValueError`（文案带已有单号）；批量场景进 `skipped`（reason = `已存在同期结算单 INV-xxx`）。
- 用既有索引 `idx_invoice_customer_period`。

### F6 同步层根治
- `execute_task()` 的 `skip_existing` 分支加当天判断：`sync_date == cst_today()` 时不做完整性跳过（当天数据持续上传，任何快照都残缺，重复执行必须重拉）。
- `order_sync._match_and_save()` 保存前跨日清理：本批 `order_codes` 中 `sync_date` 不在当天的旧行 → 删除 → 对受影响 `(customer_id, old_day)` 重算消耗（`calculate_daily_cost` 幂等）→ 每条迁移写 `SyncDetail(level="warning", category="order_move")`。
- `order_sync` 对 `cost_calc` 延迟 import（避免循环依赖）。

## 明确不做（本次范围外）

- 开启 `daily_sync` 自动同步（配置变更，需用户确认后单独执行）。
- 历史脏数据修复（PLAN 第七节：删重复单 1603、force_overwrite 重同步 10-24~10-31、复核 233/233、重生 1385 明细）——用户择机执行，本次只提供能力。
- `PricingRule.pricing_type` 的 `tier`/`tiered` 命名不一致（当前无 `tier` 数据，另开 issue；F4 只透传不改语义）。
- `DETAIL_SQL` 未按 `owner_company` 二次过滤的潜在脆弱点（当前 group_type 与公司 1:1）。
- `/invoices/generate` 显式传 items 路径的文档注明（F1 会正常校验；该路径绕过快照属调用方选择，接口文档注明即可，不改行为）。

## 验收标准

| # | 验收项 | 验证方式 |
|---|---|---|
| AC1 | 部分日期未同步 → 单张生成被拒，40001，文案含差异日期 | 集成测试 `test_invoice_generation_guard.py` |
| AC2 | 批量生成中不一致客户进 skipped（reason 含差异日期），其它客户正常生成 | 同上 |
| AC3 | 外部库不可达（engine=None 或异常）→ 放行 + warning 日志，不阻塞 | 单元测试 `test_invoice_consistency.py` |
| AC4 | `+ INTERVAL 8 HOUR` CST 分桶正确（16:00 UTC 边界样本归次日） | 单元测试 |
| AC5 | incremental 模式 `sum(invoice_items.subtotal) == invoices.total_amount` | 集成测试 `test_invoice_item_subtotal.py` |
| AC6 | 历史行 subtotal NULL → 详情/Excel 展示回退 quantity×unit_price，行为不变 | 集成测试 |
| AC7 | 详情接口两次打开数字不变（中间插入同步）；字段结构与改动前一致（20 字段） | 集成测试 + 前端既有 `usageTotal.test.ts` 通过 |
| AC8 | 同周期二次生成被拒（文案带已有单号）/ 批量跳过 | 集成测试 `test_invoice_period_dedup.py` |
| AC9 | `upload_date` 跨日变更后：旧日 `daily_orders` 行被删、旧日 `daily_consumptions` 重算、warning 明细落库 | 单元测试 `test_order_sync_cross_day.py` |
| AC10 | 当天 `skip_existing` 重复执行重拉订单（不再整体跳过） | 单元测试 |
| AC11 | 模型↔迁移一致性守卫 `TestModelMigrationParity` 通过；`alembic upgrade head` 应用到运行库 | CI + 本地 |
| AC12 | dev 库冒烟：只同步 10-01~10-30 → 生成被拒含 10-31；补同步 → 三表数字一致；27544 重生 `sum(subtotal)==total_amount` | 手工冒烟（PLAN 第八节） |
| AC13 | 质量门禁：`pytest` 全量 + `ruff` + `pyright` 0 error；前端 `vue-tsc` + `vitest` | CI |

## 风险与回滚

| 风险 | 缓解 |
|---|---|
| F1 误报卡业务 | 外部不可达放行；272 笔 16:00 边界样本已验证分桶口径 |
| F6 跨日清理误删 | 仅 `order_code` 完全匹配且 `sync_date` 非当天；删后立即重算，异常回滚 |
| F3 迁移影响历史数据 | 两列可空、不回填、COALESCE 兜底，历史文件零变化 |
| F4 详情接口响应变化 | 字段结构不变；包年字段经 daily_consumptions 还原（design.md 决策 D2） |

回滚：F1/F2/F4/F5/F6 纯代码 revert；F3 迁移 `downgrade()` 删两列。
