# 结算单：状态枚举清理 / 明细生成状态权限 / 用量总计

## Goal

三项待改：彻底废弃结算单旧流程 `paid`（含路由、服务方法、权限与存量数据迁移）；
明细生成状态拆为 `billing:detail_status_view` 与 `billing:detail_regenerate` 两个独立权限；
结算单详情计费明细表格新增 quantity 求和汇总行。

## Requirements

### 行为组 1：废弃 paid 旧流程

1. 移除 `paid` 状态枚举（前端 `INVOICE_STATUS_MAP` / `INVOICE_STATUS_CLASS_MAP`、后端 `InvoiceStatus.PAID`、前端 `Invoice.status` 联合类型、`InvoiceTimeline` 的「确认付款」节点）。
2. 移除 `pay` / `complete` 路由与 `pay_invoice` / `complete_invoice` 服务方法，及 `billing:pay` 权限种子。
3. webhook 支付回调将状态标记为 `completed`（保留 `paid_at` 作支付凭证，补 `completed_at` / `completed_by = None`）。
4. analytics 4 处 `Invoice.status.in_(["paid", "completed"])` 收窄为 `["completed"]`。
5. alembic 迁移把存量 `paid` 行改为 `completed`（`completed_at`/`completed_by` 分别回填 `paid_at`/`customer_confirmed_by`）。
6. 审计中间件 `map_method_to_action` 的 `/pay`、`/complete` 分支及对应测试删除。
7. 相关测试清理（删除已删功能的测试、参数化与 mock 数据中的 `paid`）。

### 行为组 2：明细生成状态独立权限

1. 新增权限 `billing:detail_status_view`（查看明细生成状态）与 `billing:detail_regenerate`（重新生成明细）。
2. 后端 3 个路由权限收窄：`GET /invoices/detail-logs` 用 `detail_status_view`；`POST /invoices/<id>/regenerate-detail` 与 `POST /invoices/regenerate-detail-batch` 用 `detail_regenerate`。
3. 前端 4 处 `can(...)` 换成新权限码；下载明细按钮仍用 `billing:view`。
4. 预置角色：运营经理加两项，销售经理加 `detail_status_view`；测试权限清单同步。

### 行为组 3：用量总计

1. `InvoiceDetailDrawer.vue` 计费明细表格底部新增 `<tfoot>` 汇总行，展示 `items.quantity` 之和（`formatItemNumber`），无明细时不渲染。

## Acceptance Criteria

- [ ] `grep -rn '"paid"\|InvoiceStatus.PAID\|billing:pay' backend/app backend/scripts backend/tests` 无输出（analytics 回款金额字段名 `paid` 除外）
- [ ] `grep -rn "'paid'\|\"paid\"" frontend/src` 无输出
- [ ] alembic upgrade head 后 `SELECT count(*) FROM invoices WHERE status='paid'` = 0
- [ ] 角色权限页「结算管理」分组出现「明细生成状态查看」「明细重新生成」两项
- [ ] 无 `billing:detail_status_view` 的角色：结算单管理页不显示「明细生成状态」按钮，`GET /billing/invoices/detail-logs` 返回 403
- [ ] 无 `billing:detail_regenerate` 的角色：详情抽屉与明细状态抽屉的重生按钮不可见，两个 regenerate 端点返回 403
- [ ] 含明细的结算单详情表格底部显示「用量总计」行，值 = 各明细 quantity 之和；无明细时不显示
- [ ] `cd backend && python -m pytest tests/unit/test_billing_service.py tests/integration/test_billing_api.py tests/test_analytics_service.py tests/unit/test_audit_middleware.py tests/unit/test_test_data_consistency.py -q` 全绿
- [ ] `cd frontend && npx vitest run` 与 `pnpm type-check` 通过

## Constraints

- `paid_at` 列与响应字段保留（历史凭证），仅停止写入（webhook 例外）。
- 迁移 downgrade 留空（不可逆），注释说明。
- seed 的 PRESET_ROLES 仅影响新建角色；存量角色需管理员手动授权或 `--reset`。
- 审计中间件删除 `/pay`、`/complete` 分支属清理死分支，不改变其他路径映射。
