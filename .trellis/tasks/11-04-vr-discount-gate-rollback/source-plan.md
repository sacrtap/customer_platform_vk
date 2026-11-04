# VR 结算单减免审批门禁 + 双侧审批流回退 + 减免专用权限与全审批节点发起

## Context

三个需求，均已确认实现方案：

1. **减免审批权限门禁**：VR 编辑费用结算单含减免（`discount_amount ≠ 0`）时，审批（通过）必须由持「减免审批」权限（`billing:discount_approve`）的用户执行；系统内不存在持该权限的用户时，维持原流程（销售主管一并审批，减免生效）。采用**节点门禁**方案：不新增状态、不加迁移，仅在销售主管审批通过时校验。
2. **各审批节点回退至上一步**：结算单管理页与 VR 编辑费用结算页的各内部审批节点支持「回退」到上一步，理由必填，由**当前节点审批人**执行（持该节点审批权限 + 该节点原有身份校验）。`pending_customer`（待客户确认，非内部审核节点）不回退。
3. **减免专用权限点 + 全审批节点发起**：「设置/修改减免」按钮与后端接口的权限从 `billing:edit` / `vr_settlement:edit` 切换为专用权限点 `billing:discount_apply` / `vr_settlement:discount_apply`（角色权限页可单独配置，与「编辑结算单」解耦）；可发起节点放宽到**客户确认前全部审批节点**——普通单新增 `pending_discount_approval`（修改后清空上轮审批人三字段、状态不变等待重新审批），VR 已全覆盖无需改。

### 现状基线（已核实，2026-11-04）

- VR 状态机（`backend/app/services/vr_settlement.py:49-63` docstring）：`draft → pending_cs_supervisor → pending_sales → pending_sales_supervisor → pending_customer → customer_confirmed → completed`。减免**无独立审批节点**——`confirm_sales_supervisor`（:269-306）把销售主管审批与减免审批一并完成（写 `discount_approver_id/discount_approved_at/discount_approval_comment`）。
- 普通单状态机（`backend/app/services/billing.py` `submit_invoice:1730` / `_route_to_approval_or_customer:1652`）：`draft → pending_ops → pending_sales → pending_discount_approval → pending_customer → ...`。减免节点由 `approve_discount`/`reject_discount`（:1674-1728）处理，路由权限 `billing:discount_approve`（`routes/billing/invoices.py:1315,1373`）；`_discount_reject_revert_status` 的退回点即正向分流的「上一步」——**该节点的「驳回」已是回退上一步，保持不变**。
- 回退缺口：普通单 `pending_ops`/`pending_sales` 无任何回退入口；VR `pending_cs_supervisor`/`pending_sales` 无回退入口（VR 销售主管节点的既有「驳回」`reject_sales_supervisor` 即回退上一步，保持不变）。
- 权限模型：`services/permissions.py::get_user_permissions(session, user_id) -> Set[str]`（user_roles → role_permissions → Permission）；`middleware/auth.py::require_permission` 走 `permission_cache → get_user_permissions → _check_permission`。`_check_permission` 的 `billing:manage` 通配符**不覆盖** `discount_approve`，故对 `*_approve` 类权限码直接 `in` 集合判定与装饰器等价。
- 前端模式：`can(p) = userStore.hasPermission(p)`；身份校验 `currentUserId === record.customer_sales_manager_id / customer_manager_id`；审批弹窗范式见 `VrSettlementApprovalModal.vue`（通过选填理由/驳回必填）、`DiscountApprovalModal.vue`。
- 「设置减免」现状：普通单按钮 `can('billing:edit')` + `draft/pending_ops/pending_sales`（`InvoiceDetailDrawer.vue:229-232`），service `apply_discount`（`billing.py:1567-1612`）同白名单且明确拒绝 `pending_discount_approval`；VR 按钮 `can('vr_settlement:edit')` + 客户确认前全部节点（`VrSettlementDetailDrawer.vue:151-163`，`_DISCOUNT_EDITABLE_STATUSES` 已含 `pending_sales_supervisor`）。VR apply_discount 修改时清空 `discount_approver_id/approved_at/comment`（`vr_settlement.py:364-366`）；普通单无此逻辑（原白名单到不了需清空的节点）。
- 权限码漂移门禁：`tests/unit/test_permission_drift.py` 强制后端 `require_permission(...)` 与前端 `can()/hasPermission()` 引用的权限码必须是 `scripts/seed.py::ALL_PERMISSIONS` 子集；`tests/unit/test_test_data_consistency.py` 强制 `tests/_test_data.py::PERMISSION_ROWS` ⊆ seed。新权限码必须同步注册这三处，否则门禁红灯。

## Approach

### A. 减免审批权限门禁（需求 1）

**A1. `backend/app/services/permissions.py` 新增持权用户统计**

文件顶部 import 改为 `from sqlalchemy import func, select`，新增：

```python
async def count_users_with_permission(session: AsyncSession, permission_code: str) -> int:
    """统计持指定权限码且可用的用户数（deleted_at IS NULL 且 is_active IS NOT FALSE）。

    用于「系统内是否存在持某权限的用户」判断（VR 减免审批门禁的兜底条件）。
    count(distinct User.id)：同一用户经多个角色获得同一权限只计一次。
    """
    stmt = (
        select(func.count(User.id.distinct()))
        .select_from(User)
        .join(user_roles, User.id == user_roles.c.user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .join(role_permissions, Role.id == role_permissions.c.role_id)
        .join(Permission, Permission.id == role_permissions.c.permission_id)
        .where(
            Permission.code == permission_code,
            User.deleted_at.is_(None),
            User.is_active.is_not(False),
        )
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())
```

**A2. `backend/app/services/vr_settlement.py` 门禁**

- 模块级常量（置于 `_DISCOUNT_EDITABLE_STATUSES` 附近）：`DISCOUNT_APPROVE_PERMISSION = "billing:discount_approve"`
- import：`from .permissions import count_users_with_permission, get_user_permissions`
- `confirm_sales_supervisor`（:269-306）在状态校验通过后、写 `sales_supervisor_confirmed_*` 之前插入：

```python
# 减免审批门禁：有减免且系统存在持「减免审批」权限的用户时，操作人必须持该权限；
# 无人持权时回退原流程（销售主管一并审批，减免生效）。
if settlement.discount_amount and settlement.discount_amount != 0:  # pyright: ignore[reportGeneralTypeIssues]
    holder_count = await count_users_with_permission(self.db, DISCOUNT_APPROVE_PERMISSION)
    if holder_count > 0:
        operator_permissions = await get_user_permissions(self.db, user_id)
        if DISCOUNT_APPROVE_PERMISSION not in operator_permissions:
            return False, "该结算单包含减免，需由具有减免审批权限的用户审批"
```

路由层无需改动：service 返回 `(False, msg)` 已被 `confirm_sales_supervisor` 路由（`routes/billing/vr_settlements.py:528-580`）映射为 `40001/400`。驳回（`reject_sales_supervisor`）不批准减免，不加门禁。

**A3. VR 详情/列表响应新增 `discount_approval_required`**

- `routes/billing/vr_settlements.py` 顶部加 `from ...services.permissions import count_users_with_permission`（实现时按该文件现有相对 import 层级确认）。
- `get_vr_settlement`（:163-286）响应 `data` 中 `"status"` 之后加：

```python
"discount_approval_required": (
    bool(settlement.discount_amount and settlement.discount_amount != 0)
    and await count_users_with_permission(db, "billing:discount_approve") > 0
),
```

- `get_vr_settlements`（:77-161）列表响应：构建行字典前，若任一行 `discount_amount` 非 0 则执行一次 `holders_exist = await count_users_with_permission(db, "billing:discount_approve") > 0`（否则 `False`，不发查询）；每行 dict 加 `"discount_approval_required": bool(r.discount_amount and r.discount_amount != 0) and holders_exist`。实现前先读该路由的行构建代码，按其现有结构插入。

**A4. 前端门禁**

- `frontend/src/api/vrSettlement.ts`：`VrSettlement` 接口加 `discount_approval_required?: boolean`。
- `VrSettlementDetailDrawer.vue`（销售主管审批区，模板 :190-205）：「审批通过」按钮加禁用态，`a-tooltip` 包裹禁用 span 的写法照抄同文件 `pending_sales` 销售审批禁用态（:170-186）：

```ts
const discountApprovalBlocked = computed(
  () =>
    settlement.value?.discount_approval_required === true &&
    !can('billing:discount_approve')
)
const discountApprovalTip = '该结算单包含减免，需由具有减免审批权限的用户审批'
```

「审批驳回」不受门禁限制。
- `VrSettlements.vue` 列表快捷「审批通过」按钮（:180-190）：加同样的 `:disabled` + `:title`（`v-if` 条件不变）。

### B. 回退至上一步（需求 2）

**B1. `backend/app/middleware/auth.py` 新增动态权限校验助手**（置于 `require_permission` 之后、`_check_permission` 附近）：

```python
async def ensure_permission(request: Request, permission_code: str):
    """状态依赖的权限校验（如按当前节点回退）：通过返回 None，否则返回 403 响应。

    与 require_permission 装饰器同一 lookup 路径（permission_cache → get_user_permissions
    → _check_permission），供权限点随资源当前状态变化的路由复用。
    """
    user = get_current_user(request)
    if not user:
        return json({"code": ErrorCodes.UNAUTHORIZED, "message": "未认证"}, status=401)

    from ..cache.permissions import permission_cache

    user_id = user["user_id"]
    user_permissions = await permission_cache.get_permissions(user_id)
    if user_permissions is None:
        db_session: AsyncSession = request.ctx.db_session
        user_permissions = await get_user_permissions(db_session, user_id)
        await permission_cache.set_permissions(user_id, user_permissions)  # pyright: ignore[reportArgumentType]

    if not _check_permission(user_permissions, permission_code):  # pyright: ignore[reportArgumentType]
        return json({"code": ErrorCodes.FORBIDDEN, "message": "权限不足"}, status=403)
    return None
```

**B2. `backend/app/services/billing.py` 新增 `rollback_invoice`**（置于 `confirm_sales` 方法之后）：

```python
# 回退目标映射：当前节点 → 上一步。pending_discount_approval 的回退由既有
# reject_discount 承担（其退回点即上一步，理由必填）；pending_customer 及以后不回退。
_INVOICE_ROLLBACK_TARGETS = {
    "pending_ops": "draft",
    "pending_sales": "pending_ops",
}

async def rollback_invoice(self, invoice_id: int, user_id: int, comment: str) -> Tuple[bool, str]:
    """回退至上一步审核（理由由路由层校验必填后传入）

    pending_ops → draft：操作人必须为该客户指定的运营经理；
    pending_sales → pending_ops：操作人必须为该客户指定的销售经理。
    仅改 status；ops_confirmed_*/sales_confirmed_* 等历史确认字段保留作审计轨迹。
    """
    invoice = await self.get_invoice_by_id(invoice_id)

    if not invoice:
        return False, "结算单不存在"

    target = _INVOICE_ROLLBACK_TARGETS.get(invoice.status)  # pyright: ignore[reportArgumentType]
    if target is None:
        return False, f"当前状态（{invoice.status}）不支持回退"

    customer = await self._get_customer(invoice.customer_id)  # pyright: ignore[reportArgumentType]
    if not customer:
        return False, "客户不存在"

    if invoice.status == "pending_ops":  # pyright: ignore[reportGeneralTypeIssues]
        if customer.manager_id != user_id:  # pyright: ignore[reportGeneralTypeIssues]
            return False, "您不是该客户指定的运营经理，无权回退"
    else:
        if customer.sales_manager_id != user_id:  # pyright: ignore[reportGeneralTypeIssues]
            return False, "您不是该客户指定的销售经理，无权回退"

    invoice.status = target  # pyright: ignore[reportAttributeAccessIssue]

    await self.db.commit()

    return True, "已回退至上一步"
```

**B3. `backend/app/services/vr_settlement.py` 新增 `rollback_settlement`**（置于 `reject_sales_supervisor` 之后）：

```python
# 回退目标映射：当前节点 → 上一步。pending_sales_supervisor 的回退由既有
# reject_sales_supervisor 承担（退回 pending_sales，理由必填）；pending_customer 及以后不回退。
_VR_ROLLBACK_TARGETS = {
    "pending_cs_supervisor": "draft",
    "pending_sales": "pending_cs_supervisor",
}

async def rollback_settlement(
    self, settlement_id: int, user_id: int, comment: str
) -> Tuple[bool, str]:
    """回退至上一步审核（理由由路由层校验必填后传入）

    pending_cs_supervisor → draft：仅权限校验（与 confirm_cs_supervisor 一致，无身份校验）；
    pending_sales → pending_cs_supervisor：操作人必须为该客户指定的销售（与 confirm_sales 一致）。
    仅改 status；cs_supervisor_confirmed_*/sales_confirmed_* 保留作审计轨迹。
    """
    settlement = await self.get_settlement_by_id(settlement_id)

    if not settlement:
        return False, "结算单不存在"

    target = _VR_ROLLBACK_TARGETS.get(settlement.status)  # pyright: ignore[reportGeneralTypeIssues]
    if target is None:
        return False, f"当前状态（{settlement.status}）不支持回退"

    if settlement.status == "pending_sales":  # pyright: ignore[reportGeneralTypeIssues]
        customer = await self._get_customer(settlement.customer_id)  # pyright: ignore[reportArgumentType]
        if not customer:
            return False, "客户不存在"
        if customer.sales_manager_id != user_id:  # pyright: ignore[reportGeneralTypeIssues]
            return False, "您不是该客户指定的销售，无权回退"

    settlement.status = target  # pyright: ignore[reportAttributeAccessIssue]

    await self.db.commit()

    return True, "已回退至上一步"
```

**B4. 新路由（两侧同构，照抄相邻 confirm/reject 路由的 scope → service → cache → audit 模式）**

`backend/app/routes/billing/invoices.py`（置于 `reject_discount` 路由 :1373 之后）：

```python
@billing_bp.post("/invoices/<invoice_id:int>/rollback")
@auth_required
async def rollback_invoice(request: Request, invoice_id: int):
    """回退至上一步审核（理由必填）

    pending_ops → draft（billing:ops_approve + 客户指定运营经理身份）；
    pending_sales → pending_ops（billing:sales_approve + 客户指定销售经理身份）。

    Body: { "comment": "回退理由（必填）" }
    """
    db: AsyncSession = request.ctx.db_session
    user = get_current_user(request)
    data = request.json or {}
    invoice_service = InvoiceService(InvoiceRepository(db), PricingRepository(db))

    comment = (data.get("comment") or "").strip()
    if not comment:
        return json({"code": 40001, "message": "回退必须填写理由"}, status=400)

    invoice_before = await invoice_service.get_invoice_by_id(invoice_id)
    if not invoice_before:
        return json({"code": ErrorCodes.NOT_FOUND, "message": "结算单不存在"}, status=404)

    denied = await _ensure_invoice_scope(request, invoice_before)
    if denied is not None:
        return denied

    rollback_permission = {
        "pending_ops": "billing:ops_approve",
        "pending_sales": "billing:sales_approve",
    }.get(invoice_before.status)  # pyright: ignore[reportArgumentType]
    if rollback_permission is None:
        return json(
            {"code": 40001, "message": f"当前状态（{invoice_before.status}）不支持回退"},
            status=400,
        )

    denied = await ensure_permission(request, rollback_permission)
    if denied is not None:
        return denied

    success, message = await invoice_service.rollback_invoice(
        invoice_id=invoice_id,
        user_id=user["user_id"] if user else 1,
        comment=comment,
    )
    if not success:
        return json({"code": 40001, "message": message}, status=400)

    invoice_after = await invoice_service.get_invoice_by_id(invoice_id)
    await cache_service.invalidate_billing_cache()

    await create_audit_entry(
        db_session=db,
        user_id=user.get("user_id") if user else None,
        action="rollback",
        module="billing",
        record_id=invoice_id,
        record_type="invoice",
        changes={
            "before": {"status": invoice_before.status, "comment": comment},
            "after": {"status": invoice_after.status if invoice_after else None},
        },
        operation_type="standard",
        ip_address=request.headers.get(
            "x-real-ip", request.headers.get("x-forwarded-for", request.ip)
        ),
        auto_commit=True,
    )

    return json({"code": 0, "message": message})
```

需从 `..middleware.auth`（或该文件现有 import 路径）导入 `ensure_permission`——实现时按 invoices.py 现有 import 风格确认。

`backend/app/routes/billing/vr_settlements.py`（置于 `reject_sales_supervisor` 路由 :582 之后），同构：

```python
@billing_bp.post("/vr-settlements/<settlement_id:int>/rollback")
@auth_required
async def rollback_vr_settlement(request: Request, settlement_id: int):
    """回退至上一步审核（理由必填）

    pending_cs_supervisor → draft（vr_settlement:cs_approve）；
    pending_sales → pending_cs_supervisor（vr_settlement:sales_approve + 客户指定销售身份）。

    Body: { "comment": "回退理由（必填）" }
    """
```

差异点：scope 用 `_ensure_settlement_scope`，service 用 `VrSettlementService(db)` 的 `rollback_settlement`，权限映射 `{"pending_cs_supervisor": "vr_settlement:cs_approve", "pending_sales": "vr_settlement:sales_approve"}`，audit `record_type="vr_settlement"`、`ip_address=_client_ip(request)`，其余（comment 必填 400、404、状态不在映射 400、ensure_permission 403、缓存失效、audit changes 结构）与上面逐字一致。

**B5. 前端 API**

- `frontend/src/api/billing.ts`（`cancelInvoice` :594 旁）：
  ```ts
  export function rollbackInvoice(id: number, comment: string) {
    return api.post(`/billing/invoices/${id}/rollback`, { comment })
  }
  ```
- `frontend/src/api/vrSettlement.ts`（`cancelVrSettlement` :148 旁）：
  ```ts
  export function rollbackVrSettlement(id: number, comment: string) {
    return api.post(`/billing/vr-settlements/${id}/rollback`, { comment })
  }
  ```

**B6. 新建 `frontend/src/views/billing/components/RollbackModal.vue`**

照 `VrSettlementApprovalModal.vue` 结构（a-modal `@before-ok` + a-form + a-textarea + max-length 500 show-word-limit + auto-size）：

- props：`visible: boolean`、`title?: string`（默认 `'回退'`）、`loading?: boolean`（默认 false）
- emits：`update:visible`、`submit`（payload: `comment: string`）
- 表单项：label「回退理由（必填）」，placeholder「请填写回退理由」，rules：`{ required: true, message: '回退必须填写理由' }`
- `handleSubmit`：validate 通过后 `emit('submit', form.comment.trim())`，失败/异常返回 false（不关弹窗）；打开时重置表单（watch visible，照抄 VrSettlementApprovalModal :80-90）

**B7. `InvoiceDetailDrawer.vue`**

- 模板 action-section：`pending_ops` 运营确认按钮之后加：
  ```vue
  <button
    v-if="can('billing:ops_approve') && invoice.status === 'pending_ops' && canConfirmOps"
    class="btn"
    @click="emit('rollback', invoice.id)"
  >
    回退
  </button>
  ```
  `pending_sales` 销售确认按钮之后同构（`can('billing:sales_approve') && canConfirmSales`）。
- emits 声明（:356-364 区域）加 `(e: 'rollback', id: number): void`。

**B8. `Invoices.vue`**

- `handleSingleAction`（:678-720）action 联合类型加 `'rollback'`，分支 `'rollback': () => openRollbackModal(record),`
- 新增状态与处理（照 `openApprovalModal`/`handleApprovalSuccess` :711-716 及 approvalModal 相关 refs 模式）：
  ```ts
  const rollbackModalVisible = ref(false)
  const rollbackTarget = ref<Invoice | null>(null)
  const rollbackSubmitting = ref(false)
  const openRollbackModal = (record: Invoice) => { rollbackTarget.value = record; rollbackModalVisible.value = true }
  const handleRollbackSubmit = async (comment: string) => {
    if (!rollbackTarget.value) return
    rollbackSubmitting.value = true
    try {
      await rollbackInvoice(rollbackTarget.value.id, comment)
      Message.success('已回退至上一步')
      rollbackModalVisible.value = false
      loadInvoices()
      await refreshDetailIfOpen()
    } catch (error) {
      handleError(error)
    } finally {
      rollbackSubmitting.value = false
    }
  }
  ```
  （`Message`/`handleError`/`refreshDetailIfOpen`/`loadInvoices` 均为该文件既有符号，按现有 import 使用。）
- 模板挂载 `<RollbackModal v-model:visible="rollbackModalVisible" :loading="rollbackSubmitting" title="回退至上一步审核" @submit="handleRollbackSubmit" />`（置于 DiscountApprovalModal 旁 :311-316）。
- 列表快捷操作列：`pending_ops` 行加「回退」按钮（`v-if` 同 drawer 条件，照现有 confirm-ops 快捷按钮 :190-199 的样式与 `@click.stop="handleSingleAction(record as Invoice, 'rollback')"` 模式）；`pending_sales` 行同构。

**B9. `VrSettlementDetailDrawer.vue`**

- 模板 action-section：`pending_cs_supervisor` 客服主管审批按钮之后加：
  ```vue
  <button
    v-if="can('vr_settlement:cs_approve') && settlement.status === 'pending_cs_supervisor'"
    class="btn"
    @click="emit('rollback', settlement.id)"
  >
    回退
  </button>
  ```
  `pending_sales` 销售审批 `<template>` 块内（`canConfirmSales` 分支旁）同构加 `v-if="can('vr_settlement:sales_approve') && settlement.status === 'pending_sales' && canConfirmSales"` 的回退按钮。
- emits 声明加 `(e: 'rollback', id: number): void`。

**B10. `VrSettlements.vue`**：同 B8 模式——`handleSingleAction`（:479-520）加 `'rollback'` 分支 → `openRollbackModal`；新增 rollback refs 与 `handleRollbackSubmit`（调 `rollbackVrSettlement`）；挂载 `RollbackModal`（置于 VrSettlementApprovalModal 旁 :283-288）；列表快捷列 `pending_cs_supervisor`/`pending_sales` 行加「回退」按钮（pending_sales 的加 `canConfirmSales(record)` 判断，照 :153-176 模式）。

### C. 减免专用权限点 + 全审批节点发起（需求 3）

**C1. `backend/scripts/seed.py` 注册新权限码**

`ALL_PERMISSIONS`（:41-118）：
- `("billing:discount_approve", "减免审批", "审批结算单减免申请", "billing"),`（:79）之后插入：
  ```python
  ("billing:discount_apply", "减免申请", "提交/修改结算单减免金额", "billing"),
  ```
- `("vr_settlement:edit", "编辑VR结算单", "提交/修改减免、取消VR结算单", "vr_settlement"),`（:85）整行替换为（减免职责从 edit 描述中剥离）：
  ```python
  ("vr_settlement:edit", "编辑VR结算单", "取消VR结算单", "vr_settlement"),
  ("vr_settlement:discount_apply", "VR减免申请", "提交/修改VR结算单减免金额", "vr_settlement"),
  ```
- 段注释计数同步：`# 结算管理 (18)` → `# 结算管理 (19)`；`# VR编辑费用结算 (8)` → `# VR编辑费用结算 (9)`。

`PRESET_ROLES`「运营经理」权限列表（:216-248）：`"billing:edit",` 之后插 `"billing:discount_apply",`；`"vr_settlement:edit",` 之后插 `"vr_settlement:discount_apply",`。超管由 `sync_permissions` 自动关联全部权限；销售经理/客服主管/销售主管预置角色不授予（与现状一致：三者本就无对应 edit 权限）。

**C2. `backend/tests/_test_data.py` 同步权限行**

`PERMISSION_ROWS`（:15-88）：
- `("billing:discount_approve", "减免审批", "billing"),` 之后插 `("billing:discount_apply", "减免申请", "billing"),`
- `("vr_settlement:edit", "编辑VR结算单", "vr_settlement"),` 之后插 `("vr_settlement:discount_apply", "VR减免申请", "vr_settlement"),`

（`PERMISSION_CODES` 由行数据派生，勿手改；integration/e2e conftest 同源消费。）

**C3. 后端路由权限码切换（仅两个减免路由，其余 `*:edit` 用法一律不动）**

- `backend/app/routes/billing/invoices.py:862`：`@require_permission("billing:edit")` → `@require_permission("billing:discount_apply")`（apply_discount 路由；同文件其余 11 处 `billing:edit` 不动）。
- `backend/app/routes/billing/vr_settlements.py:638`：`@require_permission("vr_settlement:edit")` → `@require_permission("vr_settlement:discount_apply")`（apply_vr_discount 路由；`cancel` 等仍用 `vr_settlement:edit`）；同路由 docstring「（draft / pending_cs_supervisor / pending_sales 可改）」改为「（客户确认前任意审批节点可改，含 pending_sales_supervisor）」。

**C4. 普通单 service 放开 `pending_discount_approval` + 清空上轮审批**

`backend/app/services/billing.py` `apply_discount`（:1567-1612）：
- 允许状态列表 `["draft", "pending_ops", "pending_sales"]`（:1581）行内追加 `"pending_discount_approval"`（不引入新常量，最小 diff）。
- docstring（:1573-1576）替换为：
  ```
  允许状态：draft / pending_ops / pending_sales / pending_discount_approval
  （客户确认前任意审批节点可改；pending_customer 起不允许再改减免，否则会绕过减免审批）。
  ```
- `invoice.discount_applied_at = now_str` 赋值之后，插入与 `vr_settlement.py:363-366` 逐字一致的清空：
  ```python
  # 重新提交减免时清空上一轮审批结果（若有），避免展示过期审批意见
  invoice.discount_approver_id = None  # pyright: ignore[reportAttributeAccessIssue]
  invoice.discount_approved_at = None  # pyright: ignore[reportAttributeAccessIssue]
  invoice.discount_approval_comment = None  # pyright: ignore[reportAttributeAccessIssue]
  ```
- 普通单在 `pending_discount_approval` 改减免后 **status 不变**（仍等待减免审批）；VR service 与 `_DISCOUNT_EDITABLE_STATUSES` 零改动（已覆盖全部节点）。

**C5. 前端按钮权限与状态**

- `frontend/src/views/billing/components/InvoiceDetailDrawer.vue:229-232`：`can('billing:edit')` → `can('billing:discount_apply')`，状态数组 `['draft', 'pending_ops', 'pending_sales']` → 追加 `'pending_discount_approval'`；上方注释（:226-228）同步改为「客户确认前任意审批节点可改（与后端 InvoiceService.apply_discount 对齐）」。
- `frontend/src/views/billing/components/VrSettlementDetailDrawer.vue:151-163`：`can('vr_settlement:edit')` → `can('vr_settlement:discount_apply')`；状态数组与注释不变。
- 范围边界：`InvoiceDetailDrawer.vue` 的 `canEditSettlementAccount`（结算账户编辑，:389-397）仍用 `billing:edit`；列表页无减免按钮；`DiscountEditModal.vue` / `VrSettlementDiscountModal.vue` 内部无权限判断，不改。

**C6. 测试更新**

- `backend/tests/unit/test_billing_service.py:2802-2816` `test_apply_discount_rejects_approval_node` **改写**为 `test_apply_discount_allowed_at_approval_node_clears_approver`：`_invoice("pending_discount_approval")` 且预置 `discount_approver_id=9`、`discount_approved_at="2026-11-01 10:00:00"`、`discount_approval_comment="同意"` → `success is True`，三字段均为 `None`，`invoice.status` 仍为 `pending_discount_approval`（mock 模式照该文件现有 `patch.object(InvoiceService, "get_invoice_by_id", AsyncMock(return_value=invoice))`）。`test_apply_discount_rejects_pending_customer`（:2786）与 `test_apply_discount_allowed_in_pending_sales`（:2818）保持不变；类 docstring（:2603-2605）补一句「`pending_discount_approval` 可改（清空上轮审批），`pending_customer` 起锁定」。
- `backend/tests/integration/test_billing_api.py::test_discount_approval_workflow` 第 4 步（:1698-1707）：注释与断言从「审批节点不允许再改减免（防止绕过审批）/ 400」改为「审批节点可修改减免申请（重新等待审批）/ 200」，随后 GET 详情断言 `discount_amount == 50`；第 5、6 步不变。
- `backend/tests/integration/test_billing_api.py::test_discount_reject_requires_comment_and_reverts` 第 4 步（:1799-1808）PUT 之后补：GET 详情断言 `discount_approval_comment is None`（重新提交减免清空驳回理由），其余断言不变。
- `frontend/src/views/billing/components/__tests__/DiscountHistorySection.test.ts`：mock（:28）`p === 'billing:edit'` → `p === 'billing:discount_apply'`；:120 用例名改「无 billing:discount_apply 权限时不渲染修改减免按钮」；新增用例：`mountDrawer({ ...baseInvoice, status: 'pending_discount_approval' })` 渲染减免按钮（`hasDiscountButton` 为 true）。
- `frontend/src/views/billing/components/__tests__/VrSettlementDrawerDiscount.test.ts`：mock（:28）`p === 'vr_settlement:edit'` → `p === 'vr_settlement:discount_apply'`；:87 用例名改「无 vr_settlement:discount_apply 权限时不渲染减免按钮」；状态用例不变（VR 白名单未动）。

## Critical files & anchors

1. `backend/app/services/vr_settlement.py` — `confirm_sales_supervisor`（门禁插入点，:269-306）；新增 `rollback_settlement`；常量 `_VR_ROLLBACK_TARGETS` 置于 `_DISCOUNT_EDITABLE_STATUSES`（:22-28）旁。
2. `backend/app/services/billing.py` — 新增 `rollback_invoice`（置于 `confirm_sales` 后）；既有 `_discount_reject_revert_status`（:1661-1672）是「驳回=回退上一步」的范式，**勿改**。
3. `backend/app/routes/billing/invoices.py` + `backend/app/routes/billing/vr_settlements.py` — 新 rollback 路由（各置于 reject 路由后）、VR 响应加 `discount_approval_required`、两个 apply_discount 路由权限码切换；相邻 confirm/reject 路由是 scope/audit/cache 的照抄模板。`backend/scripts/seed.py`（:79/:85 权限定义、:216-248 运营经理预置清单）与 `backend/tests/_test_data.py`（:15-88）必须同步注册 `billing:discount_apply` / `vr_settlement:discount_apply`，否则漂移门禁红灯。
4. `backend/app/middleware/auth.py` — 新增 `ensure_permission`（与 `require_permission` 同 lookup 路径）。
5. `frontend/src/views/billing/VrSettlements.vue`、`Invoices.vue`、`components/VrSettlementDetailDrawer.vue`、`components/InvoiceDetailDrawer.vue`、新建 `components/RollbackModal.vue`。

## Verification

```bash
# 后端（cwd=repo root；.venv 为 backend 虚拟环境）
cd backend && .venv/bin/python -m pytest tests/unit/test_vr_settlement_service.py tests/unit/test_billing_service.py tests/unit/test_permission_drift.py tests/unit/test_test_data_consistency.py tests/integration/test_vr_settlement_api.py tests/integration/test_billing_api.py -q

# 前端
cd frontend && npm run type-check && npx vitest run src/views/billing
```

新行为检查（每条对应可观察输出）：

1. **门禁拒绝**（单测）：VR 单 `pending_sales_supervisor` + `discount_amount=100` + count=1 + 操作人权限集不含 `billing:discount_approve` → `(False, "该结算单包含减免，需由具有减免审批权限的用户审批")`，settlement 状态不变。
2. **门禁放行**（单测 + 集成）：同上但操作人权限集含该码 → `(True, ...)`，`status=pending_customer` 且 `discount_approver_id/approved_at/comment` 写入；count=0 时无权限操作人也可通过（回退原流程）。
3. **VR 回退**（集成）：建单 → submit → confirm-cs 后 `POST /api/v1/billing/vr-settlements/<id>/rollback` `{"comment":"信息有误"}` → 200 且状态回 `draft`；再走到 `pending_sales` 回退 → `pending_cs_supervisor`；`draft` 状态回退 → 400「当前状态（draft）不支持回退」；空 comment → 400「回退必须填写理由」。
4. **普通单回退**（集成）：`pending_ops` 回退 → `draft`；`pending_sales` 回退 → `pending_ops`；非指定经理账号 → 400 身份文案；`draft` → 400 不支持回退。
5. **前端**（vitest）：`discount_approval_required=true` 且 `hasPermission('billing:discount_approve')=false` → 抽屉「审批通过」禁用；`false` → 可用；`pending_cs_supervisor`/`pending_sales` 渲染「回退」按钮，`pending_sales_supervisor` 不渲染。
6. **冒烟**（本地起前后端）：VR 单有减免时无减免审批权限的销售主管账号点「审批通过」被拦截并见提示；有权限账号通过；各节点「回退」弹窗必填理由后状态正确回流；普通结算单管理页同理。
7. **减免专用权限点**：`test_permission_drift.py` + `test_test_data_consistency.py` 通过 = 新码已在 seed/`_test_data` 注册且前后端引用无漂移；vitest 中 mock `hasPermission` 对 `billing:discount_apply` 返回 false → 抽屉不渲染「设置/修改减免」按钮，返回 true 且 `status='pending_discount_approval'` → 渲染。
8. **全节点发起 + 清空审批**（集成）：`test_discount_approval_workflow` 第 4 步改减免 → 200 且详情 `discount_amount=50`，第 5 步审批后 `discount_approval_comment=="同意减免"`；`test_discount_reject_requires_comment_and_reverts` 第 4 步后再 GET 详情 `discount_approval_comment is None`。
9. **冒烟补充**（权限解耦）：以仅持 `billing:edit`（无 `billing:discount_apply`）的账号登录——结算单详情页不显示「设置/修改减免」按钮，直接 `PUT /api/v1/billing/invoices/<id>/discount` 返回 403「权限不足」；在角色权限页给该角色勾选「减免申请」并重新登录（或等权限缓存 600s 过期）后恢复。VR 侧同理（`vr_settlement:edit` vs `vr_settlement:discount_apply`）。

## Assumptions & contingencies

- 「有对应减免审批权限的人」按权限码 `billing:discount_approve` 判定（与普通结算单减免审批节点同一权限点）；系统内是否存在持权用户以 DB 实时查询为准（`is_active IS NOT FALSE` 视为可审批）。
- 回退理由仅写入审计日志 `changes`，不新增模型列/迁移。
- 集成测试的 `mock_cache` fixture 给测试用户赋予全权限，无法构造「无减免审批权限的操作人」，门禁拒绝路径由单测覆盖；若实现时可在集成环境新建二级用户并签发 token，可补一条集成用例（非必须）。
- 单测 mock 注意（`.trellis/spec/backend/database-guidelines.md` Forbidden Patterns）：`count_users_with_permission` 走 `session.execute(...).scalar_one()`、`get_user_permissions` 走 `.scalars().all()`，mock side_effect 必须显式提供对应链（用现有 `_result(scalar_value=...)` / `_result(scalars_list=[...])`）；`confirm_sales_supervisor` 有减免时的 execute 顺序为：settlement → count →（count>0 时）permissions。
- 若实现时发现 `get_vr_settlements` 行构建处已有可复用的持权查询结果，直接复用，不重复查询。
- 新权限点是**解耦重构**：预置角色中仅运营经理同时持有 `billing:edit` + `vr_settlement:edit`，给运营经理加两个新码后预置角色能力与现状完全一致；持有 `billing:edit` 的**自定义角色不会自动获得新码**（seed 只增不删且不触碰自定义角色），上线后需管理员在角色权限页手动勾选，否则这些角色将失去「设置减免」能力——这是专用权限点的既定代价，已向用户确认接受。
- 上线动作（非代码改动）：部署后执行 `cd backend && .venv/bin/python scripts/seed.py --sync-permissions` 注册两个新权限码并给预置角色加码；脚本自动失效 Redis 权限缓存（`cache:permissions:*`），无需手工清理。未跑该命令前，前端按钮隐藏 + 后端对新码一律 403。
- 「任意审批节点」= 客户确认前的全部审批节点；`pending_customer` 及以后仍锁定（既有「防绕过已生效减免审批」设计与 `test_apply_discount_rejects_pending_customer`、`test_discount_approval_workflow` 第 6 步两个既有断言保持不变）。
