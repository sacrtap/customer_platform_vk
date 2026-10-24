# 减免审批节点方案

## Context

当前结算单状态机：`draft → pending_ops → pending_sales → pending_customer → customer_confirmed → completed`（任意非 completed 可 → cancelled）。已有"减免申请"功能（`apply_discount` 直接修改 `discount_amount` 并生效，无审批环节），允许在 draft/pending_ops/pending_sales/pending_customer 状态修改。

需求：在"客户确认前"增加一个"减免审批"节点。只有申请了减免（`discount_amount ≠ 0`）的结算单才进入该节点；由具备减免审批权限的用户审批；审批通过才能继续到客户确认并完成结算；审批驳回退回销售确认阶段重新走经理确认；驳回必填理由、通过可选。

预期最终状态机（有减免的单）：
`draft → pending_ops → pending_sales → pending_discount_approval → pending_customer → customer_confirmed → completed`
无减免的单：销售/运营确认后直接 → pending_customer（不进审批节点）。

产品决策（已与需求方确认，作为本方案前提）：
- 仅 `discount_amount ≠ 0` 的结算单进入审批节点；无减免的不进。
- 驳回退回"销售确认"（pending_sales）；对于多路径（无销售经理跳过 sales、不对账直提）按客户配置对称推断退回点（见 Approach 步骤 5）。
- 驳回必填审批理由，通过可选。

## Approach

### 步骤 1 — 后端模型：新增状态与字段

文件 `backend/app/models/billing.py`：

1. `InvoiceStatus` 枚举（:27-42）新增成员：
   ```python
   PENDING_DISCOUNT_APPROVAL = "pending_discount_approval"  # 待减免审批（有减免申请时进入）
   ```
   并更新类 docstring 的流转说明，在 `pending_sales → pending_customer` 之间标注"有减免则先经 pending_discount_approval"。

2. `Invoice` 模型（:121-199）新增三字段（插入在 `discount_applied_at` 附近，:144 之后）：
   ```python
   discount_approver_id: Mapped[int | None] = mapped_column(
       Integer, ForeignKey("users.id"), nullable=True
   )  # 减免审批人
   discount_approved_at: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 减免审批时间
   discount_approval_comment: Mapped[str | None] = mapped_column(Text, nullable=True)  # 审批意见/驳回理由
   ```
   注意：`approver_id`/`approved_at`（:142-143）已被"提交结算单"语义占用（submit_invoice/batch_submit 写入，前端时间线显示"提交结算"），**不可复用**，必须用新字段。

### 步骤 2 — 数据库迁移

在 `backend/alembic/versions/` 新增一个迁移文件（参照现有迁移命名风格，如 `add_discount_approval_fields.py`，revision id 自取唯一值，down_revision 指向当前 head）：
- `invoices` 表 `add_column` 三列：`discount_approver_id`(Integer, FK users.id, nullable)、`discount_approved_at`(String(50), nullable)、`discount_approval_comment`(Text, nullable)。
- downgrade `drop_column` 三列。
- status 列为 String(20) 无 DB 级枚举约束，新增状态值无需 DDL 变更。

### 步骤 3 — 权限定义

文件 `backend/scripts/seed.py`，`ALL_PERMISSIONS`（:44-139）的"结算管理"段（:57-74 之后）新增一行：
```python
("billing:discount_approve", "减免审批", "审批结算单减免申请", "billing"),
```
超级管理员角色由 seed 逻辑自动获得全部权限（:247-250），无需额外绑定。**不**绑定到"运营经理""销售经理"预置角色（减免审批是独立审批职能，避免与确认角色冲突）；是否新建预置"减免审批员"角色留作可选运维动作，不在代码内强制。`get_or_create_permission` 幂等，存量库重跑 seed 即补入。

### 步骤 4 — 后端服务：状态分流 + 审批/驳回方法

文件 `backend/app/services/billing.py`（`InvoiceService`）：

1. 新增内部分流方法（复用于所有"即将进入 pending_customer"的路径）：
   ```python
   def _route_to_approval_or_customer(self, invoice: Invoice) -> None:
       """即将进入客户确认阶段：有减免申请则先进审批节点，否则直接待客户确认。"""
       target = (
           "pending_discount_approval"
           if invoice.discount_amount and invoice.discount_amount != 0  # pyright: ignore[reportGeneralTypeIssues]
           else "pending_customer"
       )
       invoice.status = target  # pyright: ignore[reportAttributeAccessIssue]
   ```

2. 改造 4 处"设为 pending_customer"为调用上述分流：
   - `submit_invoice`（:1639-1682）：三处 `invoice.status = "pending_customer"`（:1672 防御、:1675 不对账）以及该方法的 pending_ops/pending_sales 分支保持不变——**仅替换直接落 pending_customer 的赋值为 `self._route_to_approval_or_customer(invoice)`**。注意 submit_invoice 末尾仍设置 `approver_id`/`approved_at`（提交人，不变）。
   - `confirm_ops`（:1684-1716）：无销售经理分支 `invoice.status = "pending_customer"`（:1710）→ `self._route_to_approval_or_customer(invoice)`。
   - `confirm_sales`（:1718-1745）：`invoice.status = "pending_customer"`（:1739）→ `self._route_to_approval_or_customer(invoice)`。
   - `batch_submit`（:1869-1930）：else 分支 `invoice.status = "pending_customer"`（:1920）→ `self._route_to_approval_or_customer(invoice)`。（batch_submit 不处理 require_reconciliation，其 pending_ops/pending_sales 分支不变。）

3. 收紧 `apply_discount`（:1557-1605）允许状态：将 `["draft","pending_ops","pending_sales","pending_customer"]`（:1576）改为 `["draft","pending_ops","pending_sales"]`。理由：审批通过后（pending_customer）若仍可改减免会绕过审批；审批节点本身（pending_discount_approval）不允许改申请。路由 `apply_discount` 的 docstring（invoices.py:819）同步更新允许状态说明。

4. 新增审批通过方法：
   ```python
   async def approve_discount(
       self, invoice_id: int, user_id: int, comment: Optional[str] = None
   ) -> Tuple[bool, str]:
       """减免审批通过：pending_discount_approval → pending_customer。"""
       invoice = await self.get_invoice_by_id(invoice_id)
       if not invoice:
           return False, "结算单不存在"
       if invoice.status != "pending_discount_approval":  # pyright: ignore[reportGeneralTypeIssues]
           return False, f"当前状态不能审批：{invoice.status}"
       invoice.status = "pending_customer"  # pyright: ignore[reportAttributeAccessIssue]
       invoice.discount_approver_id = user_id  # pyright: ignore[reportAttributeAccessIssue]
       invoice.discount_approved_at = datetime.now().isoformat()  # pyright: ignore[reportAttributeAccessIssue]
       if comment is not None:
           invoice.discount_approval_comment = comment  # pyright: ignore[reportAttributeAccessIssue]
       await self.db.commit()
       return True, "减免审批通过"
   ```

5. 新增审批驳回方法（含退回点推断，与 submit_invoice 正向分流对称）：
   ```python
   def _discount_reject_revert_status(self, customer: Optional[Customer]) -> str:
       """驳回退回点：与 submit_invoice 正向分流对称。
       对账+有销售经理→pending_sales；对账仅有运营经理→pending_ops；其余（不对账/防御）→draft。
       """
       if customer is not None and customer.require_reconciliation is True:  # pyright: ignore[reportGeneralTypeIssues]
           if customer.sales_manager_id:  # pyright: ignore[reportGeneralTypeIssues]
               return "pending_sales"
           if customer.manager_id:  # pyright: ignore[reportGeneralTypeIssues]
               return "pending_ops"
       return "draft"

   async def reject_discount(
       self, invoice_id: int, user_id: int, comment: str
   ) -> Tuple[bool, str]:
       """减免审批驳回：pending_discount_approval → 退回点（默认 pending_sales）。"""
       if not comment or not comment.strip():
           return False, "驳回必须填写理由"
       invoice = await self.get_invoice_by_id(invoice_id)
       if not invoice:
           return False, "结算单不存在"
       if invoice.status != "pending_discount_approval":  # pyright: ignore[reportGeneralTypeIssues]
           return False, f"当前状态不能驳回：{invoice.status}"
       customer = await self._get_customer(invoice.customer_id)  # pyright: ignore[reportArgumentType]
       revert = self._discount_reject_revert_status(customer)
       invoice.status = revert  # pyright: ignore[reportAttributeAccessIssue]
       invoice.discount_approver_id = user_id  # pyright: ignore[reportAttributeAccessIssue]
       invoice.discount_approved_at = datetime.now().isoformat()  # pyright: ignore[reportAttributeAccessIssue]
       invoice.discount_approval_comment = comment.strip()  # pyright: ignore[reportAttributeAccessIssue]
       await self.db.commit()
       return True, f"减免已驳回，退回至{ {'pending_sales':'销售确认','pending_ops':'运营确认','draft':'草稿'}[revert] }"
   ```

### 步骤 5 — 后端路由：审批/驳回端点 + 序列化字段

文件 `backend/app/routes/billing/invoices.py`：

1. 新增两个端点（紧邻 confirm-sales 路由 :1206 之后，套用 confirm_ops 路由 :1154-1203 的模板：`@auth_required` + `@require_permission("billing:discount_approve")` + `get_invoice_by_id` 存在性校验 + `create_audit_entry` + `cache_service.invalidate_billing_cache()`）：
   ```python
   @billing_bp.post("/invoices/<invoice_id:int>/approve-discount")
   @auth_required
   @require_permission("billing:discount_approve")
   async def approve_discount_route(request: Request, invoice_id: int):
       """减免审批通过"""
       # comment 可选；body: {"comment": "..."}
       # 调用 invoice_service.approve_discount(invoice_id, user_id, comment)
       # 审计 action="approve_discount"，changes before/after status
       ...

   @billing_bp.post("/invoices/<invoice_id:int>/reject-discount")
   @auth_required
   @require_permission("billing:discount_approve")
   async def reject_discount_route(request: Request, invoice_id: int):
       """减免审批驳回（驳回理由必填）"""
       # body: {"comment": "..."}；comment 缺失/空 → 400
       # 调用 invoice_service.reject_discount(invoice_id, user_id, comment)
       # 审计 action="reject_discount"，changes before/after status
       ...
   ```
   **不加** `_ensure_invoice_scope`：减免审批是独立跨客户审批职能，准入由 `billing:discount_approve` 权限控制；可见性在列表层处理（见 Assumptions）。

2. 详情/列表序列化补字段：列表序列化（:232 附近，`invoice.approver_id` 同段）追加 `discount_approver_id`、`discount_approver_name`(用 `resolve_name`)、`discount_approved_at`、`discount_approval_comment`；详情序列化（:346-348 `approver_id`/`approver_name`/`approved_at` 同段）同样追加。参照现有 `resolve_name(invoice.xxx)` 模式。

### 步骤 6 — 前端状态常量

文件 `frontend/src/constants/invoiceStatus.ts`：
- `INVOICE_STATUS_MAP`（:6-14）加 `pending_discount_approval: '待减免审批'`。
- `INVOICE_STATUS_CLASS_MAP`（:16-24）加 `pending_discount_approval: 'purple'`（与现有 gray/amber/orange/blue/green/red 区分；`InvoiceStatusBadge` 自动读取，无需改组件）。

### 步骤 7 — 前端 API 与类型

文件 `frontend/src/api/billing.ts`：
- `Invoice` 接口（:309-367）`status` 联合类型（:325-333）加 `| 'pending_discount_approval'`。
- 接口加字段：`discount_approver_id?: number | null`、`discount_approver_name?: string | null`、`discount_approved_at?: string | null`、`discount_approval_comment?: string | null`。
- 新增函数（参照 confirmOps :482 风格）：
   ```typescript
   export function approveDiscount(invoiceId: number, comment?: string) {
     return api.post(`/billing/invoices/${invoiceId}/approve-discount`, comment ? { comment } : {})
   }
   export function rejectDiscount(invoiceId: number, comment: string) {
     return api.post(`/billing/invoices/${invoiceId}/reject-discount`, { comment })
   }
   ```
文件 `frontend/src/types/index.ts`（:217-222 `Invoice` 镜像类型）同步加上述四字段与 status 联合类型成员。

### 步骤 8 — 前端 composable

文件 `frontend/src/composables/useInvoice.ts`（参照 doConfirmOps :328-337 风格）新增：
```typescript
const doApproveDiscount = async (invoiceId: number, comment?: string) => {
  try {
    await approveDiscount(invoiceId, comment)
    Message.success('审批通过')
    loadInvoices()
  } catch (err) {
    Message.error(errorMessage(err, '审批失败'))
    throw err
  }
}
const doRejectDiscount = async (invoiceId: number, comment: string) => {
  try {
    await rejectDiscount(invoiceId, comment)
    Message.success('已驳回')
    loadInvoices()
  } catch (err) {
    Message.error(errorMessage(err, '驳回失败'))
    throw err
  }
}
```
并在 return 对象（:447-484）导出 `doApproveDiscount`、`doRejectDiscount`；import 处（:1-35 附近）补 `approveDiscount, rejectDiscount`。

### 步骤 9 — 前端列表页操作

文件 `frontend/src/views/billing/Invoices.vue`：
- 操作列（:191-269）在"客户确认"按钮（:232-239）之前加审批按钮：
  ```html
  <button
    v-if="can('billing:discount_approve') && record.status === 'pending_discount_approval'"
    class="btn btn-primary-sm"
    style="padding: 4px 10px; font-size: 12px; margin-left: 4px"
    @click="handleSingleAction(record, 'approve-discount')"
  >
    审批通过
  </button>
  ```
  驳回用弹窗收集理由（见步骤 10 的统一弹窗，或在 handleSingleAction 内用 Modal.confirm + 输入）。**采用统一审批弹窗**（步骤 10）以承载"通过可选理由 / 驳回必填理由"。
- `handleSingleAction`（:616-693）的 `action` 联合类型加 `'approve-discount' | 'reject-discount'`，`actions` 字典加两项调用 `doApproveDiscount`/`doRejectDiscount` 并 `refreshDetailIfOpen()`。
- 取消按钮允许状态列表（:250-253）加 `'pending_discount_approval'`。

### 步骤 10 — 审批弹窗组件（新建）

新建 `frontend/src/views/billing/components/DiscountApprovalModal.vue`（参照 `DiscountEditModal.vue` 结构：a-modal + a-form + a-textarea）：
- props: `visible`, `invoiceId`, `mode: 'approve' | 'reject'`。
- 表单字段：`comment`（textarea，max 500）。reject 模式下 comment 必填（rule required），approve 模式可选。
- 提交调用 `approveDiscount(invoiceId, comment)` 或 `rejectDiscount(invoiceId, comment)`；成功 emit `success`。
- 在 `Invoices.vue` 注册该组件（参照 DiscountEditModal 注册 :317-324），由 `handleSingleAction` 的 approve-discount/reject-discount 打开（设 `approvalModalVisible`/`approvalMode`/`approvalInvoiceId`）。

### 步骤 11 — 前端详情抽屉

文件 `frontend/src/views/billing/components/InvoiceDetailDrawer.vue`：
- `InvoiceDrawerEmits`（:317-329）加 `(e: 'approve-discount', id: number): void`、`(e: 'reject-discount', id: number): void`。
- 操作区模板加审批按钮（`pending_discount_approval` 状态、`can('billing:discount_approve')`），emit 对应事件。
- `canEditSettlementAccount`（:348-355）允许状态数组加 `'pending_discount_approval'`（审批节点仍可调整代扣账户，不影响审批）。
- `STATUS_TO_STEP`（:423-431）加 `pending_discount_approval: 4`（与 pending_customer 同级，流程图高亮到客户确认阶段前）。
- `Invoices.vue` 模板中 `<InvoiceDetailDrawer>`（:293-307）绑定 `@approve-discount`/`@reject-discount` 到 `handleSingleAction(currentDetail!, 'approve-discount'/'reject-discount')`。

### 步骤 12 — 前端时间线

文件 `frontend/src/components/invoice/InvoiceTimeline.vue`：
- `props.invoice` 类型（:40-64）加 `discount_approver_name?: string | null`、`discount_approved_at?: string`、`discount_approval_comment?: string | null`。
- 事件节点数组（:94 起）在"提交结算"(approved_at, statusKey='pending_ops') 之后、客户确认之前，新增减免审批节点：
  ```js
  { field: 'discount_approved_at', label: '减免审批', statusKey: 'pending_discount_approval',
    operatorField: 'discount_approver_name',
    detailParts: () => props.invoice.discount_approval_comment
      ? [{ type: 'text', text: `审批意见：${props.invoice.discount_approval_comment}` }] : undefined }
  ```
  仅当 `discount_approved_at` 存在时显示（参照现有节点显隐逻辑，:218 附近的 `if (timeValue)` 判定）。

### 步骤 13 — 测试

后端 `backend/tests/unit/test_billing_service.py`（参照现有 submit/confirm 测试 :2285-2457 风格）：
- 新增 `test_approve_discount_success`：构造 pending_discount_approval + 有减免的单 → approve → 断言 status==pending_customer、discount_approver_id/approved_at 已设。
- 新增 `test_approve_discount_wrong_status`：非审批状态调用 → 断言失败。
- 新增 `test_reject_discount_requires_comment`：空 comment → 失败。
- 新增 `test_reject_discount_reverts_to_pending_sales`：对账+有销售经理 → 驳回 → pending_sales。
- 新增 `test_reject_discount_reverts_to_pending_ops`：对账无销售经理 → 驳回 → pending_ops；`..._to_draft`：不对账 → draft。
- 更新现有 submit/confirm 测试：有减免的单经确认后应落 pending_discount_approval（新增对应断言用例，保留无减免落 pending_customer 的旧用例）。
- 更新 apply_discount 测试：pending_customer 状态修改应失败（原允许的用例需改为 pending_sales 或标注新行为）。

前端 `frontend/src/composables/__tests__/useInvoice.test.ts`（参照现有 doConfirmOps 测试风格）：
- 新增 `doApproveDiscount` / `doRejectDiscount` 调用并断言 API 被调、Message 成功。

## Critical files & anchors

- `backend/app/models/billing.py` — `InvoiceStatus`(:27-42) 加状态成员；`Invoice`(:121-199,:142-144) 加三审批字段（注意 approver_id/approved_at 已被占用）。
- `backend/app/services/billing.py` — `submit_invoice`(:1639-1682)、`confirm_ops`(:1684-1716)、`confirm_sales`(:1718-1745)、`batch_submit`(:1869-1930) 四处 pending_customer 赋值改分流；`apply_discount`(:1557-1605,:1576) 收紧允许状态；新增 approve/reject 方法。
- `backend/app/routes/billing/invoices.py` — confirm_sales 路由(:1206) 后新增 approve-discount/reject-discount；序列化(:232,:346-348) 补字段；apply_discount 路由(:805-819) 更新注释。
- `backend/scripts/seed.py` — `ALL_PERMISSIONS`(:57-74) 加 billing:discount_approve。
- `frontend/src/views/billing/Invoices.vue` — 操作列(:191-269)、`handleSingleAction`(:616-693)、取消按钮状态(:250-253)、InvoiceDetailDrawer 绑定(:293-307)。
- `frontend/src/views/billing/components/InvoiceDetailDrawer.vue` — emits(:317-329)、`canEditSettlementAccount`(:348-355)、`STATUS_TO_STEP`(:423-431)。

## Verification

前置：`backend` venv（`$BACKEND_DIR/.venv/bin/python`）、PostgreSQL、Redis 可用；`frontend` 依赖已装。

1. 迁移与种子：
   - `cd backend && .venv/bin/alembic upgrade head`（三列写入成功）。
   - `python scripts/seed.py`（重跑幂等，billing:discount_approve 权限入库；超级管理员自动获得）。

2. 后端单测：
   - `cd backend && .venv/bin/python -m pytest tests/unit/test_billing_service.py -k "discount or submit or confirm" -v`（新增 approve/reject 用例 + 更新后的 submit/confirm 用例全绿）。
   - 全量：`.venv/bin/python -m pytest --cov-fail-under=50`（覆盖率门槛保持）。

3. 前端：
   - `cd frontend && npm run type-check`（0 errors）。
   - `npm run test -- useInvoice`（新 composable 用例绿）。

4. 端到端冒烟（核心新行为，需手动 UI 或脚本）：
   - 用超管登录 → 生成一张有减免（discount_amount=100）的结算单 → 提交 → 运营确认 → 销售确认 → 断言状态为 `pending_discount_approval`（非 pending_customer）。
   - 审批通过（billing:discount_approve 用户）→ 断言状态回到 `pending_customer` → 客户确认 → 自动扣款成功 → `completed`。
   - 另造一张有减免单走到审批节点 → 驳回（填理由）→ 断言状态退回 `pending_sales`，可重新销售确认→审批。
   - 造一张无减免单 → 销售确认后直接 `pending_customer`（不进审批节点）。
   - 审批通过后尝试 apply_discount 改减免 → 断言 400（pending_customer 不再允许改减免）。
   可用 `curl` 调对应路由验证状态返回，或前端结算单列表观察状态徽章显示"待减免审批"。

## Assumptions & contingencies

- **审批路由不加数据可见性 scope**：减免审批员准入仅由 `billing:discount_approve` 控制。列表层仍按现有 `customer_scope_user_id` 限制可见性——若审批员需查看全部客户待审批单，应在角色配置中同时授予 `customers:view_all`（运维配置，非代码）。不新增"待审批"专属视图（YAGNI）。
- **驳回退回点按客户当前配置推断**（不记录进入审批时的来源状态）：与 `submit_invoice` 正向分流对称。边缘情况——审批期间客户经理/对账配置被改——退回点按当前配置推断，可能与进入时不一致，但重新走流程可恢复，不致死锁。
- **预置角色**：不在 seed 中新建"减免审批员"预置角色，仅新增权限码；由管理员按需创建自定义角色并分配 `billing:discount_approve`（+建议 `customers:view_all`）。
- 若实现中发现 `InvoiceTimeline` 节点显隐逻辑（:218 附近 `if (timeValue)`）与新增审批节点不兼容，按现有 `approved_at` 节点的显隐模式对齐即可，无需设计变更。
- 若 CI 覆盖率因新增未覆盖分支下降，补 reject 的 draft/pending_ops 退回分支用例即可达标。
