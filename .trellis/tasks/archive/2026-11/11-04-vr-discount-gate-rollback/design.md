# Design — VR 减免审批门禁 + 双侧审批流回退 + 减免专用权限点

技术设计。执行顺序与验证命令见 `implement.md`。

## 1. 门禁（需求 1）

### 1.1 持权用户统计

`services/permissions.py`：`from sqlalchemy import func, select`；新增
`count_users_with_permission(session, code) -> int`：`count(distinct User.id)`，
join user_roles → Role → role_permissions → Permission，`Permission.code == code`、
`User.deleted_at IS NULL`、`User.is_active IS NOT FALSE`。

### 1.2 service 门禁

`services/vr_settlement.py`：

- 模块级常量 `DISCOUNT_APPROVE_PERMISSION = "billing:discount_approve"`（置于
  `_DISCOUNT_EDITABLE_STATUSES` 旁）。
- import `from .permissions import count_users_with_permission, get_user_permissions`。
- `confirm_sales_supervisor`：状态校验通过后、写 `sales_supervisor_confirmed_*` 之前插入：
  有减免且 count>0 时，操作人权限集不含该码 → `return False, "该结算单包含减免，需由具有减免审批权限的用户审批"`。
  路由层 `(False, msg)` 已映射 40001/400，路由零改动。

### 1.3 响应字段（前端禁用态数据源）

- `routes/billing/vr_settlements.py` 顶部 import `count_users_with_permission`。
- `get_vr_settlement`：`"status"` 之后加
  `"discount_approval_required": bool(discount_amount and != 0) and await count_users_with_permission(db, "billing:discount_approve") > 0`。
- `get_vr_settlements` 列表：行构建前若任一行 `discount_amount` 非 0 则查一次
  `holders_exist`（否则 False，不发查询）；每行 dict 加同名字段。

### 1.4 前端门禁

- `api/vrSettlement.ts`：`VrSettlement` 加 `discount_approval_required?: boolean`。
- `VrSettlementDetailDrawer.vue`：销售主管审批区「审批通过」按钮加禁用态
  （`discountApprovalBlocked` computed + tooltip 包裹禁用 span，照抄同文件
  pending_sales 销售审批禁用态写法）；「审批驳回」不受限。
- `VrSettlements.vue` 列表快捷「审批通过」加同样 `:disabled` + `:title`。

## 2. 回退（需求 2）

### 2.1 动态权限助手

`middleware/auth.py` 在 `require_permission` 后新增
`async def ensure_permission(request, permission_code)`：与 `require_permission`
同一 lookup 路径（get_current_user → permission_cache → get_user_permissions →
`_check_permission`），通过返回 None，否则 401/403。供权限点随资源当前状态
变化的路由复用。

### 2.2 service

- `services/billing.py`：`_INVOICE_ROLLBACK_TARGETS = {"pending_ops": "draft", "pending_sales": "pending_ops"}`；
  `rollback_invoice(invoice_id, user_id, comment)` 置于 `confirm_sales` 后：
  状态映射校验 → `_get_customer` → 身份校验（pending_ops 比 `customer.manager_id`，
  pending_sales 比 `customer.sales_manager_id`）→ 仅改 `status` → `self.db.commit()`。
- `services/vr_settlement.py`：`_VR_ROLLBACK_TARGETS = {"pending_cs_supervisor": "draft", "pending_sales": "pending_cs_supervisor"}`；
  `rollback_settlement(settlement_id, user_id, comment)` 置于 `reject_sales_supervisor` 后：
  同构；仅 `pending_sales` 需身份校验（比 `customer.sales_manager_id`）。
- `comment` 由路由层校验必填后传入；service 不再校验（与 reject 路由同一分工）。

### 2.3 路由（两侧同构，照抄相邻 confirm/reject 路由）

`routes/billing/invoices.py`（置于 `reject_discount` 路由后）：
`POST /invoices/<invoice_id:int>/rollback`，`@auth_required`；流程：
comment 必填（空 → 40001/400）→ 404 不存在 → `_ensure_invoice_scope` →
按 `invoice_before.status` 取映射权限码（不在映射 → 40001）→
`ensure_permission(request, code)` → service → 失败 400 →
`invalidate_billing_cache` + audit（`action="rollback"`、`record_type="invoice"`、
changes `before={status, comment}` / `after={status}`，`ip_address` 用
`request.headers.get("x-real-ip", ...)` 既有表达式）。

`routes/billing/vr_settlements.py`（置于 `reject_sales_supervisor` 路由后）：
`POST /vr-settlements/<settlement_id:int>/rollback` 同构；scope 用
`_ensure_settlement_scope`，service 用 `VrSettlementService(db).rollback_settlement`，
权限映射 `{"pending_cs_supervisor": "vr_settlement:cs_approve", "pending_sales": "vr_settlement:sales_approve"}`，
audit `record_type="vr_settlement"`、`ip_address=_client_ip(request)`。

两路由需从 `...middleware.auth` import `ensure_permission`。

### 2.4 前端

- `api/billing.ts`（`cancelInvoice` 旁）：`rollbackInvoice(id, comment)`；
  `api/vrSettlement.ts`（`cancelVrSettlement` 旁）：`rollbackVrSettlement(id, comment)`。
- 新建 `components/RollbackModal.vue`：照 `VrSettlementApprovalModal.vue`
  （a-modal `@before-ok` + a-form + a-textarea max-length 500 show-word-limit
  auto-size）；props `visible/title?/loading?`，emits `update:visible`/`submit(comment)`；
  理由必填 rules；打开时重置表单。
- 两个详情抽屉 action-section 各加两个「回退」按钮（`v-if` 与既有确认按钮同款
  权限+状态+身份条件），emits 加 `(e: 'rollback', id: number): void`。
- 两个列表页：`handleSingleAction` 加 `'rollback'` 分支；新增 rollback refs 与
  `handleRollbackSubmit`；挂载 RollbackModal；列表快捷列 `pending_ops`/
  `pending_sales`（普通单）与 `pending_cs_supervisor`/`pending_sales`（VR）行加
  「回退」按钮。
- **与 PLAN 的偏差（已核实修正）**：PLAN 让页面层直接调 `rollbackInvoice` +
  `handleError(error)`，但两个列表页均未 import `Message`/`handleError`（页面层
  无直接 API 调用先例，错误处理统一在 composable）。改为把 rollback 调用放入
  `composables/useInvoice.ts` / `useVrSettlement.ts`（`doRollback`，照既有
  `doConfirmOps` 的 `Message.success` + `errorMessage` 模式），页面照
  `doConfirmOps(record.id)` 模式调用，页面层零新增 import。

## 3. 专用权限点 + 全节点发起（需求 3）

### 3.1 注册（三处同步，漂移门禁强制）

- `scripts/seed.py`：`ALL_PERMISSIONS` 的 `billing:discount_approve` 后插
  `("billing:discount_apply", "减免申请", "提交/修改结算单减免金额", "billing")`；
  `vr_settlement:edit` 行替换为 edit（描述剥离减免职责）+ `vr_settlement:discount_apply`；
  段注释计数 `结算管理 (18)→(19)`、`VR编辑费用结算 (8)→(9)`。
  `PRESET_ROLES`「运营经理」：`"billing:edit",` 后插 `"billing:discount_apply",`；
  `"vr_settlement:edit",` 后插 `"vr_settlement:discount_apply",`。
- `tests/_test_data.py::PERMISSION_ROWS` 同步两行（`PERMISSION_CODES` 派生，勿手改）。

### 3.2 路由权限码切换（仅两个减免路由）

- `invoices.py:862` `apply_discount` 路由：`billing:edit` → `billing:discount_apply`。
- `vr_settlements.py:640` `apply_vr_discount` 路由：`vr_settlement:edit` →
  `vr_settlement:discount_apply`；docstring 改为「客户确认前任意审批节点可改，
  含 pending_sales_supervisor」。其余 `*:edit` 用法（submit/cancel/delete 等）一律不动。

### 3.3 普通单 service 放开

`services/billing.py::apply_discount`：状态白名单行内追加 `pending_discount_approval`；
docstring 允许状态段替换；`invoice.discount_applied_at = now_str` 之后插入与
`vr_settlement.py` 逐字一致的清空三字段（含注释）；status 不变（现有代码即不改 status）。

### 3.4 前端按钮权限与状态

- `InvoiceDetailDrawer.vue`：设置减免按钮 `can('billing:edit')` →
  `can('billing:discount_apply')`，状态数组追加 `'pending_discount_approval'`，
  注释同步；`canEditSettlementAccount` 仍用 `billing:edit`。
- `VrSettlementDetailDrawer.vue`：`can('vr_settlement:edit')` →
  `can('vr_settlement:discount_apply')`；状态数组不变。

## 4. 测试更新

- `tests/unit/test_vr_settlement_service.py`：新增门禁拒绝/放行/count=0 三条
  （patch `app.services.vr_settlement.count_users_with_permission` /
  `get_user_permissions`）；**改写** `test_confirm_sales_supervisor_writes_discount_approval`
  （门禁插入后既有 mock 链会 `int(settlement)` TypeError，必须显式 patch 两函数）；
  新增 `rollback_settlement` 用例（两节点回退 + draft 不支持 + 身份校验）。
- `tests/unit/test_billing_service.py`：改写
  `test_apply_discount_rejects_approval_node` →
  `test_apply_discount_allowed_at_approval_node_clears_approver`（预置三字段 →
  成功且三字段 None、status 不变）；类 docstring 补一句；新增 `rollback_invoice`
  用例（两节点 + 身份文案 + 不支持状态）。
- `tests/integration/test_vr_settlement_api.py`：新增 VR 回退集成用例（AC3）。
- `tests/integration/test_billing_api.py`：`test_discount_approval_workflow` 第 4 步
  400→200+GET 断言；`test_discount_reject_requires_comment_and_reverts` 第 4 步补
  GET 断言 `discount_approval_comment is None`；新增普通单回退集成用例（AC4）。
- `tests/unit/test_permission_drift.py`：**必须**在 `EXEMPT_WRITE_ENDPOINTS` 登记
  `/api/v1/billing/invoices/<invoice_id:int>/rollback` 与
  `/api/v1/billing/vr-settlements/<settlement_id:int>/rollback`（理由：权限码随
  结算单当前状态动态判定，`ensure_permission` 在函数体内，AST 扫描只认装饰器
  `require_permission` 字面量——PLAN 遗漏项，不登记则 `test_no_unguarded_endpoints_without_exemption` 红灯）。
- 前端 vitest：`DiscountHistorySection.test.ts` mock 与用例名切换
  `billing:discount_apply` + 新增 `pending_discount_approval` 渲染用例；
  `VrSettlementDrawerDiscount.test.ts` mock 与用例名切换
  `vr_settlement:discount_apply`。

## 5. 兼容与回滚

- 纯增量：无迁移、无模型变更；新权限码 seed 只增不删。
- 上线顺序：先部署代码（新码未注册期间前端按钮隐藏 + 后端 403，符合专用权限点
  预期），再跑 `seed.py --sync-permissions` 注册并自动失效 Redis 权限缓存。
- 回滚：git revert 即可，无数据依赖。
