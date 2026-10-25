# 技术设计：结算单批量下载明细文件

## 边界

| 层 | 改动 | 不改动 |
|---|---|---|
| 后端 | 新增 1 个元数据端点 `POST /billing/invoices/batch-download-detail` | 单条 `GET /invoices/<id>/download-detail`、轮询 `GET /invoices/file-status`、`useInvoice.pollFileStatus` |
| 前端 API | `billing.ts` 新增 `getBatchDownloadDetailMeta` | `downloadInvoiceDetail` |
| 前端组件 | 新建 `BatchDownloadDetailModal.vue`；`Invoices.vue` 接按钮/挂载 | `InvoiceDetailDrawer.handleDownload`、`DetailGenStatusDrawer` |
| 权限 | 无新增（复用 `billing:view`） | seed / 测试权限清单 |

## 后端设计

**端点**：`POST /billing/invoices/batch-download-detail`

- 装饰器：`@billing_bp.post` + `@auth_required` + `@require_permission("billing:view")`（与单条 `download_invoice_detail` 一致）。
- 请求：`{"ids": [int, ...]}`；空 ids → `ErrorCodes` 常量（沿用 40004 语义「请选择要下载的结算单」，取既有常量，见实现时核对 `error_codes.py`）。
- 查询：`sa_select(Invoice.id, Invoice.invoice_no, Invoice.customer_id, Customer.name, Invoice.detail_file_status)` + `outerjoin(Customer)` + `Invoice.id.in_(ids)` + `Invoice.deleted_at.is_(None)`。
- 可见性：`scope_user_id = await customer_scope_user_id(request)`；非 None 时追加 `or_(Customer.manager_id == scope_user_id, Customer.sales_manager_id == scope_user_id)`——与 `get_invoice_file_status`（invoices.py:2600-2608）scope 分支同构；scope 为 None（有 `customers:view_all`）时 outerjoin 仅用于取客户名，不过滤。
- 响应：`{code: 0, data: {list: [{id, invoice_no, customer_id, customer_name, detail_file_status}]}}`，`detail_file_status` 空值回退 `"pending"`。
- 导入：函数内局部导入 `Invoice` / `Customer` / `sa_select`（照搬同文件 `get_invoice_file_status` 既有模式，该文件顶部无这些符号）；`or_`、`customer_scope_user_id`、`auth_required`、`require_permission` 顶部已导入。
- 不落库、无副作用、不进事务（只读查询）。

**为什么不复用 `GET /invoices/file-status`**：它是轻量轮询接口，只返回 `{id, detail_file_status, detail_file_path}`，缺命名所需 `invoice_no`/`customer_name`；扩展会改变轮询语义与返回结构、影响 `useInvoice.pollFileStatus`。故独立端点。

## 前端设计

### API 层（`api/billing.ts`）

```ts
export function getBatchDownloadDetailMeta(ids: number[]) {
  return api.post('/billing/invoices/batch-download-detail', { ids })
}
```

### 组件 `BatchDownloadDetailModal.vue`

- 契约：`props: { visible: boolean; ids: number[] }`，`emit update:visible`；Arco `a-modal` `width=520` `mask-closable=false` `:footer=false`。
- 状态机 `phase: 'loading' | 'ready' | 'downloading' | 'done'`：
  - `watch(visible)` → true 时调 meta 接口，派生 `completed`（`detail_file_status === 'completed'`）与 `skipped`，失败 `Message.error('获取下载信息失败')` 后关闭；
  - `ready`：统计行 + 跳过橙色提示（`skipped > 0`）+「开始下载」「取消」；
  - `downloading`：串行 for 循环，每项前检查 `cancelled`；目录模式 `getFileHandle(name, {create:true}).createWritable()` 写入；降级模式 `URL.createObjectURL` + `<a download>` click（复刻 `InvoiceDetailDrawer.handleDownload` 模式）；失败入 `failed` 列表；`AbortError`（用户取消选目录）回 ready；
  - `done`：汇总行 + 失败列表 +「关闭」。
- 命名：`sanitizeFilename` 剔除 `\ / : * ? " < > |`、控制字符、首尾空白与点，空则 `unknown`；`buildFileName`：`{客户名|#customer_id}-{invoice_no}.xlsx`。
- 工具函数放组件内（仅此一处使用，不抽公共 utils）。
- 错误处理遵循 axios 拦截器既有模式（`handleError` / `Message`），blob 错误响应解析按拦截器实际行为处理。

### Invoices.vue 接入

- 工具栏「批量删除」后插按钮 `v-if="can('billing:view')"`；
- import 组件、`batchDownloadVisible` ref、`onBatchDownloadDetail`；
- 模板末尾挂载 `<BatchDownloadDetailModal v-model:visible :ids="selectedInvoiceIds" />`；
- `selectedInvoiceIds` 已由 `useInvoice()` 解构，直接透传；下载完成不刷新列表。

## 权衡

- **元数据独立端点 vs 扩展轮询接口**：轮询接口被高频调用且结构被 composable 依赖，扩展有回归风险；独立端点零影响，代价是一次额外请求（批量操作低频，可接受）。
- **串行 vs 并发**：串行避免多文件下载被浏览器拦截与目录写入竞态，代价是大批量慢；方案已记录 contingency（3 路 Promise 池，目录写入仍串行），当前不做。
- **目录写入 vs 后端打包 ZIP**：目录写入零服务端成本、即时反馈；ZIP 需服务端聚合与临时文件管理。内部系统 Chrome/Edge 为主，选前者；Safari 限制已用降级路径兜底。
