# 结算单：状态枚举清理 / 明细生成状态权限 / 用量总计

## Context

结算单（Invoice）有三项待改：
1. 列表"状态"筛选项枚举值不正确——含旧流程兼容态 `paid`（已付款）。新流程 `confirm_invoice` 走 `pending_customer → customer_confirmed → completed`，不再经过 `paid`；旧流程 `pay`/`complete` 路由虽存在但预置角色均无 `billing:pay` 权限，实际不产生。用户要求**彻底废弃旧流程**：移除 `paid` 枚举、`pay`/`complete` 路由与 `billing:pay` 权限，存量 `paid` 数据迁移为 `completed`。
2. "明细生成状态"当前复用 `billing:view`（按钮可见 + `get_invoice_detail_logs` 路由），重新生成复用 `billing:edit`。角色权限配置页缺少独立配置项。用户新增**两个独立权限**：`billing:detail_status_view`（查看）+ `billing:detail_regenerate`（重新生成）。
3. 结算单详情计费明细表格无用量汇总。用户要求 quantity 求和 + 表格底部汇总行。

## Approach

### 行为组 1：废弃 paid 旧流程

#### 1.1 前端状态枚举清理
- 编辑 `frontend/src/constants/invoiceStatus.ts`：
  - `INVOICE_STATUS_MAP`（第6-15行）删除 `paid: '已付款',`（第12行）
  - `INVOICE_STATUS_CLASS_MAP`（第17-26行）删除 `paid: 'green',`（第23行）
  - `INVOICE_STATUS_OPTIONS`（第39行）由 `Object.entries(INVOICE_STATUS_MAP)` 派生，自动剔除 paid，无需改
- `InvoiceStatusBadge.vue`、`InvoiceFilters.vue:67`、`CustomerInvoicesTab.vue:75-76` 均从上述常量读取，自动生效，无需单独改

#### 1.2 后端枚举与路由清理
- `backend/app/models/billing.py` 第27-46行 `InvoiceStatus`：
  - 删除 `PAID = "paid"  # 已付款（旧流程兼容）`（第44行）
  - docstring（第29-37行）删除"旧流程（兼容历史数据）"段（第33-34行），仅保留新流程流转与 cancelled 说明
- `backend/app/routes/billing/invoices.py`：
  - 删除 `pay_invoice` 路由函数（第1305-约1365，`@billing_bp.post("/invoices/<invoice_id:int>/pay")` 整段，含 `@require_permission("billing:pay")`）
  - 删除 `complete_invoice` 路由函数（第1367-约1420，`@billing_bp.post("/invoices/<invoice_id:int>/complete")` 整段）
  - 状态文本映射（第1654-1658附近）删除 `"paid": "已付款",`（第1655行）
  - `paid_at` 响应字段（第354行）**保留返回**——存量历史数据仍可能含此值，前端详情不再依赖它
- `backend/app/services/billing.py`：
  - 删除 `pay_invoice` 方法（第1825-1842）
  - 删除 `complete_invoice` 方法（第1845-约1820后续，`async def complete_invoice` 整段）。`_execute_deduction`（第1780起，新流程 `confirm_invoice` 使用）**保留不动**

#### 1.3 webhook 支付回调改标记 completed
- `backend/app/routes/webhooks.py` 第430-434行：
  - `invoice.status = InvoiceStatus.PAID` → `invoice.status = InvoiceStatus.COMPLETED`
  - `invoice.paid_at = datetime.utcnow()` **保留**（外部支付时间凭证）
  - 新增 `invoice.completed_at = datetime.utcnow().isoformat()`、`invoice.completed_by = None`（外部回调无操作人）
  - 状态前置检查（第407-410行 `CUSTOMER_CONFIRMED, PENDING_CUSTOMER`）保持不变
  - 响应 `invoice.status.value`（第455行）自动反映 completed

#### 1.4 analytics 状态查询收窄
- `backend/app/services/analytics.py` 4 处 `Invoice.status.in_(["paid", "completed"])` → `Invoice.status.in_(["completed"])`：第745、1608、2291、2733行
- `data["total_paid"]`（第893行附近）、`item.get("paid", 0)`（analytics 路由第1118行）是**回款金额字段名**（非状态），不改

#### 1.5 权限种子清理
- `backend/scripts/seed.py` 第71行：删除 `("billing:pay", "结算付款", "标记付款和完成结算", "billing"),`
- `backend/tests/_test_data.py` 第36行：删除 `("billing:pay", "结算付款", "billing"),`

#### 1.6 存量数据迁移
- 新建 alembic revision（`alembic revision -m "drop paid status migrate to completed"`），upgrade 执行：
  ```sql
  UPDATE invoices
  SET status = 'completed',
      completed_at = COALESCE(completed_at, paid_at),
      completed_by = COALESCE(completed_by, customer_confirmed_by)
  WHERE status = 'paid'
  ```
  downgrade 留空（不可逆，注释说明）
- `paid_at` 列**不删**（避免删列 migration 风险，保留为历史凭证字段）

#### 1.7 测试清理
- `backend/tests/integration/test_billing_api.py`：删除 `test_pay_invoice_invalid_state`（第1615）、`test_complete_invoice_insufficient_balance`（第1652）；第1756-1759 状态元组移除 `"paid"`
- `backend/tests/unit/test_billing_service.py`：删除 `test_complete_invoice_downgrades_and_keeps_paid`（第1676）、`test_complete_invoice_consumes_settlement_account_balance`（第1804）；第1895 参数化列表移除 `"paid"`
- `backend/tests/unit/test_analytics_service.py`：第107/137 状态列表移除 `"paid"`；第491/505 `paid` 测试数据改为 `completed` 或移除该断言
- `backend/tests/performance/test_api_load.py` 第226行：status 列表移除 `"paid"`
- `backend/tests/unit/test_audit_middleware.py`：`test_post_pay_invoice`（第47）、`test_post_complete_invoice`（第51）——若 `map_method_to_action` 仍含 `/pay`、`/complete` 分支则连同删除对应分支与测试；实施时 `grep map_method_to_action` 确认
- 实施完成后 `grep -rn "InvoiceStatus.PAID\|\"paid\"\|billing:pay" backend/app backend/scripts backend/tests` 确认无遗漏引用

### 行为组 2：明细生成状态独立权限

#### 2.1 新增权限点与角色默认
- `backend/scripts/seed.py` ALL_PERMISSIONS billing 段（第73行后）新增两行：
  ```python
  ("billing:detail_status_view", "明细生成状态查看", "查看明细文件生成状态", "billing"),
  ("billing:detail_regenerate", "明细重新生成", "重新生成结算单明细文件", "billing"),
  ```
- seed.py PRESET_ROLES：
  - 运营经理权限列表（第147-162）加 `"billing:detail_status_view"`、`"billing:detail_regenerate"`
  - 销售经理权限列表（第166-175）加 `"billing:detail_status_view"`
- `backend/tests/_test_data.py` billing 段同步新增上述两权限元组

#### 2.2 后端路由权限收窄
- `backend/app/routes/billing/invoices.py`：
  - `get_invoice_detail_logs`（第2428行 `@require_permission("billing:view")`）→ `@require_permission("billing:detail_status_view")`
  - `regenerate_invoice_detail_batch`（第2350行 `billing:edit`）→ `billing:detail_regenerate`
  - `regenerate_invoice_detail`（第2397行 `billing:edit`）→ `billing:detail_regenerate`

#### 2.3 前端权限控制
- `frontend/src/views/billing/Invoices.vue` 第10行：`v-if="can('billing:view')"` → `v-if="can('billing:detail_status_view')"`
- `frontend/src/views/billing/components/DetailGenStatusDrawer.vue`：
  - 第65行 `can('billing:edit')` → `can('billing:detail_regenerate')`
  - 第92行 `can('billing:edit')` → `can('billing:detail_regenerate')`
- `frontend/src/views/billing/components/InvoiceDetailDrawer.vue` 第115行（重新生成明细按钮）：`can('billing:edit')` → `can('billing:detail_regenerate')`
- 第108行下载明细按钮 `can('billing:view')` **保持不变**（不在本次范围）

### 行为组 3：用量总计

- `frontend/src/views/billing/components/InvoiceDetailDrawer.vue`：
  - script 新增 computed（紧跟第322行 `can` 定义后）：
    ```ts
    const totalUsage = computed(() =>
      (props.invoice?.items || []).reduce((s, i) => s + (Number(i.quantity) || 0), 0)
    )
    ```
  - 在 `</tbody>`（第178行）后、`</table>`（第179行）前插入（仅当有明细时显示）：
    ```vue
    <tfoot v-if="(invoice.items || []).length > 0">
      <tr class="usage-total-row">
        <td colspan="3">用量总计</td>
        <td class="amount">{{ formatItemNumber(totalUsage) }}</td>
        <td colspan="2"></td>
      </tr>
    </tfoot>
    ```
  - `formatItemNumber` 已从 `@/utils/invoiceFormatters` 导入（第292行），无需新增 import
  - 列顺序：计费类型|设备类型|楼层|用量|计费规则|小计（6列），colspan="3" 跨前三列对齐"用量总计"到用量列
  - 样式可选：`.usage-total-row td { font-weight: 600; background: #f8fafc; }` 加在文件 `<style>` 内

## Critical files & anchors

- `frontend/src/constants/invoiceStatus.ts` — 状态枚举单一来源，删 paid 两行即全前端生效
- `backend/app/routes/billing/invoices.py` — pay/complete 路由删除（1305-1420）+ 3 处明细权限收窄（2350/2397/2428）
- `backend/app/services/billing.py` — pay_invoice/complete_invoice 方法删除（1825-1880 附近），`_execute_deduction` 保留
- `backend/scripts/seed.py` — 删 billing:pay + 新增 2 权限 + 预置角色授权
- `frontend/src/views/billing/components/InvoiceDetailDrawer.vue` — 用量总计 tfoot（178-179 间）+ 重新生成按钮权限（115）

## Verification

**前置**：`backend/.venv` 已就绪；PostgreSQL 可用；前端 `npm run dev` 可启动。

1. **状态筛选项**（行为组1）：
   - `cd backend && grep -rn '"paid"\|InvoiceStatus.PAID\|billing:pay' app/ scripts/ tests/` 输出为空
   - 前端登录结算单管理页 → "状态"筛选下拉不含"已付款"项
2. **权限配置项**（行为组2）：
   - `cd backend && python -c "import asyncio; from scripts.seed import seed; ..."` 或直接 `python scripts/seed.py` 执行种子（幂等 get_or_create）
   - 角色权限页 → "结算管理"分组出现"明细生成状态查看"和"明细重新生成"两项
   - 用无 `billing:detail_status_view` 的角色登录 → 结算单管理页不显示"明细生成状态"按钮（404/无按钮）
3. **用量总计**（行为组3）：
   - 打开任一含计费明细的结算单详情 → 计费明细表格底部出现"用量总计"行，值 = 各明细 quantity 之和
   - 无明细的结算单 → 不显示总计行
4. **回归测试**：
   - `cd backend && python -m pytest tests/unit/test_billing_service.py tests/integration/test_billing_api.py tests/unit/test_analytics_service.py tests/unit/test_audit_middleware.py -q`
   - 前端 `cd frontend && npx vitest run src/composables/__tests__/useInvoice.test.ts`（确认 useInvoice 未被破坏）
5. **存量迁移**：`cd backend && alembic upgrade head`，执行后 `SELECT count(*) FROM invoices WHERE status='paid'` 返回 0

## Assumptions & contingencies

- **paid_at 列保留**：不删列、不删模型字段，仅停止写入（webhook 例外，仍写 paid_at 作支付凭证）。如实施时确认无任何读取方，可后续单独删列 migration，本次不做。
- **webhook 改标记 completed**：外部支付通知语义从"已付款"变为"已完成结算"。若实际业务仍需外部支付与余额代扣并存（即 webhook 不应废弃），则 webhook 保留 `customer_confirmed` 状态仅记录 `paid_at`/`payment_method`/`transaction_id` 而不改 status——实施前 `grep payment-notify webhooks.py` 确认 webhook 是否仍在用；若在用且业务需要区分，回退为仅记凭证不改状态。
- **map_method_to_action**：审计中间件若含 `/pay`、`/complete` 路径映射，路由删除后成为死分支。实施时 grep 确认；存在则删除分支+对应测试，保持无死代码。
- **预置角色权限变更不影响存量角色**：seed.py 的 PRESET_ROLES 仅对新建角色生效（get_or_create 已存在则跳过）。存量运营/销售经理角色需管理员在角色权限页手动勾选新权限，或 `python scripts/seed.py --reset`（ destructive，仅在测试环境）。
