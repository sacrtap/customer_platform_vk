# 结算单管理页面新功能 执行计划

## Context

结算单管理页面（`frontend/src/views/billing/Invoices.vue` + `backend/app/routes/billing/invoices.py`）需新增五项功能：(1) 销售经理/运营经理筛选项；(2) 批量提交/取消/删除（参考客户管理页多选）；(3) 修复结算流程示意图字体过大/截断（用户已澄清：付款确认环节无需新增——客户确认后自动扣款即变"已完成"，当前行为正确）；(4) 移除批量生成时"无运营/销售经理则跳过"的约束，并让流程对缺失经理的客户自动跳过对应确认步骤；(5) 明细文件异步生成状态可见化（列表增强 + 接线已有 detail-logs 日志页 + 批量重新生成）。

**已确认的决策**（用户答复）：
- 付款确认：不改状态机，`confirm_invoice` 保持 `pending_customer → customer_confirmed → 自动扣款 → completed`。
- 无经理客户流程：自动跳过缺失的经理确认步骤（不卡单）。
- 明细生成状态：列表增强 + 接线 detail-logs 日志页 + 批量重试。
- 无需新增权限点：批量提交/取消复用 `billing:edit`，批量删除复用 `billing:delete`，明细日志复用 `billing:view`。

## Approach

按行为分组，顺序构建（每组独立，可分别验证）。

### A. 经理筛选项（需求 #1）

**A1 后端 service** — `backend/app/services/billing.py` `get_invoices`（:1440 签名，:1460-1496 查询体）
- 签名新增参数：`manager_id: Optional[int] = None`、`sales_manager_id: Optional[int] = None`（插入 :1453 `mine_user_id` 之前）。
- 在 erp_system 过滤后（:1479 之后）新增：`if manager_id: stmt = stmt.where(Customer.manager_id == manager_id)` / `if sales_manager_id: stmt = stmt.where(Customer.sales_manager_id == sales_manager_id)`。
- Customer 已 inner join（:1467），直接过滤即可，无需额外 join。复用现有 `mine_user_id` 的 OR 过滤范式（:1490-1496）作对照。

**A2 后端 route** — `backend/app/routes/billing/invoices.py` `get_invoices`（:100-176）
- 在 erp_system 解析后（:112 之后）新增：`manager_id = int(request.args.get("manager_id")) if request.args.get("manager_id") else None` / 同理 `sales_manager_id`。
- 传入 service 调用（:125-136）追加 `manager_id=manager_id, sales_manager_id=sales_manager_id,`。

**A3 前端 API 类型** — `frontend/src/api/billing.ts` `getInvoices`（:386-396）
- params 类型新增 `manager_id?: string`、`sales_manager_id?: string`（与现有 `customer_id?: number` 等并列；用 string 因 FilterDropdown option value 为 string，后端 `int()` 解析）。

**A4 前端筛选器** — `frontend/src/views/billing/components/InvoiceFilters.vue`（136 行）
- `interface Filters`（:38-43）新增 `manager_id: string`、`sales_manager_id: string`。
- 模板：在 ERP FilterDropdown（:17-22）之后、「筛选」按钮（:23）之前，新增两个 `<FilterDropdown v-model="filters.manager_id" label="运营经理" :options="managerOptions" @apply="emit('search')" />` 与 `sales_manager_id`/`销售经理`。复用现有 FilterDropdown 组件（`@/components/ui/FilterDropdown.vue`，单选 modelValue:string）。
- script：`import { getManagers } from '@/api/users'`（已确认路径，useCustomerList/useBalance 均用此）。新增 `const managers = ref<Array<{id:number; real_name:string|null}>>([])`，在 `onMounted`（:58）内追加 `getManagers()` 加载（防御式解包 `res.data?.list || res.data || []`，镜像 :60-64 industryTypes 写法）。
- 新增 computed（镜像 `CustomerFilters.vue:206-218`）：`managerOptions`/`salesOptions` = `managers.value.map(m => ({ label: m.real_name || \`#${m.id}\`, value: String(m.id) }))`。两个下拉共用同一 managers 数组。

**A5 前端 composable** — `frontend/src/composables/useInvoice.ts`
- `defaultFilters`（:21-27）新增 `manager_id: ''`、`sales_manager_id: ''`。
- `loadInvoices`（:172-175）追加：`if (filters.manager_id) params.manager_id = filters.manager_id` / 同理 sales_manager_id。
- `handleReset`（:220 `Object.assign(filters, defaultFilters())`）已覆盖新字段，无需额外改。

### B. 移除经理约束 + 无经理流程跳过（需求 #4）

**B1 后端 service：移除经理跳过** — `backend/app/services/billing.py` `generate_invoices_batch`（:1976-2072）
- 删除 :2017-2026 两个 skip 块（`if not cust["manager_id"]` / `if not cust["sales_manager_id"]`）。删除后无经理客户进入正常生成流程。
- items-empty 跳过（:2038-2046）保持不变（无用量=无可结算，正确）。批量客户经 `get_customers_for_batch` 的 `pricing_type` 过滤（:1937-1945）必有规则，故 items-empty 仅出现于"有规则但本周期无用量"。

**B2 后端 service：无经理流程自动跳过** — `backend/app/services/billing.py`
- `submit_invoice`（:1626-1653）：将 :1642-1646 的二分支改为三分支：
  - `if customer and customer.manager_id:` → `pending_ops`（有运营经理，正常进入第一步）
  - `elif customer and customer.sales_manager_id:` → `pending_sales`（无运营但有销售，跳过运营直接待销售确认）
  - `else:` → `pending_customer`（两者均无，直接待客户确认）
- `confirm_ops`（:1655-1682）：将 :1676 `invoice.status = "pending_sales"` 改为条件：`if customer and customer.sales_manager_id: invoice.status = "pending_sales"` `else: invoice.status = "pending_customer"`（运营确认后若该客户无销售经理，跳过销售直达待客户确认）。
- `confirm_sales`（:1684-1711）不变（pending_sales → pending_customer，仅当有销售经理才会到达此状态）。

**B3 前端：移除经理门禁** — `frontend/src/views/billing/components/GenerateInvoiceModal.vue` `handleSubmitBatch`（:382-426）
- 删除 :396-400 的 `eligibleCount` 门禁（`previewCustomers.filter(c => c.has_manager && c.has_sales_manager).length === 0` → 报错返回）。改为：只要 `previewCustomers.length > 0` 即可生成（:391-394 的空匹配检查保留）。
- 预览区（:127-131）将"将跳过 N 个（未指定经理）"提示改为纯信息展示（不再阻止生成）。

**B4 前端详情：未配置计费规则占位** — `frontend/src/views/billing/components/InvoiceDetailDrawer.vue` 计费明细表格（:121-164）
- 当 `invoice.items` 为空时，渲染占位提示"该客户未配置计费规则或本周期无用量数据"替代空表格（`v-if="invoice.items?.length"` / `v-else` 占位）。纯展示，无新数据。

### C. 流程示意图字体/截断修复（需求 #3）

**C1 CSS 覆盖** — `frontend/src/views/billing/components/InvoiceDetailDrawer.vue` scoped style（:449-455 `.flow-steps`）
- 当前 `.flow-steps` 仅 background/border/radius/padding，无任何 `.arco-steps` 子元素覆盖（根因：Arco steps 默认字号偏大 + 720px 抽屉内 6 步 description 为人名触发截断/换行）。
- 新增 scoped 覆盖（`:deep`）：`.arco-steps-item-title { font-size: 13px; }` / `.arco-steps-item-description { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100px; }` / `.arco-steps { padding: 4px 0; }`。使人名 description 不换行、字号收敛。

### D. 批量提交/取消/删除（需求 #2）

参考客户管理页多选模式（原生 table + checkbox + 工具栏，非 Arco row-selection；见 `useCustomerList.ts:250-299` + `CustomerTable.vue:22-111` + `BatchToolbar.vue`）。

**D1 后端 service：批量方法** — `backend/app/services/billing.py` InvoiceService
- 新增 `async def batch_submit(self, invoice_ids: List[int], approver_id: int) -> Dict[str, Any]`：循环每条，复用 `submit_invoice` 的核心逻辑（查单→状态校验 draft→按 B2 三分支设状态→记 approver_id/approved_at），逐条 try/except 计入 skipped，最后 `await self.db.commit()` 单次提交。返回 `{success_count, skipped: [{id, reason}], success_ids: [...]}`。
- 新增 `async def batch_cancel(self, invoice_ids: List[int], user_id: int) -> Dict`：循环，仅对 status ∈ {draft,pending_ops,pending_sales,pending_customer} 的执行 cancel（复用 `cancel_invoice` :1865-1882 逻辑），其余 skip "当前状态不可取消"。
- 新增 `async def batch_delete(self, invoice_ids: List[int]) -> Dict`：循环软删（复用 `delete_invoice` :1884-1894），无状态限制。
- 为避免重复扣款/状态机错乱，批量方法内联状态转移逻辑（不调用会各自 commit 的单条方法），统一一次 commit。事务边界：方法内 `async with self.db.begin():` 包裹循环（遵循硬规则）。

**D2 后端 route：批量端点** — `backend/app/routes/billing/invoices.py`
- 新增 `POST /invoices/batch-submit`（@auth_required @require_permission("billing:edit")）：body `{ids: []}`，取 `user_id`，调 `invoice_service.batch_submit(ids, user_id)`，写 `create_audit_entry`（action="batch_submit"），返回 `{success_count, skipped}`。每条经 `_ensure_invoice_scope`（:52-66）数据可见性校验——在 service 循环内对每条调 scope 校验，越权的计入 skipped。
- 新增 `POST /invoices/batch-cancel`（@require_permission("billing:edit")）：同构，调 `batch_cancel`。
- 新增 `POST /invoices/batch-delete`（@require_permission("billing:delete")）：同构，调 `batch_delete`。
- 三个端点均返回 `{code:0, data:{success_count, skipped:[{id, reason}]}}`，镜像 `batch_update_customers`（customers.py:810-822）的 `{success,total,success_count,failed_count,failed_list}` 响应范式。

**D3 前端 API** — `frontend/src/api/billing.ts`
- 新增 `batchSubmitInvoices(ids: number[]) → api.post('/billing/invoices/batch-submit', {ids})`
- 新增 `batchCancelInvoices(ids: number[]) → api.post('/billing/invoices/batch-cancel', {ids})`
- 新增 `batchDeleteInvoices(ids: number[]) → api.post('/billing/invoices/batch-delete', {ids})`

**D4 前端 composable** — `frontend/src/composables/useInvoice.ts`
- 新增状态：`const selectedInvoiceIds = ref<number[]>([])`、`const hasSelected = computed(() => selectedInvoiceIds.value.length > 0)`。
- 新增 `handleBatchSelect(checked: boolean, id: number)`（镜像 useCustomerList:250-266：push/splice 去重）、`handleBatchSelectAll(checked: boolean, invoices: Invoice[])`（全选当前页 = `invoices.map(i=>i.id)`，取消 = `[]`）、`clearSelection()`（= `[]`）。
- 新增 `doBatchSubmit/doBatchCancel/doBatchDelete`：调对应 API，Message 提示 `成功 X 个，跳过 Y 个`，成功后 `loadInvoices()` + `clearSelection()`。
- 在 return 块（:364-394）导出上述新成员。

**D5 前端列表页多选 UI** — `frontend/src/views/billing/Invoices.vue`
- thead（:26-65）首列前插入全选 `<th style="width:40px"><input type="checkbox" :checked="allChecked" :indeterminate.prop="someChecked" @change="onToggleAll" /></th>`。`allChecked`/`someChecked` computed（镜像 CustomerTable:369-378）。
- tbody 行（:68-73）首列前插入 `<td @click.stop><input type="checkbox" :checked="selectedInvoiceIds.includes(record.id)" @change="onSelectRow($event, record.id)" /></td>`。
- PageHeader #actions（:5-13）或表格上方插入批量工具栏（`v-if="hasSelected"`）：显示"已选择 N 项" + 按钮「批量提交」(can('billing:edit'))/「批量取消」(can('billing:edit'))/「批量删除」(can('billing:delete')）。批量提交/取消/删除均包 `Modal.confirm` 确认（镜像 :553-561 cancel 的 Modal.confirm 范式），删除确认文案明确不可恢复。
- 翻页/搜索/重置时是否清空选择：与客户管理一致——跨页保留（不清空），全选仅当前页。

### E. 明细文件生成状态（需求 #5）

**E1 后端：扩展 detail-logs 端点** — `backend/app/routes/billing/invoices.py` `get_invoice_detail_logs`（:2194-2286）
- 将默认过滤 `Invoice.detail_file_status != "pending"`（:2216, :2219）改为 `Invoice.detail_file_status != "completed"`（默认显示 pending/generating/failed = 待处理队列 + 失败；completed 用 status_filter 显式查看）。
- 响应 data 新增 `counts: {pending, generating, completed, failed}` 统计（对当前 scope 内全量统计各状态数，不受分页影响）：用一条 `select(Invoice.detail_file_status, func.count()).group_by(...)` 查询。
- 保留 status_filter（:2240-2242）可精筛任意状态（含 completed）。

**E2 后端：批量重新生成端点** — `backend/app/routes/billing/invoices.py`
- 新增 `POST /invoices/regenerate-detail-batch`（@auth_required @require_permission("billing:edit")）：body `{ids: []}`，循环对每条 `_trigger_detail_generation(request, id)`（:83），逐条 try/except（失败计入 failed 列表，不再静默 `except: pass`，改为 `logger.warning`）。返回 `{code:0, data:{triggered: N, failed:[{id, reason}]}}`。

**E3 后端：批量生成触发失败可见化** — `backend/app/routes/billing/invoices.py`
- `generate_invoices_batch` route（:642-649）将 `except Exception: pass` 改为 `except Exception as e: logger.warning(f"结算单 {inv_id} 明细生成触发失败: {e}")`（不再静默吞掉）。单条 generate（:765）与 regenerate-detail（:2189）的 `_trigger_detail_generation` 调用本就不吞异常，保持。

**E4 前端 API** — `frontend/src/api/billing.ts`
- `getInvoiceDetailLogs`（:538-545）已存在但无调用点；新增 `regenerateDetailBatch(ids: number[]) → api.post('/billing/invoices/regenerate-detail-batch', {ids})`。

**E5 前端：明细生成状态抽屉** — 新建 `frontend/src/views/billing/components/DetailGenStatusDrawer.vue`
- `a-drawer` 从 Invoices.vue PageHeader「明细生成状态」按钮打开。调用 `getInvoiceDetailLogs({status, page, page_size})`，展示：状态筛选 tabs（全部/待生成/生成中/失败/已完成，用 counts 作 badge）+ 表格（结算单号/客户/周期/状态徽标/更新时间/操作）+ 失败行「重新生成」+ 底部「批量重新生成失败项」（调 `regenerateDetailBatch`）。
- 重新生成后轮询刷新（复用 `getInvoiceFileStatus` 思路：对 triggered 的 id 轮询直到 completed/failed）。

**E6 前端列表：失败行内重生成** — `frontend/src/views/billing/Invoices.vue` 文件列（:54 `文件` th + 对应 td）
- 对 `detail_file_status === 'failed'` 的行，文件单元格内除 ❌ 图标外增加「重新生成」文字按钮，调 `regenerateInvoiceDetail(id)`（:534 已存在）+ 触发 `startPolling()`。

## Critical files & anchors

1. `backend/app/services/billing.py` — `get_invoices`(:1440) 加筛选参数；`generate_invoices_batch`(:1976) 删经理跳过(:2017-2026)；`submit_invoice`(:1626)/`confirm_ops`(:1655) 改无经理三分支；新增 `batch_submit/batch_cancel/batch_delete`。
2. `backend/app/routes/billing/invoices.py` — `get_invoices`(:100) 加 query 参数；`get_invoice_detail_logs`(:2194) 改默认过滤+counts；新增 batch-submit/cancel/delete + regenerate-detail-batch 端点；:647 触发失败改 warning。
3. `frontend/src/views/billing/Invoices.vue` — 表头/行加 checkbox(:26,:68)；批量工具栏；失败行内重生成；打开明细状态抽屉。
4. `frontend/src/views/billing/components/InvoiceFilters.vue` — 加运营/销售经理 FilterDropdown + getManagers 加载。
5. `frontend/src/composables/useInvoice.ts` — defaultFilters/loadInvoices 加经理参数；批量选择状态+方法；导出。

（次要：`InvoiceDetailDrawer.vue` 未配置计费规则占位 + steps CSS；`GenerateInvoiceModal.vue` 删 eligibleCount 门禁；`billing.ts` 加 5 个 API；新建 `DetailGenStatusDrawer.vue`。）

## Verification

工作目录 `customer_platform_vk`，后端用 `$BACKEND_DIR/.venv/bin/python`（Python 3.12）。

**后端单元测试** — `backend/tests/unit/test_billing_service.py` 追加：
- `test_get_invoices_filter_by_manager`：构造 2 客户分属不同运营经理 + 各自结算单，断言 `get_invoices(manager_id=X)` 仅返回 X 负责的。
- `test_get_invoices_filter_by_sales_manager`：同上对 sales_manager_id。
- `test_generate_batch_no_manager_skip`：无经理客户不再被 skip，断言出现在 generated。
- `test_submit_sales_only_customer`：仅销售经理的客户 submit → `pending_sales`；`test_confirm_ops_no_sales_jumps_to_customer`：有运营无销售，confirm_ops → `pending_customer`。
- `test_batch_submit_partial`：[draft, pending_ops, draft] 批量提交 → 2 success + 1 skipped（状态不可提交）。
- `test_batch_cancel_mixed` / `test_batch_delete`：混合状态，验证 success_count/skipped。

**后端集成测试** — `backend/tests/integration/test_billing_api.py` 追加：
- `GET /api/v1/billing/invoices?manager_id=3&sales_manager_id=5` 返回正确子集（带鉴权 header）。
- `POST /invoices/batch-submit` body `{ids:[...]}` → 200 + `data.success_count`。
- `POST /invoices/batch-delete` → 软删验证。
- `GET /invoices/detail-logs` 默认不含 completed；`?status=failed` 仅失败；`data.counts` 各状态数正确。
- `POST /invoices/regenerate-detail-batch` → triggered 计数。

运行：`cd backend && .venv/bin/python -m pytest tests/unit/test_billing_service.py tests/integration/test_billing_api.py -v`。覆盖率口径 `--cov-fail-under=50`。

**前端** — 新建 `frontend/src/composables/__tests__/useInvoice.test.ts`：
- `loadInvoices` 设置 `filters.manager_id` 时 params 含 `manager_id`（mock getInvoices 断言入参）。
- `handleBatchSelect` 去重/移除；`handleBatchSelectAll` 全选当前页。
- `doBatchSubmit` 调 `batchSubmitInvoices` 并成功后 clearSelection（mock api）。
运行：`cd frontend && npx vitest run src/composables/__tests__/useInvoice.test.ts`。

**手动 UI 验证**（`cd backend && ./run_backend.sh` + `cd frontend && npm run dev`）：
1. 结算单列表选运营经理下拉 → 列表仅该经理客户；重置清空。
2. 勾选多行 → 批量工具栏出现 → 批量提交（draft 单）成功，非 draft 被跳过并提示。
3. 生成结算单弹窗批量模式：对无经理客户点生成 → 不再报"均未指定经理"，成功生成。
4. 详情抽屉流程条字号变小、人名不截断；无计费规则客户的空明细显示占位文案。
5. 点「明细生成状态」→ 抽屉显示各状态统计 + 失败项 + 批量重新生成；列表 failed 行有「重新生成」。

## Assumptions & contingencies

- **批量全选范围**：全选仅当前页（与客户管理一致），跨页保留选中。如需全选所有匹配结果需额外端点——本计划不实现，列表分页量级下当前页够用。
- **批量提交对非 draft 单**：计入 skipped（reason "状态不可提交"），不报错中断——与客户管理 batch_update 的 failed_list 范式一致。
- **无用量 vs 无规则**：批量生成（pricing_type 过滤）客户必有规则，items-empty = 本周期无用量 → 仍 skip（无可结算）。单客户无规则场景由详情页占位文案覆盖。如实际需要"无规则也生成"，在 `generate_invoices_batch` items-empty 块加一条 PricingRule EXISTS 查询，无规则则 generate 空 items——当前不实现（UI 批量必带 pricing_type，不会触发）。
- **detail-logs 默认过滤改动**：从 `!= pending` 改为 `!= completed`。该端点前端此前无调用点（死端点），改默认安全；不影响 file-status 轮询端点（:2289 独立）。
- **流程图 steps 对跳过步骤的显示**：无经理客户 draft→pending_customer→completed，a-steps 会将跳过的运营/销售步骤显示为已完成（绿）。时间线 InvoiceTimeline 仅显示实际有 timestamp 的节点（无 paid_at 则不显示"确认付款"，符合用户澄清的真实流程）。可接受，不改 steps 节点定义以保持旧流程 paid 数据兼容。
