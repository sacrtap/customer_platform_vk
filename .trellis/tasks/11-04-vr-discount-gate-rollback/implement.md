# Implement — 执行清单

顺序执行；每步完成后跑对应验证。所有命令 cwd=repo root（后端用 `backend/.venv/bin/python`）。

## 阶段 A：门禁（需求 1）

- [ ] A1 `backend/app/services/permissions.py`：import 改 `from sqlalchemy import func, select`；新增 `count_users_with_permission`。
- [ ] A2 `backend/app/services/vr_settlement.py`：常量 + import + `confirm_sales_supervisor` 门禁插入。
- [ ] A3 `backend/app/routes/billing/vr_settlements.py`：详情/列表响应加 `discount_approval_required`。
- [ ] A4 前端：`api/vrSettlement.ts` 接口字段；`VrSettlementDetailDrawer.vue` + `VrSettlements.vue` 禁用态。
- [ ] A5 单测：门禁三条 + 改写 `test_confirm_sales_supervisor_writes_discount_approval`。
- [ ] A6 验证：`cd backend && .venv/bin/python -m pytest tests/unit/test_vr_settlement_service.py -q`

## 阶段 B：回退（需求 2）

- [ ] B1 `backend/app/middleware/auth.py`：`ensure_permission`。
- [ ] B2 `backend/app/services/billing.py`：`_INVOICE_ROLLBACK_TARGETS` + `rollback_invoice`。
- [ ] B3 `backend/app/services/vr_settlement.py`：`_VR_ROLLBACK_TARGETS` + `rollback_settlement`。
- [ ] B4 路由：invoices.py / vr_settlements.py 各加 rollback 路由（照相邻 confirm/reject）。
- [ ] B5 前端 API：`rollbackInvoice` / `rollbackVrSettlement`。
- [ ] B6 composable：`useInvoice.ts` / `useVrSettlement.ts` 加 `doRollback`（照 `doConfirmOps` 模式）。
- [ ] B7 新建 `frontend/src/views/billing/components/RollbackModal.vue`。
- [ ] B8 两个详情抽屉：回退按钮 + emits。
- [ ] B9 两个列表页：`handleSingleAction` 分支 + rollback refs/提交 + 挂载 Modal + 列表快捷按钮。
- [ ] B10 单测：`rollback_invoice` / `rollback_settlement` 用例；集成：普通单 + VR 回退用例。
- [ ] B11 验证：`cd backend && .venv/bin/python -m pytest tests/unit/test_billing_service.py tests/integration/test_billing_api.py tests/integration/test_vr_settlement_api.py -q`

## 阶段 C：专用权限点 + 全节点（需求 3）

- [ ] C1 `backend/scripts/seed.py`：两个新码 + 运营经理预置 + 段注释计数。
- [ ] C2 `backend/tests/_test_data.py`：同步两行。
- [ ] C3 路由切换：invoices.py apply_discount / vr_settlements.py apply_vr_discount 权限码 + docstring。
- [ ] C4 `backend/app/services/billing.py::apply_discount`：白名单追加 + 清空三字段 + docstring。
- [ ] C5 前端：两个抽屉设置减免按钮权限与状态。
- [ ] C6 测试：单测改写 + 集成两处 + 前端两个 test.ts + `test_permission_drift.py` 豁免登记两条。

## 阶段 D：全量验证

- [ ] D1 后端：`cd backend && .venv/bin/python -m pytest tests/unit/test_vr_settlement_service.py tests/unit/test_billing_service.py tests/unit/test_permission_drift.py tests/unit/test_test_data_consistency.py tests/integration/test_vr_settlement_api.py tests/integration/test_billing_api.py -q`
- [ ] D2 lint/type：`cd backend && .venv/bin/ruff check app/ && .venv/bin/pyright`（0 error）
- [ ] D3 前端：`cd frontend && npm run type-check && npx vitest run src/views/billing`
- [ ] D4 冒烟（dev server）：AC8 四项人工验证（门禁拦截/放行、回退理由必填回流、权限解耦 403）。

## Review gates

- B4 路由完成后自查 scope→service→cache→audit 四件套与相邻路由逐字一致。
- C6 完成后跑漂移门禁两条单测，确认新码三处注册无遗漏。
- D 全绿后才进入 Phase 3（spec 沉淀 + commit）。

## Rollback points

- 每阶段独立可提交；A/B/C 互不依赖数据（仅共享 C1 注册的先决条件：A/B 的前端权限码不依赖新码）。
- 门禁为纯增量判断，回退只需移除 A2 插入段。
