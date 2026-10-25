# 结算单批量下载明细文件

## Context

结算单页面（`frontend/src/views/billing/Invoices.vue`）批量操作工具栏已有「批量提交 / 批量取消 / 批量删除」，缺「批量下载明细文件」。用户在列表勾选多张结算单后，需把这些结算单已生成完成的明细 Excel 批量下载到本地，过程中用进度提示框实时反馈。

需求确认结果（用户已选）：
- **下载形态**：前端逐个调用现有单条下载端点 `GET /billing/invoices/<id>/download-detail`（blob 响应）；用 File System Access API `showDirectoryPicker()` 让用户选择保存目录并逐个写入，Safari/Firefox 不支持时自动降级为浏览器逐个下载（不选目录，仍保留进度框）。
- **未完成文件**：下载前统计并提示「X 个明细文件未生成完成，将跳过」，只下载 `detail_file_status === 'completed'` 的，不阻塞主流程。
- **文件命名**：`{客户名}-{结算单号}.xlsx`，与单条下载 `InvoiceDetailDrawer.handleDownload` 一致；客户名缺失回退 `#{customer_id}-{invoice_no}.xlsx`。

终端状态：勾选结算单 → 点「批量下载明细」→ 进度框显示统计与跳过提示 → 用户确认 → 选目录（Chrome/Edge）或直接逐个下载（Safari/Firefox）→ 进度框实时显示 `第 i/N 个 · 成功 X · 失败 Y · 跳过 Z` + 当前文件名 + 进度条 + 取消按钮 → 完成后汇总（成功/失败/跳过 + 失败列表）。

## Approach

### 后端：新增批量下载元数据接口

为什么不复用现有 `GET /billing/invoices/file-status`（`get_invoice_file_status`，invoices.py:2568）：它是 GET 轻量轮询接口，只返回 `{id, detail_file_status, detail_file_path}`，不含文件命名所需的 `invoice_no` / `customer_name`；扩展它会污染轮询语义并改变返回结构、影响 `useInvoice.pollFileStatus`。故新增独立元数据接口。

**1. 在 `backend/app/routes/billing/invoices.py` 末尾（`get_invoice_file_status` 之后）新增：**

```python
@billing_bp.post("/invoices/batch-download-detail")
@auth_required
@require_permission("billing:view")
async def batch_download_detail_meta(request: Request):
    """批量下载明细文件元数据：返回选中结算单的命名与状态信息，供前端预检与命名。

    实际文件下载复用 GET /invoices/<id>/download-detail（逐个 blob 请求），
    本接口只提供「哪些可下载、哪些未完成、文件叫什么」。
    """
    from sqlalchemy import select as sa_select

    from ...models.billing import Invoice
    from ...models.customers import Customer

    db: AsyncSession = request.ctx.db
    data = request.json or {}
    invoice_ids = [int(i) for i in data.get("ids", [])]
    if not invoice_ids:
        return json({"code": 40004, "message": "请选择要下载的结算单"}, status=400)

    # 数据可见性（服务端强制）：无 customers:view_all 时仅可下载自己负责客户的结算单
    scope_user_id = await customer_scope_user_id(request)
    stmt = (
        sa_select(
            Invoice.id,
            Invoice.invoice_no,
            Invoice.customer_id,
            Customer.name.label("customer_name"),
            Invoice.detail_file_status,
        )
        .outerjoin(Customer, Customer.id == Invoice.customer_id)
        .where(Invoice.id.in_(invoice_ids), Invoice.deleted_at.is_(None))
    )
    if scope_user_id is not None:
        stmt = stmt.where(
            or_(
                Customer.manager_id == scope_user_id,
                Customer.sales_manager_id == scope_user_id,
            )
        )
    result = await db.execute(stmt)
    rows = result.all()

    return json(
        {
            "code": 0,
            "message": "success",
            "data": {
                "list": [
                    {
                        "id": row.id,
                        "invoice_no": row.invoice_no,
                        "customer_id": row.customer_id,
                        "customer_name": row.customer_name,
                        "detail_file_status": row.detail_file_status or "pending",
                    }
                    for row in rows
                ]
            },
        }
    )
```

权限用 `billing:view`（与单条 `download_invoice_detail` 一致），不新增权限点。`sa_select`/`Invoice`/`Customer` 均为函数内局部导入，照搬同文件 `get_invoice_file_status`（invoices.py:2573-2575）既有模式（该文件不在顶部导入这些符号）；`or_` 在文件顶部已导入（invoices.py:18）；`customer_scope_user_id`/`auth_required`/`require_permission` 顶部已导入（:24-29）。新接口无 `customers:view_all` 时用 `outerjoin(Customer)` 取 `Customer.name` 做命名，再用 `manager_id`/`sales_manager_id` 过滤，可见性逻辑与 `get_invoice_file_status` 的 scope 分支（:2600-2608）一致；无 scope 时 outerjoin 仅用于取客户名，不过滤。

### 前端：API 函数

**2. 在 `frontend/src/api/billing.ts` 末尾（`regenerateDetailBatch` 之后）新增：**

```typescript
/** 批量下载明细文件元数据：返回选中结算单的命名与状态，供前端预检跳过 + 文件命名 */
export function getBatchDownloadDetailMeta(ids: number[]) {
  return api.post('/billing/invoices/batch-download-detail', { ids })
}
```

`downloadInvoiceDetail`（billing.ts:544）保持不变，循环内复用。

### 前端：新建 BatchDownloadDetailModal.vue

**3. 新建 `frontend/src/views/billing/components/BatchDownloadDetailModal.vue`**，自包含下载逻辑（不在 `useInvoice` composable 引入 File System Access API，避免 composable 承载浏览器原生 API 与 DOM 交互）。

契约：
- `props`: `{ visible: boolean; ids: number[] }`
- `emit`: `update:visible: [val: boolean]`
- Arco `a-modal`，`width="520px"`，`mask-closable="false"`，`:footer="false"`（自定义底部按钮）

状态机（`phase` ref：`'loading' | 'ready' | 'downloading' | 'done'`）：

1. `watch(visible)`：变 true 时调 `getBatchDownloadDetailMeta(props.ids)` → 解析 list → 计算 `completed = list.filter(d => d.detail_file_status === 'completed')`、`skipped = list.length - completed.length`（未完成含 pending/generating/failed/无状态）→ `phase = 'ready'`。请求失败 → `Message.error('获取下载信息失败')` + 关闭。
2. `ready` 阶段 UI：显示「共 {ids.length} 项 · 可下载 {completed.length} 项」；若 `skipped > 0` 显示「其中 {skipped} 个明细文件未生成完成，将跳过」（橙色提示，不阻塞）。按钮：「开始下载」「取消」。
3. 点「开始下载」：
   - 检测 `const supportsDirPicker = typeof (window as any).showDirectoryPicker === 'function'`
   - 若支持：`try { dirHandle = await (window as any).showDirectoryPicker() } catch (e) { if (e.name === 'AbortError') return（用户取消选目录，回 ready 阶段）; }`
   - 若不支持：`dirHandle = null`，后续走浏览器逐个下载降级路径
   - `phase = 'downloading'`，`success = 0`，`failed = []`，`cancelled = false`
4. `downloading` 阶段：**串行**循环 `completed` 数组（串行避免浏览器多文件下载拦截与目录写入竞态；每项完成后更新进度并检查 `cancelled`）：
   ```typescript
   for (let i = 0; i < completed.length; i++) {
     if (cancelled.value) break
     current.index = i + 1
     current.fileName = buildFileName(item)  // 见下
     try {
       const res = await downloadInvoiceDetail(item.id)  // blob
       const blob = new Blob([res.data])
       if (dirHandle) {
         const fh = await dirHandle.getFileHandle(current.fileName, { create: true })
         const writable = await fh.createWritable()
         await writable.write(blob)
         await writable.close()
       } else {
         // 降级：浏览器逐个下载
         const url = window.URL.createObjectURL(blob)
         const link = document.createElement('a')
         link.href = url
         link.download = current.fileName
         link.click()
         window.URL.revokeObjectURL(url)
       }
       success.value++
     } catch (e) {
       failed.value.push({ id: item.id, invoice_no: item.invoice_no, reason: e?.response?.data?.message || '下载失败' })
     }
   }
   phase = 'done'
   ```
   （注：blob 响应错误时 axios 不解析 JSON body，`e.response.data` 可能是 Blob —— 实现时需 `await blob.text()` 解析后端 JSON 错误，或直接用通用 reason「下载失败」。实现者按 axios 拦截器既有错误处理模式判定，不强制。）
5. `done` 阶段 UI：「下载完成 · 成功 {success} · 失败 {failed.length} · 跳过 {skipped}」；失败列表（`invoice_no + reason`）；按钮：「关闭」。可选「重试失败项」（暂不做，列失败即可，避免范围膨胀）。

`buildFileName(item)`：
```typescript
function sanitizeFilename(s: string): string {
  // 剔除 Windows 非法字符 \ / : * ? " < > | 与控制字符，trim 空白与首尾点
  return (s || '').replace(/[\\/:*?"<>|\x00-\x1f]/g, '').replace(/^[\s.]+|[\s.]+$/g, '') || 'unknown'
}
function buildFileName(item): string {
  const namePart = item.customer_name
    ? sanitizeFilename(item.customer_name)
    : `#${item.customer_id}`
  return `${namePart}-${item.invoice_no}.xlsx`
}
```
前端无现成文件名清洗工具（已搜 `frontend/src`，无 sanitize 相关），组件内实现即可，不抽公共工具（仅此一处用）。

### 前端：Invoices.vue 接入

**4. 在 `frontend/src/views/billing/Invoices.vue` 接入：**

- 批量工具栏 `.batch-actions`（模板第 31-42 行）内，在「批量删除」之后、「取消选择」之前插入：
  ```html
  <button v-if="can('billing:view')" class="btn btn-sm" @click="onBatchDownloadDetail">
    批量下载明细
  </button>
  ```
- `<script setup>` import 区（第 380-388 行附近）加：
  ```typescript
  import BatchDownloadDetailModal from './components/BatchDownloadDetailModal.vue'
  ```
- 与其他弹窗 visible ref 并列（第 450-457 行附近）加：
  ```typescript
  const batchDownloadVisible = ref(false)
  ```
- 在 `onBatchDelete` 之后（第 557 行附近）加：
  ```typescript
  const onBatchDownloadDetail = () => {
    batchDownloadVisible.value = true
  }
  ```
- 模板末尾组件挂载区（第 359-360 行 `DetailGenStatusDrawer` 之后）加：
  ```html
  <BatchDownloadDetailModal
    v-model:visible="batchDownloadVisible"
    :ids="selectedInvoiceIds"
  />
  ```

`selectedInvoiceIds` 已由 `useInvoice()` 解构（Invoices.vue:440），组件直接接收，无需在 composable 增加方法。下载完成后不刷新列表（明细文件状态未变），故不调 `loadInvoices`。

## Critical files & anchors

- `backend/app/routes/billing/invoices.py:2174` — `download_invoice_detail` 单条下载端点，可见性校验（`customer_scope_user_id`）与文件路径逻辑（`settings.file_storage_path` + `detail_file_path`）是新接口复用范式；新接口插在文件末尾 `get_invoice_file_status`（:2568）之后。本文件不在顶部导入 `Invoice`/`sa_select`/`Customer`，新接口须照搬 `get_invoice_file_status`（:2573-2575）的函数内局部导入模式（见 Approach 代码块）。
- `frontend/src/api/billing.ts:544` — `downloadInvoiceDetail`（循环复用）；`:573` `regenerateDetailBatch`（新增 `getBatchDownloadDetailMeta` 的位置锚点）。
- `frontend/src/views/billing/Invoices.vue:28-43` — 批量工具栏 `.batch-actions`（按钮插入点）；`:360` 组件挂载区；`:440-448` `useInvoice` 解构（`selectedInvoiceIds` 来源）。
- `frontend/src/views/billing/components/InvoiceDetailDrawer.vue:467` — `handleDownload` 单条下载 blob→`<a>` click 模式，新组件降级路径直接复刻此逻辑。
- `frontend/src/views/billing/components/DetailGenStatusDrawer.vue:105-279` — 抽屉状态机、轮询、Arco 组件用法参考（非直接复用，仅模式参照）。

## Verification

前置：后端 `make dev`（`backend/`）、前端 `pnpm dev`（`frontend/`）已起；至少存在 2 张 `detail_file_status='completed'` 的结算单 + 1 张未完成的（可在 DB 手动置 `detail_file_status`）。

**后端接口单测**（遵循 `backend/tests/` 既有惯例，集成或单元层）：
- `POST /billing/invoices/batch-download-detail` 传 `{ids: [已完成id, 未完成id, 不存在id, 他人客户id]}`：
  - 返回 list 含可见范围内存在的 id，字段含 `id/invoice_no/customer_id/customer_name/detail_file_status`
  - 无 `customers:view_all` 的经理只能看到自己负责客户的 id（可见性过滤）
  - 空 ids 返回 400

**前端组件单测**（`frontend/src/views/billing/components/__tests__/`，Vitest + jsdom，mock `downloadInvoiceDetail` 与 `getBatchDownloadDetailMeta`）：
- `sanitizeFilename('景/发:*?')` → 剔除非法字符
- `buildFileName({customer_name:'景发', invoice_no:'INV001'})` → `景发-INV001.xlsx`；`customer_name` 为 null → `#5-INV001.xlsx`
- meta 含 2 completed + 1 pending → ready 阶段显示「可下载 2」「跳过 1」
- mock `window.showDirectoryPicker` 存在 → 走目录写入分支，验证 `getFileHandle({create:true}).createWritable().write().close()` 调用链
- mock `showDirectoryPicker` 不存在 → 走 `<a>` click 降级分支
- 取消按钮在 downloading 阶段中断循环（`cancelled=true` 后不再调 `downloadInvoiceDetail`）

**端到端手动验证**（Chrome）：
1. 进入结算单列表，勾选 3 张（2 已完成 + 1 未完成）→ 批量工具栏点「批量下载明细」
2. 进度框显示「可下载 2」「1 个未完成将跳过」→ 点「开始下载」→ 浏览器目录选择对话框弹出 → 选目录
3. 进度框实时滚动「第 1/2 个 · 景发-INV001.xlsx · 成功 1」→「第 2/2 个 · 成功 2」
4. 打开所选目录，确认 2 个 `.xlsx` 文件存在、文件名正确、可正常打开
5. Safari 降级验证：同样操作，无目录选择对话框，浏览器逐个下载 2 个文件到默认下载目录

## Assumptions & contingencies

- **浏览器分布**：内部系统用户主要用 Chrome/Edge，File System Access API 可用；Safari/Firefox 自动降级为浏览器逐个下载（不选目录，仍保留进度框与进度条）。若后续要求 Safari 也支持选目录，无技术方案（浏览器限制），届时改方案为后端打包 ZIP。
- **串行下载**：避免浏览器多文件下载拦截与目录写入竞态；大批量（如 50+）耗时较长但可接受。若实测体验差， contingency：改为 3 路并发（`Promise` 池），但目录写入仍建议串行以简化竞态处理。
- **文件覆盖**：`getFileHandle({create:true})` 对同名文件直接覆盖，与浏览器默认下载行为一致；不额外提示用户覆盖风险（避免弹窗打断批量流程）。
- **明细文件路径稳定**：`detail_file_path` 指向 `settings.file_storage_path` 下相对路径，单条 `download-detail` 端点已处理文件不存在（返回 404），批量循环中该失败归入 `failed` 列表。

## 实现结果（2026-10-25）

分支 `feat/batch-download-detail`（提交 `50c1612`），方案按上文落地，实现与方案的偏差如下：

| 项 | 方案 | 实际实现 | 原因 |
|---|---|---|---|
| 后端 db 会话 | `request.ctx.db` | `request.ctx.db_session` | 与同文件 `get_invoice_file_status` 等既有路由一致（方案笔误） |
| 空 ids 错误码 | 字面 `40004` | 字面 `40004`（`ErrorCodes.MISSING_PARAMETER` 同值） | 同文件批量端点均为字面量，保持局部一致 |
| 选目录异常兜底 | 未定义 | 非 `AbortError` 异常也降级为逐个下载并 `Message.error` 提示 | 避免个别浏览器抛错时流程卡死 |
| 降级下载 DOM 操作 | `<a>` click 后立即 revoke | 先 `appendChild` 再 click，延迟 1s 回收并 remove | 复刻 `ImportModal.downloadTemplate` 的 Firefox/Safari 兼容写法（直接复刻的 `InvoiceDetailDrawer` 旧模式有兼容缺陷） |
| 错误文案提取 | `e?.response?.data?.message` | `pickErrorMessage(error, '下载失败')` 取 `error.message` | axios 拦截器已把响应体统一 reject 为 `{code, message}` 普通对象，`response` 不存在 |
| 进度条 | 未指定 | `percent` = 0-100 整数 | E2E 实测发现初版按 0-1 小数传入显示 `10000%`，已修正并复测 `50% → 100%` |

验证结论：
- 后端：`pytest tests/integration/test_billing_api.py -k batch_download` 2 例通过（字段完整/可见性过滤/空 ids 400/软删排除）；全量 `pytest tests/` 1298 passed，唯一失败 `test_cache.py::test_init_default_ttl_config` 为既有 `system_updates` 缓存断言漂移，与本功能无关。
- 前端：`BatchDownloadDetailModal.test.ts` 8 例通过；`pnpm type-check`、`eslint`、pre-commit 全通过。
- E2E（Chrome headless，2 completed + 1 pending）：弹窗「共 2 项 · 可下载 1 项」+「1 个未生成完成将跳过」→ 降级下载 → 采样到 `第 1/2 个（50%）→ 第 2/2 个（100%）→ 成功 2 · 失败 0 · 跳过 1`；下载文件为有效 xlsx（8.4K、3 sheet），文件名 `{客户名}-{结算单号}.xlsx` 正确。目录写入分支由组件测试 mock `showDirectoryPicker` 覆盖调用链。
- 已知限制：headless Chrome 的 `showDirectoryPicker` 会挂起阻塞，选目录后的真实写入路径未做浏览器实测（单条端点文件读取逻辑既有且未改）。
