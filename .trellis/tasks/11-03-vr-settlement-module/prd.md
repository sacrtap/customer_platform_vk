# PRD：VR编辑费用结算模块

## Goal

在「结算管理」菜单下新增 **VR编辑费用结算** 模块（位于「结算单管理」下方），复用现有结算单（Invoice）模块的工程模式（Sanic + SQLAlchemy 异步 + RBAC + Alembic + Arco 前端），实现 VR 编辑费用结算单的全流程管理：手动创建 → 客服主管审批 → 销售审批 → 销售主管审批（含减免一并审批）→ 客户确认（自动扣款）→ 完成。

## Background（已核实事实）

现有结算单模块（Invoice）提供了完整的可复用基座，本次全部实测确认：

| 能力 | 现状锚点 |
|---|---|
| 扣款（行级锁 + tenacity 3 次重试 + 先赠后实 + 事务自收敛） | `backend/app/services/billing.py:222-343` `BalanceService.consume`，构造方式 `BalanceService(BalanceRepository(self.db))` |
| 确认后自动扣款模式 | `backend/app/services/billing.py:1884-1921` `_execute_deduction`：先 commit `customer_confirmed` 再扣款，失败保持该状态可重试；扣款失败返回 `(False, "客户确认成功，但扣款失败：{msg}")`，OperationalError 降级为「数据库繁忙，请稍后重试」 |
| 结算单号生成规则 | `backend/app/services/billing.py:1389-1394`：`{前缀}-{CST日期}-{customer_id}-{4位随机码}` |
| 销售身份校验 | `backend/app/services/billing.py:1821-1823`：`customer.sales_manager_id != user_id` → 「您不是该客户指定的销售，无权确认」 |
| 数据可见性 scope | `backend/app/routes/billing/invoices.py:58-72` `_ensure_invoice_scope` + `customer_scope_user_id` |
| 减免修改 + 历史 | `backend/app/services/billing.py:1557-1613` `apply_discount`（允许状态 draft/pending_ops/pending_sales，`discount_amount==0` 拒绝）+ `invoice_discount_histories` 表 |
| 权限体系 | `backend/scripts/seed.py` `ALL_PERMISSIONS`(44-75) + `PRESET_ROLES`(185-263，现仅「运营经理」「销售经理」)；迁移头 `c9d0e1f2a3b4` |
| 权限防漂移守护 | `tests/unit/test_permission_drift.py`（后端 `require_permission` + 前端 `can()`/`requiresPermission` 字面量必须是 seed 子集；反向断言无豁免裸端点）+ `tests/unit/test_test_data_consistency.py`（`tests/_test_data.py` ⊆ seed） |
| 文件上传/下载 | `POST /files/upload` 通用上传（前端封装 `api/billing.ts:532-536` `uploadDiscountAttachment`）；`main.py:281` 已挂 `/uploads/` 静态路由 |
| 前端同构原型 | `views/billing/Invoices.vue`(925 行)、`composables/useInvoice.ts`(494 行)、`constants/invoiceStatus.ts`、`components/DataTable.vue`、`components/ui/FilterDropdown.vue`、`components/CustomerAutoComplete.vue`、四个弹窗组件 |

## Requirements

### R1 数据模型与迁移
- 新建 `vr_settlements` 表（VR结算单主表）与 `vr_settlement_discount_histories` 表（减免修改历史），模型照抄 `Invoice`/`InvoiceDiscountHistory` 风格（`Mapped`/`mapped_column` + `BaseModel`）。
- `consumption_records` 表新增 `vr_settlement_id` 可空外键，用于关联 VR 扣款产生的消耗记录。
- Alembic 迁移 `d0e1f2a3b4c5`（down_revision `c9d0e1f2a3b4`）：建两表 + 加列加索引 + 幂等插入 8 个权限码并关联超级管理员。
- `models/__init__.py` 注册新模块。

### R2 权限码与预置角色
- 8 个新权限码：`vr_settlement:view / create / edit / delete / cs_approve / sales_approve / sales_supervisor_approve / confirm`（module=`vr_settlement`）。
- 「运营经理」追加 view/create/edit/confirm；「销售经理」追加 view/sales_approve；新增预置角色「客服主管」（view+cs_approve）、「销售主管」（view+sales_supervisor_approve）。
- 三处同步：`scripts/seed.py`（唯一事实源）、`tests/_test_data.py`（3 元组形态 `(code, name, module)`，测试⊆seed 守护）、迁移幂等 SQL。

### R3 服务层 `VrSettlementService`
状态机（每个流转方法返回 `tuple[bool, str]`）：

```
draft ─submit→ pending_cs_supervisor ─confirm-cs→ pending_sales ─confirm-sales→
pending_sales_supervisor ─confirm-sales-supervisor→ pending_customer ─confirm→
customer_confirmed ─扣款成功→ completed
任意非终态 ─cancel→ cancelled
pending_sales_supervisor ─reject→ pending_sales（减免保留待重新一并审批）
```

- 创建：`settlement_no = VR-{CST日期}-{customer_id}-{4位随机码}`，`status=draft`，`discount_amount=0`，`is_auto_generated=False`。
- 提交：校验 `customer.sales_manager_id` 非空，否则「该客户未指定销售经理，无法提交审批」。
- 销售审批：身份校验，非指定销售 → 「您不是该客户指定的销售，无权确认」。
- 销售主管审批通过：若 `discount_amount != 0`，一并写 `discount_approver_id/discount_approved_at/discount_approval_comment`。
- 销售主管驳回：退回 `pending_sales`，减免保持待审批。
- 减免：仅 `{draft, pending_cs_supervisor, pending_sales}` 可提交/修改；金额为 0 拒绝；每次写一条历史。
- 客户确认：先落库 `customer_confirmed` 再执行扣款；扣款走 `BalanceService.consume(customer_id=结算客户自身, amount=final_amount, vr_settlement_id=...)`；成功 → `completed`；失败保持 `customer_confirmed` 可重试。
- 取消：`{draft, pending_cs_supervisor, pending_sales, pending_sales_supervisor, pending_customer}`；删除：任意状态软删除。
- 扣减对象为**结算客户自身余额**（`customer_id`），不使用 Invoice 的 `settlement_account_id` 代扣机制（需求未提及）。

### R4 路由层（13 端点，前缀 `/api/v1/billing/vr-settlements`）

| # | 方法+路径 | 权限码 |
|---|---|---|
| 1 | GET `/vr-settlements` | `vr_settlement:view` |
| 2 | GET `/vr-settlements/<id>` | `vr_settlement:view` |
| 3 | POST `/vr-settlements` | `vr_settlement:create` |
| 4 | POST `/<id>/submit` | `vr_settlement:create` |
| 5 | POST `/<id>/confirm-cs` | `vr_settlement:cs_appro` |
| 6 | POST `/<id>/confirm-sales` | `vr_settlement:sales_approve` |
| 7 | POST `/<id>/confirm-sales-supervisor` | `vr_settlement:sales_supervisor_approve` |
| 8 | POST `/<id>/reject-sales-supervisor` | `vr_settlement:sales_supervisor_approve` |
| 9 | PUT `/<id>/discount` | `vr_settlement:edit` |
| 10 | POST `/<id>/confirm` | `vr_settlement:confirm` |
| 11 | POST `/<id>/retry-deduction` | `vr_settlement:confirm` |
| 12 | POST `/<id>/cancel` | `vr_settlement:edit` |
| 13 | DELETE `/<id>` | `vr_settlement:delete` |

统一模式：`@billing_bp.<m>` → `@auth_required` → `@require_permission`；查单 404 → scope 403 → service 调用 → 失败 400 透传 message → 成功 `invalidate_billing_cache()`。动作端点（4-8、10-12）手动审计（`create_audit_entry`，`record_type="vr_settlement"`），创建/减免/删除由审计中间件自动记录；`audit.py` 中间件跳过块追加 VR 动作端点防双写。

### R5 前端
- `api/vrSettlement.ts`：13 个 API 函数 + 类型定义（复用 `uploadDiscountAttachment` 上传明细文件）。
- `constants/vrSettlementStatus.ts`：8 状态中文映射 + 颜色 + 筛选选项。
- `composables/useVrSettlement.ts`：列表/详情/全部动作方法（无文件状态轮询）。
- `views/billing/VrSettlements.vue`：筛选行（关键词/状态/客户）+ DataTable（`:scroll="{x:1440}"`，storage-key `vr_settlements_table_columns`）+ 状态×权限×身份三维按钮显隐 + 行点击详情。
- 4 个组件：`VrSettlementCreateModal`（手动/自动单选，自动禁用+「待开发」标签）、`VrSettlementDiscountModal`、`VrSettlementApprovalModal`（approve/reject）、`VrSettlementDetailDrawer`（6 步流程条 + 减免区 + 明细文件下载 + 操作按钮）。
- 路由 `/billing/vr-settlements`（`requiresPermission: 'vr_settlement:view'`）、`useAppLayout` navSections + pageTitle、`AppSidebar` 「结算单管理」下方新按钮、`permissionGroups` 加 `vr_settlement` 模块。

### R6 测试
- 集成测试 `tests/integration/test_vr_settlement_api.py`：全流程、减免一并审批、减免编辑窗口、驳回回流、非法流转、销售身份校验、提交需指定销售、取消删除、可见性 scope 共 9 组用例；fixture 造客户（含 `sales_manager_id`）+ 1000 余额。
- 前端单测 `src/composables/__tests__/useVrSettlement.test.ts`：排序传递、搜索重置、动作调用。
- conftest TRUNCATE 列表加两新表。

## Acceptance Criteria

1. **AC1 创建**：手动创建（客户+周期+金额+上传 xlsx）→ 201，`settlement_no` 形如 `VR-20261103-<客户ID>-XXXX`，状态 `draft`，`final_amount == total_amount`。
2. **AC2 全流程**：draft → submit → confirm-cs → confirm-sales → confirm-sales-supervisor(comment) → confirm，终态 `completed`。
3. **AC3 自动扣款**：确认后客户余额 `used_total += final_amount`、可用余额 `-= final_amount`；`consumption_records` 新增一行 `amount=final_amount, vr_settlement_id=<id>, balance_after` 正确。
4. **AC4 减免一并审批**：待销售节点设置减免 100（总 1000）→ 销售主管审批通过后 `discount_approver_id/approved_at/approval_comment` 落库、`final_amount=900`、扣款 900；历史表有对应行。
5. **AC5 减免窗口**：`pending_sales_supervisor` 及之后 `PUT /discount` → 400；draft/待客服主管/待销售可改；金额 0 → 400「减免金额不能为 0」。
6. **AC6 驳回回流**：无 comment 驳回 → 400「驳回必须填写理由」；带 comment → 状态回 `pending_sales`，销售重新确认可再进销售主管审批；减免保留。
7. **AC7 非法流转**：draft 直接 confirm-cs → 400；completed 后 cancel → 400；非 pending_sales 时 confirm-sales → 400。
8. **AC8 身份校验**：非客户指定销售 confirm-sales → 400「您不是该客户指定的销售，无权确认」。
9. **AC9 提交前置**：客户无 `sales_manager_id` → submit → 400「该客户未指定销售经理，无法提交审批」。
10. **AC10 取消/删除**：非终态 cancel → `cancelled`，再 cancel → 400；draft DELETE → 软删除，再 GET 详情 404。
11. **AC11 可见性**：无 `customers:view_all` 用户访问非本人负责客户的结算单 → 403；列表仅返回本人负责客户的单。
12. **AC12 前端**：侧边栏出现「VR编辑费用结算」入口（`vr_settlement:view`）；创建弹窗「自动创建」禁用且带「待开发」标签；各状态×权限×身份按钮显隐/禁用符合规则表；详情抽屉 6 步流程条、减免区、明细文件📄可下载。
13. **AC13 权限三层一致**：`test_permission_drift.py` + `test_test_data_consistency.py` 通过（seed/路由/前端/测试数据四层 8 码一致）；角色权限页「VR编辑费用结算」分组展示 8 码。

## Out of Scope（明确不做）

- Excel 明细解析入库（文件仅上传存档 + 下载，金额由表单填写）
- 批量操作（提交/取消/删除）
- 导入导出
- 自动创建的后端实现（仅前端禁用态占位）
- 定时任务、待办聚合接入
- 结算账户代扣（`settlement_account_id`）机制——VR 扣客户自身余额

## Technical Notes（实施修正，相对原 PLAN 的 4 处偏差）

1. `tests/_test_data.py` 的 `PERMISSION_ROWS` 为 **3 元组** `(code, name, module)`（非四元组），按该形态追加 8 码。
2. 列表页 `:scroll` 用 `{ x: 1440 }`（与 Invoices.vue 实测一致，PLAN 中 1442 为笔误）。
3. discount_history 按 `applied_at` **倒序**（与现有 invoice 详情路由 `invoices.py:247-255` 一致）。
4. 扣款失败时 service 返回 `(False, "客户确认成功，但扣款失败：…")`（与 `_execute_deduction` 现有约定一致，PLAN 表格中 `(True, …)` 为笔误）；HTTP 层 400 透传，单状态保持 `customer_confirmed` 可重试。
