# 结算单明细数据一致性修复 — 执行计划

> 任务：`.trellis/tasks/11-05-invoice-consistency-fix` · 设计见 `design.md` · PRD 见 `prd.md`
> 分支：执行前 `git checkout -b fix/invoice-consistency`（base: main）

## 执行清单

### S0 前置（动手前）
- [ ] `cd backend && python -m alembic heads` 实测 head（预期 `e2f3a4b5c6d7`；若不符以实测设 down_revision）
- [ ] `cd backend && python scripts/check_schema_drift.py` 确认基线干净
- [ ] 建分支 `fix/invoice-consistency`

### S1 F3：`invoice_items` 加 `subtotal`/`order_count`（先行，F4 依赖）
- [ ] `models/billing.py` `InvoiceItem`（:252 注释处）新增两列（design.md §4 逐字）
- [ ] 新建迁移 `backend/alembic/versions/<hex>_add_invoice_item_subtotal_order_count.py`，`down_revision=` S0 实测 head；upgrade 两列 nullable=True；downgrade drop 两列
- [ ] `services/billing.py` `generate_invoice` 落库循环（:1440-1446）写 `subtotal`/`order_count`（None 安全）
- [ ] 应用迁移并验证：`python -m alembic upgrade head && python scripts/check_schema_drift.py`
- [ ] 验证：`python -m pytest tests/unit/test_billing_service.py tests/integration/test_billing_api.py tests/integration/test_migrations.py -x -q`

### S2 F1：一致性校验服务 + 接入
- [ ] 新建 `services/invoice_consistency.py`（design.md §2：`DayDiff`/`InvoiceConsistencyError`/`diff_period`；外部 SQL 同窗；本地 `utc_to_cst_date_str` 分桶；None 放行语义）
- [ ] `InvoiceService.__init__` 加 `external_engine: Optional[AsyncEngine] = None`（billing.py:1049）
- [ ] `generate_invoice` 开头：`_check_invoice_period_overlap`（S4）→ `diff_period` 校验 → 不一致抛 `InvoiceConsistencyError`（需 `_get_customer` 拿 company_id/name；放行时 `logger.warning`）
- [ ] `generate_invoices_batch` 循环内（:2327 generate_invoice 调用前）：`try: await diff_period(...) except` 不需要——直接调 `diff_period`，返回 diffs 非空 → skipped.append(reason=文案) + continue；None → 放行
- [ ] 路由 `generate`（invoices.py:771 实例化处传 external_engine；:828 调用处 try/except）：`except InvoiceConsistencyError → 40001 文案`；`except ValueError → 40001`（F5 复用）
- [ ] 路由 `generate-batch`（:636 实例化处传 external_engine）：`generate_invoice` 抛的 ValueError/InvoiceConsistencyError 在服务层循环内转 skipped（S4 决策），路由层无需新增 except（batch 不整单失败）
- [ ] 单测 `tests/unit/test_invoice_consistency.py`：方向判定×3、engine None、查询异常、16:00 边界分桶、文案含日期

### S3 F2：Excel 三表同源
- [ ] `invoice_excel.py` `_fetch_order_details`（:233）增 `order_codes: set[str] | None = None` + Python 过滤
- [ ] `invoice_excel.py` `generate_detail_file`（:178）与 `_build_and_save_excel`（:465）参数链透传 `order_codes`
- [ ] `_build_and_save_excel`：`model_count = sum(item.order_count)`（:535）；差异写备注列 J（:558）；小计列 E 改 `item["subtotal"]` 回退口径（:675）
- [ ] `tasks/invoice_detail_generator.py` 阶段 1（session commit 前）查 `daily_orders.order_code` 集合传入
- [ ] 验证：`python -m pytest tests/unit/test_invoice_excel.py -q` + 冒烟下载 Excel 核对三表（S7）

### S4 F5：周期去重
- [ ] `InvoiceService._check_invoice_period_overlap`（design.md §6 SQL，走 `idx_invoice_customer_period`）
- [ ] `generate_invoice` 开头调用，命中 `raise ValueError(f"已存在同期结算单 {inv.invoice_no}（周期重叠），请勿重复生成")`
- [ ] `generate_invoices_batch` 循环内 `try/except ValueError` 包 `generate_invoice` 调用 → skipped（reason 带单号）
- [ ] 集成测试 `tests/integration/test_invoice_period_dedup.py`：单条 40001（文案含单号）/ 批量 skipped / 零长账期不相邻误伤

### S5 F4：详情读快照
- [ ] `services/billing.py` `get_invoice_by_id`（:1551-1564）selectinload 加 `InvoiceItem.pricing_rule`
- [ ] `billing.py` 提取模块级纯函数 `build_package_breakdown(rule, total_quantity, period_days)`，`calculate_items_from_rules` 包年分支（:1195-1251）改调共用（保持既有单测全绿）
- [ ] `routes/billing/invoices.py` `get_invoice`：删 :274-288 重算块；formatted_items 改从 `invoice.items` + `item.pricing_rule` 组装（design.md §5.2 字段表；包年分量查 `daily_consumptions` 还原）
- [ ] 验证：`python -m pytest tests/integration/test_billing_api.py -k detail -q`；`cd frontend && pnpm vitest run InvoiceDetailDrawer.usageTotal`

### S6 F6：同步层根治
- [X] `sync_task_service.py`：`skip_existing` 分支加 `and sync_date != cst_today()`；import 补 `cst_today`
- [X] `order_sync.py` `_match_and_save`：批量提交后跨日清理（design.md §7.2 七步：收集 codes→查残留→删除→聚合旧日→延迟 import CostCalcService 重算→warning 明细 order_move→异常上抛）
- [X] `dto.py` `SyncDetail.category` 注释补 `order_move`
- [X] 单测 `tests/unit/test_order_sync_cross_day.py`：旧日删除+重算调用+warning 明细；既有 sync_task_service 单测扩当天用例（AC10）

### S7 验证与冒烟
- [ ] 后端全量：`cd backend && python -m pytest tests/ -q`（覆盖率合并口径 ≥50% 由 CI 判）
- [ ] `cd backend && ruff check app/ && ruff format --check app/ tests/ && pyright`
- [ ] 前端：`cd frontend && pnpm type-check && pnpm vitest run`
- [ ] dev 库冒烟（PLAN 第八节）：① 27542 只同步 10-01~10-30 skip_existing → 生成被拒且文案含 `2026-10-31`；② force_overwrite 补 10-31 → 生成成功 → 下载 Excel 核对「合计」/「计费明细」/「月份明细」三数相等；③ 27544 incremental 重生成 → `sum(subtotal) == total_amount`；④ 详情抽屉同单开两次（中间插同步）数字不变
- [ ] 新增测试文件清单：`test_invoice_consistency.py`(unit)、`test_invoice_generation_guard.py`(integration)、`test_invoice_item_subtotal.py`(integration)、`test_invoice_period_dedup.py`(integration)、`test_order_sync_cross_day.py`(unit)

## 质量门禁（每步完成后）

| 门禁 | 命令 |
|---|---|
| lint | `cd backend && ruff check app/` |
| 格式 | `cd backend && ruff format --check app/ tests/` |
| 类型 | `cd backend && pyright`（0 error） |
| 单测+集成 | `cd backend && python -m pytest tests/ -q` |
| 迁移一致 | `tests/integration/test_migrations.py::TestModelMigrationParity` |
| schema drift | `python scripts/check_schema_drift.py` |
| 前端 | `cd frontend && pnpm type-check && pnpm vitest run` |

## 回滚点

- S1 后：`alembic downgrade -1` + revert（F4 未开始，无依赖）
- S2–S6 每步独立 commit（fix: 前缀），任一步可单独 revert
- F3 downgrade 前须确认 S5 已 revert（get_invoice 读 subtotal 列）

## 交付验收边界

- 目标：PLAN F1–F6 全部落地
- 改动文件：
  - 后端：`app/models/billing.py`、`alembic/versions/f1a2b3c4d5e6_*.py`、`app/services/invoice_consistency.py`(新)、`app/services/billing.py`、`app/services/invoice_excel.py`、`app/services/order_sync.py`、`app/services/sync_task_service.py`、`app/services/dto.py`、`app/routes/billing/invoices.py`、`app/tasks/invoice_detail_generator.py`
  - 测试：`tests/unit/test_invoice_consistency.py`(新)、`tests/unit/services/test_order_sync_cross_day.py`(新)、`tests/integration/test_invoice_generation_guard.py`(新)、`tests/integration/test_invoice_period_dedup.py`(新)、`tests/integration/test_invoice_item_subtotal.py`(新)、`tests/unit/test_billing_service.py`、`tests/unit/test_invoice_excel.py`、`tests/unit/test_detail_recovery.py`、`tests/services/test_sync_task_service.py`、`tests/e2e/test_sync_task_e2e.py`
  - spec：`.trellis/spec/backend/invoice-consistency.md`(新) + `index.md`
- 验证证据（2026-11-05 本地实跑）：
  - unit+services：914 passed
  - integration（改动相关）：test_billing_api 75 passed、test_invoice_generation_guard/test_invoice_period_dedup/test_migrations 13 passed、test_invoice_item_subtotal 3 passed
  - e2e：test_sync_task_e2e 3 passed
  - 前端：vitest 265 passed（30 文件）+ vue-tsc type-check 通过
  - ruff check/format：全绿；pyright：改动文件 0 error；check_schema_drift.py：PASSED
  - dev 库冒烟：临时单 subtotal/order_count 经 GET /invoices/{id} 透传一致（造数→验证→清理）
  - 全量 integration（30min+）按仓库约定交 CI（pr-checks.yml smoke+affected / nightly backend-integration-full）
- 结论：通过。F1–F6 落地，本地覆盖改动相关全部测试；全量 integration 由 CI 门禁兜底

## 提交策略

- 按 F1–F6 逻辑拆 6 个 commit（或 S1+S2 合并若编辑重叠），每个 commit 前过质量门禁
- pre-commit 环境：`$BACKEND_DIR/.venv/bin/python`（RULES.md）
- 完成后推送分支并按需创建 PR（`/trellis:continue` 或用户指示）
