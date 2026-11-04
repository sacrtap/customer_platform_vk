# VR 减免审批门禁 + 双侧审批流回退 + 减免专用权限与全审批节点发起

> 来源：`VR_结算单减免审批门禁_双侧审批流回退_PLAN.md`（2026-11-04 已逐锚点核实）。
> 本文为需求与验收契约；技术设计见 `design.md`；执行清单见 `implement.md`。

## Goal

三项需求（均已与用户确认方案）：

1. **减免审批权限门禁**：VR 编辑费用结算单含减免（`discount_amount ≠ 0`）时，销售主管审批通过必须由持「减免审批」权限（`billing:discount_approve`）的用户执行；系统内不存在持该权限的用户时，维持原流程（销售主管一并审批，减免生效）。采用**节点门禁**方案：不新增状态、不加迁移，仅在 `confirm_sales_supervisor` 状态校验通过后校验。
2. **各审批节点回退至上一步**：结算单管理页与 VR 编辑费用结算页的各内部审批节点支持「回退」到上一步，理由必填，由当前节点审批人执行（持该节点审批权限 + 该节点原有身份校验）。`pending_customer`（待客户确认，非内部审核节点）不回退。
3. **减免专用权限点 + 全审批节点发起**：「设置/修改减免」按钮与后端接口权限从 `billing:edit` / `vr_settlement:edit` 切换为专用权限点 `billing:discount_apply` / `vr_settlement:discount_apply`（角色权限页可单独配置，与「编辑结算单」解耦）；可发起节点放宽到客户确认前全部审批节点——普通单新增 `pending_discount_approval`（修改后清空上轮审批人三字段、状态不变等待重新审批），VR 已全覆盖无需改。

## Requirements

- R1 门禁只在「有减免」时生效；无人持权（`count(distinct User.id)` 且 `deleted_at IS NULL` 且 `is_active IS NOT FALSE`）时放行任何持节点审批权限的操作人（回退原流程）。
- R2 驳回（`reject_sales_supervisor` / `reject_discount`）不批准减免，不加门禁，行为不变。
- R3 回退仅改 `status`；历史确认字段保留作审计轨迹；回退理由仅写入审计日志 `changes`，不新增模型列/迁移。
- R4 普通单回退：`pending_ops → draft`（`billing:ops_approve` + 客户指定运营经理身份）；`pending_sales → pending_ops`（`billing:sales_approve` + 客户指定销售经理身份）。VR 回退：`pending_cs_supervisor → draft`（`vr_settlement:cs_approve`，无身份校验，与 `confirm_cs_supervisor` 一致）；`pending_sales → pending_cs_supervisor`（`vr_settlement:sales_approve` + 客户指定销售身份）。
- R5 回退理由必填（空 → 400）；当前状态不在映射 → 400「当前状态（X）不支持回退」；权限不足 → 403。
- R6 新权限码 `billing:discount_apply` / `vr_settlement:discount_apply` 必须同步注册 `scripts/seed.py::ALL_PERMISSIONS`、`PRESET_ROLES`（运营经理）、`tests/_test_data.py::PERMISSION_ROWS` 三处（漂移门禁强制）。
- R7 普通单 `apply_discount` 放开 `pending_discount_approval`，重提时清空 `discount_approver_id/approved_at/comment` 三字段，status 不变；`pending_customer` 起仍锁定。VR service 零改动。

## Acceptance Criteria

- [x] AC1（单测）门禁拒绝：VR 单 `pending_sales_supervisor` + `discount_amount=100` + count=1 + 操作人权限集不含 `billing:discount_approve` → `(False, "该结算单包含减免，需由具有减免审批权限的用户审批")`，settlement 状态不变。
- [x] AC2（单测+集成）门禁放行：操作人权限集含该码 → `(True, ...)`，`status=pending_customer` 且减免审批三字段写入；count=0 时无权限操作人也可通过（回退原流程）。
- [x] AC3（集成）VR 回退：建单 → submit → confirm-cs（`pending_sales`）后 `POST /api/v1/billing/vr-settlements/<id>/rollback` `{"comment":"信息有误"}` → 200 且状态回 `pending_cs_supervisor`；再次回退 → `draft`；`draft` 回退 → 400「当前状态（draft）不支持回退」；空 comment → 400「回退必须填写理由」。（注：confirm-cs 后节点为 `pending_sales`，需两次回退才到 `draft`，与 PLAN 原文「一次回退即 draft」的措辞以真实状态机为准。）
- [x] AC4（集成）普通单回退：`pending_ops` → `draft`；`pending_sales` → `pending_ops`；非指定经理账号 → 400 身份文案；`draft` → 400 不支持回退。
- [x] AC5（vitest）`discount_approval_required=true` 且 `hasPermission('billing:discount_approve')=false` → 抽屉「审批通过」禁用；`false` → 可用；`pending_cs_supervisor` 渲染「回退」按钮，`pending_sales_supervisor` 不渲染。
- [x] AC6 权限解耦：`test_permission_drift.py` + `test_test_data_consistency.py` 通过 = 新码已注册且前后端引用无漂移；两个新 rollback 路由已在 `EXEMPT_WRITE_ENDPOINTS` 登记（动态权限码，AST 扫描不到；key 为无前缀形态，因 billing_bp 跨文件定义）。
- [x] AC7（集成）`test_discount_approval_workflow` 第 4 步审批节点改减免 → 200 且详情 `discount_amount=50`，第 5 步审批后 `discount_approval_comment=="同意减免"`；`test_discount_reject_requires_comment_and_reverts` 第 4 步后再 GET 详情 `discount_approval_comment is None`。
- [x] AC8 冒烟（本地起前后端，2026-11-04）：VR 单 submit → confirm-cs → 回退弹窗空理由被拦（「回退必须填写理由」）→ 填理由提交 → 状态回 `draft`，后端日志 `POST /vr-settlements/9/rollback 200`；`pending_sales` 节点回退入口与后端身份校验同源（非指定销售不显示，与集成用例互补）；普通单侧由集成用例 `test_rollback_to_previous_step` 覆盖；权限点切换后 dev 库已 `seed.py` 同步（`billing:discount_apply` / `vr_settlement:discount_apply`）。

## Non-goals

- 不改 VR service 状态机与 `_DISCOUNT_EDITABLE_STATUSES`（已全覆盖）。
- 不动 `pending_discount_approval` 的既有「驳回=回退上一步」行为（`reject_discount` / `_discount_reject_revert_status`）。
- 不加迁移、不加模型列；不动 `canEditSettlementAccount`（仍用 `billing:edit`）。

## Assumptions

- 「有对应减免审批权限的人」按权限码 `billing:discount_approve` 判定（与普通单减免审批节点同一权限点）；以 DB 实时查询为准。
- 集成测试 `mock_cache` 给测试用户全权限（含新码），门禁放行路径由集成覆盖、拒绝路径由单测覆盖。
- 专用权限点是解耦重构：预置角色仅运营经理同时持有两个 edit 码，加新码后能力不变；持有 edit 的自定义角色需管理员手动勾选新码（已向用户确认接受的既定代价）。上线动作：部署后跑 `scripts/seed.py --sync-permissions`。
