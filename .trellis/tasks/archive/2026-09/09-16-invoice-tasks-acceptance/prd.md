# 结算单两任务验收与归档

## Goal

对两个「**代码已实现、但 AC 未勾选、状态停留在 `in_progress`**」的历史任务执行**验收与归档**，消除 active 列表与事实不符的状态：

- `09-02-invoice-excel-discount-ui` —— 结算单明细文件生成 + 减免金额重构 + 详情 UI 优化（7 项 AC）
- `09-03-invoice-preview-enhance` —— 结算单生成优化-周期保留与计费明细预览增强（10 项 AC）

**本任务不新做功能开发**。仅在验收发现问题时，按已批准的范围修复。

## Background — 已确认事实（含证据）

### 1. 两任务代码均已落地（静态核实）

**`09-03`**：

| AC | 实现位置 |
|---|---|
| AC1 周期保留 + 客户清空 | `GenerateInvoiceModal.vue:382-387`（`form.customer_id = undefined`；注释「保留 batchPeriodRange，仅清空预览」） |
| AC2/AC3 自动刷新 | `handlePeriodChange` + `watch` |
| AC4–AC8 各计费类型渲染 | `pricingType` slot、`pricingTypeText`、`itemColumns`（`计费类型` 列） |
| AC9 API 字段透传 | `routes/billing/invoices.py:189-198`、`340-349`（`pricing_type`/`package_type`/`limit_count`/`over_limit_*`/`base_fee`） |
| AC10 批量周期保留 | 同上 `GenerateInvoiceModal.vue` |

**`09-02`**：

| AC | 实现位置 |
|---|---|
| AC1 异步生成 + 下载 | `app/tasks/invoice_detail_generator.py`；`routes/billing/invoices.py:1620` `download-detail` |
| AC1b 状态显示 | `invoices.py:98`（列表）、`258`（详情） |
| AC1c 侧边栏入口 | `composables/useAppLayout.ts:128`、`router/index.ts:181`、`views/system/InvoiceLogs.vue` |
| AC1d 重新生成 | `invoices.py:1653` `regenerate-detail` |
| AC2 双 Sheet | `services/invoice_excel.py`：`DETAIL_HEADERS` 29 列 + 「合计」Sheet（10 列 A–J）+ 额外「计费明细」Sheet |
| AC3 外部库映射 | `invoice_excel.py` 的 `DETAIL_SQL`：`FROM nest_model_order D` + 4 个 `nest_user` LEFT JOIN，按 `group_type` 与 `upload_date` 区间过滤 |
| AC4–AC7 减免重构 | `SubmitModal.vue`（允许负值，无 `min=0`）、`DiscountEditModal.vue`、`InvoiceDetailDrawer.vue`、`Invoices.vue`；文案已为「减免金额」「最终结算金额」 |
| 模型与迁移 | `models/billing.py:139-142`、`alembic/versions/p5q6r7s8t9u0_add_invoice_detail_file_fields.py` |

### 2. 运行环境（实测）

| 项 | 结果 |
|---|---|
| 后端 | `http://localhost:8000` → `/health` **200**（cwd 已确认为本项目 `backend/`） |
| 前端 | `http://localhost:5173` → **200**（vite，cwd `frontend/`） |
| PostgreSQL | 5432 监听中 |
| Redis | 6379 监听中 |
| 外部 MySQL | **可连接**：`SELECT 1` OK；`nest_model_order` **4,663,269 行 / 63 列** |
| 登录凭据 | `admin` / `admin123` → **HTTP 200, code 0**（`scripts/seed.py` 的标准种子账号） |

> 验收所需前置条件**全部满足**，无需额外准备。

### 3. 已知缺口

- `09-03` **缺 `design.md` 与 `implement.md`**（仅 `prd.md`），按 Trellis 流程属「规划未完成」。代码已实现，故建议以**实现记录**补记，而非补完整规划。
- 两个任务的 `prd.md` 中 AC **全部未勾选**。

## Requirements

- **R1** 逐条验收 `09-03` 的 AC1–AC10，每项给出「通过 / 不通过 / 无法验证」结论与证据。
- **R2** 逐条验收 `09-02` 的 AC1–AC7（含 AC1b/AC1c/AC1d），同上给出结论与证据。
- **R3** 优先级：**先 `09-03`（单文件 UI 改动，成本低）后 `09-02`（涉及异步任务、外部库、Excel 生成）**。
- **R4** 验收结论回写：勾选通过项、标注不通过项，并把证据写入本任务 `implement.md`。
- **R5** 归档两个历史任务。
- **R6** 验收过程若产生临时脚本/数据，须清理（不留在仓库）。
- **R7** 约定：不修改 `.github/workflows/`；不新增与本任务无关的重构。

## Acceptance Criteria

- [x] **AC-1** `09-03` 的 10 项 AC 逐条有结论与证据，无「未核」项。
- [x] **AC-2** `09-02` 的 7 项 AC（含 3 个子项）逐条有结论与证据，无「未核」项。
- [x] **AC-3** 涉及 UI 行为的 AC 有**实跑证据**（浏览器操作结果或 API 响应断言），非仅静态阅读代码。
- [x] **AC-4** `09-02` 的 Excel 交付物**实际生成并被读取校验**（至少核对两个 Sheet 名称、明细表头 29 列、数据行数与来源过滤条件）。
- [x] **AC-5** 两个历史任务的 `prd.md` AC 状态已按结论更新，任务状态改为与事实一致。
- [x] **AC-6** 两个历史任务已归档（`task.py archive`）。
- [x] **AC-7** 工作区无验收遗留物（临时脚本、调试输出、未提交的探针）。
- [x] **AC-8** 本任务 `implement.md` 含逐条验收结果表与证据引用。

## Out of Scope

- 为两个历史任务补充新功能（除非验收判为「不通过」且用户批准修复）。
- 补写 `09-03` 的完整 `design.md`（仅补实现记录）。
- 重构 `invoice_excel.py` / `GenerateInvoiceModal.vue` 的既有实现风格。
- 清理 `docs/technical_debt/test-infrastructure-residue-2026-09.md` 中登记的 TD-1..TD-5（另开任务）。
- 自动化回归测试的补写（除非某 AC 无法通过其他方式验证）。

## Resolved Decisions

1. **写入性验收：允许在当前开发库实跑**（用户已决定）。验收会创建测试结算单、生成 Excel 到 `uploads/invoices/`、查询外部库。产生的结算单 ID 与文件路径须在 `implement.md` 登记，便于后续清理。
2. **验收判「不通过」的处置：在本任务内修复**（用户已决定）。修复范围严格限于「使该 AC 成立」的最小改动，不做无关重构；修复后须重跑所有受影响的验收项与相关既有测试。
