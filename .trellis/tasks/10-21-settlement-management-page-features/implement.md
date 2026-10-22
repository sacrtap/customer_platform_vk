# 结算单管理页面新功能 — Implement

## 执行顺序（按计划分组 A→E，每组独立可验证）

### A. 经理筛选项
1. `backend/app/services/billing.py` `get_invoices`：签名加 `manager_id`/`sales_manager_id`，erp_system 过滤后加 `Customer.manager_id ==` / `Customer.sales_manager_id ==` 过滤。
2. `backend/app/routes/billing/invoices.py` `get_invoices`：解析两个 query 参数并传入 service。
3. `frontend/src/api/billing.ts` `getInvoices` params 加 `manager_id?: string`、`sales_manager_id?: string`。
4. `frontend/src/views/billing/components/InvoiceFilters.vue`：Filters 接口加两字段；ERP 下拉后插入两个 FilterDropdown；`getManagers` 加载 + `managerOptions`/`salesOptions` computed。
5. `frontend/src/composables/useInvoice.ts`：`defaultFilters` 加两字段空串；`loadInvoices` 透传。

### B. 移除经理约束 + 无经理流程跳过
6. `backend/app/services/billing.py` `generate_invoices_batch`：删除两个 manager skip 块（docstring 同步更新）。
7. `submit_invoice` 改三分支；`confirm_ops` 改条件跳转（docstring 同步）。
8. `frontend/src/views/billing/components/GenerateInvoiceModal.vue`：删 eligibleCount 门禁；预览提示改纯信息文案。
9. `frontend/src/views/billing/components/InvoiceDetailDrawer.vue`：计费明细表格加空态占位。

### C. 流程条样式
10. `InvoiceDetailDrawer.vue` `.flow-steps` 增加 `:deep(.arco-steps-item-title/description)` 覆盖。

### D. 批量提交/取消/删除
11. `backend/app/services/billing.py`：新增 `batch_submit`/`batch_cancel`/`batch_delete`（内联状态转移 + `async with self.db.begin()` + 行内 scope 校验 + skipped 列表）。
12. `backend/app/routes/billing/invoices.py`：新增 `POST /invoices/batch-submit`、`/batch-cancel`、`/batch-delete`（`@auth_required` + `@require_permission` + 审计 + 缓存失效）。
13. `frontend/src/api/billing.ts`：新增三个 batch API。
14. `frontend/src/composables/useInvoice.ts`：选择状态 + handleBatchSelect/SelectAll/clearSelection + doBatchSubmit/Cancel/Delete + 导出。
15. `frontend/src/views/billing/Invoices.vue`：thead/tbody 加 checkbox；批量工具栏（v-if hasSelected）；Modal.confirm 确认。

### E. 明细生成状态
16. `backend/app/routes/billing/invoices.py` `get_invoice_detail_logs`：默认过滤改 `!= completed`；加 counts group_by 统计。
17. 新增 `POST /invoices/regenerate-detail-batch`；批量生成触发 `except` 改 `logger.warning`。
18. `frontend/src/api/billing.ts`：新增 `regenerateDetailBatch`。
19. 新建 `frontend/src/views/billing/components/DetailGenStatusDrawer.vue`；Invoices.vue PageHeader 加入口按钮 + failed 行内「重新生成」。

## 验证命令

- `cd backend && .venv/bin/python -m pytest tests/unit/test_billing_service.py tests/integration/test_billing_api.py -v`
- `cd backend && .venv/bin/python -m ruff check app/ && .venv/bin/python -m pyright`
- `cd frontend && npx vitest run src/composables/__tests__/useInvoice.test.ts && pnpm type-check`
- 冒烟：`cd backend && ./run_backend.sh` + `cd frontend && npm run dev` 手动验证计划 Verification 五条。

## 回滚点

每组独立提交前可 `git checkout` 对应文件；无 schema 变更，无迁移。

## 追加：明细生成链路故障修复（2026-10-21 晚）

用户报告"生成结算单，服务端还是会报错"，完整复现后定位 4 个独立根因（详见 `docs/specs/2026-10-21-invoice-detail-generation-failure-rootcause.md`）：

1. **IllegalCharacterError**：外部 MySQL 项目名含控制字符 → `invoice_excel.py` 加 `_ILLEGAL_XML_CHARS_RE` + `_clean_cell_text`，`_row_to_dict` 出口清洗 + ws2 写入兜底 + Sheet1 customer_name 清洗。
2. **naive/aware datetime 混用**：`recharge_records.created_at` 是 naive 列，period 是 timestamptz → `_fetch_balance_info` 查询前 `replace(tzinfo=None)`（该异常被 except 吞掉，症状是"当月充值恒 0"而非报错）。
3. **QueuePool 耗尽**：81 张单并行 add_job 占满连接池 → `invoice_detail_generator.py` 模块级 `asyncio.Semaphore(5)` 限流（任务体移入 `_generate_invoice_detail_inner`）+ `main.py` 本地池 `pool_size=20, max_overflow=10`。
4. **前端轮询缺陷**：`DetailGenStatusDrawer.vue` 只轮询 generating，pending 卡死无反馈 → 改 `needsPolling()` 覆盖 pending + `onUnmounted` 清理定时器。

### 修复验证（可复核）
- 8002 端口完整跑 `generate-batch`（81 张）→ 21:58 后日志 0 ERROR，新单全部 completed
- 历史 13 张 failed 单补跑后全部 completed，failed 清零
- 单测 641 passed（新增 3 个回归测试）；ruff / pyright 通过
- 复现冒烟数据（162 张测试单 + 314 条 invoice_items + xlsx）已按用户确认删除

### 遗留
- 93 张 pending 为历史单，用户可在「明细生成状态」抽屉一键补跑
- 全库 naive/timestamptz 混用隐患仅修复实际触发的一处，同类报错模式见 spec「已知边界」
