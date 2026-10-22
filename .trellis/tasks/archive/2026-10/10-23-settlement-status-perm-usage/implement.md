# 实施记录与验收边界

## 目标

1. 彻底废弃结算单 `paid` 旧流程（枚举/路由/服务/权限/存量数据）。
2. 明细生成状态拆为 `billing:detail_status_view` + `billing:detail_regenerate` 两个独立权限。
3. 结算单详情计费明细表格新增用量总计行。

## 改动文件

### 行为组 1：废弃 paid

| 文件 | 改动 |
|---|---|
| `backend/app/models/billing.py` | 删 `InvoiceStatus.PAID` 与 docstring「旧流程」段 |
| `backend/app/routes/billing/invoices.py` | 删 `pay_invoice` / `complete_invoice` 路由（117 行）；导出 `status_map` 删 `paid` |
| `backend/app/services/billing.py` | 删 `pay_invoice` / `complete_invoice` 服务方法；`_execute_deduction` 保留 |
| `backend/app/routes/webhooks.py` | 支付回调标记 `completed`，补 `completed_at`/`completed_by=None`，保留 `paid_at` 作凭证 |
| `backend/app/services/analytics.py` | 4 处 `status.in_(["paid","completed"])` → `["completed"]` |
| `backend/app/middleware/audit.py` | 删 `map_method_to_action` 的 `/pay`、`/complete` 死分支 |
| `backend/alembic/versions/z5a6b7c8d9e0_*.py` | 新建迁移：`paid` → `completed`，COALESCE 回填 `completed_at`/`completed_by`；downgrade 留空 |
| `backend/scripts/seed.py` | 删 `billing:pay` 权限；登记到 `LEGACY_TO_NEW_PERMISSIONS`（空列表，纯废弃） |
| `backend/tests/_test_data.py` | 删 `billing:pay`，加两个新权限元组 |
| `backend/tests/unit/test_billing_service.py` | 删 2 个 complete_invoice 测试；参数化移除 `paid` |
| `backend/tests/integration/test_billing_api.py` | 删 `test_pay_invoice_invalid_state`、`test_complete_invoice_insufficient_balance`（94 行）；状态元组移除 `paid` |
| `backend/tests/test_analytics_service.py` | mock 状态列表移除 `paid`；状态统计测试数据改 `completed`/`cancelled` |
| `backend/tests/unit/test_audit_middleware.py` | 删 `test_post_pay_invoice`、`test_post_complete_invoice` |
| `backend/tests/performance/test_api_load.py` | status 列表移除 `paid` |

### 行为组 2：独立权限

| 文件 | 改动 |
|---|---|
| `backend/scripts/seed.py` | `ALL_PERMISSIONS` 加 `billing:detail_status_view`、`billing:detail_regenerate`；运营经理加两项、销售经理加 view 项 |
| `backend/tests/_test_data.py` | 同步两个新权限元组 |
| `backend/app/routes/billing/invoices.py` | `detail-logs` → `billing:detail_status_view`；`regenerate-detail` / `regenerate-detail-batch` → `billing:detail_regenerate` |
| `frontend/src/views/billing/Invoices.vue` | 「明细生成状态」按钮 → `billing:detail_status_view` |
| `frontend/src/views/billing/components/DetailGenStatusDrawer.vue` | 行内 + 批量重生按钮 → `billing:detail_regenerate` |
| `frontend/src/views/billing/components/InvoiceDetailDrawer.vue` | 重生按钮 → `billing:detail_regenerate`；下载明细仍 `billing:view` |

### 行为组 3：用量总计

| 文件 | 改动 |
|---|---|
| `frontend/src/views/billing/components/InvoiceDetailDrawer.vue` | 加 `totalUsage` computed；`</tbody>` 后插 `<tfoot>` 汇总行（`v-if` 有明细）；`.usage-total-row` 样式 |
| `frontend/src/views/billing/components/__tests__/InvoiceDetailDrawer.usageTotal.test.ts` | 新增 4 用例：无明细/undefined 不渲染、有明细求和、小数口径 |

### 前端枚举清理

| 文件 | 改动 |
|---|---|
| `frontend/src/constants/invoiceStatus.ts` | `INVOICE_STATUS_MAP` / `INVOICE_STATUS_CLASS_MAP` 删 `paid` |
| `frontend/src/api/billing.ts` | `Invoice.status` 联合类型删 `'paid'` |
| `frontend/src/components/invoice/InvoiceTimeline.vue` | 删「确认付款」节点 + `TimeField` 联合类型的 `'paid_at'` |
| `frontend/src/views/__tests__/Home.test.ts` | mock 状态 `paid` → `completed` |

## 验证结果

| 验证项 | 命令 / 场景 | 结果 |
|---|---|---|
| 后端 paid 引用清零 | `grep -rn '"paid"\|InvoiceStatus.PAID\|billing:pay' backend/app backend/scripts backend/tests` | 无输出（回款金额字段名 `total_paid`/`paid` 除外，属金额语义未改） |
| 前端 paid 引用清零 | `grep -rn "'paid'\|\"paid\"" frontend/src` | 无输出 |
| 后端 lint | `ruff check app/ scripts/ tests/ alembic/` | All checks passed |
| 后端类型 | `pyright` | 0 errors |
| 单测 | `pytest tests/unit tests/test_analytics_service.py` | 738 passed；5 failed 为 `main` 上预存失败（`TestCustomerHealthScoreService` MagicMock tiers），已 `git stash` 对照确认与本次无关 |
| 集成测试 | `pytest tests/integration -q` | 见后台任务输出 |
| 前端单测 | `npx vitest run` | 17 files / 131 tests passed |
| 前端类型 | `pnpm type-check` | 通过 |
| 迁移应用 | `alembic upgrade head` | head `z5a6b7c8d9e0`；`SELECT count(*) FROM invoices WHERE status='paid'` = 0；completed 行 `completed_at` 均非空 |
| Schema 漂移 | `scripts/check_schema_drift.py` | PASSED |
| 旧路由已移除 | `POST /billing/invoices/1/pay`、`/complete` | 404 Requested URL not found |
| 新权限端点（admin） | `GET /billing/invoices/detail-logs` | 200 |
| 新权限端点（仅 `billing:view` 的临时角色） | detail-logs / regenerate-detail / regenerate-detail-batch | 均 403（临时角色与用户已清理） |
| 角色授权（seed 后） | 超级管理员 2 项、运营经理 2 项、销售经理 1 项 | 符合计划 |
| `billing:pay` 运行库清理 | `scripts/seed.py` 步骤 2.7 | 清理废弃权限码 1 个 |
| 状态筛选项（浏览器） | 结算单管理页 → 状态下拉 | 草稿/待运营经理确认/待销售经理确认/待客户确认/客户已确认/已结算/已取消，**无「已付款」** |
| 明细状态抽屉（浏览器） | 点击「明细生成状态」 | 抽屉打开，批量重生按钮可见（admin 有新权限） |
| 用量总计（浏览器） | completed 结算单详情（quantity 432 + 15） | 汇总行显示 `447`，与明细之和一致 |
| 用量总计空态（组件测试） | items 为 `[]` / `undefined` | 不渲染 tfoot |

## 备注

- `paid_at` 列与响应字段保留：不删列、不删模型字段，webhook 仍写入作外部支付凭证。
- seed 的 PRESET_ROLES 仅对新建角色生效；存量运营/销售经理角色需管理员在角色权限页手动勾选，或测试环境 `python scripts/seed.py --reset`。
- 迁移 downgrade 留空：迁移后无法区分「原本 completed」与「paid 迁移而来」。
