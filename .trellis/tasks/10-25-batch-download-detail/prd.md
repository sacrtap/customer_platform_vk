# 结算单批量下载明细文件

## Goal

结算单列表（`frontend/src/views/billing/Invoices.vue`）批量勾选多张结算单后，一键把这些结算单**已生成完成**的明细 Excel 批量下载到本地。过程中用进度弹窗实时反馈（统计、跳过提示、逐项进度、取消、完成汇总）。

## Requirements

### 后端

1. 新增 `POST /billing/invoices/batch-download-detail`（`@auth_required` + `@require_permission("billing:view")`）：传入 `{ids: [...]}`，返回可见范围内每张结算单的 `id / invoice_no / customer_id / customer_name / detail_file_status`，供前端预检（哪些可下载/将跳过）与文件命名。
2. 数据可见性服务端强制：无 `customers:view_all` 时仅返回当前用户负责/协同客户的结算单（`Customer.manager_id` / `Customer.sales_manager_id`），与既有 `get_invoice_file_status` 的 scope 分支一致。
3. 空 `ids` 返回 400（错误码用 `ErrorCodes` 常量）；已软删结算单不出现在结果中。
4. 实际文件下载复用现有 `GET /invoices/<id>/download-detail`（逐个 blob 请求），本接口只提供元数据，不改动既有轮询接口 `GET /invoices/file-status` 的返回结构。

### 前端

5. 批量工具栏新增「批量下载明细」按钮（`billing:view` 可见），点击打开 `BatchDownloadDetailModal`。
6. `BatchDownloadDetailModal` 自包含下载逻辑（不进 `useInvoice` composable）：
   - `phase` 状态机：`loading → ready → downloading → done`；
   - `ready` 阶段显示「共 N 项 · 可下载 X 项」，`detail_file_status !== 'completed'` 的计为跳过并橙色提示「X 个明细文件未生成完成，将跳过」（不阻塞）；
   - `downloading` 阶段**串行**下载，实时显示 `第 i/N 个 · 成功 X · 失败 Y · 跳过 Z` + 当前文件名 + 进度条 + 取消按钮；
   - Chrome/Edge（File System Access API 可用）：`showDirectoryPicker()` 选目录后逐个写入；用户取消选目录（`AbortError`）回到 ready；Safari/Firefox 不支持时自动降级为浏览器逐个 `<a download>` 下载；
   - `done` 阶段汇总成功/失败/跳过 + 失败列表（`invoice_no + reason`），「关闭」按钮；不做失败重试。
7. 文件命名 `{客户名}-{结算单号}.xlsx`，与单条下载 `InvoiceDetailDrawer.handleDownload` 一致；客户名缺失回退 `#{customer_id}-{invoice_no}.xlsx`；客户名需做非法字符清洗（`\ / : * ? " < > |`、控制字符、首尾空白与点）。
8. 下载完成后不刷新列表（明细文件状态未变）。

## Acceptance Criteria

- [ ] `POST /billing/invoices/batch-download-detail` 集成测试：传 `{ids: [已完成, 未完成, 不存在, 他人客户]}` → 返回 list 仅含可见范围内存在的 id，字段含 `id/invoice_no/customer_id/customer_name/detail_file_status`；无 `customers:view_all` 的经理只能看到自己负责客户的 id；空 ids 返回 400
- [ ] `cd backend && python -m pytest tests/ -q` 通过（新增测试纳入覆盖率口径）
- [ ] `cd frontend && npx vitest run` 通过，新增组件测试覆盖：`sanitizeFilename` 剔除非法字符、`buildFileName` 命名与 `#id` 回退、ready 阶段统计与跳过提示、`showDirectoryPicker` 存在时走目录写入调用链、不存在时走 `<a>` click 降级分支、cancelled 后中断循环
- [ ] `cd frontend && pnpm type-check` 通过
- [ ] Chrome 手动端到端：勾选 2 已完成 + 1 未完成 → 进度框显示「可下载 2」「1 个未完成将跳过」→ 选目录 → 逐个写入 → 目录内 2 个命名正确的 `.xlsx` 可打开
- [ ] 新端点有 `@auth_required` + `@require_permission("billing:view")`；`cd backend && ruff check app/` 通过

## Constraints

- 不新增权限点（复用 `billing:view`）；不改动 `GET /invoices/file-status` 返回结构与 `useInvoice.pollFileStatus`。
- 串行下载：避免浏览器多文件下载拦截与目录写入竞态；大批量耗时较长可接受（不实现并发池）。
- 文件覆盖语义与浏览器默认下载一致（同名直接覆盖，不弹覆盖提示）。
- 明细文件不存在时单条端点返回 404，批量循环中归入 failed 列表，不阻塞。
