# 执行计划：结算单批量下载明细文件

## 前置核对（实施前先读）

- [ ] `backend/app/routes/billing/invoices.py`：`download_invoice_detail`（:2174）、`get_invoice_file_status`（:2568 起，局部导入模式与 scope 分支）、顶部导入区（`or_`、`customer_scope_user_id`、装饰器）、文件末尾位置
- [ ] `backend/app/constants/error_codes.py`：空列表/参数类错误既有常量（40002/40004 语义），选定「请选择要下载的结算单」对应常量
- [ ] `frontend/src/api/billing.ts`：`downloadInvoiceDetail`（:544）、`regenerateDetailBatch`（:573）之后的新增位置
- [ ] `frontend/src/views/billing/Invoices.vue`：工具栏（:28-43）、import 区（:380-388）、visible refs（:450-457）、`onBatchDelete`（:557 附近）、挂载区（:359-360）
- [ ] `frontend/src/views/billing/components/InvoiceDetailDrawer.vue`：`handleDownload` blob→`<a>` click 模式（:467）
- [ ] 既有测试惯例：`backend/tests/integration/test_billing_api.py`（file-status/batch 类用例）、`frontend/src/views/billing/components/__tests__/`（Vitest 挂载与 mock 模式）

## 实施步骤

### 1. 后端：新增批量元数据端点

- [ ] `backend/app/routes/billing/invoices.py` 末尾新增 `batch_download_detail_meta`（见 design.md 契约）
- [ ] 空 ids 返回 400 + `ErrorCodes` 常量
- [ ] 局部导入照搬 `get_invoice_file_status` 模式

### 2. 前端：API 函数

- [ ] `frontend/src/api/billing.ts` 末尾新增 `getBatchDownloadDetailMeta`

### 3. 前端：BatchDownloadDetailModal.vue

- [ ] 新建 `frontend/src/views/billing/components/BatchDownloadDetailModal.vue`：状态机、ready/downloading/done 三阶段 UI、进度条、取消
- [ ] `sanitizeFilename` / `buildFileName`（组件内）
- [ ] 目录写入分支 + `<a download>` 降级分支 + `AbortError` 回 ready
- [ ] 失败列表与汇总

### 4. 前端：Invoices.vue 接入

- [ ] 工具栏按钮、import、ref、handler、组件挂载

### 5. 测试

- [ ] 后端：`backend/tests/integration/test_billing_api.py` 新增用例（可见性过滤、字段完整、空 ids 400）
- [ ] 前端：`frontend/src/views/billing/components/__tests__/BatchDownloadDetailModal.test.ts` 新增用例（sanitize/buildFileName、ready 统计、目录写入链、降级 click、取消中断）

### 6. 验证

- [ ] `cd backend && ruff check app/ && python -m pytest tests/ -q`
- [ ] `cd frontend && npx vitest run && pnpm type-check`
- [ ] Chrome 端到端手动验证（DB 置 2 completed + 1 未完成，勾选下载，核对目录文件）

## 回滚点

- 后端：删新端点即可（无数据/迁移改动）。
- 前端：删新组件 + 还原 `billing.ts`/`Invoices.vue` 4 处接入。

## Review gates

- 步骤 1-4 完成后自检：装饰器齐全、无硬编码错误码、无 `any` 滥用（`showDirectoryPicker` 需 `window as any` 或全局类型声明，按 frontend type-safety 规范择一）、失败不吞异常。
