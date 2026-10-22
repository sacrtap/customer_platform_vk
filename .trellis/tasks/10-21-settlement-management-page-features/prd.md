# 结算单管理页面新功能 — PRD

## 需求来源

`docs/specs/2026-10-21-settlement-management-page-plan.md`（执行计划，含已确认决策与锚点核验）。

## Requirements

1. **经理筛选（A）**：结算单列表支持按运营经理、销售经理筛选；后端 service/route 加 `manager_id`/`sales_manager_id` 过滤，前端筛选器加两个下拉（复用 `FilterDropdown` + `getManagers`），composable 透传参数，重置清空。
2. **移除经理门禁 + 无经理流程跳过（B）**：
   - 批量生成不再跳过"未指定经理"的客户（items-empty 跳过保留）。
   - 状态机自动跳过缺失经理的确认步骤：`submit_invoice` 三分支（有运营→pending_ops；无运营有销售→pending_sales；都无→pending_customer）；`confirm_ops` 后无销售经理直达 pending_customer。
   - 前端生成弹窗删除 eligibleCount 门禁；预览区提示改为纯信息展示；详情抽屉空 items 渲染占位文案。
3. **流程示意图修复（C）**：`InvoiceDetailDrawer.vue` `.flow-steps` 增加 Arco steps 字号/截断 scoped 覆盖。
4. **批量提交/取消/删除（D）**：后端 `InvoiceService` 新增 `batch_submit`/`batch_cancel`/`batch_delete`（统一事务、逐条 try/except 计 skipped、行内做数据可见性校验）；三个 route 端点（权限分别 billing:edit / billing:edit / billing:delete）；前端 API + composable 选择状态与方法 + 列表多选 UI 与批量工具栏（Modal.confirm 确认）。
5. **明细生成状态可见化（E）**：detail-logs 默认过滤改 `!= completed` 并返回各状态 counts；新增 `POST /invoices/regenerate-detail-batch`；批量生成触发失败改 logger.warning；前端新建 `DetailGenStatusDrawer.vue`（tabs + counts badge + 失败行重生成 + 批量重试）；列表 failed 行增加行内「重新生成」。

## Constraints

- 不新增权限点；批量提交/取消复用 `billing:edit`，批量删除复用 `billing:delete`，明细日志复用 `billing:view`。
- 不改 `confirm_invoice` 状态机（pending_customer → customer_confirmed → 自动扣款 → completed）。
- 批量全选仅当前页，跨页保留选中（与客户管理一致）。
- 所有写操作在 `async with db.begin()` 事务内；新 route 必须 `@auth_required` + `@require_permission`。
- 后端 Python 3.12 + `$BACKEND_DIR/.venv/bin/python`；前端 vue-tsc + vitest。

## Acceptance Criteria

- [ ] `GET /api/v1/billing/invoices?manager_id=X&sales_manager_id=Y` 返回正确子集（越权仍受 mine_user_id 约束）。
- [ ] 批量生成：无经理客户出现在 generated；有规则无用量客户仍 skip。
- [ ] `submit_invoice` 三种经理组合分别进入 pending_ops / pending_sales / pending_customer；`confirm_ops` 对无销售经理客户直达 pending_customer。
- [ ] `POST /invoices/batch-submit|batch-cancel|batch-delete` 对混合状态返回 `success_count` 与 `skipped[{id,reason}]`，单次事务提交，越权单条计入 skipped。
- [ ] `GET /invoices/detail-logs` 默认不含 completed，`data.counts` 四状态统计正确，`?status=failed` 精筛生效。
- [ ] `POST /invoices/regenerate-detail-batch` 返回 triggered/failed；批量生成触发失败有 warning 日志。
- [ ] 前端：筛选下拉可用并随重置清空；多选工具栏按权限显示；明细状态抽屉展示 counts/tabs/批量重试；failed 行有行内重生成。
- [ ] `cd backend && .venv/bin/python -m pytest tests/unit/test_billing_service.py tests/integration/test_billing_api.py -v` 全绿；`cd frontend && npx vitest run src/composables/__tests__/useInvoice.test.ts` 全绿；`vue-tsc` 通过。

## Notes

- 计划锚点已与当前代码核验一致（`get_invoices` :1440、`submit_invoice` :1626、`confirm_ops` :1655、`generate_invoices_batch` :1976、route `get_invoices` :100、detail-logs :2193、批量触发 :642）。
- 该任务跨前后端，由主会话直接实现（inline 平台，跳过 sub-agent dispatch）。
